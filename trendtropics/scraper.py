import re
import unicodedata
from collections.abc import Generator
from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
from logging import getLogger
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import lxml.html
import requests_cache
import textract
from platformdirs import user_cache_dir
from requests import Session


class ScraperError(Exception):
    pass


logger = getLogger(__name__)


CACHE_DIR = Path(
    user_cache_dir("TrendTropics", ensure_exists=True)
)

REQUESTS_CACHE = CACHE_DIR / 'http_cache.sqlite'
DOWNLOADS_PATH = CACHE_DIR / "downloads"

logger.info(f"Cache directory at '{CACHE_DIR}'.")

REQUESTS_CACHE = CACHE_DIR / 'http_cache.sqlite'
DOWNLOADS_PATH.mkdir(exist_ok=True, parents=True)

#
# Se encontrar qualquer seção destas, o documento será truncado.
#
RE_TRUNCATE_SECTIONS_LIST = [
    re.compile(r'^((\d\.?)?\s*)?\s*' + expr + r'\s*$', re.IGNORECASE | re.MULTILINE)
    for expr in [
        'Declaração sobre uso de Inteligência Artificial',
        'Declaração sobre o uso de Inteligência Artificial',
        'Agradecimentos',
        'Referências',
        'Referências Bibliográficas',
        'Referenciais',
        'References',
        'Referencias'
    ]
]


#
# Se encontrar qualquer string destas, esta será apagada.
#
STRIP_LIST = [
    # SBIE 2026
    'XV Congresso Brasileiro de Informática na Educação (CBIE 2026)',
    'Anais do XXXVII Simpósio Brasileiro de Informática na Educação (SBIE 2026)',
    # SBIE 2025
    'XIV Congresso Brasileiro de Informática na Educação (CBIE 2025)',
    'Anais do XXXVI Simpósio Brasileiro de Informática na Educação (SBIE 2025)',
    # SBIE 2024
    'XIII Congresso Brasileiro de Informática na Educação (CBIE 2024)',
    'XXXV Simpósio Brasileiro de Informática na Educação (SBIE 2024)',
]


def new_requests_session() -> Session:
    try:
        return requests_cache.CachedSession(
            REQUESTS_CACHE,
            backend="sqlite",
            expire_after=86400 * 30 * 12,  # 1 ano
            allowable_methods=("GET",),
            allowable_codes=(200,),
        )
    except Exception as exc:
        raise ScraperError("Failed to create he requests session object.") from exc


@dataclass(frozen=True)
class Paper:

    doi_url: str
    title: str
    abstract: str = field(repr=False)
    pdf_path: Path = field(repr=False)

    # O lru_cache funciona porque Paper é frozen.
    @lru_cache(1)  # noqa: B019
    def get_text(self) -> str:
        all_pages: list[str] = []
        doc: str = textract.process(self.pdf_path).decode()
        doc = unicodedata.normalize("NFC", doc)
        
        stop = False
        for ix, page in enumerate(doc.split("\n\n\x0c")):
            
            # Pula a primeira página.
            if ix == 0:
                continue

            # Para a extração.
            if stop:
                break
            
            # Remove cabeçalho e rodapé do congresso, se presentes.
            len_before = len(page)
            for replace in STRIP_LIST:
                page = page.replace(replace, "").strip()
            len_after = len(page)
            if len_before == len_after:
                logger.warning(f"Failed to crop header and footer from PDF file '{str(self.doi_url)}' at page {ix}.")

            # Detecta o início da primeira seção que será truncada, se houver
            truncate_start = None
            for truncate_pattern in RE_TRUNCATE_SECTIONS_LIST:
                try:
                    match = next(truncate_pattern.finditer(page))
                except StopIteration:
                    continue
                if truncate_start is None:
                    truncate_start = match.start()
                elif truncate_start > match.start():
                    truncate_start = match.start()

            # Trunca a página.
            if truncate_start is not None:
                page = page[:truncate_start]
                stop = True

            # Salva a página.
            page = page.strip()
            all_pages.append(page)

        if not stop:
            raise ScraperError(f"Failed to detect references from the PDF at '{str(self.doi_url)}'.")

        return "\n".join(all_pages)


