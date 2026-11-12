#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сервис генерации аудио
"""

import tempfile
import gc
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.debug_core import get_debugger, debug_trace, debug_timing
from core.context import ExecutionContext, AudioFormat
from core.config_manager import AudioProcessingConfig
from core.exceptions import TTSGenerationError, AudioProcessingError, ConversionError

from utils.audio_utils import AudioUtils
from utils.text_utils import TextUtils

from engines.tts_engine import TTSEngine
from engines.audio_processor import AudioProcessor, ProcessingOptions

from models.ssml_chunk import SSMLChunk
from models.audio_chunk import AudioChunk, AudioBook, AudioChunkStatus


class AudioGenerationService:
    """
    Сервис генерации аудио.
    Оркеструет:
    - Генерацию речи через TTS
    - Постобработку аудио
    - Конвертацию в нужный формат
    - Объединение чанков
    """
    
    def __init__(self, context: ExecutionContext):
        self.context = context
        self.debug = context.debug or get_debugger()
        self.config = context.config
        
        self.audio_utils = AudioUtils()
        self.text_utils = TextUtils()
        
        # Движки
        self._tts_engine: Optional[TTSEngine] = None
        self._audio_processor: Optional[AudioProcessor] = None
        
        # Аудиокнига
        self.audio_book = AudioBook()
        
        # Временная директория
        self._temp_dir: Optional[Path] = None
        
        # Очищаем старые временные директории при старте
        self._cleanup_old_temp_dirs()
    
    @staticmethod
    def _cleanup_old_temp_dirs(max_age_hours: float = 24.0):
        """
        FIX BUG-9: удаляет только СТАРЫЕ (>24ч) временные директории.
        Раньше сносились все audiobook_* — включая каталоги параллельно
        работающего второго инстанса.
        """
        import time

        temp_root = Path(tempfile.gettempdir())
        now = time.time()
        for old_dir in temp_root.glob("audiobook_*"):
            try:
                if now - old_dir.stat().st_mtime > max_age_hours * 3600:
                    shutil.rmtree(old_dir, ignore_errors=True)
            except Exception:
                pass
    
    @property
    def tts_engine(self) -> TTSEngine:
        """Ленивая инициализация TTS движка"""
        if self._tts_engine is None:
            device = 'cuda' if self.context.deps.torch.cuda.is_available() else 'cpu'
            self._tts_engine = TTSEngine(
                voice=self.context.get_effective_voice(),
                sample_rate=self.context.get_effective_sample_rate(),
                device=device
            )
        return self._tts_engine
    
    @property
    def audio_processor(self) -> AudioProcessor:
        """Ленивая инициализация аудио процессора"""
        if self._audio_processor is None:
            if self.config:
                self._audio_processor = AudioProcessor(
                    config=self.config.audio_config
                )
            else:
                self._audio_processor = AudioProcessor()
        
        # Переопределяем опции из контекста
        self._apply_context_options()
        
        return self._audio_processor
    
    def _apply_context_options(self):
        """Применяет опции из контекста к аудио процессору"""
        opts = self.context.options
        
        if opts.lowpass:
            self._audio_processor.options.enable_lowpass = True
        if opts.lowpass_cutoff:
            self._audio_processor.options.lowpass_cutoff = opts.lowpass_cutoff
        
        if opts.no_deesser:
            self._audio_processor.options.enable_deesser = False
        if opts.deesser_threshold:
            self._audio_processor.options.deesser_threshold = opts.deesser_threshold
        
        if opts.no_spectral_nr:
            self._audio_processor.options.enable_spectral_nr = False
        if opts.spectral_nr_amount:
            self._audio_processor.options.spectral_nr_amount = opts.spectral_nr_amount
        
        if opts.room_tone:
            self._audio_processor.options.enable_room_tone = True
        
        if opts.no_normalize:
            self._audio_processor.options.enable_normalization = False
        if opts.target_volume:
            self._audio_processor.options.target_volume = opts.target_volume
    
    @debug_trace
    @debug_timing
    def generate_from_ssml(self, ssml_chunks: List[SSMLChunk]) -> List[AudioChunk]:
        """
        Генерирует аудио из списка SSML чанков.
        Поддерживает параллельную генерацию.
        """
        self.debug.log_stage("Генерация аудио", "start")
        self.debug.log(f"Чанков для генерации: {len(ssml_chunks)}", level='INFO')
        
        audio_chunks = []
        self._temp_dir = Path(tempfile.mkdtemp(prefix="audiobook_"))
        self.debug.log(f"📁 Временная директория: {self._temp_dir}", level='VERBOSE')
        
        # Подготавливаем задания
        jobs = []
        for chunk in ssml_chunks:
            output_path = self._temp_dir / f"chunk_{chunk.index:04d}.wav"
            jobs.append((chunk, output_path))
        
        # FIX BUG-5: options.workers может быть None -> executor брал
        # min(32, cpu+4) потоков вместо конфигурационных 4.
        workers = self.context.get_effective_workers()
        
        if self.context.is_debug_mode():
            # Последовательная генерация в режиме отладки
            audio_chunks = self._generate_sequential(jobs)
        else:
            # Параллельная генерация
            audio_chunks = self._generate_parallel(jobs, workers)
        
        # Постобработка
        audio_chunks = self._post_process_chunks(audio_chunks)
        
        self.audio_book.chunks = audio_chunks
        self.context.audio_files = [c.processed_path or c.wav_path for c in audio_chunks if c.is_ready]
        
        self.debug.log_stage("Генерация аудио", "end")
        
        return audio_chunks
    
    def _generate_sequential(self, jobs: List[Tuple]) -> List[AudioChunk]:
        """Последовательная генерация чанков"""
        audio_chunks = []
        
        for i, (chunk, output_path) in enumerate(jobs):
            self.debug.log(f"Генерация чанка {i+1}/{len(jobs)}...", level='INFO')
            
            audio_chunk = AudioChunk(
                ssml_content=chunk.content,
                index=chunk.index,
                chapter_index=chunk.chapter_index,
                status=AudioChunkStatus.GENERATING
            )
            
            try:
                success = self.tts_engine.generate(chunk.content, output_path)
                if success:
                    audio_chunk.status = AudioChunkStatus.COMPLETED
                    audio_chunk.wav_path = output_path
                    
                    # Получаем информацию о файле
                    info = self.audio_utils.get_wav_info(output_path)
                    if info:
                        audio_chunk.duration_seconds = info[2]
                        audio_chunk.sample_rate = info[0]
                        audio_chunk.file_size = output_path.stat().st_size
                else:
                    audio_chunk.status = AudioChunkStatus.FAILED
                    audio_chunk.error = "Ошибка генерации"
                    
            except Exception as e:
                audio_chunk.status = AudioChunkStatus.FAILED
                audio_chunk.error = str(e)
                self.debug.log_error(f"Ошибка чанка {i}", e)
            
            audio_chunks.append(audio_chunk)
            
            # Сборка мусора после каждого чанка в режиме отладки
            gc.collect()
        
        return audio_chunks
    
    def _generate_parallel(self, jobs: List[Tuple], workers: int) -> List[AudioChunk]:
        """
        Параллельная генерация чанков.
        FIX BUG-5: воркер создаёт и мутирует СВОЙ объект AudioChunk,
        главный поток только читает результат — общей изменяемой памяти нет.
        (Сам вызов Silero дополнительно сериализован Lock'ом в TTSEngine.)
        """
        results_by_index = {}
        futures = {}
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for chunk, output_path in jobs:
                future = executor.submit(
                    self._generate_single_chunk,
                    chunk,
                    output_path,
                )
                futures[future] = chunk.index
            
            completed = 0
            for future in as_completed(futures):
                index = futures[future]
                try:
                    audio_chunk = future.result()
                except Exception as e:
                    audio_chunk = AudioChunk(
                        ssml_content="",
                        index=index,
                        status=AudioChunkStatus.FAILED,
                        error=str(e),
                    )
                    self.debug.log_error(f"Ошибка в параллельном чанке {index}", e)
                results_by_index[index] = audio_chunk
                completed += 1
                self.debug.log(f"Прогресс TTS: {completed}/{len(jobs)}", level='VERBOSE')
            
            # Сборка мусора после параллельной генерации
            gc.collect()
        
        # Возвращаем в исходном порядке
        return [results_by_index[chunk.index] for chunk, _ in jobs]
    
    def _generate_single_chunk(self, chunk: SSMLChunk, output_path: Path) -> AudioChunk:
        """Генерирует один чанк. Объект AudioChunk — локальный для потока."""
        audio_chunk = AudioChunk(
            ssml_content=chunk.content,
            index=chunk.index,
            chapter_index=chunk.chapter_index,
            status=AudioChunkStatus.GENERATING
        )
        
        try:
            success = self.tts_engine.generate(chunk.content, output_path)
            if success:
                audio_chunk.status = AudioChunkStatus.COMPLETED
                audio_chunk.wav_path = output_path
                
                info = self.audio_utils.get_wav_info(output_path)
                if info:
                    audio_chunk.duration_seconds = info[2]
                    audio_chunk.sample_rate = info[0]
                    audio_chunk.file_size = output_path.stat().st_size
            else:
                audio_chunk.status = AudioChunkStatus.FAILED
                audio_chunk.error = "Ошибка генерации"
        except Exception as e:
            audio_chunk.status = AudioChunkStatus.FAILED
            audio_chunk.error = str(e)
        
        return audio_chunk
    
    def _post_process_chunks(self, audio_chunks: List[AudioChunk]) -> List[AudioChunk]:
        """Применяет постобработку к чанкам"""
        self.debug.log("Постобработка аудио...", level='INFO')
        
        for chunk in audio_chunks:
            if chunk.status == AudioChunkStatus.COMPLETED and chunk.wav_path:
                chunk.status = AudioChunkStatus.POST_PROCESSING
                
                processed_path = self._temp_dir / f"chunk_{chunk.index:04d}.processed.wav"
                try:
                    result_path = self.audio_processor.process(chunk.wav_path, processed_path)
                    chunk.processed_path = result_path
                    chunk.status = AudioChunkStatus.COMPLETED
                    
                    # Обновляем информацию
                    if result_path.exists():
                        info = self.audio_utils.get_wav_info(result_path)
                        if info:
                            chunk.duration_seconds = info[2]
                            chunk.file_size = result_path.stat().st_size
                            
                except Exception as e:
                    self.debug.log_error(f"Ошибка постобработки чанка {chunk.index}", e)
                    chunk.processed_path = chunk.wav_path
                    chunk.status = AudioChunkStatus.COMPLETED
        
        return audio_chunks
    
    @debug_trace
    def combine_chunks(self, audio_chunks: List[AudioChunk], output_path: Path) -> Optional[Path]:
        """Объединяет чанки с микро-фейдами для бесшовной склейки"""
        ready_chunks = [c for c in audio_chunks if c.is_ready]

        if not ready_chunks:
            self.debug.log_error("Нет готовых чанков для объединения")
            return None

        ready_chunks.sort(key=lambda c: c.index)
        wav_files = [c.processed_path or c.wav_path for c in ready_chunks]

        self.debug.log(f"Объединение {len(wav_files)} чанков с фейдами...", level='INFO')

        temp_combined = self._temp_dir / f"{output_path.stem}.combined.wav"

        # PERF FIX: старая версия держала ВСЮ книгу в RAM через
        # AudioSegment += (квадратичное копирование, ~10 ГБ на час аудио).
        # Теперь: микро-фейды применяются к каждому чанку отдельно (ffmpeg,
        # потоково), затем concat demuxer с -c copy — O(1) по памяти.
        import subprocess

        fade_sec = 0.01
        faded_files = []

        for i, wav_file in enumerate(wav_files):
            faded_path = self._temp_dir / f"chunk_{i:04d}.faded.wav"
            info = self.audio_utils.get_wav_info(wav_file)
            duration = info[2] if info else 0.0
            fade_out_start = max(duration - fade_sec, 0)

            cmd = [
                "ffmpeg", "-i", str(wav_file),
                "-af", f"afade=t=in:d={fade_sec},afade=t=out:st={fade_out_start}:d={fade_sec}",
                "-y", str(faded_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                faded_files.append(faded_path)
            except Exception as e:
                self.debug.log_warning(f"Фейд чанка {i} не применён ({e}), беру исходный")
                faded_files.append(wav_file)

        if self.audio_utils.concat_wav_files(faded_files, temp_combined):
            self.debug.log(f"✅ Чанки объединены с фейдами: {temp_combined}", level='INFO')
            info = self.audio_utils.get_wav_info(temp_combined)
            if info:
                self.audio_book.final_duration_seconds = info[2]
            return temp_combined

        self.debug.log_error("Не удалось объединить чанки")
        return None
    
    @debug_trace
    def convert_to_format(self, input_path: Path, output_path: Path,
                          audio_format: AudioFormat) -> Optional[Path]:
        """
        Конвертирует аудио в указанный формат.
        """
        bitrate = self.context.get_effective_bitrate()
        sample_rate = self.context.get_effective_sample_rate()
        
        output_path = output_path.with_suffix('')
        
        if self.audio_utils.convert_audio(input_path, output_path, audio_format, bitrate, sample_rate):
            final_path = output_path.with_suffix(f'.{self.audio_utils.FFMPEG_PRESETS[audio_format]["container"]}')
            self.context.final_output = final_path
            self.audio_book.output_path = final_path
            self.audio_book.total_file_size = final_path.stat().st_size
            
            return final_path
        
        return None
    
    @debug_trace
    def generate_full(self, ssml_chunks: List[SSMLChunk]) -> Optional[Path]:
        """
        Полный цикл: генерация -> постобработка -> объединение -> конвертация.
        """
        # 1. Генерация
        audio_chunks = self.generate_from_ssml(ssml_chunks)
        
        # Проверяем, что есть готовые чанки
        ready_count = sum(1 for c in audio_chunks if c.is_ready)
        if ready_count == 0:
            raise TTSGenerationError("Ни один чанк не был сгенерирован")
        
        self.debug.log(f"Сгенерировано {ready_count}/{len(audio_chunks)} чанков", level='INFO')
        
        # 2. Определяем выходной путь
        output_path = self.context.output_path
        if not output_path:
            output_path = Path("audio") / f"{self.context.input_path.stem}.m4a"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 3. Объединение (если больше одного чанка)
        if len(audio_chunks) > 1:
            combined = self.combine_chunks(audio_chunks, output_path)
        else:
            combined = audio_chunks[0].processed_path or audio_chunks[0].wav_path
        
        if not combined:
            raise AudioProcessingError("Не удалось объединить чанки")
        
        # 4. Конвертация
        if self.context.options.no_convert:
            final_path = output_path.with_suffix('.wav')
            shutil.copy2(str(combined), str(final_path))
            self.context.final_output = final_path
        else:
            audio_format = self.context.options.output_format
            
            if self.context.options.output_formats:
                final_path = None
                for fmt in self.context.options.output_formats:
                    fmt_path = self.convert_to_format(combined, output_path, fmt)
                    if fmt_path and not final_path:
                        final_path = fmt_path
            else:
                final_path = self.convert_to_format(combined, output_path, audio_format)

        # 5. Сохранение метаданных
        if final_path and final_path.exists():
            self._save_metadata(final_path)

        # 6. Очистка временных файлов
        if not self.context.is_debug_mode():
            self._cleanup_all_temp_files(audio_chunks, combined)
        else:
            self.debug.log(f"🐛 Режим отладки: временные файлы сохранены в {self._temp_dir}", level='INFO')
        
        return final_path

    def _save_metadata(self, audio_path: Path):
        """Сохраняет метаданные о генерации в аудиофайл"""

        # Собираем использованный конфиг
        config_snapshot = {
            'tts_voice': self.context.get_effective_voice(),
            'tts_sample_rate': self.context.get_effective_sample_rate(),
            'audio_deesser': self.audio_processor.options.enable_deesser,
            'audio_deesser_threshold': self.audio_processor.options.deesser_threshold,
            'audio_spectral_nr': self.audio_processor.options.enable_spectral_nr,
            'audio_spectral_nr_amount': self.audio_processor.options.spectral_nr_amount,
            'audio_lowpass': self.audio_processor.options.enable_lowpass,
            'audio_lowpass_cutoff': self.audio_processor.options.lowpass_cutoff,
            'audio_normalization': self.audio_processor.options.enable_normalization,
            'audio_target_volume': f"{self.audio_processor.options.target_volume} LUFS",
            'genre': self.context.get_effective_genre(),
            'chunk_size': self.context.get_effective_chunk_size(),
            'workers': self.context.get_effective_workers(),
        }

        # Добавляем информацию о книге
        if 'book' in self.context.metadata:
            book = self.context.metadata['book']
            config_snapshot['book_title'] = book.get('title', 'Unknown')
            config_snapshot['book_words'] = str(book.get('total_words', 0))

        # Добавляем статистику
        config_snapshot['crabook_version'] = '8.0'
        config_snapshot['generation_date'] = __import__('datetime').datetime.now().isoformat()
        config_snapshot['total_duration'] = self.audio_book.total_duration_formatted

        # Формируем метаданные
        metadata = {
            'title': self.context.metadata.get('book', {}).get('title', self.context.input_path.stem),
            'artist': 'CrABook TTS',
            'album': 'Audiobook',
            'genre': self.context.get_effective_genre(),
            'comment': f"Generated by CrABook v8.0 | Voice: {config_snapshot['tts_voice']} | "
                    f"De-esser: {config_snapshot['audio_deesser']} | "
                    f"NR: {config_snapshot['audio_spectral_nr']} | "
                    f"Volume: {config_snapshot['audio_target_volume']}",
        }

        # Записываем
        self.audio_utils.write_metadata(audio_path, metadata)
        self.debug.log(f"📝 Метаданные сохранены в аудиофайл", level='INFO')

    def _cleanup_all_temp_files(self, audio_chunks: List[AudioChunk] = None, combined_wav: Path = None):
        """Очищает ВСЕ временные файлы после успешной генерации"""
        cleaned = 0
        
        # 1. Удаляем чанки
        if audio_chunks:
            for chunk in audio_chunks:
                if chunk.wav_path and chunk.wav_path.exists():
                    chunk.wav_path.unlink()
                    cleaned += 1
                if chunk.processed_path and chunk.processed_path.exists():
                    chunk.processed_path.unlink()
                    cleaned += 1
        
        # 2. Удаляем объединённый WAV (если он во временной папке)
        if combined_wav and combined_wav.exists():
            # Проверяем, что файл в /tmp/, а не в audio/
            if 'tmp' in str(combined_wav) or 'audiobook_' in str(combined_wav):
                combined_wav.unlink()
                cleaned += 1
                self.debug.log(f"🗑️ Удалён объединённый WAV: {combined_wav.name}", level='VERBOSE')
        
        # 3. Удаляем всю временную директорию
        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                self.debug.log(f"🗑️ Удалена временная директория: {self._temp_dir}", level='VERBOSE')
            except Exception as e:
                self.debug.log_warning(f"Не удалось удалить временную директорию: {e}")
        
        self.debug.log(f"🗑️ Всего очищено: {cleaned} файлов", level='INFO')
    
    def get_progress(self) -> dict:
        """Возвращает прогресс генерации"""
        total = len(self.audio_book.chunks)
        completed = self.audio_book.completed_chunks
        failed = self.audio_book.failed_chunks
        
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'percentage': (completed / total * 100) if total > 0 else 0
        }
