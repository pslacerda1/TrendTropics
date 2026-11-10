import logging
from textwrap import shorten

import polars as pl
import typer
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from .commons import BR_INFOEDUC_STOP_WORDS, WORD_FREQS_PARQUET
from .scraper import Acta, extract_acta_from_url
from .topics import extract_word_freq_records
from .webapp import dask_app

ACTA_LIST= [
    Acta('SBIE', 2026, "https://sol.sbc.org.br/index.php/sbie/issue/view/1743"),
    Acta('SBIE', 2025, "https://sol.sbc.org.br/index.php/sbie/issue/view/1599"),
    Acta('SBIE', 2024, "https://sol.sbc.org.br/index.php/sbie/issue/view/1387"),
    Acta('SBIE', 2023, "https://sol.sbc.org.br/index.php/sbie/issue/view/1194"),
    Acta('SBIE', 2022, "https://sol.sbc.org.br/index.php/sbie/issue/view/1013"),
    Acta('SBIE', 2021, "https://sol.sbc.org.br/index.php/sbie/issue/view/847"),
    Acta('SBIE', 2020, "https://sol.sbc.org.br/index.php/sbie/issue/view/658"),

    Acta('SBIE', 2013, "https://sol.sbc.org.br/index.php/sbie/issue/view/1738"),
]


typer_app = typer.Typer(no_args_is_help=True)

@typer_app.command()
def download_papers(force_extraction: bool = False):
    for acta in ACTA_LIST:
        for paper in extract_acta_from_url(acta):
            print(paper.pdf_path.stem, paper.doi_url, shorten(paper.title, 100))
            if force_extraction:
                try:
                    assert paper.get_text()
                except Exception as exc:
                    logger.error(f'Failed to extract text contents: {exc!s}', exc_info=False)


@typer_app.command()
def extract_topics():
    
    logger.info("Starting to extract papers.")
    paper_list = []
    for acta in ACTA_LIST:
        paper_list.extend(extract_acta_from_url(acta))

    logger.info('Starting to analyze word frequencies.')
    topics = []
    wf_vocab = extract_word_freq_records(
        paper_list=paper_list,
        exclude_words=BR_INFOEDUC_STOP_WORDS
    )
    for wf in wf_vocab:
        topics.append({
            'acta_abbr': wf.paper.acta.abbr,
            'acta_year': wf.paper.acta.year,
            'paper_doi': wf.paper.doi_url,
            'paper_pdf': str(wf.paper.pdf_path),
            'word': wf.word,
            'freq': wf.freq,
        })
    
    df = pl.DataFrame(topics, schema={
        'acta_abbr': str,
        'acta_year': int,
        'paper_doi': str,
        'paper_pdf': str,
        'word': str,
        'freq': float,
    })
    df.write_parquet(WORD_FREQS_PARQUET)
    logger.info(f"Written parquet file '{WORD_FREQS_PARQUET!s}'.")


@typer_app.command()
def webapp():
    dask_app.run(debug=True)

if __name__ == "__main__":
    typer_app()