# Symphonic

Symphonic is a desktop music player for Navidrome servers, built with Python
and PySide6. The project is actively developed; a release date has not been
announced.

## Features

- Connect to Navidrome through the Subsonic API
- Browse albums, artists, and songs; search the music library
- Stream music directly from the server
- See album artwork and album names in song search results
- View artist information and discographies, with Last.fm biographies
- Synchronized lyrics from LRCLIB, with a fallback lyrics provider
- Play queue, likes, and playlists
- Like a song directly from an album's track list
- Scrobbling to Navidrome
- Local album-art cache
- Recently played tracks and playback-position restoration
- Library-loading progress and retry controls for loading failures
- Selectable interface themes
- Windows taskbar playback controls and a short pause/resume volume fade
- 12 interface language options: English, Finnish, Russian, Greek, Spanish,
  Chinese, German, French, Hungarian, Sami, Serbian, and Dutch. A few Sami
  strings fall back to English.
- On Windows, the server password is protected with Windows DPAPI. Passwords
  are not encrypted by the app on other operating systems.

## Technology

- Python 3.12.10 (tested)
- PySide6 (Qt 6)
- Navidrome / Subsonic API
- LRCLIB and Last.fm

## Screenshots

Screenshots are not included yet. Add screenshots from the current build here
once they are ready.

## Install and run on Windows

Install Python 3.12 and Git, then run these commands in PowerShell:

```powershell
git clone https://github.com/tsiopoulostomas1-del/Symphonic.git
Set-Location Symphonic
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

On first launch, the app asks for your Navidrome server URL and login
credentials. Use HTTPS on public networks. The app asks for confirmation
before connecting over HTTP.

Run the test suite from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

This repository currently contains the source code only. It does not yet
include a prebuilt `.exe` or build configuration for one.

## Security notes

The Last.fm API key is included in the desktop app's source and must be
treated as public; a key packaged in a client app cannot be kept secret.
Navidrome authentication data is protected in transit only when using HTTPS.

## License

Symphonic is licensed under the [MIT License](./LICENSE).
