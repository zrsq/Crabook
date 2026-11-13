#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Оркестратор для создания аудиокниги
Версия 8.0 - модульная архитектура с MVC
"""

import sys
import argparse
import time
from pathlib import Path

# Сначала добавляем путь
sys.path.insert(0, str(Path(__file__).parent))

# Теперь все импорты вместе
from core.debug_core import init_debug, get_debugger, debug_trace, debug_timing
from core.dependency_manager import get_dependency_manager
from core.config_manager import get_config_manager
from core.context import ExecutionContext, ProcessingOptions, ProcessingMode, AudioFormat
from core.pipeline import Pipeline, PipelineStage
from core.exceptions import AudiobookError
from services.text_preparation import TextPreparationService
from services.ssml_validation import SSMLValidationService
from services.audio_generation import AudioGenerationService
from models.ssml_chunk import SSMLChunk
from utils.file_utils import FileUtils
from utils.naming import translit_slug


class AudiobookOrchestrator:
    """
    Главный оркестратор создания аудиокниги.
    Координирует все сервисы и управляет процессом.
    """

    def __init__(self, debug_level: str = None):
        # Инициализируем отладчик
        if debug_level:
            self.debug = init_debug(debug_level)
        else:
            self.debug = get_debugger()

        self.debug.log("=" * 60, level="INFO")
        self.debug.log("🎙️ AUDIOBOOK CREATOR v8.0", level="INFO")
        self.debug.log("=" * 60, level="INFO")

        # Инициализируем менеджеры
        self.debug.log("Инициализация зависимостей...", level="INFO")
        self.deps = get_dependency_manager()

        self.debug.log("Загрузка конфигураций...", level="INFO")
        self.config = get_config_manager()

        # Контекст выполнения (будет создан при запуске)
        self.context: ExecutionContext = None

        # Сервисы (создаются при необходимости)
        self._text_service: TextPreparationService = None
        self._validation_service: SSMLValidationService = None
        self._audio_service: AudioGenerationService = None

        # Статистика
        self.start_time = None
        self.end_time = None

    @property
    def text_service(self) -> TextPreparationService:
        if self._text_service is None:
            self._text_service = TextPreparationService(self.context)
        return self._text_service

    @property
    def validation_service(self) -> SSMLValidationService:
        if self._validation_service is None:
            self._validation_service = SSMLValidationService(self.context)
        return self._validation_service

    @property
    def audio_service(self) -> AudioGenerationService:
        if self._audio_service is None:
            self._audio_service = AudioGenerationService(self.context)
        return self._audio_service

    def find_book_file(self, book_dir: str = "book") -> Path:
        """
        Ищет файл книги в указанной папке.
        """
        book_path = Path(book_dir)

        if not book_path.exists():
            raise FileNotFoundError(f"Папка '{book_dir}' не существует")

        # Поддерживаемые форматы
        formats = self.deps.get_available_formats()

        book_files = []
        for ext in formats:
            book_files.extend(book_path.glob(f"*.{ext}"))
            book_files.extend(book_path.glob(f"*.{ext.upper()}"))

        book_files = [f for f in book_files if f.is_file()]

        if len(book_files) == 0:
            raise FileNotFoundError(
                f"В папке '{book_dir}' не найдено файлов. "
                f"Поддерживаемые форматы: {', '.join(formats)}"
            )

        if len(book_files) > 1:
            files_list = "\n   ".join(f.name for f in book_files)
            raise ValueError(
                f"В папке '{book_dir}' найдено несколько файлов:\n   {files_list}\n"
                "Оставьте только один файл или укажите его явно через -i"
            )

        return book_files[0]

    def find_book_config(
        self, book_name: str, config_dir: str = "book_specific"
    ) -> Path:
        """
        Ищет конфиг для конкретной книги.
        """
        config_path = Path(config_dir)

        # Сначала ищем специфичный конфиг
        specific = config_path / f"{book_name}.json"
        if specific.exists():
            return specific

        # Потом общий
        default = config_path / "book_config.json"
        if default.exists():
            return default

        return None

    def create_context(
        self,
        input_path: Path,
        output_path: Path = None,
        options: ProcessingOptions = None,
    ) -> ExecutionContext:
        """
        Создаёт контекст выполнения.
        """
        # Определяем выходной путь
        if output_path is None:
            audio_dir = Path("audio")
            audio_dir.mkdir(exist_ok=True)

            ext = ".m4a"  # По умолчанию AAC
            if options:
                if options.output_format == AudioFormat.MP3:
                    ext = ".mp3"
                elif options.output_format == AudioFormat.WAV:
                    ext = ".wav"

            output_path = audio_dir / f"{input_path.stem}{ext}"

        # Создаём контекст
        context = ExecutionContext(
            input_path=input_path,
            output_path=output_path,
            options=options or ProcessingOptions(),
            debug=self.debug,
            deps=self.deps,
            config=self.config,
        )

        # Загружаем конфиг книги если есть.
        # FIX BUG-7: НЕ перезатираем явно указанный --book-config,
        # который main() уже загрузил в self.config.book_config.
        if self.config.book_config is None:
            book_config_path = self.find_book_config(input_path.stem)
            if book_config_path:
                self.config.load_book_config(config_path=book_config_path)
                self.debug.log(
                    f"📖 Загружен конфиг книги: {book_config_path}", level="INFO"
                )
        context.book_config = self.config.book_config

        # Определяем режим выполнения
        if self.debug.should_log("VERBOSE"):
            context.options.mode = ProcessingMode.SEQUENTIAL
            self.debug.log(
                "🐛 Режим ОТЛАДКИ: последовательное выполнение", level="INFO"
            )

        # ОТЛАДКА
        self.debug.log(f"Options genre: {context.options.genre}", level='INFO')
        self.debug.log(f"Config genre: {context.config.processing_config.default_genre if context.config else 'no config'}", level='INFO')
        self.debug.log(f"Effective genre: {context.get_effective_genre()}", level='INFO')

        return context

    @debug_trace
    @debug_timing
    def build_pipeline(self) -> Pipeline:
        """
        Строит конвейер обработки.
        """
        pipeline = Pipeline(self.context)

        # Этап 1: Подготовка текста и SSML
        stage1 = PipelineStage(
            name="Подготовка SSML",
            func=lambda ctx: self._run_text_preparation(ctx),
            enabled=True,
            can_parallelize=False,
        )
        pipeline.add_stage(stage1)

        # Этап 2: Валидация SSML (опционально)
        if not self.context.options.skip_validation:
            stage2 = PipelineStage(
                name="Валидация SSML",
                func=lambda ctx: self._run_validation(ctx),
                enabled=True,
                can_parallelize=False,
            )
            pipeline.add_stage(stage2)

        # Этап 3: Генерация аудио
        stage3 = PipelineStage(
            name="Генерация аудио",
            func=lambda ctx: self._run_audio_generation(ctx),
            enabled=True,
            can_parallelize=False,  # Внутри сервиса есть свой параллелизм
        )
        pipeline.add_stage(stage3)

        return pipeline

    def _run_text_preparation(self, context: ExecutionContext) -> dict:
        """
        Выполняет подготовку текста.
        """
        self.debug.log("\n" + "─" * 60, level="INFO")
        self.debug.log("📝 ЭТАП 1: ПОДГОТОВКА SSML", level="INFO")
        self.debug.log("─" * 60, level="INFO")

        # Подготавливаем текст
        ssml_text = self.text_service.process()

        # Разбиваем на чанки
        chunks = self.text_service.prepare_chunks()

        return {"ssml_text": ssml_text, "chunks": chunks, "chunks_count": len(chunks)}

    def _run_validation(self, context: ExecutionContext) -> dict:
        """
        Выполняет валидацию SSML.
        """
        self.debug.log("\n" + "─" * 60, level="INFO")
        self.debug.log("🔍 ЭТАП 2: ВАЛИДАЦИЯ SSML", level="INFO")
        self.debug.log("─" * 60, level="INFO")

        is_valid = self.validation_service.validate(auto_fix=True)

        result = context.validation_result

        if not is_valid:
            self.debug.log_warning(
                "SSML содержит ошибки, но генерация будет продолжена"
            )

        return result

    def _run_audio_generation(self, context: ExecutionContext) -> dict:
        """
        Выполняет генерацию аудио.
        """
        self.debug.log("\n" + "─" * 60, level="INFO")
        self.debug.log("🎙️ ЭТАП 3: ГЕНЕРАЦИЯ АУДИО", level="INFO")
        self.debug.log("─" * 60, level="INFO")

        # Получаем чанки из предыдущего этапа
        chunks_data = context.ssml_chunks
        chunks = [
            SSMLChunk(
                content=c["content"],
                index=c["index"],
                word_count=c.get("word_count", 0),
            )
            for c in chunks_data
        ]

        self.debug.log(f"Чанков для озвучивания: {len(chunks)}", level="INFO")
        self.debug.log(f"Голос: {context.get_effective_voice()}", level="INFO")
        self.debug.log(f"Потоков: {context.options.workers}", level="INFO")

        # Генерируем аудио
        final_path = self.audio_service.generate_full(chunks)

        return {"final_path": final_path, "audio_book": self.audio_service.audio_book}

    def run(
        self,
        input_path: Path = None,
        output_path: Path = None,
        options: ProcessingOptions = None,
    ) -> bool:
        """
        Запускает полный процесс создания аудиокниги.
        """
        self.start_time = time.time()

        try:
            # 1. Находим файл книги если не указан
            if input_path is None:
                input_path = self.find_book_file()
                self.debug.log(f"📖 Найден файл: {input_path.name}", level="INFO")
            elif not input_path.exists():
                raise FileNotFoundError(f"Файл не найден: {input_path}")

            # Построчный режим: каждая строка -> отдельный файл
            if options is not None and options.per_line:
                return self.run_per_line(input_path, output_path, options)

            # 2. Создаём контекст
            self.context = self.create_context(input_path, output_path, options)

            # 3. Выводим информацию о книге
            self._print_book_info()

            # 4. Строим и запускаем конвейер
            pipeline = self.build_pipeline()
            self.context = pipeline.run()

            # 5. Проверяем результат
            if self.context.has_errors():
                self.debug.log_error("Процесс завершился с ошибками")
                return False

            # 6. Выводим итоговую информацию
            self._print_final_summary()

            return True

        except AudiobookError as e:
            self.debug.log_error(f"Ошибка аудиокниги: {e}", e, show_traceback=True)
            return False
        except Exception as e:
            self.debug.log_error("Неожиданная ошибка", e, show_traceback=True)
            return False
        finally:
            self.end_time = time.time()

    def _print_book_info(self):
        """Выводит информацию о книге"""
        print("\n" + "="*60)
        print("📖 ИНФОРМАЦИЯ О КНИГЕ")
        print("="*60)
        print(f"   Файл: {self.context.input_path.name}")
        print(f"   Жанр: {self.context.get_effective_genre()}")
        print(f"   Голос: {self.context.get_effective_voice()}")

        # Формат
        if self.context.options.no_convert:
            print("   Формат: WAV (без конвертации)")
        elif self.context.options.output_formats:
            formats = ", ".join(f.value.upper() for f in self.context.options.output_formats)
            print(f"   Форматы: {formats}")
        else:
            print(f"   Формат: {self.context.options.output_format.value.upper()}")

        print(f"   Режим: {self.context.options.mode.value}")
        print(f"   Потоков: {self.context.get_effective_workers()}")

        # Дополнительная информация
        if self.context.book_config:
            print(f"   📖 Конфиг книги: {self.context.book_config.path.name}")

        print("="*60 + "\n")

    def _print_final_summary(self):
        """Выводит итоговую сводку"""
        duration = 0
        if self.end_time and self.start_time:
            duration = self.end_time - self.start_time

        print("\n" + "=" * 60)
        print("✅ АУДИОКНИГА ГОТОВА!")
        print("=" * 60)

        outputs = []
        if self._audio_service is not None:
            outputs = list(getattr(self._audio_service, "output_files", []) or [])
        if not outputs and self.context and self.context.final_output:
            outputs = [self.context.final_output]

        if outputs:
            print(f"   📁 Файлов создано: {len(outputs)}")
            for p in outputs:
                if p and p.exists():
                    size_mb = p.stat().st_size / (1024 * 1024)
                    print(f"      • {p}  ({size_mb:.2f} MB)")

        if self._audio_service and self._audio_service.audio_book:
            audio_book = self._audio_service.audio_book
            if audio_book.final_duration_seconds > 0:
                print(f"   ⏱️  Длительность: {audio_book.total_duration_formatted}")

        if duration > 0:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            print(f"   ⚙️  Время обработки: {minutes} мин {seconds} сек")

        if self.context and self.context.stats:
            print("\n📊 СТАТИСТИКА:")
            for key, value in self.context.stats.items():
                if isinstance(value, int):
                    print(f"   {key}: {value:,}")
                else:
                    print(f"   {key}: {value}")

        print("=" * 60 + "\n")

    def run_per_line(
        self,
        input_path: Path,
        output_path: Path = None,
        options: ProcessingOptions = None,
    ) -> bool:
        """Построчная генерация: каждая непустая строка -> отдельный аудиофайл."""
        import tempfile
        import shutil

        self.start_time = time.time()
        options = options or ProcessingOptions()

        try:
            text = FileUtils().extract_text(input_path)
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if not lines:
                self.debug.log_error("Файл не содержит непустых строк")
                return False

            out_dir = Path(output_path) if output_path else Path("audio")
            out_dir.mkdir(parents=True, exist_ok=True)

            if self.config.book_config is None:
                bcp = self.find_book_config(input_path.stem)
                if bcp:
                    self.config.load_book_config(config_path=bcp)
            book_config = self.config.book_config

            ext = {AudioFormat.MP3: ".mp3", AudioFormat.WAV: ".wav"}.get(
                options.output_format, ".m4a"
            )

            self.debug.log(
                f"📖 Построчный режим: {len(lines)} строк -> {out_dir}/", level="INFO"
            )

            tmp_root = Path(tempfile.mkdtemp(prefix="crabook_lines_"))
            used_names = set()
            results = []

            try:
                for i, line in enumerate(lines):
                    slug = translit_slug(line) or f"line_{i + 1:04d}"
                    base, n = slug, 2
                    while slug in used_names:
                        slug = f"{base}_{n}"
                        n += 1
                    used_names.add(slug)

                    out_file = out_dir / f"{slug}{ext}"
                    line_file = tmp_root / f"{slug}.txt"
                    line_file.write_text(line, encoding="utf-8")

                    ctx = ExecutionContext(
                        input_path=line_file,
                        output_path=out_file,
                        options=options,
                        debug=self.debug,
                        deps=self.deps,
                        config=self.config,
                    )
                    ctx.book_config = book_config
                    self.context = ctx

                    if self._text_service is None:
                        self._text_service = TextPreparationService(ctx)
                    else:
                        self._text_service.context = ctx
                    if self._validation_service is None:
                        self._validation_service = SSMLValidationService(ctx)
                    else:
                        self._validation_service.context = ctx
                    if self._audio_service is None:
                        self._audio_service = AudioGenerationService(ctx)
                    else:
                        self._audio_service.context = ctx

                    self.debug.log(f"\n[{i + 1}/{len(lines)}] {line}", level="INFO")
                    try:
                        self._run_text_preparation(ctx)
                        if not options.skip_validation:
                            self._run_validation(ctx)
                        self._run_audio_generation(ctx)
                        if ctx.has_errors():
                            self.debug.log_error(f"Строка {i + 1}: ошибки, пропуск")
                            continue
                        produced = list(getattr(self._audio_service, 'output_files', []) or [])
                        if produced:
                            results.extend(produced)
                        else:
                            results.append(ctx.final_output or out_file)
                        self.debug.log(f"✅ {out_file.name}", level="INFO")
                    except Exception as e:
                        self.debug.log_error(f"Строка {i + 1} не обработана: {e}", e)
                        continue
            finally:
                shutil.rmtree(tmp_root, ignore_errors=True)

            self._print_per_line_summary(results, out_dir)
            return len(results) > 0

        except Exception as e:
            self.debug.log_error("Ошибка построчного режима", e, show_traceback=True)
            return False
        finally:
            self.end_time = time.time()

    def _print_per_line_summary(self, results, out_dir):
        """Сводка построчного режима"""
        print("\n" + "=" * 60)
        print("✅ ПОСТРОЧНАЯ ГЕНЕРАЦИЯ ЗАВЕРШЕНА!")
        print("=" * 60)
        print(f"   📁 Каталог: {out_dir}/")
        print(f"   🔊 Файлов создано: {len(results)}")
        for p in results:
            if p and p.exists():
                print(f"      • {p.name}")
        if self.start_time and self.end_time:
            dur = self.end_time - self.start_time
            print(f"   ⚙️  Время: {int(dur // 60)} мин {int(dur % 60)} сек")
        print("=" * 60 + "\n")

def create_parser() -> argparse.ArgumentParser:
    """Создаёт парсер аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description="Создание аудиокниги из текстового файла",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Автоматический поиск файла в папке book
  python crabook.py
  
  # Указать конкретный файл
  python crabook.py -i mybook.txt
  
  # С отладкой
  python crabook.py --debug VERBOSE
  
  # Указать жанр и голос
  python crabook.py -g fiction -v aidar
  
  # Сгенерировать в MP3
  python crabook.py --format mp3 --bitrate 128k
  
  # Несколько форматов
  python crabook.py --formats aac mp3
        """,
    )

    # Основные параметры
    main_group = parser.add_argument_group("Основные параметры")
    main_group.add_argument("-i", "--input", type=Path, help="Входной файл")
    main_group.add_argument("-o", "--output", type=Path, help="Выходной файл")
    main_group.add_argument(
        "-g",
        "--genre",
        choices=["fiction", "nonfiction", "poetry", "drama"],
        help="Жанр книги",
    )
    main_group.add_argument(
        "-v",
        "--voice",
        choices=["xenia", "eugene", "aidar", "baya", "kseniya"],
        help="Голос для озвучивания",
    )

    # Параметры обработки
    proc_group = parser.add_argument_group("Параметры обработки")
    proc_group.add_argument(
        "-c", "--chunk-size", type=int, help="Размер чанка в символах"
    )
    proc_group.add_argument(
        "-w", "--workers", type=int, help="Количество потоков для генерации"
    )
    proc_group.add_argument(
        "--split-chapters", action="store_true", help="Разбить на главы"
    )
    proc_group.add_argument(
        "--skip-validation", action="store_true", help="Пропустить валидацию SSML"
    )
    proc_group.add_argument(
        "--per-line", action="store_true",
        help="Построчная генерация: каждая строка -> отдельный файл (имя = транслит строки)",
    )

    # Параметры вывода
    output_group = parser.add_argument_group("Параметры вывода")
    output_group.add_argument(
        "--format",
        choices=["aac", "mp3", "wav"],
        default="aac",
        help="Формат выходного файла",
    )
    output_group.add_argument(
        "--formats",
        nargs="+",
        choices=["aac", "mp3", "wav"],
        help="Создать несколько форматов",
    )
    output_group.add_argument("-b", "--bitrate", help="Битрейт (64k, 128k, 192k)")
    output_group.add_argument(
        "-sr", "--sample-rate", type=int, help="Частота дискретизации"
    )
    output_group.add_argument(
        "--no-convert", action="store_true", help="Не конвертировать, оставить WAV"
    )

    # Аудио постобработка
    audio_group = parser.add_argument_group("Аудио постобработка")
    audio_group.add_argument(
        "--lowpass", action="store_true", help="Включить low-pass фильтр"
    )
    audio_group.add_argument(
        "--lowpass-cutoff", type=int, help="Частота среза low-pass (Гц)"
    )
    audio_group.add_argument(
        "--no-deesser", action="store_true", help="Отключить de-esser"
    )
    audio_group.add_argument(
        "--deesser-threshold", type=float, help="Порог de-esser (dB)"
    )
    audio_group.add_argument(
        "--no-spectral-nr", action="store_true", help="Отключить шумоподавление"
    )
    audio_group.add_argument(
        "--spectral-nr-amount", type=float, help="Степень шумоподавления (0-1)"
    )
    audio_group.add_argument(
        "--room-tone", action="store_true", help="Добавить room tone"
    )
    audio_group.add_argument(
        "--no-normalize", action="store_true", help="Отключить нормализацию"
    )
    audio_group.add_argument(
        "--target-volume", type=float, help="Целевая громкость (LUFS)"
    )

    # Отладка
    debug_group = parser.add_argument_group("Отладка")
    debug_group.add_argument(
        "--debug",
        choices=["ERROR", "WARN", "INFO", "VERBOSE", "DEBUG", "TRACE"],
        help="Уровень отладки",
    )
    debug_group.add_argument(
        "--no-debug-log", action="store_true", help="Не сохранять лог в файл"
    )

    # Конфигурация
    config_group = parser.add_argument_group("Конфигурация")
    config_group.add_argument(
        "--book-config", type=Path, help="JSON файл с настройками для книги"
    )
    config_group.add_argument(
        "--config-dir", default="config", help="Папка с конфигурациями"
    )

    return parser


def build_options_from_args(args) -> ProcessingOptions:
    """Создаёт ProcessingOptions из аргументов командной строки"""
    options = ProcessingOptions()

    # Основные
    if args.genre:
        options.genre = args.genre
    if args.voice:
        options.voice = args.voice
    if args.chunk_size:
        options.chunk_size = args.chunk_size
    if args.workers:
        options.workers = args.workers

    # Обработка
    options.split_chapters = args.split_chapters
    options.skip_validation = args.skip_validation
    options.per_line = args.per_line

    # Вывод
    if args.format:
        options.output_format = AudioFormat(args.format)
    if args.formats:
        options.output_formats = [AudioFormat(f) for f in args.formats]
    if args.bitrate:
        options.bitrate = args.bitrate
    if args.sample_rate:
        options.sample_rate = args.sample_rate
    options.no_convert = args.no_convert

    # Аудио
    options.lowpass = args.lowpass
    if args.lowpass_cutoff:
        options.lowpass_cutoff = args.lowpass_cutoff
    options.no_deesser = args.no_deesser
    if args.deesser_threshold:
        options.deesser_threshold = args.deesser_threshold
    options.no_spectral_nr = args.no_spectral_nr
    if args.spectral_nr_amount:
        options.spectral_nr_amount = args.spectral_nr_amount
    options.room_tone = args.room_tone
    options.no_normalize = args.no_normalize
    if args.target_volume:
        options.target_volume = args.target_volume

    return options


def main():
    """Точка входа"""
    parser = create_parser()
    args = parser.parse_args()

    # Проверяем наличие конфигов, если нет - генерируем
    config_dir = args.config_dir or "config"
    default_config = Path(config_dir) / "default_settings.json"

    if not default_config.exists():
        print("\n⚠️ Конфигурационные файлы не найдены!")
        print("📝 Запуск генератора конфигов...\n")

        from core.config_generator import generate_configs
        generate_configs(config_dir, force=False)
        print("\n✅ Конфиги сгенерированы. Отредактируйте их при необходимости.\n")

    # Инициализируем отладчик
    if args.debug:
        init_debug(level=args.debug, log_to_file=not args.no_debug_log)

    debug = get_debugger()

    try:
        # Создаём опции
        options = build_options_from_args(args)

        # Создаём оркестратор
        orchestrator = AudiobookOrchestrator(debug_level=args.debug)

        # Загружаем конфиг книги если указан явно
        if args.book_config:
            orchestrator.config.load_book_config(config_path=args.book_config)

        # Запускаем
        success = orchestrator.run(
            input_path=args.input, output_path=args.output, options=options
        )

        # Выводим сводку отладки
        if args.debug:
            debug.print_summary()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
        debug.log_warning("Процесс прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        debug.log_error("Критическая ошибка", e, show_traceback=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
