#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сервис валидации SSML (упрощённый, без ложных срабатываний)
"""

import re
from typing import Tuple, List
from collections import Counter
from lxml import etree

from core.debug_core import get_debugger, debug_trace, debug_timing
from core.context import ExecutionContext
from models.ssml_chunk import SSMLDocument


class SSMLValidator:
    """Валидатор SSML разметки — только реальные ошибки"""
    
    def __init__(self):
        self.debug = get_debugger()
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    @debug_trace
    @debug_timing
    def validate(self, ssml_text: str) -> Tuple[bool, List[str], List[str]]:
        """Проверяет SSML текст"""
        self.errors = []
        self.warnings = []
        
        # Только критическая проверка
        self._check_speak_tags(ssml_text)
        self._check_unclosed_prosody(ssml_text)
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            self.debug.log("✅ SSML валиден", level='INFO')
        
        return is_valid, self.errors, self.warnings
    
    def _check_speak_tags(self, content: str):
        """Проверяет наличие speak тегов"""
        if '<speak>' not in content:
            self.errors.append("❌ Отсутствует открывающий тег <speak>")
        if '</speak>' not in content:
            self.errors.append("❌ Отсутствует закрывающий тег </speak>")
    
    def _check_unclosed_prosody(self, content: str):
        """Проверяет только реально незакрытые теги prosody"""
        # Считаем открывающие и закрывающие
        prosody_open = len(re.findall(r'<prosody[^/>]*>', content))
        prosody_close = len(re.findall(r'</prosody>', content))
        
        if prosody_open != prosody_close:
            diff = prosody_open - prosody_close
            if diff > 0:
                self.warnings.append(f"⚠️ Несбалансированные теги prosody: открыто {prosody_open}, закрыто {prosody_close}")
            else:
                self.errors.append(f"❌ Лишние закрывающие теги prosody")


class SSMLFixer:
    """Автоматическое исправление ошибок SSML"""
    
    def __init__(self):
        self.debug = get_debugger()
    
    @staticmethod
    def _append_closers(content: str, closers: str) -> str:
        """FIX BUG-4: вставляет закрывающие теги ПЕРЕД </speak>, а не после."""
        if '</speak>' in content:
            return content.replace('</speak>', closers + '</speak>')
        return content + closers

    @debug_trace
    def fix(self, content: str) -> Tuple[str, List[str]]:
        """Исправляет ошибки в SSML"""
        fixes_applied = []

        # 1. Балансируем prosody (перед </speak>, иначе XML ломается ещё сильнее)
        prosody_open = len(re.findall(r'<prosody[^/>]*>', content))
        prosody_close = len(re.findall(r'</prosody>', content))
        if prosody_open > prosody_close:
            missing = prosody_open - prosody_close
            content = self._append_closers(content, '</prosody>' * missing)
            fixes_applied.append(f"Добавлено {missing} тегов </prosody>")

        # 2. Балансируем say-as
        say_as_open = len(re.findall(r'<say-as[^/>]*>', content))
        say_as_close = len(re.findall(r'</say-as>', content))
        if say_as_open > say_as_close:
            missing = say_as_open - say_as_close
            content = self._append_closers(content, '</say-as>' * missing)
            fixes_applied.append(f"Добавлено {missing} тегов </say-as>")
        
        # 3. Убираем пустые теги
        content = re.sub(r'<prosody[^>]*>\s*</prosody>', '', content)
        content = re.sub(r'<say-as[^>]*>\s*</say-as>', '', content)
        
        # 4. Добавляем speak если нужно
        if '<speak>' not in content:
            content = f'<speak>\n{content}\n</speak>'
            fixes_applied.append("Добавлена обёртка <speak>")

        # 5. FIX: настоящая XML-проверка через lxml; если после починки
        # XML всё ещё битый — восстанавливаем recover-парсером.
        try:
            etree.fromstring(content.encode('utf-8'), etree.XMLParser(recover=False))
        except etree.XMLSyntaxError as e:
            self.debug.log_warning(f"SSML всё ещё невалиден ({e}), recover-парсинг")
            recovered = etree.fromstring(
                content.encode('utf-8'), etree.XMLParser(recover=True)
            )
            if recovered is not None:
                content = etree.tostring(recovered, encoding='unicode')
                fixes_applied.append("Восстановлен XML recover-парсером")

        if fixes_applied:
            self.debug.log(f"Применено исправлений: {len(fixes_applied)}", level='INFO')
        
        return content, fixes_applied


class SSMLValidationService:
    """Сервис валидации SSML"""
    
    def __init__(self, context: ExecutionContext):
        self.context = context
        self.debug = context.debug or get_debugger()
        self.validator = SSMLValidator()
        self.fixer = SSMLFixer()
    
    @debug_trace
    @debug_timing
    def validate(self, auto_fix: bool = False) -> bool:
        """
        FIX BUG-10: проверяет и чинит КАЖДЫЙ чанк из context.ssml_chunks —
        именно они уходят в TTS. Раньше чинился только context.ssml_text,
        который никто не озвучивал, поэтому исправления ни на что не влияли.
        """
        chunks = self.context.ssml_chunks
        if not chunks:
            self.debug.log_warning("Нет SSML-чанков для валидации")
            return True

        all_errors: List[str] = []
        all_warnings: List[str] = []
        all_fixes: List[str] = []

        for chunk in chunks:
            content = chunk['content']

            if auto_fix:
                content, fixes = self.fixer.fix(content)
                if fixes:
                    chunk['content'] = content
                    all_fixes.extend(f"[чанк {chunk['index']}] {f}" for f in fixes)

            _, errors, warnings = self.validator.validate(content)
            all_errors.extend(f"[чанк {chunk['index']}] {e}" for e in errors)
            all_warnings.extend(f"[чанк {chunk['index']}] {w}" for w in warnings)

        if all_fixes:
            self.context.metadata['ssml_fixes'] = all_fixes

        # Синхронизируем агрегированный текст с исправленными чанками
        self.context.ssml_text = "\n".join(c['content'] for c in chunks)

        is_valid = len(all_errors) == 0
        self.context.validation_result = {
            'is_valid': is_valid,
            'errors': all_errors,
            'warnings': all_warnings,
        }

        self.context.metadata['ssml_document'] = SSMLDocument(
            content=self.context.ssml_text,
            validation_errors=all_errors,
            validation_warnings=all_warnings,
        )

        if all_errors:
            self.debug.log_warning(f"⚠️ Найдено {len(all_errors)} критических ошибок в SSML")
        elif all_warnings:
            self.debug.log(f"⚠️ Найдено {len(all_warnings)} предупреждений", level='VERBOSE')
        else:
            self.debug.log("✅ SSML полностью валиден", level='INFO')

        return is_valid