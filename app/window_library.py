import re
import requests

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidgetItem, QTableWidgetItem,
    QMenu, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QTime
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QColor, QPainter, QPainterPath

LASTFM_API_KEY = "6e7807c08e2b0515d717009115b12d42"


class MainWindowLibrary:
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
        if not self.client:
            QMessageBox.information(
                self, "Not Connected", "Connect to your Navidrome server in Settings first."
            )
            self.open_settings()
            return

        self.switch_view(7)
        self.pd_type.setText("COLLECTION")
        self.pd_title.setText("Liked Songs")
        self.pd_icon.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #00E5FF); border-radius: 10px; font-size: 60px; color: white;")
        self.pd_icon.setText("♥")
        self.pd_icon.setAlignment(Qt.AlignCenter)
        
        self.load_liked_songs()
    def load_liked_songs(self):
        if not self.client:
            return

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
        if not self.client:
            QMessageBox.information(
                self, "Not Connected", "Connect to your Navidrome server in Settings first."
            )
            self.open_settings()
            return

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
            self.load_cover_art(
                cover_id,
                300,
                lambda data, label=img_label: self.on_album_art_downloaded(
                    data, label
                ),
            )
    def handle_album_click(self, event, album, card):
        if event.button() == Qt.LeftButton:
            self.animate_album_click(
                card, lambda: self.open_album_details(album)
            )
            event.accept()
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
            album_id = album["id"]
            self.load_cover_art(
                cover_id,
                400,
                lambda data, requested_album_id=album_id:
                    self.on_ad_art_downloaded(data, requested_album_id),
            )
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
    def on_ad_art_downloaded(self, data, album_id):
        if album_id != self.current_album_id:
            return
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            
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
        else:
            self.ad_art.clear()
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
            self.load_cover_art(
                cover_id,
                600,
                lambda data, requested_artist_id=artist_id:
                    self.on_artist_art_downloaded(data, requested_artist_id),
            )
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
    def on_artist_art_downloaded(self, data, artist_id):
        if artist_id != self.current_artist_id:
            return
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            
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
        else:
            self.art_image.clear()
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
    def on_album_art_downloaded(self, data, label):
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            
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
        else:
            label.clear()
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
    def animate_album_click(self, widget, on_finished=None):
        rect = widget.geometry()
        animation = QPropertyAnimation(widget, b"geometry", self)
        animation.setDuration(200)
        animation.setEasingCurve(QEasingCurve.OutBack)
        animation.setStartValue(rect.adjusted(5, 5, -5, -5))
        animation.setEndValue(rect)
        self.album_animations.append(animation)

        def finish_animation():
            if animation in self.album_animations:
                self.album_animations.remove(animation)
            animation.deleteLater()
            if on_finished:
                on_finished()

        animation.finished.connect(finish_animation)
        animation.start()
