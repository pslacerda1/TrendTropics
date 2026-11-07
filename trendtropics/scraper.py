import re
import unicodedata
from dataclasses import dataclass, field
from functools import cached_property
from hashlib import sha256
from logging import getLogger
from pathlib import Path
from textwrap import dedent
from urllib.parse import parse_qs, urlparse

import lxml.html
import requests_cache
from requests import Session
import textract


logger = getLogger(__name__)


requests_cache.install_cache(
    'requests-cache',
    backend='sqlite', 
    expire_after=86400*30*365, # muito tempo
    allowable_methods=('GET'),
    allowable_codes=[200],
)


DOWNLOADS_PATH = Path(__file__).parent.parent / "downloads"
DOWNLOADS_PATH.mkdir(exist_ok=True, parents=True)


RE_REFERENCES = re.compile(
    r'(\n(\d+?\.?\s+)?(Referências|Referências Bibliográficas|Bibliografia))'
)
RE_REMOVE = [
    r'XV Congresso Brasileiro de Informática na Educação \(CBIE 2026\)\n',
    r'Anais do XXXVII Simpósio Brasileiro de Informática na Educação \(SBIE 2026\)\n',
    r'DOI: 10.5753/sbie.2026.\d+'
]


@dataclass(frozen=True)
class Paper:

    doi_url: str
    title: str
    abstract: str = field(repr=False)
    pdf_path: Path = field(repr=False)

    @cached_property
    def cleaned_text(self) -> str:
        all_pages: list[str] = []
        doc: str = textract.process(self.pdf_path).decode()
        doc = unicodedata.normalize("NFC", doc)
        refs_found = False
        for ix, page in enumerate(doc.split("\n\n\x0c")):
            
            # Pula a primeira página.
            if ix == 0:
                continue

            # Para a extração se já atingiu as referências.
            if refs_found:
                break
            
            # Extrai o texto da página e remove o cabeçalho e rodapé do congresso, se presente.
            for regex in RE_REMOVE:
                page = re.sub(regex, "", page)
            page = page.strip()

            # Detecta o início das referências e remove o texto a partir desse ponto.
            # Para a extração se já atingiu as referências.
            matches = list(RE_REFERENCES.finditer(page, re.IGNORECASE))
            for match in reversed(matches):
                refs_start = match.start()
                break
            else:
                refs_start = -1

            if refs_start != -1:
                page = page[:refs_start]
                refs_found = True
                
            # Salva a página.
            page = page.strip()
            all_pages.append(page)

        if not refs_found:
            raise Exception("Failed to detect references in the PDF.")

        return "\n".join(all_pages)


def extract_paper_from_url(session: Session, url: str) -> Paper:
    """
    Download a paper from its URL.

    Args:
        session: The session to use for the request.
        url: The URL of the paper.
    """
    try:
        resp = session.get(url)
        html_content = resp.content.decode()
        doc = lxml.html.fromstring(html_content)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download and parse the HTML for the paper at {url}."
        ) from exc

    try:
        doi: str = doc.xpath('//div[contains(@class, "doi")]//a/text()')[0].strip()
        abstract: str = ' '.join(doc.xpath('//div[contains(@class, "abstract")]')[0].itertext()).strip()
        if abstract.startswith("Resumo"):
            abstract = abstract[len("Resumo"):].strip()
        title: str = doc.xpath('//h1[@class="page_title"]/text()')[0].strip()
        pdf_url: str = doc.xpath('//a[@class="obj_galley_link pdf"]/@href')[0].strip()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to extract DOI and abstract from the paper at {url}."
        ) from exc
    
    try:
        resp = session.get(pdf_url)
        html_content = resp.content.decode()
        doc = lxml.html.fromstring(html_content)
        pdf_viewer_url = doc.xpath('//iframe/@src')[0].strip()
        pdf_url = parse_qs(urlparse(pdf_viewer_url).query)['file'][0]
    except Exception as exc:
        raise RuntimeError(
            f"Failed to extract the PDF URL from the paper at {url}."
        ) from exc
    
    pdf_sha = sha256(doi.encode("utf-8")).hexdigest()
    pdf_path = DOWNLOADS_PATH / f"{pdf_sha}.pdf"
    
    try:
        resp = session.get(pdf_url)
        with open(pdf_path, "wb") as f:
            f.write(resp.content)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download the PDF for the paper at {url}."
        ) from exc

    return Paper(doi_url=doi, title=title, abstract=abstract, pdf_path=pdf_path)


def extract_acta_from_url(
    session: Session,
    url: str,
    max_papers: int | None = None
) -> list[Paper]:
    """
    Extract all papers from an acta URL.

    Args:
        session: The session to use for the request.
        url: The URL of the acta.
    """
    try:
        resp = session.get(url)
        html_content = resp.content.decode()
        doc = lxml.html.fromstring(html_content)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download and parse the HTML for the acta at {url}."
        ) from exc

    paper_ls = []
    try:
        paper_items = doc.xpath('//div[@class="obj_article_summary"]')
        for pi in paper_items:
            # Limita o número de artigos extraídos, se especificado.
            if max_papers and max_papers == len(paper_ls):
                break
            
            # Extrai o URL do artigo.
            paper_url = pi.xpath('./div[@class="title"]/a/@href')[0].strip()

            # Extrai texto do botão de download do PDF para verificar se é um artigo em português.
            url_button_text = pi.cssselect('.obj_galley_link.pdf')[0].text.strip()
            if 'PDF' != url_button_text:
                # Ignora artigos em outros idiomas.
                continue
            try:
                paper = extract_paper_from_url(session, paper_url)
                paper_ls.append(paper)
            except Exception as exc:
                logger.exception("Failed to extract paper.", exc_info=exc)
                continue
            
    except Exception as exc:
        raise RuntimeError(
            f"Failed to extract paper URLs from the acta at {url}."
        ) from exc

    return paper_ls