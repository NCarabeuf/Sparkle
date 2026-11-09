from array import array
from collections import deque
import logging
import os
from pathlib import Path
import random
import sys
from threading import Lock
from time import perf_counter

from PySide6.QtCore import QEventLoop, QIODevice, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat, QAudioSink, QMediaDevices

from src.asset_manager import get_asset


# Minimum time between the START of any two sounds, in seconds.
# Events during this interval are ignored, never queued or played late.
SOUND_COOLDOWN_SECONDS = 0.2

# Empty: use the Windows default output. Otherwise use a unique part of its
# name, e.g. "Realtek", to bypass Bluetooth for Sparkle only. Restart to apply.
SOUND_OUTPUT_DEVICE = ""

SOUND_CATEGORIES = ("cff", "crush", "glass", "shine", "talk")
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
# About 21 ms at 48 kHz stereo. Qt fills this buffer from the GUI thread;
# 5 ms is shorter than a Windows audio period and starves the output.
AUDIO_BUFFER_BYTES = 4096


def select_audio_output(name):
    default = QMediaDevices.defaultAudioOutput()
    name = name.strip().casefold()
    if not name:
        return default
    devices = QMediaDevices.audioOutputs()
    exact = [device for device in devices if device.description().casefold() == name]
    matches = exact or [device for device in devices
                        if name in device.description().casefold()]
    if len(matches) == 1:
        return matches[0]
    logging.getLogger(__name__).warning(
        "Sortie audio %r introuvable ou ambigue ; sortie par defaut : %s. "
        "Sorties disponibles : %s",
        name, default.description(),
        "; ".join(device.description() for device in devices),
    )
    return default


def configure_audio_backend():
    if sys.platform != "win32":
        return
    # Qt 6.12 probes MF video encoders even when only decoding audio.
    # Skip those unused encoders, keeping audio decoding and error logs intact.
    name = "QT_FFMPEG_EXCLUDE_ENCODERS"
    excluded = {value.strip().lower() for value in os.environ.get(name, "").split(",")
                if value.strip()}
    excluded.update(("av1_mf", "h264_mf", "hevc_mf"))
    os.environ[name] = ",".join(sorted(excluded))


def trim_leading_silence(samples, sample_rate, channels):
    """Remove quiet MP3 padding in memory, retaining 2 ms before the attack."""
    first = next((i for i, value in enumerate(samples) if abs(value) >= 100), None)
    if first is None:
        return samples
    cut_frames = max(0, first // channels - sample_rate * 2 // 1000)
    return samples[cut_frames * channels:]


class AudioMixer(QIODevice):
    """Every accepted sound has its own position and plays to completion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._voices = []
        self._lock = Lock()
        # Disable QIODevice read-ahead, which otherwise adds audible latency.
        self.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Unbuffered)

    def add_sound(self, samples):
        if samples:
            with self._lock:
                self._voices.append((samples, 0))

    def clear(self):
        with self._lock:
            self._voices.clear()

    def isSequential(self):
        return True

    def bytesAvailable(self):
        return AUDIO_BUFFER_BYTES

    def readData(self, maximum):
        sample_count = maximum // 4 * 2  # Whole stereo frames, signed 16-bit PCM.
        with self._lock:
            if not self._voices:
                return bytes(sample_count * 2)
            mixed = [0] * sample_count
            remaining = []
            for samples, offset in self._voices:
                count = min(sample_count, len(samples) - offset)
                for index, value in enumerate(samples[offset:offset + count]):
                    mixed[index] += value
                offset += count
                if offset < len(samples):
                    remaining.append((samples, offset))
            self._voices = remaining
        return array("h", (
            32767 if value > 32767 else -32768 if value < -32768 else value
            for value in mixed
        )).tobytes()


class SoundController(QObject):
    preloaded = Signal()

    def __init__(self, parent=None, *, sound_root: Path | None = None):
        super().__init__(parent)
        configure_audio_backend()
        self.cooldown_seconds = SOUND_COOLDOWN_SECONDS
        self._last_started = None
        self._closed = False
        self.ready = False
        self._samples = {category: [] for category in SOUND_CATEGORIES}
        self._sources = deque()
        root = sound_root if sound_root is not None else get_asset("sfx")
        for category in SOUND_CATEGORIES:
            folder = root / category
            if folder.is_dir():
                self._sources.extend(
                    (category, path) for path in sorted(folder.iterdir())
                    if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
                )
        self.format = QAudioFormat()
        self.format.setSampleRate(48000)
        self.format.setChannelCount(2)
        self.format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self.mixer = AudioMixer(self)
        self.output_device = select_audio_output(SOUND_OUTPUT_DEVICE)
        self.sink = QAudioSink(self.output_device, self.format, self)
        self.sink.setVolume(0.7)
        self.sink.setBufferSize(AUDIO_BUFFER_BYTES)
        # Silence keeps the output device open between actions.
        self.sink.start(self.mixer)
        self._decoder = QAudioDecoder(self)
        self._decoder.setAudioFormat(self.format)
        self._decoder.bufferReady.connect(self._read_buffer)
        self._decoder.finished.connect(self._decoded)
        self._decoder.error.connect(self._decode_error)
        self._current_source = None
        self._chunks = []
        QTimer.singleShot(0, self._next_source)

    def _next_source(self):
        if self._closed:
            return
        if not self._sources:
            self.ready = True
            self.preloaded.emit()
            return
        source = self._sources.popleft()
        # stop/setSource can emit finished for the OLD source synchronously.
        self._decoder.stop()
        self._decoder.setSource(QUrl.fromLocalFile(str(source[1].resolve())))
        self._current_source = source
        self._chunks = []
        self._decoder.start()

    def _read_buffer(self):
        buffer = self._decoder.read()
        if not buffer.isValid() or self._current_source is None:
            return
        fmt = buffer.format()
        if (fmt.sampleRate() != 48000 or fmt.channelCount() != 2
                or fmt.sampleFormat() != QAudioFormat.SampleFormat.Int16):
            self._decode_error("Format audio incompatible.")
            return
        self._chunks.append(bytes(buffer.data()))

    def _decoded(self):
        if self._closed or self._current_source is None:
            return
        samples = array("h")
        samples.frombytes(b"".join(self._chunks))
        if samples:
            self._samples[self._current_source[0]].append(
                trim_leading_silence(samples, 48000, 2)
            )
        self._current_source = None
        self._chunks.clear()
        QTimer.singleShot(0, self._next_source)

    def _decode_error(self, error):
        if self._closed or self._current_source is None:
            return
        message = error if isinstance(error, str) else self._decoder.errorString()
        logging.getLogger(__name__).warning("Son %s : %s", self._current_source[1], message)
        self._current_source = None
        self._chunks.clear()
        self._decoder.stop()
        QTimer.singleShot(0, self._next_source)

    def wait_until_ready(self, timeout_ms=10000):
        if self.ready or self._closed:
            return self.ready
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        self.preloaded.connect(loop.quit)
        timer.start(timeout_ms)
        loop.exec()
        timer.stop()
        self.preloaded.disconnect(loop.quit)
        return self.ready

    @Slot(str)
    def play(self, category):
        clips = self._samples.get(category)
        if self._closed or not clips:
            return False
        now = perf_counter()
        if (self._last_started is not None
                and now - self._last_started < self.cooldown_seconds):
            return False
        self.mixer.add_sound(random.choice(clips))
        self._last_started = now
        return True

    @Slot()
    def close(self):
        if self._closed:
            return
        self._closed = True
        self._decoder.stop()
        self.sink.stop()
        self.mixer.clear()
        self.mixer.close()
