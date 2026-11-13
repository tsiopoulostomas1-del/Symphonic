from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QSlider, QStackedWidget, QGridLayout, QScrollArea,
    QTableWidget, QHeaderView, QLineEdit, QGraphicsOpacityEffect,
    QProgressBar,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QTimer


class MainWindowUI:
    def setup_main_ui(self):
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
        sidebar.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 20)
        
        logo = QLabel("Symphonic")
        logo.setObjectName("logo")
        sidebar_layout.addWidget(logo)
        sidebar_layout.addSpacing(30)

        self.btn_nav_artists = QPushButton(self.text("artists"))
        self.btn_nav_albums = QPushButton(self.text("albums"))
        self.btn_nav_songs = QPushButton(self.text("songs"))
        self.btn_nav_queue = QPushButton(self.text("queue"))
        self.btn_nav_nowplaying = QPushButton(self.text("now_playing"))
        self.btn_nav_recent = QPushButton(self.text("recently_played"))
        
        for btn in [
            self.btn_nav_artists, self.btn_nav_albums, self.btn_nav_songs,
            self.btn_nav_queue, self.btn_nav_nowplaying, self.btn_nav_recent,
        ]:
            btn.setObjectName("navButton")
            btn.setCursor(Qt.PointingHandCursor)
            sidebar_layout.addWidget(btn)

        self.btn_nav_artists.clicked.connect(lambda: self.switch_view(0))
        self.btn_nav_albums.clicked.connect(lambda: self.switch_view(1))
        self.btn_nav_songs.clicked.connect(lambda: self.switch_view(2))
        self.btn_nav_queue.clicked.connect(lambda: self.switch_view(3))
        self.btn_nav_nowplaying.clicked.connect(lambda: self.open_now_playing_view(None))
        self.btn_nav_recent.clicked.connect(lambda: self.switch_view(8))
        
        sidebar_layout.addSpacing(20)
        
        self.btn_liked_songs = QPushButton(self.text("liked_songs"))
        self.btn_liked_songs.setObjectName("navButton")
        self.btn_liked_songs.setCursor(Qt.PointingHandCursor)
        self.btn_liked_songs.clicked.connect(self.open_liked_songs)
        sidebar_layout.addWidget(self.btn_liked_songs)
        
        self.playlist_label = QLabel(self.text("playlists"))
        self.playlist_label.setObjectName("playlistLabel")
        sidebar_layout.addWidget(self.playlist_label)
        
        self.playlists_list = QListWidget()
        self.playlists_list.setObjectName("sidebarPlaylists")
        self.playlists_list.setStyleSheet("background: transparent; border: none; outline: none;")
        self.playlists_list.itemClicked.connect(self.on_playlist_clicked)
        sidebar_layout.addWidget(self.playlists_list)

        sidebar_layout.addStretch()
        
        self.btn_nav_settings = QPushButton(self.text("settings"))
        self.btn_nav_settings.setObjectName("navButton")
        self.btn_nav_settings.setCursor(Qt.PointingHandCursor)
        self.btn_nav_settings.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(self.btn_nav_settings)

        self.btn_ui_settings = QPushButton(self.text("ui_settings"))
        self.btn_ui_settings.setObjectName("navButton")
        self.btn_ui_settings.setCursor(Qt.PointingHandCursor)
        self.btn_ui_settings.clicked.connect(self.open_ui_settings)
        sidebar_layout.addWidget(self.btn_ui_settings)
        
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

        self.page_title = QLabel(self.text("songs"))
        self.page_title.setObjectName("pageTitle")
        top_bar.addWidget(self.page_title)
        top_bar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.text("search_library"))
        self.search_input.setObjectName("searchInput")
        self.search_input.setFixedWidth(300)
        self.search_input.returnPressed.connect(self.perform_search)
        top_bar.addWidget(self.search_input)
        self.library_status = QLabel(self.text("preparing_library"))
        self.library_status.setObjectName("libraryStatus")
        self.library_status.setMinimumWidth(210)
        self.library_progress = QProgressBar()
        self.library_progress.setObjectName("libraryProgress")
        self.library_progress.setRange(0, 0)
        self.library_progress.setFixedWidth(90)
        self.library_progress.hide()
        self.retry_library_button = QPushButton(self.text("retry"))
        self.retry_library_button.setObjectName("navButton")
        self.retry_library_button.setCursor(Qt.PointingHandCursor)
        self.retry_library_button.clicked.connect(self.load_all_data)
        self.retry_library_button.hide()
        top_bar.addWidget(self.library_progress)
        top_bar.addWidget(self.library_status)
        top_bar.addWidget(self.retry_library_button)
        
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
        self.songs_table.setHorizontalHeaderLabels([
            self.text("title"), self.text("artist"), self.text("album"), self.text("time")
        ])
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
        self.queue_table.setHorizontalHeaderLabels([
            self.text("title"), self.text("artist"), self.text("album")
        ])
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
        self.ad_title = QLabel(self.text("album"))
        self.ad_title.setObjectName("adTitle")
        self.ad_artist = QLabel(self.text("artist"))
        self.ad_artist.setObjectName("adArtist")
        self.ad_meta = QLabel(self.text("year_genre_tracks"))
        self.ad_meta.setObjectName("adMeta")
        
        self.btn_play_album = QPushButton(self.text("play_album"))
        self.btn_play_album.setObjectName("adPlayBtn")
        self.btn_play_album.setFixedWidth(140)
        self.btn_play_album.setFixedHeight(44)
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
        self.ad_table.setColumnCount(4)
        self.ad_table.setHorizontalHeaderLabels([
            self.text("track_number"), self.text("title"), self.text("time"), ""
        ])
        self.ad_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ad_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ad_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ad_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.ad_table.setColumnWidth(3, 42)
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
        
        self.art_name = QLabel(self.text("artist"))
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
        
        self.disc_title = QLabel(self.text("discography"))
        self.disc_title.setObjectName("pageTitle")
        self.disc_title.setStyleSheet("font-size: 24px; margin-bottom: 10px;")
        art_right.addWidget(self.disc_title)

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
        
        self.pd_type = QLabel(self.text("playlist").upper())
        self.pd_type.setObjectName("pdType")
        
        self.pd_title = QLabel(self.text("title"))
        self.pd_title.setObjectName("pdTitle")
        
        self.pd_meta = QLabel(self.text("songs_count", count=0))
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
        self.pd_table.setHorizontalHeaderLabels([
            self.text("track_number"), self.text("title"),
            self.text("artist"), self.text("time")
        ])
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

        # 8: RECENTLY PLAYED
        self.recent_widget = QWidget()
        recent_layout = QVBoxLayout(self.recent_widget)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        self.resume_playback_button = QPushButton(self.text("continue_listening"))
        self.resume_playback_button.setObjectName("adPlayBtn")
        self.resume_playback_button.setFixedWidth(190)
        self.resume_playback_button.setEnabled(False)
        self.resume_playback_button.clicked.connect(self.resume_last_playback)
        recent_layout.addWidget(self.resume_playback_button, alignment=Qt.AlignLeft)
        self.recent_status = QLabel(self.text("recent_empty"))
        recent_layout.addWidget(self.recent_status)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("trackList")
        self.recent_list.itemDoubleClicked.connect(self.play_recent_song)
        recent_layout.addWidget(self.recent_list)
        self.content_stack.addWidget(self.recent_widget) # 8
        self.content_stack.setCurrentIndex(2)
        
        content_layout.addWidget(self.content_stack)
        top_layout.addWidget(self.main_content_widget)
        self.main_layout.addLayout(top_layout)

    def setup_overlays(self):
        # --- Now Playing Full Screen Overlay ---
        self.now_playing_overlay = QWidget(self)
        self.now_playing_overlay.setObjectName("nowPlayingOverlay")
        self.now_playing_overlay.hide()
        
        np_over_layout = QVBoxLayout(self.now_playing_overlay)
        np_over_layout.setContentsMargins(40, 40, 40, 40)
        
        close_btn = QPushButton("✕")
        close_btn.setToolTip(self.text("close"))
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.close_now_playing_view)
        np_over_layout.addWidget(close_btn, alignment=Qt.AlignLeft)

        np_over_layout.addStretch()
        
        self.big_art = QLabel()
        self.big_art.setFixedSize(360, 360)
        self.big_art.setObjectName("bigArt")
        np_over_layout.addWidget(self.big_art, alignment=Qt.AlignCenter)
        
        self.big_title = QLabel(self.text("not_playing"))
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
        lyr_close_btn.setToolTip(self.text("close"))
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
