#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модель аудио чанка
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class AudioChunkStatus(Enum):
    """Статус аудио чанка"""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    POST_PROCESSING = "post_processing"


@dataclass
class AudioChunk:
    """Модель аудио чанка"""

    ssml_content: str
    index: int
    chapter_index: Optional[int] = None
    status: AudioChunkStatus = AudioChunkStatus.PENDING
    wav_path: Optional[Path] = None
    processed_path: Optional[Path] = None
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    file_size: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        """Готов ли чанк"""
        return self.status == AudioChunkStatus.COMPLETED and self.wav_path is not None

    @property
    def duration_formatted(self) -> str:
        """Форматированная длительность"""
        minutes = int(self.duration_seconds // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class AudioBook:
    """Модель аудиокниги"""

    chunks: list = field(default_factory=list)
    output_path: Optional[Path] = None
    final_duration_seconds: float = 0.0
    total_file_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def completed_chunks(self) -> int:
        """Количество завершённых чанков"""
        return sum(1 for c in self.chunks if c.status == AudioChunkStatus.COMPLETED)

    @property
    def failed_chunks(self) -> int:
        """Количество упавших чанков"""
        return sum(1 for c in self.chunks if c.status == AudioChunkStatus.FAILED)

    @property
    def is_complete(self) -> bool:
        """Завершена ли генерация всех чанков"""
        return all(
            c.status in (AudioChunkStatus.COMPLETED, AudioChunkStatus.FAILED)
            for c in self.chunks
        )

    @property
    def total_duration_formatted(self) -> str:
        """Форматированная общая длительность"""
        hours = int(self.final_duration_seconds // 3600)
        minutes = int((self.final_duration_seconds % 3600) // 60)
        seconds = int(self.final_duration_seconds % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
