from logging import getLogger
from pathlib import Path


BR_INFOEDUC_STOP_WORDS = (
    Path(__file__).parent / 'br_infoeduc_stopwords.txt'
).read_text().splitlines()


WORKDIR = Path(__file__).parent.parent / 'workdir'

REQUESTS_CACHE = WORKDIR / 'http_cache.sqlite'
WORD_FREQS_PARQUET = WORKDIR / 'word_freqs.parquet'

DOWNLOADS_PATH = WORKDIR / "downloads"
DOWNLOADS_PATH.mkdir(exist_ok=True, parents=True)

logger = getLogger(__name__)
logger.info(f"Work directory set at '{WORKDIR}'.")


class TrendTropicsException(Exception):
    pass
