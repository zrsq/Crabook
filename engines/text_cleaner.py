#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Движок очистки текста
"""

import re
from typing import Tuple, List

from core.debug_core import get_debugger, debug_trace
from utils.text_utils import TextUtils


class TextCleaner:
    """
    Движок очистки текста.
    Удаляет мусор, нормализует форматирование.
    """

    def __init__(self):
        self.debug = get_debugger()
        self.text_utils = TextUtils()

    @debug_trace
    def clean(self, text: str) -> Tuple[str, List[str]]:
        """
        Очищает текст и возвращает (очищенный_текст, список_абзацев).
        """
        self.debug.log("Начало очистки текста", level="INFO")

        # Базовая очистка через TextUtils
        cleaned, paragraphs = self.text_utils.clean_text(text)

        # Дополнительная очистка
        cleaned = self._remove_page_numbers(cleaned)
        cleaned = self._normalize_spaces(cleaned)
        cleaned = self._fix_common_typos(cleaned)

        # Обновляем абзацы
        paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]

        self.debug.log(f"Очистка завершена: {len(paragraphs)} абзацев", level="INFO")
        return cleaned, paragraphs

    def _remove_page_numbers(self, text: str) -> str:
        """Удаляет номера страниц"""
        # Одинокие числа на отдельных строках
        text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)
        return text

    def _normalize_spaces(self, text: str) -> str:
        """Нормализует пробелы"""
        # Множественные пробелы
        text = re.sub(r" +", " ", text)
        # Пробелы перед знаками препинания
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        # Множественные переносы строк
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _fix_common_typos(self, text: str) -> str:
        """Исправляет распространённые опечатки"""
        # Заменяем латинские буквы на кириллицу в русских словах
        replacements = {
            "e": "е",
            "E": "Е",
            "y": "у",
            "Y": "У",
            "k": "к",
            "K": "К",
            "o": "о",
            "O": "О",
            "p": "р",
            "P": "Р",
            "a": "а",
            "A": "А",
            "c": "с",
            "C": "С",
            "x": "х",
            "X": "Х",
        }

        # Только для слов, которые выглядят как русские
        def fix_word(match):
            word = match.group(0)
            # Если в слове есть кириллица, заменяем латиницу
            if re.search(r"[а-яА-ЯёЁ]", word):
                for lat, cyr in replacements.items():
                    word = word.replace(lat, cyr)
            return word

        text = re.sub(r"\b[а-яА-ЯёЁa-zA-Z]+\b", fix_word, text)
        return text


class ParagraphSplitter:
    """Разбивает текст на абзацы для обработки"""

    def __init__(self):
        self.debug = get_debugger()

    @debug_trace
    def split_into_paragraphs(self, text: str) -> List[str]:
        """Разбивает текст на абзацы"""
        paragraphs = []

        for line in text.split("\n"):
            line = line.strip()
            if line:
                paragraphs.append(line)

        self.debug.log(f"Разбито на {len(paragraphs)} абзацев", level="VERBOSE")
        return paragraphs

    @debug_trace
    def split_into_sentences(self, paragraph: str) -> List[str]:
        """Разбивает абзац на предложения"""
        # Учитываем диалоги и прямую речь
        sentences = re.split(r'(?<=[.!?…])\s+(?=[А-ЯA-Z"\'«—])', paragraph)
        return [s.strip() for s in sentences if s.strip()]
