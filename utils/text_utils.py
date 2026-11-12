#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Утилиты для работы с текстом
"""

import re
from typing import List, Tuple


class TextUtils:
    """Утилиты для обработки текста"""

    # FIX: маркеры защиты точек/дефисов. Раньше '<.>' и '<->' удалялись
    # любым strip_tags как XML-теги вместе с точками. Символы Private
    # Use Area не встречаются в книгах и не похожи на теги.
    DOT_MARK = '\ue000'
    DASH_MARK = '\ue001'

    def __init__(self):
        pass
    
    # ==================== НЕСТАТИЧЕСКИЕ МЕТОДЫ (вызываются через self) ====================
    
    def clean_text(self, text: str) -> Tuple[str, List[str]]:
        """
        Базовая очистка текста: удаление лишних пробелов, 
        нормализация переносов строк, разбиение на абзацы.
        """
        if not text:
            return "", []
        
        # Заменяем табуляции на пробелы
        text = text.replace('\t', ' ')
        
        # Нормализуем переносы строк
        text = re.sub(r'\r\n|\r', '\n', text)
        
        # Удаляем множественные пробелы
        text = re.sub(r' +', ' ', text)
        
        # Удаляем пробелы в начале и конце строк
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        
        # Убираем пустые строки в начале и конце
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        
        # Фильтруем пустые строки для абзацев
        paragraphs = [line for line in lines if line]
        
        # Объединяем обратно с нормализованными переносами
        cleaned_text = '\n'.join(paragraphs)
        
        return cleaned_text, paragraphs
    
    def split_into_chapters(self, text: str) -> List[Tuple[str, str]]:
        """
        Разбивает текст на главы по заголовкам.
        Возвращает список кортежей (название_главы, содержимое).
        """
        # Паттерны для поиска глав
        chapter_patterns = [
            # Глава 1, Глава I, Chapter 1
            r'(?:^|\n)\s*(?:Глава|ГЛАВА|Chapter|CHAPTER)\s+(\d+|[IVX]+)\s*[\.\:\-\—]?\s*([^\n]*)',
            # 1. Название, I. Название
            r'(?:^|\n)\s*(\d+|[IVX]+)\s*\.\s*([^\n]+)',
        ]
        
        chapters = []
        
        # Ищем все заголовки глав
        all_matches = []
        for pattern in chapter_patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                all_matches.append({
                    'start': match.start(),
                    'end': match.end(),
                    'number': match.group(1),
                    'title': match.group(2).strip() if len(match.groups()) > 1 else '',
                    'full': match.group(0).strip()
                })
        
        if not all_matches:
            # Если глав не найдено, возвращаем весь текст как одну главу
            return [("Текст", text)]
        
        # Сортируем по позиции
        all_matches.sort(key=lambda x: x['start'])
        
        # Формируем главы
        for i, match in enumerate(all_matches):
            start = match['start']
            
            if i < len(all_matches) - 1:
                end = all_matches[i + 1]['start']
            else:
                end = len(text)
            
            content = text[start:end].strip()
            
            # Формируем название главы
            if match['title']:
                title = f"Глава {match['number']}. {match['title']}"
            else:
                title = f"Глава {match['number']}"
            
            chapters.append((title, content))
        
        return chapters
    
    def count_words(self, text: str) -> int:
        """
        Подсчитывает количество слов в тексте.
        """
        # Удаляем SSML теги если есть
        clean_text = re.sub(r'<[^>]+>', ' ', text)
        # Разбиваем по пробелам
        words = re.findall(r'[А-Яа-яЁёA-Za-z]+(?:[-+][А-Яа-яЁёA-Za-z]+)*', clean_text)
        return len(words)
    
    def estimate_duration(self, text: str, words_per_minute: int = 150) -> float:
        """
        Оценивает длительность озвучивания текста в секундах.
        """
        word_count = self.count_words(text)
        return (word_count / words_per_minute) * 60
    
    def split_sentences(self, text: str) -> List[str]:
        """
        Разбивает текст на предложения с учетом сокращений и аббревиатур.
        """
        if not text:
            return []
            
        text = " " + text + "  "
        
        # Заменяем распространённые сокращения, чтобы точка не считалась концом предложения
        abbreviations = [
            r'т\.д\.',
            r'т\.п\.',
            r'т\.е\.',
            r'т\.к\.',
            r'и т\.д\.',
            r'и т\.п\.',
            r'и др\.',
            r'см\.',
            r'напр\.',
            r'рис\.',
            r'табл\.',
            r'стр\.',
            r'г\.',
            r'ул\.',
            r'пр\.',
            r'д\.',
            r'пер\.',
        ]
        
        for abbr in abbreviations:
            # Экранируем точки и заменяем на временный маркер
            pattern = abbr.replace('.', r'\.')
            replacement = abbr.replace('.', self.DOT_MARK)
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Заменяем "г-н", "г-жа"
        text = text.replace("г-н", f"г{self.DASH_MARK}н")
        text = text.replace("г-жа", f"г{self.DASH_MARK}жа")
        
        # Заменяем числа с точкой (1.5, 3.14)
        text = re.sub(r'(\d)\.(\d)', rf'\1{self.DOT_MARK}\2', text)
        
        # FIX BUG-3: убран re.IGNORECASE — с ним [А-ЯЁ] матчил и строчные,
        # из-за чего ЛЮБАЯ граница "слово. Слово" склеивалась в одно предложение.
        # Инициалы без пробела: "А.С." — обе буквы заглавные.
        text = re.sub(r'\b([А-ЯЁA-Z])\.([А-ЯЁA-Z])\.',
                      rf'\1{self.DOT_MARK}\2{self.DOT_MARK}', text)
        # Инициал с пробелом: "А. С. Пушкин". Требуем одиночную заглавную
        # (перед ней НЕ буква), чтобы не съесть границу "Конец. Начало".
        text = re.sub(
            r'(?<![А-Яа-яЁёA-Za-z])([А-ЯЁA-Z])\.\s+(?=[А-ЯЁA-Z](?:[.<]|[а-яёa-z]))',
            rf'\1{self.DOT_MARK} ', text
        )
        
        # Разбиваем по .!?...
        sentences = re.split(r'(?<=[.!?…])\s+', text)
        
        # Возвращаем сокращения на место и фильтруем пустые строки
        processed_sentences = []
        for s in sentences:
            s = s.strip()
            # Восстанавливаем точки
            s = s.replace(self.DOT_MARK, ".")
            s = s.replace(self.DASH_MARK, "-")
            
            # Убираем лишние пробелы
            s = re.sub(r'\s+', ' ', s)
            
            if s:
                processed_sentences.append(s)
                
        return processed_sentences
    
    def split_sentences_tagged(self, text: str) -> List[str]:
        """
        FIX BUG-2: разбивает текст С SSML-тегами на предложения,
        не разрывая теги и не теряя разметку. Каждый тег заменяется
        плейсхолдером без точек, применяется split_sentences к
        «скелету», затем теги возвращаются на место.
        """
        if not text:
            return []

        placeholders = []

        def _stash(m):
            placeholders.append(m.group(0))
            return f'\ue010{len(placeholders) - 1}\ue011'

        skeleton = re.sub(r'<[^>]+>', _stash, text)
        sentences = self.split_sentences(skeleton)

        restored = []
        for s in sentences:
            s = re.sub(r'\ue010(\d+)\ue011',
                       lambda m: placeholders[int(m.group(1))], s)
            if s.strip():
                restored.append(s.strip())
        return restored

    # ==================== СТАТИЧЕСКИЕ МЕТОДЫ (вызываются через TextUtils.method) ====================
    
    @staticmethod
    def split_by_tags(text: str) -> List[str]:
        """
        Разбивает текст на части, не разрывая XML/SSML теги.
        ВАЖНО: Это статический метод, вызывается как TextUtils.split_by_tags()
        """
        if not text:
            return []
        
        parts = []
        current = ""
        in_tag = False
        
        for char in text:
            if char == '<':
                if current and not in_tag:
                    parts.append(current)
                    current = ""
                in_tag = True
                current += char
            elif char == '>':
                current += char
                if in_tag:
                    parts.append(current)
                    current = ""
                in_tag = False
            else:
                current += char
        
        if current:
            parts.append(current)
        
        return parts
    
    @staticmethod
    def truncate_to_words(text: str, max_words: int) -> str:
        """
        Обрезает текст до указанного количества слов.
        """
        words = re.findall(r'\S+', text)
        if len(words) <= max_words:
            return text
        
        truncated = ' '.join(words[:max_words])
        return truncated + '...'
    
    @staticmethod
    def extract_quotes(text: str) -> List[str]:
        """
        Извлекает все цитаты из текста.
        """
        # Ищем текст в кавычках
        patterns = [
            r'"([^"]*)"',           # "цитата"
            r'«([^»]*)»',           # «цитата»
            r'„([^"]*)"',           # „цитата"
            r"'([^']*)'",           # 'цитата'
        ]
        
        quotes = []
        for pattern in patterns:
            quotes.extend(re.findall(pattern, text))
        
        return quotes
    
    @staticmethod
    def format_ssml_break(milliseconds: int) -> str:
        """
        Форматирует паузу для SSML.
        """
        return f'<break time="{milliseconds}ms"/>'
    
    @staticmethod
    def clean_whitespace(text: str) -> str:
        """
        Очищает лишние пробелы и переносы строк.
        """
        # Заменяем множественные пробелы на один
        text = re.sub(r'[ \t]+', ' ', text)
        # Заменяем множественные переносы строк
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Убираем пробелы в начале и конце строк
        text = re.sub(r'^[ \t]+|[ \t]+$', '', text, flags=re.MULTILINE)
        return text.strip()
    
    @staticmethod
    def has_russian(text: str) -> bool:
        """
        Проверяет, содержит ли текст русские буквы.
        """
        return bool(re.search(r'[А-Яа-яЁё]', text))
    
    @staticmethod
    def fix_typo_quotes(text: str) -> str:
        """
        Исправляет типографские кавычки.
        """
        # Заменяем английские кавычки на русские «ёлочки»
        text = re.sub(r'(^|\s)"([^"]*)', r'\1«\2', text)
        text = re.sub(r'([^"]*)"(\s|$|[.,!?;:])', r'\1»\2', text)
        
        return text