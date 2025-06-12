from your_app_name.services import github_api # Importa as funções da API
from your_app_name.models import Repositorio, Issue, Commit, GitUser
from django.db import transaction
from datetime import datetime
import re # Para parsing de mensagens de commit

# Regex para encontrar referências a issues na mensagem de commit
ISSUE_REF_PATTERN = re.compile(r'(?:fix(?:es|ed)?|close(?:s|d)?|resolve(?:s|d)?)\s#(\d+)', re.IGNORECASE)

def _get_or_create_git_user(user_data):
    """Auxiliar para obter ou criar um GitUser."""
    if not user_data or 'id' not in user_data:
        return None
    user, created = GitUser.objects.get_or_create(
        external_id=str(user_data['id']), # IDs podem vir como int, mas CharField é mais flexível
        defaults={
            'username': user_data.get('login'),
            'avatar_url': user_data.get('avatar_url'),
            'web_url': user_data.get('html_url'),
            'user_type': user_data.get('type'),
        }
    )
    # Se não foi criado, mas o username ou avatar_url mudaram, você pode atualizar aqui
    if not created and (user.username != user_data.get('login') or user.avatar_url != user_data.get('avatar_url')):
        user.username = user_data.get('login')
        user.avatar_url = user_data.get('avatar_url')
        user.save()
    return user


def sync_repository_metadata(repo_obj: Repositorio):
    """
    Sincroniza os metadados gerais de um repositório (estrelas, descrição, etc.).
    """
    try:
        repo_data = github_api.get_repo_data(repo_obj.owner, repo_obj.name)
        repo_obj.description = repo_data.get('description')
        repo_obj.language = repo_data.get('language')
        repo_obj.stars_count = repo_data.get('stargazers_count', 0)
        repo_obj.forks_count = repo_data.get('forks_count', 0)
        repo_obj.open_issues_count = repo_data.get('open_issues_count', 0)
        repo_obj.default_branch = repo_data.get('default_branch', 'main')
        repo_obj.is_private = repo_data.get('private', False)
        repo_obj.archived = repo_data.get('archived', False)
        repo_obj.web_url = repo_data.get('html_url')
        repo_obj.clone_url_http = repo_data.get('clone_url')
        repo_obj.clone_url_ssh = repo_data.get('ssh_url')
        repo_obj.external_id = str(repo_data.get('id')) # Guardar o ID externo
        repo_obj.save()
        print(f"Metadados do repositório {repo_obj.full_name} sincronizados.")
    except Exception as e:
        print(f"Erro ao sincronizar metadados para {repo_obj.full_name}: {e}")
        # Logar erro, enviar para Sentry, etc.


def sync_repository_issues(repo_obj: Repositorio, state='all', since_datetime=None):
    """
    Baixa e grava issues de um repositório, com suporte a filtro e paginação.
    `since_datetime`: datetime object para buscar issues ATUALIZADAS a partir dessa data.
    """
    print(f"Iniciando sincronização de issues para {repo_obj.full_name}...")
    page = 1
    has_more = True
    processed_count = 0
    issues_ids_in_batch = set() # Para evitar duplicatas na mesma execução

    while has_more:
        try:
            # Converte datetime para string ISO 8601 exigida pela API
            since_str = since_datetime.isoformat() + 'Z' if since_datetime else None
            issues_data = github_api.fetch_repo_issues(
                repo_obj.owner, repo_obj.name,
                state=state,
                since=since_str,
                page=page
            )

            if not issues_data:
                has_more = False
                break

            with transaction.atomic(): # Garante que todas as operações no DB sejam atômicas
                for issue_data in issues_data:
                    # Algumas APIs retornam PRs como Issues. Você pode filtrar aqui.
                    if 'pull_request' in issue_data:
                        continue # Pule pull requests se você tiver um modelo separado para eles

                    # Evita processar a mesma issue se por algum motivo vier duplicada na paginação
                    if issue_data['id'] in issues_ids_in_batch:
                        continue
                    issues_ids_in_batch.add(issue_data['id'])


                    author_obj = _get_or_create_git_user(issue_data.get('user'))
                    closed_by_obj = _get_or_create_git_user(issue_data.get('closed_by'))

                    issue, created = Issue.objects.update_or_create(
                        repository=repo_obj,
                        external_id=str(issue_data['id']),
                        defaults={
                            'number': issue_data['number'],
                            'title': issue_data['title'],
                            'body': issue_data['body'],
                            'state': issue_data['state'],
                            'created_at_git': datetime.fromisoformat(issue_data['created_at'].replace('Z', '+00:00')),
                            'updated_at_git': datetime.fromisoformat(issue_data['updated_at'].replace('Z', '+00:00')),
                            'closed_at_git': datetime.fromisoformat(issue_data['closed_at'].replace('Z', '+00:00')) if issue_data['closed_at'] else None,
                            'author': author_obj,
                            'comments_count': issue_data.get('comments', 0),
                            'labels': issue_data.get('labels'),
                            'milestone': issue_data.get('milestone'),
                            'is_pull_request': 'pull_request' in issue_data,
                            'web_url': issue_data.get('html_url'),
                            'synced_at': timezone.now(),
                        }
                    )
                    issue.closed_by = closed_by_obj # Atribui o closed_by separadamente
                    issue.save()

                    # Lida com assignees (Many-to-Many)
                    assignees_to_add = []
                    for assignee_data in issue_data.get('assignees', []):
                        assignee_obj = _get_or_create_git_user(assignee_data)
                        if assignee_obj:
                            assignees_to_add.append(assignee_obj)
                    issue.assignees.set(assignees_to_add) # .set() remove os antigos e adiciona os novos

                    if created:
                        processed_count += 1
                        # print(f"  Issue #{issue.number} criada.")
                    else:
                        # print(f"  Issue #{issue.number} atualizada.")
                        pass # Já existe, mas foi atualizada

            if len(issues_data) < github_api.PER_PAGE_DEFAULT: # PER_PAGE_DEFAULT = 100
                has_more = False # Se menos do que o total por página, é a última página

            page += 1

        except github_api.GitHubAPIError as e:
            print(f"Erro da API do GitHub ao sincronizar issues para {repo_obj.full_name} (página {page}): {e}")
            has_more = False # Parar a sincronização para este repositório
            # Logar erro e considerar re-agendar ou notificar

        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão ao sincronizar issues para {repo_obj.full_name} (página {page}): {e}")
            has_more = False
            # Logar erro, tentar novamente mais tarde

        except Exception as e:
            print(f"Erro inesperado ao processar issues para {repo_obj.full_name} (página {page}): {e}")
            has_more = False
            # Logar erro e considerar re-agendar ou notificar

    repo_obj.last_sync_issues_at = timezone.now()
    repo_obj.save(update_fields=['last_sync_issues_at']) # Atualiza apenas o campo da data de sincronização
    print(f"Sincronização de issues para {repo_obj.full_name} concluída. {processed_count} novas/atualizadas issues.")


