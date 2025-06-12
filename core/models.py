from django.db import models
from django.utils import timezone
import json


class Repositorio(models.Model):
    name = models.CharField(max_length=255, help_text="Nome do repositório (ex: my-project)")
    owner = models.CharField(max_length=255, help_text="Proprietário/Organização do repositório (ex: octocat)")
    full_name = models.CharField(max_length=512, unique=True,
                                 help_text="Nome completo do repositório (owner/name)",
                                 db_index=True) 
    # URL e informações da API
    # Alternativa mais flexível para múltiplas plataformas:
    GIT_PLATFORM_CHOICES = [
        ('github', 'GitHub'),
        ('gitlab', 'GitLab'),
        ('bitbucket', 'Bitbucket'),
        # Adicione outras plataformas conforme necessário
    ]
    platform = models.CharField(
        max_length=20,
        choices=GIT_PLATFORM_CHOICES,
        default='github',
        help_text="Plataforma Git onde o repositório está hospedado."
    )
    external_id = models.CharField(max_length=100, blank=True, null=True,
                                   help_text="ID único do repositório na plataforma externa (ex: GitHub ID). Útil para APIs.")
    clone_url_http = models.URLField(max_length=512, blank=True, null=True,
                                     help_text="URL para clonar o repositório via HTTPS")
    clone_url_ssh = models.CharField(max_length=512, blank=True, null=True,
                                     help_text="URL para clonar o repositório via SSH (formato SSH).")
    web_url = models.URLField(max_length=512, blank=True, null=True,
                              help_text="URL do repositório na interface web (ex: https://github.com/owner/name)")

    # Status e Metadados
    description = models.TextField(blank=True, null=True,
                                  help_text="Descrição do repositório")
    language = models.CharField(max_length=100, blank=True, null=True,
                                help_text="Linguagem principal do repositório")
    stars_count = models.IntegerField(default=0,
                                      help_text="Número de estrelas/likes do repositório")
    forks_count = models.IntegerField(default=0,
                                      help_text="Número de forks do repositório")
    open_issues_count = models.IntegerField(default=0,
                                            help_text="Número de issues abertas (do Git, pode ser atualizado)")
    default_branch = models.CharField(max_length=100, default='main',
                                      help_text="Nome do branch padrão (main, master, etc.)")
    is_private = models.BooleanField(default=False,
                                     help_text="Indica se o repositório é privado")
    archived = models.BooleanField(default=False,
                                   help_text="Indica se o repositório foi arquivado na plataforma Git")

    # Controle da Aplicação
    active = models.BooleanField(default=True,
                                 help_text="Indica se o monitoramento deste repositório está ativo.")
    last_sync_issues_at = models.DateTimeField(blank=True, null=True,
                                               help_text="Data/hora da última sincronização de issues.")
    last_sync_commits_at = models.DateTimeField(blank=True, null=True,
                                                help_text="Data/hora da última sincronização de commits.")
    created_at = models.DateTimeField(auto_now_add=True,
                                      help_text="Data/hora de criação do registro no seu sistema.")
    updated_at = models.DateTimeField(auto_now=True,
                                      help_text="Data/hora da última atualização do registro no seu sistema.")

    class Meta:
        verbose_name = "Repositório"
        verbose_name_plural = "Repositórios"
        ordering = ['full_name'] # Ordena por nome completo por padrão
        # Se você tiver repositórios com o mesmo nome em diferentes plataformas
        # considere adicionar um 'unique_together' com owner, name e platform
        # unique_together = (('owner', 'name', 'platform'),) # Mais robusto

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        # Atualiza full_name automaticamente antes de salvar
        if self.owner and self.name and not self.full_name:
            self.full_name = f"{self.owner}/{self.name}"
        super().save(*args, **kwargs)

    @property
    def issues_synced(self):
        return self.issue_set.count()

    @property
    def commits_synced(self):
        return self.commit_set.count()
    

