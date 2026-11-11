#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Утилиты для работы с аудио
"""

import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from core.debug_core import get_debugger, debug_trace
from core.dependency_manager import get_dependency_manager
from core.context import AudioFormat


class AudioUtils:
    """Утилиты для работы с аудиофайлами"""

    # Пресеты для FFmpeg
    FFMPEG_PRESETS = {
        AudioFormat.AAC: {
            "codec": "aac",
            "container": "m4a",
            "default_bitrate": "64k",
            "extra_args": ["-movflags", "+faststart"],
        },
        AudioFormat.MP3: {
            "codec": "libmp3lame",
            "container": "mp3",
            "default_bitrate": "128k",
            "extra_args": ["-q:a", "2"],
        },
        AudioFormat.WAV: {
            "codec": "pcm_s16le",
            "container": "wav",
            "default_bitrate": None,
            "extra_args": [],
        },
    }

    def __init__(self):
        self.debug = get_debugger()
        self.deps = get_dependency_manager()
        self._ffmpeg_available = None

    def is_ffmpeg_available(self) -> bool:
        """Проверяет доступность ffmpeg"""
        if self._ffmpeg_available is None:
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
                self._ffmpeg_available = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                self._ffmpeg_available = False
                self.debug.log_warning("FFmpeg не найден")
        return self._ffmpeg_available

    @debug_trace
    def get_wav_info(self, wav_path: Path) -> Optional[Tuple[int, int, float]]:
        """
        Получает информацию о WAV файле.
        Возвращает (sample_rate, channels, duration_seconds).
        """
        if not self.deps.is_available("scipy.io.wavfile"):
            return None

        try:
            rate, data = self.deps.wavfile.read(str(wav_path))

            if len(data.shape) > 1:
                channels = data.shape[1]
                samples = data.shape[0]
            else:
                channels = 1
                samples = len(data)

            duration = samples / rate

            self.debug.log_audio_info(str(wav_path), duration, rate, channels)
            return rate, channels, duration
        except Exception as e:
            self.debug.log_error(f"Ошибка чтения WAV: {wav_path}", e)
            return None

    def write_metadata(self, audio_path: Path, metadata: Dict[str, Any]) -> bool:
        """
        Записывает метаданные в аудиофайл через ffmpeg.
        """
        if not self.is_ffmpeg_available():
            self.debug.log_warning("FFmpeg недоступен, метаданные не сохранены")
            return False

        # Формируем аргументы для ffmpeg
        metadata_args = []
        for key, value in metadata.items():
            # Очищаем значение от недопустимых символов
            clean_value = str(value).replace('"', "'").replace('\n', ' ')[:500]
            metadata_args.extend(['-metadata', f'{key}={clean_value}'])

        # Создаём временный файл
        temp_path = audio_path.with_suffix('.temp' + audio_path.suffix)

        cmd = [
            'ffmpeg',
            '-i', str(audio_path),
            *metadata_args,
            '-c', 'copy',
            '-y', str(temp_path)
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            # Заменяем оригинальный файл
            temp_path.replace(audio_path)
            self.debug.log(f"✅ Метаданные записаны в: {audio_path.name}", level='INFO')
            return True
        except Exception as e:
            self.debug.log_error(f"Ошибка записи метаданных", e)
            if temp_path.exists():
                temp_path.unlink()
            return False


    @debug_trace
    def convert_audio(
        self,
        input_path: Path,
        output_path: Path,
        format: AudioFormat,
        bitrate: Optional[str] = None,
        sample_rate: int = 24000,
    ) -> bool:
        """
        Конвертирует аудио в указанный формат через FFmpeg.
        """
        if not self.is_ffmpeg_available():
            self.debug.log_error("FFmpeg недоступен")
            return False

        preset = self.FFMPEG_PRESETS.get(format)
        if not preset:
            self.debug.log_error(f"Неподдерживаемый формат: {format}")
            return False

        # Определяем выходной путь с правильным расширением
        output_path = output_path.with_suffix(f".{preset['container']}")

        bitrate = bitrate or preset["default_bitrate"]

        cmd = [
            "ffmpeg",
            "-i",
            str(input_path),
            "-c:a",
            preset["codec"],
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
        ]

        if bitrate:
            cmd.extend(["-b:a", bitrate])

        cmd.extend(preset["extra_args"])
        cmd.extend(["-y", str(output_path)])

        self.debug.log(
            f"Конвертация: {input_path.name} -> {output_path.name}", level="INFO"
        )

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.debug.log_file_operation(
                "convert", str(output_path), output_path.stat().st_size, True
            )
            return True
        except subprocess.CalledProcessError as e:
            self.debug.log_error("Ошибка конвертации", e)
            self.debug.log(f"STDERR: {e.stderr[:500]}", level="ERROR")
            return False

    @debug_trace
    def concat_wav_files(self, wav_files: List[Path], output_path: Path) -> bool:
        """
        Объединяет несколько WAV файлов в один.
        """
        if not self.is_ffmpeg_available():
            return False

        # Создаём файл со списком
        list_file = output_path.with_suffix(".txt")
        with open(list_file, "w") as f:
            for wav in wav_files:
                f.write(f"file '{wav.absolute()}'\n")

        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            "-y",
            str(output_path),
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            list_file.unlink()
            return True
        except Exception as e:
            self.debug.log_error("Ошибка объединения WAV", e)
            if list_file.exists():
                list_file.unlink()
            return False

    @debug_trace
    def apply_deesser(
        self,
        input_path: Path,
        output_path: Path,
        threshold_db: float = -25.0,
        center_freq: int = 6000,
        q: float = 1.0,
    ) -> bool:
        """Применяет de-esser к аудио"""
        if not (
            self.deps.is_available("scipy.signal")
            and self.deps.is_available("scipy.io.wavfile")
        ):
            self.debug.log_warning("SciPy недоступен, de-esser отключён")
            return False

        import numpy as np

        try:
            rate, data = self.deps.wavfile.read(str(input_path))
            audio_float = data.astype(np.float32) / 32768.0

            nyquist = rate / 2
            bandwidth = center_freq / q
            low = max(center_freq - bandwidth / 2, 100) / nyquist
            high = min(center_freq + bandwidth / 2, nyquist - 100) / nyquist

            b, a = self.deps.scipy_signal.butter(4, [low, high], btype="band")
            sibilant = self.deps.scipy_signal.lfilter(b, a, audio_float)
            envelope = np.abs(sibilant)

            kernel = int(rate * 0.01)
            kernel = kernel + 1 if kernel % 2 == 0 else kernel
            envelope = self.deps.scipy_signal.medfilt(envelope, kernel_size=kernel)

            threshold_linear = 10 ** (threshold_db / 20)
            gain = np.ones_like(envelope)
            mask = envelope > threshold_linear
            gain[mask] = (threshold_linear / envelope[mask]) ** 0.7

            audio_processed = audio_float - sibilant + sibilant * gain
            self.deps.wavfile.write(
                str(output_path), rate, (audio_processed * 32767).astype(np.int16)
            )

            self.debug.log("✅ De-esser применён", level="INFO")
            return True
        except Exception as e:
            self.debug.log_error("Ошибка de-esser", e)
            return False

    @debug_trace
    def apply_spectral_nr(
        self, input_path: Path, output_path: Path, amount: float = 0.5
    ) -> bool:
        """Применяет спектральное шумоподавление"""
        if not (
            self.deps.is_available("noisereduce")
            and self.deps.is_available("scipy.io.wavfile")
        ):
            self.debug.log_warning("noisereduce недоступен")
            return False

        import numpy as np

        try:
            rate, data = self.deps.wavfile.read(str(input_path))
            audio_float = data.astype(np.float32) / 32768.0

            reduced = self.deps.noisereduce.reduce_noise(
                y=audio_float,
                sr=rate,
                stationary=True,
                prop_decrease=amount,
                n_fft=2048,
                win_length=2048,
                hop_length=512,
            )

            self.deps.wavfile.write(
                str(output_path), rate, (reduced * 32767).astype(np.int16)
            )

            self.debug.log("✅ Шумоподавление применено", level="INFO")
            return True
        except Exception as e:
            self.debug.log_error("Ошибка шумоподавления", e)
            return False

    @debug_trace
    def apply_lowpass(
        self, input_path: Path, output_path: Path, cutoff_freq: int = 4000
    ) -> bool:
        """Применяет low-pass фильтр"""
        if not (
            self.deps.is_available("scipy.signal")
            and self.deps.is_available("scipy.io.wavfile")
        ):
            return False

        import numpy as np

        try:
            rate, data = self.deps.wavfile.read(str(input_path))
            audio_float = data.astype(np.float32) / 32768.0

            b, a = self.deps.scipy_signal.butter(
                4, cutoff_freq / (rate / 2), btype="low"
            )
            filtered = self.deps.scipy_signal.filtfilt(b, a, audio_float)

            self.deps.wavfile.write(
                str(output_path), rate, (filtered * 32767).astype(np.int16)
            )

            self.debug.log("✅ Low-pass применён", level="INFO")
            return True
        except Exception as e:
            self.debug.log_error("Ошибка low-pass", e)
            return False

    @debug_trace
    def normalize_loudness(
        self, input_path: Path, output_path: Path, target_loudness: float = -16.0
    ) -> bool:
        """Нормализует громкость по LUFS"""
        import numpy as np

        if self.deps.is_available("pyloudnorm") and self.deps.is_available(
            "scipy.io.wavfile"
        ):
            try:
                rate, data = self.deps.wavfile.read(str(input_path))
                audio_float = data.astype(np.float32) / 32768.0

                meter = self.deps.pyloudnorm.Meter(rate)
                current = meter.integrated_loudness(audio_float)

                if np.isfinite(current):
                    gain = 10 ** ((target_loudness - current) / 20)
                    normalized = audio_float * gain
                    self.deps.wavfile.write(
                        str(output_path), rate, (normalized * 32767).astype(np.int16)
                    )
                    self.debug.log(
                        f"✅ Нормализация: {current:.1f} → {target_loudness:.1f} LUFS",
                        level="INFO",
                    )
                    return True
            except Exception as e:
                self.debug.log_error("Ошибка нормализации LUFS", e)

        # Fallback: пиковая нормализация
        try:
            rate, data = self.deps.wavfile.read(str(input_path))
            max_val = np.max(np.abs(data))
            if max_val > 0:
                normalized = (data * (0.9 * 32767 / max_val)).astype(np.int16)
                self.deps.wavfile.write(str(output_path), rate, normalized)
                self.debug.log("✅ Пиковая нормализация применена", level="INFO")
                return True
        except Exception as e:
            self.debug.log_error("Ошибка пиковой нормализации", e)

        return False

    @debug_trace
    def add_room_tone(
        self, input_path: Path, output_path: Path, tone_level_db: float = -70.0
    ) -> bool:
        """Добавляет комнатный тон (pink noise)"""
        if not (
            self.deps.is_available("scipy.io.wavfile")
            and self.deps.is_available("numpy")
        ):
            return False

        import numpy as np

        try:
            rate, data = self.deps.wavfile.read(str(input_path))
            audio_float = data.astype(np.float32) / 32768.0

            samples = len(audio_float)
            white = np.random.normal(0, 1, samples)
            pink = np.zeros_like(white)

            b0, b1, b2 = 0.99765, -1.98553, 0.98788
            a1, a2 = -1.98553, 0.98788

            x1 = x2 = y1 = y2 = 0
            for i in range(samples):
                y0 = b0 * white[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
                pink[i] = y0
                x2, x1 = x1, white[i]
                y2, y1 = y1, y0

            pink = pink / np.std(pink) * 0.1 * (10 ** (tone_level_db / 20))
            mixed = audio_float + pink

            self.deps.wavfile.write(
                str(output_path), rate, (mixed * 32767).astype(np.int16)
            )

            self.debug.log("✅ Room tone добавлен", level="INFO")
            return True
        except Exception as e:
            self.debug.log_error("Ошибка room tone", e)
            return False
