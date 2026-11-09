import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QListWidget, QListWidgetItem, QPushButton,
)

from app.player import Player
from app.subsonic import SubsonicClient
from app.main_window import LibraryLoader
from app.window_library import ArtistDetailsLoader, MainWindowLibrary, SearchLoader
from app.window_playback import MainWindowPlayback
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
        fetch_bio.return_value = "Artist biography"
        loader = ArtistDetailsLoader(1, client, "artist-1", "Artist")
        loaded = []
        loader.loaded.connect(lambda *args: loaded.append(args))

        loader.run()

        self.assertEqual(client.get_artist_info.call_args.args, ("artist-1",))
        self.assertEqual(loaded[0][2:], (artist_info, "Artist biography"))

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


if __name__ == "__main__":
    unittest.main()
