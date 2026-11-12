#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Контекст выполнения - передаётся между всеми этапами обработки
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum


class ProcessingMode(Enum):
    """Режим обработки"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class AudioFormat(Enum):
    """Формат выходного аудио"""
    AAC = "aac"
    MP3 = "mp3"
    WAV = "wav"


@dataclass
class ProcessingOptions:
    """Опции обработки"""
    mode: ProcessingMode = ProcessingMode.PARALLEL
    genre: Optional[str] = None
    voice: Optional[str] = None
    sample_rate: Optional[int] = None
    bitrate: Optional[str] = None
    chunk_size: Optional[int] = None
    workers: Optional[int] = None
    split_chapters: bool = False
    skip_validation: bool = False
    no_convert: bool = False
    output_format: AudioFormat = AudioFormat.AAC
    output_formats: List[AudioFormat] = field(default_factory=list)

    # Аудио постобработка
    lowpass: bool = False
    lowpass_cutoff: Optional[int] = None
    no_deesser: bool = False
    deesser_threshold: Optional[float] = None
    deesser_freq: Optional[int] = None
    no_spectral_nr: bool = False
    spectral_nr_amount: Optional[float] = None
    room_tone: bool = False
    room_tone_level: Optional[float] = None
    no_normalize: bool = False
    target_volume: Optional[float] = None


@dataclass
class ExecutionContext:
    """Контекст выполнения"""
    input_path: Path
    output_path: Optional[Path] = None
    options: ProcessingOptions = field(default_factory=ProcessingOptions)
    
    debug: Optional[Any] = None
    deps: Optional[Any] = None
    config: Optional[Any] = None
    book_config: Optional[Any] = None
    
    raw_text: Optional[str] = None
    cleaned_text: Optional[str] = None
    paragraphs: List[str] = field(default_factory=list)
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    
    ssml_text: Optional[str] = None
    ssml_chunks: List[Dict[str, Any]] = field(default_factory=list)
    validation_result: Optional[Dict[str, Any]] = None
    
    audio_files: List[Path] = field(default_factory=list)
    final_output: Optional[Path] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str):
        self.errors.append(error)
        if self.debug:
            self.debug.log_error(error)

    def add_warning(self, warning: str):
        self.warnings.append(warning)
        if self.debug:
            self.debug.log_warning(warning)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def is_debug_mode(self) -> bool:
        return self.options.mode == ProcessingMode.SEQUENTIAL

    def get_effective_genre(self) -> str:
        if self.options.genre:
            return self.options.genre
        if self.config and hasattr(self.config, 'processing_config'):
            return self.config.processing_config.default_genre
        return "fiction"

    def get_effective_voice(self) -> str:
        if self.options.voice:
            return self.options.voice
        if self.config and hasattr(self.config, 'tts_config'):
            return self.config.tts_config.default_voice
        return "xenia"

    def get_effective_sample_rate(self) -> int:
        if self.options.sample_rate:
            return self.options.sample_rate
        if self.config and hasattr(self.config, 'tts_config'):
            return self.config.tts_config.default_sample_rate
        return 24000

    def get_effective_bitrate(self) -> str:
        if self.options.bitrate:
            return self.options.bitrate
        
        format_defaults = {
            AudioFormat.AAC: "64k",
            AudioFormat.MP3: "128k",
            AudioFormat.WAV: None,
        }
        
        fmt = self.options.output_format
        if fmt in format_defaults and format_defaults[fmt]:
            return format_defaults[fmt]
        
        if self.config and hasattr(self.config, 'tts_config'):
            return self.config.tts_config.default_bitrate
        return "64k"

    def get_effective_chunk_size(self) -> int:
        if self.options.chunk_size:
            return self.options.chunk_size
        if self.config and hasattr(self.config, 'tts_config'):
            return self.config.tts_config.default_chunk_size
        return 500  # FIX BUG-8: согласовано с TTSConfig.default_chunk_size

    def get_effective_workers(self) -> int:
        if self.options.workers:
            return self.options.workers
        if self.config and hasattr(self.config, 'tts_config'):
            return self.config.tts_config.default_workers
        return 4
