from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QWidget

from .theme import ThemePackage


class ThemeAudioController:
    def __init__(self, parent: QWidget):
        self.player = QMediaPlayer(parent)
        self.audio = QAudioOutput(parent)
        self.player.setAudioOutput(self.audio)
        self.current_path: Path | None = None
        self.title = ""
        self.enabled = False

    def apply_theme(self, theme: ThemePackage, volume: int = 35, enabled: bool = False) -> None:
        self.stop()
        path = theme.music_path()
        self.current_path = path
        self.title = str((theme.music or {}).get("title") or theme.name)
        self.enabled = bool(enabled and path)
        self.set_volume(volume)
        if path:
            self.player.setSource(QUrl.fromLocalFile(str(path)))

    def has_music(self) -> bool:
        return self.current_path is not None

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def play_pause(self) -> bool:
        if not self.has_music():
            return False
        if self.is_playing():
            self.player.pause()
            return False
        self.player.play()
        return True

    def stop(self) -> None:
        self.player.stop()

    def set_volume(self, volume: int) -> None:
        clamped = max(0, min(100, int(volume)))
        self.audio.setVolume(clamped / 100)
