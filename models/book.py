#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модель книги
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
import re


@dataclass
class Chapter:
    """Модель главы"""

    title: str
    content: str
    index: int
    start_pos: int = 0
    end_pos: int = 0
    word_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.word_count:
            self.word_count = len(re.findall(r"\b[а-яА-ЯёЁa-zA-Z]+\b", self.content))


@dataclass
class Book:
    """Модель книги"""

    path: Path
    title: str
    author: Optional[str] = None
    raw_text: str = ""
    cleaned_text: str = ""
    chapters: List[Chapter] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path, text: str = "") -> "Book":
        """Создаёт модель книги из файла"""
        title = path.stem

        # Пытаемся извлечь автора из имени файла
        author = None
        if " - " in title:
            parts = title.split(" - ")
            if len(parts) >= 2:
                author = parts[0]
                title = " - ".join(parts[1:])

        return cls(path=path, title=title, author=author, raw_text=text)

    @property
    def total_word_count(self) -> int:
        """Общее количество слов"""
        if self.chapters:
            return sum(c.word_count for c in self.chapters)
        return len(
            re.findall(r"\b[а-яА-ЯёЁa-zA-Z]+\b", self.cleaned_text or self.raw_text)
        )

    @property
    def estimated_duration_minutes(self) -> float:
        """
        Оценка длительности аудиокниги в минутах.
        Средняя скорость: 150 слов в минуту.
        """
        return self.total_word_count / 150

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует модель в словарь"""
        return {
            "path": str(self.path),
            "title": self.title,
            "author": self.author,
            "total_words": self.total_word_count,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "chapters_count": len(self.chapters),
            "metadata": self.metadata,
        }
