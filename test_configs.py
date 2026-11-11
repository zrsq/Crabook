#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тестирование применения всех конфигурационных параметров
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.context import ExecutionContext, ProcessingOptions


def print_section(title: str):
    """Печатает заголовок секции"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_config_loading():
    """Тест 1: Проверка загрузки конфигов"""
    print_section("ТЕСТ 1: ЗАГРУЗКА КОНФИГОВ")
    
    config = ConfigManager()
    
    print(f"\n📁 Конфигурации загружены из: {config.config_dir}")
    print(f"\n🔧 TTS Config:")
    print(f"   - voice: {config.tts_config.default_voice}")
    print(f"   - sample_rate: {config.tts_config.default_sample_rate}")
    print(f"   - bitrate: {config.tts_config.default_bitrate}")
    print(f"   - chunk_size: {config.tts_config.default_chunk_size}")
    print(f"   - workers: {config.tts_config.default_workers}")
    
    print(f"\n🎧 Audio Processing Config:")
    print(f"   - enable_lowpass: {config.audio_config.enable_lowpass_filter}")
    print(f"   - lowpass_cutoff: {config.audio_config.lowpass_cutoff_freq}")
    print(f"   - enable_deesser: {config.audio_config.enable_deesser}")
    print(f"   - deesser_threshold: {config.audio_config.deesser_threshold}")
    print(f"   - deesser_center_freq: {config.audio_config.deesser_center_freq}")
    print(f"   - deesser_q: {config.audio_config.deesser_q}")
    print(f"   - enable_spectral_nr: {config.audio_config.enable_spectral_nr}")
    print(f"   - spectral_nr_amount: {config.audio_config.spectral_nr_amount}")
    print(f"   - enable_room_tone: {config.audio_config.enable_room_tone}")
    print(f"   - room_tone_level: {config.audio_config.room_tone_level}")
    print(f"   - enable_normalization: {config.audio_config.enable_normalization}")
    print(f"   - target_volume: {config.audio_config.target_volume}")
    
    print(f"\n📝 Processing Config:")
    print(f"   - default_genre: {config.processing_config.default_genre}")
    print(f"   - split_chapters: {config.processing_config.split_chapters}")
    
    print(f"\n⏱️  Pause Config:")
    print(f"   - paragraph: {config.pause_config.paragraph} ms")
    print(f"   - dialog_change: {config.pause_config.dialog_change} ms")
    print(f"   - exclamation: {config.pause_config.exclamation} ms")
    print(f"   - question: {config.pause_config.question} ms")
    print(f"   - comma_long: {config.pause_config.comma_long} ms")
    print(f"   - enumeration: {config.pause_config.enumeration} ms")
    print(f"   - chapter: {config.pause_config.chapter} ms")
    
    print(f"\n📚 Словари:")
    print(f"   - accent_overrides: {len(config.accent_overrides)}")
    print(f"   - abbreviations: {len(config.abbreviations)}")
    print(f"   - manual_fixes: {len(config.manual_fixes)}")
    print(f"   - keywords_effects: {len(config.keywords_effects)}")
    
    return config


def test_effective_values(config: ConfigManager):
    """Тест 2: Проверка эффективных значений через контекст"""
    print_section("ТЕСТ 2: ЭФФЕКТИВНЫЕ ЗНАЧЕНИЯ (через ExecutionContext)")
    
    context = ExecutionContext(
        input_path=Path("book/test.txt"),
        options=ProcessingOptions(),
        config=config
    )
    
    print(f"\n🎯 Эффективные значения (Options=None, берутся из Config):")
    print(f"   - genre: {context.get_effective_genre()}")
    print(f"   - voice: {context.get_effective_voice()}")
    print(f"   - sample_rate: {context.get_effective_sample_rate()}")
    print(f"   - bitrate: {context.get_effective_bitrate()}")
    print(f"   - chunk_size: {context.get_effective_chunk_size()}")
    print(f"   - workers: {context.get_effective_workers()}")
    
    return context


def test_options_override(config: ConfigManager):
    """Тест 3: Проверка переопределения через командную строку"""
    print_section("ТЕСТ 3: ПЕРЕОПРЕДЕЛЕНИЕ ЧЕРЕЗ OPTIONS (эмуляция --voice eugene --genre drama)")
    
    # Эмулируем аргументы командной строки
    options = ProcessingOptions(
        voice="eugene",
        genre="drama",
        sample_rate=48000,
        bitrate="128k",
        chunk_size=1500,
        workers=8,
        no_deesser=True,
        target_volume=-20.0
    )
    
    context = ExecutionContext(
        input_path=Path("book/test.txt"),
        options=options,
        config=config
    )
    
    print(f"\n🎯 Эффективные значения (с переопределением):")
    print(f"   - genre: {context.get_effective_genre()} (Options: {options.genre}, Config: {config.processing_config.default_genre})")
    print(f"   - voice: {context.get_effective_voice()} (Options: {options.voice}, Config: {config.tts_config.default_voice})")
    print(f"   - sample_rate: {context.get_effective_sample_rate()} (Options: {options.sample_rate}, Config: {config.tts_config.default_sample_rate})")
    print(f"   - bitrate: {context.get_effective_bitrate()} (Options: {options.bitrate}, Config: {config.tts_config.default_bitrate})")
    print(f"   - chunk_size: {context.get_effective_chunk_size()} (Options: {options.chunk_size}, Config: {config.tts_config.default_chunk_size})")
    print(f"   - workers: {context.get_effective_workers()} (Options: {options.workers}, Config: {config.tts_config.default_workers})")
    
    return context


def test_audio_processing_options(config: ConfigManager):
    """Тест 4: Проверка опций аудиообработки"""
    print_section("ТЕСТ 4: ОПЦИИ АУДИООБРАБОТКИ")
    
    # Эмулируем флаги командной строки
    options = ProcessingOptions(
        lowpass=True,
        lowpass_cutoff=6000,
        no_deesser=False,
        deesser_threshold=-35.0,
        no_spectral_nr=False,
        spectral_nr_amount=0.2,
        room_tone=True,
        room_tone_level=-60.0,
        no_normalize=False,
        target_volume=-18.0
    )
    
    from engines.audio_processor import AudioProcessor
    processor = AudioProcessor(config=config.audio_config)
    
    # Применяем опции (эмуляция _apply_context_options)
    processor.options.enable_lowpass = options.lowpass or processor.options.enable_lowpass
    if options.lowpass_cutoff:
        processor.options.lowpass_cutoff = options.lowpass_cutoff
    if options.no_deesser:
        processor.options.enable_deesser = False
    if options.deesser_threshold:
        processor.options.deesser_threshold = options.deesser_threshold
    if options.no_spectral_nr:
        processor.options.enable_spectral_nr = False
    if options.spectral_nr_amount:
        processor.options.spectral_nr_amount = options.spectral_nr_amount
    if options.room_tone:
        processor.options.enable_room_tone = True
    if options.room_tone_level:
        processor.options.room_tone_level = options.room_tone_level
    if options.no_normalize:
        processor.options.enable_normalization = False
    if options.target_volume:
        processor.options.target_volume = options.target_volume
    
    print(f"\n🎛️ Итоговые настройки AudioProcessor:")
    print(f"   - enable_lowpass: {processor.options.enable_lowpass}")
    print(f"   - lowpass_cutoff: {processor.options.lowpass_cutoff}")
    print(f"   - enable_deesser: {processor.options.enable_deesser}")
    print(f"   - deesser_threshold: {processor.options.deesser_threshold}")
    print(f"   - enable_spectral_nr: {processor.options.enable_spectral_nr}")
    print(f"   - spectral_nr_amount: {processor.options.spectral_nr_amount}")
    print(f"   - enable_room_tone: {processor.options.enable_room_tone}")
    print(f"   - room_tone_level: {processor.options.room_tone_level}")
    print(f"   - enable_normalization: {processor.options.enable_normalization}")
    print(f"   - target_volume: {processor.options.target_volume}")
    
    return processor


def test_genre_pauses(config: ConfigManager):
    """Тест 5: Проверка пауз для разных жанров"""
    print_section("ТЕСТ 5: ПАУЗЫ ДЛЯ РАЗНЫХ ЖАНРОВ")
    
    genres = ['fiction', 'nonfiction', 'poetry', 'drama']
    
    print(f"\n📊 Сравнение пауз (в миллисекундах):")
    print(f"\n{'Жанр':<15} {'para':<8} {'dialog':<8} {'excl':<8} {'quest':<8} {'comma':<8} {'enum':<8} {'chapter':<8}")
    print("-" * 80)
    
    for genre in genres:
        pause_config = config.get_pause_config_for_genre(genre)
        print(f"{genre:<15} "
              f"{pause_config.paragraph:<8} "
              f"{pause_config.dialog_change:<8} "
              f"{pause_config.exclamation:<8} "
              f"{pause_config.question:<8} "
              f"{pause_config.comma_long:<8} "
              f"{pause_config.enumeration:<8} "
              f"{pause_config.chapter:<8}")


def test_merged_configs(config: ConfigManager):
    """Тест 6: Проверка слияния конфигов книги"""
    print_section("ТЕСТ 6: СЛИЯНИЕ КОНФИГОВ (общие + книги)")
    
    # Создаём временный конфиг книги
    temp_book_config = Path("book_specific/_test_book.json")
    temp_book_config.parent.mkdir(exist_ok=True)
    
    test_book_data = {
        "accents": {"тест": "т+ест"},
        "abbreviations": {"ТЕСТ": "Тестовое Сокращение"},
        "manual_fixes": {"олдскул": "олдскульный"},
        "custom_effects": {"дракон": "loud"}
    }
    
    with open(temp_book_config, 'w', encoding='utf-8') as f:
        json.dump(test_book_data, f, ensure_ascii=False, indent=2)
    
    # Загружаем конфиг книги
    config.load_book_config(config_path=temp_book_config)
    
    print(f"\n📖 Загружен конфиг книги: {temp_book_config}")
    print(f"\n🔄 Объединённые значения:")
    print(f"   - accent_overrides (общие + книга): {len(config.get_merged_accent_overrides())}")
    print(f"   - abbreviations (общие + книга): {len(config.get_merged_abbreviations())}")
    print(f"   - manual_fixes (общие + книга): {len(config.get_merged_fixes())}")
    print(f"   - keywords_effects (общие + книга): {len(config.get_merged_effects())}")
    
    # Проверяем конкретные значения
    merged_accents = config.get_merged_accent_overrides()
    print(f"\n   Пример accent: 'тест' -> '{merged_accents.get('тест', 'НЕ НАЙДЕНО')}'")
    
    merged_abbr = config.get_merged_abbreviations()
    print(f"   Пример abbreviation: 'ТЕСТ' -> '{merged_abbr.get('ТЕСТ', 'НЕ НАЙДЕНО')}'")
    
    # Удаляем временный файл
    temp_book_config.unlink()
    config.book_config = None
    
    print(f"\n🗑️ Временный конфиг удалён")


def test_config_generator():
    """Тест 7: Проверка генератора конфигов"""
    print_section("ТЕСТ 7: ГЕНЕРАТОР КОНФИГОВ")
    
    try:
        from core.config_generator import AutoConfigGenerator
        
        # Создаём временную директорию
        temp_dir = Path("/tmp/crabook_test_configs")
        temp_dir.mkdir(exist_ok=True)
        
        generator = AutoConfigGenerator(temp_dir)
        config = generator._generate_default_settings()
        
        print(f"\n📝 Сгенерированный default_settings.json:")
        print(f"   - voice: {config['tts']['default_voice']}")
        print(f"   - target_volume: {config['audio_processing']['target_volume']}")
        print(f"   - default_genre: {config['processing']['default_genre']}")
        print(f"   - deesser_threshold: {config['audio_processing']['deesser_threshold']}")
        print(f"   - spectral_nr_amount: {config['audio_processing']['spectral_nr_amount']}")
        
        # Очистка
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🗑️ Временная директория удалена")
        
    except ImportError as e:
        print(f"\n⚠️ Не удалось импортировать генератор: {e}")


def main():
    """Запуск всех тестов"""
    print("\n" + "="*70)
    print(f"  🧪 ТЕСТИРОВАНИЕ КОНФИГУРАЦИЙ CrABook")
    print(f"  Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Тест 1: Загрузка
    config = test_config_loading()
    
    # Тест 2: Эффективные значения
    test_effective_values(config)
    
    # Тест 3: Переопределение
    test_options_override(config)
    
    # Тест 4: Аудиообработка
    test_audio_processing_options(config)
    
    # Тест 5: Паузы по жанрам
    test_genre_pauses(config)
    
    # Тест 6: Слияние конфигов
    test_merged_configs(config)
    
    # Тест 7: Генератор
    test_config_generator()
    
    print_section("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print("\n")


if __name__ == "__main__":
    main()