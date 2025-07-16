# core/tasks.py

from celery import shared_task
from core.models import Repositorio
from core.services.git_sync import (
    sync_repository_metadata, 
    sync_repository_issues,
    sync_repository_commits
)
from datetime import datetime
from django.utils import timezone

# Se você precisar de outras tarefas, importe também:
# from celery.schedules import crontab # Para agendamento mais complexo


@shared_task(bind=True, default_retry_delay=300, max_retries=5)
def sync_repo_metadata_task(self, repo_id: int):
    """
    Tarefa Celery para sincronizar os metadados gerais de um repositório
    (descrição, estrelas, forks, etc.) usando a API do Git.

    Args:
        repo_id (int): O ID primário (pk) do objeto Repositorio a ser sincronizado.
    """
    try:
        # Tenta obter a instância do Repositório pelo ID
        repo = Repositorio.objects.get(id=repo_id)
        print(f"Iniciando sincronização de metadados para o repositório ID: {repo_id} ({repo.full_name})...")

        # Chama a função de serviço que lida com a lógica de API e atualização do DB
        sync_repository_metadata(repo)

        print(f"Sincronização de metadados para '{repo.full_name}' concluída com sucesso.")

    except Repositorio.DoesNotExist:
        # Se o repositório não for encontrado, significa que foi deletado ou o ID está errado.
        print(f"Erro: Repositório com ID {repo_id} não encontrado no banco de dados. Tarefa ignorada.")
        # Não tenta novamente, pois o objeto não existe.
        return f"Repositório com ID {repo_id} não encontrado."

    except Exception as e:
        # Captura qualquer outra exceção que possa ocorrer durante a execução da tarefa
        print(f"Erro inesperado na tarefa sync_repo_metadata_task para repo ID {repo_id}: {e}")
        # Logar o erro completo para depuração (e.g., com Sentry)

        # Re-tenta a tarefa se houver um erro, para resiliência contra falhas temporárias de rede/API.
        try:
            print(f"Tentando novamente a tarefa sync_repo_metadata_task para repo ID {repo_id}...")
            self.retry(exc=e) # `exc=e` passa a exceção original para o log do retry
        except self.MaxRetriesExceededError:
            print(f"Limite de tentativas excedido para sync_repo_metadata_task (repo ID: {repo_id}).")
            # Aqui você pode enviar uma notificação final de falha.
            return f"Falha após múltiplas tentativas para o repositório ID {repo_id}."


@shared_task(bind=True, default_retry_delay=300, max_retries=5)
def sync_issue_metadata_task(self, repo_id: int, state: str = 'all', since_datetime_str: str = None, full_sync: bool = False):
    """
    Tarefa Celery para sincronizar issues de um repositório,
    com filtros de estado e data de atualização.

    Args:
        repo_id (int): O ID primário (pk) do objeto Repositorio a ser sincronizado.
        state (str): Estado das issues a buscar ('all', 'open', 'closed').
        since_datetime_str (str): String ISO 8601 da data/hora para buscar issues
                                  ATUALIZADAS a partir dessa data.
        full_sync (bool): Se True, ignora `last_sync_issues_at` e `since_datetime_str`
                          para uma sincronização completa (ignora filtro de data).
    """
    try:
        repo = Repositorio.objects.get(id=repo_id)
        print(f"Iniciando sincronização de issues para o repositório ID: {repo_id} ({repo.full_name})...")
        print(f"Filtros aplicados: estado='{state}', desde='{since_datetime_str}', full_sync={full_sync}")

        # --- Lógica para determinar o 'since_datetime' efetivo ---
        effective_since_datetime = None
        if full_sync:
            # Se full_sync for True, ignore qualquer data e faça uma sincronização completa.
            effective_since_datetime = None
        elif since_datetime_str:
            # Se 'since_datetime_str' for fornecido, use-o (convertendo de volta para datetime).
            try:
                # O .replace('Z', '+00:00') é para garantir compatibilidade com `datetime.fromisoformat`
                # para strings ISO 8601 que terminam com 'Z' (Zulu time / UTC).
                effective_since_datetime = datetime.fromisoformat(since_datetime_str.replace('Z', '+00:00'))
            except ValueError:
                print(f"Aviso: Formato de data 'since_datetime_str' inválido: {since_datetime_str}. Ignorando filtro de data.")
                effective_since_datetime = None
        else:
            # Se nenhum filtro explícito de data e nem full_sync, use a última data de sincronização do repositório.
            effective_since_datetime = repo.last_sync_issues_at
        # --- Fim da lógica 'since_datetime' ---

        # Chama a função de service, passando os argumentos de filtro
        sync_repository_issues(repo, state=state, since_datetime=effective_since_datetime)

        print(f"Sincronização de issues para '{repo.full_name}' concluída com sucesso.")

    except Repositorio.DoesNotExist:
        # Se o repositório não for encontrado, significa que foi deletado ou o ID está errado.
        print(f"Erro: Repositório com ID {repo_id} não encontrado no banco de dados. Tarefa ignorada.")
        return f"Repositório com ID {repo_id} não encontrado."

    except Exception as e:
        # Captura qualquer outra exceção que possa ocorrer durante a execução da tarefa
        print(f"Erro inesperado na tarefa sync_issue_metadata_task para repo ID {repo_id}: {e}")
        # Re-tenta a tarefa se houver um erro, para resiliência contra falhas temporárias de rede/API.
        try:
            print(f"Tentando novamente a tarefa sync_issue_metadata_task para repo ID {repo_id}...")
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            print(f"Limite de tentativas excedido para sync_issue_metadata_task (repo ID: {repo_id}).")
            # Aqui você pode enviar uma notificação final de falha.
            return f"Falha após múltiplas tentativas para o repositório ID {repo_id}."


