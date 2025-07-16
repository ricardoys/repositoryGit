# core.views
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from core.models import Repositorio
from core.tasks import (
    sync_repo_metadata_task,
    sync_issue_metadata_task,
    sync_commit_metadata_task
)
from core.forms import IssueSyncForm, CommitSyncForm
from django.utils import timezone
from datetime import datetime


def repository_list(request):
    """View para listar todos os repositórios."""
    repos = Repositorio.objects.all().order_by('full_name')
    return render(request, 'core/repository_list.html', {'repos': repos})


def repository_detail(request, pk):
    """View para exibir detalhes de um repositório."""
    repo = get_object_or_404(Repositorio, pk=pk)
    return render(request, 'core/repository_detail.html', {'repo': repo})


def sync_repository_view(request, pk):
    """View para acionar a sincronização de metadados de um repositório via Celery."""
    repo = get_object_or_404(Repositorio, pk=pk)

    if request.method == 'POST': # É uma boa prática usar POST para ações que modificam dados
        # Enfileira a tarefa Celery para sincronizar APENAS os metadados do repositório
        sync_repo_metadata_task.delay(repo.id)

        # Se você quiser sincronizar TUDO (metadados, issues e commits):
        # full_sync_repository_task.delay(repo.id)

        messages.success(request, f"Sincronização para '{repo.full_name}' enfileirada com sucesso! As informações serão atualizadas em breve.")
        return redirect('repository_detail', pk=repo.id) # Redireciona de volta para a página de detalhes do repo
    
    # Se for uma requisição GET, apenas exibe um formulário de confirmação
    return render(request, 'core/confirm_sync.html', {'repo': repo})


def sync_issues_view(request, pk):
    """View para acionar a sincronização de issues de um repositório via Celery."""
    repo = get_object_or_404(Repositorio, pk=pk)

    if request.method == 'POST':
        form = IssueSyncForm(request.POST)
        if form.is_valid():
            state = form.cleaned_data['state']
            since_datetime = form.cleaned_data['since_datetime']
            full_sync = form.cleaned_data['full_sync']

            # Converte o datetime para string ISO 8601 para passar para a tarefa Celery
            # É importante garantir que o datetime seja timezone-aware (preferencialmente UTC)
            # antes de converter para ISO 8601 para a API do GitHub.
            since_datetime_str = None
            if since_datetime:
                if timezone.is_aware(since_datetime):
                    # Já é aware, apenas formatar
                    since_datetime_str = since_datetime.isoformat(timespec='seconds')
                else:
                    # Assumindo que datetime local sem timezone, converte para UTC
                    # Se o seu servidor for sempre UTC, pode ser mais simples.
                    since_datetime_str = timezone.make_aware(since_datetime, timezone.utc).isoformat(timespec='seconds')
                # A API do GitHub espera 'Z' para indicar UTC.
                if not (since_datetime_str.endswith('+00:00') or since_datetime_str.endswith('Z')):
                    since_datetime_str += 'Z'


            # Enfileira a tarefa Celery com os filtros.
            # Note o nome da task: sync_issue_metadata_task
            sync_issue_metadata_task.delay(
                repo.id,
                state=state,
                since_datetime_str=since_datetime_str,
                full_sync=full_sync
            )

            messages.success(request, f"Sincronização de issues para '{repo.full_name}' enfileirada com os filtros selecionados.")
            return redirect('repository_detail', pk=repo.id) # Redireciona para a página de detalhes do repositório
        else:
            # Se o formulário não for válido, re-renderiza com erros
            messages.error(request, "Por favor, corrija os erros no formulário.")
    else:
        # Requisição GET: inicializa o formulário
        initial_data = {}
        if repo.last_sync_issues_at:
            # Pre-popula com a última data de sincronização, convertendo para o formato HTML 'datetime-local'
            # Garanta que a data seja formatada corretamente para o widget HTML.
            # Se 'last_sync_issues_at' for timezone-aware, considere converter para o fuso horário local do usuário,
            # mas para o input type="datetime-local", um formato simples sem tzinfo é geralmente esperado.
            local_time = timezone.localtime(repo.last_sync_issues_at) if timezone.is_aware(repo.last_sync_issues_at) else repo.last_sync_issues_at
            initial_data['since_datetime'] = local_time.strftime('%Y-%m-%dT%H:%M')


        form = IssueSyncForm(initial=initial_data)

    return render(request, 'core/issue_sync_form.html', {'form': form, 'repo': repo})


