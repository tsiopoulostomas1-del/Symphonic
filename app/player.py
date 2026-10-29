from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, QObject, Signal
import random

class Player(QObject):
    position_changed = Signal(int)
    duration_changed = Signal(int)
    playback_state_changed = Signal(QMediaPlayer.PlaybackState)
    track_changed = Signal(dict) # Now emits the actual song dictionary!

    def __init__(self):
        super().__init__()
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        self.media_player.positionChanged.connect(self.position_changed.emit)
        self.media_player.durationChanged.connect(self.duration_changed.emit)
        self.media_player.playbackStateChanged.connect(self.playback_state_changed.emit)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Queue now holds dictionaries: [{"url": "...", "song_data": {...}}]
        self.queue = []
        self.current_index = -1
        self.is_shuffle = False
        self.is_repeat = False
        
        self.audio_output.setVolume(0.5)

    def set_queue(self, songs_list: list, client):
        """Replaces the entire queue with a new list of songs."""
        self.queue = []
        for song in songs_list:
            url = client.get_stream_url(song["id"])
            self.queue.append({"url": url, "song_data": song})
        self.current_index = -1

    def add_to_queue(self, song: dict, client, play_next: bool = False):
        """Adds a single song to the queue."""
        url = client.get_stream_url(song["id"])
        item = {"url": url, "song_data": song}
        
        if play_next:
            # Insert immediately after the current track
            if self.current_index == -1:
                # If nothing is playing, just start the queue with it
                self.queue.append(item)
            else:
                insert_at = self.current_index + 1
                self.queue.insert(insert_at, item)
        else:
            # Add to the absolute end of the queue
            self.queue.append(item)

    def play_index(self, index: int):
        if 0 <= index < len(self.queue):
            self.current_index = index
            item = self.queue[index]
            self.media_player.setSource(QUrl(item["url"]))
            self.media_player.play()
            self.track_changed.emit(item["song_data"])

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def set_position(self, position: int):
        self.media_player.setPosition(position)

    def set_volume(self, value: int):
        self.audio_output.setVolume(value / 100.0)

    def toggle_shuffle(self):
        self.is_shuffle = not self.is_shuffle
        return self.is_shuffle

    def toggle_repeat(self):
        self.is_repeat = not self.is_repeat
        return self.is_repeat

    def next(self):
        if not self.queue: return
        
        if self.is_shuffle:
            next_idx = random.randint(0, len(self.queue) - 1)
            self.play_index(next_idx)
        elif self.current_index + 1 < len(self.queue):
            self.play_index(self.current_index + 1)
        elif self.is_repeat:
            self.play_index(0)

    def prev(self):
        if self.media_player.position() > 3000:
            self.media_player.setPosition(0)
        elif self.current_index > 0:
            self.play_index(self.current_index - 1)
        elif self.is_repeat and self.queue:
            self.play_index(len(self.queue) - 1)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.is_repeat and not self.is_shuffle:
                self.media_player.setPosition(0)
                self.media_player.play()
            else:
                self.next()