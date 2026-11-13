#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Утилиты именования файлов для построчного режима."""

import re


def translit_slug(text: str, max_len: int = 80) -> str:
    """Транслит строки в безопасное имя файла.

    Кириллица -> латиница (transliterate), нижний регистр, пробелы -> '_',
    только [a-z0-9_], без повторов '_', обрезка до max_len.
    Пустой результат -> '' (вызывающий код подставит индекс).
    """
    try:
        from transliterate import translit
    except ImportError as e:
        raise ImportError(
            "Для --per-line нужна библиотека transliterate: uv add transliterate"
        ) from e

    latin = translit(text, "ru", reversed=True).lower()
    latin = re.sub(r"\s+", "_", latin.strip())
    latin = re.sub(r"[^a-z0-9_]", "", latin)
    latin = re.sub(r"_+", "_", latin).strip("_")
    if len(latin) > max_len:
        latin = latin[:max_len].rstrip("_")
    return latin
