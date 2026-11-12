# 🦀 Crabook

Генератор аудиокниг на русском языке: превращает книги (txt, fb2, epub, docx, pdf)
в озвученные аудиофайлы (m4a / mp3 / wav) с правильной расстановкой ударений
и постобработкой звука.

## Возможности

- 📖 **Входные форматы:** txt, fb2, epub, docx, pdf
- 🎯 **Ударения:** RUAccent (нейросеть + словари), ручные переопределения
- 🔢 **Числа и даты** произносятся прописью (num2words)
- 🎭 **SSML:** паузы, темп/высота для ключевых слов и эмоций (адаптируется под Silero)
- 🎙 **TTS:** Silero v5.4 (ru) — голоса `xenia`, `aidar`, `baya`, `kseniya`
- 🎚 **Постобработка:** de-esser, шумоподавление, нормализация громкости (LUFS), room tone
- 🧵 **Параллельная генерация**, разбиение на чанки и главы
- ⚙️ **Гибкие конфиги** (JSON) + отдельные настройки для каждой книги

## Требования

- Python **3.11+**
- **ffmpeg**
- ~2 ГБ свободного места (модели RUAccent и Silero скачиваются при первом запуске)

## Установка

```bash
# ffmpeg
sudo pacman -S ffmpeg          # Arch
# sudo apt install ffmpeg      # Debian/Ubuntu

# окружение (uv)
uv venv --python 3.11
source .venv/bin/activate

# PyTorch: CPU-версия (без дискретной GPU) — экономит ~2.5 ГБ
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt
```

Альтернатива через pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## Быстрый старт

```bash
mkdir -p book
cp /путь/к/книге.txt book/

python crabook.py -i book/книга.txt
# результат: audio/книга.m4a
```

Без `-i` Crabook ищет единственный файл в папке `book/`:

```bash
python crabook.py
```

## Основные параметры CLI

| Флаг | Описание |
|------|----------|
| `-i, --input` | Входной файл |
| `-o, --output` | Выходной файл |
| `-g, --genre` | Жанр: `fiction`, `nonfiction`, `poetry`, `drama` |
| `-v, --voice` | Голос: `xenia` (по умолч.), `aidar`, `baya`, `kseniya` |
| `-c, --chunk-size` | Размер чанка в символах (по умолч. 500) |
| `-w, --workers` | Число потоков генерации |
| `--format` | Формат: `aac` (по умолч.), `mp3`, `wav` |
| `--formats` | Несколько форматов сразу, напр. `--formats aac mp3` |
| `-b, --bitrate` | Битрейт, напр. `128k` |
| `--split-chapters` | Разбить на главы |
| `--skip-validation` | Пропустить валидацию SSML |
| `--book-config` | JSON с настройками для конкретной книги |
| `--debug` | Уровень лога: `ERROR`…`TRACE` |

Полный список: `python crabook.py --help`.

Примеры:

```bash
# драма в mp3
python crabook.py -i book/play.txt -g drama -v aidar --format mp3 -b 128k

# несколько форматов + 6 потоков
python crabook.py -i book/novel.txt --formats aac mp3 -w 6

# со своим конфигом книги
python crabook.py -i book/novel.txt --book-config book_specific/novel.json
```

## Конфигурация

При первом запуске в `config/` генерируются JSON-настройки:

- `default_settings.json` — голос, размер чанка, потоки, постобработка
- `accent_overrides.json` — переопределение ударений
- `abbreviations.json` — расшифровка сокращений
- `keywords_effects.json` — эмоции/эффекты для ключевых слов
- `manual_fixes.json` — ручные замены текста

Для отдельной книги положите `book_specific/имя_книги.json` — он применится
автоматически при совпадении имени файла.

## Структура проекта

```text
Crabook/
├── crabook.py        # точка входа: оркестратор + CLI
├── core/             # конфиги, контекст, конвейер, зависимости, отладка
├── services/         # подготовка текста, валидация SSML, генерация аудио
├── engines/          # RUAccent, Silero TTS, SSML-билдер, очистка, аудио
├── models/           # dataclass-модели (веса RUAccent — локально, не в git)
├── utils/            # работа с файлами, текстом, аудио
├── config/           # JSON-настройки
├── book_specific/    # пер-книжные конфиги
├── book/             # входные книги (не в git)
├── audio/            # результат (не в git)
└── tests/            # регрессионные тесты
```

## Тесты

```bash
uv pip install pytest
python -m pytest tests/ -v
```

## Примечания

- Модели RUAccent и Silero скачиваются при первом запуске — нужен интернет.
- Голос `eugene` доступен в более новых моделях Silero (v5.5+); в v5.4 его нет.
- Файлы книг, аудио, логи и веса моделей не хранятся в git (см. `.gitignore`).