def extract_paper_from_url(url: str) -> Paper:
    """
    Download a paper from its URL.

    Args:
        url: The URL of the paper.
    """

    session = new_requests_session()

    try:
        resp = session.get(url)
        html_content = resp.content.decode()
        doc = lxml.html.fromstring(html_content)
    except Exception as exc:
        raise ScraperError(
            f"Failed to download and parse the HTML for the paper at '{url}'."
        ) from exc

    try:
        doi: str = doc.xpath('//div[contains(@class, "doi")]//a/text()')[0].strip()
        abstract: str = ' '.join(doc.xpath('//div[contains(@class, "abstract")]')[0].itertext()).strip()
        if abstract.startswith("Resumo"):
            abstract = abstract[len("Resumo"):].strip()
        title: str = doc.xpath('//h1[@class="page_title"]/text()')[0].strip()
        pdf_url: str = doc.xpath('//a[@class="obj_galley_link pdf"]/@href')[0].strip()
    except Exception as exc:
        raise ScraperError(
            f"Failed to extract DOI and abstract from the paper at '{url}'."
        ) from exc
    
    try:
        resp = session.get(pdf_url)
        html_content = resp.content.decode()
        doc = lxml.html.fromstring(html_content)
        pdf_viewer_url = doc.xpath('//iframe/@src')[0].strip()
        pdf_url = parse_qs(urlparse(pdf_viewer_url).query)['file'][0]
    except Exception as exc:
        raise ScraperError(
            f"Failed to extract the PDF URL from the paper at '{url}'."
        ) from exc
    
    pdf_sha = sha256(doi.encode("utf-8")).hexdigest()
    pdf_path = DOWNLOADS_PATH / f"{pdf_sha}.pdf"
    
    try:
        resp = session.get(pdf_url)
        with open(pdf_path, "wb") as f:
            f.write(resp.content)
    except Exception as exc:
        raise ScraperError(
            f"Failed to download the PDF for the paper at '{url}'."
        ) from exc

    return Paper(doi_url=doi, title=title, abstract=abstract, pdf_path=pdf_path)


def extract_acta_from_url(
    url: str,
    max_papers: int | None = None
) -> Generator[Paper]:
    """
    Extract all papers from an acta URL.

    Args:
        url: The URL of the acta.
    """
    
    session: Session = new_requests_session()
    
    try:
        resp = session.get(url)
        html_content = resp.content.decode()
        doc = lxml.html.fromstring(html_content)
    except Exception as exc:
        raise ScraperError(
            f"Failed to download and parse the HTML for the acta at '{url}'."
        ) from exc
    
    try:
        max_count = 0
        paper_items = doc.xpath('//div[@class="obj_article_summary"]')
        for ix, pi in enumerate(paper_items):

            # Pula o editorial.
            if ix == 0:
                continue
            
            # Extrai o URL do artigo.
            paper_url = pi.xpath('./div[@class="title"]/a/@href')[0].strip()

            # Extrai texto do botão de download do PDF para verificar se é um artigo em português.
            url_button_text = pi.cssselect('.obj_galley_link.pdf')[0].text.strip()
            if 'PDF' != url_button_text:
                # Ignora artigos em outros idiomas.
                ix -= 1
                continue
            try:
                yield extract_paper_from_url(paper_url)
            except Exception as exc:
                logger.error("Failed to extract paper.", exc_info=exc)
                continue
            
            # Limita o número de artigos extraídos, se especificado.
            max_count += 1
            if max_papers and max_papers == max_count:
                break
        
    except Exception as exc:
        raise ScraperError(
            f"Failed to extract paper URLs from the acta at '{url}'."
        ) from exc
