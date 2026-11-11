#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Движок генерации речи (TTS)
"""

import os
import re
import ssl
from pathlib import Path
from typing import Optional, List, Tuple

from core.debug_core import get_debugger, debug_trace
from core.dependency_manager import get_dependency_manager
from core.exceptions import TTSGenerationError


class TTSEngine:
    """Движок генерации речи через Silero TTS v5.4"""

    AVAILABLE_VOICES = ["xenia", "eugene", "aidar", "baya", "kseniya", "random"]

    # Согласовано с max_chunk_chars = 400 в text_preparation.py
    MAX_TEXT_LENGTH = 500
    
    UNSUPPORTED_PROSPY_ATTRS = ['volume', 'contour', 'range', 'duration']
    
    MODEL_URLS = [
        "https://models.silero.ai/models/tts/ru/v5_4_ru.pt",
        "https://github.com/snakers4/silero-models/raw/master/models/tts/ru/v5_4_ru.pt",
    ]

    LOCAL_MODEL_FILE = "v5_4_ru.pt"

    def __init__(
        self, voice: str = "xenia", sample_rate: int = 24000, device: str = "cpu"
    ):
        self.debug = get_debugger()
        self.deps = get_dependency_manager()
        self.voice = voice
        self.sample_rate = sample_rate
        self.device = device
        self.model = None
        self._init_model()

    @debug_trace
    def _init_model(self):
        if not self.deps.is_available("torch"):
            raise TTSGenerationError("PyTorch не установлен")

        self.debug.log("🎙️ Загрузка Silero TTS v5.4...", level="INFO")

        if self.device == "auto":
            self.device = "cuda" if self.deps.torch.cuda.is_available() else "cpu"

        self._load_model()

    def _load_model(self):
        if os.path.isfile(self.LOCAL_MODEL_FILE):
            try:
                self._load_from_file(self.LOCAL_MODEL_FILE)
                self.debug.log(f"✅ Модель загружена из {self.LOCAL_MODEL_FILE}", level="INFO")
                return
            except Exception as e:
                self.debug.log_warning(f"Ошибка загрузки локального файла: {e}")

        if self._try_load_from_hub():
            return

        if self._download_and_load():
            return

        raise TTSGenerationError(
            f"Не удалось загрузить модель TTS.\n"
            f"Скачайте вручную: wget {self.MODEL_URLS[0]}\n"
            f"И положите файл {self.LOCAL_MODEL_FILE} в корень проекта."
        )

    def _try_load_from_hub(self) -> bool:
        try:
            self.debug.log("Попытка загрузки из torch.hub...", level="VERBOSE")
            ssl._create_default_https_context = ssl._create_unverified_context

            model, _ = self.deps.torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language="ru",
                speaker="v5_4_ru",
                trust_repo=True,
                force_reload=False,
            )
            model.to(self.device)
            self.model = model
            self.debug.log(f"✅ Модель загружена из hub на {self.device}", level="INFO")
            return True

        except Exception as e:
            self.debug.log_warning(f"Загрузка из hub не удалась: {e}")
            return False

    def _download_and_load(self) -> bool:
        for url in self.MODEL_URLS:
            try:
                self.debug.log(f"📥 Скачивание модели с {url}...", level="INFO")
                self.deps.torch.hub.download_url_to_file(url, self.LOCAL_MODEL_FILE)
                self.debug.log(f"✅ Модель сохранена как {self.LOCAL_MODEL_FILE}", level="INFO")

                self._load_from_file(self.LOCAL_MODEL_FILE)
                self.debug.log(f"✅ Модель загружена на {self.device}", level="INFO")
                return True

            except Exception as e:
                self.debug.log_warning(f"Не удалось скачать с {url}: {e}")
                continue

        return False

    def _load_from_file(self, filepath: str):
        model = self.deps.torch.package.PackageImporter(filepath).load_pickle(
            "tts_models", "model"
        )
        model.to(self.device)
        self.model = model

    def _clean_ssml(self, text: str) -> str:
        import html
        import re

        # 1. Разекранируем (чтобы &lt; стал <)
        text = html.unescape(text)

        # 2. Если чанк все же пришел битым (например, "азывались</prosody>")
        # Мы удаляем все теги, у которых нет пары внутри этого чанка
        if text.count('<') != text.count('>'):
            # Если скобки не парные - вычищаем их вообще, оставляем голый текст
            text = re.sub(r'<[^>]+>', '', text)
            text = text.replace('<', '').replace('>', '')

        # 3. Гарантируем одну обертку <speak>
        text = text.replace('<speak>', '').replace('</speak>', '').strip()

        # 4. Удаляем мусорные куски типа 'rate="90%"', которые остались без тега
        text = re.sub(r'[a-z]+="[^"]*"', '', text)

        return f"<speak>{text}</speak>"

    @debug_trace
    def generate(self, ssml_text: str, output_path: Path) -> bool:
        if not self.model:
            raise TTSGenerationError("Модель не загружена")

        original_text = ssml_text
        ssml_text = self._clean_ssml(ssml_text)

        self.debug.log(f"Генерация аудио: {len(ssml_text)} символов", level="VERBOSE")
        self.debug.log_text_sample("SSML для TTS", ssml_text, 300)

        try:
            with self.deps.torch.no_grad():
                self.model.save_wav(
                    ssml_text=ssml_text,
                    speaker=self.voice,
                    sample_rate=self.sample_rate,
                    audio_path=str(output_path),
                )

            if output_path.exists() and output_path.stat().st_size > 5000:
                self.debug.log_audio_info(str(output_path))
                return True
            else:
                return False

        except Exception as e:
            error_msg = str(e)
            
            if "Empty <prosody> tag" in error_msg:
                self.debug.log_warning(f"⚠️ Обнаружен пустой prosody, пробую агрессивную очистку...")
                aggressive = re.sub(r'</?prosody[^>]*>', '', original_text)
                aggressive = re.sub(r'<[^>]+>', ' ', aggressive)
                aggressive = re.sub(r'\s+', ' ', aggressive).strip()
                aggressive = f"<speak>{aggressive}</speak>"
                
                try:
                    with self.deps.torch.no_grad():
                        self.model.save_wav(
                            ssml_text=aggressive,
                            speaker=self.voice,
                            sample_rate=self.sample_rate,
                            audio_path=str(output_path),
                        )
                    if output_path.exists() and output_path.stat().st_size > 5000:
                        self.debug.log("✅ Агрессивная очистка сработала", level="INFO")
                        return True
                except Exception as e2:
                    self.debug.log_error(f"❌ Агрессивная очистка не помогла: {e2}")
            
            elif "too long" in error_msg.lower():
                self.debug.log_warning(f"⚠️ Текст слишком длинный, пробую обрезать...")
                clean = re.sub(r'<[^>]+>', '', original_text)
                clean = re.sub(r'\s+', ' ', clean).strip()
                
                if len(clean) > 400:
                    truncated = clean[:400]
                    last_dot = truncated.rfind('.')
                    if last_dot > 200:
                        clean = truncated[:last_dot + 1]
                    else:
                        clean = truncated
                
                short_ssml = f"<speak>{clean}</speak>"
                
                try:
                    with self.deps.torch.no_grad():
                        self.model.save_wav(
                            ssml_text=short_ssml,
                            speaker=self.voice,
                            sample_rate=self.sample_rate,
                            audio_path=str(output_path),
                        )
                    if output_path.exists() and output_path.stat().st_size > 5000:
                        self.debug.log("✅ Обрезанный текст сгенерирован", level="INFO")
                        return True
                except Exception as e2:
                    self.debug.log_error(f"❌ Обрезанный текст тоже не сработал: {e2}")
            
            elif "empty <prosody>" in error_msg or "syntax error" in error_msg.lower():
                self.debug.log_warning(f"⚠️ Silero ругается на синтаксис SSML, удаляю ВСЕ теги...")
                plain_text = re.sub(r'<[^>]+>', ' ', original_text)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                
                if not plain_text:
                    plain_text = "..."
                    
                plain_ssml = f"<speak>{plain_text}</speak>"
                try:
                    with self.deps.torch.no_grad():
                        self.model.save_wav(
                            ssml_text=plain_ssml,
                            speaker=self.voice,
                            sample_rate=self.sample_rate,
                            audio_path=str(output_path),
                        )
                    if output_path.exists() and output_path.stat().st_size > 5000:
                        self.debug.log("✅ Сгенерировано через чистый текст (без SSML)", level="INFO")
                        return True
                except Exception as e2:
                    self.debug.log_error(f"❌ Даже чистый текст не сработал: {e2}")
            
            else:
                self.debug.log_warning(f"⚠️ Ошибка SSML: {e}, пробую упрощённый вариант...")
                
                simple = re.sub(r"<[^>]+>", " ", original_text)
                simple = re.sub(r"\s+", " ", simple).strip()
                
                if len(simple) > self.MAX_TEXT_LENGTH:
                    simple = simple[:self.MAX_TEXT_LENGTH]
                    last_space = simple.rfind(' ')
                    if last_space > 0:
                        simple = simple[:last_space]
                
                simple = f"<speak>{simple}</speak>"

                try:
                    with self.deps.torch.no_grad():
                        self.model.save_wav(
                            ssml_text=simple,
                            speaker=self.voice,
                            sample_rate=self.sample_rate,
                            audio_path=str(output_path),
                        )

                    if output_path.exists() and output_path.stat().st_size > 5000:
                        self.debug.log("✅ Упрощённый SSML сработал", level="INFO")
                        return True

                except Exception as e2:
                    self.debug.log_error(f"❌ Упрощённый SSML тоже не сработал: {e2}")

            raise TTSGenerationError(f"Ошибка генерации: {e}")

    @debug_trace
    def generate_chunks(
        self, chunks: List[Tuple[str, Path]], workers: int = 4
    ) -> List[Tuple[Path, bool, Optional[str]]]:
        results = []

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for ssml_text, output_path in chunks:
                future = executor.submit(self._generate_safe, ssml_text, output_path)
                futures[future] = output_path

            for future in as_completed(futures):
                output_path = futures[future]
                try:
                    success, error = future.result()
                    results.append((output_path, success, error))
                except Exception as e:
                    results.append((output_path, False, str(e)))

        return results

    def _generate_safe(
        self, ssml_text: str, output_path: Path
    ) -> Tuple[bool, Optional[str]]:
        try:
            success = self.generate(ssml_text, output_path)
            return success, None
        except Exception as e:
            return False, str(e)

    def list_voices(self) -> List[str]:
        return self.AVAILABLE_VOICES
