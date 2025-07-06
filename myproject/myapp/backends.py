# myapp/backends.py
import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

logger = logging.getLogger(__name__)
UserModel = get_user_model()


class CustomAuthBackend(ModelBackend):
    """
    Backend de autenticación personalizado que permite iniciar sesión
    usando el correo electrónico o el nombre de usuario.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Sobrescribe el método de autenticación.
        """
        if username is None:
            # Django pasa el valor del campo USERNAME_FIELD como 'username'.
            # En nuestro caso, es el email.
            return None

        try:
            # Busca un usuario cuyo email o username coincida (sin distinguir mayúsculas/minúsculas).
            # Esto permite flexibilidad si en el futuro decides usar usernames para algo.
            user = UserModel.objects.get(
                Q(email__iexact=username) | Q(username__iexact=username)
            )

        except UserModel.DoesNotExist:
            logger.debug(
                f"Intento de login fallido: Usuario '{username}' no encontrado.")
            return None
        except UserModel.MultipleObjectsReturned:
            # Esto indica un problema grave de datos si ocurre.
            logger.error(
                f"¡ERROR DE AUTENTICACIÓN! Múltiples usuarios encontrados para '{username}'.")
            return None

        # Una vez encontrado el usuario, verificamos la contraseña y si la cuenta está activa.
        # El método `user_can_authenticate` de la clase base ya verifica `user.is_active`.
        if user.check_password(password) and self.user_can_authenticate(user):
            logger.info(f"Autenticación exitosa para el usuario: {user.email}")
            return user
        else:
            # La contraseña es incorrecta o el usuario no está activo.
            logger.warning(
                f"Autenticación fallida para {username}: Contraseña incorrecta o cuenta inactiva.")
            return None

    def get_user(self, user_id):
        """
        Obtiene un usuario por su ID. Este método es usado por Django
        para recuperar el objeto de usuario de la sesión.
        """
        try:
            user = UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None

        # Devuelve el usuario solo si sigue estando activo.
        return user if self.user_can_authenticate(user) else None
