import re
from collections import Counter
from dataclasses import dataclass
from logging import getLogger

from math import log10

from .commons import TrendTropicsException
from .scraper import Paper

logger = getLogger(__name__)


class TopicsException(TrendTropicsException):
    pass


@dataclass
class WordFreqRecord:
    paper: Paper
    word: str
    freq: float


def extract_word_freq_records(
    paper_list: list[Paper],
    include_words: list[str] | None = None,
    exclude_words: list[str] | None = None,
) -> list[WordFreqRecord]:

    if include_words and exclude_words:
        raise TopicsException(
            "Cannot set include_words and exclude_words at the same time."
        )
    
    topics = []
    for paper in paper_list:
        try:
            words = paper.get_text().split()
        except Exception as exc:
            logger.error(f"Failed to extract the PDF '{paper.pdf_path!s}': {exc!s}")
            continue

        counter = Counter(words).most_common()
        counter = [
            (w, f)
            for w, f in counter
            if len(w) > 1 and not re.match(r'\d', w)
        ]
        if exclude_words:
            counter = [
                (w, f)
                for w, f in counter
                if w.lower() not in exclude_words
            ]
        if include_words:
            counter = [
                (w, f)
                for w, f in counter
                if w in include_words
            ]
        counter = [
            (w, log10(f) / len(words))
            for w, f in counter
        ]
        for word, freq in counter:
            topics.append(WordFreqRecord(
                paper=paper,
                word=word,
                freq=freq,
            ))
    return topics