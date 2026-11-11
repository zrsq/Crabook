# 🎙️ Crabook

Создание профессиональных аудиокниг из текстовых файлов с использованием нейросетевого синтеза речи Silero TTS.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/Version-8.0-orange)]()

## 📖 О проекте

Crabook — это модульный инструмент для автоматического создания аудиокниг из электронных книг. Проект использует современные технологии синтеза речи, автоматической расстановки ударений и интеллектуальной SSML-разметки для создания естественно звучащих аудиокниг.

### ✨ Возможности

- 📚 **Поддержка форматов:** TXT, DOCX, FB2, EPUB, PDF
- 🎯 **Автоматическая расстановка ударений** (RUAccent)
- 🏷️ **SSML-разметка:** паузы, эмоции, интонация, скорость речи
- 🎤 **Несколько голосов:** xenia, eugene, aidar, baya, kseniya
- ⚡ **Параллельная генерация** чанков для ускорения
- 🎛️ **Профессиональная постобработка:**
  - De-esser (подавление шипящих)
  - Шумоподавление (Spectral NR)
  - Нормализация громкости (LUFS)
  - Low-pass фильтр
- 💾 **Поддержка форматов вывода:** AAC (M4A), MP3, WAV
- 🐛 **Встроенная система отладки** с подробными логами
- ⚙️ **Гибкая конфигурация** через JSON файлы

## 🚀 Быстрый старт

### Установка

```bash
# Клонируем репозиторий
git clone https://github.com/yourusername/audiobook-creator.git
cd audiobook-creator

# Устанавливаем зависимости
pip install -r requirements.txt

# Устанавливаем модель spaCy (для синтаксического анализа)
python -m spacy download ru_core_news_sm


project/
├── crabook.py                    # Новый оркестратор
├── core/
│   ├── __init__.py
│   ├── debug_core.py             # Отладчик
│   ├── exceptions.py             # Исключения
│   ├── dependency_manager.py     # Менеджер зависимостей
│   ├── config_manager.py         # Менеджер конфигураций
│   ├── context.py                # Контекст выполнения
│   └── pipeline.py               # Конвейер обработки
├── services/
│   ├── __init__.py
│   ├── text_preparation.py       # Сервис подготовки текста
│   ├── ssml_validation.py        # Сервис валидации SSML
│   └── audio_generation.py       # Сервис генерации аудио
├── engines/
│   ├── __init__.py
│   ├── text_cleaner.py           # Очистка текста
│   ├── accent_engine.py          # Расстановка ударений
│   ├── ssml_builder.py           # Построение SSML
│   ├── tts_engine.py             # Генерация речи
│   └── audio_processor.py        # Обработка аудио
├── models/
│   ├── __init__.py
│   ├── book.py                   # Модель книги
│   ├── ssml_chunk.py             # Модель SSML чанка
│   └── audio_chunk.py            # Модель аудио чанка
├── utils/
│   ├── __init__.py
│   ├── file_utils.py             # Работа с файлами
│   ├── text_utils.py             # Работа с текстом
│   └── audio_utils.py            # Работа с аудио
├── config/                       # Конфигурации (существующие)
├── book/                         # Книги (существующие)
├── audio/                        # Выходные аудио (существующие)
└── logs/                         # Логи (существующие)
