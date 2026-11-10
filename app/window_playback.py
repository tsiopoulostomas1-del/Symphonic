import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QListWidgetItem,
    QTableWidgetItem,
)
from PySide6.QtCore import Qt, QTime, QTimer, QThread, Signal, Slot
from PySide6.QtGui import QPixmap, QColor, QPainter, QPainterPath, QFontMetrics
from PySide6.QtMultimedia import QMediaPlayer

from app.services import fetch_lyrics_from_lrclib, fetch_lyrics_from_lyrics_ovh


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


class LyricsLoader(QThread):
    loaded = Signal(int, object)

    def __init__(self, request_id, title, artist):
        super().__init__()
        self.request_id = request_id
        self.title = title
        self.artist = artist

    def run(self):
        result = fetch_lyrics_from_lrclib(self.title, self.artist)
        synced = result.get("syncedLyrics", "")
        plain = result.get("plainLyrics", "")
        if not synced and not plain:
            plain = fetch_lyrics_from_lyrics_ovh(self.title, self.artist)
        self.loaded.emit(self.request_id, {"synced": synced, "plain": plain})


class ScrobbleWorker(QThread):
    def __init__(self, client, song_id):
        super().__init__()
        self.client = client
        self.song_id = song_id

    def run(self):
        self.client.scrobble(self.song_id)


