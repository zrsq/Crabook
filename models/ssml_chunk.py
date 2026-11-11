#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модель SSML чанка
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class SSMLChunk:
    """Модель чанка SSML для озвучивания"""

    content: str
    index: int
    chapter_index: Optional[int] = None
    chapter_title: Optional[str] = None
    word_count: int = 0
    char_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.char_count = len(self.content)
        if not self.word_count:
            import re

            # Не считаем теги
            text_only = re.sub(r"<[^>]+>", "", self.content)
            self.word_count = len(re.findall(r"\b[а-яА-ЯёЁa-zA-Z]+\b", text_only))

    @property
    def estimated_duration_seconds(self) -> float:
        """Оценка длительности в секундах"""
        return (self.word_count / 150) * 60


@dataclass
class SSMLDocument:
    """Модель SSML документа"""

    content: str
    chunks: list = field(default_factory=list)
    validation_errors: list = field(default_factory=list)
    validation_warnings: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Валиден ли документ"""
        return len(self.validation_errors) == 0

    @property
    def total_chunks(self) -> int:
        """Количество чанков"""
        return len(self.chunks)

    @property
    def total_words(self) -> int:
        """Общее количество слов"""
        return sum(c.word_count for c in self.chunks)
