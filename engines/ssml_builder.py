#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Движок построения SSML разметки (версия с lxml)
"""

import re
import html
from typing import Dict, List, Optional
from lxml import etree

from core.debug_core import get_debugger, debug_trace
from core.config_manager import PauseConfig, ConfigManager
from core.dependency_manager import get_dependency_manager
from utils.text_utils import TextUtils


class SSMLBuilder:
    """Движок построения SSML разметки с использованием lxml для чистого XML."""

    UNSUPPORTED_PROSPY_ATTRS = ['volume', 'contour', 'range', 'duration']

    def __init__(
        self, pause_config: PauseConfig = None, config_manager: ConfigManager = None
    ):
        self.debug = get_debugger()
        self.deps = get_dependency_manager()
        self.text_utils = TextUtils()

        self.pause_config = pause_config or PauseConfig()
        self.config_manager = config_manager

        self.effect_to_ssml = {}
        self.ramp_effects = {}

        if config_manager:
            self.effect_to_ssml = config_manager.EFFECT_TO_SSML
            self.ramp_effects = config_manager.RAMP_EFFECTS

        self.keywords_effects: Dict[str, str] = {}

        self.NSMAP = {None: "http://www.w3.org/2001/10/synthesis"}
        self.SPEAK = f"{{{self.NSMAP[None]}}}speak"
        self.BREAK = f"{{{self.NSMAP[None]}}}break"
        self.PROSODY = f"{{{self.NSMAP[None]}}}prosody"
        self.SAY_AS = f"{{{self.NSMAP[None]}}}say-as"
        self.EMPHASIS = f"{{{self.NSMAP[None]}}}emphasis"

        self.nlp = None
        self._init_syntax_analyzer()

    @debug_trace
    def _init_syntax_analyzer(self):
        if self.deps.is_available("natasha"):
            try:
                from natasha import Segmenter, MorphVocab, NewsEmbedding
                from natasha import NewsMorphTagger, NewsSyntaxParser

                self.segmenter = Segmenter()
                self.morph_vocab = MorphVocab()
                emb = NewsEmbedding()
                self.morph_tagger = NewsMorphTagger(emb)
                self.syntax_parser = NewsSyntaxParser(emb)
                self.nlp = "natasha"
                self.debug.log("✅ Natasha готов", level="INFO")
            except Exception as e:
                self.debug.log_warning(f"Ошибка Natasha: {e}")

    def set_keywords_effects(self, effects: Dict[str, str]):
        self.keywords_effects = effects

    @debug_trace
    def build(self, text: str, paragraphs: List[str] = None) -> str:
        self.debug.log("Построение SSML разметки (lxml)...", level="INFO")

        if paragraphs is None:
            paragraphs = text.split("\n")

        speak_elem = etree.Element(self.SPEAK, nsmap=self.NSMAP)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            self._process_paragraph(para, speak_elem)

            break_elem = etree.SubElement(speak_elem, self.BREAK)
            break_elem.set("time", f"{self.pause_config.paragraph}ms")

        ssml_bytes = etree.tostring(
            speak_elem,
            encoding='utf-8',
            xml_declaration=False,
            pretty_print=False
        )
        ssml_text = ssml_bytes.decode('utf-8')

        # Удаляем пустые теги prosody
        ssml_text = re.sub(r'<prosody\s*></prosody>', '', ssml_text)
        ssml_text = re.sub(r'<prosody\s+></prosody>', '', ssml_text)
        ssml_text = re.sub(r'<prosody\s*>\s*</prosody>', '', ssml_text)

        ssml_text = self._strip_namespaces(ssml_text)
        ssml_text = self._remove_unsupported_attrs(ssml_text)

        # Финальная проверка: не оставляем пустые теги
        ssml_text = re.sub(r'<prosody\s*></prosody>', '', ssml_text)

        self.debug.log("✅ SSML разметка построена", level="INFO")
        return ssml_text

    def _process_paragraph(self, paragraph: str, parent_elem):
        # FIX BUG-12: не создаём вложенные <prosody>, если абзац уже
        # содержит prosody-разметку (Silero ругается на вложенность).
        if re.match(r'^\s*[—\-]', paragraph) and '<prosody' not in paragraph:
            prosody = etree.SubElement(parent_elem, self.PROSODY)
            prosody.set("pitch", "medium")
            prosody.set("rate", "105%")
            self._add_text_with_effects(paragraph, prosody)
        else:
            self._add_text_with_effects(paragraph, parent_elem)

    def _add_text_with_effects(self, text: str, parent_elem):
        if self.keywords_effects:
            text = self._apply_keyword_effects_to_text(text)

        text = self._process_long_words_in_text(text)

        self._add_safe_fragment(text, parent_elem)

    def _add_safe_fragment(self, text: str, parent_elem):
        if not text:
            return

        text = html.unescape(text)

        if '<' in text and '>' in text:
            try:
                wrapped = f"<span>{text}</span>"
                parser = etree.XMLParser(recover=True, remove_blank_text=True)
                fragment = etree.fromstring(wrapped.encode('utf-8'), parser=parser)

                # FIX BUG-1: текст ДО первого дочернего тега терялся,
                # т.к. добавлялся только при отсутствии детей.
                if fragment.text:
                    self._append_text(parent_elem, fragment.text)

                # append() переносит и tail каждого ребёнка — отдельно
                # добавлять хвосты не нужно (это дублировало текст).
                for child in fragment.getchildren():
                    parent_elem.append(child)

                return
            except Exception:
                pass

        self._append_text(parent_elem, text)

    def _append_text(self, element, text):
        if len(element) > 0:
            last = element[-1]
            last.tail = (last.tail or "") + text
        else:
            element.text = (element.text or "") + text

    def _apply_keyword_effects_to_text(self, text: str) -> str:
        if not self.keywords_effects:
            return text

        for word, effect in self.keywords_effects.items():
            if effect in self.effect_to_ssml:
                tag_start, tag_name = self.effect_to_ssml[effect]
                pattern = rf'\b({re.escape(word)})\b'
                replacement = rf'<{tag_start}>\1</{tag_name}>'
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def _split_protected_blocks(text: str) -> List[str]:
        """
        FIX BUG-12: разбивает текст на блоки с учётом ВЛОЖЕННОСТИ
        <say-as>/<prosody>. Старый non-greedy regex матчил до первого
        закрывающего тега и ломал разметку на вложенных prosody.
        """
        parts = TextUtils.split_by_tags(text)
        blocks, buf, depth = [], [], 0
        for part in parts:
            is_open = bool(re.match(r'<(say-as|prosody)(?:\s[^>]*)?>$', part))
            is_close = bool(re.match(r'</(say-as|prosody)>$', part))
            if depth > 0:
                buf.append(part)
                if is_open:
                    depth += 1
                elif is_close:
                    depth -= 1
                    if depth == 0:
                        blocks.append("".join(buf))
                        buf = []
            elif is_open:
                depth = 1
                buf = [part]
            else:
                blocks.append(part)
        if buf:
            blocks.append("".join(buf))
        return blocks

    def _process_long_words_in_text(self, text: str) -> str:
        """Применяет prosody rate='90%' к длинным словам (>=9 букв)."""
        def repl(match):
            word = match.group(0)
            clean_word = word.replace('+', '')
            # Только если слово длинное и НЕ содержит пробелов
            if len(clean_word) >= 9 and ' ' not in clean_word:
                return f'<prosody rate="90%">{word}</prosody>'
            return word

        result_parts = []
        for block in self._split_protected_blocks(text):
            if block.startswith('<say-as') or block.startswith('<prosody'):
                result_parts.append(block)
            else:
                parts = TextUtils.split_by_tags(block)
                for i, part in enumerate(parts):
                    if not part.startswith('<'):
                        parts[i] = re.sub(r'\b[А-Яа-яёЁ]+\b', repl, part)
                result_parts.append("".join(parts))

        result = "".join(result_parts)
        # Удаляем пустые теги prosody
        result = re.sub(r'<prosody\s*></prosody>', '', result)
        result = re.sub(r'<prosody\s+></prosody>', '', result)
        return result

    def _strip_namespaces(self, ssml_text: str) -> str:
        ssml_text = re.sub(r'\s+xmlns(:\w+)?="[^"]*"', '', ssml_text)
        ssml_text = re.sub(r'</?ns0:', '</', ssml_text)
        ssml_text = re.sub(r'<ns0:', '<', ssml_text)
        return ssml_text

    def _remove_unsupported_attrs(self, ssml_text: str) -> str:
        for attr in self.UNSUPPORTED_PROSPY_ATTRS:
            ssml_text = re.sub(rf'\s+{attr}="[^"]*"', '', ssml_text)
            ssml_text = re.sub(rf"\s+{attr}='[^']*'", '', ssml_text)
        ssml_text = re.sub(r'<prosody\s*>', '<prosody>', ssml_text)
        ssml_text = re.sub(r'<prosody[^>]*>\s*</prosody>', '', ssml_text)
        return ssml_text


class NumbersToSayAs:
    """Преобразует числа и даты в SSML say-as теги"""

    def __init__(self):
        self.debug = get_debugger()
        self.deps = get_dependency_manager()

    @debug_trace
    def convert(self, text: str) -> str:
        text = self._convert_dates(text)
        text = self._convert_time(text)
        if self.deps.is_available("num2words"):
            text = self._convert_numbers(text)
        return text

    def _convert_dates(self, text: str) -> str:
        def date_repl(match):
            day, month, year = match.groups()
            return f'<say-as interpret-as="date" format="dmy">{day}.{month}.{year}</say-as>'

        parts = TextUtils.split_by_tags(text)
        for i, part in enumerate(parts):
            if not part.startswith("<"):
                parts[i] = re.sub(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", date_repl, part)
        return "".join(parts)

    def _convert_time(self, text: str) -> str:
        def time_repl(match):
            hour, minute = match.groups()
            return f'<say-as interpret-as="time">{hour}:{minute}</say-as>'

        parts = TextUtils.split_by_tags(text)
        for i, part in enumerate(parts):
            if not part.startswith("<"):
                parts[i] = re.sub(r"\b(\d{1,2}):(\d{2})\b", time_repl, part)
        return "".join(parts)

    def _convert_numbers(self, text: str) -> str:
        if not self.deps.is_available("num2words"):
            return text

        def number_repl(match):
            num_str = match.group(0).replace(" ", "")
            try:
                num = int(num_str)
                if num >= 1000:
                    words = self.deps.num2words.num2words(num, lang="ru")
                    return f'<say-as interpret-as="cardinal">{words}</say-as>'
            except:
                pass
            return match.group(0)

        parts = TextUtils.split_by_tags(text)
        for i, part in enumerate(parts):
            if not part.startswith("<"):
                # FIX BUG-13: старый паттерн захватывал хвостовой пробел
                # ("1984 ") и склеивал слова. Теперь: группы по 3 цифры
                # через пробел ИЛИ 4+ цифр подряд.
                parts[i] = re.sub(
                    r"\b\d{1,3}(?: \d{3})+\b|\b\d{4,}\b", number_repl, part
                )
        text = "".join(parts)

        # FIX BUG-12: сбалансированная защита вложенных тегов
        result_parts = []
        for block in SSMLBuilder._split_protected_blocks(text):
            if block.startswith('<say-as') or block.startswith('<prosody'):
                result_parts.append(block)
            else:
                result_parts.append(self._process_long_words_safe(block))
        return "".join(result_parts)

    def _process_long_words_safe(self, text: str) -> str:
        def repl(match):
            word = match.group(0)
            clean_word = word.replace('+', '')
            if len(clean_word) >= 9 and ' ' not in clean_word:
                return f'<prosody rate="90%">{word}</prosody>'
            return word

        parts = TextUtils.split_by_tags(text)
        for i, part in enumerate(parts):
            if not part.startswith('<'):
                parts[i] = re.sub(r'\b[А-Яа-яёЁ]+\b', repl, part)

        result = "".join(parts)
        result = re.sub(r'<prosody\s*></prosody>', '', result)
        return result