import requests
import os
import time

# Constantes para a API do GitHub
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_TOKEN = os.getenv("GITHUB_TOKEN") # Obtenha do .env

class GitHubAPIError(Exception):
    """Exceção customizada para erros da API do GitHub."""
    pass

def _make_github_request(url, params=None, headers=None, page=1, per_page=100):
    """
    Função auxiliar genérica para fazer requisições à API do GitHub.
    Lida com autenticação, paginação e tratamento básico de erros/rate limits.
    """
    if headers is None:
        headers = {}
    if GITHUB_API_TOKEN:
        headers['Authorization'] = f"token {GITHUB_API_TOKEN}"
    headers['Accept'] = 'application/vnd.github.v3+json' # Recomendado pela API do GitHub

    if params is None:
        params = {}
    params['page'] = page
    params['per_page'] = per_page

    response = requests.get(url, headers=headers, params=params)

    # Lidar com Rate Limits (GitHub envia cabeçalhos X-RateLimit-*)
    if 'X-RateLimit-Remaining' in response.headers and int(response.headers['X-RateLimit-Remaining']) < 50:
        reset_time = int(response.headers['X-RateLimit-Reset'])
        sleep_duration = max(0, reset_time - time.time()) + 10 # Adiciona uma margem
        print(f"Baixo limite de taxa restante ({response.headers['X-RateLimit-Remaining']}). Dormindo por {sleep_duration} segundos.")
        time.sleep(sleep_duration)

    response.raise_for_status() # Levanta um HTTPError para 4xx/5xx responses

    return response.json()

def get_repo_data(owner, repo_name):
    """Busca dados gerais de um repositório."""
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo_name}"
    return _make_github_request(url)

def fetch_repo_issues(owner, repo_name, state='all', since=None, page=1, per_page=100):
    """
    Busca issues de um repositório com paginação e filtros.
    `since`: Apenas issues atualizadas a partir desta data (ISO 8601).
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo_name}/issues"
    params = {'state': state, 'direction': 'asc'} # Ordena por data de criação ascendente

    if since:
        params['since'] = since # "YYYY-MM-DDTHH:MM:SSZ"

    return _make_github_request(url, params=params, page=page, per_page=per_page)

def fetch_repo_commits(owner, repo_name, since=None, until=None, sha=None, page=1, per_page=100):
    """
    Busca commits de um repositório com paginação e filtros.
    `since`: Apenas commits feitos a partir desta data.
    `until`: Apenas commits feitos até esta data.
    `sha`: Branch, tag ou SHA para iniciar a busca.
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo_name}/commits"
    params = {'direction': 'asc'} # Ordena por data do committer ascendente

    if since:
        params['since'] = since
    if until:
        params['until'] = until
    if sha:
        params['sha'] = sha # Ex: 'main' ou 'a1b2c3d'

    return _make_github_request(url, params=params, page=page, per_page=per_page)

# Exemplo de como obter o total (pode não ser direto para todas as APIs)
def get_total_issues_count(owner, repo_name):
    # Algumas APIs (como GitHub) não fornecem um "total_count" fácil para issues.
    # Você pode ter que fazer uma requisição com per_page=1 e ver o cabeçalho 'Link'
    # ou ir para a última página. Isso pode ser caro.
    # O ideal é confiar no que vem da API, ou iterar.
    # Para o GitHub, o melhor é baixar e contar, ou usar a informação do repositório se ela for atualizada.
    repo_data = get_repo_data(owner, repo_name)
    return repo_data.get('open_issues_count', 0) # Não inclui issues fechadas

def get_total_commits_count(owner, repo_name, branch='main'):
    # O GitHub não fornece um total de commits direto na API de repositórios.
    # Você teria que clonar e contar, ou iterar sobre a API de commits.
    # Para estimar, pode-se pegar o último commit e ver a diferença de tempo,
    # ou simplesmente sincronizar tudo e contar no seu DB.
    # Por simplicidade, vou retornar um valor fictício ou 0 se não for direto.
    return 0 # Não é trivial para obter via API sem baixar todos os commits