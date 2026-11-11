#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Движок обработки аудио
"""

from pathlib import Path
from typing import List
from dataclasses import dataclass

from core.debug_core import get_debugger, debug_trace
from core.config_manager import AudioProcessingConfig
from utils.audio_utils import AudioUtils


@dataclass
class ProcessingOptions:
    """Опции обработки аудио"""

    enable_deesser: bool = True
    deesser_threshold: float = -25.0
    deesser_center_freq: int = 6000
    deesser_q: float = 1.0

    enable_spectral_nr: bool = True
    spectral_nr_amount: float = 0.5

    enable_room_tone: bool = False
    room_tone_level: float = -70.0

    enable_lowpass: bool = False
    lowpass_cutoff: int = 4000

    enable_normalization: bool = True
    target_volume: float = -16.0


class AudioProcessor:
    """
    Движок постобработки аудио.
    Применяет de-esser, шумоподавление, нормализацию и т.д.
    """

    def __init__(
        self, options: ProcessingOptions = None, config: AudioProcessingConfig = None
    ):
        self.debug = get_debugger()
        self.audio_utils = AudioUtils()

        if options:
            self.options = options
        elif config:
            self.options = ProcessingOptions(
                enable_deesser=config.enable_deesser,
                deesser_threshold=config.deesser_threshold,
                deesser_center_freq=config.deesser_center_freq,
                deesser_q=config.deesser_q,
                enable_spectral_nr=config.enable_spectral_nr,
                spectral_nr_amount=config.spectral_nr_amount,
                enable_room_tone=config.enable_room_tone,
                room_tone_level=config.room_tone_level,
                enable_lowpass=config.enable_lowpass_filter,
                lowpass_cutoff=config.lowpass_cutoff_freq,
                enable_normalization=config.enable_normalization,
                target_volume=config.target_volume,
            )
        else:
            self.options = ProcessingOptions()

    @debug_trace
    def process(self, input_path: Path, output_path: Path = None) -> Path:
        """
        Применяет все этапы постобработки к аудиофайлу.
        """
        if output_path is None:
            output_path = input_path.with_suffix(".processed.wav")

        current_file = input_path
        temp_files = []

        # De-esser
        if self.options.enable_deesser:
            deessed = current_file.with_suffix(".deessed.wav")
            if self.audio_utils.apply_deesser(
                current_file,
                deessed,
                self.options.deesser_threshold,
                self.options.deesser_center_freq,
                self.options.deesser_q,
            ):
                current_file = deessed
                temp_files.append(deessed)

        # Шумоподавление
        if self.options.enable_spectral_nr:
            nr_file = current_file.with_suffix(".nr.wav")
            if self.audio_utils.apply_spectral_nr(
                current_file, nr_file, self.options.spectral_nr_amount
            ):
                current_file = nr_file
                temp_files.append(nr_file)

        # Room tone
        if self.options.enable_room_tone:
            room_file = current_file.with_suffix(".room.wav")
            if self.audio_utils.add_room_tone(
                current_file, room_file, self.options.room_tone_level
            ):
                current_file = room_file
                temp_files.append(room_file)

        # Low-pass фильтр
        if self.options.enable_lowpass:
            filtered = current_file.with_suffix(".filtered.wav")
            if self.audio_utils.apply_lowpass(
                current_file, filtered, self.options.lowpass_cutoff
            ):
                current_file = filtered
                temp_files.append(filtered)

        # Нормализация
        if self.options.enable_normalization:
            normalized = current_file.with_suffix(".norm.wav")
            if self.audio_utils.normalize_loudness(
                current_file, normalized, self.options.target_volume
            ):
                current_file = normalized
                temp_files.append(normalized)

        # Копируем результат в output_path если нужно
        if current_file != output_path:
            import shutil

            shutil.copy2(str(current_file), str(output_path))

        # Удаляем временные файлы
        for temp in temp_files:
            if temp.exists() and temp != output_path:
                temp.unlink()

        self.debug.log(f"✅ Постобработка завершена: {output_path}", level="INFO")
        return output_path

    @debug_trace
    def process_batch(self, files: List[Path], output_dir: Path = None) -> List[Path]:
        """
        Обрабатывает несколько аудиофайлов.
        """
        results = []

        for i, file in enumerate(files):
            if output_dir:
                output_path = output_dir / f"processed_{i:04d}.wav"
            else:
                output_path = None

            processed = self.process(file, output_path)
            results.append(processed)

            self.debug.log(f"Прогресс обработки: {i + 1}/{len(files)}", level="VERBOSE")

        return results
