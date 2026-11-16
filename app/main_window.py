import logging
import os
import random

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QListWidgetItem, QLabel, QWidget,
    QPushButton, QGraphicsOpacityEffect, QLineEdit, QTextEdit, QPlainTextEdit,
    QAbstractSpinBox,
)
from PySide6.QtCore import (
    Qt, QEvent, QPoint, QRect, QRectF, QUrl, QPropertyAnimation,
    QEasingCurve, QTimer, QThread, Signal, Slot,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtGui import QPixmap, QColor, QIcon, QPainter, QPainterPath
from shiboken6 import isValid

from app.app_state import load_app_state, save_app_state
from app.artwork_cache import ArtworkCache
from app.branding import app_icon
from app.player import Player
from app.subsonic import SubsonicClient
from app.settings import load_settings, save_theme
from app.themes import THEMES, build_stylesheet
from app.translations import translate
from app.widgets.settings_dialog import SettingsDialog
from app.widgets.ui_settings_dialog import UISettingsDialog
from app.window_ui import MainWindowUI
from app.window_library import MainWindowLibrary
from app.window_playback import MainWindowPlayback
from app.windows_taskbar import WindowsTaskbarControls

logger = logging.getLogger(__name__)

ARTIST_COVER_ROLE = Qt.UserRole + 1
ARTIST_ARTWORK_REQUESTED_ROLE = Qt.UserRole + 2


class LibraryLoader(QThread):
    loaded = Signal(int, object, object)
    completed = Signal(int, object)
    failed = Signal(int, object, str)
    progress = Signal(int, str)

    def __init__(self, request_id, client, language="en"):
        super().__init__()
        self.request_id = request_id
        self.client = client
        self.language = language

    def text(self, key, **values):
        return translate(self.language, key, **values)

    def run(self):
        stage = self.text("server_connection")
        try:
            self.progress.emit(self.request_id, self.text("checking_server"))
            if not self.client.ping():
                raise ConnectionError(
                    self.client.ping_error or self.text("could_not_connect_server")
                )

            stage = self.text("albums")
            self.progress.emit(self.request_id, self.text("loading_albums"))
            albums = self.client.get_albums()
            self.loaded.emit(self.request_id, self.client, {"albums": albums})

            stage = self.text("artists")
            self.progress.emit(self.request_id, self.text("loading_artists"))
            artists = self.client.get_artists()
            self.loaded.emit(self.request_id, self.client, {"artists": artists})

            stage = self.text("songs")
            self.progress.emit(self.request_id, self.text("loading_songs"))
            songs = self.client.get_all_songs(
                albums,
                progress_callback=lambda current, total: self.progress.emit(
                    self.request_id,
                    self.text(
                        "loading_songs_progress", current=current, total=total
                    ),
                ),
            )
            self.loaded.emit(self.request_id, self.client, {"songs": songs})

            stage = self.text("playlists")
            self.progress.emit(self.request_id, self.text("loading_playlists"))
            playlists = self.client.get_playlists()
            self.loaded.emit(
                self.request_id, self.client, {"playlists": playlists}
            )
            self.completed.emit(self.request_id, self.client)
        except Exception as exc:
            self.failed.emit(
                self.request_id,
                self.client,
                self.text("library_stage_failed", stage=stage, error=exc),
            )


class MainWindow(MainWindowUI, MainWindowLibrary, MainWindowPlayback, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Symphonic")
        self.setWindowIcon(app_icon())
        self.resize(1100, 750)

        self.network_manager = QNetworkAccessManager()
        self.artwork_cache = ArtworkCache()
        
        self.settings = load_settings()
        self.language = self.settings.get("language", "en")
        self.accent_color = THEMES.get(
            self.settings.get("theme", "midnight"), THEMES["midnight"]
        )["accent"]
        self.app_state = load_app_state()
        self.recently_played = self.app_state.get("recently_played", [])
        if not isinstance(self.recently_played, list):
            self.recently_played = []
        else:
            self.recently_played = [
                song for song in self.recently_played if isinstance(song, dict)
            ][:20]
        self.sync_state_server()
        self.client = None
        self.background_workers = []
        self.library_load_id = 0
        self.lyrics_request_id = 0
        self.artist_details_request_id = 0
        self.search_request_id = 0
        self.search_results_data = []
        self.songs_data = []
        self.artists_data = []
        self.albums_data = []
        self.current_song_id = None
        self.playback_restored = False
        self.scrobbled_song_id = None
        self.last_playback_position = None
        self.listened_ms = 0
        self.current_artist_name = None
        self.album_animations = []
        
        self.current_album_songs = []
        self.current_album_id = None
        self.current_artist_albums = []
        self.current_artist_id = None
        
        self.liked_songs_data = []
        self.current_playlists = []
        self.current_playlist_id = None
        self.current_playlist_songs = []
        self.showing_liked_songs = False
        
        self.lyrics_lines = [] 
        self.current_lyric_index = -1
        self.lyric_labels = []
        
        self.lyrics_timer = QTimer()
        self.lyrics_timer.setInterval(30) 
        self.lyrics_timer.timeout.connect(self.update_lyrics_sync)

        if self.settings.get("server"):
            self.client = SubsonicClient(
                self.settings["server"], 
                self.settings["username"], 
                self.settings["password"]
            )

        self.player = Player()
        self.player.position_changed.connect(self.update_seek_bars)
        self.player.duration_changed.connect(self.set_seek_bar_ranges)
        self.player.playback_state_changed.connect(self.update_play_buttons)
        self.player.track_changed.connect(self.on_track_changed)
        self.taskbar_controls = None
        if os.name == "nt":
            try:
                self.taskbar_controls = WindowsTaskbarControls(
                    self.player.prev,
                    self.player.toggle_play_pause,
                    self.player.next,
                )
                application = QApplication.instance()
                if application is not None:
                    application.installNativeEventFilter(self.taskbar_controls)
            except OSError:
                logger.warning(
                    "Windows taskbar playback controls are unavailable.",
                    exc_info=True,
                )

        self.setup_main_ui()
        self.update_active_navigation(self.content_stack.currentIndex())
        self.artists_list.verticalScrollBar().valueChanged.connect(
            self.load_visible_artist_art
        )
        self.albums_scroll.verticalScrollBar().valueChanged.connect(
            self.load_visible_album_art
        )
        self.artist_albums_scroll.verticalScrollBar().valueChanged.connect(
            self.load_visible_album_art
        )
        self.content_stack.currentChanged.connect(
            lambda index: QTimer.singleShot(0, self.schedule_visible_artwork)
            if index >= 0
            else None
        )
        self.view_transition_effect = QGraphicsOpacityEffect(self.content_stack)
        self.content_stack.setGraphicsEffect(self.view_transition_effect)
        self.view_transition_animation = None
        self.setup_player_ui()
        self.playback_state_timer = QTimer(self)
        self.playback_state_timer.setInterval(10000)
        self.playback_state_timer.timeout.connect(self.save_playback_state)
        self.playback_state_timer.start()
        self.setup_overlays()
        self.retranslate_ui()
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)
        QTimer.singleShot(0, self.setup_taskbar_controls)
        QTimer.singleShot(0, self.load_visible_album_art)
        QTimer.singleShot(0, self.load_all_data)

    def schedule_visible_artwork(self):
        self.load_visible_album_art()
        self.load_visible_artist_art()

    def setup_taskbar_controls(self):
        if self.taskbar_controls:
            self.taskbar_controls.set_playing(
                self.player.media_player.playbackState()
                == QMediaPlayer.PlayingState
            )

    def text(self, key, **values):
        return translate(self.language, key, **values)

    def retranslate_ui(self):
        self.setWindowTitle("Symphonic")
        for button, key in (
            (self.btn_nav_artists, "artists"),
            (self.btn_nav_albums, "albums"),
            (self.btn_nav_songs, "songs"),
            (self.btn_nav_queue, "queue"),
            (self.btn_nav_nowplaying, "now_playing"),
            (self.btn_nav_recent, "recently_played"),
            (self.btn_liked_songs, "liked_songs"),
            (self.btn_nav_settings, "settings"),
            (self.btn_ui_settings, "ui_settings"),
            (self.retry_library_button, "retry"),
            (self.btn_play_album, "play_album"),
            (self.resume_playback_button, "continue_listening"),
        ):
            button.setText(self.text(key))

        self.shuffle_albums_button.setText(self.text("shuffle_albums"))
        self.clear_genre_filter_button.setText(self.text("clear"))
        selected_genre = self.genre_filter.currentText()
        self.genre_filter.blockSignals(True)
        self.genre_filter.setItemText(0, self.text("all_genres"))
        if selected_genre:
            selected_index = self.genre_filter.findText(selected_genre)
            if selected_index >= 0:
                self.genre_filter.setCurrentIndex(selected_index)
        self.genre_filter.blockSignals(False)

        self.playlist_label.setText(self.text("playlists"))
        self.search_input.setPlaceholderText(self.text("search_library"))
        self.page_title.setText(
            self.text(
                (
                    "artists", "albums", "songs", "queue", "search_results",
                    "album_details", "artist_details", "playlist",
                    "recently_played",
                )[self.content_stack.currentIndex()]
            )
        )
        self.songs_table.setHorizontalHeaderLabels([
            self.text("title"), self.text("artist"), self.text("album"),
            self.text("time"),
        ])
        self.queue_table.setHorizontalHeaderLabels([
            self.text("title"), self.text("artist"), self.text("album"),
        ])
        self.ad_table.setHorizontalHeaderLabels([
            self.text("track_number"), self.text("title"), self.text("time"), "",
        ])
        self.pd_table.setHorizontalHeaderLabels([
            self.text("track_number"), self.text("title"), self.text("artist"),
            self.text("time"),
        ])
        self.disc_title.setText(self.text("discography"))
        if self.showing_liked_songs and self.content_stack.currentIndex() == 7:
            self.pd_type.setText(self.text("collection"))
            self.pd_title.setText(self.text("liked_songs"))
            self.pd_meta.setText(
                self.text("songs_count", count=len(self.liked_songs_data))
            )
        elif self.content_stack.currentIndex() == 7:
            self.pd_type.setText(self.text("playlist").upper())
            self.pd_meta.setText(
                self.text("songs_count", count=len(self.current_playlist_songs))
            )

        current_song = next(
            (
                item["song_data"]
                for item in self.player.queue
                if item["song_data"].get("id") == self.current_song_id
            ),
            None,
        )
        if current_song:
            title = current_song.get("title", self.text("unknown"))
            artist = current_song.get("artist", self.text("unknown"))
            self.np_title.setText(title)
            self.np_title.setToolTip(title)
            self.np_artist.setText(artist)
            self.big_title.setText(title)
            self.big_artist.setText(artist)
        else:
            self.np_title.setText(self.text("not_playing"))
            self.np_title.setToolTip("")
            self.np_artist.setText(self.text("select_track"))
            self.big_title.setText(self.text("not_playing"))

        self.btn_like.setToolTip(
            self.text("unlike") if self.btn_like.text() == "♥"
            else self.text("like")
        )
        self.btn_lyrics.setToolTip(self.text("lyrics"))
        self.btn_shuffle.setToolTip(self.text("shuffle"))
        self.btn_prev.setToolTip(self.text("previous"))
        self.btn_next.setToolTip(self.text("next"))
        self.btn_repeat.setToolTip(self.text("repeat"))
        for close_button in (
            self.now_playing_overlay.findChild(QPushButton),
            self.lyrics_overlay.findChild(QPushButton),
        ):
            if close_button:
                close_button.setToolTip(self.text("close"))
        if self.player.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.btn_play.setToolTip(self.text("pause"))
        else:
            self.btn_play.setToolTip(self.text("play"))
        self.populate_recently_played()
        self.volume_label.setText(self.text("volume"))
        if self.songs_data:
            self.populate_songs_table(self.songs_data)
        self.populate_queue_table()
        self.update_resume_button()

    @staticmethod
    def _album_key(item, is_album=False):
        album_id = item.get("albumId")
        if is_album and not album_id:
            album_id = item.get("id")
        if album_id:
            return f"id:{album_id}"

        album_name = item.get("albumName") or item.get("album") or item.get("name")
        if isinstance(album_name, dict):
            album_name = album_name.get("name", "")
        artist = item.get("artist", "")
        if isinstance(artist, dict):
            artist = artist.get("name", "")
        return f"name:{str(album_name).casefold()}|{str(artist).casefold()}"

    @staticmethod
    def _item_genres(item):
        genres = set()
        for field in ("genre", "genres"):
            values = item.get(field, [])
            if isinstance(values, (str, dict)):
                values = [values]
            elif not isinstance(values, (list, tuple, set)):
                continue
            for value in values:
                if isinstance(value, dict):
                    value = value.get("name", "")
                if isinstance(value, str) and value.strip():
                    genres.add(value.strip())
        return genres

    def update_album_genre_options(self):
        genres = {}
        for album in self.albums_data:
            for genre in self._item_genres(album):
                genres.setdefault(genre.casefold(), genre)
        for song in self.songs_data:
            for genre in self._item_genres(song):
                genres.setdefault(genre.casefold(), genre)

        selected_genre = self.genre_filter.currentText()
        self.genre_filter.blockSignals(True)
        self.genre_filter.clear()
        self.genre_filter.addItem(self.text("all_genres"))
        self.genre_filter.addItems(
            sorted(genres.values(), key=str.casefold)
        )
        selected_index = self.genre_filter.findText(selected_genre)
        if selected_index >= 0:
            self.genre_filter.setCurrentIndex(selected_index)
        self.genre_filter.blockSignals(False)

    def filter_albums_by_genre(self, _index):
        self.render_album_grid()

    def render_album_grid(self):
        if not hasattr(self, "albums_grid"):
            return

        self.stop_album_animations()
        selected_genre = (
            self.genre_filter.currentText()
            if hasattr(self, "genre_filter")
            and self.genre_filter.currentIndex() > 0
            else ""
        )
        song_genres = {}
        for song in self.songs_data:
            song_genres.setdefault(self._album_key(song), set()).update(
                self._item_genres(song)
            )

        albums = [
            album for album in self.albums_data
            if not selected_genre
            or selected_genre.casefold() in {
                genre.casefold()
                for genre in (
                    self._item_genres(album)
                    | song_genres.get(
                        self._album_key(album, is_album=True), set()
                    )
                )
            }
        ]

        while self.albums_grid.count():
            item = self.albums_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for index, album in enumerate(albums):
            self.add_album_card(
                album,
                self.albums_grid,
                index // 5,
                index % 5,
            )
        QTimer.singleShot(0, self.load_visible_album_art)

    def shuffle_albums(self):
        song_groups = {}
        for song in self.songs_data:
            if song.get("id"):
                song_groups.setdefault(self._album_key(song), []).append(song)

        selected_genre = (
            self.genre_filter.currentText()
            if self.genre_filter.currentIndex() > 0
            else ""
        )
        songs = []
        for album in self.albums_data:
            album_songs = song_groups.get(
                self._album_key(album, is_album=True), []
            )
            album_genres = self._item_genres(album)
            for song in album_songs:
                album_genres.update(self._item_genres(song))
            if selected_genre and selected_genre.casefold() not in {
                genre.casefold() for genre in album_genres
            }:
                continue
            if album_songs:
                songs.append(random.choice(album_songs))

        if not songs:
            QMessageBox.information(
                self,
                self.text("shuffle_albums"),
                self.text("no_albums_to_shuffle"),
            )
            return

        random.shuffle(songs)
        self.player.is_shuffle = False
        self.player.is_repeat = False
        self.btn_shuffle.setStyleSheet("color: #64748B;")
        self.btn_repeat.setStyleSheet("color: #64748B;")
        self.play_songs(songs, 0)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Left, Qt.Key_Right)
            and isinstance(obj, QWidget)
            and obj.window() is self
        ):
            focused = QApplication.focusWidget()
            if not isinstance(
                focused, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)
            ):
                duration = self.player.media_player.duration()
                if duration > 0:
                    offset = -5000 if event.key() == Qt.Key_Left else 5000
                    position = self.player.media_player.position()
                    self.player.set_position(
                        max(0, min(position + offset, duration))
                    )
                    event.accept()
                    return True

        # ONLY trigger the hover logic if the lyrics overlay is currently visible!
        if self.lyrics_overlay.isVisible():
            if obj == self.hover_zone or obj == self.now_playing_bar:
                if event.type() == QEvent.Enter:
                    self.hide_bar_timer.stop() 
                    self.show_player_bar()
                elif event.type() == QEvent.Leave:
                    self.hide_bar_timer.start()
                
        return super().eventFilter(obj, event)
    def show_player_bar(self):
        if self.now_playing_bar.y() == self.height() - 90:
            return
            
        self.now_playing_bar.show()
        self.now_playing_bar.raise_()
        
        self.bar_anim = QPropertyAnimation(self.now_playing_bar, b"geometry")
        self.bar_anim.setDuration(200)
        self.bar_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        rect = self.now_playing_bar.geometry()
        start_rect = QRect(rect.x(), self.height(), rect.width(), rect.height())
        end_rect = QRect(0, self.height() - 90, self.width(), 90)
        
        self.bar_anim.setStartValue(start_rect)
        self.bar_anim.setEndValue(end_rect)
        self.bar_anim.start()
    def hide_player_bar(self):
        if self.now_playing_bar.y() >= self.height():
            return
            
        self.bar_anim = QPropertyAnimation(self.now_playing_bar, b"geometry")
        self.bar_anim.setDuration(200)
        self.bar_anim.setEasingCurve(QEasingCurve.InCubic)
        
        rect = self.now_playing_bar.geometry()
        start_rect = QRect(0, self.height() - 90, self.width(), 90)
        end_rect = QRect(rect.x(), self.height(), rect.width(), rect.height())
        
        self.bar_anim.setStartValue(start_rect)
        self.bar_anim.setEndValue(end_rect)
        
        self.bar_anim.finished.connect(self.now_playing_bar.hide)
        self.bar_anim.start()
    def switch_view(self, index):
        self.content_stack.setCurrentIndex(index)
        self.update_active_navigation(index)
        title_keys = [
            "artists", "albums", "songs", "queue", "search_results",
            "album_details", "artist_details", "playlist", "recently_played",
        ]
        self.page_title.setText(self.text(title_keys[index]))
        if index in (0, 1, 2, 3, 8):
            self.app_state["last_view"] = index
            self.save_current_app_state()

        if self.view_transition_animation:
            self.view_transition_animation.stop()
            self.view_transition_animation.deleteLater()
        self.view_transition_effect.setOpacity(0.82)
        self.view_transition_animation = QPropertyAnimation(
            self.view_transition_effect, b"opacity", self
        )
        self.view_transition_animation.finished.connect(
            self.view_transition_animation.deleteLater
        )
        self.view_transition_animation.finished.connect(
            lambda: setattr(self, "view_transition_animation", None)
        )
        self.view_transition_animation.setDuration(170)
        self.view_transition_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.view_transition_animation.setStartValue(0.82)
        self.view_transition_animation.setEndValue(1.0)
        self.view_transition_animation.start()
        
        if index in [5, 6, 7]:
            self.btn_back.show()
        else:
            self.btn_back.hide()
            
        if index == 3:
            self.populate_queue_table()

    def update_active_navigation(self, index):
        navigation_by_view = {
            0: self.btn_nav_artists,
            1: self.btn_nav_albums,
            2: self.btn_nav_songs,
            3: self.btn_nav_queue,
            4: self.btn_nav_songs,
            5: self.btn_nav_albums,
            6: self.btn_nav_artists,
            8: self.btn_nav_recent,
        }
        if index == 7 and self.showing_liked_songs:
            active_button = self.btn_liked_songs
        else:
            active_button = navigation_by_view.get(index)
        self.set_active_navigation(active_button)

    def go_back(self):
        current = self.content_stack.currentIndex()
        if current == 5:
            self.switch_view(1) 
        elif current == 6:
            self.switch_view(0) 
        elif current == 7:
            self.switch_view(2)
    def toggle_shuffle(self):
        active = self.player.toggle_shuffle()
        self.btn_shuffle.setStyleSheet(
            f"color: {self.accent_color};" if active else "color: #64748B;"
        )
    def toggle_repeat(self):
        active = self.player.toggle_repeat()
        self.btn_repeat.setStyleSheet(
            f"color: {self.accent_color};" if active else "color: #64748B;"
        )
    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = load_settings()
            self.language = self.settings.get("language", "en")
            self.retranslate_ui()
            self.sync_state_server()
            self.client = SubsonicClient(self.settings["server"], self.settings["username"], self.settings["password"])
            self.songs_data = []
            self.artists_data = []
            self.albums_data = []
            self.current_playlists = []
            self.search_results_data = []
            self.artists_list.clear()
            self.songs_table.setRowCount(0)
            self.playlists_list.clear()
            self.stop_album_animations()
            for i in reversed(range(self.albums_grid.count())): 
                widget = self.albums_grid.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            self.load_all_data()

    def open_ui_settings(self):
        dialog = UISettingsDialog(
            self.settings.get("theme", "midnight"),
            self.language,
            self,
        )
        if not dialog.exec():
            return

        theme = dialog.selected_theme
        if theme not in THEMES:
            return
        try:
            stylesheet = build_stylesheet(theme)
            save_theme(theme)
            application = QApplication.instance()
            if application:
                application.setStyleSheet(stylesheet)

            self.settings["theme"] = theme
            self.accent_color = THEMES[theme]["accent"]
            if self.btn_like.text() == "♥":
                self.btn_like.setStyleSheet(
                    f"color: {self.accent_color}; font-size: 20px;"
                )
            self.btn_shuffle.setStyleSheet(
                f"color: {self.accent_color};"
                if self.player.is_shuffle else "color: #64748B;"
            )
            self.btn_repeat.setStyleSheet(
                f"color: {self.accent_color};"
                if self.player.is_repeat else "color: #64748B;"
            )
            self.populate_songs_table(self.songs_data)
        except Exception:
            logger.exception("Could not apply the selected theme.")
            QMessageBox.critical(
                self, self.text("error"), self.text("theme_apply_failed")
            )
            return

    def load_all_data(self):
        if not self.client:
            self.library_progress.hide()
            self.library_status.setText(self.text("not_connected_setup"))
            self.open_settings()
            return

        self.library_load_id += 1
        load_id = self.library_load_id
        client = self.client
        worker = LibraryLoader(load_id, client, self.language)
        worker.loaded.connect(self.on_library_loaded)
        worker.completed.connect(self.on_library_load_completed)
        worker.failed.connect(self.on_library_load_failed)
        worker.progress.connect(self.on_library_load_progress)
        self.library_status.setText(self.text("connecting"))
        self.library_progress.show()
        self.retry_library_button.hide()
        self.keep_background_worker(worker)
        worker.start()
    def keep_background_worker(self, worker):
        self.background_workers.append(worker)
        worker.finished.connect(self.on_background_worker_finished)
    @Slot()
    def on_background_worker_finished(self):
        worker = self.sender()
        if worker in self.background_workers:
            self.background_workers.remove(worker)
    @Slot(int, object, object)
    def on_library_loaded(self, request_id, client, data):
        if request_id != self.library_load_id or client is not self.client:
            return
        if getattr(self, "_library_display_failure_id", None) == request_id:
            return

        try:
            self._apply_library_data(data)
        except Exception:
            logger.exception(
                "Could not display data returned by the library loader."
            )
            self._library_display_failure_id = request_id
            self.library_progress.hide()
            self.retry_library_button.show()
            self.library_status.setText(self.text("library_load_failed_status"))
            QMessageBox.warning(
                self,
                self.text("library_load_failed"),
                self.text("library_load_failed_status"),
            )

    def _apply_library_data(self, data):
        if "songs" in data:
            self.songs_data = data["songs"]
            self.populate_songs_table(self.songs_data)
            self.update_album_genre_options()
            self.render_album_grid()
            self._refresh_artist_cover_data()
            QTimer.singleShot(0, self.load_visible_artist_art)

        if "artists" in data:
            self.artists_data = data["artists"]
            self.artists_list.clear()
            self.artists_data = [
                artist for artist in self.artists_data
                if isinstance(artist, dict)
            ]
            for artist in self.artists_data:
                item = QListWidgetItem(artist.get("name", self.text("unknown")))
                item.setData(Qt.UserRole, artist.get("id"))
                self.artists_list.addItem(item)
            self._refresh_artist_cover_data()
            QTimer.singleShot(0, self.load_visible_artist_art)

        if "albums" in data:
            self.albums_data = data["albums"]
            self.update_album_genre_options()
            self.render_album_grid()
                
        if "playlists" in data:
            self.current_playlists = data["playlists"]
            self.playlists_list.clear()
            for playlist in self.current_playlists:
                item = QListWidgetItem(playlist.get("name", self.text("unknown")))
                item.setData(Qt.UserRole, playlist["id"])
                self.playlists_list.addItem(item)

        if "albums" in data:
            self.library_status.setText(
                self.text("loaded_albums", count=len(self.albums_data))
            )
        elif "artists" in data:
            self.library_status.setText(
                self.text("loaded_artists", count=len(self.artists_data))
            )
        elif "songs" in data:
            self.library_status.setText(
                self.text("loaded_songs", count=len(self.songs_data))
            )

    def _refresh_artist_cover_data(self):
        covers_by_artist_id = {}
        covers_by_artist_name = {}
        for media in self.albums_data + self.songs_data:
            cover_id = media.get("coverArt")
            if not cover_id:
                continue
            artist_id = media.get("artistId")
            if artist_id is not None:
                covers_by_artist_id.setdefault(str(artist_id), str(cover_id))
            artist_name = media.get("artist")
            if artist_name:
                covers_by_artist_name.setdefault(
                    str(artist_name).casefold(), str(cover_id)
                )

        for row, artist in enumerate(self.artists_data):
            item = self.artists_list.item(row)
            if item is None:
                continue
            cover_id = (
                artist.get("coverArt")
                or covers_by_artist_id.get(str(artist.get("id", "")))
                or covers_by_artist_name.get(
                    str(artist.get("name", "")).casefold()
                )
            )
            item.setData(ARTIST_COVER_ROLE, str(cover_id) if cover_id else "")

    def load_visible_artist_art(self):
        viewport = self.artists_list.viewport()
        viewport_rect = viewport.rect()
        first = self.artists_list.indexAt(QPoint(8, 0))
        if not first.isValid():
            return
        last = self.artists_list.indexAt(
            QPoint(8, max(0, viewport_rect.height() - 1))
        )
        last_row = last.row() if last.isValid() else self.artists_list.count() - 1

        for row in range(first.row(), last_row + 1):
            item = self.artists_list.item(row)
            if item is None or not self.artists_list.visualItemRect(item).intersects(
                viewport_rect
            ):
                continue
            cover_id = item.data(ARTIST_COVER_ROLE)
            if not cover_id or item.data(ARTIST_ARTWORK_REQUESTED_ROLE):
                continue

            artist_id = item.data(Qt.UserRole)
            if artist_id is None:
                continue
            item.setData(ARTIST_ARTWORK_REQUESTED_ROLE, True)
            self.load_cover_art(
                str(cover_id),
                80,
                lambda data, requested_id=artist_id,
                    requested_cover_id=str(cover_id):
                        self._set_artist_thumbnail(
                            data, requested_id, requested_cover_id
                        ),
            )

    def _set_artist_thumbnail(self, data, artist_id, cover_id):
        if not data:
            return
        item = None
        for row in range(self.artists_list.count()):
            candidate = self.artists_list.item(row)
            if (
                candidate
                and candidate.data(Qt.UserRole) == artist_id
                and candidate.data(ARTIST_COVER_ROLE) == cover_id
            ):
                item = candidate
                break
        if item is None:
            return

        image = QPixmap()
        if not image.loadFromData(data):
            return

        size = self.artists_list.iconSize()
        scaled = image.scaled(
            size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        x = max(0, (scaled.width() - size.width()) // 2)
        y = max(0, (scaled.height() - size.height()) // 2)
        cropped = scaled.copy(x, y, size.width(), size.height())
        rounded = QPixmap(size)
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, size.width(), size.height()), 7, 7)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()

        item.setIcon(QIcon(rounded))
    @Slot(int, object)
    def on_library_load_completed(self, request_id, client):
        if request_id != self.library_load_id or client is not self.client:
            return
        if getattr(self, "_library_display_failure_id", None) == request_id:
            return

        song_count = len(self.songs_data)
        artist_count = len(self.artists_data)
        album_count = len(self.albums_data)
        self.library_status.setText(
            self.text(
                "loaded_library",
                songs=song_count,
                artists=artist_count,
                albums=album_count,
            )
        )
        self.library_progress.hide()
        self.retry_library_button.hide()
        self.populate_recently_played()
        self.update_resume_button()
        last_view = self.app_state.get("last_view", 2)
        if last_view in (0, 1, 2, 3, 8):
            self.switch_view(last_view)
        self.restore_last_playback()
        if not song_count and not artist_count and not album_count:
            QMessageBox.information(
                self,
                self.text("empty_library_title"),
                self.text("empty_library_message"),
            )
    @Slot(int, str)
    def on_library_load_progress(self, request_id, message):
        if request_id == self.library_load_id:
            self.library_status.setText(message)
    @Slot(int, object, str)
    def on_library_load_failed(self, request_id, client, message):
        if request_id != self.library_load_id or client is not self.client:
            return
        self.library_progress.hide()
        self.retry_library_button.show()
        self.library_status.setText(self.text("library_load_failed_status"))
        QMessageBox.warning(self, self.text("library_load_failed"), message)

    def load_cover_art(self, cover_id, size, callback):
        if not cover_id or not self.client:
            callback(b"")
            return

        server = self.settings.get("server", "")
        cached_data = self.artwork_cache.load(server, str(cover_id), size)
        if cached_data is not None:
            image = QPixmap()
            if image.loadFromData(cached_data):
                callback(cached_data)
                return
            logger.warning("Ignoring invalid cached artwork for %s", cover_id)
            self.artwork_cache.remove(server, str(cover_id), size)

        request = QNetworkRequest(
            QUrl(self.client.get_cover_art_url(str(cover_id), size=size))
        )
        reply = self.network_manager.get(request)
        finished = False

        def finish_request():
            nonlocal finished
            if finished:
                return
            finished = True
            if not isValid(reply):
                logger.warning(
                    "Artwork reply was disposed before it could be processed: %s",
                    cover_id,
                )
                return

            if reply.error() == QNetworkReply.NoError:
                data = bytes(reply.readAll())
                image = QPixmap()
                if image.loadFromData(data):
                    self.artwork_cache.store(server, str(cover_id), size, data)
                else:
                    logger.warning("Server returned invalid artwork for %s", cover_id)
                    data = b""
                callback(data)
            else:
                logger.warning(
                    "Could not download artwork %s: %s",
                    cover_id,
                    reply.errorString(),
                )
                callback(b"")
            reply.deleteLater()

        reply.finished.connect(
            finish_request, Qt.ConnectionType.SingleShotConnection
        )

    def load_visible_album_art(self):
        for grid, scroll_area, size in (
            (self.albums_grid, self.albums_scroll, 300),
            (self.artist_albums_grid, self.artist_albums_scroll, 300),
        ):
            viewport = scroll_area.viewport()
            visible_rect = viewport.rect()
            for index in range(grid.count()):
                card = grid.itemAt(index).widget()
                if not card or not card.isVisible():
                    continue
                card_position = card.mapTo(viewport, card.rect().topLeft())
                if not visible_rect.intersects(card.rect().translated(card_position)):
                    continue

                image_label = card.findChild(QLabel, "albumImage")
                if not image_label or image_label.property("artworkLoaded"):
                    continue
                cover_id = image_label.property("coverId")
                if not cover_id:
                    continue

                image_label.setProperty("artworkLoaded", True)
                self.load_cover_art(
                    str(cover_id),
                    size,
                    lambda data, label=image_label:
                        self.on_album_art_downloaded(data, label)
                        if isValid(label)
                        else None,
                )

    def save_current_app_state(self):
        self.app_state["recently_played"] = self.recently_played[:20]
        save_app_state(self.app_state)

    def sync_state_server(self):
        server_identity = (
            f"{self.settings.get('server', '').rstrip('/')}|"
            f"{self.settings.get('username', '')}"
        )
        previous_identity = self.app_state.get("server_identity")
        if previous_identity and previous_identity != server_identity:
            self.app_state = {}
            self.recently_played = []
            if hasattr(self, "recent_list"):
                self.populate_recently_played()
                self.update_resume_button()
        self.app_state["server_identity"] = server_identity
        self.save_current_app_state()

    def save_playback_state(self):
        if self.current_song_id and not self.player.pending_position:
            self.app_state["last_track_id"] = self.current_song_id
            self.app_state["last_position"] = self.player.media_player.position()
        if hasattr(self, "volume_slider"):
            self.app_state["volume"] = self.volume_slider.value()
        self.save_current_app_state()

    def save_volume_state(self, volume):
        self.app_state["volume"] = volume
        self.save_current_app_state()

    def update_resume_button(self):
        song_id = self.app_state.get("last_track_id")
        song_exists = any(song.get("id") == song_id for song in self.songs_data)
        self.resume_playback_button.setEnabled(song_exists)
        if song_exists:
            self.recent_status.setText(self.text("recent_resume"))
        elif self.recently_played:
            self.recent_status.setText(self.text("recent_choose"))
        else:
            self.recent_status.setText(self.text("recent_empty"))

    def closeEvent(self, event):
        self.save_playback_state()
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        if self.taskbar_controls:
            application = QApplication.instance()
            if application is not None:
                application.removeNativeEventFilter(self.taskbar_controls)
            self.taskbar_controls.close()
            self.taskbar_controls = None
        super().closeEvent(event)
