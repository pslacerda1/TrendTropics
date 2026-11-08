from hashlib import sha256
from trendtropics.scraper import Paper, extract_paper_from_url, extract_acta_from_url


def test_extract_paper_from_url_0():
    doi_url = "https://doi.org/10.5753/sbie.2026.28387"
    paper = extract_paper_from_url(doi_url)
    
    assert isinstance(paper, Paper)
    assert paper.doi_url == doi_url
    assert paper.title == "Uma Proposta de Sistema Tutor Inteligente para a Disciplina Cálculo Diferencial"
    
    assert paper.abstract.startswith("Disciplinas de Cálculo Diferencial impõem")
    assert 'Este artigo apresenta o Solve With Me' in paper.abstract
    assert paper.abstract.endswith("Espera-se que a ferramenta contribua para o aprimoramento do ensino de Cálculo e para a redução de evasão e reprovação.")

    assert paper.pdf_path.stem == "e642ca95c2f486fbff21002bc1c27555417e957959269c5992ddaa0f0fa27285"
    assert paper.pdf_path.stem == sha256(doi_url.encode()).hexdigest()
    assert paper.pdf_path.read_bytes()[:4] == b"%PDF"

    assert paper.get_text().startswith("Ao mesmo tempo")
    assert paper.get_text().endswith("disciplinas de Cálculo.")


def test_extract_paper_from_url_1():
    doi_url = "https://doi.org/10.5753/sbie.2026.26702"
    paper = extract_paper_from_url(doi_url)
    
    assert isinstance(paper, Paper)
    assert paper.doi_url == doi_url
    assert paper.title == "Evolução das atribuições do tutor na Educação a Distância (EaD): uma análise documental e comparativa entre decretos federais com ênfase no Decreto nº 12.456/2025"
    
    assert paper.abstract.startswith("A Educação a Distância (EaD")
    assert paper.abstract.endswith("regulamentação e à valorização profissional.")

    assert paper.pdf_path.stem == "e64dc67231b8544d4c60ad4c50de96a370a106001ecca09c216b644e74390671"
    assert paper.pdf_path.stem == sha256(doi_url.encode()).hexdigest()
    assert paper.pdf_path.read_bytes()[:4] == b"%PDF"

    assert paper.get_text().startswith("enquanto os tutores")
    assert paper.get_text().endswith("educação brasileira.")


def test_extract_acta_from_url():
    acta_url = "https://sol.sbc.org.br/index.php/sbie/issue/view/1743"
    paper_ls = list(extract_acta_from_url(acta_url, max_papers=5))
    
    assert all(isinstance(paper, Paper) for paper in paper_ls)
    assert [
        "https://doi.org/10.5753/sbie.2026.23539",
        "https://doi.org/10.5753/sbie.2026.25540",
        "https://doi.org/10.5753/sbie.2026.26409",
        "https://doi.org/10.5753/sbie.2026.26628",
        "https://doi.org/10.5753/sbie.2026.26702"
    ] == [paper.doi_url for paper in paper_ls]