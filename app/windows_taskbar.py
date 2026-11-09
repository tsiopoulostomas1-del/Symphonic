import ctypes
import logging
import os
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer


logger = logging.getLogger(__name__)

WM_COMMAND = 0x0111
THBN_CLICKED = 0x1800
BUTTON_PREVIOUS = 1
BUTTON_PLAY_PAUSE = 2
BUTTON_NEXT = 3


class _Guid(ctypes.Structure):
    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", ctypes.c_ubyte * 8),
    ]


class _ThumbButton(ctypes.Structure):
    _fields_ = [
        ("dwMask", wintypes.DWORD),
        ("iId", wintypes.UINT),
        ("iBitmap", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 260),
        ("dwFlags", wintypes.DWORD),
    ]


class _NativeMessage(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wintypes.DWORD),
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


def _guid(data1, data2, data3, data4):
    value = _Guid()
    value.data1 = data1
    value.data2 = data2
    value.data3 = data3
    value.data4[:] = data4
    return value


class WindowsTaskbarControls(QAbstractNativeEventFilter):
    """Windows thumbnail-toolbar controls for the main player window."""

    def __init__(self, previous, toggle_play_pause, next_track):
        super().__init__()
        if os.name != "nt":
            raise OSError("Windows taskbar controls are only available on Windows.")

        self._ole32 = ctypes.OleDLL("ole32")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._initialized_com = False
        self._taskbar = ctypes.c_void_p()
        self._icons = {}
        self._added_hwnd = None
        self._playing = False
        self._commands = {
            BUTTON_PREVIOUS: previous,
            BUTTON_PLAY_PAUSE: toggle_play_pause,
            BUTTON_NEXT: next_track,
        }

        self._initialize_com()
        try:
            self._create_taskbar()
            self._icons = {
                "previous": self._create_icon("previous"),
                "play": self._create_icon("play"),
                "pause": self._create_icon("pause"),
                "next": self._create_icon("next"),
            }
            self.taskbar_button_created = self._register_taskbar_message()
        except Exception:
            self.close()
            raise

    def _initialize_com(self):
        self._ole32.CoInitialize.argtypes = [ctypes.c_void_p]
        self._ole32.CoInitialize.restype = ctypes.c_long
        result = self._ole32.CoInitialize(None)
        if result < 0:
            raise OSError(result, "Could not initialize COM for taskbar controls.")
        self._initialized_com = True

    def _create_taskbar(self):
        self._ole32.CoCreateInstance.argtypes = [
            ctypes.POINTER(_Guid),
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_Guid),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._ole32.CoCreateInstance.restype = ctypes.c_long
        class_id = _guid(
            0x56FDF344,
            0xFD6D,
            0x11D0,
            (0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90),
        )
        interface_id = _guid(
            0xEA1AFB91,
            0x9E28,
            0x4B86,
            (0x90, 0xE9, 0x9E, 0x9F, 0x8A, 0x5E, 0xEF, 0xAF),
        )
        result = self._ole32.CoCreateInstance(
            ctypes.byref(class_id),
            None,
            0x1,
            ctypes.byref(interface_id),
            ctypes.byref(self._taskbar),
        )
        self._check_hresult(result, "Could not create the Windows taskbar interface.")
        self._call(3, ctypes.c_long)

    def _call(self, index, return_type, *arguments):
        vtable = ctypes.cast(
            self._taskbar, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        prototype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
            return_type, ctypes.c_void_p, *[kind for kind, _ in arguments]
        )
        function = prototype(vtable[index])
        values = [value for _, value in arguments]
        result = function(self._taskbar, *values)
        self._check_hresult(result, "Windows taskbar operation failed.")
        return result

    @staticmethod
    def _check_hresult(result, message):
        if result < 0:
            raise OSError(result, message)

    def _register_taskbar_message(self):
        self._user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
        self._user32.RegisterWindowMessageW.restype = wintypes.UINT
        message = self._user32.RegisterWindowMessageW("TaskbarButtonCreated")
        if not message:
            raise ctypes.WinError(ctypes.get_last_error())
        logger.info("Registered taskbar button notification %#x", message)
        logger.info("Registered Windows taskbar button-created message: %#x", message)
        return message

    def _create_icon(self, name):
        pixels = [[False] * 16 for _ in range(16)]
        if name == "play":
            for y in range(3, 13):
                for x in range(3, 14 - (abs(8 - y) * 2)):
                    pixels[y][x] = True
        elif name == "pause":
            for y in range(3, 13):
                for x in (*range(4, 7), *range(10, 13)):
                    pixels[y][x] = True
        elif name in ("previous", "next"):
            for y in range(3, 13):
                inset = abs(8 - y)
                if name == "previous":
                    pixels[y][1] = True
                    pixels[y][2] = True
                    for x in range(3 + inset, 13):
                        pixels[y][x] = True
                else:
                    pixels[y][13] = True
                    pixels[y][14] = True
                    for x in range(3, 13 - inset):
                        pixels[y][x] = True

        and_mask = bytearray([0xFF] * 32)
        xor_mask = bytearray(32)
        for y in range(16):
            for x in range(16):
                if pixels[y][x]:
                    row = 15 - y
                    byte_index = row * 2 + x // 8
                    bit = 1 << (7 - x % 8)
                    and_mask[byte_index] &= ~bit
                    xor_mask[byte_index] |= bit

        self._user32.CreateIcon.argtypes = [
            wintypes.HINSTANCE,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.BYTE,
            wintypes.BYTE,
            ctypes.POINTER(wintypes.BYTE),
            ctypes.POINTER(wintypes.BYTE),
        ]
        self._user32.CreateIcon.restype = wintypes.HICON
        self._user32.DestroyIcon.argtypes = [wintypes.HICON]
        self._user32.DestroyIcon.restype = wintypes.BOOL
        and_bits = (wintypes.BYTE * len(and_mask)).from_buffer(and_mask)
        xor_bits = (wintypes.BYTE * len(xor_mask)).from_buffer(xor_mask)
        icon = self._user32.CreateIcon(
            None, 16, 16, 1, 1, and_bits, xor_bits
        )
        if not icon:
            raise ctypes.WinError(ctypes.get_last_error())
        return icon

    def _buttons(self):
        play_icon = self._icons["pause" if self._playing else "play"]
        return (_ThumbButton * 3)(
            _ThumbButton(0x2 | 0x4 | 0x8, BUTTON_PREVIOUS, 0,
                        self._icons["previous"], "Previous", 0),
            _ThumbButton(0x2 | 0x4 | 0x8, BUTTON_PLAY_PAUSE, 0,
                        play_icon, "Pause" if self._playing else "Play", 0),
            _ThumbButton(0x2 | 0x4 | 0x8, BUTTON_NEXT, 0,
                        self._icons["next"], "Next", 0),
        )

    def add_buttons(self, hwnd):
        buttons = self._buttons()
        self._call(
            15,
            ctypes.c_long,
            (wintypes.HWND, hwnd),
            (wintypes.UINT, len(buttons)),
            (ctypes.POINTER(_ThumbButton), buttons),
        )
        self._added_hwnd = hwnd
        logger.info("Added playback controls to taskbar window handle %#x", hwnd)

    def set_playing(self, playing):
        self._playing = playing
        if self._added_hwnd is None:
            return
        QTimer.singleShot(0, self._update_buttons)

    def _update_buttons(self):
        if self._added_hwnd is None:
            return
        buttons = self._buttons()
        try:
            self._call(
                16,
                ctypes.c_long,
                (wintypes.HWND, self._added_hwnd),
                (wintypes.UINT, len(buttons)),
                (ctypes.POINTER(_ThumbButton), buttons),
            )
        except OSError:
            logger.warning(
                "Could not update Windows taskbar playback controls.",
                exc_info=True,
            )

    def process_native_message(self, message_address):
        message = ctypes.cast(
            message_address, ctypes.POINTER(_NativeMessage)
        ).contents
        if message.message == self.taskbar_button_created:
            try:
                self.add_buttons(message.hwnd)
            except OSError:
                logger.warning(
                    "Could not add Windows taskbar playback controls.",
                    exc_info=True,
                )
            return False

        if message.message != WM_COMMAND:
            return False
        if self._added_hwnd is None or message.hwnd != self._added_hwnd:
            return False
        command = message.wParam & 0xFFFF
        notification = (message.wParam >> 16) & 0xFFFF
        callback = self._commands.get(command)
        if notification != THBN_CLICKED or callback is None:
            return False
        callback()
        return True

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) not in (
            b"windows_generic_MSG",
            b"windows_dispatcher_MSG",
        ):
            return False
        return self.process_native_message(int(message))

    def close(self):
        if self._taskbar:
            vtable = ctypes.cast(
                self._taskbar, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
            ).contents
            release = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
                wintypes.ULONG, ctypes.c_void_p
            )(vtable[2])
            release(self._taskbar)
            self._taskbar = ctypes.c_void_p()

        if hasattr(self, "_user32"):
            for icon in self._icons.values():
                self._user32.DestroyIcon(icon)
        self._icons.clear()

        if self._initialized_com:
            self._ole32.CoUninitialize()
            self._initialized_com = False
