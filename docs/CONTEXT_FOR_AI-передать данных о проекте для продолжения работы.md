📋 Как эффективно передать проект в новый чат:
Вариант 1: Создать файл-дайджест

Создай один файл project_digest.txt, в который скопируй содержимое всех ключевых файлов в формате:
text

[file name]: crabook.py
[file content begin]
... код ...
[file content end]

[file name]: core/context.py
[file content begin]
... код ...
[file content end]

... и так далее ...

И просто вставь его в чат. Я прочитаю всё!
Вариант 2: Использовать скрипт для генерации дайджеста

Создай make_digest.py:
python

#!/usr/bin/env python3
import os
from pathlib import Path

files_to_include = [
    "crabook.py",
    "core/context.py",
    "core/config_manager.py",
    "core/pipeline.py",
    "services/text_preparation.py",
    "services/audio_generation.py",
    "engines/tts_engine.py",
    "engines/audio_processor.py",
    "engines/ssml_builder.py",
    "config/default_settings.json",
]

with open("project_digest.txt", "w") as out:
    for f in files_to_include:
        path = Path(f)
        if path.exists():
            out.write(f"[file name]: {f}\n")
            out.write("[file content begin]\n")
            out.write(path.read_text())
            out.write("\n[file content end]\n\n")

print("✅ project_digest.txt создан!")

Запусти и вставь содержимое project_digest.txt в чат.
Вариант 3: Использовать тот же чат

Просто продолжай в этом же чате! Я помню всю историю, все изменения, все файлы. Новые вопросы можно задавать здесь же.
