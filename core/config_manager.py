#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Менеджер конфигураций - единая загрузка всех JSON конфигов
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from core.debug_core import get_debugger, debug_trace


@dataclass
class PauseConfig:
    """Конфигурация пауз для SSML"""

    paragraph: int = 800
    dialog_change: int = 450
    exclamation: int = 350
    question: int = 350
    comma_long: int = 200
    enumeration: int = 120
    chapter: int = 1500

    @classmethod
    def from_dict(cls, data: dict) -> "PauseConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TTSConfig:
    """Конфигурация TTS"""

    default_voice: str = "xenia"
    default_sample_rate: int = 24000
    default_bitrate: str = "64k"
    default_chunk_size: int = 900
    default_workers: int = 4

    @classmethod
    def from_dict(cls, data: dict) -> "TTSConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AudioProcessingConfig:
    """Конфигурация обработки аудио"""

    enable_lowpass_filter: bool = False
    lowpass_cutoff_freq: int = 4000
    enable_deesser: bool = True
    deesser_threshold: float = -32.0      # Было -25.0
    deesser_center_freq: int = 5500       # Было 6000
    deesser_q: float = 0.6                # Было 1.0
    enable_spectral_nr: bool = True
    spectral_nr_amount: float = 0.12      # Было 0.5
    enable_room_tone: bool = False
    room_tone_level: float = -70.0
    enable_normalization: bool = True
    target_volume: float = -23.0          # Было -16.0

    @classmethod
    def from_dict(cls, data: dict) -> 'AudioProcessingConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProcessingConfig:
    """Конфигурация обработки"""

    default_genre: str = "fiction"
    split_chapters: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessingConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BookConfig:
    """Конфигурация конкретной книги"""

    path: Optional[Path] = None
    accents: Dict[str, str] = field(default_factory=dict)
    abbreviations: Dict[str, str] = field(default_factory=dict)
    manual_fixes: Dict[str, str] = field(default_factory=dict)
    custom_effects: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "BookConfig":
        return cls(
            accents=data.get("accents", {}),
            abbreviations=data.get("abbreviations", {}),
            manual_fixes=data.get("manual_fixes", {}),
            custom_effects=data.get("custom_effects", {}),
        )


