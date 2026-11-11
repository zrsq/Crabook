#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сервис валидации SSML (упрощённый, без ложных срабатываний)
"""

import re
from typing import Tuple, List
from collections import Counter

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
    
    @debug_trace
    def fix(self, content: str) -> Tuple[str, List[str]]:
        """Исправляет ошибки в SSML"""
        fixes_applied = []
        
        # 1. Балансируем теги prosody
        prosody_open = len(re.findall(r'<prosody[^/>]*>', content))
        prosody_close = len(re.findall(r'</prosody>', content))
        if prosody_open > prosody_close:
            content += '</prosody>' * (prosody_open - prosody_close)
            fixes_applied.append(f"Добавлено {prosody_open - prosody_close} тегов </prosody>")
        
        # 2. Балансируем say-as
        say_as_open = len(re.findall(r'<say-as[^/>]*>', content))
        say_as_close = len(re.findall(r'</say-as>', content))
        if say_as_open > say_as_close:
            content += '</say-as>' * (say_as_open - say_as_close)
            fixes_applied.append(f"Добавлено {say_as_open - say_as_close} тегов </say-as>")
        
        # 3. Убираем пустые теги
        content = re.sub(r'<prosody[^>]*>\s*</prosody>', '', content)
        content = re.sub(r'<say-as[^>]*>\s*</say-as>', '', content)
        
        # 4. Добавляем speak если нужно
        if '<speak>' not in content:
            content = f'<speak>\n{content}\n</speak>'
            fixes_applied.append("Добавлена обёртка <speak>")
        
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
        """Проверяет SSML"""
        if not self.context.ssml_text:
            return False
        
        ssml_text = self.context.ssml_text
        
        if auto_fix:
            ssml_text, fixes = self.fixer.fix(ssml_text)
            self.context.ssml_text = ssml_text
            if fixes:
                self.context.metadata['ssml_fixes'] = fixes
        
        is_valid, errors, warnings = self.validator.validate(ssml_text)
        
        self.context.validation_result = {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings
        }
        
        # Создаём SSML документ
        ssml_doc = SSMLDocument(
            content=ssml_text,
            validation_errors=errors,
            validation_warnings=warnings
        )
        self.context.metadata['ssml_document'] = ssml_doc
        
        # Выводим только если есть реальные ошибки
        if errors:
            self.debug.log_warning(f"⚠️ Найдено {len(errors)} критических ошибок в SSML")
        elif warnings:
            self.debug.log(f"⚠️ Найдено {len(warnings)} предупреждений", level='VERBOSE')
        else:
            self.debug.log("✅ SSML полностью валиден", level='INFO')
        
        return is_valid