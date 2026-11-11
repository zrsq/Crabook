📦 Что подготовить для нового чата
1. Краткое описание проекта (в первом сообщении)
text

CrABook — создание аудиокниг из текста с TTS Silero.
- MVC архитектура
- SSML разметка, ударения (RUAccent), синтаксический анализ (Natasha)
- Постобработка аудио (de-esser, шумоподавление, нормализация LUFS)
- Параллельная генерация чанков

2. Структура проекта (вставь как код)
text

crabook/
├── crabook.py              # Оркестратор (Controller)
├── core/                   # Ядро
│   ├── debug_core.py       # Отладка
│   ├── dependency_manager.py
│   ├── config_manager.py
│   ├── context.py          # ExecutionContext, ProcessingOptions
│   ├── pipeline.py
│   └── exceptions.py
├── services/               # Бизнес-логика
│   ├── text_preparation.py
│   ├── ssml_validation.py
│   └── audio_generation.py
├── engines/                # Низкоуровневые движки
│   ├── text_cleaner.py
│   ├── accent_engine.py
│   ├── ssml_builder.py
│   ├── tts_engine.py       # Silero TTS
│   └── audio_processor.py  # De-esser, NR, Normalization
├── models/                 # Dataclass'ы
│   ├── book.py
│   ├── ssml_chunk.py
│   └── audio_chunk.py
├── utils/                  # Утилиты
│   ├── file_utils.py
│   ├── text_utils.py
│   └── audio_utils.py
├── config/                 # JSON конфиги
├── book/                   # Входные файлы
├── audio/                  # Выходные аудио
└── logs/                   # Логи

3. Ключевые точки входа (укажи, что куда смотреть)
Задача	Файл	Класс/Метод
Добавить новый фильтр аудио	engines/audio_processor.py	AudioProcessor.process()
Изменить SSML разметку	engines/ssml_builder.py	SSMLBuilder._process_paragraph()
Добавить новый формат вывода	utils/audio_utils.py	FFMPEG_PRESETS
Изменить параметры TTS	engines/tts_engine.py	TTSEngine.__init__()
Добавить аргумент командной строки	crabook.py + core/context.py	ProcessingOptions
4. Файлы, которые нужно показать

Если нужна помощь с конкретным модулем — приложи только этот файл в сообщении:
text

[file name]: engines/audio_processor.py
[file content begin]
... полное содержимое ...
[file content end]

5. Готовый шаблон для нового чата
text

Привет! Продолжаем работу над CrABook (создание аудиокниг).

📁 Структура проекта:
[вставь структуру из пункта 2]

🎯 Задача: [опиши что нужно сделать]

🔧 Ключевые файлы для этой задачи:
- [файл 1] — [что в нём]
- [файл 2] — [что в нём]

📎 Прилагаю содержимое файлов:
[вставь файлы через [file name]...[file content]]

Контекст: проект на Python 3.11, используется Silero TTS v5, RUAccent, Natasha.

💡 Совет

Сохрани этот ответ в docs/CONTEXT_FOR_AI.md — и при новом чате просто скопируешь его вместе с нужными файлами. Я сразу пойму архитектуру и смогу помочь!
