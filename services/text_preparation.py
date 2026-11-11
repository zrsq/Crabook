#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сервис подготовки текста
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple
from lxml import etree

from core.debug_core import get_debugger, debug_trace, debug_timing
from core.context import ExecutionContext
from core.config_manager import ConfigManager, PauseConfig
from core.exceptions import TextExtractionError, AccentError, SSMLBuildError

from utils.file_utils import FileUtils
from utils.text_utils import TextUtils

from engines.text_cleaner import TextCleaner
from engines.accent_engine import AccentEngine
from engines.ssml_builder import SSMLBuilder, NumbersToSayAs

from models.book import Book, Chapter
from models.ssml_chunk import SSMLDocument, SSMLChunk


class TextPreparationService:
    """
    Сервис подготовки текста.
    """

    def __init__(self, context: ExecutionContext):
        self.context = context
        self.debug = context.debug or get_debugger()
        self.config = context.config or ConfigManager()

        self.file_utils = FileUtils()
        self.text_utils = TextUtils()

        self._cleaner: Optional[TextCleaner] = None
        self._accent_engine: Optional[AccentEngine] = None
        self._ssml_builder: Optional[SSMLBuilder] = None
        self._numbers_converter: Optional[NumbersToSayAs] = None

        # Сохраняем финальный обработанный текст
        self.final_processed_text: Optional[str] = None
        self.final_paragraphs: Optional[List[str]] = None

    @property
    def cleaner(self) -> TextCleaner:
        if self._cleaner is None:
            self._cleaner = TextCleaner()
        return self._cleaner

    @property
    def accent_engine(self) -> AccentEngine:
        if self._accent_engine is None:
            overrides = self.config.get_merged_accent_overrides()
            self._accent_engine = AccentEngine(
                model='turbo3.1',
                overrides=overrides
            )
        return self._accent_engine

    @property
    def ssml_builder(self) -> SSMLBuilder:
        if self._ssml_builder is None:
            genre = self.context.get_effective_genre()
            pause_config = self.config.get_pause_config_for_genre(genre)
            self._ssml_builder = SSMLBuilder(
                pause_config=pause_config,
                config_manager=self.config
            )
            self._ssml_builder.set_keywords_effects(
                self.config.get_merged_effects()
            )
        return self._ssml_builder

    @property
    def numbers_converter(self) -> NumbersToSayAs:
        if self._numbers_converter is None:
            self._numbers_converter = NumbersToSayAs()
        return self._numbers_converter

    @debug_trace
    @debug_timing
    def process(self) -> str:
        """
        Основной метод обработки.
        Готовит финальный текст со ВСЕМИ трансформациями,
        но НЕ строит полный SSML.
        """
        self.debug.log_stage("Подготовка текста", "start")

        # 1. Извлечение
        raw_text = self._extract_text()
        self.context.raw_text = raw_text

        book = Book.from_file(self.context.input_path, raw_text)
        self.context.metadata['book'] = book.to_dict()

        # 2. Очистка
        cleaned_text, paragraphs = self._clean_text(raw_text)
        self.context.cleaned_text = cleaned_text
        self.context.paragraphs = paragraphs

        # Сохраняем параграфы для SSML
        self.final_paragraphs = paragraphs

        if self.context.options.split_chapters:
            chapters = self._split_into_chapters(cleaned_text)
            self.context.chapters = chapters

        # 3. Применяем ВСЕ трансформации к тексту
        accented_text = self._apply_accents(cleaned_text)
        text_with_numbers = self._convert_numbers(accented_text)
        fixed_text = self._apply_manual_fixes(text_with_numbers)
        expanded_text = self._expand_abbreviations(fixed_text)

        # 4. Сохраняем финальный обработанный текст (с тегами!)
        self.final_processed_text = expanded_text
        self.context.stats['final_chars'] = len(expanded_text)

        self.debug.log_stage("Подготовка текста", "end")
        self.debug.log(f"✅ Финальный текст готов: {len(expanded_text)} символов", level='INFO')

        return expanded_text

    @debug_trace
    def _extract_text(self) -> str:
        self.debug.log(f"Извлечение текста из: {self.context.input_path}", level='INFO')
        try:
            text = self.file_utils.extract_text(self.context.input_path)
            if not text:
                raise TextExtractionError("Текст не найден в файле")
            self.debug.log(f"Извлечено {len(text):,} символов", level='INFO')
            self.context.stats['raw_chars'] = len(text)
            return text
        except Exception as e:
            raise TextExtractionError(f"Ошибка извлечения текста: {e}") from e

    @debug_trace
    def _clean_text(self, text: str) -> Tuple[str, List[str]]:
        self.debug.log("Очистка текста...", level='INFO')
        cleaned, paragraphs = self.cleaner.clean(text)
        self.context.stats['cleaned_chars'] = len(cleaned)
        self.context.stats['paragraphs'] = len(paragraphs)
        return cleaned, paragraphs

    @debug_trace
    def _split_into_chapters(self, text: str) -> List[dict]:
        self.debug.log("Разбиение на главы...", level='INFO')
        chapters_info = self.text_utils.split_into_chapters(text)
        chapters = []
        for i, (title, content) in enumerate(chapters_info):
            chapters.append({'title': title, 'content': content, 'index': i})
        self.context.stats['chapters'] = len(chapters)
        return chapters

    @debug_trace
    def _apply_accents(self, text: str) -> str:
        self.debug.log("Расстановка ударений...", level='INFO')
        try:
            accented = self.accent_engine.apply(text)
            self.context.stats['accents_applied'] = accented.count('+')
            return accented
        except Exception as e:
            raise AccentError(f"Ошибка расстановки ударений: {e}") from e

    @debug_trace
    def _convert_numbers(self, text: str) -> str:
        self.debug.log("Преобразование чисел...", level='INFO')
        return self.numbers_converter.convert(text)

    @debug_trace
    def _apply_manual_fixes(self, text: str) -> str:
        fixes = self.config.get_merged_fixes()
        if not fixes:
            return text
        self.debug.log(f"Применение {len(fixes)} ручных исправлений...", level='VERBOSE')
        for wrong, correct in fixes.items():
            text = text.replace(wrong, correct)
        return text

    @debug_trace
    def _expand_abbreviations(self, text: str) -> str:
        abbreviations = self.config.get_merged_abbreviations()
        if not abbreviations:
            return text
        self.debug.log(f"Расшифровка {len(abbreviations)} аббревиатур...", level='VERBOSE')
        for abbr, full in abbreviations.items():
            text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)
        return text

    def _strip_tags(self, text: str) -> str:
        """Удаляет все XML/SSML теги, оставляя только чистый текст."""
        return re.sub(r'<[^>]+>', '', text)

    def _find_original_chunk(self, clean_chunk: str, full_text: str) -> str:
        """
        Находит оригинальный фрагмент в полном тексте (с тегами),
        соответствующий чистому чанку.
        """
        # Упрощённый подход: ищем первое вхождение чистого текста в полном тексте
        # Это работает, потому что чистый текст — это тот же текст, но без тегов
        clean_chunk_escaped = re.escape(clean_chunk)
        pattern = re.compile(clean_chunk_escaped)
        
        match = pattern.search(full_text)
        if match:
            return match.group(0)
        
        # Если не нашли (например, из-за пробелов), возвращаем чистый чанк
        return clean_chunk

    @debug_trace
    def _build_ssml_for_chunk(self, chunk_text: str) -> str:
        """Строит SSML для одного чанка."""
        try:
            ssml = self.ssml_builder.build(chunk_text, [chunk_text])
            return ssml
        except Exception as e:
            raise SSMLBuildError(f"Ошибка построения SSML: {e}") from e

    @debug_trace
    def prepare_chunks(self, chunk_size: int = 400) -> List[SSMLChunk]:
        """
        Разбивает текст на чанки:
        1. Нарезает ЧИСТЫЙ текст (без тегов) по предложениям.
        2. Для каждого чанка находит соответствующий фрагмент в ОРИГИНАЛЬНОМ тексте (с тегами).
        3. Строит SSML из оригинального фрагмента.
        """
        if not self.final_processed_text:
            raise ValueError("Сначала вызови process()")

        # 1. Получаем чистый текст (без тегов) для нарезки
        clean_text = self._strip_tags(self.final_processed_text)

        # 2. Разбиваем чистый текст на предложения
        sentences = self.text_utils.split_sentences(clean_text)

        if not sentences:
            self.debug.log_warning("Не удалось разбить текст на предложения, создаю один чанк")
            sentences = [clean_text]

        self.debug.log(f"Текст разбит на {len(sentences)} предложений", level='INFO')

        # 3. Группируем предложения в чанки (по чистому тексту)
        clean_chunks = []
        current_batch = []
        current_len = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue

            if current_len + len(sent) > chunk_size and current_batch:
                clean_chunks.append(" ".join(current_batch))
                current_batch = []
                current_len = 0

            current_batch.append(sent)
            current_len += len(sent)

        if current_batch:
            clean_chunks.append(" ".join(current_batch))

        self.debug.log(f"Предложения сгруппированы в {len(clean_chunks)} чанков", level='INFO')

        # 4. Для каждого чистого чанка находим оригинальный текст (с тегами) и строим SSML
        ssml_chunks = []
        full_text = self.final_processed_text
        
        for i, clean_chunk in enumerate(clean_chunks):
            # Находим оригинальный фрагмент
            original_chunk = self._find_original_chunk(clean_chunk, full_text)
            
            # Строим SSML
            ssml_content = self._build_ssml_for_chunk(original_chunk)
            
            # Сохраняем для отладки
            chunk_path = Path("logs") / f"debug_chunk_{i:04d}.txt"
            with open(chunk_path, 'w', encoding='utf-8') as f:
                f.write(ssml_content)
            
            chunk = SSMLChunk(content=ssml_content, index=i)
            ssml_chunks.append(chunk)
            self.debug.log(f"Чанк {i} сохранён: {chunk_path}", level='VERBOSE')

        # Обновляем контекст
        self.context.ssml_chunks = [
            {'index': c.index, 'content': c.content} for c in ssml_chunks
        ]

        self.debug.log(f"✅ Создано {len(ssml_chunks)} валидных чанков с SSML-разметкой", level='INFO')
        return ssml_chunks