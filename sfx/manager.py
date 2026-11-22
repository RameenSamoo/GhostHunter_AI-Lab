"""Loads the synthesized .wav files and plays them through pygame.mixer.

If no audio device is available the manager silently becomes a no-op, so
the game still runs on machines (or CI) without sound.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from config import HEARTBEAT_MAX_INTERVAL, HEARTBEAT_MIN_INTERVAL
from .synth import generate_all


class SoundManager:
    def __init__(self, audio_dir: Path, muted: bool = False):
        generate_all(audio_dir)
        self.enabled = False
        self.muted = muted
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._heartbeat_timer = 0.0
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(16)
            for path in audio_dir.glob("*.wav"):
                self.sounds[path.stem] = pygame.mixer.Sound(str(path))
            self._drone_channel = pygame.mixer.Channel(0)
            self._heart_channel = pygame.mixer.Channel(1)
            pygame.mixer.set_reserved(2)
            self.enabled = True
        except pygame.error:
            self.enabled = False

    # ---------------------------------------------------------------- basics
    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled or self.muted or name not in self.sounds:
            return
        snd = self.sounds[name]
        snd.set_volume(volume)
        snd.play()

    def start_drone(self) -> None:
        if self.enabled and not self.muted and not self._drone_channel.get_busy():
            self._drone_channel.play(self.sounds["ambient_drone"], loops=-1, fade_ms=1500)
            self._drone_channel.set_volume(0.55)

    def stop_drone(self, fade_ms: int = 600) -> None:
        if self.enabled:
            self._drone_channel.fadeout(fade_ms)

    def pause_all(self) -> None:
        if self.enabled:
            pygame.mixer.pause()

    def resume_all(self) -> None:
        if self.enabled:
            pygame.mixer.unpause()

    # -------------------------------------------------------------- heartbeat
    @staticmethod
    def heartbeat_interval(reading: int | None, max_distance: int) -> float:
        """Seconds between beats from the latest *noisy reading* (never the
        ghost's true position). Reading 0 -> fastest, map max -> slowest."""
        if reading is None or max_distance <= 0:
            return HEARTBEAT_MAX_INTERVAL
        frac = min(1.0, max(0.0, reading / max_distance))
        return HEARTBEAT_MIN_INTERVAL + (HEARTBEAT_MAX_INTERVAL - HEARTBEAT_MIN_INTERVAL) * frac

    def reset_heartbeat(self) -> None:
        self._heartbeat_timer = 0.0

    def update_heartbeat(self, dt: float, reading: int | None, max_distance: int) -> bool:
        """Advance the heartbeat clock; returns True on the frame a beat fires."""
        interval = self.heartbeat_interval(reading, max_distance)
        self._heartbeat_timer += dt
        if self._heartbeat_timer < interval:
            return False
        self._heartbeat_timer = 0.0
        if self.enabled and not self.muted:
            closeness = 1.0 - (interval - HEARTBEAT_MIN_INTERVAL) / (HEARTBEAT_MAX_INTERVAL - HEARTBEAT_MIN_INTERVAL)
            self._heart_channel.set_volume(0.35 + 0.65 * closeness)
            self._heart_channel.play(self.sounds["heartbeat"])
        return True
