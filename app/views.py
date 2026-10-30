"""
Symphonic — view content logic.

This module contains everything that fills the visible views with data:
artist list, album grid, song table, queue, album/artist detail pages,
playlists and search results.

It does not know about the window layout — it only receives the window
instance and uses its widgets and services. This separation keeps the main
window file focused on wiring and navigation.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidgetItem, QListWidgetItem,
)
from PySide6.QtCore import Qt, QUrl, QTime, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QColor, QPainter, QPainterPath
from PySide6.QtNetwork import QNetworkRequest, QNetworkReply

from app.services import (
    LyricLabel,
    fetch_artist_bio_from_lastfm,
)
from app.settings import load_settings


class Views:
    """Fills the main window's views with data.

    The instance holds a reference to the MainWindow so it can access its
    widgets, the Subsonic client and the player. Every method here is called
    by MainWindow in response to a user action or a navigation event.
    """

    def __init__(self, main_window):
        self.window = main_window

    # -----------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------

    def populate_playlists_sidebar(self):
        """Load playlist names into the sidebar list."""
        w = self.window
        w.current_playlists = w.client.get_playlists()
        w.playlists_list.clear()
        for playlist in w.current_playlists:
            item = QListWidgetItem(playlist["name"])
            item.setData(Qt.UserRole, playlist["id"])
            w.playlists_list.addItem(item)

    # -----------------------------------------------------------------
    # Artists view
    # -----------------------------------------------------------------

    def populate_artists_list(self):
        """Load all artists into the artists list widget."""
        w = self.window
        w.artists_list.clear()
        for artist in w.client.get_artists():
            item = QListWidgetItem(artist.get("name", "Unknown"))
            item.setData(Qt.UserRole, artist.get("id"))
            w.artists_list.addItem(item)

    # -----------------------------------------------------------------
    # Albums grid
    # -----------------------------------------------------------------

    def populate_albums_grid(self):
        """Load all albums into the main album grid."""
        w = self.window
        row, col = 0, 0
        for album in w.client.get_albums():
            self.create_album_card(album, w.albums_grid, row, col)
            col += 1
            if col > 4:
                col = 0
                row += 1

    def create_album_card(self, album, grid, row, col):
        """Create a single clickable album card and place it in the grid."""
        w = self.window
        card = QWidget()
        card.setObjectName("albumCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(8)

        img_label = QLabel()
        img_label.setObjectName("albumImage")
        if grid == w.artist_albums_grid:
            img_label.setFixedSize(140, 140)
        else:
            img_label.setFixedSize(160, 160)

        title_label = QLabel(album.get("name", "Unknown"))
        title_label.setWordWrap(True)
        title_label.setObjectName("albumTitle")

        card_layout.addWidget(img_label)
        card_layout.addWidget(title_label)
        card_layout.addStretch()

        card.mousePressEvent = lambda event, a=album, c=card: self.handle_album_card_click(
            event, a, c
        )
        card.setCursor(Qt.PointingHandCursor)
        grid.addWidget(card, row, col)

        cover_id = album.get("coverArt")
        if cover_id:
            url = w.client.get_cover_art_url(cover_id, size=300)
            request = QNetworkRequest(QUrl(url))
            reply = w.network_manager.get(request)
            img_label.reply = reply  # keep reference so it isn't garbage-collected
            img_label.reply.finished.connect(
                lambda r=reply, lbl=img_label: self.on_album_art_downloaded(r, lbl)
            )

    def handle_album_card_click(self, event, album, card):
        """Open the album detail page and animate the card on click."""
        if event.button() == Qt.LeftButton:
            self.animate_album_card_click(card)
            self.show_album_details(album)
            event.accept()

    def animate_album_card_click(self, widget):
        """A short shrink-and-return animation for a clicked album card."""
        w = self.window
        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(150)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        rect = widget.geometry()
        shrunk = rect.adjusted(4, 4, -4, -4)

        anim.setStartValue(rect)
        anim.setKeyValueAt(0.5, shrunk)
        anim.setEndValue(rect)

        w.album_animations.append(anim)
        anim.start()
        anim.finished.connect(
            lambda: w.album_animations.remove(anim)
            if anim in w.album_animations
            else None
        )

    def on_album_art_downloaded(self, reply, label):
        """Draw a downloaded cover art into the given label with rounded corners."""
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            w, h = label.width(), label.height()
            scaled = pixmap.scaled(
                w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            rounded = QPixmap(scaled.size())
            rounded.fill(Qt.transparent)

            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(rounded.rect(), 10, 10)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()

            label.setPixmap(rounded)
        reply.deleteLater()

    # -----------------------------------------------------------------
    # Songs view
    # -----------------------------------------------------------------

    def populate_songs_table(self, songs):
        """Fill the songs table with the given list of song dicts."""
        w = self.window
        w.songs_table.setRowCount(0)
        w.songs_table.setRowCount(len(songs))
        for row, song in enumerate(songs):
            item_title = QTableWidgetItem(song.get("title", "Unknown"))
            if song.get("id") == w.current_song_id:
                item_title.setForeground(QColor("#00E5FF"))
                item_title.setText(f"▶ {song.get('title', 'Unknown')}")
            w.songs_table.setItem(row, 0, item_title)
            w.songs_table.setItem(row, 1, QTableWidgetItem(song.get("artist", "Unknown")))
            w.songs_table.setItem(row, 2, QTableWidgetItem(song.get("album", "Unknown")))
            dur = song.get("duration", 0)
            w.songs_table.setItem(
                row, 3, QTableWidgetItem(QTime(0, 0).addSecs(dur).toString("m:ss"))
            )

    # -----------------------------------------------------------------
    # Queue view
    # -----------------------------------------------------------------

    def populate_queue_table(self):
        """Fill the queue table from the player's current queue."""
        w = self.window
        w.queue_table.setRowCount(0)
        w.queue_table.setRowCount(len(w.player.queue))
        for row, item in enumerate(w.player.queue):
            song = item["song_data"]
            if row == w.player.current_index:
                title = QTableWidgetItem(f"▶ {song.get('title', 'Unknown')}")
                title.setForeground(QColor("#00E5FF"))
            else:
                title = QTableWidgetItem(song.get("title", "Unknown"))
            w.queue_table.setItem(row, 0, title)
            w.queue_table.setItem(row, 1, QTableWidgetItem(song.get("artist", "Unknown")))
            w.queue_table.setItem(row, 2, QTableWidgetItem(song.get("album", "Unknown")))

    # -----------------------------------------------------------------
    # Album detail page
    # -----------------------------------------------------------------

    def show_album_details(self, album):
        """Switch to the album detail page and fill it with the album's data."""
        w = self.window
        w.switch_view(5)
        w.current_album_id = album["id"]
        w.ad_title.setText(album.get("name", "Unknown"))
        w.ad_artist.setText(album.get("artist", "Unknown"))

        meta_parts = []
        if album.get("year"):
            meta_parts.append(str(album["year"]))
        if album.get("genre"):
            meta_parts.append(album["genre"])
        if album.get("songCount"):
            meta_parts.append(f"{album['songCount']} tracks")
        w.ad_meta.setText(" • ".join(meta_parts))

        cover_id = album.get("coverArt")
        if cover_id:
            url = w.client.get_cover_art_url(cover_id, size=400)
            reply = w.network_manager.get(QNetworkRequest(QUrl(url)))
            reply.finished.connect(self.on_album_detail_art_downloaded)
        else:
            w.ad_art.clear()

        w.current_album_songs = w.client.get_album_songs(w.current_album_id)
        self.populate_album_tracklist(w.current_album_songs)

    def populate_album_tracklist(self, songs):
        """Fill the album detail page's track list."""
        w = self.window
        w.ad_table.setRowCount(0)
        w.ad_table.setRowCount(len(songs))
        for row, song in enumerate(songs):
            track_num = QTableWidgetItem(str(song.get("track", row + 1)))
            track_num.setForeground(QColor("#64748B"))
            dur = song.get("duration", 0)
            w.ad_table.setItem(row, 0, track_num)
            w.ad_table.setItem(row, 1, QTableWidgetItem(song.get("title", "Unknown")))
            w.ad_table.setItem(
                row, 2, QTableWidgetItem(QTime(0, 0).addSecs(dur).toString("m:ss"))
            )

    def on_album_detail_art_downloaded(self):
        """Draw the large cover art on the album detail page with rounded corners."""
        w = self.window
        reply = w.sender()
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            scaled = pixmap.scaled(
                200, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            rounded = QPixmap(scaled.size())
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(rounded.rect(), 12, 12)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()
            w.ad_art.setPixmap(rounded)
        reply.deleteLater()

    def play_album_from_start(self):
        """Play the currently displayed album from its first track."""
        w = self.window
        if w.current_album_songs:
            w.play_songs(w.current_album_songs, 0)

    def play_album_track_at_index(self, index):
        """Play a specific track from the currently displayed album."""
        w = self.window
        w.play_songs(w.current_album_songs, index.row())

    # -----------------------------------------------------------------
    # Artist detail page
    # -----------------------------------------------------------------

    def show_artist_details(self, artist_id, artist_name):
        """Switch to the artist detail page, load bio and discography."""
        w = self.window
        w.switch_view(6)
        w.current_artist_id = artist_id
        w.current_artist_name = artist_name
        w.art_name.setText(artist_name)
        w.art_bio.setText("Loading biography...")

        # Clear previous discography
        for i in reversed(range(w.artist_albums_grid.count())):
            widget = w.artist_albums_grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        artist_info = w.client.get_artist_info(artist_id)

        bio = fetch_artist_bio_from_lastfm(artist_name, w.lastfm_api_key)
        w.art_bio.setText(bio if bio else "No biography available.")

        cover_id = artist_info.get("coverArt")
        if cover_id:
            url = w.client.get_cover_art_url(cover_id, size=600)
            reply = w.network_manager.get(QNetworkRequest(QUrl(url)))
            reply.finished.connect(self.on_artist_art_downloaded)
        else:
            w.art_image.clear()

        self.populate_artist_discography(artist_info.get("album", []))

    def populate_artist_discography(self, albums):
        """Fill the artist page's album grid with the artist's albums."""
        w = self.window
        row, col = 0, 0
        for album in albums:
            self.create_album_card(album, w.artist_albums_grid, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

    def on_artist_art_downloaded(self):
        """Draw the artist portrait on the artist page as a circle."""
        w = self.window
        reply = w.sender()
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            scaled = pixmap.scaled(
                280, 280, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            rounded = QPixmap(scaled.size())
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addEllipse(rounded.rect())
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()
            w.art_image.setPixmap(rounded)
        reply.deleteLater()

    # -----------------------------------------------------------------
    # Liked songs / playlist detail pages
    # -----------------------------------------------------------------

    def show_liked_songs(self):
        """Switch to the liked songs page and load the list."""
        w = self.window
        w.switch_view(7)
        w.pd_type.setText("COLLECTION")
        w.pd_title.setText("Liked Songs")
        w.pd_icon.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #4f46e5, stop:1 #00E5FF); border-radius: 10px; "
            "font-size: 60px; color: white;"
        )
        w.pd_icon.setText("♥")
        w.pd_icon.setAlignment(Qt.AlignCenter)
        self.populate_liked_songs_table()

    def populate_liked_songs_table(self):
        """Fill the liked songs table."""
        w = self.window
        w.liked_songs_data = w.client.get_starred_songs()
        w.pd_meta.setText(f"{len(w.liked_songs_data)} songs")
        w.pd_table.setRowCount(0)
        w.pd_table.setRowCount(len(w.liked_songs_data))
        for row, song in enumerate(w.liked_songs_data):
            w.pd_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            w.pd_table.setItem(row, 1, QTableWidgetItem(song.get("title", "Unknown")))
            w.pd_table.setItem(row, 2, QTableWidgetItem(song.get("artist", "Unknown")))
            dur = song.get("duration", 0)
            w.pd_table.setItem(
                row, 3, QTableWidgetItem(QTime(0, 0).addSecs(dur).toString("m:ss"))
            )

    def show_playlist(self, playlist_id, playlist_name):
        """Switch to a specific playlist page and load it."""
        w = self.window
        w.switch_view(7)
        w.current_playlist_id = playlist_id
        w.pd_type.setText("PLAYLIST")
        w.pd_title.setText(playlist_name)
        w.pd_icon.setStyleSheet("background-color: #1A1F2B; border-radius: 10px;")
        w.pd_icon.setPixmap(QPixmap())

        w.current_playlist_songs = w.client.get_playlist_songs(playlist_id)
        w.pd_meta.setText(f"{len(w.current_playlist_songs)} songs")
        w.pd_table.setRowCount(0)
        w.pd_table.setRowCount(len(w.current_playlist_songs))
        for row, song in enumerate(w.current_playlist_songs):
            w.pd_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            w.pd_table.setItem(row, 1, QTableWidgetItem(song.get("title", "Unknown")))
            w.pd_table.setItem(row, 2, QTableWidgetItem(song.get("artist", "Unknown")))
            dur = song.get("duration", 0)
            w.pd_table.setItem(
                row, 3, QTableWidgetItem(QTime(0, 0).addSecs(dur).toString("m:ss"))
            )

    # -----------------------------------------------------------------
    # Search view
    # -----------------------------------------------------------------

    def perform_search(self, query):
        """Run a search and switch to the results view."""
        w = self.window
        results = w.client.search(query)
        w.search_results_list.clear()
        for song in results:
            item = QListWidgetItem(
                f"{song.get('title', 'Unknown')}    —    {song.get('artist', 'Unknown')}"
            )
            w.search_results_list.addItem(item)
        w.switch_view(4)
        return results