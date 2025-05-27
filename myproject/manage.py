#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import atexit
import django.db
import django
from django.conf import settings

# Intenta importar 'sequences' aquí para la depuración
try:
    import sequences
    sequences_imported_for_debug = True
except ImportError:
    sequences_imported_for_debug = False
    print("WARN: No se pudo importar 'sequences' al inicio de manage.py (puede ser normal si aún no se ha configurado).")


def close_connections():
    try:
        django.db.connections.close_all()
    except Exception as e:
        print(f"Error al cerrar conexiones: {e}")


atexit.register(close_connections)


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # --- Bloque de Depuración para 'sequences' ---
    print("-" * 20 + " DEBUGGING SEQUENCES IMPORT " + "-" * 20)
    # Para confirmar que es el del venv
    print(f"Python Executable: {sys.executable}")
    print("sys.path:")
    for p in sys.path:
        print(f"  - {p}")
    print("\nIntentando importar 'sequences' (de nuevo si falló antes)...")
    if sequences_imported_for_debug:
        # Ya se importó arriba, usar esa referencia
        try:
            # Imprime la ubicación del módulo 'sequences' encontrado
            print(f"Ubicación de 'sequences' encontrado: {sequences.__file__}")
            # Intenta acceder al atributo que falla
            print(
                f"Intentando acceder a 'get_next_value': {hasattr(sequences, 'get_next_value')}")
            if hasattr(sequences, 'get_next_value'):
                print("-> ¡Atributo 'get_next_value' ENCONTRADO en el módulo importado!")
            else:
                print(
                    "-> ERROR: Atributo 'get_next_value' NO encontrado en el módulo importado.")
                # Listar otros atributos para ver qué contiene
                print("Atributos disponibles en 'sequences':")
                try:
                    for attr in dir(sequences):
                        if not attr.startswith('_'):  # Omitir privados/dunder
                            print(f"  - {attr}")
                except Exception as e:
                    print(f"  (No se pudieron listar atributos: {e})")

        except AttributeError:
            # Esto puede pasar si 'sequences' es un módulo sin __file__ (raro aquí)
            print(
                f"ERROR: 'sequences' importado, pero no tiene atributo '__file__'. ¿Es un namespace package?")
        except Exception as e:
            print(f"ERROR inesperado al inspeccionar 'sequences': {e}")
    else:
        # Si falló la importación inicial, lo indicamos
        print("ERROR: Falla al importar 'sequences' globalmente en manage.py.")

    print("-" * 20 + " FIN DEBUGGING " + "-" * 20 + "\n")
    # --- Fin del Bloque de Depuración ---

    # La línea original donde ocurre el setup
    django.setup()
    # Mensaje más descriptivo
    print(f"AUTH_USER_MODEL configurado: {settings.AUTH_USER_MODEL}")
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
