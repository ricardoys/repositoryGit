# repositoriogit/__init__.py

# Isso garantirá que o aplicativo Celery esteja sempre importado quando o Django iniciar,
# para que as tarefas compartilhadas possam ser encontradas.
from .celery import app as celery_app

__all__ = ('celery_app',)