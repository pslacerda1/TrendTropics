import logging
from pprint import pp
from textwrap import shorten

import typer
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from .scraper import extract_acta_from_url
from .topics import find_most_frequent_words


ACTAS = [
    (2026, "https://sol.sbc.org.br/index.php/sbie/issue/view/1743"),
    (2025, "https://sol.sbc.org.br/index.php/sbie/issue/view/1599"),
    (2024, "https://sol.sbc.org.br/index.php/sbie/issue/view/1387"),
]


app = typer.Typer(no_args_is_help=True)

@app.command()
def scrap():
    for year, acta_url in ACTAS:
        for paper in extract_acta_from_url(acta_url):
            print(paper.pdf_path.stem, paper.doi_url, year, shorten(paper.title, 100))
            try:
                assert paper.get_text()
            except Exception as exc:
                logger.exception(exc)


@app.command()
def topics():
    docs: list[str]  = []
    for _, acta_url in ACTAS:
        for paper in extract_acta_from_url(acta_url):
            try:
                docs.append(paper.get_text())
            except Exception as exc:
                logger.exception(exc)

    top_words = find_most_frequent_words(docs)
    pp(top_words[:50])

if __name__ == "__main__":
    app()