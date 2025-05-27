# myapp/backends.py
import logging  # Añadir import de logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
# Importar directamente el modelo es generalmente seguro aquí
# from .models import Usuario # O usar get_user_model consistentemente

logger = logging.getLogger(__name__)  # Configurar logger
UserModel = get_user_model()


class CustomAuthBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            # El backend de Django espera que username sea el primer argumento posicional
            # o una keyword 'username'. Si no viene, no podemos buscar.
            # A menudo, Django pasa el valor del campo USERNAME_FIELD como 'username'.
            # Si tu USERNAME_FIELD es 'email', username contendrá el email.
            return None

        try:
            # Buscar por email (case-insensitive) o username (case-insensitive)
            user = UserModel.objects.get(
                Q(email__iexact=username) | Q(username__iexact=username)
            )

            # Verificar contraseña y estado de la cuenta
            if user.check_password(password) and self.user_can_authenticate(user):
                # user_can_authenticate verifica user.is_active por defecto
                # Añadir tus chequeos personalizados aquí si son necesarios además de is_active
                if user.activo and user.nivel_acceso >= 1:  # Usando tus campos
                    return user
                else:
                    logger.warning(
                        f"Autenticación fallida para {username}: Usuario inactivo o sin nivel de acceso suficiente.")
                    return None  # Fallo explícito por estado/nivel
            else:
                # Contraseña incorrecta
                logger.warning(
                    f"Autenticación fallida para {username}: Contraseña incorrecta.")
                return None

        except UserModel.DoesNotExist:
            logger.debug(
                f"Autenticación fallida: Usuario '{username}' no encontrado.")
            return None
        except UserModel.MultipleObjectsReturned:
            # ¡Esto indica un problema de datos! Deberías investigarlo.
            logger.error(
                f"¡ERROR DE AUTENTICACIÓN! Múltiples usuarios encontrados para '{username}'.")
            return None
        # NO atrapar Exception genérico aquí. Dejar que errores de BD (OperationalError, InterfaceError, etc.)
        # se propaguen para que Django los maneje y los tests fallen correctamente.
        # except Exception as e:
        #     logger.error(f"Error inesperado durante autenticación para '{username}': {e}", exc_info=True)
        #     return None

    def get_user(self, user_id):
        # Este método generalmente no necesita cambios, el de ModelBackend funciona bien.
        try:
            user = UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        # Devolver usuario si está activo según la lógica de ModelBackend
        return user if self.user_can_authenticate(user) else None