class MainWindowPlayback:
    def setup_player_ui(self):
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
        self.np_title = QLabel(self.text("not_playing"))
        self.np_title.setObjectName("npTitle")
        
        self.np_artist = QPushButton(self.text("select_track"))
        self.np_artist.setObjectName("npArtistBtn")
        self.np_artist.setCursor(Qt.PointingHandCursor)
        self.np_artist.clicked.connect(self.open_current_artist)
        self.np_artist.setStyleSheet("text-align: left;") 
        
        info_layout.addWidget(self.np_title)
        info_layout.addWidget(self.np_artist)
        left_layout.addLayout(info_layout)
        
        self.btn_like = QPushButton("♡")
        self.btn_like.setObjectName("likeBtn")
        self.btn_like.setToolTip(self.text("like"))
        self.btn_like.setCursor(Qt.PointingHandCursor)
        self.btn_like.clicked.connect(self.toggle_like_current_song)
        left_layout.addWidget(self.btn_like)
        
        self.btn_lyrics = QPushButton("🎙️")
        self.btn_lyrics.setObjectName("likeBtn") 
        self.btn_lyrics.setToolTip(self.text("lyrics"))
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
        
        self.btn_shuffle = QPushButton("⤨")
        self.btn_prev = QPushButton("◀◀")
        self.btn_play = QPushButton("▶")
        self.btn_next = QPushButton("▶▶")
        self.btn_repeat = QPushButton("⟲ / RPT")
        self.btn_shuffle.setToolTip(self.text("shuffle"))
        self.btn_prev.setToolTip(self.text("previous"))
        self.btn_play.setToolTip(self.text("play"))
        self.btn_next.setToolTip(self.text("next"))
        self.btn_repeat.setToolTip(self.text("repeat"))
        
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

        self.volume_label = QLabel(self.text("volume"))
        self.volume_label.setObjectName("smallCtrlBtn")
        right_layout.addWidget(self.volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volumeBar")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.player.set_volume)
        right_layout.addWidget(self.volume_slider)

        player_bar_layout.addWidget(right_widget)
        
        self.main_layout.addWidget(self.now_playing_bar)


    def populate_queue_table(self):
        self.queue_table.setRowCount(0)
        self.queue_table.setRowCount(len(self.player.queue))
        
        for row, item in enumerate(self.player.queue):
            song = item["song_data"]
            
            if row == self.player.current_index:
                item_title = QTableWidgetItem(
                    f"▶ {song.get('title', self.text('unknown'))}"
                )
                item_title.setForeground(QColor("#00E5FF"))
            else:
                item_title = QTableWidgetItem(
                    song.get("title", self.text("unknown"))
                )
                
            self.queue_table.setItem(row, 0, item_title)
            self.queue_table.setItem(
                row, 1, QTableWidgetItem(song.get("artist", self.text("unknown")))
            )
            self.queue_table.setItem(
                row, 2, QTableWidgetItem(song.get("album", self.text("unknown")))
            )
    def on_queue_table_double_clicked(self, index):
        self.player.play_index(index.row())
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
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            
        self.lyrics_lines = []
        self.lyric_labels = []
        self.current_lyric_index = -1
        
        loading_lbl = QLabel(self.text("loading_lyrics"))
        loading_lbl.setObjectName("lyricsText")
        loading_lbl.setStyleSheet("color: #94A3B8; font-size: 24px;")
        self.lyrics_container_layout.addWidget(loading_lbl)

        self.lyrics_request_id += 1
        worker = LyricsLoader(self.lyrics_request_id, title, artist)
        worker.loaded.connect(self.on_lyrics_loaded)
        self.keep_background_worker(worker)
        worker.start()
    @Slot(int, object)
    def on_lyrics_loaded(self, request_id, result):
        if request_id != self.lyrics_request_id:
            return

        for i in reversed(range(self.lyrics_container_layout.count())):
            widget = self.lyrics_container_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        synced_lyrics = result["synced"]
        plain_lyrics = result["plain"]
        if synced_lyrics:
            self.parse_lrc(synced_lyrics)
        elif plain_lyrics:
            for line in plain_lyrics.split("\n"):
                if line.strip():
                    self.lyrics_container_layout.addWidget(LyricLabel(line))
        else:
            no_lyrics = QLabel(self.text("lyrics_unavailable"))
            no_lyrics.setObjectName("lyricsText")
            no_lyrics.setStyleSheet("color: #94A3B8; font-size: 20px;")
            self.lyrics_container_layout.addWidget(no_lyrics)
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
        if event is not None:
            event.accept()
    def close_now_playing_view(self):
        self.now_playing_overlay.hide()
    def play_songs(self, songs_list, start_index):
        self.player.set_queue(songs_list, self.client)
        self.player.play_index(start_index)
    def populate_recently_played(self):
        self.recent_list.clear()
        self.recently_played = [
            song for song in self.recently_played if isinstance(song, dict)
        ][:20]
        for song in self.recently_played:
            title = song.get("title", self.text("unknown"))
            artist = song.get("artist", self.text("unknown"))
            item = QListWidgetItem(f"{title}    —    {artist}")
            item.setData(Qt.UserRole, song)
            self.recent_list.addItem(item)
    def play_recent_song(self, item):
        song = item.data(Qt.UserRole)
        if not isinstance(song, dict):
            return
        self.play_songs(self.recently_played, self.recent_list.row(item))
    def resume_last_playback(self):
        song_id = self.app_state.get("last_track_id")
        song = next(
            (item for item in self.songs_data if item.get("id") == song_id),
            None,
        )
        if not song:
            self.update_resume_button()
            return

        try:
            position = max(0, int(self.app_state.get("last_position", 0)))
            duration = max(0, int(song.get("duration", 0))) * 1000
        except (TypeError, ValueError):
            position = 0
            duration = 0
        if duration and position >= duration - 5000:
            position = 0
        self.player.set_queue([song], self.client)
        self.player.play_index(0, position)
        self.switch_view(8)
    def on_song_table_double_clicked(self, index):
        self.play_songs(self.songs_data, index.row())
    def on_search_result_double_clicked(self, item):
        song = item.data(Qt.UserRole)
        if not isinstance(song, dict):
            return
        self.play_songs(
            self.search_results_data,
            self.search_results_list.row(item),
        )
    def on_track_changed(self, song):
        self.current_song_id = song["id"]
        self.scrobbled_song_id = None
        self.last_playback_position = None
        self.listened_ms = 0
        self.current_artist_name = song.get("artist", self.text("unknown"))
        resume_position = self.player.pending_position
        self.recently_played = [
            item for item in self.recently_played
            if item.get("id") != song.get("id")
        ]
        self.recently_played.insert(0, dict(song))
        self.recently_played = self.recently_played[:20]
        self.app_state["last_track_id"] = song["id"]
        self.app_state["last_position"] = resume_position
        self.save_current_app_state()
        self.populate_recently_played()
        self.update_resume_button()
        
        self.np_title.setText(song.get("title", self.text("unknown")))
        self.np_artist.setText(song.get("artist", self.text("unknown")))
        self.big_title.setText(song.get("title", self.text("unknown")))
        self.big_artist.setText(song.get("artist", self.text("unknown")))

        dur_sec = song.get("duration", 0)
        self.time_total.setText(QTime(0, 0).addSecs(dur_sec).toString("m:ss"))
        self.time_current.setText("0:00")

        if song.get("starred"):
            self.btn_like.setText("♥")
            self.btn_like.setToolTip(self.text("unlike"))
            self.btn_like.setStyleSheet("color: #00E5FF; font-size: 20px;")
        else:
            self.btn_like.setText("♡")
            self.btn_like.setToolTip(self.text("like"))
            self.btn_like.setStyleSheet("color: #94A3B8; font-size: 20px;")
            
        if self.lyrics_overlay.isVisible():
            self.fetch_lyrics(song.get("title", ""), song.get("artist", ""))

        self.populate_songs_table(self.songs_data)
        if self.content_stack.currentIndex() == 3:
            self.populate_queue_table()

        if song.get("coverArt"):
            self.load_cover_art(
                song["coverArt"],
                600,
                lambda data, song_id=song["id"]:
                    self.on_now_playing_art_downloaded(data, song_id),
            )
        else:
            self.art_label.clear()
            self.big_art.clear()
    def on_now_playing_art_downloaded(self, data, song_id):
        if song_id != self.current_song_id:
            return
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            
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
    def update_seek_bars(self, position):
        self.maybe_scrobble_track(position)

        if not self.seek_bar.isSliderDown(): 
            self.seek_bar.setValue(position)
            self.time_current.setText(QTime(0, 0).addMSecs(position).toString("m:ss"))
            
        if not self.big_seek.isSliderDown(): 
            self.big_seek.setValue(position)
    def maybe_scrobble_track(self, position):
        if not self.current_song_id or self.current_song_id == self.scrobbled_song_id:
            return

        previous_position = self.last_playback_position
        self.last_playback_position = position
        if (
            previous_position is not None
            and self.player.media_player.playbackState() == QMediaPlayer.PlayingState
        ):
            played_delta = position - previous_position
            if 0 < played_delta <= 3000:
                self.listened_ms += played_delta

        duration = self.player.media_player.duration()
        if duration <= 0 or self.listened_ms < min(duration // 2, 4 * 60 * 1000):
            return

        self.scrobbled_song_id = self.current_song_id
        worker = ScrobbleWorker(self.client, self.current_song_id)
        self.keep_background_worker(worker)
        worker.start()
    def set_seek_bar_ranges(self, duration):
        self.seek_bar.setRange(0, duration)
        self.big_seek.setRange(0, duration)
    def update_play_buttons(self, state):
        self.btn_play.setText("❚❚" if state == QMediaPlayer.PlayingState else "▶")
        self.btn_play.setToolTip(
            self.text("pause")
            if state == QMediaPlayer.PlayingState
            else self.text("play")
        )
        if self.taskbar_controls:
            self.taskbar_controls.set_playing(state == QMediaPlayer.PlayingState)
