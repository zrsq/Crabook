#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Кастомные исключения для Audiobook Creator
"""

class AudiobookError(Exception):
    """Базовое исключение для всех ошибок проекта"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class DependencyError(AudiobookError):
    """Ошибка при отсутствии необходимой зависимости"""


class ConfigError(AudiobookError):
    """Ошибка при загрузке или валидации конфигурации"""


class TextExtractionError(AudiobookError):
    """Ошибка при извлечении текста из файла"""


class AccentError(AudiobookError):
    """Ошибка при расстановке ударений"""


class SSMLBuildError(AudiobookError):
    """Ошибка при построении SSML"""


class SSMLValidationError(AudiobookError):
    """Ошибка валидации SSML"""


class TTSGenerationError(AudiobookError):
    """Ошибка при генерации речи"""


class AudioProcessingError(AudiobookError):
    """Ошибка при обработке аудио"""


class ConversionError(AudiobookError):
    """Ошибка при конвертации аудио"""


class PipelineError(AudiobookError):
    """Ошибка в конвейере обработки"""
