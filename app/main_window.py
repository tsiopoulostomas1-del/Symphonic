import os
import requests
import re
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QListWidget, QListWidgetItem, QPushButton, QSlider,
    QStackedWidget, QGridLayout, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QMenu, QInputDialog, QMessageBox, 
    QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, QUrl, QSize, QTime, QPropertyAnimation, QEasingCurve, 
    QTimer, QEvent, QRect
)
from PySide6.QtGui import QPixmap, QIcon, QColor, QPainter, QPainterPath, QFontMetrics
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from app.player import Player
from app.subsonic import SubsonicClient
from app.settings import load_settings
from app.widgets.settings_dialog import SettingsDialog

LASTFM_API_KEY = "6e7807c08e2b0515d717009115b12d42" 

class LyricLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("color: #64748B; font-size: 20px; font-weight: bold; background: transparent; padding: 5px;")
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        metrics = QFontMetrics(self.font())
        rect = metrics.boundingRect(0, 0, self.width() - 10, 10000, Qt.TextWordWrap, self.text())
        self.setMinimumHeight(rect.height() + 20)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Symphonic")
        self.resize(1100, 750)

        self.network_manager = QNetworkAccessManager()
        
        self.settings = load_settings()
        self.client = None
        self.songs_data = []
        self.current_song_id = None
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

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 20)
        
        logo = QLabel("Symphonic")
        logo.setObjectName("logo")
        sidebar_layout.addWidget(logo)
        sidebar_layout.addSpacing(30)

        self.btn_nav_artists = QPushButton("Artists")
        self.btn_nav_albums = QPushButton("Albums")
        self.btn_nav_songs = QPushButton("Songs")
        self.btn_nav_queue = QPushButton("Queue")
        self.btn_nav_nowplaying = QPushButton("Now Playing")
        
        for btn in [self.btn_nav_artists, self.btn_nav_albums, self.btn_nav_songs, self.btn_nav_queue, self.btn_nav_nowplaying]:
            btn.setObjectName("navButton")
            btn.setCursor(Qt.PointingHandCursor)
            sidebar_layout.addWidget(btn)

        self.btn_nav_artists.clicked.connect(lambda: self.switch_view(0))
        self.btn_nav_albums.clicked.connect(lambda: self.switch_view(1))
        self.btn_nav_songs.clicked.connect(lambda: self.switch_view(2))
        self.btn_nav_queue.clicked.connect(lambda: self.switch_view(3))
        self.btn_nav_nowplaying.clicked.connect(lambda: self.open_now_playing_view(None))
        
        sidebar_layout.addSpacing(20)
        
        self.btn_liked_songs = QPushButton("Liked Songs")
        self.btn_liked_songs.setObjectName("navButton")
        self.btn_liked_songs.setCursor(Qt.PointingHandCursor)
        self.btn_liked_songs.clicked.connect(self.open_liked_songs)
        sidebar_layout.addWidget(self.btn_liked_songs)
        
        playlist_label = QLabel("PLAYLISTS")
        playlist_label.setObjectName("playlistLabel")
        sidebar_layout.addWidget(playlist_label)
        
        self.playlists_list = QListWidget()
        self.playlists_list.setObjectName("sidebarPlaylists")
        self.playlists_list.setStyleSheet("background: transparent; border: none; outline: none;")
        self.playlists_list.itemClicked.connect(self.on_playlist_clicked)
        sidebar_layout.addWidget(self.playlists_list)

        sidebar_layout.addStretch()
        
        self.btn_nav_settings = QPushButton("Settings")
        self.btn_nav_settings.setObjectName("navButton")
        self.btn_nav_settings.setCursor(Qt.PointingHandCursor)
        self.btn_nav_settings.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(self.btn_nav_settings)
        
        top_layout.addWidget(sidebar)

        # --- Main Content Area ---
        self.main_content_widget = QWidget()
        self.main_content_widget.setObjectName("contentArea")
        content_layout = QVBoxLayout(self.main_content_widget)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(15)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        
        self.btn_back = QPushButton("←")
        self.btn_back.setObjectName("backBtn")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setFixedSize(32, 32)
        self.btn_back.clicked.connect(self.go_back)
        self.btn_back.hide()
        top_bar.addWidget(self.btn_back)

        self.page_title = QLabel("Songs")
        self.page_title.setObjectName("pageTitle")
        top_bar.addWidget(self.page_title)
        top_bar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search library...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setFixedWidth(300)
        self.search_input.returnPressed.connect(self.perform_search)
        top_bar.addWidget(self.search_input)
        
        content_layout.addLayout(top_bar)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")
        
        # 0: Artists
        self.artists_widget = QWidget()
        artists_layout = QVBoxLayout(self.artists_widget)
        artists_layout.setContentsMargins(0, 0, 0, 0)
        self.artists_list = QListWidget()
        self.artists_list.setObjectName("trackList")
        self.artists_list.itemDoubleClicked.connect(self.on_artist_double_clicked)
        self.artists_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.artists_list.customContextMenuRequested.connect(self.show_artists_context_menu)
        artists_layout.addWidget(self.artists_list)

        # 1: Albums
        self.albums_widget = QWidget()
        albums_layout = QVBoxLayout(self.albums_widget)
        albums_layout.setContentsMargins(0, 0, 0, 0)
        self.albums_scroll = QScrollArea()
        self.albums_scroll.setWidgetResizable(True)
        self.albums_scroll.setStyleSheet("background: transparent; border: none;")
        self.albums_grid_widget = QWidget()
        self.albums_grid = QGridLayout(self.albums_grid_widget)
        self.albums_grid.setSpacing(20)
        self.albums_scroll.setWidget(self.albums_grid_widget)
        albums_layout.addWidget(self.albums_scroll)

        # 2: Songs
        self.songs_widget = QWidget()
        songs_layout = QVBoxLayout(self.songs_widget)
        songs_layout.setContentsMargins(0, 0, 0, 0)
        self.songs_table = QTableWidget()
        self.songs_table.setObjectName("songsTable")
        self.songs_table.setColumnCount(4)
        self.songs_table.setHorizontalHeaderLabels(["Title", "Artist", "Album", "Time"])
        self.songs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.songs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.songs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.songs_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.songs_table.verticalHeader().setVisible(False)
        self.songs_table.setShowGrid(False)
        self.songs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.songs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.songs_table.doubleClicked.connect(self.on_song_table_double_clicked)
        self.songs_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.songs_table.customContextMenuRequested.connect(self.show_songs_context_menu)
        songs_layout.addWidget(self.songs_table)

        # 3: Queue
        self.queue_widget = QWidget()
        queue_layout = QVBoxLayout(self.queue_widget)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_table = QTableWidget()
        self.queue_table.setObjectName("songsTable")
        self.queue_table.setColumnCount(3)
        self.queue_table.setHorizontalHeaderLabels(["Title", "Artist", "Album"])
        self.queue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setShowGrid(False)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.queue_table.doubleClicked.connect(self.on_queue_table_double_clicked)
        queue_layout.addWidget(self.queue_table)

        # 4: Search
        self.search_widget = QWidget()
        search_layout = QVBoxLayout(self.search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.search_results_list = QListWidget()
        self.search_results_list.setObjectName("trackList")
        self.search_results_list.itemDoubleClicked.connect(self.on_search_result_double_clicked)
        search_layout.addWidget(self.search_results_list)

        # 5: ALBUM DETAILS
        self.album_details_widget = QWidget()
        ad_layout = QVBoxLayout(self.album_details_widget)
        ad_layout.setContentsMargins(0, 0, 0, 0)
        ad_layout.setSpacing(20)

        ad_header = QHBoxLayout()
        ad_header.setSpacing(30)
        
        self.ad_art = QLabel()
        self.ad_art.setFixedSize(200, 200)
        self.ad_art.setObjectName("adArt")
        
        ad_info_layout = QVBoxLayout()
        ad_info_layout.setAlignment(Qt.AlignVCenter)
        self.ad_title = QLabel("Album Title")
        self.ad_title.setObjectName("adTitle")
        self.ad_artist = QLabel("Artist Name")
        self.ad_artist.setObjectName("adArtist")
        self.ad_meta = QLabel("Year • Genre • Tracks")
        self.ad_meta.setObjectName("adMeta")
        
        self.btn_play_album = QPushButton("Play Album")
        self.btn_play_album.setObjectName("adPlayBtn")
        self.btn_play_album.setFixedWidth(140)
        self.btn_play_album.setCursor(Qt.PointingHandCursor)
        self.btn_play_album.clicked.connect(self.play_current_album)
        
        ad_info_layout.addWidget(self.ad_title)
        ad_info_layout.addWidget(self.ad_artist)
        ad_info_layout.addWidget(self.ad_meta)
        ad_info_layout.addSpacing(15)
        ad_info_layout.addWidget(self.btn_play_album)
        
        ad_header.addWidget(self.ad_art)
        ad_header.addLayout(ad_info_layout)
        ad_header.addStretch()
        ad_layout.addLayout(ad_header)

        self.ad_table = QTableWidget()
        self.ad_table.setObjectName("songsTable")
        self.ad_table.setColumnCount(3)
        self.ad_table.setHorizontalHeaderLabels(["#", "Title", "Time"])
        self.ad_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ad_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ad_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ad_table.verticalHeader().setVisible(False)
        self.ad_table.setShowGrid(False)
        self.ad_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ad_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ad_table.doubleClicked.connect(self.on_album_track_double_clicked)
        ad_layout.addWidget(self.ad_table)

        # 6: ARTIST DETAILS
        self.artist_details_widget = QWidget()
        art_layout = QHBoxLayout(self.artist_details_widget)
        art_layout.setContentsMargins(0, 0, 0, 0)
        art_layout.setSpacing(40)

        art_left_widget = QWidget()
        art_left_widget.setFixedWidth(320)
        art_left = QVBoxLayout(art_left_widget)
        art_left.setContentsMargins(0, 0, 0, 0)
        art_left.setAlignment(Qt.AlignTop)

        self.art_image = QLabel()
        self.art_image.setFixedSize(280, 280)
        self.art_image.setObjectName("artImage")
        art_left.addWidget(self.art_image)
        
        art_left.addSpacing(20)
        
        self.art_name = QLabel("Artist Name")
        self.art_name.setObjectName("artName")
        self.art_name.setWordWrap(True)
        art_left.addWidget(self.art_name)
        
        art_left.addSpacing(15)
        
        self.art_bio = QLabel("")
        self.art_bio.setObjectName("artBio")
        self.art_bio.setWordWrap(True)
        art_left.addWidget(self.art_bio)
        
        art_layout.addWidget(art_left_widget)

        art_right_widget = QWidget()
        art_right = QVBoxLayout(art_right_widget)
        art_right.setContentsMargins(0, 0, 0, 0)
        
        disc_title = QLabel("Discography")
        disc_title.setObjectName("pageTitle")
        disc_title.setStyleSheet("font-size: 24px; margin-bottom: 10px;")
        art_right.addWidget(disc_title)

        self.artist_albums_scroll = QScrollArea()
        self.artist_albums_scroll.setWidgetResizable(True)
        self.artist_albums_scroll.setStyleSheet("background: transparent; border: none;")
        self.artist_albums_grid_widget = QWidget()
        self.artist_albums_grid = QGridLayout(self.artist_albums_grid_widget)
        self.artist_albums_grid.setSpacing(20)
        self.artist_albums_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft) 
        self.artist_albums_scroll.setWidget(self.artist_albums_grid_widget)
        art_right.addWidget(self.artist_albums_scroll)
        
        art_layout.addWidget(art_right_widget, stretch=1)

        # 7: LIKED SONGS / PLAYLIST DETAILS
        self.playlist_details_widget = QWidget()
        pd_layout = QVBoxLayout(self.playlist_details_widget)
        pd_layout.setContentsMargins(0, 0, 0, 0)
        pd_layout.setSpacing(20)

        pd_header = QWidget()
        pd_header.setObjectName("pdHeader")
        pd_header.setFixedHeight(180)
        pd_header_layout = QHBoxLayout(pd_header)
        pd_header_layout.setContentsMargins(30, 30, 30, 30)
        pd_header_layout.setSpacing(30)
        
        self.pd_icon = QLabel()
        self.pd_icon.setFixedSize(140, 140)
        self.pd_icon.setObjectName("pdIcon")
        
        pd_info = QVBoxLayout()
        pd_info.setAlignment(Qt.AlignBottom) 
        pd_info.setSpacing(2)
        
        self.pd_type = QLabel("PLAYLIST")
        self.pd_type.setObjectName("pdType")
        
        self.pd_title = QLabel("Title")
        self.pd_title.setObjectName("pdTitle")
        
        self.pd_meta = QLabel("0 tracks")
        self.pd_meta.setObjectName("pdMeta")
        
        pd_info.addWidget(self.pd_type)
        pd_info.addWidget(self.pd_title)
        pd_info.addWidget(self.pd_meta)
        
        pd_header_layout.addWidget(self.pd_icon)
        pd_header_layout.addLayout(pd_info)
        pd_header_layout.addStretch()
        
        pd_layout.addWidget(pd_header)

        self.pd_table = QTableWidget()
        self.pd_table.setObjectName("songsTable")
        self.pd_table.setColumnCount(4)
        self.pd_table.setHorizontalHeaderLabels(["#", "Title", "Artist", "Time"])
        self.pd_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pd_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.pd_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pd_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.pd_table.verticalHeader().setVisible(False)
        self.pd_table.setShowGrid(False)
        self.pd_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pd_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pd_table.doubleClicked.connect(self.on_playlist_track_double_clicked)
        pd_layout.addWidget(self.pd_table)

        self.content_stack.addWidget(self.artists_widget) # 0
        self.content_stack.addWidget(self.albums_widget)  # 1
        self.content_stack.addWidget(self.songs_widget)   # 2
        self.content_stack.addWidget(self.queue_widget)   # 3
        self.content_stack.addWidget(self.search_widget)  # 4
        self.content_stack.addWidget(self.album_details_widget) # 5
        self.content_stack.addWidget(self.artist_details_widget) # 6
        self.content_stack.addWidget(self.playlist_details_widget) # 7
        
        content_layout.addWidget(self.content_stack)
        top_layout.addWidget(self.main_content_widget)
        self.main_layout.addLayout(top_layout)

        # --- Bottom Now Playing Bar (FIXED IN LAYOUT) ---
        self.now_playing_bar = QWidget()
        self.now_playing_bar.setObjectName("nowPlayingBar")
        self.now_playing_bar.setFixedHeight(90)
        
        player_bar_layout = QHBoxLayout(self.now_playing_bar)
        player_bar_layout.setContentsMargins(0, 0, 0, 0) 
        player_bar_layout.setSpacing(0)

        left_widget = QWidget()
        left_widget.setFixedWidth(340) 
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(24, 8, 0, 8) 
        left_layout.setSpacing(16)

        self.art_label = QLabel()
        self.art_label.setObjectName("albumArt")
        self.art_label.setFixedSize(56, 56)
        self.art_label.setCursor(Qt.PointingHandCursor)
        self.art_label.mousePressEvent = self.open_now_playing_view
        left_layout.addWidget(self.art_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignVCenter)
        self.np_title = QLabel("Not Playing")
        self.np_title.setObjectName("npTitle")
        
        self.np_artist = QPushButton("Select a track")
        self.np_artist.setObjectName("npArtistBtn")
        self.np_artist.setCursor(Qt.PointingHandCursor)
        self.np_artist.clicked.connect(self.open_current_artist)
        self.np_artist.setStyleSheet("text-align: left;") 
        
        info_layout.addWidget(self.np_title)
        info_layout.addWidget(self.np_artist)
        left_layout.addLayout(info_layout)
        
        self.btn_like = QPushButton("♡")
        self.btn_like.setObjectName("likeBtn")
        self.btn_like.setCursor(Qt.PointingHandCursor)
        self.btn_like.clicked.connect(self.toggle_like_current_song)
        left_layout.addWidget(self.btn_like)
        
        self.btn_lyrics = QPushButton("🎤")
        self.btn_lyrics.setObjectName("likeBtn") 
        self.btn_lyrics.setCursor(Qt.PointingHandCursor)
        self.btn_lyrics.clicked.connect(self.toggle_lyrics_view)
        left_layout.addWidget(self.btn_lyrics)
        
        player_bar_layout.addWidget(left_widget)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 8, 0, 8)
        center_layout.setSpacing(4)
        center_layout.setAlignment(Qt.AlignCenter)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(20)
        controls_layout.setAlignment(Qt.AlignCenter)
        
        self.btn_shuffle = QPushButton("SHFL")
        self.btn_prev = QPushButton("◄◄")
        self.btn_play = QPushButton("▶")
        self.btn_next = QPushButton("►►")
        self.btn_repeat = QPushButton("RPT")
        
        for btn in [self.btn_shuffle, self.btn_prev, self.btn_play, self.btn_next, self.btn_repeat]:
            btn.setCursor(Qt.PointingHandCursor)
            controls_layout.addWidget(btn)
            
        self.btn_shuffle.setObjectName("smallCtrlBtn")
        self.btn_repeat.setObjectName("smallCtrlBtn")
        self.btn_prev.setObjectName("controlBtn")
        self.btn_next.setObjectName("controlBtn")
        self.btn_play.setObjectName("playBtn") 
        
        self.btn_play.clicked.connect(self.player.toggle_play_pause)
        self.btn_next.clicked.connect(self.player.next)
        self.btn_prev.clicked.connect(self.player.prev)
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        self.btn_repeat.clicked.connect(self.toggle_repeat)
        
        center_layout.addLayout(controls_layout)

        seek_layout = QHBoxLayout()
        seek_layout.setSpacing(10)
        seek_layout.setAlignment(Qt.AlignCenter)
        
        self.time_current = QLabel("0:00")
        self.time_current.setObjectName("timeLabel")
        
        self.seek_bar = QSlider(Qt.Horizontal)
        self.seek_bar.setObjectName("seekBar")
        self.seek_bar.setRange(0, 100)
        self.seek_bar.setFixedWidth(400)
        self.seek_bar.sliderMoved.connect(self.player.set_position)
        
        self.time_total = QLabel("0:00")
        self.time_total.setObjectName("timeLabel")
        
        seek_layout.addWidget(self.time_current)
        seek_layout.addWidget(self.seek_bar)
        seek_layout.addWidget(self.time_total)
        
        center_layout.addLayout(seek_layout)
        player_bar_layout.addWidget(center_widget, stretch=1)

        right_widget = QWidget()
        right_widget.setFixedWidth(340) 
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 8, 24, 8) 
        right_layout.setSpacing(10)
        right_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        vol_label = QLabel("VOL")
        vol_label.setObjectName("smallCtrlBtn")
        right_layout.addWidget(vol_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volumeBar")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.player.set_volume)
        right_layout.addWidget(self.volume_slider)

        player_bar_layout.addWidget(right_widget)
        
        self.main_layout.addWidget(self.now_playing_bar)

        # --- Now Playing Full Screen Overlay ---
        self.now_playing_overlay = QWidget(self)
        self.now_playing_overlay.setObjectName("nowPlayingOverlay")
        self.now_playing_overlay.hide()
        
        np_over_layout = QVBoxLayout(self.now_playing_overlay)
        np_over_layout.setContentsMargins(40, 40, 40, 40)
        
        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.close_now_playing_view)
        np_over_layout.addWidget(close_btn, alignment=Qt.AlignLeft)

        np_over_layout.addStretch()
        
        self.big_art = QLabel()
        self.big_art.setFixedSize(360, 360)
        self.big_art.setObjectName("bigArt")
        np_over_layout.addWidget(self.big_art, alignment=Qt.AlignCenter)
        
        self.big_title = QLabel("Not Playing")
        self.big_title.setObjectName("bigTitle")
        self.big_title.setAlignment(Qt.AlignCenter)
        np_over_layout.addWidget(self.big_title)
        
        self.big_artist = QLabel("")
        self.big_artist.setObjectName("bigArtist")
        self.big_artist.setAlignment(Qt.AlignCenter)
        np_over_layout.addWidget(self.big_artist)
        
        self.big_seek = QSlider(Qt.Horizontal)
        self.big_seek.setObjectName("seekBar")
        self.big_seek.setRange(0, 100)
        self.big_seek.setFixedWidth(400)
        self.big_seek.sliderMoved.connect(self.player.set_position)
        np_over_layout.addWidget(self.big_seek, alignment=Qt.AlignCenter)
        
        np_over_layout.addStretch()

        # --- LYRICS OVERLAY ---
        self.lyrics_overlay = QWidget(self)
        self.lyrics_overlay.setObjectName("lyricsOverlay")
        self.lyrics_overlay.hide()
        
        self.lyrics_opacity = QGraphicsOpacityEffect(self.lyrics_overlay)
        self.lyrics_overlay.setGraphicsEffect(self.lyrics_opacity)
        self.lyrics_fade = QPropertyAnimation(self.lyrics_opacity, b"opacity")
        self.lyrics_fade.setDuration(250)
        
        lyr_layout = QVBoxLayout(self.lyrics_overlay)
        lyr_layout.setContentsMargins(40, 40, 40, 40)
        
        lyr_close_btn = QPushButton("✕")
        lyr_close_btn.setObjectName("closeBtn")
        lyr_close_btn.setFixedSize(36, 36)
        lyr_close_btn.clicked.connect(self.toggle_lyrics_view)
        lyr_layout.addWidget(lyr_close_btn, alignment=Qt.AlignLeft)
        
        self.lyrics_scroll = QScrollArea()
        self.lyrics_scroll.setWidgetResizable(True)
        self.lyrics_scroll.setStyleSheet("background: transparent; border: none;")
        self.lyrics_scroll.setAlignment(Qt.AlignCenter) 
        
        self.lyrics_inner_widget = QWidget()
        self.lyrics_inner_widget.setFixedWidth(900) 
        self.lyrics_inner_widget.setStyleSheet("background: transparent;")
        
        self.lyrics_container_layout = QVBoxLayout(self.lyrics_inner_widget)
        self.lyrics_container_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.lyrics_container_layout.setSpacing(20)
        self.lyrics_container_layout.setContentsMargins(20, 100, 20, 100) 
        
        self.lyrics_scroll.setWidget(self.lyrics_inner_widget)
        lyr_layout.addWidget(self.lyrics_scroll)

        # The hover zone exists, but ONLY works when lyrics are open
        self.hover_zone = QWidget(self.lyrics_overlay)
        self.hover_zone.setStyleSheet("background: transparent;")
        self.hover_zone.setMouseTracking(True)
        self.hover_zone.installEventFilter(self)
        self.hover_zone.setFixedHeight(80)
        
        self.hide_bar_timer = QTimer()
        self.hide_bar_timer.setSingleShot(True)
        self.hide_bar_timer.setInterval(100) 
        self.hide_bar_timer.timeout.connect(self.hide_player_bar)

        self.load_all_data()

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
        self.content_stack.setCurrentIndex(index)
        titles = ["Artists", "Albums", "Songs", "Queue", "Search Results", "Album Details", "Artist Details", "Playlist"]
        self.page_title.setText(titles[index])
        
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

    def populate_queue_table(self):
        self.queue_table.setRowCount(0)
        self.queue_table.setRowCount(len(self.player.queue))
        
        for row, item in enumerate(self.player.queue):
            song = item["song_data"]
            
            if row == self.player.current_index:
                item_title = QTableWidgetItem(f"▶ {song.get('title', 'Unknown')}")
                item_title.setForeground(QColor("#00E5FF"))
            else:
                item_title = QTableWidgetItem(song.get('title', 'Unknown'))
                
            self.queue_table.setItem(row, 0, item_title)
            self.queue_table.setItem(row, 1, QTableWidgetItem(song.get("artist", "Unknown")))
            self.queue_table.setItem(row, 2, QTableWidgetItem(song.get("album", "Unknown")))

    def on_queue_table_double_clicked(self, index):
        self.player.play_index(index.row())

    def show_songs_context_menu(self, pos):
        index = self.songs_table.indexAt(pos)
        if not index.isValid(): return
        
        row = index.row()
        song = self.songs_data[row]
        
        menu = QMenu()
        play_next_action = menu.addAction("Play Next")
        add_to_queue_action = menu.addAction("Add to Queue")
        like_action = menu.addAction("Like Song")
        add_to_playlist_action = menu.addAction("Add to Playlist")
        
        action = menu.exec(self.songs_table.viewport().mapToGlobal(pos))
        
        if action == play_next_action:
            self.player.add_to_queue(song, self.client, play_next=True)
            self.populate_queue_table()
        elif action == add_to_queue_action:
            self.player.add_to_queue(song, self.client, play_next=False)
            self.populate_queue_table()
        elif action == like_action:
            self.client.star_song(song["id"], True)
            self.load_liked_songs()
        elif action == add_to_playlist_action:
            self.prompt_add_to_playlist(song["id"])

    def show_artists_context_menu(self, pos):
        item = self.artists_list.itemAt(pos)
        if not item: return
        
        menu = QMenu()
        go_to_artist_action = menu.addAction("Go to Artist")
        
        action = menu.exec(self.artists_list.viewport().mapToGlobal(pos))
        
        if action == go_to_artist_action:
            self.open_artist_details(item.data(Qt.UserRole), item.text())

    def prompt_add_to_playlist(self, song_id):
        if not self.current_playlists:
            QMessageBox.warning(self, "No Playlists", "You don't have any playlists.")
            return
            
        playlist_names = [p["name"] for p in self.current_playlists]
        name, ok = QInputDialog.getItem(self, "Add to Playlist", "Select Playlist:", playlist_names, 0, False)
        
        if ok and name:
            for p in self.current_playlists:
                if p["name"] == name:
                    self.client.update_playlist(p["id"], song_id_to_add=song_id)
                    QMessageBox.information(self, "Success", f"Added to {name}")
                    break

    def open_liked_songs(self):
        self.switch_view(7)
        self.pd_type.setText("COLLECTION")
        self.pd_title.setText("Liked Songs")
        self.pd_icon.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #00E5FF); border-radius: 10px; font-size: 60px; color: white;")
        self.pd_icon.setText("♥")
        self.pd_icon.setAlignment(Qt.AlignCenter)
        
        self.load_liked_songs()

    def load_liked_songs(self):
        self.liked_songs_data = self.client.get_starred_songs()
        self.pd_meta.setText(f"{len(self.liked_songs_data)} songs")
        
        self.pd_table.setRowCount(0)
        self.pd_table.setRowCount(len(self.liked_songs_data))
        
        for row, song in enumerate(self.liked_songs_data):
            self.pd_table.setItem(row, 0, QTableWidgetItem(str(row+1)))
            self.pd_table.setItem(row, 1, QTableWidgetItem(song.get("title", "Unknown")))
            self.pd_table.setItem(row, 2, QTableWidgetItem(song.get("artist", "Unknown")))
            dur_str = QTime(0, 0).addSecs(song.get("duration", 0)).toString("m:ss")
            self.pd_table.setItem(row, 3, QTableWidgetItem(dur_str))

    def on_playlist_clicked(self, item):
        playlist_id = item.data(Qt.UserRole)
        playlist_name = item.text()
        
        self.switch_view(7)
        self.current_playlist_id = playlist_id
        self.pd_type.setText("PLAYLIST")
        self.pd_title.setText(playlist_name)
        self.pd_icon.setStyleSheet("background-color: #1A1F2B; border-radius: 10px;")
        self.pd_icon.setPixmap(QPixmap()) 
        
        self.current_playlist_songs = self.client.get_playlist_songs(playlist_id)
        self.pd_meta.setText(f"{len(self.current_playlist_songs)} songs")
        
        self.pd_table.setRowCount(0)
        self.pd_table.setRowCount(len(self.current_playlist_songs))
        
        for row, song in enumerate(self.current_playlist_songs):
            self.pd_table.setItem(row, 0, QTableWidgetItem(str(row+1)))
            self.pd_table.setItem(row, 1, QTableWidgetItem(song.get("title", "Unknown")))
            self.pd_table.setItem(row, 2, QTableWidgetItem(song.get("artist", "Unknown")))
            dur_str = QTime(0, 0).addSecs(song.get("duration", 0)).toString("m:ss")
            self.pd_table.setItem(row, 3, QTableWidgetItem(dur_str))

    def on_playlist_track_double_clicked(self, index):
        if self.content_stack.currentIndex() == 7:
            songs = self.liked_songs_data if self.pd_title.text() == "Liked Songs" else self.current_playlist_songs
            self.play_songs(songs, index.row())

    def toggle_like_current_song(self):
        if not self.current_song_id: return
        
        if self.btn_like.text() == "♡":
            self.client.star_song(self.current_song_id, True)
            self.btn_like.setText("♥")
            self.btn_like.setStyleSheet("color: #00E5FF; font-size: 20px;")
        else:
            self.client.star_song(self.current_song_id, False)
            self.btn_like.setText("♡")
            self.btn_like.setStyleSheet("color: #94A3B8; font-size: 20px;")

    def toggle_lyrics_view(self):
        if self.lyrics_overlay.isVisible():
            self.lyrics_fade.stop()
            try: self.lyrics_fade.finished.disconnect()
            except: pass
            self.lyrics_fade.setStartValue(1.0)
            self.lyrics_fade.setEndValue(0.0)
            self.lyrics_fade.finished.connect(self.finish_closing_lyrics)
            self.lyrics_fade.start()
        else:
            self.lyrics_overlay.resize(self.centralWidget().size())
            self.hover_zone.setGeometry(0, self.lyrics_overlay.height() - 80, self.lyrics_overlay.width(), 80)
            self.lyrics_overlay.show()
            self.lyrics_overlay.raise_()
            
            self.lyrics_fade.stop()
            try: self.lyrics_fade.finished.disconnect()
            except: pass
            
            self.lyrics_fade.setStartValue(0.0)
            self.lyrics_fade.setEndValue(1.0)
            self.lyrics_fade.start()
            
            if self.current_song_id:
                self.fetch_lyrics(self.np_title.text(), self.np_artist.text())
            self.lyrics_timer.start()
            
            # Hide the player bar when entering lyrics mode
            self.now_playing_bar.hide()

    def finish_closing_lyrics(self):
        self.lyrics_overlay.hide()
        self.lyrics_timer.stop()
        
        # Restore the player bar back into the layout
        self.main_layout.addWidget(self.now_playing_bar)
        self.now_playing_bar.show() 
        
        try: self.lyrics_fade.finished.disconnect()
        except: pass

    def fetch_lyrics(self, title, artist):
        for i in reversed(range(self.lyrics_container_layout.count())): 
            widget = self.lyrics_container_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
            
        self.lyrics_lines = []
        self.lyric_labels = []
        self.current_lyric_index = -1
        
        loading_lbl = QLabel("Searching for lyrics...")
        loading_lbl.setObjectName("lyricsText")
        loading_lbl.setStyleSheet("color: #94A3B8; font-size: 24px;")
        self.lyrics_container_layout.addWidget(loading_lbl)
        
        try:
            url = "https://lrclib.net/api/search"
            headers = {"User-Agent": "SymphonicDesktop/1.0 (https://github.com/yourusername/symphonic)"}
            params = {"track_name": title, "artist_name": artist}
            
            r = requests.get(url, params=params, headers=headers, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                if data and len(data) > 0:
                    best_match = data[0]
                    synced_lyrics = best_match.get("syncedLyrics")
                    plain_lyrics = best_match.get("plainLyrics")
                    
                    loading_lbl.setParent(None)
                    
                    if synced_lyrics:
                        self.parse_lrc(synced_lyrics)
                        return
                    elif plain_lyrics:
                        for line in plain_lyrics.split('\n'):
                            if not line.strip(): continue
                            lbl = LyricLabel(line)
                            self.lyrics_container_layout.addWidget(lbl)
                        return
        except Exception as e:
            print(f"LRCLIB Error: {e}")

        try:
            loading_lbl.setText("Searching backup sources...")
            fallback_url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
            r2 = requests.get(fallback_url, timeout=10)
            loading_lbl.setParent(None)
            
            if r2.status_code == 200:
                data2 = r2.json()
                plain_lyrics = data2.get("lyrics", "")
                
                if plain_lyrics:
                    for line in plain_lyrics.split('\n'):
                        if not line.strip(): continue
                        lbl = LyricLabel(line)
                        self.lyrics_container_layout.addWidget(lbl)
                    return
            
            no_lbl = QLabel("Lyrics currently unavailable. Please try again later.")
            no_lbl.setObjectName("lyricsText")
            no_lbl.setStyleSheet("color: #94A3B8; font-size: 20px;")
            self.lyrics_container_layout.addWidget(no_lbl)
            
        except Exception as e:
            loading_lbl.setText("Lyrics currently unavailable. Please try again later.")
            loading_lbl.setStyleSheet("color: #94A3B8; font-size: 20px;")
            print(f"Fallback Lyrics Error: {e}")

    def parse_lrc(self, lrc_text):
        lines = lrc_text.split('\n')
        for line in lines:
            match = re.match(r'\[(\d{2}):(\d{2}\.\d{2,3})\](.*)', line)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                text = match.group(3).strip()
                
                if text:
                    total_ms = int((minutes * 60 + seconds) * 1000)
                    self.lyrics_lines.append((total_ms, text))
                    
                    lbl = LyricLabel(text)
                    self.lyrics_container_layout.addWidget(lbl)
                    self.lyric_labels.append(lbl)
                    
        self.lyrics_container_layout.addStretch()

    def update_lyrics_sync(self):
        if not self.lyrics_lines or not self.lyrics_overlay.isVisible():
            return
            
        sync_offset = 250 
        current_time = self.player.media_player.position() + sync_offset
        
        active_index = -1
        for i, (timestamp, _) in enumerate(self.lyrics_lines):
            if current_time >= timestamp:
                active_index = i
            else:
                break
                
        if active_index != self.current_lyric_index and active_index != -1:
            self.current_lyric_index = active_index
            
            for lbl in self.lyric_labels:
                lbl.setStyleSheet("color: #64748B; font-size: 20px; font-weight: bold; background: transparent; padding: 5px;")
                
            active_lbl = self.lyric_labels[active_index]
            active_lbl.setStyleSheet("color: #00E5FF; font-size: 26px; font-weight: 900; background: transparent; padding: 5px;")
            
            QTimer.singleShot(50, lambda: self.lyrics_scroll.ensureWidgetVisible(active_lbl, 50, 200))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.now_playing_overlay.resize(self.centralWidget().size())
        if hasattr(self, 'lyrics_overlay'):
            self.lyrics_overlay.resize(self.centralWidget().size())
            if hasattr(self, 'hover_zone'):
                self.hover_zone.setGeometry(0, self.lyrics_overlay.height() - 80, self.lyrics_overlay.width(), 80)

    def open_now_playing_view(self, event):
        self.now_playing_overlay.resize(self.centralWidget().size())
        self.now_playing_overlay.show()
        self.now_playing_overlay.raise_()

    def close_now_playing_view(self):
        self.now_playing_overlay.hide()
        
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
            self.client = SubsonicClient(self.settings["server"], self.settings["username"], self.settings["password"])
            self.artists_list.clear()
            self.songs_table.setRowCount(0)
            for i in reversed(range(self.albums_grid.count())): 
                widget = self.albums_grid.itemAt(i).widget()
                if widget: widget.setParent(None)
            self.load_all_data()

    def load_all_data(self):
        if not self.client:
            self.open_settings()
            return
        if not self.client.ping():
            self.songs_table.setRowCount(0)
            return

        self.songs_data = self.client.get_all_songs()
        self.populate_songs_table(self.songs_data)

        self.artists_list.clear()
        for artist in self.client.get_artists():
            item = QListWidgetItem(artist.get("name", "Unknown"))
            item.setData(Qt.UserRole, artist.get("id"))
            self.artists_list.addItem(item)

        row, col = 0, 0
        for album in self.client.get_albums():
            self.add_album_card(album, self.albums_grid, row, col)
            col += 1
            if col > 4:
                col = 0
                row += 1
                
        self.current_playlists = self.client.get_playlists()
        self.playlists_list.clear()
        for p in self.current_playlists:
            item = QListWidgetItem(p["name"])
            item.setData(Qt.UserRole, p["id"])
            self.playlists_list.addItem(item)

    def add_album_card(self, album, grid, row, col):
        card = QWidget()
        card.setObjectName("albumCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8) 
        card_layout.setSpacing(8)
        
        img_label = QLabel()
        img_label.setObjectName("albumImage")
        if grid == self.artist_albums_grid:
            img_label.setFixedSize(140, 140)
        else:
            img_label.setFixedSize(160, 160)
        
        title_label = QLabel(album.get("name", "Unknown"))
        title_label.setWordWrap(True)
        title_label.setObjectName("albumTitle")
        
        card_layout.addWidget(img_label)
        card_layout.addWidget(title_label)
        card_layout.addStretch()
        
        card.mousePressEvent = lambda event, a=album, c=card: self.handle_album_click(event, a, c)
        card.setCursor(Qt.PointingHandCursor)
        grid.addWidget(card, row, col)
        
        cover_id = album.get("coverArt")
        if cover_id:
            url = self.client.get_cover_art_url(cover_id, size=300)
            request = QNetworkRequest(QUrl(url))
            reply = self.network_manager.get(request)
            img_label.reply = reply 
            img_label.reply.finished.connect(lambda r=reply, lbl=img_label: self.on_album_art_downloaded(r, lbl))

    def handle_album_click(self, event, album, card):
        if event.button() == Qt.LeftButton:
            self.animate_click(card)
            self.open_album_details(album)
            event.accept()

    def animate_click(self, widget):
        """Tehdään varma klikkaus-efekti muuttamalla widgetin tyyliä hetkellisesti."""
        # Otetaan talteen widgetin alkuperäinen tyyli
        alkuperainen_tyyli = widget.styleSheet()
        
        # Asetetaan klikkaustyyli (esim. haalistetaan taustaa tai lisätään harmaa vivahde)
        widget.setStyleSheet(alkuperainen_tyyli + "; background-color: rgba(255, 255, 255, 0.15);")
        
        # Luodaan pikavauhtia ajastin, joka palauttaa alkuperäisen tyylin 120 millisekunnin (0.12s) päästä
        QTimer.singleShot(120, lambda: widget.setStyleSheet(alkuperainen_tyyli))


    def open_album_details(self, album):
        self.switch_view(5)
        self.current_album_id = album["id"]
        self.ad_title.setText(album.get("name", "Unknown"))
        self.ad_artist.setText(album.get("artist", "Unknown"))
        
        year = album.get("year", "")
        genre = album.get("genre", "")
        song_count = album.get("songCount", 0)
        meta_str = []
        if year: meta_str.append(str(year))
        if genre: meta_str.append(genre)
        if song_count: meta_str.append(f"{song_count} tracks")
        
        self.ad_meta.setText(" • ".join(meta_str))
        
        cover_id = album.get("coverArt")
        if cover_id:
            url = self.client.get_cover_art_url(cover_id, size=400)
            reply = self.network_manager.get(QNetworkRequest(QUrl(url)))
            reply.finished.connect(self.on_ad_art_downloaded)
        else:
            self.ad_art.clear()

        self.current_album_songs = self.client.get_album_songs(self.current_album_id)
        self.ad_table.setRowCount(0)
        self.ad_table.setRowCount(len(self.current_album_songs))
        
        for row, song in enumerate(self.current_album_songs):
            track_num = str(song.get("track", row + 1))
            title = song.get("title", "Unknown")
            dur_sec = song.get("duration", 0)
            dur_str = QTime(0, 0).addSecs(dur_sec).toString("m:ss")
            
            item_num = QTableWidgetItem(track_num)
            item_num.setForeground(QColor("#64748B"))
            
            self.ad_table.setItem(row, 0, item_num)
            self.ad_table.setItem(row, 1, QTableWidgetItem(title))
            self.ad_table.setItem(row, 2, QTableWidgetItem(dur_str))

    def on_ad_art_downloaded(self):
        reply = self.sender()
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            
            scaled_pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            rounded = QPixmap(scaled_pixmap.size())
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(rounded.rect(), 12, 12)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()
            
            self.ad_art.setPixmap(rounded)
        reply.deleteLater()

    def play_current_album(self):
        if self.current_album_songs:
            self.play_songs(self.current_album_songs, 0)

    def on_album_track_double_clicked(self, index):
        self.play_songs(self.current_album_songs, index.row())

    def open_artist_details(self, artist_id, artist_name):
        self.switch_view(6)
        self.current_artist_id = artist_id
        self.current_artist_name = artist_name
        self.art_name.setText(artist_name)
        self.art_bio.setText("Loading biography...")
        
        for i in reversed(range(self.artist_albums_grid.count())): 
            widget = self.artist_albums_grid.itemAt(i).widget()
            if widget: widget.setParent(None)

        artist_info = self.client.get_artist_info(artist_id)
        
        if LASTFM_API_KEY != "YOUR_API_KEY_HERE":
            try:
                params = {
                    "method": "artist.getinfo",
                    "artist": artist_name,
                    "api_key": LASTFM_API_KEY,
                    "format": "json"
                }
                r = requests.get("http://ws.audioscrobbler.com/2.0/", params=params, timeout=5)
                data = r.json()
                
                if "artist" in data and "bio" in data["artist"]:
                    bio_text = data["artist"]["bio"]["summary"]
                    bio_text = re.sub('<[^<]+?>', '', bio_text)
                    self.art_bio.setText(bio_text)
                else:
                    self.art_bio.setText("No biography available.")
            except Exception as e:
                self.art_bio.setText("Could not load biography.")
        else:
            self.art_bio.setText("Add your Last.fm API key in the code to see biographies.")

        cover_id = artist_info.get("coverArt")
        if cover_id:
            url = self.client.get_cover_art_url(cover_id, size=600)
            reply = self.network_manager.get(QNetworkRequest(QUrl(url)))
            reply.finished.connect(self.on_artist_art_downloaded)
        else:
            self.art_image.clear()

        self.current_artist_albums = artist_info.get("album", [])
        row, col = 0, 0
        for album in self.current_artist_albums:
            self.add_album_card(album, self.artist_albums_grid, row, col)
            col += 1
            if col > 2: 
                col = 0
                row += 1

    def on_artist_art_downloaded(self):
        reply = self.sender()
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            
            scaled_pixmap = pixmap.scaled(280, 280, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            rounded = QPixmap(scaled_pixmap.size())
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addEllipse(rounded.rect()) 
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()
            
            self.art_image.setPixmap(rounded)
        reply.deleteLater()

    def open_current_artist(self):
        if not self.current_artist_name: return
        for i in range(self.artists_list.count()):
            item = self.artists_list.item(i)
            if item.text() == self.current_artist_name:
                self.open_artist_details(item.data(Qt.UserRole), item.text())
                return

    def populate_songs_table(self, songs):
        self.songs_table.setRowCount(0)
        self.songs_table.setRowCount(len(songs))
        for row, song in enumerate(songs):
            item_title = QTableWidgetItem(song.get("title", "Unknown"))
            if song.get("id") == self.current_song_id:
                item_title.setForeground(QColor("#00E5FF"))
                item_title.setText(f"▶ {song.get('title', 'Unknown')}")
            
            self.songs_table.setItem(row, 0, item_title)
            self.songs_table.setItem(row, 1, QTableWidgetItem(song.get("artist", "Unknown")))
            self.songs_table.setItem(row, 2, QTableWidgetItem(song.get("album", "Unknown")))
            dur_sec = song.get("duration", 0)
            self.songs_table.setItem(row, 3, QTableWidgetItem(QTime(0, 0).addSecs(dur_sec).toString("m:ss")))

    def on_album_art_downloaded(self, reply, label):
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            
            w = label.width()
            h = label.height()
            
            scaled_pixmap = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            rounded = QPixmap(scaled_pixmap.size())
            rounded.fill(Qt.transparent)

            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(rounded.rect(), 10, 10) 
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()

            label.setPixmap(rounded)
        reply.deleteLater()

    def play_songs(self, songs_list, start_index):
        self.player.set_queue(songs_list, self.client)
        self.player.play_index(start_index)

    def on_song_table_double_clicked(self, index):
        self.play_songs(self.songs_data, index.row())

    def on_artist_double_clicked(self, item):
        self.open_artist_details(item.data(Qt.UserRole), item.text())

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query: return
        
        self.search_results_list.clear()
        for song in self.client.search(query):
            item = QListWidgetItem(f"{song.get('title', 'Unknown')}    —    {song.get('artist', 'Unknown')}")
            self.search_results_list.addItem(item)
        self.switch_view(4)

    def on_search_result_double_clicked(self, item):
        self.play_songs(self.client.search(self.search_input.text().strip()), self.search_results_list.row(item))

    def on_track_changed(self, song):
        self.current_song_id = song["id"]
        self.current_artist_name = song.get("artist", "Unknown")
        
        self.np_title.setText(song.get("title", "Unknown"))
        self.np_artist.setText(song.get("artist", "Unknown"))
        self.big_title.setText(song.get("title", "Unknown"))
        self.big_artist.setText(song.get("artist", "Unknown"))

        dur_sec = song.get("duration", 0)
        self.time_total.setText(QTime(0, 0).addSecs(dur_sec).toString("m:ss"))
        self.time_current.setText("0:00")

        if song.get("starred"):
            self.btn_like.setText("♥")
            self.btn_like.setStyleSheet("color: #00E5FF; font-size: 20px;")
        else:
            self.btn_like.setText("♡")
            self.btn_like.setStyleSheet("color: #94A3B8; font-size: 20px;")
            
        if self.lyrics_overlay.isVisible():
            self.fetch_lyrics(song.get("title", ""), song.get("artist", ""))

        self.client.scrobble(song["id"])
        
        self.populate_songs_table(self.songs_data)
        if self.content_stack.currentIndex() == 3:
            self.populate_queue_table()

        if song.get("coverArt"):
            reply = self.network_manager.get(QNetworkRequest(QUrl(self.client.get_cover_art_url(song["coverArt"], size=600))))
            reply.finished.connect(self.on_now_playing_art_downloaded)
        else:
            self.art_label.clear()
            self.big_art.clear()

    def on_now_playing_art_downloaded(self):
        reply = self.sender()
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            
            scaled_small = pixmap.scaled(56, 56, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            rounded_small = QPixmap(scaled_small.size())
            rounded_small.fill(Qt.transparent)
            painter = QPainter(rounded_small)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(rounded_small.rect(), 6, 6)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled_small)
            painter.end()
            self.art_label.setPixmap(rounded_small)

            scaled_big = pixmap.scaled(360, 360, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            rounded_big = QPixmap(scaled_big.size())
            rounded_big.fill(Qt.transparent)
            painter = QPainter(rounded_big)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(rounded_big.rect(), 16, 16)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled_big)
            painter.end()
            self.big_art.setPixmap(rounded_big)
            
        else:
            self.art_label.clear()
            self.big_art.clear()
        reply.deleteLater()

    def update_seek_bars(self, position):
        if not self.seek_bar.isSliderDown(): 
            self.seek_bar.setValue(position)
            self.time_current.setText(QTime(0, 0).addMSecs(position).toString("m:ss"))
            
        if not self.big_seek.isSliderDown(): 
            self.big_seek.setValue(position)

    def set_seek_bar_ranges(self, duration):
        self.seek_bar.setRange(0, duration)
        self.big_seek.setRange(0, duration)

    def update_play_buttons(self, state):
        self.btn_play.setText("❚❚" if state == QMediaPlayer.PlayingState else "▶")


    def animate_album_click(self, widget):
        """Tehdään albumi-widgetille lyhyt ja pehmeä klikkaus-vilahdus."""
        efekti = widget.graphicsEffect()
        if not isinstance(efekti, QGraphicsOpacityEffect):
            efekti = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(efekti)
            
        animaatio = QPropertyAnimation(efekti, b"opacity")
        animaatio.setDuration(180) # Kesto 0.18 sekuntia
        
        animaatio.setKeyValueAt(0.0, 1.0)
        animaatio.setKeyValueAt(0.4, 0.4)
        animaatio.setKeyValueAt(1.0, 1.0)
        
        animaatio.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.album_animations.append(animaatio)
        animaatio.finished.connect(lambda: self.album_animations.remove(animaatio) if animaatio in self.album_animations else None)
        
        animaatio.start()
