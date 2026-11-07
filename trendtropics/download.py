from dataclasses import dataclass, field
import requests_cache
from requests import Session
from lxml import html


requests_cache.install_cache(
    'requests-cache',
    backend='sqlite', 
    expire_after=86400*30*365, # muito tempo
    allowable_methods=('GET'),
    allowable_codes=[200],
)


@dataclass(frozen=True)
class Paper:
    doi: str
    title: str
    abstract: str = field(repr=False)


def extract_paper_from_url(session: Session, url: str) -> Paper:
    """
    Download a paper from its URL.

    Args:
        session: The session to use for the request.
        url: The URL of the paper.
    """
    try:
        ret = session.get(url)
        html_content = ret.content.decode("utf-8")
        doc = html.fromstring(html_content)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download and parse the HTML for the paper at {url}."
        ) from exc

    try:
        doi: str = doc.xpath('//div[contains(@class, "doi")]//a/text()')[0].strip()
        abstract: str = ' '.join(doc.xpath('//div[contains(@class, "abstract")]/text()')).strip()
        title: str = doc.xpath('//h1[@class="page_title"]/text()')[0].strip()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to extract DOI and abstract from the paper at {url}."
        ) from exc

    return Paper(doi=doi, title=title, abstract=abstract)

print(extract_paper_from_url(Session(), "https://doi.org/10.5753/sbie.2026.28387"))

