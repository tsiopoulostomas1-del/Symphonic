import logging

from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QListWidgetItem, QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, QEvent, QRect, QUrl, QPropertyAnimation, QEasingCurve, QTimer,
    QThread, Signal, Slot,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtGui import QPixmap
from shiboken6 import isValid

from app.app_state import load_app_state, save_app_state
from app.artwork_cache import ArtworkCache
from app.player import Player
from app.subsonic import SubsonicClient
from app.settings import load_settings
from app.widgets.settings_dialog import SettingsDialog
from app.window_ui import MainWindowUI
from app.window_library import MainWindowLibrary
from app.window_playback import MainWindowPlayback

logger = logging.getLogger(__name__)


class LibraryLoader(QThread):
    loaded = Signal(int, object, object)
    completed = Signal(int, object)
    failed = Signal(int, object, str)
    progress = Signal(int, str)

    def __init__(self, request_id, client):
        super().__init__()
        self.request_id = request_id
        self.client = client

    def run(self):
        stage = "server connection"
        try:
            self.progress.emit(self.request_id, "Checking server...")
            if not self.client.ping():
                raise ConnectionError(
                    self.client.ping_error or "Could not connect to the Navidrome server."
                )

            stage = "albums"
            self.progress.emit(self.request_id, "Loading albums...")
            albums = self.client.get_albums()
            self.loaded.emit(self.request_id, self.client, {"albums": albums})

            stage = "artists"
            self.progress.emit(self.request_id, "Loading artists...")
            artists = self.client.get_artists()
            self.loaded.emit(self.request_id, self.client, {"artists": artists})

            stage = "songs"
            self.progress.emit(self.request_id, "Loading songs...")
            songs = self.client.get_all_songs(
                albums,
                progress_callback=lambda current, total: self.progress.emit(
                    self.request_id,
                    f"Loading songs ({current}/{total} albums)...",
                ),
            )
            self.loaded.emit(self.request_id, self.client, {"songs": songs})

            stage = "playlists"
            self.progress.emit(self.request_id, "Loading playlists...")
            playlists = self.client.get_playlists()
            self.loaded.emit(
                self.request_id, self.client, {"playlists": playlists}
            )
            self.completed.emit(self.request_id, self.client)
        except Exception as exc:
            self.failed.emit(
                self.request_id, self.client, f"{stage.title()} loading failed: {exc}"
            )


