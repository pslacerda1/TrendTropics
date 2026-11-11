import re
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from logging import getLogger
from math import log10

import polars as pl

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
    extract_unigrams=True,
    extract_bigrams=True,
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
        
        tokens: list[str] = []
        if extract_unigrams:
            tokens.extend(words)
        if extract_bigrams:
            tokens.extend(
                f"{w1} {w2}"
                for w1, w2 in
                pairwise(words)
            )

        counter = Counter(tokens).most_common()
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


def compute_top_topics(
    word_freqs: pl.DataFrame,
    acta_abbr: str,
    word_rank: tuple[int, int],
    extra_words: list[str],
    years_range: tuple[int, int],
) -> pl.DataFrame:
    # Número de artigos por ano
    article_counts = (
        word_freqs
        .filter(pl.col("acta_abbr") == acta_abbr)
        .select("paper_doi", "acta_year")
        .group_by("acta_year")
        .agg(n_articles=pl.len())
    )

    # Ranquear palavras da acta entre a posição 0 e 1 do word_ranking.
    top_words = (
        word_freqs
        .filter(pl.col("acta_abbr") == acta_abbr)
        .group_by("word")
        .agg(total_freq=pl.col("freq").sum())
        .sort("total_freq", descending=True)
        .with_columns(
            rank=pl.col("total_freq").rank(method="ordinal", descending=True)
        )
        .filter(
            pl.col("rank").is_between(word_rank[0], word_rank[1])
        )
        .get_column("word")
        .to_list()
    )
    top_words = [
        *top_words,
        *extra_words,
    ]

    # Média por ano, considerando artigos sem ocorrência como zero
    top_topics = (
        word_freqs
        .filter(
            (pl.col("acta_abbr") == acta_abbr)
            & pl.col("word").is_in(top_words)
            & pl.col("acta_year").is_between(years_range[0], years_range[1])
        )
        .group_by("acta_year", "word")
        .agg(total_freq=pl.col("freq").sum())
        .join(article_counts, on="acta_year")
        .with_columns(
            freq=pl.col("total_freq") / pl.col("n_articles")
        )
        .sort("acta_year")
    )
    return top_topics