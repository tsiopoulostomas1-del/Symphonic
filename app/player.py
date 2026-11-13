from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QElapsedTimer, QObject, QTimer, QUrl, Signal
import random


FADE_DURATION_MS = 250
FADE_INTERVAL_MS = 16


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
        self.pending_position = 0
        self._user_volume = 0.5
        self._volume_level = 1.0
        self._fade_start_level = 1.0
        self._fade_end_level = 1.0
        self._pause_after_fade = False
        self._fade_clock = QElapsedTimer()
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(FADE_INTERVAL_MS)
        self._fade_timer.timeout.connect(self._update_volume_fade)
        self._apply_output_volume()

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

    def play_index(self, index: int, start_position: int = 0):
        if 0 <= index < len(self.queue):
            was_playing = (
                self.media_player.playbackState() == QMediaPlayer.PlayingState
            )
            self.current_index = index
            item = self.queue[index]
            self.pending_position = max(0, start_position)
            self.media_player.setSource(QUrl(item["url"]))
            self._play_with_fade(was_playing)
            self.track_changed.emit(item["song_data"])

    def load_index_paused(self, index: int, start_position: int = 0):
        if 0 <= index < len(self.queue):
            self.current_index = index
            item = self.queue[index]
            self.pending_position = max(0, start_position)
            self.media_player.setSource(QUrl(item["url"]))
            self.track_changed.emit(item["song_data"])

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            if self._pause_after_fade:
                self._start_volume_fade(1.0)
            else:
                self._start_volume_fade(0.0, pause_after=True)
        else:
            self._play_with_fade(was_playing=False)

    def _play_with_fade(self, was_playing: bool):
        should_fade_in = not was_playing or self._pause_after_fade
        if should_fade_in and not self._fade_timer.isActive():
            self._volume_level = 0.0
            self._apply_output_volume()

        self._pause_after_fade = False
        self.media_player.play()
        if should_fade_in:
            self._start_volume_fade(1.0)

    def set_position(self, position: int):
        self.media_player.setPosition(position)

    def set_volume(self, value: int):
        self._user_volume = max(0, min(value, 100)) / 100.0
        self._apply_output_volume()

    def _apply_output_volume(self):
        self.audio_output.setVolume(self._user_volume * self._volume_level)

    def _start_volume_fade(self, target_level: float, pause_after: bool = False):
        if self._fade_timer.isActive():
            self._pause_after_fade = False
            self._update_volume_fade()

        self._fade_start_level = self._volume_level
        self._fade_end_level = target_level
        self._pause_after_fade = pause_after
        self._fade_clock.restart()
        self._fade_timer.start()
        self._apply_fade_progress(0.0)

    def _update_volume_fade(self):
        progress = min(
            self._fade_clock.elapsed() / FADE_DURATION_MS,
            1.0,
        )
        self._apply_fade_progress(progress)

    def _apply_fade_progress(self, progress: float):
        progress = max(0.0, min(progress, 1.0))
        self._volume_level = (
            self._fade_start_level
            + (self._fade_end_level - self._fade_start_level) * progress
        )
        self._apply_output_volume()

        if progress == 1.0:
            self._fade_timer.stop()
            if self._pause_after_fade:
                self._pause_after_fade = False
                self.media_player.pause()

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
        if status in (
            QMediaPlayer.LoadedMedia,
            QMediaPlayer.BufferedMedia,
        ) and self.pending_position:
            self.media_player.setPosition(self.pending_position)
            self.pending_position = 0

        if status == QMediaPlayer.EndOfMedia:
            if self.is_repeat and not self.is_shuffle:
                self.media_player.setPosition(0)
                self.media_player.play()
            else:
                self.next()