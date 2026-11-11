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