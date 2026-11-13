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
- 📝 **Построчный режим** (`--per-line`): каждая строка → отдельный файл с именем-транслитом
- 🎞 **Мульти-форматы** (`--formats`): один прогон → несколько форматов сразу
- ⚙️ **Гибкие конфиги** (JSON) + отдельные настройки для каждой книги

## Требования

- **ffmpeg** (системный пакет)
- **uv** — менеджер пакетов и Python (установится автоматически, если его нет)
- ~2 ГБ свободного места (модели RUAccent и Silero скачиваются при первом запуске)

Python 3.11 скачивается `uv` автоматически — устанавливать вручную не нужно.

## Установка

Один раз ставим системные зависимости:

```bash
# ffmpeg
sudo pacman -S --needed ffmpeg git   # Arch
# sudo apt install ffmpeg git        # Debian/Ubuntu

# uv (если ещё не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

Клонируем и устанавливаем проект:

```bash
git clone git@github.com:zrsq/Crabook.git
cd Crabook
uv sync
```

`uv sync` сам скачает Python 3.11 (если нет подходящего), создаст `.venv` и поставит все зависимости — включая PyTorch (CPU-версию через отдельный index).

Или одной командой через `setup.sh` (если он есть в репозитории):

```bash
./setup.sh
```

## Быстрый старт

```bash
mkdir -p book
cp /путь/к/книге.txt book/

uv run python crabook.py -i book/книга.txt
# результат: audio/книга.m4a
```

Без `-i` Crabook ищет единственный файл в папке `book/`:

```bash
uv run python crabook.py
```

> Все команды проекта запускайте через `uv run` — он автоматически использует проектное окружение.

## Основные параметры CLI

| Флаг | Описание |
|------|----------|
| `-i, --input` | Входной файл |
| `-o, --output` | Выходной файл (или каталог для `--per-line`) |
| `-g, --genre` | Жанр: `fiction`, `nonfiction`, `poetry`, `drama` |
| `-v, --voice` | Голос: `xenia` (по умолч.), `aidar`, `baya`, `kseniya` |
| `-c, --chunk-size` | Размер чанка в символах (по умолч. 500) |
| `-w, --workers` | Число потоков генерации |
| `--format` | Формат: `aac` (по умолч.), `mp3`, `wav` |
| `--formats` | Несколько форматов сразу, напр. `--formats aac mp3 wav` |
| `--no-convert` | Не конвертировать — оставить WAV |
| `-b, --bitrate` | Битрейт, напр. `128k` |
| `--split-chapters` | Разбить на главы |
| `--skip-validation` | Пропустить валидацию SSML |
| `--per-line` | Построчная генерация (каждая строка → отдельный файл) |
| `--book-config` | JSON с настройками для конкретной книги |
| `--debug` | Уровень лога: `ERROR`…`TRACE` |

Полный список: `uv run python crabook.py --help`.

## Примеры

Обычный режим:

```bash
# драма в mp3
uv run python crabook.py -i book/play.txt -g drama -v aidar --format mp3 -b 128k

# несколько форматов за один прогон + 6 потоков
uv run python crabook.py -i book/novel.txt --formats aac mp3 wav -w 6

# со своим конфигом книги
uv run python crabook.py -i book/novel.txt --book-config book_specific/novel.json

# только WAV, без перекодирования
uv run python crabook.py -i book/novel.txt --no-convert
```

## Построчный режим (`--per-line`)

Каждая непустая строка входного файла становится отдельным аудиофайлом.
Имя файла = транслит строки (кириллица → латиница, нижний регистр, пробелы → `_`).

```bash
# файл с фразами построчно
printf 'Привет мир\nЭто тестовая строка\nВ 1984 году всё изменилось\n' > book/lines.txt

uv run python crabook.py -i book/lines.txt --per-line -v kseniya
```

Результат в `audio/`:

```
privet_mir.m4a
eto_testovaja_stroka.m4a
v_1984_godu_vse_izmenilos.m4a
```

Построчный режим поддерживает все остальные опции:

```bash
# в mp3
uv run python crabook.py -i book/lines.txt --per-line --format mp3

# в двух форматах сразу
uv run python crabook.py -i book/lines.txt --per-line --formats aac mp3

# в свой каталог (-o = каталог в этом режиме)
uv run python crabook.py -i book/lines.txt --per-line -o audio/phrases
```

Длинные строки автоматически разбиваются на чанки и склеиваются в один файл.
Все обычные преобразования (ударения, числа, SSML, постобработка) применяются к каждой строке.

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
├── utils/            # работа с файлами, текстом, аудио, именование
├── config/           # JSON-настройки
├── book_specific/    # пер-книжные конфиги
├── book/             # входные книги (не в git)
├── audio/            # результат (не в git)
└── tests/            # регрессионные тесты
```

## Тесты

```bash
uv run python -m pytest tests/ -v
```

## Примечания

- Модели RUAccent и Silero скачиваются при первом запуске — нужен интернет.
- Голос `eugene` доступен в более новых моделях Silero (v5.5+); в v5.4 его нет.
- Транслит использует схему `ja/ju` (ГОСТ-подобная): `я → ja`, `ю → ju`, `ж → zh`.
- Файлы книг, аудио, логи и веса моделей не хранятся в git (см. `.gitignore`).
- Проект работает в режиме приложения (`tool.uv.package = false`), запуск через `uv run`.