class MainWindow(MainWindowUI, MainWindowLibrary, MainWindowPlayback, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Symphonic")
        self.resize(1100, 750)

        self.network_manager = QNetworkAccessManager()
        self.artwork_cache = ArtworkCache()
        
        self.settings = load_settings()
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
        self.songs_data = []
        self.artists_data = []
        self.albums_data = []
        self.current_song_id = None
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

        self.setup_main_ui()
        self.view_transition_effect = QGraphicsOpacityEffect(self.content_stack)
        self.content_stack.setGraphicsEffect(self.view_transition_effect)
        self.view_transition_animation = None
        self.setup_player_ui()
        self.playback_state_timer = QTimer(self)
        self.playback_state_timer.setInterval(10000)
        self.playback_state_timer.timeout.connect(self.save_playback_state)
        self.playback_state_timer.start()
        self.setup_overlays()
        QTimer.singleShot(0, self.load_all_data)

    def eventFilter(self, obj, event):
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
        previous_index = self.content_stack.currentIndex()
        self.content_stack.setCurrentIndex(index)
        titles = [
            "Artists", "Albums", "Songs", "Queue", "Search Results",
            "Album Details", "Artist Details", "Playlist", "Recently Played",
        ]
        self.page_title.setText(titles[index])
        if index in (0, 1, 2, 3, 8):
            self.app_state["last_view"] = index
            self.save_current_app_state()

        if previous_index != index:
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
        self.btn_shuffle.setStyleSheet("color: #00E5FF;" if active else "color: #64748B;")
    def toggle_repeat(self):
        active = self.player.toggle_repeat()
        self.btn_repeat.setStyleSheet("color: #00E5FF;" if active else "color: #64748B;")
    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = load_settings()
            self.sync_state_server()
            self.client = SubsonicClient(self.settings["server"], self.settings["username"], self.settings["password"])
            self.songs_data = []
            self.artists_data = []
            self.albums_data = []
            self.current_playlists = []
            self.artists_list.clear()
            self.songs_table.setRowCount(0)
            self.playlists_list.clear()
            for i in reversed(range(self.albums_grid.count())): 
                widget = self.albums_grid.itemAt(i).widget()
                if widget: widget.setParent(None)
            self.load_all_data()
    def load_all_data(self):
        if not self.client:
            self.library_progress.hide()
            self.library_status.setText("Not connected. Configure a server in Settings.")
            self.open_settings()
            return

        self.library_load_id += 1
        load_id = self.library_load_id
        client = self.client
        worker = LibraryLoader(load_id, client)
        worker.loaded.connect(self.on_library_loaded)
        worker.completed.connect(self.on_library_load_completed)
        worker.failed.connect(self.on_library_load_failed)
        worker.progress.connect(self.on_library_load_progress)
        self.library_status.setText("Connecting...")
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

        if "songs" in data:
            self.songs_data = data["songs"]
            self.populate_songs_table(self.songs_data)

        if "artists" in data:
            self.artists_data = data["artists"]
            self.artists_list.clear()
            for artist in self.artists_data:
                item = QListWidgetItem(artist.get("name", "Unknown"))
                item.setData(Qt.UserRole, artist.get("id"))
                self.artists_list.addItem(item)

        if "albums" in data:
            self.albums_data = data["albums"]
            for i in reversed(range(self.albums_grid.count())):
                widget = self.albums_grid.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            row, col = 0, 0
            for album in self.albums_data:
                self.add_album_card(album, self.albums_grid, row, col)
                col += 1
                if col > 4:
                    col = 0
                    row += 1
                
        if "playlists" in data:
            self.current_playlists = data["playlists"]
            self.playlists_list.clear()
            for playlist in self.current_playlists:
                item = QListWidgetItem(playlist["name"])
                item.setData(Qt.UserRole, playlist["id"])
                self.playlists_list.addItem(item)

        if "albums" in data:
            self.library_status.setText(
                f"Loaded {len(self.albums_data)} albums; loading library..."
            )
        elif "artists" in data:
            self.library_status.setText(
                f"Loaded {len(self.artists_data)} artists; loading songs..."
            )
        elif "songs" in data:
            self.library_status.setText(
                f"Loaded {len(self.songs_data)} songs; loading playlists..."
            )

    @Slot(int, object)
    def on_library_load_completed(self, request_id, client):
        if request_id != self.library_load_id or client is not self.client:
            return

        song_count = len(self.songs_data)
        artist_count = len(self.artists_data)
        album_count = len(self.albums_data)
        self.library_status.setText(
            f"Loaded {song_count} songs, {artist_count} artists, {album_count} albums"
        )
        self.library_progress.hide()
        self.retry_library_button.hide()
        self.populate_recently_played()
        self.update_resume_button()
        last_view = self.app_state.get("last_view", 2)
        if last_view in (0, 1, 2, 3, 8):
            self.switch_view(last_view)
        if not song_count and not artist_count and not album_count:
            QMessageBox.information(
                self,
                "Library Is Empty",
                "The server connected successfully but returned no songs, artists, "
                "or albums. Check that the library is scanned and that this account "
                "has permission to access it.",
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
        stage = message.partition(" loading failed:")[0]
        self.library_status.setText(f"Library load failed during {stage.lower()}")
        QMessageBox.warning(self, "Library Load Failed", message)

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
        self.save_current_app_state()

    def update_resume_button(self):
        song_id = self.app_state.get("last_track_id")
        song_exists = any(song.get("id") == song_id for song in self.songs_data)
        self.resume_playback_button.setEnabled(song_exists)
        if song_exists:
            self.recent_status.setText("Continue where you left off, or choose a recent track.")
        elif self.recently_played:
            self.recent_status.setText("Choose a recently played track to start listening.")
        else:
            self.recent_status.setText("Your recently played tracks will appear here.")

    def closeEvent(self, event):
        self.save_playback_state()
        super().closeEvent(event)
