#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ядро системы отладки для Audiobook Creator
Обеспечивает единый интерфейс для отладки на всех этапах процесса
"""

import time
import traceback
import functools
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Any, Callable, Dict, Union

# ========== Уровни отладки ==========
DEBUG_LEVELS = {
    "ERROR": 0,  # Только ошибки
    "WARN": 1,  # Ошибки и предупреждения
    "INFO": 2,  # Основная информация
    "VERBOSE": 3,  # Детальная информация
    "DEBUG": 4,  # Всё подряд (для разработки)
    "TRACE": 5,  # Трассировка вызовов функций
}

# Цвета для терминала (Arch Linux / ANSI)
COLORS = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
    "RED": "\033[31m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "BLUE": "\033[34m",
    "MAGENTA": "\033[35m",
    "CYAN": "\033[36m",
    "WHITE": "\033[37m",
    "BG_RED": "\033[41m",
    "BG_GREEN": "\033[42m",
    "BG_YELLOW": "\033[43m",
    "BG_BLUE": "\033[44m",
}


class DebugCore:
    """Ядро отладчика - единый центр управления отладкой"""

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
        self.level = DEBUG_LEVELS["INFO"]
        self.enabled = False
        self.log_file = None
        self.log_dir = Path("logs")
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.call_stack = []
        self.timings = {}
        self.errors = []
        self.warnings = []
        self.stats = defaultdict(int)
        self.file_operations = []
        self.process_stages = []

        # Создаём директорию для логов
        self.log_dir.mkdir(exist_ok=True)

    def initialize(self, level: Union[int, str] = "INFO", log_to_file: bool = True):
        """Инициализация отладчика с указанным уровнем"""

        # Устанавливаем уровень отладки
        if isinstance(level, str):
            level = level.upper()
            self.level = DEBUG_LEVELS.get(level, DEBUG_LEVELS["INFO"])
        else:
            self.level = level

        self.enabled = self.level > DEBUG_LEVELS["ERROR"]

        # Настройка файла лога
        if log_to_file:
            log_filename = f"debug_{self.session_id}.log"
            self.log_file = self.log_dir / log_filename

            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write(f"{'=' * 80}\n")
                f.write(f"ОТЛАДОЧНЫЙ ЛОГ - Сессия: {self.session_id}\n")
                f.write(f"Уровень: {self.get_level_name()}\n")
                f.write(
                    f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(f"{'=' * 80}\n\n")

        self.log("=" * 60, level="INFO")
        self.log("🐛 ОТЛАДЧИК АКТИВИРОВАН", level="INFO", color="CYAN")
        self.log(f"   Уровень: {self.get_level_name()} ({self.level})", level="INFO")
        self.log(
            f"   Лог файл: {self.log_file if self.log_file else 'не создан'}",
            level="INFO",
        )
        self.log("=" * 60, level="INFO")

        return self

    def get_level_name(self) -> str:
        """Возвращает название текущего уровня отладки"""
        for name, value in DEBUG_LEVELS.items():
            if value == self.level:
                return name
        return "UNKNOWN"

    def should_log(self, level: Union[str, int]) -> bool:
        """Проверяет, нужно ли логировать на данном уровне"""
        if not self.enabled:
            return False

        if isinstance(level, str):
            level_value = DEBUG_LEVELS.get(level.upper(), DEBUG_LEVELS["INFO"])
        else:
            level_value = level

        return level_value <= self.level

    def log(
        self,
        message: str,
        level: str = "INFO",
        color: str = None,
        indent: int = 0,
        file_only: bool = False,
    ):
        """Универсальный метод логирования"""

        if not self.should_log(level):
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = f"[{timestamp}] [{level}]"
        indented_msg = " " * indent + message

        if color and not file_only:
            colored_prefix = (
                f"{COLORS.get(color, COLORS['RESET'])}{prefix}{COLORS['RESET']}"
            )
            print(f"{colored_prefix} {indented_msg}")
        elif not file_only:
            default_color = {
                "ERROR": "RED",
                "WARN": "YELLOW",
                "INFO": "GREEN",
                "VERBOSE": "BLUE",
                "DEBUG": "MAGENTA",
                "TRACE": "DIM",
            }.get(level.upper(), "WHITE")
            colored_prefix = (
                f"{COLORS.get(default_color, COLORS['RESET'])}{prefix}{COLORS['RESET']}"
            )
            print(f"{colored_prefix} {indented_msg}")

        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{prefix} {indented_msg}\n")

    def log_error(
        self, message: str, exception: Exception = None, show_traceback: bool = False
    ):
        """Логирование ошибки с дополнительной информацией"""
        self.errors.append(
            {
                "time": datetime.now(),
                "message": message,
                "exception": str(exception) if exception else None,
                "traceback": traceback.format_exc()
                if exception and show_traceback
                else None,
            }
        )

        self.log(f"❌ {message}", level="ERROR", color="RED")

        if exception:
            self.log(f"   Исключение: {exception}", level="ERROR", color="RED")

        if show_traceback and exception:
            tb_lines = traceback.format_exc().split("\n")
            for line in tb_lines[:10]:
                if line.strip():
                    self.log(f"   {line}", level="ERROR", color="DIM")

    def log_warning(self, message: str):
        """Логирование предупреждения"""
        self.warnings.append({"time": datetime.now(), "message": message})
        self.log(f"⚠️ {message}", level="WARN", color="YELLOW")

    def log_stage(self, stage_name: str, action: str = "start", details: Dict = None):
        """Логирование этапов процесса"""
        stage_info = {
            "name": stage_name,
            "action": action,
            "time": datetime.now(),
            "details": details or {},
        }

        if action == "start":
            self.process_stages.append(stage_info)
            self.log(f"▶️ {stage_name} - НАЧАЛО", level="INFO", color="CYAN")
            if details:
                for key, value in details.items():
                    self.log(f"   {key}: {value}", level="VERBOSE")
        elif action == "end":
            self.log(f"✅ {stage_name} - ЗАВЕРШЕН", level="INFO", color="GREEN")
        elif action == "error":
            self.log(f"❌ {stage_name} - ОШИБКА", level="ERROR", color="RED")

        return stage_info

    def trace_call(self, func_name: str, args: tuple, kwargs: dict):
        """Трассировка вызова функции (для уровня TRACE)"""
        if not self.should_log("TRACE"):
            return

        args_str = ", ".join([repr(a)[:50] for a in args[:3]])
        kwargs_str = ", ".join(
            [f"{k}={repr(v)[:30]}" for k, v in list(kwargs.items())[:3]]
        )

        call_str = f"{func_name}({args_str}"
        if kwargs_str:
            call_str += f", {kwargs_str}"
        call_str += ")"

        self.log(f"🔧 ВЫЗОВ: {call_str}", level="TRACE", color="DIM", indent=2)
        self.call_stack.append((func_name, time.time()))

    def trace_return(self, func_name: str, result: Any = None):
        """Трассировка возврата из функции"""
        if not self.should_log("TRACE"):
            return

        if self.call_stack and self.call_stack[-1][0] == func_name:
            self.call_stack.pop()

        if result is not None:
            result_str = repr(result)[:50]
            self.log(
                f"🔧 ВОЗВРАТ: {func_name} -> {result_str}",
                level="TRACE",
                color="DIM",
                indent=2,
            )

    def start_timing(self, name: str):
        """Начать измерение времени выполнения"""
        self.timings[name] = {"start": time.time(), "end": None, "duration": None}
        if self.should_log("DEBUG"):
            self.log(f"⏱️ ТАЙМИНГ СТАРТ: {name}", level="DEBUG", color="BLUE")

    def end_timing(self, name: str):
        """Закончить измерение времени выполнения"""
        if name in self.timings:
            self.timings[name]["end"] = time.time()
            self.timings[name]["duration"] = (
                self.timings[name]["end"] - self.timings[name]["start"]
            )
            duration = self.timings[name]["duration"]

            if self.should_log("DEBUG"):
                color = "GREEN" if duration < 1 else "YELLOW" if duration < 5 else "RED"
                self.log(
                    f"⏱️ ТАЙМИНГ КОНЕЦ: {name} - {duration:.3f} сек",
                    level="DEBUG",
                    color=color,
                )

    def log_file_operation(
        self, operation: str, file_path: str, size: int = None, success: bool = True
    ):
        """Логирование операций с файлами"""
        op_info = {
            "operation": operation,
            "path": str(file_path),
            "size": size,
            "success": success,
            "time": datetime.now(),
        }
        self.file_operations.append(op_info)
        self.stats[f"file_{operation}"] += 1

        if self.should_log("VERBOSE"):
            status = "✅" if success else "❌"
            size_str = f" ({size / 1024:.1f} KB)" if size else ""
            self.log(
                f"{status} {operation}: {file_path}{size_str}",
                level="VERBOSE",
                color="DIM",
            )

    def log_variable(self, name: str, value: Any, max_len: int = 100):
        """Логирование значения переменной для отладки"""
        if not self.should_log("DEBUG"):
            return

        value_str = repr(value)
        if len(value_str) > max_len:
            value_str = value_str[:max_len] + "..."

        self.log(f"📊 ПЕРЕМЕННАЯ: {name} = {value_str}", level="DEBUG", color="MAGENTA")

    def log_text_sample(self, name: str, text: str, max_chars: int = 200):
        """Логирование образца текста"""
        if not self.should_log("VERBOSE") or not text:
            return

        sample = text[:max_chars]
        if len(text) > max_chars:
            sample += "..."

        self.log(f"📝 {name}: {len(text)} символов", level="VERBOSE", color="CYAN")
        self.log(f"   Образец: {repr(sample)}", level="VERBOSE", color="DIM", indent=2)

    def log_audio_info(
        self,
        file_path: str,
        duration: float = None,
        sample_rate: int = None,
        channels: int = None,
    ):
        """Логирование информации об аудиофайле"""
        if not self.should_log("INFO"):
            return

        size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
        size_mb = size / (1024 * 1024)

        info = f"📁 АУДИОФАЙЛ: {file_path}"
        info += f"\n   Размер: {size_mb:.2f} MB"
        if duration:
            minutes = int(duration // 60)
            seconds = duration % 60
            info += f"\n   Длительность: {minutes}:{seconds:02.0f}"
        if sample_rate:
            info += f"\n   Частота: {sample_rate} Hz"
        if channels:
            info += f"\n   Каналов: {channels}"

        self.log(info, level="INFO", color="GREEN")

    def print_summary(self):
        """Вывод сводки отладки"""
        self.log("\n" + "=" * 60, level="INFO")
        self.log("📊 СВОДКА ОТЛАДКИ", level="INFO", color="CYAN")
        self.log("=" * 60, level="INFO")

        if self.errors:
            self.log(f"\n❌ Ошибок: {len(self.errors)}", level="INFO")
            for i, error in enumerate(self.errors[:5], 1):
                self.log(f"   {i}. {error['message']}", level="INFO", color="RED")

        if self.warnings:
            self.log(f"\n⚠️ Предупреждений: {len(self.warnings)}", level="INFO")
            for i, warning in enumerate(self.warnings[:5], 1):
                self.log(f"   {i}. {warning['message']}", level="INFO", color="YELLOW")

        if self.stats:
            self.log("\n📈 СТАТИСТИКА:", level="INFO")
            for key, value in sorted(self.stats.items()):
                self.log(f"   {key}: {value}", level="INFO", color="GREEN")

        if self.timings:
            self.log("\n⏱️ ТАЙМИНГИ:", level="INFO")
            for name, timing in sorted(self.timings.items()):
                if timing["duration"]:
                    self.log(
                        f"   {name}: {timing['duration']:.3f} сек",
                        level="INFO",
                        color="BLUE",
                    )

        self.log("\n" + "=" * 60, level="INFO")
        self.log("🏁 ОТЛАДКА ЗАВЕРШЕНА", level="INFO", color="CYAN")
        if self.log_file:
            self.log(f"   Лог сохранён: {self.log_file}", level="INFO")
        self.log("=" * 60, level="INFO")


# ========== Декораторы ==========


def debug_trace(func: Callable) -> Callable:
    """Декоратор для трассировки вызовов функций"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        debug = DebugCore()
        if debug.should_log("TRACE"):
            debug.trace_call(func.__name__, args, kwargs)

        try:
            result = func(*args, **kwargs)
            if debug.should_log("TRACE"):
                debug.trace_return(func.__name__, result)
            return result
        except Exception as e:
            debug.log_error(f"Ошибка в {func.__name__}", e, show_traceback=True)
            raise

    return wrapper


def debug_timing(func: Callable) -> Callable:
    """Декоратор для измерения времени выполнения"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        debug = DebugCore()
        func_name = func.__name__
        debug.start_timing(func_name)
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            debug.end_timing(func_name)

    return wrapper


# ========== Глобальный экземпляр ==========
_DEBUG_INSTANCE = None


def get_debugger() -> DebugCore:
    """Получить глобальный экземпляр отладчика"""
    global _DEBUG_INSTANCE
    if _DEBUG_INSTANCE is None:
        _DEBUG_INSTANCE = DebugCore()
    return _DEBUG_INSTANCE


def init_debug(level: Union[str, int] = "INFO", log_to_file: bool = True) -> DebugCore:
    """Инициализировать глобальный отладчик"""
    debugger = get_debugger()
    debugger.initialize(level, log_to_file)
    return debugger
