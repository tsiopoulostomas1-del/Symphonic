import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem

from app.subsonic import SubsonicClient
from app.main_window import LibraryLoader
from app.window_library import ArtistDetailsLoader, SearchLoader
from app.window_playback import MainWindowPlayback


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