class GitUser(models.Model):
    external_id = models.CharField(max_length=100, unique=True, db_index=True,
                                   help_text="ID único do usuário na plataforma Git (ex: GitHub user ID)")
    username = models.CharField(max_length=255, db_index=True,
                                help_text="Nome de usuário na plataforma Git")
    avatar_url = models.URLField(max_length=512, blank=True, null=True)
    web_url = models.URLField(max_length=512, blank=True, null=True)
    user_type = models.CharField(max_length=50, blank=True, null=True,
                                 help_text="Tipo de usuário (User, Bot, Organization)")

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Usuário Git"
        verbose_name_plural = "Usuários Git"
        ordering = ['username']


class Issue(models.Model):
    # Relacionamento com Repositório
    repository = models.ForeignKey('Repositorio', on_delete=models.CASCADE, related_name='issues',
                                   help_text="Repositório ao qual esta issue pertence.")

    # Identificação da Issue na Plataforma Git
    external_id = models.CharField(max_length=100,
                                   help_text="ID único da issue na plataforma Git (ex: GitHub Issue ID)")
    number = models.IntegerField(db_index=True,
                                 help_text="Número da issue dentro do repositório (ex: #123).")
    title = models.CharField(max_length=512, help_text="Título da issue.")
    body = models.TextField(blank=True, null=True,
                            help_text="Corpo/descrição da issue.")
    state = models.CharField(max_length=20, db_index=True,
                             choices=[('open', 'Open'), ('closed', 'Closed'), ('all', 'All')],
                             help_text="Estado atual da issue (aberta, fechada).")

    # Datas e Tempos
    created_at_git = models.DateTimeField(db_index=True,
                                          help_text="Data e hora de criação da issue na plataforma Git.")
    updated_at_git = models.DateTimeField(db_index=True,
                                          help_text="Data e hora da última atualização da issue na plataforma Git.")
    closed_at_git = models.DateTimeField(blank=True, null=True, db_index=True,
                                         help_text="Data e hora de fechamento da issue na plataforma Git.")

    # Pessoas envolvidas
    author = models.ForeignKey(GitUser, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='authored_issues',
                               help_text="Usuário que criou a issue.")
    assignees = models.ManyToManyField(GitUser, blank=True,
                                       related_name='assigned_issues',
                                       help_text="Usuários atribuídos a esta issue.")
    closed_by = models.ForeignKey(GitUser, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='closed_issues',
                                  help_text="Usuário que fechou a issue (se aplicável).")

    # Outras informações
    labels = models.JSONField(blank=True, null=True,
                              help_text="Array JSON de labels/tags da issue.")
    milestone = models.JSONField(blank=True, null=True,
                                 help_text="Informações da milestone da issue (JSON).")
    comments_count = models.IntegerField(default=0,
                                         help_text="Número de comentários na issue.")
    is_pull_request = models.BooleanField(default=False,
                                          help_text="Indica se esta 'issue' é na verdade um pull request (algumas APIs tratam PRs como issues).")
    web_url = models.URLField(max_length=512, blank=True, null=True,
                              help_text="URL da issue na interface web.")

    # Metadados da Aplicação
    synced_at = models.DateTimeField(auto_now_add=True,
                                     help_text="Data e hora da sincronização desta issue para o seu sistema.")

    class Meta:
        verbose_name = "Issue"
        verbose_name_plural = "Issues"
        ordering = ['-created_at_git'] # Ordena pelas mais recentes por padrão
        # Garante que não haja duas issues com o mesmo número no mesmo repositório
        unique_together = (('repository', 'external_id'),) # Use external_id para garantir unicidade global da issue no Git

    def __str__(self):
        return f"#{self.number} - {self.title} ({self.repository.full_name})"

    @property
    def time_to_close(self):
        """Calcula o tempo para fechar a issue, se estiver fechada."""
        if self.state == 'closed' and self.closed_at_git and self.created_at_git:
            return self.closed_at_git - self.created_at_git
        return None

    @property
    def is_open(self):
        return self.state == 'open'


