# repositoriogit/celery.py

import os
from celery import Celery

# Define o módulo de configurações padrão do Django para o programa 'celery'.
# Isso garante que o Celery use as configurações do seu projeto Django.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'repositoriogit.settings')

# Cria uma instância do aplicativo Celery.
# O nome do aplicativo ('repositoriogit') é o nome do seu projeto.
app = Celery('repositoriogit')

# Carrega as configurações do Celery a partir do objeto de configurações do Django.
# O namespace 'CELERY' significa que todas as configurações do Celery no settings.py
# devem começar com 'CELERY_', por exemplo, CELERY_BROKER_URL.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descobre e carrega automaticamente as tarefas de todos os aplicativos Django registrados.
# Isso significa que o Celery irá procurar por um arquivo tasks.py em cada app em INSTALLED_APPS
# e registrar as funções decoradas com @shared_task como tarefas.
app.autodiscover_tasks()

# Definições opcionais para fins de depuração
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')