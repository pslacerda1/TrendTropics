from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests_cache
from requests import Session
import lxml.html


requests_cache.install_cache(
    'requests-cache',
    backend='sqlite', 
    expire_after=86400*30*365, # muito tempo
    allowable_methods=('GET'),
    allowable_codes=[200],
)


DOWNLOADS_PATH = Path(__file__).parent.parent / "downloads"
DOWNLOADS_PATH.mkdir(exist_ok=True, parents=True)


@dataclass(frozen=True)
class Paper:
    doi_url: str
    title: str
    abstract: str = field(repr=False)
    pdf_path: Path = field(repr=False)


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
        abstract: str = ' '.join(doc.xpath('//div[contains(@class, "abstract")]/text()')).strip()
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