class Commit(models.Model):
    # Relacionamento com Repositório
    repository = models.ForeignKey('Repositorio', on_delete=models.CASCADE, related_name='commits',
                                   help_text="Repositório ao qual este commit pertence.")

    # Identificação do Commit
    sha = models.CharField(max_length=40, db_index=True,
                           help_text="O SHA completo (hash) do commit.")
    short_sha = models.CharField(max_length=7, db_index=True,
                                 help_text="O SHA curto do commit (primeiros 7 caracteres).")

    # Mensagem do Commit
    message = models.TextField(help_text="Mensagem completa do commit.")
    # headline = models.CharField(max_length=255, blank=True, null=True,
    #                             help_text="Primeira linha da mensagem do commit (assunto).")

    # Autor e Committer (podem ser pessoas diferentes)
    author = models.ForeignKey('GitUser', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='authored_commits',
                               help_text="Usuário que é o autor (quem escreveu) do commit.")
    committer = models.ForeignKey('GitUser', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='committed_commits',
                                  help_text="Usuário que é o committer (quem aplicou) do commit.")

    # Datas (importante: autor e committer têm datas diferentes no Git)
    author_date_git = models.DateTimeField(db_index=True,
                                           help_text="Data e hora em que o autor fez o commit.")
    committer_date_git = models.DateTimeField(db_index=True,
                                              help_text="Data e hora em que o committer aplicou o commit.")

    # Estatísticas de Mudança (geralmente fornecidas pela API)
    additions = models.IntegerField(default=0, help_text="Número de linhas adicionadas no commit.")
    deletions = models.IntegerField(default=0, help_text="Número de linhas deletadas no commit.")
    total_changes = models.IntegerField(default=0, help_text="Total de linhas modificadas (adições + deleções).")

    # Informações de Parentesco (para rastrear a árvore do Git)
    # Lista de SHAs dos commits pais. A maioria dos commits tem um pai, mas merges têm dois ou mais.
    parents_shas = models.JSONField(blank=True, null=True,
                                    help_text="Lista JSON dos SHAs dos commits pais.")

    # Informações de Verificação (assinatura GPG, etc.)
    verification_status = models.CharField(max_length=50, blank=True, null=True,
                                           help_text="Status de verificação do commit (ex: 'verified', 'unverified', 'not_signed').")
    verification_reason = models.CharField(max_length=255, blank=True, null=True,
                                           help_text="Razão do status de verificação.")

    # URL na Web
    web_url = models.URLField(max_length=512, blank=True, null=True,
                              help_text="URL do commit na interface web da plataforma Git.")

    # Vinculação com Issues (Many-to-Many)
    # Este campo será preenchido após parsing da mensagem do commit
    issues = models.ManyToManyField('Issue', blank=True, related_name='linked_commits',
                                    help_text="Issues vinculadas a este commit através da mensagem.")

    # Metadados da Aplicação
    synced_at = models.DateTimeField(auto_now_add=True,
                                     help_text="Data e hora da sincronização deste commit para o seu sistema.")

    class Meta:
        verbose_name = "Commit"
        verbose_name_plural = "Commits"
        ordering = ['-committer_date_git'] # Ordena pelos commits mais recentes por padrão
        # Garante que não haja dois commits com o mesmo SHA no mesmo repositório
        unique_together = (('repository', 'sha'),)

    def __str__(self):
        return f"{self.short_sha} - {self.message[:50]}... ({self.repository.full_name})"

    # Propriedades e Métodos Úteis
    @property
    def has_issues(self):
        return self.issues.exists()

    @property
    def is_merge_commit(self):
        # Um merge commit tem mais de um pai
        return len(self.parents_shas) > 1 if self.parents_shas else False