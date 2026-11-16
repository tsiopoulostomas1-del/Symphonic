import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from PySide6.QtCore import QBuffer, QIODevice, QPropertyAnimation, QSize, Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QWidget,
)

from app.player import Player
from app.services import fetch_artist_bio_from_lastfm
from app.subsonic import SubsonicClient
from app.main_window import ARTIST_COVER_ROLE, LibraryLoader, MainWindow
from app.window_library import ArtistDetailsLoader, MainWindowLibrary, SearchLoader
from app.window_playback import MainWindowPlayback
from app.window_ui import MainWindowUI
from app.widgets.settings_dialog import SettingsDialog
from app.windows_taskbar import (
    BUTTON_NEXT, BUTTON_PLAY_PAUSE, BUTTON_PREVIOUS, THBN_CLICKED, WM_COMMAND,
    WindowsTaskbarControls, _NativeMessage,
)


class SubsonicClientTests(unittest.TestCase):
    @patch("app.subsonic.requests.get")
    def test_get_all_songs_loads_tracks_from_each_album(self, mock_get):
        songs = [
            {"id": "song-1", "title": "First"},
            {"id": "song-2", "title": "Second"},
        ]
        responses = []
        for song in songs:
            response = Mock()
            response.json.return_value = {
                "subsonic-response": {
                    "status": "ok",
                    "album": {"song": [song]},
                }
            }
            responses.append(response)
        mock_get.side_effect = responses

        client = SubsonicClient("http://server", "user", "password")
        progress = Mock()
        result = client.get_all_songs(
            [{"id": "album-1"}, {"id": "album-2"}],
            progress_callback=progress,
        )

        self.assertEqual(result, songs)
        self.assertEqual(mock_get.call_count, 2)
        self.assertTrue(all(
            call.args[0].endswith("/rest/getAlbum.view")
            for call in mock_get.call_args_list
        ))
        self.assertEqual(
            [call.kwargs["params"]["id"] for call in mock_get.call_args_list],
            ["album-1", "album-2"],
        )
        self.assertEqual(progress.call_args_list, [call(1, 2), call(2, 2)])

    @patch("app.subsonic.requests.get")
    def test_get_all_songs_returns_empty_for_empty_album_list(self, mock_get):
        client = SubsonicClient("http://server", "user", "password")

        self.assertEqual(client.get_all_songs([]), [])
        mock_get.assert_not_called()

    @patch("app.subsonic.requests.get")
    def test_get_albums_reports_missing_response_section(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "unexpected": {},
            }
        }
        mock_get.return_value = response
        client = SubsonicClient("http://server", "user", "password")

        with self.assertRaisesRegex(
            ValueError, "missing the expected 'albumList2' section"
        ):
            client.get_albums()

    @patch("app.subsonic.requests.get")
    def test_star_song_checks_subsonic_response(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 40, "message": "Wrong username or password"},
            }
        }
        mock_get.return_value = response
        client = SubsonicClient("http://server", "user", "password")

        with self.assertRaisesRegex(RuntimeError, "Wrong username or password"):
            client.star_song("song-1")

        self.assertTrue(mock_get.call_args.args[0].endswith("/rest/star.view"))
        self.assertEqual(mock_get.call_args.kwargs["params"]["id"], "song-1")

    @patch("app.subsonic.requests.get")
    def test_update_playlist_checks_subsonic_response(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "subsonic-response": {
                "status": "failed",
                "error": {"code": 40, "message": "Permission denied"},
            }
        }
        mock_get.return_value = response
        client = SubsonicClient("http://server", "user", "password")

        with self.assertRaisesRegex(RuntimeError, "Permission denied"):
            client.update_playlist("playlist-1", "song-1")

    @patch("app.services.requests.get")
    def test_artist_biography_uses_https(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "artist": {"bio": {"summary": "Artist bio"}}
        }
        mock_get.return_value = response

        result = fetch_artist_bio_from_lastfm("Artist", "public-api-key")

        self.assertEqual(result, "Artist bio")
        self.assertTrue(mock_get.call_args.args[0].startswith("https://"))

    def test_album_song_like_updates_local_state_after_server_success(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        song = {"id": "song-1"}
        button = QPushButton("♡")
        window = SimpleNamespace(
            client=Mock(),
            current_album_songs=[song],
            songs_data=[song],
            liked_songs_data=[],
            current_song_id=None,
            ad_table=Mock(),
        )
        window.ad_table.cellWidget.return_value = button

        MainWindowLibrary.toggle_album_song_like(window, 0)

        window.client.star_song.assert_called_once_with("song-1", True)
        self.assertTrue(song["starred"])
        self.assertEqual(window.liked_songs_data, [song])
        self.assertEqual(button.text(), "♥")

        MainWindowLibrary.toggle_album_song_like(window, 0)

        window.client.star_song.assert_has_calls(
            [call("song-1", True), call("song-1", False)]
        )
        self.assertNotIn("starred", song)
        self.assertEqual(window.liked_songs_data, [])
        self.assertEqual(button.text(), "♡")

    def test_player_fades_pause_and_resume_without_changing_user_volume(self):
        self.assertIsNotNone(QApplication.instance() or QApplication([]))
        player = Player()
        player.media_player = Mock()
        player.media_player.playbackState.return_value = QMediaPlayer.PlayingState
        player.audio_output = Mock()
        player._user_volume = 0.6

        try:
            player.toggle_play_pause()
            self.assertTrue(player._pause_after_fade)
            player._apply_fade_progress(0.5)
            self.assertAlmostEqual(
                player.audio_output.setVolume.call_args.args[0], 0.3
            )
            player.set_volume(40)
            self.assertAlmostEqual(
                player.audio_output.setVolume.call_args.args[0], 0.2
            )
            player._apply_fade_progress(1.0)
            player.media_player.pause.assert_called_once_with()
            self.assertEqual(player._volume_level, 0.0)
            self.assertAlmostEqual(player._user_volume, 0.4)

            player.media_player.playbackState.return_value = (
                QMediaPlayer.PausedState
            )
            player.toggle_play_pause()
            player.media_player.play.assert_called_once_with()
            self.assertEqual(player._volume_level, 0.0)
            player._apply_fade_progress(0.5)
            self.assertAlmostEqual(
                player.audio_output.setVolume.call_args.args[0], 0.2
            )
            player._apply_fade_progress(1.0)
            self.assertAlmostEqual(
                player.audio_output.setVolume.call_args.args[0], 0.4
            )
        finally:
            player._fade_timer.stop()

    def test_taskbar_thumbnail_commands_dispatch_to_player_actions(self):
        controls = WindowsTaskbarControls.__new__(WindowsTaskbarControls)
        calls = []
        controls._commands = {
            BUTTON_PREVIOUS: lambda: calls.append("previous"),
            BUTTON_PLAY_PAUSE: lambda: calls.append("toggle"),
            BUTTON_NEXT: lambda: calls.append("next"),
        }
        controls._added_hwnd = 1
        controls.taskbar_button_created = 0xC001

        for button_id, expected in (
            (BUTTON_PREVIOUS, "previous"),
            (BUTTON_PLAY_PAUSE, "toggle"),
            (BUTTON_NEXT, "next"),
        ):
            message = _NativeMessage()
            message.hwnd = 1
            message.message = WM_COMMAND
            message.wParam = (THBN_CLICKED << 16) | button_id
            self.assertTrue(
                controls.nativeEventFilter(
                    b"windows_generic_MSG", ctypes.addressof(message)
                )
            )
            self.assertEqual(calls[-1], expected)

        self.assertFalse(
            controls.nativeEventFilter(
                b"other_native_event", ctypes.addressof(message)
            )
        )

    def test_taskbar_button_created_message_registers_toolbar_for_its_window(self):
        controls = WindowsTaskbarControls.__new__(WindowsTaskbarControls)
        controls.taskbar_button_created = 0xC001
        controls.add_buttons = Mock()
        message = _NativeMessage()
        message.hwnd = 1234
        message.message = controls.taskbar_button_created

        self.assertFalse(
            controls.nativeEventFilter(
                b"windows_generic_MSG", ctypes.addressof(message)
            )
        )

        controls.add_buttons.assert_called_once_with(1234)

    def test_taskbar_playback_icon_updates_after_native_event_returns(self):
        app = QApplication.instance() or QApplication([])
        controls = WindowsTaskbarControls.__new__(WindowsTaskbarControls)
        controls._icons = {
            "previous": 1,
            "play": 2,
            "pause": 3,
            "next": 4,
        }
        controls._playing = False
        controls._added_hwnd = 1234
        controls._taskbar = Mock()
        controls._call = Mock()

        controls.set_playing(True)
        controls._call.assert_not_called()
        app.processEvents()

        pause_buttons = controls._call.call_args.args[4][1]
        self.assertEqual(pause_buttons[1].hIcon, 3)
        self.assertEqual(pause_buttons[1].szTip, "Pause")

        controls._call.reset_mock()
        controls.set_playing(False)
        app.processEvents()

        play_buttons = controls._call.call_args.args[4][1]
        self.assertEqual(play_buttons[1].hIcon, 2)
        self.assertEqual(play_buttons[1].szTip, "Play")


    def test_library_loader_emits_available_albums_before_later_failure(self):
        client = Mock()
        client.ping.return_value = True
        client.get_albums.return_value = [{"id": "album-1"}]
        client.get_artists.side_effect = RuntimeError("artist endpoint failed")

        loader = LibraryLoader(1, client)
        loaded = []
        failed = []
        loader.loaded.connect(lambda *args: loaded.append(args[2]))
        loader.failed.connect(
            lambda *args: failed.append(args[2])
        )

        loader.run()

        self.assertEqual(loaded, [{"albums": [{"id": "album-1"}]}])
        self.assertEqual(len(failed), 1)
        self.assertIn("Artists loading failed", failed[0])

    def test_library_loader_emits_each_stage_and_completes(self):
        albums = [{"id": "album-1"}]
        artists = [{"id": "artist-1"}]
        songs = [{"id": "song-1"}]
        playlists = [{"id": "playlist-1"}]
        client = Mock()
        client.ping.return_value = True
        client.get_albums.return_value = albums
        client.get_artists.return_value = artists
        client.get_all_songs.return_value = songs
        client.get_playlists.return_value = playlists

        loader = LibraryLoader(1, client)
        loaded = []
        completed = []
        loader.loaded.connect(lambda *args: loaded.append(args[2]))
        loader.completed.connect(lambda *args: completed.append(args[1]))

        loader.run()

        self.assertEqual(
            loaded,
            [
                {"albums": albums},
                {"artists": artists},
                {"songs": songs},
                {"playlists": playlists},
            ],
        )
        self.assertEqual(completed, [client])

    @patch("app.window_library.fetch_artist_bio_from_lastfm")
    def test_artist_details_loader_fetches_off_ui_thread(self, fetch_bio):
        artist_info = {"id": "artist-1", "album": []}
        client = Mock()
        client.get_artist_info.return_value = artist_info
        loader = ArtistDetailsLoader(1, client, "artist-1", "Artist")
        loaded = []
        bios = []
        loader.loaded.connect(lambda *args: loaded.append(args))
        loader.bio_loaded.connect(lambda *args: bios.append(args))

        def fetch_bio_after_artist_info(*_args):
            self.assertEqual(loaded, [(1, "artist-1", artist_info)])
            return "Artist biography"

        fetch_bio.side_effect = fetch_bio_after_artist_info

        loader.run()

        self.assertEqual(client.get_artist_info.call_args.args, ("artist-1",))
        self.assertEqual(loaded, [(1, "artist-1", artist_info)])
        self.assertEqual(bios, [(1, "artist-1", "Artist biography")])

    def test_artist_discography_uses_library_cover_when_missing(self):
        album_grid = object()
        window = SimpleNamespace(
            artist_details_request_id=5,
            current_artist_id="artist-1",
            albums_data=[{"id": "album-1", "coverArt": "cover-1"}],
            songs_data=[],
            artist_albums_grid=album_grid,
            add_album_card=Mock(),
            load_visible_album_art=Mock(),
        )
        artist_info = {
            "album": [{"id": "album-1", "name": "Artist album"}]
        }

        with patch("app.window_library.QTimer.singleShot") as single_shot:
            MainWindowLibrary.on_artist_details_loaded(
                window, 5, "artist-1", artist_info
            )

        self.assertEqual(
            window.current_artist_albums[0]["coverArt"], "cover-1"
        )
        window.add_album_card.assert_called_once_with(
            window.current_artist_albums[0], album_grid, 0, 0
        )
        single_shot.assert_called_once_with(0, window.load_visible_album_art)

    def test_artist_list_uses_matching_album_art_as_thumbnail_source(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        artists_list = QListWidget()
        item = QListWidgetItem("Artist")
        item.setData(Qt.UserRole, "artist-1")
        artists_list.addItem(item)
        window = SimpleNamespace(
            artists_data=[{"id": "artist-1", "name": "Artist"}],
            artists_list=artists_list,
            albums_data=[{
                "artistId": "artist-1",
                "artist": "Artist",
                "coverArt": "album-cover",
            }],
            songs_data=[],
        )

        MainWindow._refresh_artist_cover_data(window)

        self.assertEqual(item.data(ARTIST_COVER_ROLE), "album-cover")

    def test_artist_thumbnail_is_rounded_icon_at_list_icon_size(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        artists_list = QListWidget()
        artists_list.setIconSize(QSize(40, 40))
        item = QListWidgetItem("Artist")
        item.setData(Qt.UserRole, "artist-1")
        item.setData(ARTIST_COVER_ROLE, "album-cover")
        artists_list.addItem(item)
        source = QPixmap(80, 40)
        source.fill(QColor("red"))
        buffer = QBuffer()
        self.assertTrue(buffer.open(QIODevice.WriteOnly))
        self.assertTrue(source.save(buffer, "PNG"))
        image_data = bytes(buffer.data())
        buffer.close()

        MainWindow._set_artist_thumbnail(
            SimpleNamespace(artists_list=artists_list),
            image_data,
            "artist-1",
            "album-cover",
        )

        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.icon().pixmap(QSize(40, 40)).size(), QSize(40, 40))

    def test_active_navigation_maps_detail_pages_to_parent_sections(self):
        window = SimpleNamespace(
            btn_nav_artists=object(),
            btn_nav_albums=object(),
            btn_nav_songs=object(),
            btn_nav_queue=object(),
            btn_nav_recent=object(),
            btn_liked_songs=object(),
            showing_liked_songs=False,
            set_active_navigation=Mock(),
        )

        MainWindow.update_active_navigation(window, 5)
        window.set_active_navigation.assert_called_once_with(window.btn_nav_albums)
        window.set_active_navigation.reset_mock()
        MainWindow.update_active_navigation(window, 6)
        window.set_active_navigation.assert_called_once_with(window.btn_nav_artists)
        window.set_active_navigation.reset_mock()
        MainWindow.update_active_navigation(window, 7)
        window.set_active_navigation.assert_called_once_with(None)
        window.showing_liked_songs = True
        window.set_active_navigation.reset_mock()
        MainWindow.update_active_navigation(window, 7)
        window.set_active_navigation.assert_called_once_with(window.btn_liked_songs)

    def test_active_navigation_property_updates_for_sidebar_buttons(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        first = QPushButton()
        second = QPushButton()
        first.setObjectName("navButton")
        second.setObjectName("navButton")
        window = SimpleNamespace(navigation_buttons=[first, second])

        MainWindowUI.set_active_navigation(window, second)

        self.assertFalse(first.property("active"))
        self.assertTrue(second.property("active"))

    def test_search_loader_returns_matching_song_data(self):
        songs = [{"id": "song-1", "title": "Matched song"}]
        client = Mock()
        client.search.return_value = songs
        loader = SearchLoader(2, client, "matched")
        loaded = []
        loader.loaded.connect(lambda *args: loaded.append(args))

        loader.run()

        client.search.assert_called_once_with("matched")
        self.assertEqual(loaded[0], (2, "matched", songs))

    def test_search_result_playback_uses_selected_result_without_searching_again(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        songs = [{"id": "first"}, {"id": "selected"}, {"id": "third"}]
        results_list = QListWidget()
        for song in songs:
            item = QListWidgetItem(song["id"])
            item.setData(Qt.UserRole, song)
            results_list.addItem(item)
        play_songs = Mock()
        window = SimpleNamespace(
            search_results_data=songs,
            search_results_list=results_list,
            play_songs=play_songs,
        )

        MainWindowPlayback.on_search_result_double_clicked(
            window, results_list.item(1)
        )

        play_songs.assert_called_once_with(songs, 1)

    def test_play_songs_ignores_out_of_range_selection(self):
        player = Mock()
        window = SimpleNamespace(player=player, client=Mock())

        MainWindowPlayback.play_songs(window, [{"id": "song-1"}], 1)

        player.set_queue.assert_not_called()
        player.play_index.assert_not_called()

    def test_album_rerender_stops_running_click_animations(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        widget = QWidget()
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(5000)
        animation.start()
        window = SimpleNamespace(album_animations=[animation])

        MainWindowLibrary.stop_album_animations(window)

        self.assertEqual(animation.state(), QPropertyAnimation.Stopped)
        self.assertEqual(window.album_animations, [])
        widget.close()

    def test_search_results_show_album_and_load_cover_art(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        pixmap = QPixmap(8, 8)
        pixmap.fill(Qt.red)
        buffer = QBuffer()
        self.assertTrue(buffer.open(QIODevice.WriteOnly))
        self.assertTrue(pixmap.save(buffer, "PNG"))
        image_data = bytes(buffer.data())

        results_list = QListWidget()
        window = SimpleNamespace(
            search_request_id=3,
            search_input=SimpleNamespace(text=lambda: "matched"),
            search_results_data=[],
            search_results_list=results_list,
            text=lambda key: "Unknown",
            load_cover_art=lambda cover_id, size, callback: callback(image_data),
            switch_view=Mock(),
        )
        window.on_search_art_downloaded = (
            lambda data, request_id, song_id:
                MainWindowLibrary.on_search_art_downloaded(
                    window, data, request_id, song_id
                )
        )
        song = {
            "id": "song-1",
            "title": "Matched song",
            "artist": "Matched artist",
            "album": "Matched album",
            "coverArt": "cover-1",
        }

        MainWindowLibrary.on_search_loaded(window, 3, "matched", [song])

        item = results_list.item(0)
        self.assertIn("Matched album", item.text())
        self.assertFalse(item.icon().isNull())
        self.assertEqual(item.data(Qt.UserRole), song)

    def test_stale_search_artwork_is_ignored(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        results_list = QListWidget()
        item = QListWidgetItem("Current result")
        item.setData(Qt.UserRole, {"id": "song-1"})
        results_list.addItem(item)
        window = SimpleNamespace(
            search_request_id=4,
            search_results_list=results_list,
        )

        MainWindowLibrary.on_search_art_downloaded(
            window, b"not an image", 3, "song-1"
        )

        self.assertTrue(item.icon().isNull())

    def test_library_display_errors_are_reported_without_escaping_slot(self):
        client = object()
        window = SimpleNamespace(
            library_load_id=1,
            client=client,
            _apply_library_data=Mock(side_effect=RuntimeError("bad data")),
            library_progress=Mock(),
            retry_library_button=Mock(),
            library_status=Mock(),
            text=lambda key: key,
        )

        with (
            patch("app.main_window.logger.exception") as log_error,
            patch("app.main_window.QMessageBox.warning") as warning,
        ):
            MainWindow.on_library_loaded(window, 1, client, {"albums": []})

        window.library_progress.hide.assert_called_once_with()
        window.retry_library_button.show.assert_called_once_with()
        self.assertEqual(window._library_display_failure_id, 1)
        log_error.assert_called_once()
        warning.assert_called_once()

    @patch(
        "app.widgets.settings_dialog.QMessageBox.question",
        return_value=QMessageBox.No,
    )
    @patch("app.widgets.settings_dialog.SubsonicClient")
    def test_settings_dialog_requires_confirmation_for_http(
        self, mock_client, mock_question
    ):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        dialog = SettingsDialog({"language": "en"})
        dialog.server_input.setText("http://music.example.com")
        dialog.user_input.setText("user")
        dialog.pass_input.setText("password")

        dialog.validate_and_save()

        mock_question.assert_called_once()
        mock_client.assert_not_called()
        dialog.title_cycle_timer.stop()
        dialog.close()


if __name__ == "__main__":
    unittest.main()
