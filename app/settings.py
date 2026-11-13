import os
import json
import base64
import ctypes
import tempfile
from ctypes import wintypes

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".symphonic")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
ENCRYPTED_PASSWORD_PREFIX = "dpapi:"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _protect_windows_password(password: str) -> str:
    if os.name != "nt":
        return password

    data = password.encode("utf-8")
    input_buffer = ctypes.create_string_buffer(data)
    input_blob = _DataBlob(
        len(data), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    output_blob = _DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return ENCRYPTED_PASSWORD_PREFIX + base64.b64encode(encrypted).decode("ascii")
    finally:
        _free_windows_blob(output_blob)


def _unprotect_windows_password(password: str) -> str:
    if not password.startswith(ENCRYPTED_PASSWORD_PREFIX):
        return password
    if os.name != "nt":
        raise OSError("This saved password can only be decrypted on Windows.")

    encrypted = base64.b64decode(password[len(ENCRYPTED_PASSWORD_PREFIX):])
    input_buffer = ctypes.create_string_buffer(encrypted)
    input_blob = _DataBlob(
        len(encrypted), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    output_blob = _DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        _free_windows_blob(output_blob)


def _free_windows_blob(blob: _DataBlob):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    local_free(blob.pbData)

def load_settings() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                settings = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {
                "server": "",
                "username": "",
                "password": "",
                "language": "en",
                "theme": "midnight",
            }
        stored_password = settings.get("password", "")
        settings["password"] = _unprotect_windows_password(stored_password)

        settings.setdefault("language", "en")
        settings.setdefault("theme", "midnight")

        if os.name == "nt" and not stored_password.startswith(ENCRYPTED_PASSWORD_PREFIX):
            save_settings(
                settings.get("server", ""),
                settings.get("username", ""),
                settings["password"],
                settings["language"],
                settings["theme"],
            )
        return settings

    return {"server": "",
            "username": "",
            "password": "",
            "language": "en",
            "theme": "midnight"}


def save_settings(
    server: str,
    username: str,
    password: str,
    language: str = "en",
    theme: str = "midnight",
):
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    with open(CONFIG_FILE, "w") as f:
        json.dump(
            {
                "server": server,
                "username": username,
                "password": _protect_windows_password(password),
                "language": language,
                "theme": theme,
            },
            f,
        )


def save_theme(theme: str) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        if not isinstance(settings, dict):
            raise ValueError("The settings file must contain a JSON object.")
    else:
        settings = {
            "server": "",
            "username": "",
            "password": "",
            "language": "en",
        }

    settings["theme"] = theme
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_DIR,
            suffix=".tmp",
            delete=False,
        ) as settings_file:
            temporary_path = settings_file.name
            json.dump(settings, settings_file)
        os.replace(temporary_path, CONFIG_FILE)
    except OSError:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise