import hashlib
import secrets
import requests
from urllib.parse import urlencode


class SubsonicClient:
    def __init__(self, server: str, username: str, password: str):
        self.server = server.rstrip("/")
        self.username = username
        self.password = password
        self.client_name = "Symphonic"
        self.ping_error = ""

    @staticmethod
    def _as_list(value):
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    @staticmethod
    def _parse_response(response):
        response.raise_for_status()
        payload = response.json()
        subsonic_response = payload.get("subsonic-response")
        if not isinstance(subsonic_response, dict):
            raise ValueError("The server returned an invalid Subsonic API response.")
        if subsonic_response.get("status") == "failed":
            error = subsonic_response.get("error", {})
            message = error.get("message", "Unknown Subsonic API error.")
            code = error.get("code")
            if code is not None:
                message = f"Subsonic API error {code}: {message}"
            raise RuntimeError(message)
        return subsonic_response

    def _generate_auth(self) -> dict:
        salt = secrets.token_hex(6)
        token = hashlib.md5((self.password + salt).encode("utf-8")).hexdigest()
        return {"u": self.username, "t": token, "s": salt, "v": "1.16.1", "c": self.client_name, "f": "json"}

    def ping(self) -> bool:
        params = self._generate_auth()
        try:
            resp = requests.get(f"{self.server}/rest/ping.view", params=params, timeout=5)
            response = resp.json().get("subsonic-response", {})
            if response.get("status") == "ok":
                self.ping_error = ""
                return True
            self.ping_error = response.get("error", {}).get(
                "message", f"Server returned status {resp.status_code}."
            )
        except requests.RequestException as exc:
            self.ping_error = str(exc)
        except ValueError as exc:
            self.ping_error = f"Server returned an invalid response: {exc}"
        return False

    def get_all_songs(self) -> list:
        params = self._generate_auth()
        params["query"] = ""
        page_size = 500
        songs = []
        offset = 0
        while True:
            params["songCount"] = page_size
            params["songOffset"] = offset
            resp = requests.get(
                f"{self.server}/rest/search3.view", params=params, timeout=15
            )
            result = self._parse_response(resp).get("searchResult3", {})
            batch = self._as_list(result.get("song"))
            songs.extend(batch)
            if len(batch) < page_size:
                return songs
            offset += len(batch)

    def get_albums(self) -> list:
        params = self._generate_auth()
        params["type"] = "alphabeticalByName"
        page_size = 500
        albums = []
        offset = 0
        while True:
            params["size"] = page_size
            params["offset"] = offset
            resp = requests.get(
                f"{self.server}/rest/getAlbumList2.view", params=params, timeout=15
            )
            result = self._parse_response(resp).get("albumList2", {})
            batch = self._as_list(result.get("album"))
            albums.extend(batch)
            if len(batch) < page_size:
                return albums
            offset += len(batch)

    def get_artists(self) -> list:
        params = self._generate_auth()
        resp = requests.get(
            f"{self.server}/rest/getArtists.view", params=params, timeout=15
        )
        indexes = self._as_list(
            self._parse_response(resp).get("artists", {}).get("index")
        )
        artists = []
        for idx in indexes:
            artists.extend(self._as_list(idx.get("artist")))
        return artists

    def get_album_songs(self, album_id: str) -> list:
        params = self._generate_auth()
        params["id"] = album_id
        resp = requests.get(
            f"{self.server}/rest/getAlbum.view", params=params, timeout=15
        )
        album = self._parse_response(resp).get("album", {})
        return self._as_list(album.get("song"))

    def get_artist_songs(self, artist_id: str) -> list:
        params = self._generate_auth()
        params["id"] = artist_id
        resp = requests.get(
            f"{self.server}/rest/getArtist.view", params=params, timeout=15
        )
        albums = self._as_list(
            self._parse_response(resp).get("artist", {}).get("album")
        )
        all_songs = []
        for album in albums:
            all_songs.extend(self.get_album_songs(album["id"]))
        return all_songs

    def get_artist_info(self, artist_id: str) -> dict:
        params = self._generate_auth()
        params["id"] = artist_id
        resp = requests.get(
            f"{self.server}/rest/getArtist.view", params=params, timeout=15
        )
        return self._parse_response(resp).get("artist", {})

    def get_stream_url(self, song_id: str) -> str:
        params = self._generate_auth()
        params["id"] = song_id
        return f"{self.server}/rest/stream.view?{urlencode(params)}"

    def get_cover_art_url(self, cover_id: str, size: int = 300) -> str:
        if not cover_id:
            return ""
        params = self._generate_auth()
        params["id"] = cover_id
        params["size"] = size
        return f"{self.server}/rest/getCoverArt.view?{urlencode(params)}"

    def search(self, query: str) -> list:
        params = self._generate_auth()
        params["query"] = query
        params["songCount"] = 50
        resp = requests.get(
            f"{self.server}/rest/search3.view", params=params, timeout=15
        )
        result = self._parse_response(resp).get("searchResult3", {})
        return self._as_list(result.get("song"))

    def scrobble(self, song_id: str, submission: bool = True):
        params = self._generate_auth()
        params["id"] = song_id
        params["submission"] = "true" if submission else "false"
        try:
            requests.get(f"{self.server}/rest/scrobble.view", params=params, timeout=3)
        except Exception:
            pass

    # --- LIKES & FAVORITES ---
    def star_song(self, song_id: str, star: bool = True):
        params = self._generate_auth()
        params["id"] = song_id
        action = "star" if star else "unstar"
        requests.get(f"{self.server}/rest/{action}.view", params=params, timeout=15)

    def get_starred_songs(self) -> list:
        params = self._generate_auth()
        resp = requests.get(
            f"{self.server}/rest/getStarred2.view", params=params, timeout=15
        )
        result = self._parse_response(resp).get("starred2", {})
        return self._as_list(result.get("song"))

    # --- PLAYLISTS ---
    def get_playlists(self) -> list:
        params = self._generate_auth()
        resp = requests.get(
            f"{self.server}/rest/getPlaylists.view", params=params, timeout=15
        )
        result = self._parse_response(resp).get("playlists", {})
        return self._as_list(result.get("playlist"))

    def get_playlist_songs(self, playlist_id: str) -> list:
        params = self._generate_auth()
        params["id"] = playlist_id
        resp = requests.get(
            f"{self.server}/rest/getPlaylist.view", params=params, timeout=15
        )
        result = self._parse_response(resp).get("playlist", {})
        return self._as_list(result.get("entry"))

    def create_playlist(self, name: str, song_ids: list = None) -> str:
        params = self._generate_auth()
        params["name"] = name
        if song_ids:
            params["songId"] = song_ids
        resp = requests.get(
            f"{self.server}/rest/createPlaylist.view", params=params, timeout=15
        )
        playlist = self._parse_response(resp).get("playlist", {})
        return playlist.get("id", "")

    def update_playlist(self, playlist_id: str, song_id_to_add: str = None):
        params = self._generate_auth()
        params["playlistId"] = playlist_id
        if song_id_to_add:
            params["songIdToAdd"] = song_id_to_add
        requests.get(
            f"{self.server}/rest/updatePlaylist.view", params=params, timeout=15
        )