class ConfigManager:
    """
    Централизованный менеджер конфигураций.
    Загружает все JSON конфиги ОДИН раз.
    """

    # Пресеты жанров
    GENRE_PRESETS = {
        "fiction": {
            "pause_config": {
                "paragraph": 900,
                "dialog_change": 500,
                "exclamation": 400,
                "question": 400,
                "comma_long": 250,
                "enumeration": 150,
                "chapter": 2000,
            },
            "rate": "medium",
            "pitch_variation": True,
        },
        "nonfiction": {
            "pause_config": {
                "paragraph": 700,
                "dialog_change": 400,
                "exclamation": 300,
                "question": 300,
                "comma_long": 150,
                "enumeration": 100,
                "chapter": 1200,
            },
            "rate": "medium",
            "pitch_variation": False,
        },
        "poetry": {
            "pause_config": {
                "paragraph": 600,
                "dialog_change": 400,
                "exclamation": 500,
                "question": 500,
                "comma_long": 300,
                "enumeration": 200,
                "chapter": 1500,
            },
            "rate": "slow",
            "pitch_variation": True,
        },
        "drama": {
            "pause_config": {
                "paragraph": 800,
                "dialog_change": 600,
                "exclamation": 450,
                "question": 450,
                "comma_long": 250,
                "enumeration": 150,
                "chapter": 1800,
            },
            "rate": "medium",
            "pitch_variation": True,
        },
    }

    # Маппинг эффектов на SSML теги
    EFFECT_TO_SSML = {
        "slow": ('prosody rate="slow"', "prosody"),
        "fast": ('prosody rate="fast"', "prosody"),
        "soft": ('prosody volume="soft"', "prosody"),
        "loud": ('prosody volume="loud"', "prosody"),
        "high_pitch": ('prosody pitch="high"', "prosody"),
        "low_pitch": ('prosody pitch="low"', "prosody"),
        "fast_high": ('prosody rate="fast" pitch="high"', "prosody"),
        "slow_low": ('prosody rate="slow" pitch="low"', "prosody"),
        "soft_slow": ('prosody volume="soft" rate="slow"', "prosody"),
        "loud_fast": ('prosody volume="loud" rate="fast"', "prosody"),
        "joy": ('prosody pitch="high" rate="105%"', "prosody"),
        "sadness": ('prosody pitch="low" rate="90%"', "prosody"),
        "anger": ('prosody volume="loud" rate="110%"', "prosody"),
        "fear": ('prosody pitch="high" rate="115%" volume="soft"', "prosody"),
        "surprise": ('prosody pitch="high" rate="110%"', "prosody"),
        "disgust": ('prosody pitch="low" rate="95%"', "prosody"),
        "whisper": ('prosody volume="x-soft"', "prosody"),
        "thought": ('prosody volume="soft" pitch="medium"', "prosody"),
    }

    # Ramp эффекты
    RAMP_EFFECTS = {
        "crescendo": ('prosody volume="soft"', 'prosody volume="loud"', "prosody"),
        "diminuendo": ('prosody volume="loud"', 'prosody volume="soft"', "prosody"),
        "accelerando": ('prosody rate="slow"', 'prosody rate="fast"', "prosody"),
        "rallentando": ('prosody rate="fast"', 'prosody rate="slow"', "prosody"),
    }

    def __init__(
        self, config_dir: str = "config", book_specific_dir: str = "book_specific"
    ):
        self.debug = get_debugger()
        self.config_dir = Path(config_dir)
        self.book_specific_dir = Path(book_specific_dir)

        # Конфигурации
        self.settings: Dict[str, Any] = {}
        self.tts_config = TTSConfig()
        self.audio_config = AudioProcessingConfig()
        self.processing_config = ProcessingConfig()
        self.pause_config = PauseConfig()

        # Словари
        self.accent_overrides: Dict[str, str] = {}
        self.abbreviations: Dict[str, str] = {}
        self.manual_fixes: Dict[str, str] = {}
        self.keywords_effects: Dict[str, str] = {}
        self.emotions: Dict[str, Any] = {}
        self.say_as_patterns: Dict[str, Any] = {}
        self.syntax_patterns: Dict[str, Any] = {}

        # Конфиг книги
        self.book_config: Optional[BookConfig] = None

        self._load_all()


    def _validate_configs(self):
        """Валидирует значения конфигов на допустимые диапазоны"""
        warnings = []

        # Валидация TTS
        if self.tts_config.default_sample_rate not in [8000, 16000, 24000, 44100, 48000]:
            warnings.append(f"sample_rate={self.tts_config.default_sample_rate} (рекомендуется: 24000)")

        if self.tts_config.default_workers < 1 or self.tts_config.default_workers > 32:
            warnings.append(f"workers={self.tts_config.default_workers} (рекомендуется: 1-16)")

        if self.tts_config.default_chunk_size < 100 or self.tts_config.default_chunk_size > 5000:
            warnings.append(f"chunk_size={self.tts_config.default_chunk_size} (рекомендуется: 500-2000)")

        # Валидация аудио
        ap = self.audio_config
        if ap.enable_lowpass_filter and (ap.lowpass_cutoff_freq < 1000 or ap.lowpass_cutoff_freq > 20000):
            warnings.append(f"lowpass_cutoff={ap.lowpass_cutoff_freq} Hz (рекомендуется: 4000-16000)")

        if ap.enable_deesser:
            if ap.deesser_threshold < -60 or ap.deesser_threshold > 0:
                warnings.append(f"deesser_threshold={ap.deesser_threshold} dB (рекомендуется: -40..-20)")
            if ap.deesser_center_freq < 2000 or ap.deesser_center_freq > 12000:
                warnings.append(f"deesser_center_freq={ap.deesser_center_freq} Hz (рекомендуется: 4000-8000)")
            if ap.deesser_q < 0.1 or ap.deesser_q > 5.0:
                warnings.append(f"deesser_q={ap.deesser_q} (рекомендуется: 0.5-2.0)")

        if ap.enable_spectral_nr:
            if ap.spectral_nr_amount < 0.0 or ap.spectral_nr_amount > 1.0:
                warnings.append(f"spectral_nr_amount={ap.spectral_nr_amount} (должно быть: 0.0-1.0)")

        if ap.enable_room_tone:
            if ap.room_tone_level < -100 or ap.room_tone_level > -20:
                warnings.append(f"room_tone_level={ap.room_tone_level} dB (рекомендуется: -80..-40)")

        if ap.enable_normalization:
            if ap.target_volume < -40 or ap.target_volume > -10:
                warnings.append(f"target_volume={ap.target_volume} LUFS (рекомендуется: -23..-16)")

        # Выводим предупреждения
        if warnings:
            self.debug.log_warning("⚠️ Обнаружены неоптимальные настройки в конфиге:")
            for w in warnings:
                self.debug.log_warning(f"   {w}")


    @debug_trace
    def _load_json(self, filename: str, default: Any = None) -> Any:
        """Загружает JSON файл"""
        file_path = self.config_dir / filename
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.debug.log(f"✅ Загружен конфиг: {filename}", level="VERBOSE")
                    return data
            except Exception as e:
                self.debug.log_error(f"Ошибка загрузки {filename}", e)
                return default
        else:
            self.debug.log(f"⚠️ Файл не найден: {filename}", level="VERBOSE")
            return default

    @debug_trace
    def _load_all(self):
        """Загружает все конфигурации"""
        self.debug.log_stage("Загрузка конфигураций", "start")

        # Основные настройки
        self.settings = self._load_json("default_settings.json", {})

        # Парсим в типизированные конфиги
        if "tts" in self.settings:
            self.tts_config = TTSConfig.from_dict(self.settings["tts"])
        if "audio_processing" in self.settings:
            self.audio_config = AudioProcessingConfig.from_dict(
                self.settings["audio_processing"]
            )
        if "processing" in self.settings:
            self.processing_config = ProcessingConfig.from_dict(
                self.settings["processing"]
            )
        if "pause_config" in self.settings:
            self.pause_config = PauseConfig.from_dict(self.settings["pause_config"])

        # Словари
        accents_data = self._load_json("accent_overrides.json", {})
        self.accent_overrides = accents_data.get("accents", {})

        abbreviations_data = self._load_json("abbreviations.json", {})
        self.abbreviations = abbreviations_data.get("abbreviations", {})

        fixes_data = self._load_json("manual_fixes.json", {})
        self.manual_fixes = fixes_data.get("replacements", {})

        keywords_data = self._load_json("keywords_effects.json", {})
        for effect, words in keywords_data.get("keywords", {}).items():
            for word in words:
                self.keywords_effects[word.lower()] = effect

        emotions_data = self._load_json("emotions.json", {})
        self.emotions = emotions_data.get("emotions", {})
        for emotion, data in self.emotions.items():
            for word in data.get("keywords", []):
                self.keywords_effects[word.lower()] = emotion

        self.say_as_patterns = self._load_json("say_as_patterns.json", {})
        self.syntax_patterns = self._load_json("syntax_patterns.json", {})

        self.debug.log_stage("Загрузка конфигураций", "end")
        self._print_summary()
        self._validate_configs()

    def _print_summary(self):
        """Выводит сводку о загруженных конфигах"""
        self.debug.log("\n📊 ЗАГРУЖЕННЫЕ КОНФИГУРАЦИИ:", level="INFO")
        self.debug.log(f"   Ударений: {len(self.accent_overrides)}", level="INFO")
        self.debug.log(f"   Аббревиатур: {len(self.abbreviations)}", level="INFO")
        self.debug.log(f"   Исправлений: {len(self.manual_fixes)}", level="INFO")
        self.debug.log(f"   Ключевых слов: {len(self.keywords_effects)}", level="INFO")

    @debug_trace
    def load_book_config(
        self, book_name: str = None, config_path: Path = None
    ) -> Optional[BookConfig]:
        """Загружает конфиг для конкретной книги"""
        if config_path and config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.book_config = BookConfig.from_dict(data)
                self.book_config.path = config_path
                self.debug.log(f"✅ Загружен конфиг книги: {config_path}", level="INFO")
            except Exception as e:
                self.debug.log_error("Ошибка загрузки конфига книги", e)
                return None
        elif book_name:
            # Ищем по имени
            specific_path = self.book_specific_dir / f"{book_name}.json"
            if specific_path.exists():
                return self.load_book_config(config_path=specific_path)

            # Общий конфиг
            default_path = self.book_specific_dir / "book_config.json"
            if default_path.exists():
                return self.load_book_config(config_path=default_path)

        return None

    def get_merged_accent_overrides(self) -> Dict[str, str]:
        """Возвращает объединённые переопределения ударений (общие + книги)"""
        result = self.accent_overrides.copy()
        if self.book_config:
            result.update(self.book_config.accents)
        return result

    def get_merged_abbreviations(self) -> Dict[str, str]:
        """Возвращает объединённые аббревиатуры"""
        result = self.abbreviations.copy()
        if self.book_config:
            result.update(self.book_config.abbreviations)
        return result

    def get_merged_fixes(self) -> Dict[str, str]:
        """Возвращает объединённые исправления"""
        result = self.manual_fixes.copy()
        if self.book_config:
            result.update(self.book_config.manual_fixes)
        return result

    def get_merged_effects(self) -> Dict[str, str]:
        """Возвращает объединённые эффекты"""
        result = self.keywords_effects.copy()
        if self.book_config:
            result.update(self.book_config.custom_effects)
        return result

    def get_genre_preset(self, genre: str) -> Dict[str, Any]:
        """Возвращает пресет для жанра"""
        return self.GENRE_PRESETS.get(genre, self.GENRE_PRESETS["fiction"])

    def get_pause_config_for_genre(self, genre: str) -> PauseConfig:
        """Возвращает конфигурацию пауз с учётом жанра"""
        preset = self.get_genre_preset(genre)
        pause_data = preset.get("pause_config", {})

        # Начинаем с базовых значений
        result = PauseConfig()
        # Применяем значения из настроек
        for key in result.__dict__:
            if hasattr(self.pause_config, key):
                setattr(result, key, getattr(self.pause_config, key))
        # Применяем пресет жанра (переопределяет)
        for key, value in pause_data.items():
            if hasattr(result, key):
                setattr(result, key, value)

        return result


# Глобальный экземпляр
_CONFIG_INSTANCE = None


def get_config_manager(
    config_dir: str = "config", book_specific_dir: str = "book_specific"
) -> ConfigManager:
    """Получить глобальный экземпляр менеджера конфигураций"""
    global _CONFIG_INSTANCE
    if _CONFIG_INSTANCE is None:
        _CONFIG_INSTANCE = ConfigManager(config_dir, book_specific_dir)
    return _CONFIG_INSTANCE
