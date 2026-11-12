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

    @debug_trace
    def _build_ssml_for_chunk(self, chunk_text: str) -> str:
        """Строит SSML для одного чанка."""
        try:
            ssml = self.ssml_builder.build(chunk_text, [chunk_text])
            return ssml
        except Exception as e:
            raise SSMLBuildError(f"Ошибка построения SSML: {e}") from e

    @debug_trace
    def prepare_chunks(self, chunk_size: int = None) -> List[SSMLChunk]:
        """
        FIX BUG-2: разбивает текст С ТЕГАМИ на чанки по предложениям.

        Старая реализация нарезала чистый текст и пыталась найти его
        в тексте с тегами через re.search — совпадение было невозможно,
        если внутри чанка есть хоть один тег, и вся SSML-разметка
        (ударения, числа, эффекты) молча терялась.

        Теперь предложения получаются из split_sentences_tagged(),
        а размер чанка считается по длине ЧИСТОГО текста (без тегов).
        """
        if not self.final_processed_text:
            raise ValueError("Сначала вызови process()")

        # FIX BUG-8: размер чанка берём из CLI/конфига через контекст
        if chunk_size is None:
            chunk_size = self.context.get_effective_chunk_size()

        sentences = self.text_utils.split_sentences_tagged(self.final_processed_text)

        if not sentences:
            self.debug.log_warning("Не удалось разбить текст на предложения, создаю один чанк")
            sentences = [self.final_processed_text]

        self.debug.log(f"Текст разбит на {len(sentences)} предложений", level='INFO')

        # Группируем предложения в чанки по длине чистого текста
        text_chunks = []
        current_batch = []
        current_len = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue

            plain_len = len(self._strip_tags(sent))

            if current_len + plain_len > chunk_size and current_batch:
                text_chunks.append(" ".join(current_batch))
                current_batch = []
                current_len = 0

            current_batch.append(sent)
            current_len += plain_len

        if current_batch:
            text_chunks.append(" ".join(current_batch))

        self.debug.log(f"Предложения сгруппированы в {len(text_chunks)} чанков", level='INFO')

        # Строим SSML для каждого чанка (теги уже внутри — не теряются)
        ssml_chunks = []
        dump_debug = self.debug.should_log("DEBUG")
        if dump_debug:
            Path("logs").mkdir(exist_ok=True)

        for i, chunk_text in enumerate(text_chunks):
            ssml_content = self._build_ssml_for_chunk(chunk_text)

            # FIX: дамп чанков только в режиме DEBUG (раньше писался всегда —
            # тысячи файлов на книгу даже без --debug)
            if dump_debug:
                chunk_path = Path("logs") / f"debug_chunk_{i:04d}.txt"
                with open(chunk_path, 'w', encoding='utf-8') as f:
                    f.write(ssml_content)
                self.debug.log(f"Чанк {i} сохранён: {chunk_path}", level='DEBUG')

            chunk = SSMLChunk(content=ssml_content, index=i)
            ssml_chunks.append(chunk)

        # Обновляем контекст (word_count сохраняем, чтобы не пересчитывать)
        self.context.ssml_chunks = [
            {'index': c.index, 'content': c.content, 'word_count': c.word_count}
            for c in ssml_chunks
        ]
        # Сохраняем полный SSML для этапа валидации
        self.context.ssml_text = "\n".join(c.content for c in ssml_chunks)

        self.debug.log(f"✅ Создано {len(ssml_chunks)} валидных чанков с SSML-разметкой", level='INFO')
        return ssml_chunks
