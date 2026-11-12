#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Автоматический генератор конфигурационных файлов
Сканирует код проекта и создаёт JSON с комментариями
"""

import json
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional, get_type_hints
from dataclasses import fields, Field


class AutoConfigGenerator:
    """Автоматически генерирует конфиги из dataclass'ов проекта"""
    
    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir
        self.config_dir.mkdir(exist_ok=True)
    
    def generate_all(self) -> Dict[str, Path]:
        """Генерирует все конфигурационные файлы"""
        generated = {}
        
        # Основной конфиг
        default_config = self._generate_default_settings()
        generated["default_settings.json"] = self._save_config(
            "default_settings.json", default_config
        )
        
        # Конфиг ударений (пример)
        accent_config = self._generate_accent_overrides()
        generated["accent_overrides.json"] = self._save_config(
            "accent_overrides.json", accent_config
        )
        
        # Конфиг аббревиатур (пример)
        abbreviations_config = self._generate_abbreviations()
        generated["abbreviations.json"] = self._save_config(
            "abbreviations.json", abbreviations_config
        )
        
        # Конфиг ключевых слов (пример)
        keywords_config = self._generate_keywords_effects()
        generated["keywords_effects.json"] = self._save_config(
            "keywords_effects.json", keywords_config
        )
        
        # Конфиг эмоций (пример)
        emotions_config = self._generate_emotions()
        generated["emotions.json"] = self._save_config(
            "emotions.json", emotions_config
        )
        
        # Конфиг ручных исправлений (пример)
        fixes_config = self._generate_manual_fixes()
        generated["manual_fixes.json"] = self._save_config(
            "manual_fixes.json", fixes_config
        )
        
        # Конфиг книги (шаблон)
        book_config = self._generate_book_config_template()
        generated["_book_template.json"] = self._save_config(
            "_book_template.json", book_config
        )

        # Шаблон книги — в book_specific/
        book_config = self._generate_book_config_template()
        book_specific_dir = Path("book_specific")
        book_specific_dir.mkdir(exist_ok=True)
        generated["_book_template.json"] = self._save_config(
            book_specific_dir / "_book_template.json", book_config
        )
        
        return generated
    
    def _save_config(self, filename: str, config: Dict) -> Path:
        """Сохраняет конфиг в файл"""
        filepath = self.config_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return filepath
    
    def _generate_default_settings(self) -> Dict[str, Any]:
        """Генерирует основной конфиг из анализа кода"""
        
        # Импортируем здесь чтобы избежать циклических импортов
        try:
            from core.context import ProcessingOptions
            from core.config_manager import (
                TTSConfig, AudioProcessingConfig, ProcessingConfig, PauseConfig
            )
        except ImportError:
            # Fallback если не удалось импортировать
            return self._get_fallback_default_settings()
        
        config = {
            "_comment": "=" * 80,
            "_description": "Основной файл настроек CrABook. Автоматически сгенерирован.",
            "_version": "8.0",
            "_auto_generated": True,
            
            "tts": self._dataclass_to_dict(TTSConfig()),
            "audio_processing": self._dataclass_to_dict(AudioProcessingConfig()),
            "processing": self._dataclass_to_dict(ProcessingConfig()),
            "pause_config": self._dataclass_to_dict(PauseConfig()),
            
            "ssml": {
                "use_ssml": True,
                "enable_emotions": True,
                "enable_question_markup": True,
                "enable_exclamation_markup": True
            }
        }
        
        return config
    
    def _dataclass_to_dict(self, obj: Any) -> Dict[str, Any]:
        """Преобразует dataclass в словарь со значениями по умолчанию"""
        result = {}
        
        for field in fields(obj):
            value = getattr(obj, field.name)
            
            # Преобразуем в JSON-совместимый формат
            if hasattr(value, 'value'):  # Enum
                value = value.value
            elif isinstance(value, Path):
                value = str(value)
            
            result[field.name] = value
        
        return result
    
    def _generate_accent_overrides(self) -> Dict[str, Any]:
        """Генерирует шаблон переопределения ударений"""
        return {
            "_comment": "Переопределение ударений для слов, которые RUAccent ставит неправильно",
            "_format": "слово_без_ударения: слово_с_ударением",
            "_example": "звонит: звон+ит",
            "accents": {
                "звонит": "звон+ит",
                "торты": "т+орты",
                "красивее": "крас+ивее",
                "баловать": "балов+ать",
                "включит": "включ+ит",
                "ждала": "ждал+а",
                "занята": "занят+а",
                "начался": "началс+я",
                "поднялась": "поднял+ась",
                "приняла": "принял+а",
                "создала": "создал+а",
                "углубить": "углуб+ить",
                "ходатайство": "ход+атайство",
                "черпать": "ч+ерпать",
                "щавель": "щав+ель"
            }
        }
    
    def _generate_abbreviations(self) -> Dict[str, Any]:
        """Генерирует шаблон расшифровки аббревиатур"""
        return {
            "_comment": "Расшифровка аббревиатур и сокращений",
            "abbreviations": {
                "т.е.": "то есть",
                "т.к.": "так как",
                "т.п.": "тому подобное",
                "т.д.": "так далее",
                "руб.": "рублей",
                "коп.": "копеек",
                "г.": "год",
                "гг.": "годы",
                "в.": "век",
                "вв.": "века",
                "стр.": "страница",
                "рис.": "рисунок",
                "табл.": "таблица"
            }
        }
    
    def _generate_keywords_effects(self) -> Dict[str, Any]:
        """Генерирует шаблон эффектов для ключевых слов"""
        return {
            "_comment": "SSML эффекты для ключевых слов",
            "_available_effects": [
                "slow", "fast", "soft", "loud",
                "high_pitch", "low_pitch", "whisper", "thought",
                "joy", "sadness", "anger", "fear", "surprise", "disgust"
            ],
            "keywords": {
                "slow": ["медленно", "тяжело", "осторожно"],
                "fast": ["быстро", "стремительно", "мгновенно"],
                "soft": ["тихо", "шепотом", "нежно"],
                "loud": ["громко", "крикнул", "воскликнул"],
                "whisper": ["шепнул", "прошептал", "шепот"],
                "joy": ["радостно", "весело", "счастливо"],
                "sadness": ["грустно", "печально", "тоскливо"],
                "anger": ["гневно", "яростно", "злобно"],
                "fear": ["испуганно", "боязливо", "страх"],
                "surprise": ["удивлённо", "изумлённо", "поражённо"]
            }
        }
    
    def _generate_emotions(self) -> Dict[str, Any]:
        """Генерирует шаблон эмоциональной окраски"""
        return {
            "_comment": "Эмоциональная окраска текста",
            "emotions": {
                "joy": {
                    "pitch": "high",
                    "rate": "105%",
                    "volume": "medium",
                    "keywords": ["радость", "счастье", "восторг", "улыбка", "смех"]
                },
                "sadness": {
                    "pitch": "low",
                    "rate": "90%",
                    "volume": "soft",
                    "keywords": ["грусть", "печаль", "тоска", "слёзы", "горе"]
                },
                "anger": {
                    "pitch": "medium",
                    "rate": "110%",
                    "volume": "loud",
                    "keywords": ["гнев", "ярость", "злость", "ненависть", "бешенство"]
                },
                "fear": {
                    "pitch": "high",
                    "rate": "115%",
                    "volume": "soft",
                    "keywords": ["страх", "ужас", "испуг", "трепет", "паника"]
                },
                "surprise": {
                    "pitch": "high",
                    "rate": "110%",
                    "volume": "medium",
                    "keywords": ["удивление", "изумление", "неожиданность", "шок"]
                }
            }
        }
    
    def _generate_manual_fixes(self) -> Dict[str, Any]:
        """Генерирует шаблон ручных исправлений текста"""
        return {
            "_comment": "Ручные исправления текста (замены)",
            "_note": "Полезно для исправления опечаток или специфичных терминов",
            "replacements": {
                "неправильное слово": "правильное слово",
                "опечатка": "исправление"
            }
        }
    
    def _generate_book_config_template(self) -> Dict[str, Any]:
        """Генерирует шаблон конфига для конкретной книги"""
        return {
            "_comment": "Шаблон конфигурации для конкретной книги",
            "_usage": "Скопируйте в book_specific/НАЗВАНИЕ_КНИГИ.json и измените под книгу",
            "_note": "Все поля опциональны",
            
            "accents": {
                "_description": "Переопределение ударений для этой книги",
                "слово": "сл+ово"
            },
            "abbreviations": {
                "_description": "Специфичные аббревиатуры книги",
                "АББР": "расшифровка"
            },
            "manual_fixes": {
                "_description": "Исправления специфичных для книги опечаток",
                "опечатка": "исправление"
            },
            "custom_effects": {
                "_description": "Особые эффекты для ключевых слов книги",
                "дракон": "loud",
                "магия": "high_pitch"
            }
        }
    
    def _get_fallback_default_settings(self) -> Dict[str, Any]:
        """Fallback конфиг если не удалось импортировать классы"""
        return {
            "_comment": "Fallback конфиг - сгенерирован без доступа к исходным классам",
            "tts": {
                "default_voice": "xenia",
                "default_chunk_size": 500,
                "default_workers": 4,
                "default_sample_rate": 24000,
                "default_bitrate": "64k"
            },
            "audio_processing": {
                "enable_lowpass_filter": False,
                "lowpass_cutoff_freq": 4000,
                "enable_deesser": True,
                "deesser_threshold": -32.0,
                "deesser_center_freq": 5500,
                "deesser_q": 0.6,
                "enable_spectral_nr": True,
                "spectral_nr_amount": 0.12,
                "enable_room_tone": False,
                "room_tone_level": -70.0,
                "enable_normalization": True,
                "target_volume": -23.0          # Исправлено на -23.0
            },
            "ssml": {
                "use_ssml": True,
                "enable_emotions": True,
                "enable_question_markup": True,
                "enable_exclamation_markup": True
            },
            "processing": {
                "default_genre": "fiction",
                "max_chunk_size": 2000,
                "min_chunk_size": 100,
                "max_workers": 8,
                "timeout_per_chunk": 180
            },
            "pause_config": {
                "paragraph": 800,
                "dialog_change": 450,
                "exclamation": 350,
                "question": 350,
                "comma_long": 200,
                "enumeration": 120,
                "chapter": 1500
            }
        }


def generate_configs(config_dir: str = "config", force: bool = False) -> Dict[str, Path]:
    """
    Генерирует конфигурационные файлы если они отсутствуют
    
    Args:
        config_dir: Директория для конфигов
        force: Принудительно перезаписать существующие
    
    Returns:
        Словарь {имя_файла: путь}
    """
    generator = AutoConfigGenerator(Path(config_dir))
    
    # Проверяем, нужно ли генерировать
    default_config_path = Path(config_dir) / "default_settings.json"
    
    if not default_config_path.exists() or force:
        print("📝 Генерация конфигурационных файлов...")
        generated = generator.generate_all()
        
        for name, path in generated.items():
            print(f"   ✅ {name}")
        
        print(f"\n📁 Конфиги сохранены в: {config_dir}/")
        return generated
    else:
        print(f"✅ Конфиги уже существуют в {config_dir}/")
        return {}


if __name__ == "__main__":
    # Запуск генерации
    import argparse
    
    parser = argparse.ArgumentParser(description="Генератор конфигов CrABook")
    parser.add_argument("--config-dir", default="config", help="Директория для конфигов")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие")
    
    args = parser.parse_args()
    generate_configs(args.config_dir, args.force)
