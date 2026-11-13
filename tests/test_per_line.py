"""Тесты построчного режима: транслит-имена файлов."""
from utils.naming import translit_slug


def test_translit_basic():
    assert translit_slug("Привет мир") == "privet_mir"


def test_translit_lower_underscore():
    assert translit_slug("  Это   Тест  ") == "eto_test"


def test_translit_punct_removed():
    assert translit_slug("Привет, мир!") == "privet_mir"


def test_translit_empty():
    assert translit_slug("!!!") == ""


def test_translit_long():
    assert len(translit_slug("очень " * 50, max_len=20)) <= 20
