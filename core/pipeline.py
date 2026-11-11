#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Конвейер обработки - управляет последовательностью этапов
"""

import time
import gc
from typing import Callable, List, Dict, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.context import ExecutionContext, ProcessingMode
from core.exceptions import PipelineError
from core.debug_core import get_debugger, debug_trace, debug_timing


@dataclass
class PipelineStage:
    """Этап конвейера"""

    name: str
    func: Callable
    enabled: bool = True
    can_parallelize: bool = False
    depends_on: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """
    Конвейер обработки.
    Управляет выполнением этапов в правильном порядке.
    """

    def __init__(self, context: ExecutionContext):
        self.context = context
        self.debug = context.debug or get_debugger()
        self.stages: List[PipelineStage] = []
        self.results: Dict[str, Any] = {}
        self.timings: Dict[str, float] = {}

    def add_stage(self, stage: PipelineStage) -> "Pipeline":
        """Добавляет этап в конвейер"""
        self.stages.append(stage)
        self.debug.log(f"➕ Добавлен этап: {stage.name}", level="VERBOSE")
        return self

    def add_stages(self, stages: List[PipelineStage]) -> "Pipeline":
        """Добавляет несколько этапов"""
        for stage in stages:
            self.add_stage(stage)
        return self

    @debug_trace
    @debug_timing
    def _run_stage(self, stage: PipelineStage) -> Any:
        """Выполняет один этап"""
        self.debug.log_stage(stage.name, "start")

        start_time = time.time()

        try:
            result = stage.func(self.context)
            self.results[stage.name] = result
            self.timings[stage.name] = time.time() - start_time

            self.debug.log_stage(stage.name, "end")
            self.debug.log(
                f"   ⏱️ Время: {self.timings[stage.name]:.2f} сек", level="INFO"
            )

            return result
        except Exception as e:
            self.debug.log_stage(stage.name, "error")
            self.context.add_error(f"Ошибка на этапе {stage.name}: {e}")
            raise PipelineError(
                f"Этап {stage.name} завершился с ошибкой", {"stage": stage.name}
            ) from e

    @debug_trace
    def run(self) -> ExecutionContext:
        """
        Запускает конвейер.
        В режиме SEQUENTIAL - этапы выполняются строго последовательно.
        В режиме PARALLEL - этапы, которые можно распараллелить, выполняются параллельно.
        """
        self.debug.log_stage("ЗАПУСК КОНВЕЙЕРА", "start")
        self.debug.log(f"   Режим: {self.context.options.mode.value}", level="INFO")
        self.debug.log(f"   Этапов: {len(self.stages)}", level="INFO")

        if self.context.options.mode == ProcessingMode.SEQUENTIAL:
            return self._run_sequential()
        else:
            return self._run_parallel()

    def _run_sequential(self) -> ExecutionContext:
        """Последовательное выполнение этапов"""
        self.debug.log("🔄 Последовательное выполнение", level="INFO")

        for i, stage in enumerate(self.stages, 1):
            if not stage.enabled:
                self.debug.log(f"⏭️ Пропущен этап: {stage.name}", level="INFO")
                continue

            self.debug.log(
                f"\n--- Этап {i}/{len(self.stages)}: {stage.name} ---", level="INFO"
            )

            try:
                self._run_stage(stage)
            except PipelineError:
                # Останавливаем конвейер при ошибке
                self.debug.log_error(f"❌ Конвейер остановлен на этапе: {stage.name}")
                break

            # Принудительная сборка мусора после тяжёлых этапов
            if "tts" in stage.name.lower() or "audio" in stage.name.lower():
                gc.collect()
                self.debug.log("🧹 Сборка мусора выполнена", level="VERBOSE")

        self._print_summary()
        return self.context

    def _run_parallel(self) -> ExecutionContext:
        """Параллельное выполнение этапов (где возможно)"""
        self.debug.log("⚡ Параллельное выполнение", level="INFO")

        # Группируем этапы: последовательные и параллельные группы
        groups = self._group_stages()

        for group_idx, group in enumerate(groups, 1):
            if len(group) == 1:
                # Один этап - выполняем последовательно
                stage = group[0]
                if stage.enabled:
                    self.debug.log(
                        f"\n--- Этап {group_idx}/{len(groups)}: {stage.name} ---",
                        level="INFO",
                    )
                    try:
                        self._run_stage(stage)
                    except PipelineError:
                        break
            else:
                # Несколько этапов - выполняем параллельно
                self.debug.log(
                    f"\n--- Параллельная группа {group_idx}/{len(groups)}: "
                    + f"{', '.join(s.name for s in group)} ---",
                    level="INFO",
                )

                with ThreadPoolExecutor(max_workers=len(group)) as executor:
                    futures = {}
                    for stage in group:
                        if stage.enabled:
                            futures[executor.submit(self._run_stage, stage)] = stage

                    for future in as_completed(futures):
                        stage = futures[future]
                        try:
                            future.result()
                        except PipelineError as e:
                            self.debug.log_error(
                                f"Ошибка в параллельном этапе {stage.name}: {e}"
                            )
                            # Отменяем остальные
                            for f in futures:
                                f.cancel()
                            break

                gc.collect()

        self._print_summary()
        return self.context

    def _group_stages(self) -> List[List[PipelineStage]]:
        """Группирует этапы для параллельного выполнения"""
        groups = []
        current_group = []

        for stage in self.stages:
            if stage.can_parallelize:
                current_group.append(stage)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([stage])

        if current_group:
            groups.append(current_group)

        return groups

    def _print_summary(self):
        """Выводит сводку выполнения"""
        self.debug.log("\n" + "=" * 60, level="INFO")
        self.debug.log("📊 СВОДКА ВЫПОЛНЕНИЯ КОНВЕЙЕРА", level="INFO")
        self.debug.log("=" * 60, level="INFO")

        total_time = sum(self.timings.values())
        self.debug.log(f"⏱️ Общее время: {total_time:.2f} сек", level="INFO")

        for stage_name, duration in self.timings.items():
            percentage = (duration / total_time * 100) if total_time > 0 else 0
            self.debug.log(
                f"   {stage_name}: {duration:.2f} сек ({percentage:.1f}%)", level="INFO"
            )

        if self.context.errors:
            self.debug.log(f"\n❌ Ошибок: {len(self.context.errors)}", level="INFO")
        if self.context.warnings:
            self.debug.log(
                f"⚠️ Предупреждений: {len(self.context.warnings)}", level="INFO"
            )

        self.debug.log_stage("ЗАВЕРШЕНИЕ КОНВЕЙЕРА", "end")
