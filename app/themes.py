from pathlib import Path

THEMES = {
    "midnight": {
        "label": "Midnight Cyan",
        "accent": "#00E5FF",
        "hover": "#66F0FF",
        "selection": "#0F2A3F",
    },
    "violet": {
        "label": "Violet",
        "accent": "#A78BFA",
        "hover": "#C4B5FD",
        "selection": "#292341",
    },
    "ember": {
        "label": "Ember",
        "accent": "#FF9B54",
        "hover": "#FFC078",
        "selection": "#38291F",
    },
    "light": {
        "label": "Soft Light",
        "accent": "#008EA3",
        "hover": "#007487",
        "selection": "#D9ECF3",
    },
}

_LIGHT_COLORS = {
    "#12151C": "#F4F6FA",
    "#0B0E14": "#E8EDF4",
    "#1A1F2B": "#E8EDF4",
    "#1F2430": "#D5DCE7",
    "#2A303C": "#C8D1DE",
    "#E2E8F0": "#263244",
    "#CBD5E1": "#344154",
    "#94A3B8": "#657286",
    "#64748B": "#748196",
    "#FFFFFF": "#1D2735",
    "#0F2A3F": "#D9ECF3",
}

_LIGHT_OVERRIDES = """
#sidebar, #nowPlayingBar { background-color: #E8EDF4; }
#contentArea, #contentStack, #settingsDialog { background-color: #F4F6FA; }
#logo, #pageTitle, #npTitle, #adTitle, #artName, #pdTitle, #dialogTitle {
    color: #1D2735;
}
#navButton { color: #566275; }
#navButton:hover { background-color: #DCE3EC; color: #1D2735; }
#trackList, #songsTable, #sidebarPlaylists { color: #344154; }
#trackList::item, #sidebarPlaylists::item { color: #344154; }
#trackList::item:hover, #songsTable::item:hover,
#sidebarPlaylists::item:hover { background-color: #E8EDF4; }
#trackList::item:selected, #songsTable::item:selected,
#sidebarPlaylists::item:selected { background-color: #D9ECF3; }
QHeaderView::section { background-color: #F4F6FA; color: #657286; }
#searchInput, #settingsDialog QLineEdit, #languageSelector {
    background-color: #FFFFFF; color: #263244; border-color: #D5DCE7;
}
#nowPlayingBar { border-top-color: #D5DCE7; }
#npArtistBtn, #smallCtrlBtn, #controlBtn { color: #657286; }
#timeLabel, #playlistLabel, #adMeta, #artBio, #pdType, #pdMeta,
#inputLabel { color: #657286; }
#controlBtn:hover, #smallCtrlBtn:hover, #likeBtn:hover,
#albumTrackLikeBtn:hover { color: #263244; }
#playBtn { background-color: #263244; color: #FFFFFF; }
#playBtn:hover { background-color: #344154; }
#backBtn, #adArt, #artImage, #pdIcon { background-color: #E8EDF4; }
#backBtn { color: #566275; }
#backBtn:hover { background-color: #008EA3; color: #FFFFFF; }
#settingsDialog QLineEdit:focus { border-color: #008EA3; }
#dialogCancelBtn { color: #566275; border-color: #C8D1DE; }
#dialogCancelBtn:hover { background-color: #E8EDF4; color: #263244; }
#albumCard {
    background-color: #FFFFFF;
    border: 1px solid #E1E7F0;
    border-bottom: 2px solid #D5DCE7;
    border-radius: 12px;
}
#albumCard:hover {
    background-color: #FFFFFF;
    border-color: #C8D4E2;
    border-bottom-color: #B8C6D8;
}
#albumImage {
    background-color: #E8EDF4;
    border: 1px solid #D5DCE7;
    border-radius: 10px;
}
"""


def build_stylesheet(theme: str = "midnight") -> str:
    theme_values = THEMES.get(theme, THEMES["midnight"])
    app_dir = Path(__file__).resolve().parent
    stylesheet_path = app_dir.parent / "style.qss"
    stylesheet = stylesheet_path.read_text(encoding="utf-8")
    genre_arrow_path = str(app_dir / "img" / "chevron-down.svg").replace(
        "\\", "/"
    )
    stylesheet = stylesheet.replace("__GENRE_ARROW__", genre_arrow_path)

    if theme == "light":
        for source, target in _LIGHT_COLORS.items():
            stylesheet = stylesheet.replace(source, target)
        stylesheet += _LIGHT_OVERRIDES

    stylesheet = stylesheet.replace("#00E5FF", theme_values["accent"])
    stylesheet = stylesheet.replace("#66F0FF", theme_values["hover"])
    stylesheet = stylesheet.replace("#0F2A3F", theme_values["selection"])
    return stylesheet
