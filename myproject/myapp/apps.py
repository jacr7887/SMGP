from django.apps import AppConfig


class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    def ready(self):
        try:
            import myapp.signals  # Importa tus señales aquí
            # Mensaje de confirmación
            print(">>> Señales de myapp cargadas correctamente.")
        except ImportError:
            print("ADVERTENCIA: No se pudo importar myapp.signals.")
        except Exception as e:
            print(f"ERROR al importar señales de myapp: {e}")
