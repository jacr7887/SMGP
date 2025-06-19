# myproject/myproject/celery.py

import os
from celery import Celery

# 1. El nombre del módulo de settings es 'myproject.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# 2. Crear la instancia de Celery. Usa el nombre del proyecto.
app = Celery('myproject')

# 3. Cargar la configuración desde tu settings.py de Django.
app.config_from_object('django.conf:settings', namespace='CELERY')

# 4. Descubrir tareas en todas las apps (buscará en myapp/tasks.py).
app.autodiscover_tasks()
