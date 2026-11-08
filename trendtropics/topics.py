from pathlib import Path

from sklearn.feature_extraction.text import CountVectorizer


BR_INFOEDUC_STOP_WORDS = (
    Path(__file__).parent / 'br_infoeduc_stopwords.txt'
).read_text().splitlines()


def find_most_frequent_words(
    docs: list[str],
    ngram_range: tuple[int, int] = (1, 1)
) -> list[tuple[str, int]]:
    vectorizer = CountVectorizer(
        stop_words=BR_INFOEDUC_STOP_WORDS,
        ngram_range=ngram_range
    )
    X = vectorizer.fit_transform(docs)

    frequencies = X.sum(axis=0).A1
    words: list[str] = vectorizer.get_feature_names_out()

    most_frequent = sorted(
        zip(words, map(int, frequencies)),
        key=lambda item: item[1],
        reverse=True,
    )
    return most_frequent
