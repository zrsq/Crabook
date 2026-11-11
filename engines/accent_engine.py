#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Движок расстановки ударений
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional

from core.debug_core import get_debugger, debug_trace


class AccentEngine:
    """Движок расстановки ударений через RUAccent"""

    def __init__(self, model: str = 'turbo3.1', overrides: Dict[str, str] = None):
        self.debug = get_debugger()
        self.model_name = model
        self.overrides = overrides or {}
        
        # Папка для моделей и кеша
        self.models_dir = Path("models") / "ruaccent"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Папка для кеша обработанных текстов
        self.cache_dir = Path("cache") / "accents"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.accentizer = None
        self._init_accentizer()

    @debug_trace
    def _init_accentizer(self):
        """Инициализирует акцентизатор"""
        self.debug.log(f"Загрузка модели RUAccent: {self.model_name}", level='INFO')
        
        from ruaccent import RUAccent
        
        self.accentizer = RUAccent()
        
        # Загружаем модель с оптимизациями
        self.accentizer.load(
            omograph_model_size=self.model_name,
            use_dictionary=True,
            tiny_mode=True,  # 🔥 Меньше памяти, быстрее загрузка
            workdir=str(self.models_dir)
        )
        
        self.debug.log(f"✅ Модель загружена: {self.model_name}", level='INFO')

    def _get_text_hash(self, text: str) -> str:
        """Вычисляет хеш текста для кеширования"""
        # Учитываем также overrides, так как они влияют на результат
        content = text + json.dumps(self.overrides, sort_keys=True)
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _get_cached_result(self, text_hash: str) -> Optional[str]:
        """Пытается загрузить результат из кеша"""
        cache_file = self.cache_dir / f"{text_hash}.txt"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = f.read()
                self.debug.log(f"✅ Загружено из кеша: {cache_file.name}", level='VERBOSE')
                return cached
            except Exception:
                pass
        return None

    def _save_to_cache(self, text_hash: str, accented_text: str):
        """Сохраняет результат в кеш"""
        cache_file = self.cache_dir / f"{text_hash}.txt"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(accented_text)
            self.debug.log(f"💾 Сохранено в кеш: {cache_file.name}", level='VERBOSE')
        except Exception as e:
            self.debug.log_warning(f"Не удалось сохранить кеш: {e}")

    @debug_trace
    def apply(self, text: str) -> str:
        """
        Расставляет ударения в тексте.
        Использует кеширование для ускорения повторных запусков.
        """
        if not text:
            return text
        
        # Проверяем кеш
        text_hash = self._get_text_hash(text)
        cached = self._get_cached_result(text_hash)
        if cached is not None:
            return cached
        
        self.debug.log(f"Расстановка ударений ({len(text):,} символов)...", level='INFO')
        
        # Применяем ручные переопределения ДО обработки
        for word, accented in self.overrides.items():
            # Заменяем только целые слова
            text = self._replace_word(text, word, accented)
        
        # Основная обработка через RUAccent
        result = self.accentizer.process_all(text)
        
        # Сохраняем в кеш
        self._save_to_cache(text_hash, result)
        
        return result

    def _replace_word(self, text: str, word: str, replacement: str) -> str:
        """Заменяет слово с учётом границ"""
        import re
        pattern = r'\b' + re.escape(word) + r'\b'
        return re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    def apply_batch(self, texts: list) -> list:
        """Обрабатывает список текстов"""
        return [self.apply(t) for t in texts]