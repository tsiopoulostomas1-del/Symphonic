"""
Symphonic — external services and helper classes.

This module contains all code that talks to external APIs (LRCLIB, lyrics.ovh,
Last.fm) and the custom LyricLabel widget used by the lyrics overlay.

Keeping this separate from the UI makes it easy to test, replace or mock the
external services without touching the window code.
"""

import re
import requests
from urllib.parse import quote
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics


# ---------------------------------------------------------------------------
# Custom widget
# ---------------------------------------------------------------------------

class LyricLabel(QLabel):
    """A QLabel for a single lyric line that recalculates its own height.

    Qt's default QLabel does not grow correctly when text wraps, which causes
    lyric lines to be cut off. This subclass forces a correct minimum height
    whenever the label is resized.
    """

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "color: #64748B; font-size: 20px; font-weight: bold; "
            "background: transparent; padding: 5px;"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        metrics = QFontMetrics(self.font())
        rect = metrics.boundingRect(
            0, 0, self.width() - 10, 10000, Qt.TextWordWrap, self.text()
        )
        self.setMinimumHeight(rect.height() + 20)


# ---------------------------------------------------------------------------
# LRCLIB (synced lyrics)
# ---------------------------------------------------------------------------

LRCLIB_URL = "https://lrclib.net/api/search"
LRCLIB_USER_AGENT = (
    "SymphonicDesktop/1.0 (https://github.com/tsiopoulostomas1-del/Symphonic)"
)


def fetch_lyrics_from_lrclib(track_title: str, artist_name: str) -> dict:
    """Search LRCLIB for a track and return the best match as a dict.

    Returns a dict with keys ``syncedLyrics`` and ``plainLyrics`` (either may
    be None if not available). Returns an empty dict if no match was found or
    the request failed.
    """
    try:
        response = requests.get(
            LRCLIB_URL,
            params={"track_name": track_title, "artist_name": artist_name},
            headers={"User-Agent": LRCLIB_USER_AGENT},
            timeout=10,
        )
        if response.status_code != 200:
            return {}
        data = response.json()
        if not data:
            return {}
        return data[0]
    except Exception as exc:
        print(f"LRCLIB error: {exc}")
        return {}


def parse_lrc_timestamps(lrc_text: str) -> list:
    """Parse LRC formatted text into a list of (timestamp_ms, line) tuples.

    LRC lines look like ``[01:23.45] Some lyric line``. Lines without a
    timestamp (metadata tags) are ignored.
    """
    result = []
    for line in lrc_text.split("\n"):
        match = re.match(r"\[(\d{2}):(\d{2}\.\d{2,3})\](.*)", line)
        if not match:
            continue
        minutes = int(match.group(1))
        seconds = float(match.group(2))
        text = match.group(3).strip()
        if not text:
            continue
        total_ms = int((minutes * 60 + seconds) * 1000)
        result.append((total_ms, text))
    return result


# ---------------------------------------------------------------------------
# lyrics.ovh (plain text fallback)
# ---------------------------------------------------------------------------

LYRICS_OVH_URL = "https://api.lyrics.ovh/v1/{artist}/{title}"


def fetch_lyrics_from_lyrics_ovh(track_title: str, artist_name: str) -> str:
    """Fetch plain-text lyrics from lyrics.ovh as a fallback.

    Returns the lyrics as a single string, or an empty string on failure.
    """
    try:
        url = LYRICS_OVH_URL.format(
            artist=quote(artist_name, safe=""),
            title=quote(track_title, safe=""),
        )
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return ""
        return response.json().get("lyrics", "")
    except Exception as exc:
        print(f"lyrics.ovh error: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Last.fm (artist biography)
# ---------------------------------------------------------------------------

LASTFM_URL = "http://ws.audioscrobbler.com/2.0/"


def fetch_artist_bio_from_lastfm(artist_name: str, api_key: str) -> str:
    """Fetch the artist biography summary from Last.fm.

    Returns a cleaned, plain-text biography string, or an empty string if the
    artist was not found or the request failed.
    """
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        return ""
    try:
        response = requests.get(
            LASTFM_URL,
            params={
                "method": "artist.getinfo",
                "artist": artist_name,
                "api_key": api_key,
                "format": "json",
            },
            timeout=5,
        )
        data = response.json()
        if "artist" not in data or "bio" not in data["artist"]:
            return ""
        bio_text = data["artist"]["bio"]["summary"]
        # Strip any HTML tags Last.fm includes in the summary
        return re.sub("<[^<]+?>", "", bio_text)
    except Exception as exc:
        print(f"Last.fm error: {exc}")
        return ""