#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Утилиты для работы с файлами
"""

from pathlib import Path
from typing import List

from core.debug_core import get_debugger, debug_trace
from core.dependency_manager import get_dependency_manager


class FileUtils:
    """Утилиты для работы с файлами разных форматов"""

    def __init__(self):
        self.debug = get_debugger()
        self.deps = get_dependency_manager()

    @debug_trace
    def detect_encoding(self, file_path: Path) -> str:
        """Определяет кодировку файла"""
        if self.deps.is_available("chardet"):
            with open(file_path, "rb") as f:
                result = self.deps.chardet.detect(f.read(100000))
                encoding = result.get("encoding", "utf-8")
                self.debug.log(f"Определена кодировка: {encoding}", level="VERBOSE")
                return encoding
        return "utf-8"

    @debug_trace
    def read_text_file(self, file_path: Path) -> str:
        """Читает текстовый файл с автоопределением кодировки"""
        encoding = self.detect_encoding(file_path)
        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            content = f.read()
        self.debug.log_file_operation("read", str(file_path), len(content), True)
        return content

    @debug_trace
    def read_docx(self, file_path: Path) -> str:
        """Читает DOCX файл"""
        if not self.deps.is_available("docx"):
            raise ImportError("python-docx не установлен")

        doc = self.deps.docx.Document(str(file_path))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        content = "\n".join(paragraphs)
        self.debug.log_file_operation("read_docx", str(file_path), len(content), True)
        return content

    @debug_trace
    def read_fb2(self, file_path: Path) -> str:
        """Читает FB2 файл"""
        if not self.deps.is_available("bs4"):
            raise ImportError("beautifulsoup4 не установлен")

        with open(file_path, "rb") as f:
            soup = self.deps.bs4.BeautifulSoup(f.read(), "xml")
            paragraphs = [
                p.get_text() for p in soup.find_all("p") if p.get_text().strip()
            ]
            content = "\n".join(paragraphs)
        self.debug.log_file_operation("read_fb2", str(file_path), len(content), True)
        return content

    @debug_trace
    def read_epub(self, file_path: Path) -> str:
        """Читает EPUB файл"""
        if not (self.deps.is_available("ebooklib") and self.deps.is_available("bs4")):
            raise ImportError("ebooklib и beautifulsoup4 не установлены")

        book = self.deps.ebooklib.epub.read_epub(str(file_path))
        texts = []
        for item in book.get_items_of_type(self.deps.ebooklib.ITEM_DOCUMENT):
            soup = self.deps.bs4.BeautifulSoup(item.get_content(), "html.parser")
            texts.append(soup.get_text())
        content = "\n".join(texts)
        self.debug.log_file_operation("read_epub", str(file_path), len(content), True)
        return content

    @debug_trace
    def read_pdf(self, file_path: Path) -> str:
        """Читает PDF файл"""
        content = ""

        if self.deps.is_available("pdfplumber"):
            import pdfplumber

            with pdfplumber.open(str(file_path)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
                content = "\n".join(pages)
        elif self.deps.is_available("fitz"):
            doc = self.deps.fitz.open(str(file_path))
            pages = [page.get_text() for page in doc]
            content = "\n".join(pages)
            doc.close()
        else:
            raise ImportError("pdfplumber или PyMuPDF не установлены")

        self.debug.log_file_operation("read_pdf", str(file_path), len(content), True)
        return content

    @debug_trace
    def extract_text(self, file_path: Path) -> str:
        """
        Извлекает текст из файла любого поддерживаемого формата.
        Автоматически определяет формат по расширению.
        """
        ext = file_path.suffix.lower()

        self.debug.log(f"Извлечение текста из: {file_path}", level="INFO")

        if ext == ".txt":
            return self.read_text_file(file_path)
        elif ext == ".docx":
            return self.read_docx(file_path)
        elif ext == ".fb2":
            return self.read_fb2(file_path)
        elif ext == ".epub":
            return self.read_epub(file_path)
        elif ext == ".pdf":
            return self.read_pdf(file_path)
        else:
            raise ValueError(f"Неподдерживаемый формат: {ext}")

    @debug_trace
    def write_file(self, file_path: Path, content: str, encoding: str = "utf-8"):
        """Записывает содержимое в файл"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        self.debug.log_file_operation("write", str(file_path), len(content), True)

    @debug_trace
    def find_files(self, directory: Path, extensions: List[str]) -> List[Path]:
        """Ищет файлы с указанными расширениями в директории"""
        files = []
        for ext in extensions:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            files.extend(directory.glob(pattern))
            files.extend(directory.glob(pattern.upper()))
        return [f for f in files if f.is_file()]

    def ensure_dir(self, path: Path) -> Path:
        """Создаёт директорию, если её нет"""
        path.mkdir(parents=True, exist_ok=True)
        return path
