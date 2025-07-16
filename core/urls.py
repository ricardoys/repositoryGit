# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # página de listagem de repositórios
    path('repositorios/', views.repository_list, name='repository_list'),
    # View para acionar a sincronização de um repositório específico
    path('repositorios/<int:pk>/sincronizar/', views.sync_repository_view, name='sync_repository'),
    # página de detalhes de um repositório
    path('repositorios/<int:pk>/', views.repository_detail, name='repository_detail'),
    # formulário de parâmetros e sincronização de issues
    path('repositorios/<int:pk>/sincronizar_issues/', views.sync_issues_view, name='sync_issues'),
    # formulário de parâmetros e sincronização de commits
    path('repositorios/<int:pk>/sincronizar_commits/', views.sync_commits_view, name='sync_commits'),
]