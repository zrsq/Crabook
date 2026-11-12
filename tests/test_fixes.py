"""Регрессия на критические баги (без TTS-зависимостей)."""
import re

from lxml import etree

from utils.text_utils import TextUtils
from engines.ssml_builder import SSMLBuilder
from services.ssml_validation import SSMLFixer


def test_bug1_leading_text_kept():
    out = SSMLBuilder().build('Начало <prosody rate="90%">длинноеслово</prosody> конец.')
    assert "Начало" in out and "конец" in out


def test_bug3_sentence_boundary():
    assert TextUtils().split_sentences("Конец. Начало нового") == ["Конец.", "Начало нового"]


def test_bug3_initials_still_protected():
    s = TextUtils().split_sentences("Это А. С. Пушкин написал.")
    assert len(s) == 1


def test_bug2_tagged_split_keeps_tags():
    text = 'Он сказал <prosody rate="90%">приветствую</prosody> тебя. И ушёл.'
    sents = TextUtils().split_sentences_tagged(text)
    assert len(sents) == 2
    assert '<prosody rate="90%">приветствую</prosody>' in sents[0]


def test_bug4_fixer_produces_valid_xml():
    fixed, _ = SSMLFixer().fix('<speak><prosody rate="90%">текст</speak>')
    etree.fromstring(fixed.encode())  # не должно бросить


def test_bug12_nested_prosody_protected():
    text = '<prosody rate="slow">он сказал <prosody rate="90%">приветствую</prosody> громко</prosody>'
    assert SSMLBuilder._split_protected_blocks(text) == [text]


def test_bug13_year_no_trailing_space():
    assert re.findall(r"\b\d{1,3}(?: \d{3})+\b|\b\d{4,}\b", "В 1984 году") == ["1984"]