def sync_repository_commits(repo_obj: Repositorio, since_datetime=None, until_datetime=None):
    """
    Baixa e grava commits de um repositório, com suporte a filtro e paginação.
    `since_datetime`: datetime object para buscar commits feitos a partir desta data.
    `until_datetime`: datetime object para buscar commits feitos até esta data.
    """
    print(f"Iniciando sincronização de commits para {repo_obj.full_name}...")
    page = 1
    has_more = True
    processed_count = 0
    commits_shas_in_batch = set() # Para evitar duplicatas na mesma execução

    while has_more:
        try:
            since_str = since_datetime.isoformat() + 'Z' if since_datetime else None
            until_str = until_datetime.isoformat() + 'Z' if until_datetime else None

            commits_data = github_api.fetch_repo_commits(
                repo_obj.owner, repo_obj.name,
                since=since_str,
                until=until_str,
                page=page
            )

            if not commits_data:
                has_more = False
                break

            with transaction.atomic():
                for commit_data in commits_data:
                    commit_sha = commit_data['sha']
                    if commit_sha in commits_shas_in_batch:
                        continue
                    commits_shas_in_batch.add(commit_sha)

                    author_obj = _get_or_create_git_user(commit_data['author'])
                    committer_obj = _get_or_create_git_user(commit_data['committer'])

                    commit, created = Commit.objects.update_or_create(
                        repository=repo_obj,
                        sha=commit_sha,
                        defaults={
                            'short_sha': commit_sha[:7],
                            'message': commit_data['commit']['message'],
                            'author': author_obj,
                            'committer': committer_obj,
                            'author_date_git': datetime.fromisoformat(commit_data['commit']['author']['date'].replace('Z', '+00:00')),
                            'committer_date_git': datetime.fromisoformat(commit_data['commit']['committer']['date'].replace('Z', '+00:00')),
                            'additions': commit_data['stats']['additions'] if 'stats' in commit_data else 0,
                            'deletions': commit_data['stats']['deletions'] if 'stats' in commit_data else 0,
                            'total_changes': commit_data['stats']['total'] if 'stats' in commit_data else 0,
                            'parents_shas': [p['sha'] for p in commit_data['parents']],
                            'verification_status': commit_data['commit']['verification']['verified'] if 'verification' in commit_data['commit'] else 'unverified',
                            'verification_reason': commit_data['commit']['verification']['reason'] if 'verification' in commit_data['commit'] else '',
                            'web_url': commit_data['html_url'],
                            'synced_at': timezone.now(),
                        }
                    )

                    # Lógica para vincular issues ao commit (parsing da mensagem)
                    linked_issue_numbers = ISSUE_REF_PATTERN.findall(commit.message)
                    if linked_issue_numbers:
                        # Buscar issues do mesmo repositório com esses números
                        issues_to_link = Issue.objects.filter(
                            repository=repo_obj,
                            number__in=linked_issue_numbers
                        )
                        commit.issues.set(issues_to_link) # Seta o M2M para as issues encontradas

                    if created:
                        processed_count += 1
                        # print(f"  Commit {commit.short_sha} criado.")
                    # else:
                        # print(f"  Commit {commit.short_sha} atualizado.")

            if len(commits_data) < github_api.PER_PAGE_DEFAULT:
                has_more = False

            page += 1

        except github_api.GitHubAPIError as e:
            print(f"Erro da API do GitHub ao sincronizar commits para {repo_obj.full_name} (página {page}): {e}")
            has_more = False
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão ao sincronizar commits para {repo_obj.full_name} (página {page}): {e}")
            has_more = False
        except Exception as e:
            print(f"Erro inesperado ao processar commits para {repo_obj.full_name} (página {page}): {e}")
            has_more = False

    repo_obj.last_sync_commits_at = timezone.now()
    repo_obj.save(update_fields=['last_sync_commits_at'])
    print(f"Sincronização de commits para {repo_obj.full_name} concluída. {processed_count} novas/atualizadas commits.")