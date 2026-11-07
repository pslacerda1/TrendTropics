from requests import Session

from trendtropics.download import Paper, extract_paper_from_url


def test_extract_paper_from_url():
    doi_url = "https://doi.org/10.5753/sbie.2026.28387"
    paper = extract_paper_from_url(Session(), doi_url)
    
    assert isinstance(paper, Paper)
    assert paper.doi == doi_url
    assert paper.title == "Uma Proposta de Sistema Tutor Inteligente para a Disciplina Cálculo Diferencial"
    
    assert paper.abstract.startswith("Disciplinas de Cálculo Diferencial impõem")
    assert 'Este artigo apresenta o Solve With Me' in paper.abstract
    assert paper.abstract.endswith("Espera-se que a ferramenta contribua para o aprimoramento do ensino de Cálculo e para a redução de evasão e reprovação.")