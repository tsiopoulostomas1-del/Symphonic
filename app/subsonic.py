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

    def _generate_auth(self) -> dict:
        salt = secrets.token_hex(6)
        token = hashlib.md5((self.password + salt).encode("utf-8")).hexdigest()
        return {"u": self.username, "t": token, "s": salt, "v": "1.16.1", "c": self.client_name, "f": "json"}

    def ping(self) -> bool:
        params = self._generate_auth()
        try:
            resp = requests.get(f"{self.server}/rest/ping.view", params=params, timeout=5)
            return resp.json().get("subsonic-response", {}).get("status") == "ok"
        except Exception:
            return False

    def get_all_songs(self) -> list:
        params = self._generate_auth()
        params["query"] = ""
        params["songCount"] = 5000
        params["songOffset"] = 0
        resp = requests.get(f"{self.server}/rest/search3.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["searchResult3"]["song"]
        except KeyError:
            return []

    def get_albums(self) -> list:
        params = self._generate_auth()
        params["type"] = "alphabeticalByName"
        params["size"] = 500
        params["offset"] = 0
        resp = requests.get(f"{self.server}/rest/getAlbumList2.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["albumList2"]["album"]
        except KeyError:
            return []

    def get_artists(self) -> list:
        params = self._generate_auth()
        resp = requests.get(f"{self.server}/rest/getArtists.view", params=params)
        resp.raise_for_status()
        try:
            indexes = resp.json()["subsonic-response"]["artists"]["index"]
            artists = []
            for idx in indexes:
                artists.extend(idx.get("artist", []))
            return artists
        except KeyError:
            return []

    def get_album_songs(self, album_id: str) -> list:
        params = self._generate_auth()
        params["id"] = album_id
        resp = requests.get(f"{self.server}/rest/getAlbum.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["album"]["song"]
        except KeyError:
            return []

    def get_artist_songs(self, artist_id: str) -> list:
        params = self._generate_auth()
        params["id"] = artist_id
        resp = requests.get(f"{self.server}/rest/getArtist.view", params=params)
        resp.raise_for_status()
        try:
            albums = resp.json()["subsonic-response"]["artist"]["album"]
            all_songs = []
            for album in albums:
                all_songs.extend(self.get_album_songs(album["id"]))
            return all_songs
        except KeyError:
            return []

    def get_artist_info(self, artist_id: str) -> dict:
        params = self._generate_auth()
        params["id"] = artist_id
        resp = requests.get(f"{self.server}/rest/getArtist.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["artist"]
        except KeyError:
            return {}

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
        resp = requests.get(f"{self.server}/rest/search3.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["searchResult3"]["song"]
        except KeyError:
            return []

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
        requests.get(f"{self.server}/rest/{action}.view", params=params)

    def get_starred_songs(self) -> list:
        params = self._generate_auth()
        resp = requests.get(f"{self.server}/rest/getStarred2.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["starred2"]["song"]
        except KeyError:
            return []

    # --- PLAYLISTS ---
    def get_playlists(self) -> list:
        params = self._generate_auth()
        resp = requests.get(f"{self.server}/rest/getPlaylists.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["playlists"]["playlist"]
        except KeyError:
            return []

    def get_playlist_songs(self, playlist_id: str) -> list:
        params = self._generate_auth()
        params["id"] = playlist_id
        resp = requests.get(f"{self.server}/rest/getPlaylist.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["playlist"]["entry"]
        except KeyError:
            return []

    def create_playlist(self, name: str, song_ids: list = None) -> str:
        params = self._generate_auth()
        params["name"] = name
        if song_ids:
            params["songId"] = song_ids
        resp = requests.get(f"{self.server}/rest/createPlaylist.view", params=params)
        resp.raise_for_status()
        try:
            return resp.json()["subsonic-response"]["playlist"]["id"]
        except KeyError:
            return ""

    def update_playlist(self, playlist_id: str, song_id_to_add: str = None):
        params = self._generate_auth()
        params["playlistId"] = playlist_id
        if song_id_to_add:
            params["songIdToAdd"] = song_id_to_add
        requests.get(f"{self.server}/rest/updatePlaylist.view", params=params)