@shared_task(bind=True, default_retry_delay=300, max_retries=5)
def sync_commit_metadata_task(self, repo_id: int, since_datetime_str: str = None, until_datetime_str: str = None, full_sync: bool = False):
    """
    Tarefa Celery para sincronizar commits de um repositório,
    com filtros de data de criação (since e until).

    Args:
        repo_id (int): O ID primário (pk) do objeto Repositorio a ser sincronizado.
        since_datetime_str (str): String ISO 8601 da data/hora para buscar commits feitos a partir desta data.
        until_datetime_str (str): String ISO 8601 da data/hora para buscar commits feitos até esta data.
        full_sync (bool): Se True, ignora `last_sync_commits_at` e `since_datetime_str`
                          para uma sincronização completa.
    """
    try:
        repo = Repositorio.objects.get(id=repo_id)
        print(f"Iniciando sincronização de commits para o repositório ID: {repo_id} ({repo.full_name})...")
        print(f"Filtros aplicados: desde='{since_datetime_str}', até='{until_datetime_str}', full_sync={full_sync}")

        # --- Lógica para determinar o 'since_datetime' efetivo ---
        effective_since_datetime = None
        if full_sync:
            effective_since_datetime = None # Força sincronização completa (ignora data de início)
        elif since_datetime_str:
            try:
                effective_since_datetime = datetime.fromisoformat(since_datetime_str.replace('Z', '+00:00'))
            except ValueError:
                print(f"Aviso: Formato de data 'since_datetime_str' inválido: {since_datetime_str}. Ignorando filtro de data de início.")
                effective_since_datetime = None
        else:
            # Se nenhum filtro explícito de data de início e nem full_sync, use a última data de sincronização do repositório.
            # Isso permite sincronização incremental padrão.
            effective_since_datetime = repo.last_sync_commits_at
        # --- Fim da lógica 'since_datetime' ---

        # --- Lógica para determinar o 'until_datetime' efetivo ---
        effective_until_datetime = None
        if until_datetime_str:
            try:
                effective_until_datetime = datetime.fromisoformat(until_datetime_str.replace('Z', '+00:00'))
            except ValueError:
                print(f"Aviso: Formato de data 'until_datetime_str' inválido: {until_datetime_str}. Ignorando filtro de data de fim.")
                effective_until_datetime = None
        # Se 'until_datetime_str' for None, o service buscará commits até o momento da execução, o que é o padrão.
        # --- Fim da lógica 'until_datetime' ---


        # Chama a função de service, passando os argumentos de filtro
        sync_repository_commits(
            repo,
            since_datetime=effective_since_datetime,
            until_datetime=effective_until_datetime
        )

        print(f"Sincronização de commits para '{repo.full_name}' concluída com sucesso.")

    except Repositorio.DoesNotExist:
        print(f"Erro: Repositório com ID {repo_id} não encontrado no banco de dados. Tarefa ignorada.")
        return f"Repositório com ID {repo_id} não encontrado."

    except Exception as e:
        print(f"Erro inesperado na tarefa sync_commit_metadata_task para repo ID {repo_id}: {e}")
        try:
            print(f"Tentando novamente a tarefa sync_commit_metadata_task para repo ID {repo_id}...")
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            print(f"Limite de tentativas excedido para sync_commit_metadata_task (repo ID: {repo_id}).")
            return f"Falha após múltiplas tentativas para o repositório ID {repo_id}."