#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Движок генерации речи (TTS)
"""

import os
import re
import threading
from pathlib import Path
from typing import Optional, List, Tuple

from core.debug_core import get_debugger, debug_trace
from core.dependency_manager import get_dependency_manager
from core.exceptions import TTSGenerationError


class TTSEngine:
    """Движок генерации речи через Silero TTS v5.4"""

    AVAILABLE_VOICES = ["xenia", "eugene", "aidar", "baya", "kseniya", "random"]

    # Лимит длины SSML для одного вызова save_wav (Silero ~1000 с тегами)
    MAX_TEXT_LENGTH = 900
    # Макс. длина ЧИСТОГО текста в части при дроблении длинного чанка
    FALLBACK_PART_CHARS = 400
    
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
        # FIX BUG-5: Silero/TorchScript модель НЕ потокобезопасна.
        # Все вызовы save_wav сериализуем блокировкой.
        self._lock = threading.Lock()
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
            # FIX SEC-1: убрано глобальное отключение проверки TLS.
            # При проблемах с прокси настройте SSL_CERT_FILE/certifi.

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
        """Приводит SSML к подмножеству, поддерживаемому Silero.

        Silero понимает только speak/break/prosody/p/s, причём rate/pitch
        принимают лишь ключевые слова (x-slow..x-fast / x-low..x-high),
        а не проценты. Теги say-as/emphasis и т.п. не поддерживаются.
        Поэтому: неподдерживаемые теги разворачиваем в текст, проценты
        переводим в ключевые слова, паузы break сохраняем.
        """
        import html
        import re

        text = html.unescape(text).strip()

        # 1. Разворачиваем неподдерживаемые теги, сохраняя содержимое.
        #    [^>]* корректно поглощает атрибуты с дефисом (interpret-as).
        text = re.sub(
            r'</?(say-as|emphasis|sub|phoneme|lang|voice|amazon:effect)[^>]*>',
            '', text)

        # 2. Убираем неподдерживаемые атрибуты prosody.
        text = re.sub(r'\s+(volume|contour|range|duration)="[^"]*"', '', text)

        # 3. Prosody без атрибутов разворачиваем (иначе "Empty <prosody> tag").
        text = re.sub(r'<prosody\s*>(.*?)</prosody>', r'\1', text, flags=re.DOTALL)

        # 4. rate/pitch -> ключевые слова Silero (проценты тоже).
        text = re.sub(r'rate="([^"]*)"',
                      lambda m: f'rate="{self._ssml_key(m.group(1), "rate")}"', text)
        text = re.sub(r'pitch="([^"]*)"',
                      lambda m: f'pitch="{self._ssml_key(m.group(1), "pitch")}"', text)

        # 5. Гарантируем одну обёртку <speak>.
        text = re.sub(r'^\s*<speak[^>]*>', '', text)
        text = re.sub(r'</speak>\s*$', '', text).strip()

        return f"<speak>{text}</speak>"

    @staticmethod
    def _ssml_key(value: str, kind: str) -> str:
        """Переводит значение rate/pitch (в т.ч. проценты) в ключевое слово Silero."""
        import re
        keys = (['x-slow', 'slow', 'medium', 'fast', 'x-fast'] if kind == 'rate'
                else ['x-low', 'low', 'medium', 'high', 'x-high'])
        v = value.strip().lower()
        if v in keys:
            return v
        m = re.match(r'^([+-]?\d+(?:\.\d+)?)\s*%$', v)
        if m:
            p = float(m.group(1))
            if p < 80:
                return keys[0]
            if p < 95:
                return keys[1]
            if p <= 105:
                return keys[2]
            if p <= 120:
                return keys[3]
            return keys[4]
        return 'medium'

    def _save_wav_locked(self, ssml_text: str, output_path: Path):
        """FIX BUG-5: единственный вход в model.save_wav — под блокировкой."""
        with self._lock:
            with self.deps.torch.no_grad():
                self.model.save_wav(
                    ssml_text=ssml_text,
                    speaker=self.voice,
                    sample_rate=self.sample_rate,
                    audio_path=str(output_path),
                )

    def _wav_ok(self, output_path: Path) -> bool:
        return output_path.exists() and output_path.stat().st_size > 5000

    def _generate_split(self, plain_text: str, output_path: Path) -> bool:
        """
        FIX BUG-6: длинный текст генерируется ЧАСТЯМИ и склеивается.
        Текст книги НИКОГДА не обрезается и не теряется.
        """
        from utils.text_utils import TextUtils
        from utils.audio_utils import AudioUtils

        sentences = TextUtils().split_sentences(plain_text) or [plain_text]
        parts, batch, length = [], [], 0
        for sent in sentences:
            if length + len(sent) > self.FALLBACK_PART_CHARS and batch:
                parts.append(" ".join(batch))
                batch, length = [], 0
            # Одно предложение длиннее лимита — режем по словам (без потери)
            while len(sent) > self.FALLBACK_PART_CHARS:
                cut = sent.rfind(' ', 0, self.FALLBACK_PART_CHARS)
                if cut <= 0:
                    cut = self.FALLBACK_PART_CHARS
                parts.append(sent[:cut])
                sent = sent[cut:].lstrip()
            if sent:
                batch.append(sent)
                length += len(sent)
        if batch:
            parts.append(" ".join(batch))

        self.debug.log(
            f"Длинный чанк разбит на {len(parts)} частей (без потери текста)",
            level="INFO",
        )

        part_files = []
        try:
            for i, part in enumerate(parts):
                part_path = output_path.with_suffix(f".part{i:03d}.wav")
                self._save_wav_locked(f"<speak>{part}</speak>", part_path)
                if not self._wav_ok(part_path):
                    raise TTSGenerationError(f"Часть {i} не сгенерирована")
                part_files.append(part_path)

            if len(part_files) == 1:
                part_files[0].replace(output_path)
                return True

            if not AudioUtils().concat_wav_files(part_files, output_path):
                raise TTSGenerationError("Не удалось склеить части WAV")
            return self._wav_ok(output_path)
        finally:
            for p in part_files:
                if p.exists() and p != output_path:
                    try:
                        p.unlink()
                    except OSError:
                        pass

    @debug_trace
    def generate(self, ssml_text: str, output_path: Path) -> bool:
        if not self.model:
            raise TTSGenerationError("Модель не загружена")

        original_text = ssml_text
        ssml_text = self._clean_ssml(ssml_text)

        self.debug.log(f"Генерация аудио: {len(ssml_text)} символов", level="VERBOSE")
        self.debug.log_text_sample("SSML для TTS", ssml_text, 300)

        try:
            self._save_wav_locked(ssml_text, output_path)
            if self._wav_ok(output_path):
                self.debug.log_audio_info(str(output_path))
                return True
            return False

        except Exception as e:
            error_msg = str(e)
            plain_text = re.sub(r'<[^>]+>', ' ', original_text)
            plain_text = re.sub(r'\s+', ' ', plain_text).strip()

            if "Empty <prosody> tag" in error_msg:
                self.debug.log_warning("⚠️ Пустой prosody, пробую агрессивную очистку...")
                aggressive = re.sub(r'</?prosody[^>]*>', '', original_text)
                aggressive = re.sub(r'<[^>]+>', ' ', aggressive)
                aggressive = re.sub(r'\s+', ' ', aggressive).strip()
                try:
                    self._save_wav_locked(f"<speak>{aggressive}</speak>", output_path)
                    if self._wav_ok(output_path):
                        self.debug.log("✅ Агрессивная очистка сработала", level="INFO")
                        return True
                except Exception as e2:
                    self.debug.log_error(f"❌ Агрессивная очистка не помогла: {e2}")
                return self._generate_split(aggressive or plain_text, output_path)

            elif "too long" in error_msg.lower():
                # FIX BUG-6: раньше clean[:400] ВЫБРАСЫВАЛ кусок книги.
                self.debug.log_warning("⚠️ Текст слишком длинный, дроблю на части...")
                return self._generate_split(plain_text, output_path)

            elif "empty <prosody>" in error_msg or "syntax error" in error_msg.lower():
                self.debug.log_warning("⚠️ Silero ругается на синтаксис SSML, удаляю ВСЕ теги...")
                plain_text = plain_text or "..."
                try:
                    self._save_wav_locked(f"<speak>{plain_text}</speak>", output_path)
                    if self._wav_ok(output_path):
                        self.debug.log("✅ Сгенерировано через чистый текст (без SSML)", level="INFO")
                        return True
                except Exception as e2:
                    self.debug.log_error(f"❌ Чистый текст не сработал: {e2}")
                return self._generate_split(plain_text, output_path)

            else:
                self.debug.log_warning(f"⚠️ Ошибка SSML: {e}, пробую упрощённый вариант...")
                try:
                    self._save_wav_locked(f"<speak>{plain_text}</speak>", output_path)
                    if self._wav_ok(output_path):
                        self.debug.log("✅ Упрощённый SSML сработал", level="INFO")
                        return True
                except Exception as e2:
                    self.debug.log_error(f"❌ Упрощённый SSML не сработал: {e2}")
                # FIX BUG-6: вместо обрезки до MAX_TEXT_LENGTH — дробление
                return self._generate_split(plain_text, output_path)

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
