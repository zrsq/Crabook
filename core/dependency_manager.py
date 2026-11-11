#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Менеджер зависимостей - единая точка импорта и проверки всех внешних библиотек
"""

import sys
import subprocess
import importlib
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass

from core.exceptions import DependencyError
from core.debug_core import get_debugger, debug_trace


@dataclass
class DependencyInfo:
    """Информация о зависимости"""

    module_name: str
    package_name: str
    import_path: str
    required: bool = True
    min_version: Optional[str] = None
    loaded: bool = False
    module: Any = None
    error: Optional[str] = None


class DependencyManager:
    """
    Централизованный менеджер зависимостей.
    Загружает и проверяет все необходимые библиотеки ОДИН раз.
    """

    # Конфигурация всех зависимостей
    DEPENDENCIES = {
        # Основные (обязательные)
        "torch": DependencyInfo("torch", "torch", "torch", required=True),
        "numpy": DependencyInfo("numpy", "numpy", "numpy", required=True),
        "chardet": DependencyInfo("chardet", "chardet", "chardet", required=False),
        "ruaccent": DependencyInfo("ruaccent", "ruaccent", "ruaccent", required=True),
        # Для аудиообработки
        "scipy.signal": DependencyInfo(
            "scipy.signal", "scipy", "scipy.signal", required=False
        ),
        "scipy.io.wavfile": DependencyInfo(
            "scipy.io.wavfile", "scipy", "scipy.io.wavfile", required=False
        ),
        "noisereduce": DependencyInfo(
            "noisereduce", "noisereduce", "noisereduce", required=False
        ),
        "pyloudnorm": DependencyInfo(
            "pyloudnorm", "pyloudnorm", "pyloudnorm", required=False
        ),
        # Для синтаксического анализа
        "natasha": DependencyInfo("natasha", "natasha", "natasha", required=False),
        "spacy": DependencyInfo("spacy", "spacy", "spacy", required=False),
        # Для форматов файлов
        "docx": DependencyInfo("docx", "python-docx", "docx", required=False),
        "ebooklib": DependencyInfo("ebooklib", "ebooklib", "ebooklib", required=False),
        "bs4": DependencyInfo("bs4", "beautifulsoup4", "bs4", required=False),
        "pdfplumber": DependencyInfo(
            "pdfplumber", "pdfplumber", "pdfplumber", required=False
        ),
        "fitz": DependencyInfo("fitz", "PyMuPDF", "fitz", required=False),
        # Прочее
        "num2words": DependencyInfo(
            "num2words", "num2words", "num2words", required=False
        ),
    }

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.debug = get_debugger()
        self.deps: Dict[str, DependencyInfo] = {}
        self._load_all()

    @debug_trace
    def _install_package(self, package_name: str) -> bool:
        """Устанавливает пакет через pip"""
        try:
            self.debug.log(f"📦 Установка пакета: {package_name}", level="INFO")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", package_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.debug.log(f"✅ Пакет установлен: {package_name}", level="VERBOSE")
            return True
        except Exception as e:
            self.debug.log_error(f"Ошибка установки {package_name}", e)
            return False

    @debug_trace
    def _safe_import(self, info: DependencyInfo) -> Tuple[bool, Any, Optional[str]]:
        """Безопасный импорт модуля с автоматической установкой"""
        try:
            module = importlib.import_module(info.import_path)
            self.debug.log(f"✅ Импортирован: {info.module_name}", level="VERBOSE")
            return True, module, None
        except ImportError as e:
            if info.package_name:
                self.debug.log(
                    f"⚠️ {info.module_name} не найден, установка...", level="INFO"
                )
                if self._install_package(info.package_name):
                    try:
                        module = importlib.import_module(info.import_path)
                        return True, module, None
                    except ImportError as e2:
                        error_msg = f"Не удалось импортировать после установки: {e2}"
                        return False, None, error_msg
                else:
                    error_msg = f"Не удалось установить пакет {info.package_name}"
                    return False, None, error_msg
            else:
                error_msg = f"Модуль не найден: {e}"
                return False, None, error_msg

    @debug_trace
    def _load_all(self):
        """Загружает все зависимости"""
        self.debug.log_stage("Загрузка зависимостей", "start")

        for name, info in self.DEPENDENCIES.items():
            loaded, module, error = self._safe_import(info)

            info.loaded = loaded
            info.module = module
            info.error = error

            self.deps[name] = info

            if info.required and not loaded:
                self.debug.log_error(
                    f"❌ Обязательная зависимость не загружена: {name}"
                )
                raise DependencyError(
                    f"Не удалось загрузить обязательную зависимость: {name}",
                    {"error": error},
                )

        # Специальная обработка spaCy модели
        if self.is_available("spacy"):
            try:
                self.spacy.load("ru_core_news_sm")
                self.debug.log(
                    "✅ Модель spaCy ru_core_news_sm загружена", level="VERBOSE"
                )
            except:
                self.debug.log(
                    "📦 Загрузка модели spaCy ru_core_news_sm...", level="INFO"
                )
                subprocess.check_call(
                    [sys.executable, "-m", "spacy", "download", "ru_core_news_sm"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        # Специальная обработка ONNX для ruaccent
        try:
            import onnxruntime as ort

            if not hasattr(ort.InferenceSession, "_orig_run"):

                def patched_run(self, output_names, input_feed, run_options=None):
                    if "token_type_ids" not in input_feed:
                        for input_meta in self.get_inputs():
                            if input_meta.name == "token_type_ids":
                                if "input_ids" in input_feed:
                                    input_feed["token_type_ids"] = __import__(
                                        "numpy"
                                    ).zeros_like(input_feed["input_ids"])
                                break
                    return self._orig_run(output_names, input_feed, run_options)

                ort.InferenceSession._orig_run = ort.InferenceSession.run
                ort.InferenceSession.run = patched_run
                self.debug.log("✅ ONNX хак применён", level="VERBOSE")
        except Exception:
            pass

        self.debug.log_stage("Загрузка зависимостей", "end")
        self._print_summary()

    def _print_summary(self):
        """Выводит сводку о загруженных зависимостях"""
        self.debug.log("\n📊 ДОСТУПНЫЕ МОДУЛИ:", level="INFO")

        for name, info in self.deps.items():
            status = "✅" if info.loaded else "⚠️" if not info.required else "❌"
            self.debug.log(f"   {status} {name}", level="INFO")

    def is_available(self, name: str) -> bool:
        """Проверяет, доступен ли модуль"""
        return name in self.deps and self.deps[name].loaded

    def get(self, name: str) -> Any:
        """Возвращает загруженный модуль или None"""
        if name in self.deps and self.deps[name].loaded:
            return self.deps[name].module
        return None

    # Свойства для удобного доступа
    @property
    def torch(self):
        return self.get("torch")

    @property
    def numpy(self):
        return self.get("numpy")

    @property
    def chardet(self):
        return self.get("chardet")

    @property
    def ruaccent(self):
        return self.get("ruaccent")

    @property
    def scipy_signal(self):
        return self.get("scipy.signal")

    @property
    def wavfile(self):
        return self.get("scipy.io.wavfile")

    @property
    def noisereduce(self):
        return self.get("noisereduce")

    @property
    def pyloudnorm(self):
        return self.get("pyloudnorm")

    @property
    def natasha(self):
        return self.get("natasha")

    @property
    def spacy(self):
        return self.get("spacy")

    @property
    def docx(self):
        return self.get("docx")

    @property
    def ebooklib(self):
        return self.get("ebooklib")

    @property
    def bs4(self):
        return self.get("bs4")

    @property
    def pdfplumber(self):
        return self.get("pdfplumber")

    @property
    def fitz(self):
        return self.get("fitz")

    @property
    def num2words(self):
        return self.get("num2words")

    def get_available_formats(self) -> List[str]:
        """Возвращает список доступных форматов файлов"""
        formats = ["txt"]  # txt всегда доступен
        if self.is_available("docx"):
            formats.append("docx")
        if self.is_available("ebooklib") and self.is_available("bs4"):
            formats.append("epub")
        if self.is_available("bs4"):
            formats.append("fb2")
        if self.is_available("pdfplumber") or self.is_available("fitz"):
            formats.append("pdf")
        return formats


# Глобальный экземпляр
_DEPS_INSTANCE = None


def get_dependency_manager() -> DependencyManager:
    """Получить глобальный экземпляр менеджера зависимостей"""
    global _DEPS_INSTANCE
    if _DEPS_INSTANCE is None:
        _DEPS_INSTANCE = DependencyManager()
    return _DEPS_INSTANCE