def sync_commits_view(request, pk):
    """
    View para exibir um formulário de filtro para sincronização de commits
    e para acionar a tarefa Celery com esses filtros.
    """
    repo = get_object_or_404(Repositorio, pk=pk)

    if request.method == 'POST':
        form = CommitSyncForm(request.POST)
        if form.is_valid():
            since_datetime = form.cleaned_data['since_datetime']
            until_datetime = form.cleaned_data['until_datetime']
            full_sync = form.cleaned_data['full_sync']

            # Converte os objetos datetime para strings ISO 8601
            # para passar para a tarefa Celery, garantindo que sejam timezone-aware (UTC).
            since_datetime_str = None
            if since_datetime:
                if timezone.is_aware(since_datetime):
                    since_datetime_str = since_datetime.isoformat(timespec='seconds')
                else:
                    since_datetime_str = timezone.make_aware(since_datetime, timezone.utc).isoformat(timespec='seconds')
                if not (since_datetime_str.endswith('+00:00') or since_datetime_str.endswith('Z')):
                    since_datetime_str += 'Z'

            until_datetime_str = None
            if until_datetime:
                if timezone.is_aware(until_datetime):
                    until_datetime_str = until_datetime.isoformat(timespec='seconds')
                else:
                    until_datetime_str = timezone.make_aware(until_datetime, timezone.utc).isoformat(timespec='seconds')
                if not (until_datetime_str.endswith('+00:00') or until_datetime_str.endswith('Z')):
                    until_datetime_str += 'Z'

            # Enfileira a tarefa Celery com os filtros
            sync_commit_metadata_task.delay(
                repo.id,
                since_datetime_str=since_datetime_str,
                until_datetime_str=until_datetime_str,
                full_sync=full_sync
            )

            messages.success(request, f"Sincronização de commits para '{repo.full_name}' enfileirada com os filtros selecionados.")
            return redirect('repository_detail', pk=repo.id) # Redireciona para a página de detalhes do repositório
        else:
            # Se o formulário não for válido, re-renderiza com erros
            messages.error(request, "Por favor, corrija os erros no formulário de sincronização de commits.")
    else:
        # Requisição GET: inicializa o formulário
        initial_data = {}
        if repo.last_sync_commits_at:
            # Pre-popula com a última data de sincronização, formatando para o widget HTML 'datetime-local'
            local_time = timezone.localtime(repo.last_sync_commits_at) if timezone.is_aware(repo.last_sync_commits_at) else repo.last_sync_commits_at
            initial_data['since_datetime'] = local_time.strftime('%Y-%m-%dT%H:%M')

        form = CommitSyncForm(initial=initial_data)

    return render(request, 'core/commit_sync_form.html', {'form': form, 'repo': repo})


# Opcional: Uma view para listar os commits, similar a issue_list_view
def commit_list_view(request, pk):
    """
    View para listar os commits sincronizados de um repositório.
    """
    repo = get_object_or_404(Repositorio, pk=pk)
    # Assumindo que você tem um modelo 'Commit' e ele tem uma ForeignKey para 'Repositorio'
    commits = Commit.objects.filter(repository=repo).order_by('-committer_date_git') # Ordena pelos mais recentes
    
    return render(request, 'core/commit_list.html', {
        'repo': repo,
        'commits': commits
    })