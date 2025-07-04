# models.py
# Needed for dynamic model fetching if used in Meta or methods
# Tus validadores
from .validators import validate_past_date, validate_telefono_venezuela, validate_pasaporte
from .commons import CommonChoices, RAMO_ABREVIATURAS, RANGO_ETARIO_ABREVIATURAS
import logging  # Para logging
import uuid  # Para _generate_unique_username
import hashlib
from django.utils import timezone  # Para default=timezone.now en date_joined
from django.core.validators import MinValueValidator, MaxValueValidator
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db.models.functions import Coalesce
from django.db.models import Sum, Q, DecimalField, Value
from django.db.models import Sum
from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator, validate_email
from django.db import models
from django.db import transaction
from django.conf import settings
from sequences import get_next_value
from django.core.exceptions import ValidationError
from django.db.models import JSONField
from datetime import datetime, date, timedelta
import pgtrigger
from django.utils import timezone as django_timezone
from dateutil.relativedelta import relativedelta
from pgtrigger import Protect, Insert, Update
from pgtrigger import Q as TriggerQ
from pgtrigger.core import F as TriggerF
from .validators import (
    validate_rif, validate_cedula, validate_file_size, validate_file_type, validate_telefono_venezuela, validate_past_date, validate_date_range, validate_contrato_vigencia, validate_numero_contrato, validate_certificado, validate_afiliado_contrato, validate_reclamacion_monto, validate_estado_reclamacion, validate_metodo_pago, validate_monto_pago, validate_monto_pago_factura)
from .commons import (
    CommonChoices)

from django.db.models import (
    Q, Prefetch, Sum, Index
)

from django.apps import apps
from decimal import Decimal, InvalidOperation
import re
import uuid
import logging
import sequences
from django.db import connection  # Para verificar si la tabla de secuencias existe

# Logger general para el módulo models.py
logger = logging.getLogger(__name__)

# Logger específico para operaciones de guardado en modelos que queremos rastrear
logger_model_save = logging.getLogger(__name__ + ".model_save_operations")


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(activo=True)


# ---------------------------
# Generador de Secuencias
# -----------------------------
try:
    from sequences import get_next_value
except ImportError:
    get_next_value = None

logger_seq = logging.getLogger(__name__ + ".sequences_custom")


def generar_codigo_unico(sequence_name, prefix, length, fallback_prefix="ERR-UUID"):
    can_use_sequence = False
    if get_next_value is not None:
        try:
            with connection.cursor() as cursor:
                # Intenta una consulta que falle si la tabla no existe.
                cursor.execute(
                    "SELECT COUNT(*) FROM sequences_sequence WHERE name = %s LIMIT 1;", [sequence_name])
            can_use_sequence = True
        except Exception as db_error:
            logger_seq.warning(
                f"No se pudo verificar/acceder a la tabla de secuencias para '{sequence_name}'. Error: {db_error}. Usando fallback UUID."
            )
    else:
        logger_seq.error(
            f"La función get_next_value de 'sequences' no está disponible. Usando fallback UUID para '{sequence_name}'.")

    if can_use_sequence:
        try:
            next_val = get_next_value(sequence_name, initial_value=1)
            if not isinstance(next_val, int):
                logger_seq.error(
                    f"get_next_value para '{sequence_name}' no devolvió un entero, sino: {next_val} (Tipo: {type(next_val)}). Usando fallback UUID."
                )
                raise ValueError("Valor de secuencia no es entero.")

            codigo_propuesto = f"{prefix}{next_val:0{length}d}"
            logger_seq.debug(
                f"Código propuesto por secuencia '{sequence_name}': {codigo_propuesto}")
            return codigo_propuesto
        except RuntimeError as e:
            logger_seq.warning(
                f"Sequence '{sequence_name}' no existe aún o error de runtime, usando fallback: {e}")
        except Exception as e:
            logger_seq.error(
                f"Error generando secuencia '{sequence_name}' para {prefix}: {e}", exc_info=True)

    logger_seq.warning(
        f"Usando fallback UUID para generar código para prefijo '{prefix}' (secuencia: '{sequence_name}')")

    # <--- ¡¡¡AJUSTA ESTO AL MAX_LENGTH DE Intermediario.codigo!!!
    MODEL_FIELD_MAX_LENGTH = 15

    available_uuid_length = MODEL_FIELD_MAX_LENGTH - (len(fallback_prefix) + 1)

    if available_uuid_length < 4:
        logger_seq.error(
            f"Fallback prefix '{fallback_prefix}' es demasiado largo para el campo de max_length {MODEL_FIELD_MAX_LENGTH}. Usando UUID truncado.")
        return uuid.uuid4().hex[:MODEL_FIELD_MAX_LENGTH]

    uuid_part = uuid.uuid4().hex[:available_uuid_length]
    final_code = f"{fallback_prefix}-{uuid_part}"

    logger_seq.info(f"Código de fallback generado: {final_code}")
    return final_code

# ---------------------------
# Licencia de software
# ---------------------------


class LicenseInfo(models.Model):
    SINGLETON_ID = 1
    id = models.PositiveIntegerField(
        primary_key=True, default=SINGLETON_ID, editable=False)
    license_key = models.CharField(
        max_length=512, unique=True, help_text="Clave de licencia activa.")
    expiry_date = models.DateField(
        help_text="Fecha de expiración de la licencia.")
    last_updated = models.DateTimeField(
        auto_now=True)  # Cambiado de last_checked

    permissions = [
        ("change_licenseinfo", "Puede cambiar la información de la licencia"),
    ]

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_ID
        # Opcional: Validar antes de guardar
        if self.expiry_date and self.expiry_date < date.today():
            logger.warning(
                f"Guardando registro de licencia expirada: {self.expiry_date}")
            # No lanzar error aquí para permitir guardar claves expiradas, la validación está en is_valid
        super().save(*args, **kwargs)

    def clean(self):
        if self.pk != self.SINGLETON_ID:  # Si la instancia que se está validando NO tiene el pk correcto
            # Y si ya existe la instancia singleton correcta
            if self.__class__.objects.filter(pk=self.SINGLETON_ID).exists():
                raise ValidationError(
                    f"Solo puede existir una configuración de licencia con ID={self.SINGLETON_ID}. "
                    f"Está intentando guardar una con ID={self.pk}."
                )
        # Adicionalmente, si se está creando una nueva (pk es None) y ya existe la singleton:
        if self.pk is None and self.__class__.objects.filter(pk=self.SINGLETON_ID).exists():
            raise ValidationError(
                "Solo puede existir una configuración de licencia (ID=1). Ya existe una.")

    @property  # Convertido a property para claridad
    def is_valid(self):
        """Verifica si la licencia almacenada es válida hoy."""
        if not isinstance(self.expiry_date, date):
            return False
        # Válida hasta el final del día de expiración
        return date.today() <= self.expiry_date

    def __str__(self):
        valid_str = "VÁLIDA" if self.is_valid else "EXPIRADA/INVÁLIDA"
        return f"Licencia (Expira: {self.expiry_date.strftime('%Y-%m-%d')}) - {valid_str}"

    class Meta:
        verbose_name = "Información de Licencia"
        verbose_name_plural = "Información de Licencia"

# ------------------------------
# Modelo Notificacion
# ------------------------------


class Notificacion(models.Model):
    from encrypted_model_fields.fields import EncryptedTextField

    TIPO_NOTIFICACION_CHOICES = [
        ('info', 'Información'),        # Azul claro (predeterminado)
        ('success', 'Éxito'),         # Verde
        ('warning', 'Advertencia'),    # Naranja/Amarillo
        ('error', 'Error'),           # Rojo
        ('system', 'Sistema'),        # Gris/Neutro (ej. Mantenimiento)
    ]

    # A quién va dirigida la notificación
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # Si se borra el usuario, se borran sus notificaciones
        related_name='notificaciones',
        verbose_name="Usuario Destino"
    )
    # Contenido y tipo
    mensaje = EncryptedTextField(verbose_name="Mensaje")
    tipo = models.CharField(
        choices=TIPO_NOTIFICACION_CHOICES,
        default='info',
        verbose_name="Tipo"
    )
    # Enlace opcional
    # Usamos CharField por flexibilidad
    url_destino = models.CharField(
        max_length=500, blank=True, null=True, verbose_name="URL Destino")
    # Estado
    leida = models.BooleanField(
        default=False, db_index=True, verbose_name="Leída")
    fecha_creacion = models.DateTimeField(
        editable=False, auto_now_add=True, db_index=True, verbose_name="Fecha Creación")

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha_creacion']  # Las más nuevas primero

    def __str__(self):
        leida_str = "Leída" if self.leida else "No Leída"
        # Usar email o username según prefieras
        return f"Para {self.usuario.email}: {self.mensaje[:50]}... ({leida_str})"


# myapp/models.py

logger = logging.getLogger(__name__)

# ---------------------------
# ModeloBase (Como lo proporcionaste)
# ---------------------------


class ModeloBase(models.Model):
    from encrypted_model_fields.fields import EncryptedCharField

    primer_nombre = EncryptedCharField("Primer Nombre")
    segundo_nombre = EncryptedCharField(
        "Segundo Nombre", blank=True, null=True, default='')
    primer_apellido = EncryptedCharField("Primer Apellido")
    segundo_apellido = EncryptedCharField(
        "Segundo Apellido", blank=True, null=True, default='')
    fecha_creacion = models.DateTimeField(
        editable=False, auto_now_add=True, db_index=True, verbose_name="Fecha Creación",
        help_text="Fecha y hora en que se creó este registro (automático)."
    )
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        editable=False,
        verbose_name="Fecha de Modificación",
        db_index=True,
        help_text="Fecha y hora de la última modificación de este registro (automático)."
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['primer_apellido', 'primer_nombre']),
        ]

# ---------------------------
# UsuarioManager (Ajustado a tus CommonChoices)
# ---------------------------


class UsuarioManager(BaseUserManager):
    def _generate_unique_username(self, base_username):
        # Esta función auxiliar está perfecta, no necesita cambios.
        base_username_cleaned = "".join(
            filter(str.isalnum, base_username))[:20]
        base_part = base_username_cleaned[:20]
        unique_part = uuid.uuid4().hex[:6]
        return f"{base_part}_{unique_part}"[:150]

    def _create_user(self, email, password, **extra_fields):
        """
        Método base privado para crear y guardar un usuario con un email y contraseña.
        """
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        email = self.normalize_email(email)

        # Generar username si no se provee
        if 'username' not in extra_fields or not extra_fields.get('username'):
            base_username = email.split('@')[0]
            extra_fields['username'] = self._generate_unique_username(
                base_username)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        # El método save() del modelo se encargará del resto
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """
        Crea un usuario estándar.
        """
        # Forzamos los valores por defecto para un usuario no privilegiado.
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        # El tipo de usuario por defecto será 'CLIENTE' si no se especifica otro.
        extra_fields.setdefault('tipo_usuario', 'CLIENTE')
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Crea un superusuario.
        """
        # Forzamos los valores que definen a un superusuario.
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('activo', True)
        # El rol de un superusuario siempre será 'ADMIN'.
        extra_fields['tipo_usuario'] = 'ADMIN'

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


# ===================================================================
# ===              MODELO USUARIO CORREGIDO Y FINAL               ===
# ===================================================================

class Usuario(AbstractUser, ModeloBase):
    from encrypted_model_fields.fields import EncryptedEmailField, EncryptedDateField, EncryptedCharField, EncryptedTextField

    # --- Campos de AbstractUser que no usamos ---
    first_name = None
    last_name = None

    # --- Campos Principales ---
    email = models.EmailField(
        "Correo Electrónico",
        unique=True,
        error_messages={
            'unique': "Este correo electrónico ya está registrado."},
        help_text="Correo electrónico único, usado para el login.",
        validators=[validate_email]
    )
    # El campo 'username' de AbstractUser se mantiene por compatibilidad con Django,
    # pero lo hacemos no editable y lo generamos automáticamente.
    username = models.CharField(
        "Nombre de usuario (interno)", max_length=150, unique=True,
        help_text="Requerido. Generado automáticamente si se omite.",
        error_messages={
            'unique': "Un usuario con ese nombre de usuario ya existe."},
        editable=False
    )

    # --- NUESTRA FUENTE DE LA VERDAD PARA PERMISOS ---
    tipo_usuario = models.CharField(
        "Tipo de Usuario (Rol)",
        max_length=50,
        choices=CommonChoices.TIPO_USUARIO,
        default='CLIENTE',  # Un default seguro
        db_index=True,
        help_text="Clasificación funcional que define los permisos del usuario."
    )
    activo = models.BooleanField(
        "Cuenta Activa", default=True,
        help_text="Controla si el usuario puede iniciar sesión. Desmarcar en lugar de borrar."
    )
    fecha_nacimiento = EncryptedDateField("Fecha de Nacimiento", validators=[
                                          validate_past_date], null=True, blank=True)
    departamento = models.CharField(
        "Departamento", max_length=50, choices=CommonChoices.DEPARTAMENTO, blank=True, null=True, db_index=True)
    telefono = EncryptedCharField("Teléfono", validators=[
                                  validate_telefono_venezuela], blank=True, null=True)
    direccion = EncryptedTextField("Dirección", blank=True, null=True)
    intermediario = models.ForeignKey(
        'Intermediario', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='usuarios_asignados', verbose_name="Intermediario Asociado", db_index=True
    )

    # --- Configuración del Modelo ---
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['primer_nombre', 'primer_apellido']

    objects = UsuarioManager()
    all_objects = models.Manager()  # Para poder ver usuarios inactivos si es necesario

    # Mapeo de Rol a Nombre de Grupo de Permisos
    ROL_A_GRUPO_NOMBRE = {
        'ADMIN': 'Rol - Administrador',
        'INTERMEDIARIO': 'Rol - Intermediario',
        'CLIENTE': 'Rol - Cliente',
        'AUDITOR': 'Rol - Auditor',
    }

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para sincronizar el estado y los permisos
        basados en el `tipo_usuario`.
        """
        # 1. Sincronizar el estado `is_active` de Django con nuestro campo `activo`
        self.is_active = self.activo

        # 2. Sincronizar los privilegios de staff/superuser basados en el rol
        if self.tipo_usuario == 'ADMIN':
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False

        # 3. Obtener el tipo de usuario anterior para detectar cambios
        is_new = self._state.adding
        old_tipo_usuario = None
        if not is_new:
            try:
                old_instance = Usuario.objects.only(
                    'tipo_usuario').get(pk=self.pk)
                old_tipo_usuario = old_instance.tipo_usuario
            except Usuario.DoesNotExist:
                pass  # El objeto aún no existe, se tratará como nuevo

        # 4. Guardar el objeto en la base de datos
        super().save(*args, **kwargs)

        # 5. Sincronizar los grupos de permisos si es un usuario nuevo o su rol cambió
        if is_new or (old_tipo_usuario != self.tipo_usuario):
            self._assign_group_based_on_role()

    def _assign_group_based_on_role(self):
        """
        Añade al usuario al grupo correspondiente a su rol y lo elimina de los otros.
        """
        if not self.pk:
            return

        from django.contrib.auth.models import Group

        current_group_name = self.ROL_A_GRUPO_NOMBRE.get(self.tipo_usuario)

        # Eliminar al usuario de todos los grupos de roles gestionados por este sistema
        self.groups.remove(
            *Group.objects.filter(name__in=self.ROL_A_GRUPO_NOMBRE.values()))

        # Si el rol tiene un grupo asociado (ej. no es ADMIN, que ya es superuser), lo añadimos.
        if current_group_name and self.tipo_usuario != 'ADMIN':
            try:
                group_obj, created = Group.objects.get_or_create(
                    name=current_group_name)
                if created:
                    logger.warning(f"Grupo de rol '{current_group_name}' fue CREADO automáticamente. "
                                   f"Ejecute 'manage.py setup_roles' para asignarle permisos.")
                self.groups.add(group_obj)
                logger.info(
                    f"Usuario {self.email} añadido al grupo '{current_group_name}'.")
            except Exception as e:
                logger.error(
                    f"Error asignando grupo '{current_group_name}' al usuario {self.email}: {e}", exc_info=True)

    # --- Métodos de conveniencia (sin cambios) ---
    def get_full_name(self):
        parts = [self.primer_apellido, self.segundo_apellido]
        apellidos = " ".join(p for p in parts if p).strip()
        parts = [self.primer_nombre, self.segundo_nombre]
        nombres = " ".join(p for p in parts if p).strip()
        if apellidos and nombres:
            return f"{apellidos}, {nombres}"
        return nombres or apellidos or self.email

    def get_short_name(self):
        return self.primer_nombre or self.email.split('@')[0]

    def __str__(self):
        return self.get_full_name() or self.email

    class Meta:
        verbose_name = "Usuario del Sistema"
        verbose_name_plural = "Usuarios del Sistema"
        indexes = [
            models.Index(fields=['tipo_usuario', 'activo']),
            models.Index(fields=['departamento', 'activo']),
            models.Index(fields=['email'])
        ] + (ModeloBase.Meta.indexes if hasattr(ModeloBase, 'Meta') and hasattr(ModeloBase.Meta, 'indexes') else [])
        ordering = ['-date_joined']  # Orden por defecto seguro y no encriptado
# ---------------------------
# ContratoBase Corregido
# ---------------------------


@pgtrigger.register(
    Protect(
        name="contratobase_check_fecha_fin_after_inicio",
        operation=Insert | Update,
        condition=TriggerQ(new__fecha_fin_vigencia__lt=TriggerF('new__fecha_inicio_vigencia'))),
    Protect(
        name="contratobase_check_fecha_inicio_after_emision",
        operation=Insert | Update,
        condition=TriggerQ(new__fecha_inicio_vigencia__lt=TriggerF('new__fecha_emision__date')))
)
class ContratoBase(ModeloBase):
    ramo = models.CharField(
        max_length=50,
        choices=CommonChoices.RAMO,
        verbose_name="Ramo del Contrato",
        db_index=True,
        help_text="Tipo de seguro o servicio cubierto por el contrato (ej. Salud, Vida, Automóvil)."
    )
    forma_pago = models.CharField(
        max_length=20,
        choices=CommonChoices.FORMA_PAGO,
        default='MENSUAL',
        verbose_name="Forma de Pago",
        db_index=True,
        help_text="Frecuencia con la que se realizan los pagos del contrato (ej. Mensual, Anual)."
    )
    pagos_realizados = models.PositiveIntegerField(
        default=0,
        verbose_name="Pagos Realizados",
        blank=True,
        editable=True,
        help_text="Número de pagos o cuotas abonadas para este contrato hasta la fecha."
    )
    estatus = models.CharField(
        max_length=21,
        choices=CommonChoices.ESTADOS_VIGENCIA,
        default='VIGENTE',
        verbose_name="Estatus del Contrato",
        db_index=True,
        help_text="Estado actual de la vigencia del contrato (ej. Vigente, Vencido, Anulado)."
    )
    estado_contrato = models.CharField(
        "Estado Contrato",
        max_length=50,
        choices=CommonChoices.ESTADO_CONTRATO,
        blank=True,
        null=True,
        help_text="Estado administrativo o de proceso del contrato (ej. Renovación, Pendiente)."
    )
    suma_asegurada = models.DecimalField(
        max_digits=17,
        decimal_places=2,
        verbose_name="Suma Asegurada / Monto Cobertura",
        null=True,
        blank=True,
        db_index=True,
        help_text="Monto máximo que la aseguradora pagaría por siniestros cubiertos bajo este contrato/póliza.",
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    historial_cambios = JSONField(
        default=list,
        blank=True,
        verbose_name="Historial de Cambios (Estructurado)",
        help_text="Registro estructurado de modificaciones importantes realizadas al contrato."
    )
    numero_contrato = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
        validators=[validate_numero_contrato],
        help_text="Identificador único y secuencial asignado al contrato (generalmente automático)."
    )
    numero_poliza = models.CharField(
        max_length=50,
        verbose_name="Número de Póliza",
        db_index=True,
        unique=True,
        editable=False,
        help_text="Número único de la póliza asociada al contrato (generalmente automático)."
    )
    fecha_emision = models.DateTimeField(
        verbose_name="Fecha de Emisión del Contrato",
        db_index=True,
        editable=True,
        default=django_timezone.now,
        help_text="Fecha y hora en que se emitió oficialmente el contrato."
    )
    fecha_inicio_vigencia = models.DateField(
        verbose_name="Fecha de Inicio de Vigencia",
        db_index=True,
        blank=True,
        null=True,
        help_text="Fecha a partir de la cual el contrato entra en vigor (puede establecerse después)."
    )
    fecha_fin_vigencia = models.DateField(
        verbose_name="Fecha de Fin de Vigencia",
        db_index=True,
        blank=True,
        null=True,
        help_text="Fecha en la que finaliza la vigencia del contrato (puede establecerse después)."
    )
    periodo_vigencia_meses = models.PositiveIntegerField(
        verbose_name="Duración del Contrato (Meses)",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Número de meses de vigencia. Si se indica, la Fecha Fin se calcula automáticamente.",
        db_index=True
    )
    monto_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto Total del Contrato",
        help_text="Costo total del contrato para el período de vigencia especificado.",
        # Permite que la BD acepte NULL (importante para la migración)
        null=True,
        blank=True  # Le dice a los formularios de Django que este campo NO es requerido
    )
    intermediario = models.ForeignKey(
        'Intermediario',
        on_delete=models.PROTECT,
        verbose_name="Intermediario",
        db_index=True,
        help_text="Intermediario responsable de la gestión o venta de este contrato."
    )
    consultar_afiliados_activos = models.BooleanField(
        default=False,
        verbose_name="Consultar en data de afiliados activos",
        help_text="Indica si la información de este contrato debe cruzarse con la base de datos de afiliados activos."
    )
    certificado = models.CharField(
        max_length=20,
        verbose_name="Número de Certificado",
        blank=True,
        null=True,
        unique=True,
        editable=False,
        validators=[validate_certificado],
        help_text="Número de certificado único asociado (auto-generado o manual)."
    )
    tarifa_aplicada = models.ForeignKey(
        'Tarifa',
        on_delete=models.PROTECT,
        # Generará 'contratoindividual_set', 'contratocolectivo_set'
        related_name='%(class)s_set',
        # Generará 'contrato_contratoindividual', 'contrato_contratocolectivo'
        related_query_name='contrato_%(class)s',
        verbose_name="Tarifa Aplicada",
        null=False,
        blank=False,
        help_text="La tarifa utilizada para calcular el costo inicial/renovado."
    )

    def _calculate_monto_total_base(self):
        if self.tarifa_aplicada and self.tarifa_aplicada.monto_anual is not None and \
           isinstance(self.tarifa_aplicada.monto_anual, Decimal) and not self.tarifa_aplicada.monto_anual.is_nan():
            tarifa_anual_base = self.tarifa_aplicada.monto_anual
            if self.periodo_vigencia_meses and isinstance(self.periodo_vigencia_meses, int) and self.periodo_vigencia_meses > 0:
                if self.periodo_vigencia_meses == 12:
                    calculated_monto = tarifa_anual_base
                else:
                    calculated_monto = (
                        tarifa_anual_base / Decimal(12)) * Decimal(self.periodo_vigencia_meses)
                return calculated_monto.quantize(Decimal("0.01"), ROUND_HALF_UP)
            else:  # Sin periodo_vigencia_meses válido, usar tarifa anual base si es un contrato de 12 meses implícito o si no hay periodo
                return tarifa_anual_base.quantize(Decimal("0.01"), ROUND_HALF_UP)
        return None

    @property
    def total_pagado_a_facturas(self):
        """
        Suma los montos de los pagos activos asociados a las facturas activas de este contrato.
        Esta property realiza una consulta a la BD cada vez que se llama, garantizando datos frescos.
        """
        if hasattr(self, 'factura_set'):
            return self.factura_set.filter(
                activo=True,
                pagos__activo=True
            ).aggregate(
                total=Coalesce(Sum('pagos__monto_pago'), Decimal(
                    '0.00'), output_field=DecimalField())
            )['total']
        return Decimal('0.00')

    @property
    def saldo_pendiente_contrato(self):
        """
        Calcula el saldo pendiente del contrato restando los pagos al monto total.
        Usa la property `total_pagado_a_facturas` para asegurar el cálculo con datos frescos.
        """
        monto_total_contrato = self.monto_total if isinstance(
            self.monto_total, Decimal) else Decimal('0.00')
        if monto_total_contrato <= Decimal('0.00'):
            return Decimal('0.00')

        pendiente = monto_total_contrato - self.total_pagado_a_facturas
        return max(Decimal('0.00'), pendiente)

    def save(self, *args, **kwargs):
        # Esta lógica se asegura de que el campo NUNCA se guarde como NULL
        if self.tarifa_aplicada and self.periodo_vigencia_meses:
            tarifa_anual = self.tarifa_aplicada.monto_anual
            if tarifa_anual is not None and self.periodo_vigencia_meses > 0:
                self.monto_total = (Decimal(tarifa_anual) / 12) * \
                    Decimal(self.periodo_vigencia_meses)
                self.monto_total = self.monto_total.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)

        if self.monto_total is None:
            self.monto_total = Decimal('0.00')

        super().save(*args, **kwargs)

    @property
    def cantidad_cuotas_estimadas(self):
        periodo_a_usar = self.periodo_vigencia_meses

        if self.forma_pago == 'CONTADO':
            return 1

        if not (periodo_a_usar is not None and isinstance(periodo_a_usar, int) and periodo_a_usar > 0):
            return None

        meses = periodo_a_usar
        cuotas_calculadas = 0
        if self.forma_pago == 'MENSUAL':
            cuotas_calculadas = meses
        elif self.forma_pago == 'TRIMESTRAL':
            cuotas_calculadas = (meses + 2) // 3
        elif self.forma_pago == 'SEMESTRAL':
            cuotas_calculadas = (meses + 5) // 6
        elif self.forma_pago == 'ANUAL':
            cuotas_calculadas = (meses + 11) // 12

        if cuotas_calculadas > 0:
            return cuotas_calculadas

        return None

    @property
    # Nueva propiedad para mostrar en el detalle
    def importe_anual_contrato(self):
        """Devuelve el costo anualizado del contrato basado en su monto_total y duración."""
        if self.monto_total is not None and self.periodo_vigencia_meses and self.periodo_vigencia_meses > 0:
            costo_mensual = self.monto_total / \
                Decimal(self.periodo_vigencia_meses)
            return (costo_mensual * 12).quantize(Decimal("0.01"), ROUND_HALF_UP)
        elif self.monto_total is not None and (not self.periodo_vigencia_meses or self.periodo_vigencia_meses == 0):
            # Si no hay periodo o es 0, pero hay monto_total, asumimos que es el monto anual.
            # Esto podría necesitar ajuste según tu lógica de negocio.
            return self.monto_total
        return None

    @property
    def dias_vigencia_transcurridos(self):
        if self.fecha_inicio_vigencia and self.fecha_fin_vigencia:
            hoy = date.today()
            fecha_comparacion = min(hoy, self.fecha_fin_vigencia)
            if fecha_comparacion >= self.fecha_inicio_vigencia:
                return (fecha_comparacion - self.fecha_inicio_vigencia).days
        return 0

    @property
    def porcentaje_ejecucion_vigencia(self):
        if not self.fecha_inicio_vigencia or not self.fecha_fin_vigencia or self.fecha_fin_vigencia < self.fecha_inicio_vigencia:
            return 0  # O None

        # Duración total en días del contrato
        duracion_total_dias = (self.fecha_fin_vigencia -
                               self.fecha_inicio_vigencia).days + 1
        if duracion_total_dias <= 0:
            return 0  # O None

        # Días transcurridos (usando la propiedad que ya tienes)
        dias_transcurridos = self.dias_vigencia_transcurridos

        if dias_transcurridos is None or dias_transcurridos < 0:  # Debería ser 0 o más
            return 0  # O None

        porcentaje = (Decimal(dias_transcurridos) /
                      Decimal(duracion_total_dias)) * 100
        # Asegurar que esté entre 0 y 100 y redondear a entero
        return min(max(int(porcentaje.quantize(Decimal('1'), rounding=ROUND_HALF_UP)), 0), 100)

    @property
    def esta_vigente(self):
        hoy = date.today()
        # Asegurarse que las fechas no sean None antes de comparar
        if self.fecha_inicio_vigencia and self.fecha_fin_vigencia:
            return (self.fecha_inicio_vigencia <= hoy <= self.fecha_fin_vigencia) and self.estatus == 'VIGENTE'
        return False

    @property
    def monto_cuota_estimada(self):
        cuotas = self.cantidad_cuotas_estimadas

        if self.forma_pago == 'CONTADO':
            return self.monto_total

        if not (isinstance(cuotas, (int, Decimal)) and cuotas > 0):
            return None  # Sale si cuotas no es un número positivo

        if self.monto_total is None or not isinstance(self.monto_total, Decimal):
            return None  # Sale si monto_total no es un Decimal válido

        if self.monto_total > Decimal('0.00'):
            try:
                decimal_cuotas = Decimal(cuotas)
                monto_calculado = (
                    self.monto_total / decimal_cuotas).quantize(Decimal("0.01"), ROUND_HALF_UP)
                return monto_calculado
            except (TypeError, InvalidOperation, ZeroDivisionError) as e:
                logger.error(
                    f"Error en división para monto_cuota_estimada (Contrato {self.pk or 'Nuevo'}): cuotas={repr(cuotas)}, monto_total={repr(self.monto_total)}. Error: {e}")
                return None
        # Si el monto total es exactamente 0
        elif self.monto_total == Decimal('0.00'):
            return Decimal('0.00')
        # monto_total es negativo (aunque los validadores deberían prevenir esto)
        else:
            return None  # O manejar de otra forma si un monto total negativo es posible y tiene sentido

    @property
    def duracion_calculada_meses(self):
        if self.fecha_inicio_vigencia and self.fecha_fin_vigencia and self.fecha_fin_vigencia >= self.fecha_inicio_vigencia:
            delta = relativedelta(
                self.fecha_fin_vigencia + timedelta(days=1), self.fecha_inicio_vigencia)
            meses = delta.years * 12 + delta.months
            # Si hay días restantes y queremos redondear al mes siguiente o contar el mes parcial
            if delta.days > 0 and meses == 0:  # Menos de un mes pero hay días
                return 1
            elif delta.days > 15:  # Si son más de 15 días del último mes completo
                meses += 1
            # Asegurar al menos 1 si hay un rango de fechas válido
            return max(1, meses)
        elif self.periodo_vigencia_meses:  # Si ya está almacenado, usarlo
            return self.periodo_vigencia_meses
        return None

    @property
    def dias_vigencia_restantes(self):
        """Calcula los días restantes de vigencia del contrato si está vigente."""
        if self.fecha_fin_vigencia and self.estatus == 'VIGENTE':  # Solo si está vigente
            hoy = date.today()
            if hoy <= self.fecha_fin_vigencia:
                return (self.fecha_fin_vigencia - hoy).days
        return 0  # O None si prefieres indicar que no aplica

    @property
    def necesita_renovacion_pronto(self, dias_umbral=60):
        """Indica si el contrato necesita renovación pronto (ej. <60 días para vencer)."""
        if self.estatus == 'VIGENTE' and self.fecha_fin_vigencia:
            dias_restantes = self.dias_vigencia_restantes
            if dias_restantes is not None and dias_restantes < dias_umbral:
                return True
        return False

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['ramo', 'estatus']),
            models.Index(fields=['intermediario']),
            models.Index(
                fields=['fecha_inicio_vigencia', 'fecha_fin_vigencia']),
            models.Index(fields=['suma_asegurada', 'estatus']),
            models.Index(fields=['numero_contrato']),
            models.Index(fields=['numero_poliza']),
            models.Index(fields=['certificado'])
        ] + ModeloBase.Meta.indexes
        ordering = ['-fecha_emision']

# ---------------------------
# Afiliado Individual (Corregido)
# ---------------------------


class AfiliadoIndividual(ModeloBase):
    from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField, EncryptedEmailField, EncryptedDateField
    intermediario = models.ForeignKey(
        'Intermediario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='afiliados_individuales_asignados',
        verbose_name="Intermediario Asignado Directamente",
        help_text="Intermediario directamente asignado a la gestión de este afiliado individual (si aplica)."
    )
    tipo_identificacion = models.CharField(
        max_length=20,
        choices=CommonChoices.TIPO_IDENTIFICACION,
        verbose_name="Tipo de Identificación",
        db_index=True,
        help_text="Tipo de documento de identidad principal del afiliado."
    )
    cedula = EncryptedCharField(
        verbose_name="Cédula de Identidad",
        help_text=(
            "Cédula de Identidad del afiliado. Formato: V-12345678 o E-8765432 (guion opcional)."),
        validators=[validate_cedula]
    )
    cedula_hash = models.CharField(
        max_length=64,  # SHA-256 produce un hash de 64 caracteres hexadecimales
        unique=True,    # Esta restricción SÍ se aplicará en la BD y será rápida
        db_index=True,  # Indexar para búsquedas aún más rápidas
        null=False,      # Temporalmente permitimos null para la migración
        blank=True,
        editable=False,
        verbose_name="Hash de la Cédula (para búsquedas)"
    )
    estado_civil = models.CharField(
        max_length=50,
        choices=CommonChoices.ESTADO_CIVIL,
        default='S',
        verbose_name="Estado Civil",
        db_index=True,
        help_text="Estado civil actual del afiliado."
    )
    sexo = models.CharField(
        max_length=50,
        choices=CommonChoices.SEXO,
        verbose_name="Sexo",
        db_index=True,
        help_text="Sexo biológico del afiliado."
    )
    parentesco = models.CharField(
        max_length=50,
        choices=CommonChoices.PARENTESCO,
        verbose_name="Parentesco",
        db_index=True,
        default='TITULAR',
        help_text="Relación del afiliado con el titular del contrato (si aplica, por defecto Titular)."
    )
    fecha_nacimiento = EncryptedDateField(
        verbose_name="Fecha de Nacimiento",
        validators=[validate_past_date],
        help_text="Fecha de nacimiento del afiliado. Formato: AAAA-MM-DD."
    )
    nacionalidad = models.CharField(
        max_length=50,
        verbose_name="Nacionalidad",
        default='Venezolano',
        db_index=True,
        help_text="País de nacionalidad del afiliado."
    )
    zona_postal = models.CharField(
        max_length=4,
        verbose_name="Zona Postal",
        blank=True,
        null=True,
        help_text="Código postal venezolano de 4 dígitos (Ej: 1010)."
    )
    estado = models.CharField(
        max_length=50,
        choices=CommonChoices.ESTADOS_VE,
        verbose_name="Estado",
        blank=False, null=False,
        db_index=True,
        help_text="Estado o región de residencia principal en Venezuela."
    )
    municipio = models.CharField(
        max_length=100,
        verbose_name="Municipio",
        blank=True, null=True,
        help_text="Municipio de residencia (complementario al estado)."
    )
    ciudad = models.CharField(
        max_length=100,
        verbose_name="Ciudad",
        blank=True, null=True,
        help_text="Ciudad de residencia (complementario al estado/municipio)."
    )
    fecha_ingreso = models.DateField(
        verbose_name="Fecha de Ingreso",
        blank=True,
        null=True,
        db_index=True,
        help_text="Fecha en que el afiliado ingresó al sistema o al contrato asociado."
    )
    direccion_habitacion = EncryptedTextField(
        verbose_name="Dirección Habitación",
        blank=True,
        null=True,
        help_text=("Dirección completa de residencia. Mínimo 10 caracteres.")
    )
    telefono_habitacion = EncryptedCharField(
        verbose_name="Teléfono Habitación",
        blank=True,
        null=True,
        help_text="Teléfono de contacto residencial. Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",
    )
    email = EncryptedEmailField(
        verbose_name="Correo Electrónico",
        blank=True,
        null=True,
        help_text="Correo electrónico personal del afiliado (opcional)."
    )
    direccion_oficina = EncryptedTextField(
        verbose_name="Dirección Oficina",
        blank=True,
        null=True,
        help_text="Dirección del lugar de trabajo del afiliado (opcional)."
    )
    telefono_oficina = EncryptedCharField(
        verbose_name="Teléfono Oficina",
        blank=True,
        null=True,
        help_text="Teléfono de contacto laboral. Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",
    )
    codigo_validacion = models.CharField(
        max_length=100,
        verbose_name="Validación Mes/Año",
        blank=True,
        null=True,
        editable=False,
        help_text="Código específico para validaciones periódicas (ej. Mes/Año)."
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Estado activo",
        help_text="Indica si el afiliado está activo en el sistema."
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    @property
    def nombre_completo(self):
        nombres = f"{self.primer_nombre} {self.segundo_nombre}".strip()
        apellidos = f"{self.primer_apellido} {self.segundo_apellido}".strip()
        return f"{apellidos}, {nombres}".strip()

    @property
    def edad(self):
        hoy = django_timezone.now().date()
        return hoy.year - self.fecha_nacimiento.year - ((hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    # Renombrado para evitar colisión con el de Contrato
    def _generar_codigo_validacion(self):
        print(
            f"    AF-IND (PK:{self.pk or 'Nuevo'}) GENERANDO CODIGO VALIDACION...")
        fecha_val = django_timezone.now()
        mes_ano_str = fecha_val.strftime("%m%y")  # MMYY

        pk_str = str(self.pk) if self.pk else "NVO"  # "NVO" para nuevo
        seq_name = f"val_afi_{pk_str}_{mes_ano_str}"

        try:
            next_val = get_next_value(seq_name, initial_value=1)
            codigo = f"VAL-AFI{pk_str}-{mes_ano_str}-{next_val:02d}"
            print(
                f"    AF-IND (PK:{self.pk or 'Nuevo'}) _generar_codigo_validacion - Generado: {codigo}")
            return codigo
        except Exception as e:
            print(
                f"    AF-IND (PK:{self.pk or 'Nuevo'}) _generar_codigo_validacion - EXCEPCIÓN: {e}")
            timestamp = django_timezone.now().strftime("%H%M%S")
            return f"VAL-AFI-ERR-{mes_ano_str}-{timestamp}"

    # --- MÉTODO 'save' CORREGIDO Y COMPLETO ---
    def save(self, *args, **kwargs):
        # Generar el hash ANTES de cualquier otra cosa.
        if self.cedula:
            self.cedula_hash = hashlib.sha256(
                self.cedula.encode('utf-8')).hexdigest()
        else:
            self.cedula_hash = None

        # El resto de tu lógica de save original
        is_new = self._state.adding
        if is_new and not self.codigo_validacion:
            self.codigo_validacion = self._generar_codigo_validacion()
            self._cv_needs_update_post_save = True
        else:
            self._cv_needs_update_post_save = False

        super().save(*args, **kwargs)

        if hasattr(self, '_cv_needs_update_post_save') and self._cv_needs_update_post_save and self.pk:
            new_cv = self._generar_codigo_validacion()
            if self.codigo_validacion != new_cv:
                AfiliadoIndividual.objects.filter(
                    pk=self.pk).update(codigo_validacion=new_cv)
                self.codigo_validacion = new_cv
            del self._cv_needs_update_post_save

    class Meta:
        verbose_name = "Afiliado Individual"
        verbose_name_plural = "Afiliados Individuales"
        indexes = [
            models.Index(fields=['primer_apellido', 'primer_nombre']),
            models.Index(fields=['fecha_nacimiento']),
            models.Index(fields=['fecha_ingreso']),
        ]
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido} ({self.cedula})"

    def clean(self):
        super().clean()
        hoy = date.today()

        if self.fecha_nacimiento:
            if self.fecha_nacimiento > hoy:
                raise ValidationError(
                    {'fecha_nacimiento': "Fecha de nacimiento no puede ser futura"})

        if self.fecha_ingreso:
            if self.fecha_ingreso > hoy:
                raise ValidationError(
                    {'fecha_ingreso': "Fecha de ingreso no puede ser futura"})
            if self.fecha_nacimiento and self.fecha_ingreso < self.fecha_nacimiento:
                raise ValidationError(
                    {'fecha_ingreso': "Fecha de ingreso no puede ser anterior a la fecha de nacimiento."})

    @classmethod
    def con_relaciones(cls):
        """Optimizado para consultas relacionadas"""
        return cls.objects.select_related(
            'contratos__intermediario'
        ).prefetch_related(
            'contratos'  # Prefetch para relaciones inversas
        )

# ---------------------------
# AfiliadoColectivo
# ---------------------------


class AfiliadoColectivo(ModeloBase):
    from encrypted_model_fields.fields import EncryptedTextField, EncryptedEmailField, EncryptedCharField
    # === Campos de empresa ===
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Indica si el registro de este afiliado colectivo (empresa) está activo."

    )

    intermediario = models.ForeignKey(
        'Intermediario',
        on_delete=models.SET_NULL,  # O PROTECT si es obligatorio
        null=True,  # Permite que no tenga uno asignado inicialmente
        blank=True,
        related_name='afiliados_colectivos_asignados',
        verbose_name="Intermediario Asignado Directamente",
        help_text="Intermediario directamente asignado a la gestión de esta empresa (si aplica)."

    )

    razon_social = EncryptedCharField(
        verbose_name="Razón Social",
        null=False,
        blank=False,
        help_text="Nombre legal completo de la empresa o institución."
    )

    rif = EncryptedCharField(
        verbose_name="RIF",
        null=True,
        blank=True,
        default=None,
        validators=[validate_rif],
        help_text="RIF de la empresa. Formato Requerido: Letra-8Números-1Número (Ej: J-12345678-9).",
    )
    rif_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        null=False,     # Requerido para la 1ra migración
        blank=True,
        editable=False,
        verbose_name="Hash del RIF (para búsquedas)"
    )
    tipo_empresa = models.CharField(
        max_length=50,
        choices=CommonChoices.TIPO_EMPRESA,
        verbose_name="Tipo de Empresa",
        default='PRIVADA',
        help_text="Clasificación de la empresa (ej. Pública, Privada)."
    )

    # === Dirección comercial ===
    direccion_comercial = EncryptedTextField(
        verbose_name="Dirección Fiscal",
        help_text="Ej: Av. Principal, Edif. Torreón, Piso 5, Municipio Chacao",
        blank=True,
        null=True
    )
    estado = models.CharField(
        max_length=50,
        choices=CommonChoices.ESTADOS_VE,
        verbose_name=("Estado"),
        blank=False, null=False,
        help_text="Estado o región donde se ubica la sede principal en Venezuela."
    )
    municipio = models.CharField(
        max_length=100,
        verbose_name=("Municipio"),
        blank=True,
        null=True,

        help_text="Municipio donde se ubica la sede (complementario al estado)."
    )
    ciudad = models.CharField(
        max_length=100,
        verbose_name=("Ciudad"),
        blank=True,
        null=True,

        help_text="Ciudad donde se ubica la sede (complementario al estado/municipio)."
    )
    zona_postal = models.CharField(
        max_length=4,
        verbose_name="Zona Postal",
        blank=True,
        null=True,
        # <-- EXISTENTE
        help_text="Código postal venezolano de 4 dígitos (Ej: 1010)."
    )
    telefono_contacto = EncryptedCharField(
        verbose_name="Teléfono Principal",
        validators=[validate_telefono_venezuela],
        blank=True,
        help_text="Número de teléfono principal de contacto. Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",  # <-- MODIFICADO
        null=True
    )
    email_contacto = EncryptedEmailField(
        verbose_name="Email Corporativo",
        blank=True,
        null=True,
        validators=[validate_email],
        help_text="Correo electrónico principal de contacto de la empresa."
    )

    @property
    def nombre_completo(self):
        return self.razon_social

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def save(self, *args, **kwargs):
        # --- 1. Generar hash para RIF ---
        if self.rif:
            self.rif_hash = hashlib.sha256(
                self.rif.encode('utf-8')).hexdigest()
        else:
            self.rif_hash = None

        # --- 2. Lógica original para llenar nombres ---
        # No depende de si es nuevo o no, así que se puede ejecutar siempre.
        if not self.primer_nombre and self.razon_social:
            self.primer_nombre = self.razon_social[:100]
        if not self.primer_apellido:
            self.primer_apellido = "(Colectivo)"

        # --- 3. Llamada final al save() de la clase padre ---
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Afiliado Colectivo"
        verbose_name_plural = "Afiliados Colectivos"
        indexes = [
            models.Index(fields=['razon_social']),
            models.Index(fields=['activo']),
        ]

    def __str__(self):
        return f"{self.razon_social} (RIF: {self.rif})"

    @classmethod
    def con_relaciones(cls):
        return cls.objects.prefetch_related(
            'contratos_afiliados__reclamacion_set'  # Corregido related_name
        )


# ---------------------------
# Contrato Individual (Optimizado)
# ---------------------------


class ContratoIndividual(ContratoBase):
    from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField, EncryptedEmailField
    activo = models.BooleanField(default=True, verbose_name="Estado activo",
                                 help_text="Indica si este registro de contrato individual está activo en el sistema.")
    tipo_identificacion_contratante = models.CharField(
        max_length=20,
        choices=CommonChoices.TIPO_IDENTIFICACION,
        verbose_name="Tipo de Identificación del Contratante",

        help_text="Tipo de documento (Cédula o RIF) de la persona o entidad que paga el contrato."
    )
    contratante_cedula = EncryptedCharField(
        verbose_name="Cédula/RIF del Contratante",
        help_text="Cédula o RIF de quien paga. Introduzca V/E + 7-8 dígitos (Cédula) o J/G/V/E + 8 dígitos + verificador (RIF, formato con guiones requerido).",
    )
    contratante_nombre = EncryptedCharField(
        verbose_name="Nombre del Contratante",
        help_text="Nombre completo o razón social de quien paga el contrato."
    )
    direccion_contratante = EncryptedTextField(
        verbose_name="Dirección del Contratante",
        blank=True,
        null=True,
        help_text="Dirección fiscal o principal del contratante."
    )
    telefono_contratante = EncryptedCharField(
        verbose_name="Teléfono del Contratante",
        blank=True,
        null=True,
        help_text="Teléfono de contacto del contratante. Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",
        validators=[validate_telefono_venezuela]
    )
    email_contratante = EncryptedEmailField(
        verbose_name="Email del Contratante",
        blank=True,
        null=True,
        help_text="Correo electrónico principal del contratante.",
        validators=[validate_email]
    )
    afiliado = models.ForeignKey(
        'AfiliadoIndividual',
        on_delete=models.PROTECT,
        related_name='contratos',
        verbose_name="Afiliado Individual",
        db_index=True,
        help_text="Afiliado individual principal cubierto por este contrato."
    )
    plan_contratado = models.CharField(
        max_length=255,
        verbose_name="Plan Contratado",
        blank=True,
        null=True,
        help_text="Nombre o código del plan de cobertura específico adquirido."
    )
    numero_recibo = models.CharField(
        max_length=50,  # Para REC-IND- + 8 dígitos
        verbose_name="Número de Recibo Individual",
        unique=True,
        blank=True,
        editable=False,
        db_index=True,
        help_text="Formato: REC-IND-XXXXXXXX (Auto-generado)."
    )
    comision_recibo = models.DecimalField(
        max_digits=5,  # OJO: Verificar si 5 es suficiente para monto, o si es %
        decimal_places=2,
        blank=True,
        null=True,

        help_text="Monto (o porcentaje) de la comisión calculado por recibo (si aplica)."
    )
    certificado = models.CharField(
        max_length=50,  # Ajusta si es necesario (CERT-IND- + 6 = 15)
        verbose_name="Número de Certificado",
        unique=True,
        blank=True,
        editable=False,
        db_index=True,
        help_text="Formato: CERT-IND-XXXXXX (Auto-generado).",
        null=True  # Mantener si estaba, aunque blank=True/editable=False lo hacen menos necesario
    )
    fecha_inicio_vigencia_recibo = models.DateField(
        verbose_name="Fecha Inicio Vigencia Recibo",
        blank=True,
        null=True,
        help_text="Fecha de inicio de la cobertura del recibo actual o próximo."
    )
    fecha_fin_vigencia_recibo = models.DateField(
        verbose_name="Fecha Fin Vigencia Recibo",
        blank=True,
        null=True,
        help_text="Fecha de fin de la cobertura del recibo actual o próximo."
    )
    criterio_busqueda = models.CharField(
        max_length=255,
        verbose_name="Criterio de Búsqueda",
        blank=True,
        null=True,
        help_text="Campo adicional para búsquedas o filtros personalizados."
    )
    dias_transcurridos_ingreso = models.IntegerField(
        verbose_name="Días transcurridos desde ingreso",
        blank=True,
        null=True,
        help_text="Número de días desde que el afiliado ingresó (calculado o registrado)."
    )
    estatus_detalle = models.TextField(
        verbose_name="Estatus Detallado",
        blank=True,
        null=True,
        help_text="Descripción más detallada del estado actual del contrato."
    )
    estatus_emision_recibo = models.CharField(
        max_length=20,
        choices=CommonChoices.EMISION_RECIBO,
        default='SIN_EMITIR',
        verbose_name="Estatus de Emisión del Recibo",
        db_index=True,
        help_text="Indica si el recibo actual o próximo ha sido generado."
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def puede_eliminarse(self):
        return not (self.factura_set.exists() or self.reclamacion_set.exists())

    def clean(self):
        super().clean()
        error_messages = {}

        tipo_id_contratante_valor = self.tipo_identificacion_contratante
        numero_documento_contratante = self.contratante_cedula

        if tipo_id_contratante_valor and not numero_documento_contratante:
            error_messages.setdefault('contratante_cedula', []).append(
                "El número de documento es obligatorio si se selecciona un tipo de identificación."
            )
        elif numero_documento_contratante:
            if tipo_id_contratante_valor == 'CEDULA':
                try:
                    validate_cedula(numero_documento_contratante)
                except ValidationError as e:
                    error_messages.setdefault('contratante_cedula', []).extend(
                        e.messages if hasattr(e, 'messages') else [str(e)]
                    )
            elif tipo_id_contratante_valor == 'RIF':
                try:
                    validate_rif(numero_documento_contratante)
                except ValidationError as e:
                    error_messages.setdefault('contratante_cedula', []).extend(
                        e.messages if hasattr(e, 'messages') else [str(e)]
                    )
            elif tipo_id_contratante_valor == 'PASAPORTE':
                try:
                    validate_pasaporte(numero_documento_contratante)
                except ValidationError as e:
                    error_messages.setdefault('contratante_cedula', []).extend(
                        e.messages if hasattr(e, 'messages') else [str(e)]
                    )
        elif not numero_documento_contratante and not self._meta.get_field('contratante_cedula').blank:
            error_messages.setdefault('contratante_cedula', []).append(
                "Este campo es obligatorio.")

        # --- Validación de fechas del contrato ---
        # Los campos de fecha del modelo ya son objetos date o datetime (aware si USE_TZ=True)
        fecha_emision_obj = self.fecha_emision
        fecha_inicio_vigencia_obj = self.fecha_inicio_vigencia
        fecha_fin_vigencia_obj = self.fecha_fin_vigencia

        # Obtener solo la parte de la fecha para comparaciones si son datetime
        fecha_emision_date = None
        if isinstance(fecha_emision_obj, datetime):
            fecha_emision_date = django_timezone.localtime(fecha_emision_obj).date(
            ) if django_timezone.is_aware(fecha_emision_obj) else fecha_emision_obj.date()
        elif isinstance(fecha_emision_obj, date):
            fecha_emision_date = fecha_emision_obj

        fecha_inicio_vigencia_date = None
        if isinstance(fecha_inicio_vigencia_obj, datetime):
            fecha_inicio_vigencia_date = django_timezone.localtime(fecha_inicio_vigencia_obj).date(
            ) if django_timezone.is_aware(fecha_inicio_vigencia_obj) else fecha_inicio_vigencia_obj.date()
        elif isinstance(fecha_inicio_vigencia_obj, date):
            fecha_inicio_vigencia_date = fecha_inicio_vigencia_obj

        fecha_fin_vigencia_date = None
        if isinstance(fecha_fin_vigencia_obj, datetime):
            fecha_fin_vigencia_date = django_timezone.localtime(fecha_fin_vigencia_obj).date(
            ) if django_timezone.is_aware(fecha_fin_vigencia_obj) else fecha_fin_vigencia_obj.date()
        elif isinstance(fecha_fin_vigencia_obj, date):
            fecha_fin_vigencia_date = fecha_fin_vigencia_obj

        if fecha_emision_date and fecha_inicio_vigencia_date and fecha_emision_date > fecha_inicio_vigencia_date:
            error_messages.setdefault('fecha_emision', []).append(
                "La fecha de emisión no puede ser posterior a la fecha de inicio de vigencia."
            )

        if fecha_inicio_vigencia_date and fecha_fin_vigencia_date:
            if fecha_fin_vigencia_date < fecha_inicio_vigencia_date:
                error_messages.setdefault('fecha_fin_vigencia', []).append(
                    "La fecha de fin de vigencia no puede ser anterior a la fecha de inicio."
                )
            if self.periodo_vigencia_meses is not None:
                try:
                    # Asegurarse que periodo_vigencia_meses es un entero
                    periodo_meses_int = int(self.periodo_vigencia_meses)
                    fin_calculado_desde_periodo = fecha_inicio_vigencia_date + \
                        relativedelta(months=+periodo_meses_int) - \
                        timedelta(days=1)
                    if fin_calculado_desde_periodo != fecha_fin_vigencia_date:
                        error_messages.setdefault('fecha_fin_vigencia', []).append(
                            f"La fecha de fin ({fecha_fin_vigencia_date.strftime('%d/%m/%Y')}) no coincide con la duración de {periodo_meses_int} meses "
                            f"(que resultaría en {fin_calculado_desde_periodo.strftime('%d/%m/%Y')})."
                        )
                except (TypeError, ValueError):
                    error_messages.setdefault('periodo_vigencia_meses', []).append(
                        "La duración en meses debe ser un número entero válido.")

        # --- Validaciones para fechas de recibo ---
        fecha_inicio_recibo_obj = self.fecha_inicio_vigencia_recibo
        fecha_fin_recibo_obj = self.fecha_fin_vigencia_recibo

        fecha_inicio_recibo_date = None
        if isinstance(fecha_inicio_recibo_obj, datetime):
            fecha_inicio_recibo_date = django_timezone.localtime(fecha_inicio_recibo_obj).date(
            ) if django_timezone.is_aware(fecha_inicio_recibo_obj) else fecha_inicio_recibo_obj.date()
        elif isinstance(fecha_inicio_recibo_obj, date):
            fecha_inicio_recibo_date = fecha_inicio_recibo_obj

        fecha_fin_recibo_date = None
        if isinstance(fecha_fin_recibo_obj, datetime):
            fecha_fin_recibo_date = django_timezone.localtime(fecha_fin_recibo_obj).date(
            ) if django_timezone.is_aware(fecha_fin_recibo_obj) else fecha_fin_recibo_obj.date()
        elif isinstance(fecha_fin_recibo_obj, date):
            fecha_fin_recibo_date = fecha_fin_recibo_obj

        if fecha_inicio_recibo_date and fecha_inicio_vigencia_date and fecha_inicio_recibo_date < fecha_inicio_vigencia_date:
            error_messages.setdefault('fecha_inicio_vigencia_recibo', []).append(
                "El inicio de vigencia del recibo no puede ser anterior al inicio de vigencia del contrato."
            )

        fecha_final_efectiva_contrato = fecha_fin_vigencia_date
        if not fecha_final_efectiva_contrato and fecha_inicio_vigencia_date and self.periodo_vigencia_meses:
            try:
                periodo_meses_int = int(self.periodo_vigencia_meses)
                fecha_final_efectiva_contrato = fecha_inicio_vigencia_date + \
                    relativedelta(months=+periodo_meses_int) - \
                    timedelta(days=1)
            except (TypeError, ValueError):
                pass  # Error ya manejado para periodo_vigencia_meses

        if fecha_fin_recibo_date and fecha_final_efectiva_contrato and fecha_fin_recibo_date > fecha_final_efectiva_contrato:
            error_messages.setdefault('fecha_fin_vigencia_recibo', []).append(
                "El fin de vigencia del recibo no puede ser posterior al fin de vigencia del contrato."
            )

        if fecha_inicio_recibo_date and fecha_fin_recibo_date and fecha_fin_recibo_date < fecha_inicio_recibo_date:
            error_messages.setdefault('fecha_fin_vigencia_recibo', []).append(
                "La fecha de fin de vigencia del recibo no puede ser anterior a su fecha de inicio."
            )

        if error_messages:
            raise ValidationError(error_messages)

    def _generar_recibo_inicial_contrato(self):
        # print(f"    CI (PK:{self.pk or 'Nuevo'}) GENERANDO RECIBO INICIAL...")
        fecha_em = self.fecha_emision or django_timezone.now()
        fecha_em_str_aa = fecha_em.strftime("%y%m%d")

        nc_parte = "SCN"
        if self.numero_contrato and '-' in self.numero_contrato:
            try:
                partes_nc = self.numero_contrato.split('-')
                nc_parte = partes_nc[-1][:4] if partes_nc[-1] else "XXXX"
            except:
                nc_parte = str(self.pk or "NVO")[:4].zfill(4)
        elif self.pk:
            nc_parte = str(self.pk)[:4].zfill(4)
        else:
            nc_parte = "NVO0"

        seq_name = f"ci_rec_ini_{nc_parte}_{fecha_em_str_aa}"
        prefijo = f"REC-IND-{nc_parte}-EM{fecha_em_str_aa}-"
        return generar_codigo_unico(seq_name, prefijo, 2, fallback_prefix=f"REC-IND-ERR-{fecha_em_str_aa}")

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        self._monto_total_pre_calculado_por_hijo = False

        # --- 1. Sincronizar datos del Afiliado ---
        # Es bueno hacerlo primero para que otros cálculos puedan usar los nombres.
        if self.afiliado:
            if is_new or not self.primer_nombre:
                self.primer_nombre = self.afiliado.primer_nombre
                self.segundo_nombre = self.afiliado.segundo_nombre
                self.primer_apellido = self.afiliado.primer_apellido
                self.segundo_apellido = self.afiliado.segundo_apellido

        # --- 2. Manejo de Fechas y Vigencia ---
        # Asegurar que fecha_emision sea 'aware'
        if self.fecha_emision and django_timezone.is_naive(self.fecha_emision):
            self.fecha_emision = django_timezone.make_aware(
                self.fecha_emision, django_timezone.get_current_timezone())
        elif is_new and not self.fecha_emision:
            self.fecha_emision = django_timezone.now()

        # Establecer fecha de inicio si no existe
        if not self.fecha_inicio_vigencia and self.fecha_emision:
            self.fecha_inicio_vigencia = self.fecha_emision.date()

        # Sincronizar periodo_vigencia_meses y fecha_fin_vigencia
        if self.fecha_inicio_vigencia and relativedelta:
            if self.periodo_vigencia_meses and isinstance(self.periodo_vigencia_meses, int) and self.periodo_vigencia_meses > 0:
                self.fecha_fin_vigencia = self.fecha_inicio_vigencia + \
                    relativedelta(
                        months=+self.periodo_vigencia_meses) - timedelta(days=1)
            elif self.fecha_fin_vigencia and self.fecha_fin_vigencia >= self.fecha_inicio_vigencia:
                delta = relativedelta(
                    self.fecha_fin_vigencia + timedelta(days=1), self.fecha_inicio_vigencia)
                meses_calculados = delta.years * 12 + delta.months
                if delta.days > 15:
                    meses_calculados += 1
                elif delta.days > 0 and meses_calculados == 0:
                    meses_calculados = 1
                self.periodo_vigencia_meses = max(1, meses_calculados)
            elif is_new:
                self.periodo_vigencia_meses = 12
                self.fecha_fin_vigencia = self.fecha_inicio_vigencia + \
                    relativedelta(months=+12) - timedelta(days=1)

        # --- 3. Generación de Códigos Únicos para instancias nuevas ---
        if is_new:
            if not self.numero_contrato:
                self.numero_contrato = f"CONT-IND-{uuid.uuid4().hex[:12].upper()}"
            if not self.numero_poliza:
                self.numero_poliza = f"POL-IND-{uuid.uuid4().hex[:12].upper()}"
            if not self.certificado:
                self.certificado = f"CERT-IND-{uuid.uuid4().hex[:12].upper()}"
            if not self.numero_recibo:
                fecha_recibo_str = (
                    self.fecha_emision or django_timezone.now()).strftime("%y%m%d")
                self.numero_recibo = f"REC-IND-{fecha_recibo_str}-{uuid.uuid4().hex[:10].upper()}"

        # --- 4. Cálculos finales ---
        if self.afiliado and self.afiliado.fecha_ingreso and self.fecha_emision:
            self.dias_transcurridos_ingreso = (self.fecha_emision.date(
            ) - self.afiliado.fecha_ingreso).days if self.fecha_emision.date() >= self.afiliado.fecha_ingreso else 0
        else:
            self.dias_transcurridos_ingreso = None

        # --- 5. Llamada final al save() de la clase padre ---
        # ContratoBase.save() se encargará del cálculo de monto_total.
        super().save(*args, **kwargs)

    def generate_contract_number(self):
        with transaction.atomic():  # Transacción atómica completa
            try:
                current_date = django_timezone.now().strftime("%y%m%d")
                seq_name = f'ci_{current_date}'

                logger.debug(
                    f"[Generate Contract Num - Ind] Secuencia: {seq_name}")
                next_val = get_next_value(seq_name, initial_value=1)

                return f"CONT-IND-{django_timezone.now().strftime('%Y%m%d')}-{next_val:04d}"

            except Exception as e:
                logger.exception(
                    f"Error generando número de contrato individual: {e}")
                timestamp = django_timezone.now().strftime("%Y%m%d%H%M%S")
                unique_id = uuid.uuid4().hex[:6]  # ID más corto pero único
                return f"ERR-CI-{timestamp}-{unique_id}"

    def generate_policy_number(self):
        with transaction.atomic():  # Transacción atómica completa
            try:
                current_date = django_timezone.now().strftime("%y%m%d")
                seq_name = f'pi_{current_date}'

                logger.debug(
                    f"[Generate Policy Num - Ind] Secuencia: {seq_name}")
                next_val = get_next_value(seq_name, initial_value=1)

                return f"POL-IND-{django_timezone.now().strftime('%Y%m%d')}-{next_val:04d}"

            except Exception as e:
                logger.exception(
                    f"Error generando número de póliza individual: {e}")
                timestamp = django_timezone.now().strftime("%Y%m%d%H%M%S")
                unique_id = uuid.uuid4().hex[:6]
                return f"ERR-PI-{timestamp}-{unique_id}"

    @classmethod
    def con_relaciones(cls):
        return cls.objects.select_related('intermediario', 'afiliado').prefetch_related(
            Prefetch('reclamacion_set', queryset=Reclamacion.objects.select_related(
                'usuario_asignado')),
            Prefetch('factura_set',
                     queryset=Factura.objects.prefetch_related('pagos'))
        )

    @property
    def monto_total_pagado_reclamaciones(self):
        # Suma los Pago.monto_pago donde Pago.reclamacion.contrato_individual == self
        total_pagado = Pago.objects.filter(
            reclamacion__contrato_individual=self,  # ESPECÍFICO PARA ContratoIndividual
            activo=True,
            reclamacion__activo=True
        ).aggregate(
            total=Coalesce(Sum('monto_pago'), Decimal(
                '0.00'), output_field=DecimalField())
        )['total']
        return total_pagado.quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def saldo_disponible_cobertura(self):
        if self.suma_asegurada is None:
            return Decimal('0.00')
        consumido = self.monto_total_pagado_reclamaciones
        disponible = self.suma_asegurada - consumido
        return max(Decimal('0.00'), disponible).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def porcentaje_cobertura_consumido(self):
        if not self.suma_asegurada or self.suma_asegurada <= Decimal('0.00'):
            return Decimal('0.0')
        consumido = self.monto_total_pagado_reclamaciones
        if self.suma_asegurada == Decimal('0.00'):
            return Decimal('0.0') if consumido == Decimal('0.00') else Decimal('100.0')
        porcentaje = (consumido / self.suma_asegurada) * Decimal('100.00')
        return porcentaje.quantize(Decimal("0.1"), ROUND_HALF_UP)

    class Meta:
        verbose_name = "Contrato Individual"
        verbose_name_plural = "Contratos Individuales"
        indexes = [
            Index(fields=['estatus']), Index(
                fields=['contratante_cedula']),
            Index(fields=['activo']),  # Índice para campo activo
        ]
        permissions = [('can_anular_contrato', "Puede anular contratos"),
                       ('can_renovar_contrato', "Puede renovar contratos")]
        ordering = ['-fecha_emision']

    def __str__(self):
        afiliado_nombre = f"{self.afiliado.primer_nombre} {self.afiliado.primer_apellido}" if self.afiliado else "Sin Afiliado"
        return f"CI: {self.numero_contrato} - {afiliado_nombre}"


# ---------------------------
# Contrato Colectivo (Optimizado)
# ---------------------------
try:
    from sequences import get_next_value
except ImportError:
    def get_next_value(sequence_name, initial_value=1):  # Fallback simple
        print(
            f"ADVERTENCIA: get_next_value de 'sequences' no encontrado. Usando fallback simple para {sequence_name}.")
        # Esta es una implementación muy básica y NO segura para producción si 'sequences' no está.
        # Deberías asegurar que 'sequences' esté instalado y funcionando.
        # Para propósitos de seeder, podría ser suficiente si se reinicia cada vez.
        if not hasattr(get_next_value, 'counters'):
            get_next_value.counters = {}
        if sequence_name not in get_next_value.counters:
            get_next_value.counters[sequence_name] = initial_value
            return initial_value
        else:
            get_next_value.counters[sequence_name] += 1
            return get_next_value.counters[sequence_name]


class ContratoColectivo(ContratoBase):
    from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField
    activo = models.BooleanField(default=True, verbose_name="Estado activo",
                                 help_text="Indica si este registro de contrato colectivo está activo en el sistema.")
    tipo_empresa = models.CharField(
        max_length=50,
        choices=CommonChoices.TIPO_EMPRESA,
        default='PRIVADA',
        verbose_name="Tipo de Empresa",
        db_index=True,
        help_text="Clasificación de la empresa contratante."
    )
    criterio_busqueda = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Criterio de Búsqueda",
        help_text="Campo adicional para búsquedas o filtros personalizados."
    )
    razon_social = EncryptedCharField(
        verbose_name="Razón Social de la Empresa",
        null=True,
        help_text="Nombre legal completo de la empresa contratante."
    )
    rif = EncryptedCharField(
        verbose_name="RIF de la Empresa (Copiado)",
        validators=[validate_rif],
        help_text="RIF de la empresa contratante (copiado automáticamente).",
        blank=True,
        null=True
    )
    cantidad_empleados = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Cantidad de Empleados",
        db_index=True,
        help_text="Número total de empleados cubiertos o elegibles bajo este contrato."
    )
    direccion_comercial = EncryptedTextField(
        verbose_name="Dirección Comercial",
        blank=True,
        null=True,
        help_text="Dirección principal o fiscal de la empresa contratante."
    )
    zona_postal = models.CharField(
        max_length=4,
        verbose_name="Zona Postal",
        blank=True,
        null=True,
        db_index=True,
        help_text="Código postal venezolano de 4 dígitos (Ej: 1010)."
    )
    plan_contratado = models.CharField(
        max_length=255,
        verbose_name="Plan Contratado",
        blank=True,
        null=True,
        help_text="Nombre o código del plan de cobertura específico adquirido para el colectivo."
    )
    numero_recibo = models.CharField(
        max_length=50,
        verbose_name="Número de Recibo Colectivo",
        unique=True,
        blank=True,
        editable=False,
        db_index=True,
        help_text="Formato: REC-COL-XXXXXXXX (Auto-generado)."
    )
    comision_recibo = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Comisión del Recibo",
        blank=True,
        null=True,
        help_text="Monto numérico de la comisión asociada a este recibo específico."
    )
    codigo_validacion = models.CharField(
        max_length=100,
        verbose_name="Validación Mes/Año",
        blank=True,
        null=True,
        editable=False,
        db_index=True,
        help_text="Código específico para validaciones periódicas (ej. Mes/Año)."
    )
    intermediario = models.ForeignKey(
        'Intermediario',
        on_delete=models.PROTECT,
        verbose_name="Intermediario",
        # Asegúrate que este related_name sea único o deseado
        related_name='contratos_colectivos',
        db_index=True,
        null=True,
        blank=True,
        help_text="Intermediario responsable de la gestión o venta de este contrato."
    )
    afiliados_colectivos = models.ManyToManyField(
        'AfiliadoColectivo',
        verbose_name='Afiliados asociados',
        blank=True,
        help_text='Empresas o grupos afiliados vinculados a este contrato colectivo.',
        related_name='contratos_afiliados'
    )
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def puede_eliminarse(self):
        try:
            reclamaciones_exist = Reclamacion.objects.filter(
                contrato_colectivo=self).exists()
        except NameError:
            reclamaciones_exist = False
        try:
            facturas_exist = self.factura_set.exists()
        except NameError:
            facturas_exist = False
        return not (facturas_exist or reclamaciones_exist or self.afiliados_colectivos.exists())

    def __str__(self):
        rs = self.razon_social or "Sin Razón Social"
        rf = self.rif or "Sin RIF"
        nc = self.numero_contrato or 'PENDIENTE_NUM_CONTRATO'
        return f"CC: {nc} - {rs} ({rf})"

    def generate_contract_number(self):
        print("    ENTRANDO A CC.generate_contract_number")
        final_generated_value = None
        # Nuevo nombre para prueba aún más limpia
        seq_name = 'contrato_colectivo_global_seq_v4'

        try:
            current_datetime_obj = django_timezone.now()
            current_date_str_num = current_datetime_obj.strftime('%Y%m%d')

            print(
                f"    CC.generate_contract_number - Usando seq_name: '{seq_name}'")

            if get_next_value is None:
                print(
                    "    CC.generate_contract_number - ERROR CRÍTICO: get_next_value es None (no importado)!")
                # No lanzar excepción aquí, dejar que el fallback general lo maneje
                # para que el print de "Usando fallback" se muestre.
            else:
                next_val = get_next_value(seq_name, initial_value=1)
                print(
                    f"    CC.generate_contract_number - next_val obtenido de sequences: '{next_val}' (Tipo: {type(next_val)})")

                if next_val is None:
                    print(
                        f"    CC.generate_contract_number - ADVERTENCIA: get_next_value devolvió None para {seq_name}!")
                    # final_generated_value permanecerá None, activando el fallback
                elif isinstance(next_val, int):
                    final_generated_value = f"CONT-COL-{current_date_str_num}-{next_val:04d}"
                else:
                    print(
                        f"    CC.generate_contract_number - ADVERTENCIA: next_val ('{next_val}') no es un entero. No se puede formatear.")
                    # final_generated_value permanecerá None, activando el fallback

            print(
                f"    CC.generate_contract_number - Valor después de formateo (o None si falló): '{final_generated_value}'")

        except Exception as e:
            # Este except captura errores de get_next_value si no es None pero falla, o errores de formateo si no se capturaron antes.
            print(
                f"    CC.generate_contract_number - EXCEPCIÓN DURANTE GENERACIÓN PRINCIPAL: {type(e).__name__} - {e}")
            # final_generated_value sigue siendo None o el valor parcial que tenía, el siguiente if lo manejará.

        # Fallback si final_generated_value sigue siendo None (por error en get_next_value o formateo)
        if not final_generated_value:  # Esto es True si final_generated_value es None o ""
            print(
                f"    CC.generate_contract_number - final_generated_value ('{final_generated_value}') es None o vacío. Usando fallback.")
            timestamp_fallback = django_timezone.now().strftime("%Y%m%d%H%M%S%f")
            unique_id_fallback = uuid.uuid4().hex[:6]
            final_generated_value = f"ERR-CC-{timestamp_fallback}-{unique_id_fallback}"
            print(
                f"    CC.generate_contract_number - Valor de fallback generado: '{final_generated_value}'")

        # Último chequeo para asegurar que no sea una cadena vacía
        if not final_generated_value:
            print(
                f"    CC.generate_contract_number - ERROR FATALÍSIMO: final_generated_value ('{final_generated_value}') sigue vacío después de fallback.")
            final_generated_value = f"ULTRA_FALLO_{django_timezone.now().strftime('%Y%m%d%H%M%S%f')}"

        print(
            f"    CC.generate_contract_number - RETORNANDO: '{final_generated_value}'")
        return str(final_generated_value)  # Asegurar que sea string

    def generate_policy_number(self):
        # Similar a generate_contract_number, pero con prefijo POL-COL y otra secuencia
        print("    ENTRANDO A CC.generate_policy_number")
        final_generated_value = None
        seq_name = 'policy_colectivo_global_seq_v4'
        try:
            current_datetime_obj = django_timezone.now()
            current_date_str_num = current_datetime_obj.strftime('%Y%m%d')
            print(
                f"    CC.generate_policy_number - Usando seq_name: '{seq_name}'")
            if get_next_value is None:
                raise RuntimeError("get_next_value no importado")

            next_val = get_next_value(seq_name, initial_value=1)
            print(f"    CC.generate_policy_number - next_val: '{next_val}'")
            if next_val is None:
                raise ValueError("get_next_value retornó None para póliza")
            if isinstance(next_val, int):
                final_generated_value = f"POL-COL-{current_date_str_num}-{next_val:04d}"
            else:
                print(
                    f"    CC.generate_policy_number - ADVERTENCIA: next_val no es entero.")
        except Exception as e:
            print(f"    CC.generate_policy_number - EXCEPCIÓN: {e}")

        if not final_generated_value:
            print(f"    CC.generate_policy_number - Usando fallback.")
            timestamp_fallback = django_timezone.now().strftime("%Y%m%d%H%M%S%f")
            unique_id_fallback = uuid.uuid4().hex[:6]
            final_generated_value = f"ERR-PC-{timestamp_fallback}-{unique_id_fallback}"

        print(
            f"    CC.generate_policy_number - RETORNANDO: '{final_generated_value}'")
        return str(final_generated_value)

    def _generar_recibo_inicial_contrato(self):
        # print(f"    CC (PK:{self.pk or 'Nuevo'}) GENERANDO RECIBO INICIAL...")
        fecha_em = self.fecha_emision or django_timezone.now()
        fecha_em_str_aa = fecha_em.strftime("%y%m%d")

        nc_parte = "SCN"
        if self.numero_contrato and '-' in self.numero_contrato:
            try:
                partes_nc = self.numero_contrato.split('-')
                nc_parte = partes_nc[-1][:4] if partes_nc[-1] else "XXXX"
            except:
                nc_parte = str(self.pk or "NVO")[:4].zfill(4)
        elif self.pk:
            nc_parte = str(self.pk)[:4].zfill(4)
        else:
            nc_parte = "NVO0"

        seq_name = f"cc_rec_ini_{nc_parte}_{fecha_em_str_aa}"
        prefijo = f"REC-COL-{nc_parte}-EM{fecha_em_str_aa}-"
        return generar_codigo_unico(seq_name, prefijo, 2, fallback_prefix=f"REC-COL-ERR-{fecha_em_str_aa}")

    def _generar_codigo_validacion_contrato(self):
        # print(f"    CC (PK:{self.pk or 'Nuevo'}) GENERANDO CODIGO VALIDACION CONTRATO...")
        fecha_val = django_timezone.now()
        mes_ano_str = fecha_val.strftime("%m%y")
        id_obj_corto = str(self.pk % 1000).zfill(3) if self.pk else "NVO"

        tipo_pref = "CCC"
        seq_name = f"val_{tipo_pref.lower()}_{id_obj_corto}_{mes_ano_str}"
        prefijo = f"VAL-{tipo_pref}{id_obj_corto}-{mes_ano_str}-"
        return generar_codigo_unico(seq_name, prefijo, 2, fallback_prefix=f"VAL-{tipo_pref}-ERR-{mes_ano_str}")

    def _calculate_monto_total_colectivo(self):
        if self.tarifa_aplicada and self.tarifa_aplicada.monto_anual is not None and \
           isinstance(self.tarifa_aplicada.monto_anual, Decimal) and not self.tarifa_aplicada.monto_anual.is_nan() and \
           self.periodo_vigencia_meses and self.periodo_vigencia_meses > 0:

            tarifa_anual_base = self.tarifa_aplicada.monto_anual  # $10,000.00

            # Calcula el costo del plan para la duración del contrato
            # Si periodo_vigencia_meses es 12, esto será igual a tarifa_anual_base.
            # Si es 6 meses, será la mitad, etc.
            costo_del_plan_para_periodo_contrato = (
                tarifa_anual_base / Decimal(12)) * Decimal(self.periodo_vigencia_meses)

            calculated_monto = costo_del_plan_para_periodo_contrato

            return calculated_monto.quantize(Decimal("0.01"), ROUND_HALF_UP)
        return None

# En la clase ContratoColectivo (models.py)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        self._monto_total_pre_calculado_por_hijo = False

        # --- 1. Manejo de Fechas y Vigencia ---
        if self.fecha_emision and django_timezone.is_naive(self.fecha_emision):
            self.fecha_emision = django_timezone.make_aware(
                self.fecha_emision, django_timezone.get_current_timezone())
        elif is_new and not self.fecha_emision:
            self.fecha_emision = django_timezone.now()

        if not self.fecha_inicio_vigencia and self.fecha_emision and is_new:
            self.fecha_inicio_vigencia = self.fecha_emision.date()

        if self.fecha_inicio_vigencia and relativedelta:
            if self.periodo_vigencia_meses and isinstance(self.periodo_vigencia_meses, int) and self.periodo_vigencia_meses > 0:
                self.fecha_fin_vigencia = self.fecha_inicio_vigencia + \
                    relativedelta(
                        months=+self.periodo_vigencia_meses) - timedelta(days=1)
            elif self.fecha_fin_vigencia and self.fecha_fin_vigencia >= self.fecha_inicio_vigencia:
                delta = relativedelta(
                    self.fecha_fin_vigencia + timedelta(days=1), self.fecha_inicio_vigencia)
                meses_calculados = delta.years * 12 + delta.months
                if delta.days > 15:
                    meses_calculados += 1
                elif delta.days > 0 and meses_calculados == 0:
                    meses_calculados = 1
                self.periodo_vigencia_meses = max(1, meses_calculados)
            elif is_new:
                self.periodo_vigencia_meses = 12
                if self.fecha_inicio_vigencia:
                    self.fecha_fin_vigencia = self.fecha_inicio_vigencia + \
                        relativedelta(months=+12) - timedelta(days=1)

        # --- 2. Generación de Códigos Únicos para instancias nuevas ---
        if is_new:
            if not self.numero_contrato:
                self.numero_contrato = f"CONT-COL-{uuid.uuid4().hex[:12].upper()}"
            if not self.numero_poliza:
                self.numero_poliza = f"POL-COL-{uuid.uuid4().hex[:12].upper()}"
            if not self.certificado:
                self.certificado = f"CERT-COL-{uuid.uuid4().hex[:8].upper()}"
            if not self.numero_recibo:
                fecha_recibo_str = (
                    self.fecha_emision or django_timezone.now()).strftime("%y%m%d")
                self.numero_recibo = f"REC-COL-{fecha_recibo_str}-{uuid.uuid4().hex[:10].upper()}"
            if not self.codigo_validacion:
                self.codigo_validacion = f"VAL-CCC-{uuid.uuid4().hex[:12].upper()}"

        # --- 3. Llenar campos de ModeloBase ---
        if not self.primer_nombre and self.razon_social:
            parts = self.razon_social.split(maxsplit=1)
            self.primer_nombre = parts[0][:100]
            self.primer_apellido = f"(Colectivo {self.rif or ''})"[
                :100] if len(parts) > 1 else "(Colectivo)"
        elif not self.primer_nombre:
            self.primer_nombre = "Colectivo Sin Razón Social"
            self.primer_apellido = "(Colectivo)"

        # --- 4. Cálculo de monto_total ---
        monto_colectivo_calculado = self._calculate_monto_total_colectivo()
        if monto_colectivo_calculado is not None:
            self.monto_total = monto_colectivo_calculado
            self._monto_total_pre_calculado_por_hijo = True
        elif self.monto_total is None:
            self.monto_total = Decimal('0.00')

        # --- 5. Llamada final al save() de la clase padre ---
        super().save(*args, **kwargs)

    @classmethod
    def con_relaciones(cls):
        try:
            ReclamacionModel = apps.get_model('myapp', 'Reclamacion')
            FacturaModel = apps.get_model('myapp', 'Factura')
            reclamacion_qs = ReclamacionModel.objects.all()
            factura_qs = FacturaModel.objects.all()
        except LookupError:  # Si los modelos no están definidos aún o no se encuentran
            ReclamacionModel = Reclamacion  # Intentar usar la importación directa
            FacturaModel = Factura
            reclamacion_qs = Reclamacion.objects.none()
            factura_qs = Factura.objects.none()
        except NameError:  # Si Reclamacion o Factura no están en el scope global
            reclamacion_qs = apps.get_model(
                'myapp', 'Reclamacion').objects.none()
            factura_qs = apps.get_model('myapp', 'Factura').objects.none()

        return cls.objects.select_related('intermediario').prefetch_related(
            Prefetch('afiliados_colectivos'),
            Prefetch('reclamacion_set', queryset=reclamacion_qs),
            Prefetch('factura_set', queryset=factura_qs)
        )

    @property
    def saldo_pendiente_contrato(self):  # Para el "Resumen Financiero"
        if not self.monto_total or self.monto_total < Decimal('0.00'):
            return Decimal('0.00')
        pendiente = self.monto_total - \
            self.total_pagado_a_facturas  # Usa la property anterior
        return max(Decimal('0.00'), pendiente).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def monto_total_pagado_reclamaciones(self):  # Para "Consumo de Cobertura"
        # Asumiendo que Pago tiene una FK a Reclamacion llamada 'reclamacion'
        # y Reclamacion tiene una FK a ContratoColectivo llamada 'contrato_colectivo'
        total_pagado = Pago.objects.filter(
            reclamacion__contrato_colectivo=self,
            activo=True,
            reclamacion__activo=True  # Opcional: si las reclamaciones pueden estar inactivas
        ).aggregate(
            total=Coalesce(Sum('monto_pago'), Decimal(
                '0.00'), output_field=DecimalField())
        )['total']
        return total_pagado.quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def saldo_disponible_cobertura(self):  # Para "Consumo de Cobertura"
        if self.suma_asegurada is None:
            return Decimal('0.00')
        consumido = self.monto_total_pagado_reclamaciones
        disponible = self.suma_asegurada - consumido
        return max(Decimal('0.00'), disponible).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def porcentaje_cobertura_consumido(self):  # Para "Consumo de Cobertura"
        if not self.suma_asegurada or self.suma_asegurada <= Decimal('0.00'):
            return Decimal('0.0')
        consumido = self.monto_total_pagado_reclamaciones
        # Evitar división por cero si suma_asegurada es 0 pero hubo consumo (caso anómalo)
        if self.suma_asegurada == Decimal('0.00'):
            return Decimal('0.0') if consumido == Decimal('0.00') else Decimal('100.0')

        porcentaje = (consumido / self.suma_asegurada) * Decimal('100.00')
        return porcentaje.quantize(Decimal("0.1"), ROUND_HALF_UP)

    class Meta:
        verbose_name = "Contrato Colectivo"
        verbose_name_plural = "Contratos Colectivos"
        indexes = [
            models.Index(fields=['tipo_empresa', 'cantidad_empleados']),
            models.Index(fields=['fecha_emision', 'monto_total']),
            models.Index(fields=['rif']),
            models.Index(fields=['activo']),
            models.Index(fields=['tarifa_aplicada'])
        ]
        ordering = ['-fecha_emision']
# ---------------------------
# Intermediario (Optimizado con prefetch)
# ---------------------------


class Intermediario(ModeloBase):
    from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField, EncryptedEmailField

    activo = models.BooleanField(
        default=True,
        verbose_name="Estado activo",
        help_text="Indica si el intermediario está activo en el sistema."
    )
    # Código de Intermediario: INT-XXXXXX
    codigo = models.CharField(
        max_length=15,  # Ajustado para prefijo + 6 dígitos + margen
        unique=True,
        verbose_name="Código de Intermediario",
        db_index=True,
        blank=True,     # Necesario si se genera en save()
        editable=False,  # Hacer no editable manualmente
        help_text="Formato: INT-XXXXXX (Auto-generado)."
    )
    nombre_completo = EncryptedCharField(
        verbose_name="Nombre Completo del Intermediario",
        help_text="Nombre completo o razón social del intermediario."
    )
    rif = EncryptedCharField(
        verbose_name="RIF",
        blank=True,
        null=True,
        help_text="Formato Requerido: Letra-8Números-1Número (Ej: J-12345678-9).",
        validators=[validate_rif]  # Asegúrate que validate_rif esté definido
    )
    rif_hash = models.CharField(
        max_length=64,
        # unique=True, # Comentado para la 1ra migración
        db_index=True,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Hash del RIF (para búsquedas)"
    )
    direccion_fiscal = EncryptedTextField(
        verbose_name="Dirección Fiscal",
        blank=True,
        null=True,
        help_text="Dirección fiscal registrada del intermediario."
    )
    telefono_contacto = EncryptedCharField(
        verbose_name="Teléfono de Contacto",
        blank=True,
        null=True,
        help_text="Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",
        validators=[validate_telefono_venezuela]
    )
    email_contacto = EncryptedEmailField(
        verbose_name="Email de Contacto",
        blank=True,
        null=True,
        validators=[validate_email],
        help_text="Correo electrónico principal de contacto del intermediario."
    )
    intermediario_relacionado = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_intermediarios',
        verbose_name="Intermediario Padre/Relacionado",
        help_text="Intermediario principal o supervisor al que reporta este (si aplica)."
    )
    porcentaje_comision = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('50.00')),  # O 100.00 si es el límite
        ],
        verbose_name="Porcentaje de Comisión",
        default=Decimal('0.00'),
        db_index=True,
        help_text="Porcentaje de comisión asignado. Entre 0.00 y 50.00 (o 100.00)."
    )
    porcentaje_override = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(
            Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Porcentaje de Override",
        help_text="Porcentaje adicional que este intermediario gana sobre las ventas de sus intermediarios subordinados (si aplica).",
        blank=True,
    )

    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='intermediarios_gestionados',
        blank=True,
        verbose_name="Usuarios que gestionan este Intermediario",
        help_text="Usuarios del sistema autorizados a gestionar o ver información de este intermediario."
    )

    # Managers
    objects = SoftDeleteManager()  # Manager para registros activos
    all_objects = models.Manager()  # Manager estándar para todos los registros

    def __str__(self):
        """Devuelve una representación legible del objeto."""
        # Usará el código generado automáticamente
        return f"{self.codigo or 'PENDIENTE'} - {self.nombre_completo or 'Sin Nombre'}"

    @classmethod
    def con_contratos(cls):
        """Optimizado para cargar contratos relacionados."""
        # Importar aquí o globalmente si no hay riesgo de ciclo
        # from .models import ContratoIndividual, ContratoColectivo, Usuario
        try:
            # Optimizar las consultas de prefetch
            contrato_ind_qs = ContratoIndividual.objects.only(
                'id', 'numero_contrato', 'fecha_emision', 'estatus', 'afiliado_id'
                # Ejemplo
            ).select_related('afiliado__primer_nombre', 'afiliado__primer_apellido')

            contrato_col_qs = ContratoColectivo.objects.only(
                'id', 'numero_contrato', 'fecha_emision', 'estatus', 'razon_social'
            )

            usuario_qs = Usuario.objects.only('id', 'username', 'email')

        except NameError:  # Si los modelos no están definidos aún
            contrato_ind_qs = ContratoIndividual.objects.none()
            contrato_col_qs = ContratoColectivo.objects.none()
            usuario_qs = Usuario.objects.none()

        return cls.objects.prefetch_related(
            # Usar related_name si está definido en ContratoIndividual/Colectivo, sino _set
            Prefetch('contratoindividual_set', queryset=contrato_ind_qs),
            # Usando related_name si existe
            Prefetch('contratos_colectivos', queryset=contrato_col_qs),
            Prefetch('usuarios', queryset=usuario_qs)
        )

    def clean(self):
        super().clean()
        # Validación de formato RIF (redundante si validator está bien, pero seguro)
        if self.rif:
            try:
                validate_rif(self.rif)
            except ValidationError as e:
                raise ValidationError({'rif': e.messages})

        # Validación de comisión vs RIF
        if self.porcentaje_comision is not None and self.porcentaje_comision > 10 and not self.rif:
            raise ValidationError({
                "porcentaje_comision": "Se requiere un RIF válido para comisiones mayores al 10%.",
                "rif": "Este campo es obligatorio si la comisión es mayor al 10%."
            })

    def save(self, *args, **kwargs):
        # --- 1. Generar hash para RIF ---
        # Se hace primero para asegurar que el hash esté listo antes de guardar.
        if self.rif:
            self.rif_hash = hashlib.sha256(
                self.rif.encode('utf-8')).hexdigest()
        else:
            self.rif_hash = None

        # --- 2. Lógica original para instancias nuevas ---
        is_new = self._state.adding
        if is_new and not self.codigo:
            # Tu lógica de generación de código UUID
            prefijo_temp = "INT-"
            uuid_hex_length = 11
            max_attempts = 5
            for _ in range(max_attempts):
                generated_code = f"{prefijo_temp}{uuid.uuid4().hex[:uuid_hex_length].upper()}"
                if not Intermediario.all_objects.filter(codigo=generated_code).exists():
                    self.codigo = generated_code
                    break
            else:
                logger.error(
                    f"No se pudo generar un código UUID único para Intermediario después de {max_attempts} intentos.")
                self.codigo = uuid.uuid4(
                ).hex[:self._meta.get_field('codigo').max_length]

            logger.info(
                f"Intermediario nuevo (PK: {self.pk or 'Pre-save'}), código generado (UUID): {self.codigo}")

        # --- 3. Lógica original para llenar nombres ---
        if not self.primer_nombre and self.nombre_completo:
            parts = self.nombre_completo.split(maxsplit=1)
            self.primer_nombre = parts[0][:100]
            if len(parts) > 1:
                self.primer_apellido = parts[1][:100]
            else:
                self.primer_apellido = "(Intermediario)"

        # --- 4. Llamada final al save() de la clase padre ---
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Intermediario"
        verbose_name_plural = "Intermediarios"
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['nombre_completo']),
            models.Index(fields=['rif']),
            models.Index(fields=['porcentaje_comision', 'activo']),
        ]
        # ordering = ['nombre_completo'] # Descomentar si no hay ordering en ModeloBase
# ---------------------------
# Factura (Modelo Completo Corregido)
# ---------------------------


class Factura(ModeloBase):
    TOLERANCE = Decimal('0.01')
    activo = models.BooleanField(
        default=True,
        verbose_name="Estado activo",
        help_text="Indica si el registro de esta factura está activo/visible en el sistema."
    )
    estatus_factura = models.CharField(
        max_length=50,
        choices=CommonChoices.ESTATUS_FACTURA,
        default='GENERADA',
        verbose_name="Estatus de Factura",
        db_index=True,
        help_text="Estado del ciclo de vida de la factura."
    )
    contrato_individual = models.ForeignKey(
        'ContratoIndividual',  # Asegúrate que ContratoIndividual esté definido/importado
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='factura_set',
        help_text="Contrato individual al que corresponde esta factura (si aplica)."
    )
    contrato_colectivo = models.ForeignKey(
        'ContratoColectivo',  # Asegúrate que ContratoColectivo esté definido/importado
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='factura_set',
        help_text="Contrato colectivo al que corresponde esta factura (si aplica)."
    )
    vigencia_recibo_desde = models.DateField(
        verbose_name="Vigencia Recibo Desde",
        db_index=True,
        help_text="Fecha de inicio del período de cobertura que cubre esta factura."
    )
    vigencia_recibo_hasta = models.DateField(
        verbose_name="Vigencia Recibo Hasta",
        db_index=True,
        help_text="Fecha de fin del período de cobertura que cubre esta factura."
    )
    intermediario = models.ForeignKey(
        'Intermediario',  # Asegúrate que Intermediario esté definido/importado
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Intermediario",
        related_name='facturas',
        help_text="Intermediario asociado a la factura (puede heredar del contrato)."
    )
    monto = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        null=True,  # Permite valores nulos en la base de datos
        blank=True,  # Permite que el campo esté vacío en los formularios
        help_text="Monto base (subtotal) de la factura."
    )
    monto_pendiente = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
        verbose_name="Monto Pendiente",
        db_index=True,
        help_text="Saldo restante por pagar de esta factura (calculado automáticamente)."
    )
    numero_recibo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de Recibo",
        db_index=True,
        blank=True,
        editable=False,
        help_text="Formato: REC-XXXXXXXXX (Auto-generado)."
    )
    dias_periodo_cobro = models.IntegerField(
        verbose_name="Días del período de cobro",
        # Permitir 0 si es un pago único o no aplica
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
        help_text="Duración en días del período que cubre la factura (calculado o manual)."
    )
    estatus_emision = models.CharField(
        max_length=20,
        choices=CommonChoices.EMISION_RECIBO,
        default='SIN_EMITIR',
        verbose_name="Estatus de Emisión",
        help_text="Estado de la generación del documento físico o digital de la factura."
    )
    pagada = models.BooleanField(
        default=False,
        verbose_name="Pagada",
        db_index=True,
        editable=False,
        help_text="Indica si la factura ha sido completamente pagada (calculado automáticamente)."
    )
    relacion_ingreso = models.CharField(
        max_length=50,
        verbose_name="N° Relación de Ingreso",
        blank=True,
        null=True,
        editable=False,
        db_index=True,
        help_text="Formato: RI-XXXXXXXXXX (Auto-generado)."
    )
    recibos_pendientes_cache = models.PositiveIntegerField(
        default=0,
        db_index=True,
        editable=False,
        help_text="Campo interno para optimización. ¡Requiere lógica explícita para mantenerlo actualizado!"
    )
    aplica_igtf = models.BooleanField(
        default=False,
        verbose_name="¿Condiciones para IGTF presentes?",
        help_text="Marcar si la transacción asociada a esta factura cumple las condiciones para aplicar IGTF. (Informativo)"
    )
    observaciones = models.TextField(
        verbose_name="Observaciones de la Factura",
        blank=True,
        null=True,
        help_text="Notas o comentarios adicionales específicos de esta factura."
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def _generar_numero_recibo_factura(self):
        fecha_actual_str = django_timezone.now().strftime("%y%m%d")
        tipo_contrato_str = "UNK"
        id_contrato_ref_simple = "NA"
        contrato_obj = self.contrato_individual or self.contrato_colectivo
        if contrato_obj:
            tipo_contrato_str = "IND" if self.contrato_individual else "COL"
            id_contrato_ref_simple = str(
                contrato_obj.pk if contrato_obj and contrato_obj.pk else "NEW")[:5]
        uuid_part = uuid.uuid4().hex[:12].upper()
        return f"REC-{tipo_contrato_str}-{id_contrato_ref_simple}-{fecha_actual_str}-{uuid_part}"[:50]

    def _generar_relacion_ingreso_factura(self):
        # Implementa tu lógica para generar_codigo_unico o usa UUID
        fecha_actual = django_timezone.now()
        return f"RI-{fecha_actual.strftime('%Y%m%d')}-{uuid.uuid4().hex[:10].upper()}"[:50]

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        # --- LÓGICA CORREGIDA ---
        if is_new:
            # Al crear, el monto pendiente es igual al monto total de la factura.
            self.monto_pendiente = self.monto if self.monto is not None else Decimal(
                '0.00')

            # Generamos códigos únicos solo en la creación
            if not self.numero_recibo:
                self.numero_recibo = self._generar_numero_recibo_factura()
            if not self.relacion_ingreso:
                self.relacion_ingreso = self._generar_relacion_ingreso_factura()

        # La lógica para marcar como 'pagada' debe basarse en el monto_pendiente.
        # La señal post-pago se encargará de actualizar monto_pendiente, y esta lógica se aplicará.
        if self.monto_pendiente is not None and self.monto_pendiente <= self.TOLERANCE:
            self.pagada = True
            # Si se paga completamente, el estado debe reflejarlo.
            if self.estatus_factura != 'ANULADA':
                self.estatus_factura = 'PAGADA'
        else:
            self.pagada = False
            # Si deja de estar pagada (ej. se anula un pago), volvemos a un estado pendiente.
            if self.estatus_factura == 'PAGADA':
                self.estatus_factura = 'PENDIENTE'

        super().save(*args, **kwargs)

    @property
    def ramo_contrato(self):
        if self.contrato_individual and self.contrato_individual.ramo:
            return self.contrato_individual.get_ramo_display()
        elif self.contrato_colectivo and self.contrato_colectivo.ramo:
            return self.contrato_colectivo.get_ramo_display()
        return None

    @property
    def get_contrato_asociado(self):
        """
        Devuelve el objeto de contrato (Individual o Colectivo) al que está
        asociada esta factura.
        """
        return self.contrato_individual or self.contrato_colectivo

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        indexes = [
            models.Index(fields=['numero_recibo']),
            models.Index(fields=['relacion_ingreso']),
            models.Index(fields=['contrato_individual']),
            models.Index(fields=['contrato_colectivo']),
            models.Index(fields=['intermediario']),
            models.Index(fields=['vigencia_recibo_desde',
                         'vigencia_recibo_hasta']),
            models.Index(fields=['pagada', 'activo']),
            models.Index(fields=['aplica_igtf', 'pagada']),
        ]
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.numero_recibo or f"Factura ID {self.pk}"

# =====================#
# AUDITORIA SISTEMA   #
# =====================#


def get_modelo_choices():
    current_app_name = "myapp"  # Asegúrate de que este sea el nombre de tu aplicación
    return [
        (m._meta.db_table, m._meta.verbose_name)
        for m in apps.get_app_config(current_app_name).get_models()
    ]


class AuditoriaSistema(models.Model):
    from encrypted_model_fields.fields import EncryptedTextField, EncryptedCharField
    tipo_accion = models.CharField(
        max_length=50,
        choices=CommonChoices.TIPO_ACCION,
        verbose_name=("Tipo de Acción"),
        db_index=True,
        null=True,
        blank=True,

        help_text="Tipo de operación registrada (ej. CREACION, LOGIN, ERROR)."
    )
    resultado_accion = models.CharField(
        max_length=50,
        choices=CommonChoices.RESULTADO_ACCION,
        verbose_name=("Resultado de Acción"),
        db_index=True,
        null=True,
        blank=True,
        help_text="Indica si la acción registrada fue exitosa o fallida."
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=("Usuario"),
        db_index=True,

        help_text="Usuario que realizó la acción registrada (si aplica)."
    )
    tabla_afectada = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=("Tabla Afectada"),
        help_text="Nombre de la tabla de la base de datos modificada por la acción."
    )
    registro_id_afectado = models.IntegerField(
        verbose_name=("ID Registro Afectado"),
        blank=True,
        null=True,
        db_index=True,

        help_text="ID (clave primaria) del registro específico afectado por la acción."
    )
    detalle_accion = EncryptedTextField(
        verbose_name=("Detalle de la Acción"),
        blank=True,
        null=True,
        help_text="Descripción detallada de la acción realizada o del error ocurrido."
    )
    direccion_ip = EncryptedCharField(
        verbose_name=("Dirección IP"),
        blank=True,
        null=True,
        db_index=True,
        help_text="Dirección IP desde la cual se originó la acción."
    )
    agente_usuario = EncryptedTextField(
        verbose_name=("Agente de Usuario (User Agent)"),
        blank=True,
        null=True,
        help_text="Información del navegador o cliente utilizado para realizar la acción."
    )
    tiempo_inicio = models.DateTimeField(
        verbose_name=("Tiempo de Inicio"),
        auto_now_add=True,
        db_index=True,

        help_text="Fecha y hora exactas en que se inició el registro de la acción (automático)."
    )
    tiempo_final = models.DateTimeField(
        verbose_name=("Tiempo de Finalización"),
        null=True,
        blank=True,
        default=None,

        help_text="Fecha y hora en que finalizó la operación registrada (si aplica)."
    )
    control_fecha_actual = models.DateTimeField(
        verbose_name=("Control Fecha Actual"),
        auto_now_add=True,
        db_index=True,

        help_text="Marca de tiempo de control al momento de crear el registro de auditoría (automático)."
    )

    @classmethod
    def con_usuario(cls):
        return cls.objects.select_related('usuario')

    def clean(self):
        if self.tiempo_final and self.tiempo_final < self.tiempo_inicio:
            raise ValidationError(
                ("La fecha final no puede ser anterior a la inicial.")
            )

    # Definición del trigger de auditoría
    trigger_audit = pgtrigger.Trigger(
        name='auditoria_afiliado',
        operation=(pgtrigger.Insert | pgtrigger.Update | pgtrigger.Delete),
        when=pgtrigger.After,
        # Asegúrate de que esta función esté definida
        func='myapp.auditoria_afiliado_audit()'
    )

    class Meta:
        verbose_name = ("Auditoría del Sistema")
        verbose_name_plural = ("Auditorías del Sistema (Hoja1)")
        ordering = ['-tiempo_inicio']
        indexes = [
            models.Index(fields=['tipo_accion', 'resultado_accion']),
            models.Index(fields=['direccion_ip', 'usuario']),
        ]
        permissions = [('view_exportacion', ('Puede exportar datos'))]

# ------------------------------
# Reclamación (Optimizado)
# ------------------------------


class ReclamacionManager(models.Manager):
    def con_relaciones_completas(self):
        return self.select_related(
            'contrato_individual__afiliado',
            'contrato_colectivo__intermediario',
            'usuario_asignado'
        ).prefetch_related('pagos')


class Reclamacion(ModeloBase):
    from encrypted_model_fields.fields import EncryptedTextField
    numero_reclamacion = models.CharField(
        max_length=50,
        unique=True,    # Importante: True desde el inicio ahora
        verbose_name="Número de Reclamación",
        db_index=True,
        blank=True,
        editable=False,
        help_text="Identificador único de la reclamación (Auto-generado)."
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="¿Reclamación activa?",
        db_index=True,
        help_text="Indica si el registro de esta reclamación está activo/visible en el sistema."
    )
    tipo_reclamacion = models.CharField(
        max_length=50,
        choices=CommonChoices.TIPO_RECLAMACION,
        default='MEDICA',
        verbose_name=("Tipo de Reclamación"),
        db_index=True,
        help_text="Naturaleza de la reclamación (ej. Médica, Dental, Administrativa)."
    )
    diagnostico_principal = models.CharField(
        max_length=225,
        verbose_name="Diagnóstico Principal",
        choices=CommonChoices.DIAGNOSTICOS,
        blank=True,
        null=True,
        db_index=True,
        help_text="Diagnóstico principal estandarizado asociado a la reclamación."
    )
    estado = models.CharField(
        max_length=50,
        choices=CommonChoices.ESTADO_RECLAMACION,
        default='ABIERTA',
        blank=False,  # Asumo que estado siempre debe tener un valor
        null=False,  # Asumo que estado siempre debe tener un valor
        verbose_name=("Estado de la Reclamación"),
        db_index=True,
        help_text="Estado actual del proceso de la reclamación (ej. Abierta, Aprobada, Pagada)."
    )
    descripcion_reclamo = EncryptedTextField(
        verbose_name=("Descripción del Reclamo"),
        blank=False,
        null=False,
        help_text="Descripción detallada del motivo de la reclamación realizada por el cliente."
    )
    monto_reclamado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto Reclamado",
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Monto solicitado por el cliente en la reclamación. Debe ser mayor a 0."
    )
    contrato_individual = models.ForeignKey(
        'ContratoIndividual',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=("Contrato Individual"),
        db_index=True,
        help_text="Contrato individual bajo el cual se realiza la reclamación (si aplica)."
    )
    contrato_colectivo = models.ForeignKey(
        'ContratoColectivo',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=("Contrato Colectivo"),
        db_index=True,
        help_text="Contrato colectivo bajo el cual se realiza la reclamación (si aplica)."
    )
    fecha_reclamo = models.DateField(
        verbose_name=("Fecha de Reclamación"),
        db_index=True,
        help_text="Fecha en que el cliente presentó o se registró la reclamación."
    )
    fecha_cierre_reclamo = models.DateField(
        verbose_name=("Fecha de Cierre de Reclamación"),
        blank=True,
        null=True,
        db_index=True,
        help_text="Fecha en que la reclamación fue resuelta o cerrada definitivamente."
    )
    usuario_asignado = models.ForeignKey(
        'Usuario',  # O settings.AUTH_USER_MODEL
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=("Usuario Asignado a la Reclamación"),
        db_index=True,
        help_text="Usuario del sistema responsable de gestionar esta reclamación."
    )
    documentos_adjuntos = models.FileField(
        upload_to='reclamos/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'png']),
            validate_file_size  # Asegúrate que validate_file_size esté definida
        ],
        verbose_name="Documentos Adjuntos",
        blank=True,
        null=True,
        help_text="Archivos PDF, JPG, PNG que soportan la reclamación. Tamaño máx: 10MB."
    )
    observaciones_internas = EncryptedTextField(  # También es buena idea cifrar este
        verbose_name=("Observaciones Internas"),
        blank=True,
        null=True,
        help_text="Notas o comentarios internos del personal sobre la reclamación (no visibles al cliente)."
    )
    observaciones_cliente = EncryptedTextField(
        verbose_name=("Observaciones para el Cliente"),
        blank=True,
        null=True,
        help_text="Comentarios o respuestas proporcionadas al cliente sobre el estado o resolución de la reclamación."
    )

    objects = ReclamacionManager()  # Tu manager personalizado
    all_objects = models.Manager()  # O SoftDeleteManager si lo usas para Reclamacion

    def _generar_numero_reclamacion(self):
        fecha_actual_str = django_timezone.now().strftime("%y%m%d")
        tipo_contrato_str = "UNK"
        id_contrato_ref_simple = "NA"
        contrato_obj = self.contrato_individual or self.contrato_colectivo
        if contrato_obj:
            tipo_contrato_str = "CI" if self.contrato_individual else "CC"
            # Usar el PK del contrato si ya existe, de lo contrario un placeholder
            # Es importante que contrato_obj.pk exista si el contrato ya fue guardado.
            # Si el contrato es nuevo y aún no tiene PK, esto podría dar "NEW".
            id_contrato_ref_simple = str(contrato_obj.pk if contrato_obj and hasattr(
                contrato_obj, 'pk') and contrato_obj.pk else "NEW")[:5]

        # Añadir el PK de la propia reclamación (si ya existe) para mayor unicidad,
        # o un UUID si es una instancia nueva sin PK.
        # Sin embargo, _generar_numero_reclamacion se llama ANTES de que el PK se asigne en el primer save.
        # Por lo tanto, nos basaremos en UUID para la parte variable si es nuevo.

        # Un poco más largo para mayor unicidad
        uuid_part = uuid.uuid4().hex[:8].upper()

        # Formato: RECL-YYMMDD-CI/CC-IDCONTRATO-UUID
        codigo_generado = f"RECL-{fecha_actual_str}-{tipo_contrato_str}-{id_contrato_ref_simple}-{uuid_part}"
        # Asegurar que no exceda max_length
        return codigo_generado[:self._meta.get_field('numero_reclamacion').max_length]

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if is_new and not self.numero_reclamacion:
            self.numero_reclamacion = self._generar_numero_reclamacion()
            # Bucle para asegurar unicidad en caso de colisión (extremadamente improbable con UUID)
            while type(self).objects.filter(numero_reclamacion=self.numero_reclamacion).exists():
                logger.warning(
                    f"Colisión detectada para numero_reclamacion: {self.numero_reclamacion}. Regenerando...")
                self.numero_reclamacion = self._generar_numero_reclamacion()

        # Tu lógica de validación de estado
        is_updating = not self._state.adding
        if is_updating and self.pk:
            try:
                original = type(self).objects.only('estado').get(pk=self.pk)
                if original.estado != self.estado:
                    # Asumo que validate_estado_reclamacion existe y está importada
                    validate_estado_reclamacion(original.estado, self.estado)
            except type(self).DoesNotExist:
                logger.warning(
                    f"Reclamacion con PK {self.pk} no encontrada durante save (update).")
            except NameError:  # Si validate_estado_reclamacion no está definida
                logger.error(
                    "La función validate_estado_reclamacion no está definida o importada.")
            except ValidationError as e:
                raise ValidationError(
                    f"Transición de estado inválida: {e.message if hasattr(e, 'message') else str(e)}")

        super().save(*args, **kwargs)

    def get_estado_display_valor(self, valor_estado=None):
        estado_a_buscar = valor_estado if valor_estado is not None else self.estado
        estado_map = dict(CommonChoices.ESTADO_RECLAMACION)
        return estado_map.get(estado_a_buscar, estado_a_buscar)

    def get_contrato_asociado_display(self):
        if self.contrato_individual:
            return f"CI: {self.contrato_individual.numero_contrato or f'ID {self.contrato_individual.pk}'}"
        elif self.contrato_colectivo:
            return f"CC: {self.contrato_colectivo.numero_contrato or f'ID {self.contrato_colectivo.pk}'}"
        return "Sin Contrato"

    def clean(self):
        super().clean()
        # ... (tu lógica de clean existente) ...
        error_dict = {}
        contrato = self.contrato_individual or self.contrato_colectivo

        if not contrato:
            raise ValidationError(
                {"contrato_individual": "Debe seleccionar un contrato individual o colectivo."})
        elif self.contrato_individual and self.contrato_colectivo:
            raise ValidationError(
                {"contrato_individual": "No puede seleccionar ambos tipos de contrato."})

        if contrato and self.monto_reclamado is not None:
            if hasattr(contrato, 'suma_asegurada') and contrato.suma_asegurada is not None:
                try:
                    monto_reclamado_dec = Decimal(self.monto_reclamado)
                    suma_asegurada_dec = Decimal(contrato.suma_asegurada)
                    if monto_reclamado_dec > suma_asegurada_dec:
                        error_dict.setdefault('monto_reclamado', []).append(
                            ValidationError(
                                f"Monto reclamado (${monto_reclamado_dec:,.2f}) excede suma asegurada (${suma_asegurada_dec:,.2f}).",
                                code='monto_excede_cobertura'
                            )
                        )
                except (InvalidOperation, TypeError):
                    error_dict.setdefault('monto_reclamado', []).append(
                        ValidationError("Monto/Suma asegurada inválidos."))
            else:
                logger.warning(
                    f"Contrato {contrato.pk if contrato and contrato.pk else 'Nuevo'} sin suma asegurada para validar Reclamación {self.pk if self.pk else 'Nueva'}.")

        if self.fecha_reclamo:
            if contrato and hasattr(contrato, 'fecha_inicio_vigencia') and contrato.fecha_inicio_vigencia and self.fecha_reclamo < contrato.fecha_inicio_vigencia:
                error_dict.setdefault('fecha_reclamo', []).append(
                    'Fecha reclamación anterior a inicio vigencia.')
        else:
            error_dict.setdefault('fecha_reclamo', []).append(
                'Fecha de reclamación es obligatoria.')

        if self.fecha_cierre_reclamo and self.fecha_reclamo and self.fecha_cierre_reclamo < self.fecha_reclamo:
            error_dict.setdefault('fecha_cierre_reclamo', []).append(
                "Fecha cierre no puede ser anterior a fecha reclamo.")

        if self.estado == 'CERRADA' and not self.fecha_cierre_reclamo:
            error_dict.setdefault('fecha_cierre_reclamo', []).append(
                "Indicar fecha cierre para estado 'CERRADA'.")

        if error_dict:
            raise ValidationError(error_dict)

    def __str__(self):
        identificador_contrato = "Sin Contrato Asociado"
        if self.contrato_individual:
            numero_ci = self.contrato_individual.numero_contrato or f"ID {self.contrato_individual.pk}"
            identificador_contrato = f"CI:{numero_ci}"
        elif self.contrato_colectivo:
            numero_cc = self.contrato_colectivo.numero_contrato or f"ID {self.contrato_colectivo.pk}"
            identificador_contrato = f"CC:{numero_cc}"

        # Mostrar ID si el número aún no está (no debería pasar con la lógica de save)
        num_reclamacion_display = self.numero_reclamacion or f"ID:{self.pk}"
        return f"Reclamo {num_reclamacion_display} ({identificador_contrato}) - {self.get_estado_display()}"

    class Meta:
        verbose_name = ("Reclamación")
        verbose_name_plural = ("Reclamaciones")
        indexes = [
            # Índice para el nuevo campo
            models.Index(fields=['numero_reclamacion']),
            models.Index(fields=['tipo_reclamacion', 'estado']),
            models.Index(fields=['fecha_reclamo', 'fecha_cierre_reclamo']),
            models.Index(fields=['contrato_individual']),
            models.Index(fields=['contrato_colectivo']),
            models.Index(fields=['usuario_asignado']),
            models.Index(fields=['monto_reclamado']),
            models.Index(fields=['activo']),
        ]
        ordering = ['-fecha_reclamo']

# ------------------------------
# Pago (Modelo Completo Corregido)
# ------------------------------


class Pago(ModeloBase):  # Heredar de ModeloBase si aplica
    from encrypted_model_fields.fields import EncryptedCharField
    TOLERANCE = Decimal('0.01')
    activo = models.BooleanField(
        default=True, verbose_name="Estado activo",
        help_text="Indica si este registro de pago está activo/visible en el sistema."
    )
    forma_pago = models.CharField(
        max_length=50, choices=CommonChoices.FORMA_PAGO_RECLAMACION, default='TRANSFERENCIA',
        verbose_name="Forma de Pago", db_index=True, validators=[validate_metodo_pago],
        help_text="Método utilizado para realizar el pago."
    )
    reclamacion = models.ForeignKey(
        'Reclamacion', on_delete=models.PROTECT, related_name='pagos', null=True, blank=True,
        help_text="Reclamación pagada (si aplica)."
    )
    fecha_pago = models.DateField(
        verbose_name="Fecha de Pago", db_index=True, help_text="Fecha efectiva del pago."
    )
    monto_pago = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="Monto del Pago", db_index=True,
        validators=[MinValueValidator(Decimal('0.01'))], help_text="Monto exacto pagado (> 0)."
    )
    aplica_igtf_pago = models.BooleanField(
        default=False, verbose_name="¿Pago sujeto a IGTF?",
        help_text="Marcar si este pago específico genera IGTF."
    )
    referencia_pago = EncryptedCharField(
        verbose_name="Referencia de Pago", blank=True,
        help_text="Identificador único del pago (ej. N° transferencia)."
    )
    fecha_notificacion_pago = models.DateField(
        verbose_name="Fecha de Notificación de Pago", blank=True, null=True,
        help_text="Fecha registro del pago en sistema."
    )
    observaciones_pago = models.TextField(
        verbose_name="Observaciones del Pago", blank=True, null=True,
        help_text="Notas adicionales sobre el pago."
    )
    documentos_soporte_pago = models.FileField(
        upload_to='documentos_pagos/', blank=True, null=True,
        verbose_name="Documentos de Soporte del Pago", validators=[validate_file_size, validate_file_type],
        help_text="Archivos adjuntos (comprobante). PDF, JPG, PNG. Max 10MB."
    )
    factura = models.ForeignKey(
        'Factura', on_delete=models.PROTECT, related_name='pagos',
        verbose_name="Factura Asociada", db_index=True, null=True, blank=True,
        help_text="Factura abonada (si aplica)."
    )

    objects = models.Manager()
    # Usar SoftDeleteManager si aplica, sino models.Manager()
    all_objects = SoftDeleteManager()

    @transaction.atomic
    def save(self, *args, **kwargs):
        logger.debug(f"Pago {self.pk or '(Nuevo)'}: Llamando a super().save()")
        super().save(*args, **kwargs)
        # YA NO llama a los métodos de actualización

    @transaction.atomic
    def delete(self, *args, **kwargs):
        logger.debug(f"Pago {self.pk}: Llamando a super().delete()")
        super().delete(*args, **kwargs)
        # YA NO llama a los métodos de actualización

    def clean(self):
        super().clean()
        if not self.factura_id and not self.reclamacion_id:
            raise ValidationError(
                {"__all__": "El pago debe estar asociado a una Factura o a una Reclamación."})
        if self.factura_id and self.reclamacion_id:
            raise ValidationError(
                {"__all__": "El pago no puede estar asociado a Factura y Reclamación a la vez."})

        current_monto_pago = self.monto_pago or Decimal('0.00')
        is_update = self.pk is not None
        original_monto = Decimal('0.00')
        original_activo = False

        if is_update:
            try:
                original_pago = Pago.objects.get(pk=self.pk)
                original_monto = original_pago.monto_pago or Decimal('0.00')
                original_activo = original_pago.activo
            except Pago.DoesNotExist:
                is_update = False

        if is_update and original_activo and not self.activo:
            pass  # Permitir inactivar sin validar monto
        elif self.factura_id:
            try:
                FacturaModel = apps.get_model('myapp', 'Factura')
                factura = FacturaModel.objects.get(pk=self.factura_id)
                monto_factura = factura.monto or Decimal('0.00')
                pagos_otros_activos = factura.pagos.filter(
                    activo=True).exclude(pk=self.pk if is_update else None)
                total_pagado_otros = pagos_otros_activos.aggregate(
                    t=Coalesce(Sum('monto_pago'), Decimal(
                        '0.00'), output_field=DecimalField())
                )['t']
                pendiente_antes_este_pago = max(
                    Decimal('0.00'), monto_factura - total_pagado_otros)

                if current_monto_pago > pendiente_antes_este_pago + self.TOLERANCE:
                    raise ValidationError({'monto_pago': (
                        f"Monto del pago (${current_monto_pago:.2f}) excede el pendiente real "
                        f"(${pendiente_antes_este_pago:.2f}) de la Factura {factura.numero_recibo}.")})
            except FacturaModel.DoesNotExist:
                raise ValidationError(
                    {'factura': "La factura asociada no existe."})
        elif self.reclamacion_id:
            try:
                ReclamacionModel = apps.get_model('myapp', 'Reclamacion')
                reclamacion = ReclamacionModel.objects.get(
                    pk=self.reclamacion_id)
                monto_reclamado = reclamacion.monto_reclamado or Decimal(
                    '0.00')
                pagos_otros_activos = reclamacion.pagos.filter(
                    activo=True).exclude(pk=self.pk if is_update else None)
                total_pagado_otros = pagos_otros_activos.aggregate(
                    t=Coalesce(Sum('monto_pago'), Decimal(
                        '0.00'), output_field=DecimalField())
                )['t']
                pendiente_antes_este_pago = max(
                    Decimal('0.00'), monto_reclamado - total_pagado_otros)

                if current_monto_pago > pendiente_antes_este_pago + self.TOLERANCE:
                    raise ValidationError({'monto_pago': (
                        f"Monto del pago (${current_monto_pago:.2f}) excede el pendiente real "
                        f"(${pendiente_antes_este_pago:.2f}) de la Reclamación #{reclamacion.pk}.")})
            except ReclamacionModel.DoesNotExist:
                raise ValidationError(
                    {'reclamacion': "La reclamación asociada no existe."})

    class Meta:
        verbose_name = "Pago Registrado"
        verbose_name_plural = "Pagos Registrados"
        indexes = [
            models.Index(fields=['forma_pago', 'fecha_pago']), models.Index(
                fields=['referencia_pago']),
            models.Index(fields=['reclamacion']), models.Index(
                fields=['factura']),
            models.Index(fields=['fecha_pago', 'monto_pago']
                         ), models.Index(fields=['activo']),
            models.Index(fields=['aplica_igtf_pago'])
        ]
        ordering = ['-fecha_pago']

    def __str__(self):
        ref = self.referencia_pago or f"ID:{self.pk}"
        monto_str = f"{self.monto_pago:.2f}" if self.monto_pago else "0.00"
        assoc = ""
        if self.factura_id:
            # Intentar obtener el número de recibo de la caché del objeto si está cargado
            if hasattr(self, 'factura') and self.factura and hasattr(self.factura, 'numero_recibo'):
                assoc = f"Fact:{self.factura.numero_recibo}"
            else:
                assoc = f"Fact ID:{self.factura_id}"
        elif self.reclamacion_id:
            assoc = f"Rec ID:{self.reclamacion_id}"
        return f"Pago {ref} ({assoc}) - {monto_str}"


# ------------------------------
# Registro Comision (Intermediario Padre)
# ------------------------------

# No necesita heredar de ModeloBase a menos que quieras esos campos
class RegistroComision(models.Model):
    TIPO_COMISION_CHOICES = [
        ('DIRECTA', 'Comisión Directa'),
        ('OVERRIDE', 'Comisión de Override'),
    ]
    ESTATUS_PAGO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Pago'),
        ('PAGADA', 'Pagada'),
        ('ANULADA', 'Anulada'),  # Por si la comisión se anula
    ]

    intermediario = models.ForeignKey(
        Intermediario,
        on_delete=models.PROTECT,  # Proteger para no borrar intermediario si tiene comisiones
        related_name="comisiones_ganadas",
        verbose_name="Intermediario Beneficiario"
    )
    # Referencia al contrato que originó la comisión
    contrato_individual = models.ForeignKey(
        ContratoIndividual,
        # Si se borra el contrato, la comisión puede quedar registrada pero sin enlace directo
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="comisiones_generadas"
    )
    contrato_colectivo = models.ForeignKey(
        ContratoColectivo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="comisiones_generadas"
    )
    pago_cliente = models.ForeignKey(
        Pago,
        on_delete=models.SET_NULL,  # Si se borra el pago del cliente, la comisión puede quedar
        null=True, blank=True,
        related_name="comisiones_originadas",
        verbose_name="Pago del Cliente que Originó la Comisión"
    )
    factura_origen = models.ForeignKey(
        Factura,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="comisiones_asociadas",
        verbose_name="Factura que Originó la Comisión"
    )
    tipo_comision = models.CharField(
        max_length=10,
        choices=TIPO_COMISION_CHOICES,
        verbose_name="Tipo de Comisión"
    )
    # Porcentaje que se aplicó para esta comisión específica
    porcentaje_aplicado = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name="Porcentaje Aplicado (%)"
    )
    # Sobre qué monto se calculó la comisión (ej. monto de la factura, prima neta)
    monto_base_calculo = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Monto Base para Cálculo"
    )
    monto_comision = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Monto de la Comisión"
    )
    fecha_calculo = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Cálculo"
    )
    # Para registrar cuándo se le paga esta comisión al intermediario
    fecha_pago_a_intermediario = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de Pago a Intermediario"
    )
    estatus_pago_comision = models.CharField(
        max_length=20,
        choices=ESTATUS_PAGO_CHOICES,
        default='PENDIENTE',
        verbose_name="Estatus del Pago de Comisión"
    )
    # Quién es el intermediario que generó la venta (para overrides)
    intermediario_vendedor = models.ForeignKey(
        Intermediario,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ventas_para_override",
        verbose_name="Intermediario Vendedor (si aplica override)"
    )
    usuario_que_liquido = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # O models.PROTECT si prefieres no borrar la comisión si se borra el usuario
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # Puede ser blank si se liquida por un proceso automático en el futuro o si no se requiere siempre
        related_name="comisiones_liquidadas_por_usuario",
        verbose_name="Usuario que Liquidó la Comisión"
    )

    comprobante_pago = models.FileField(
        upload_to='comprobantes_comisiones/',
        validators=[validate_file_size, validate_file_type],
        verbose_name="Comprobante de Pago de Comisión",
        null=True,
        blank=True,
        help_text="Comprobante de la liquidación (PDF, JPG, PNG. Max 10MB)."
    )

    def __str__(self):
        # ... (tu método __str__) ...
        contrato_str = ""
        if self.contrato_individual:
            contrato_str = f"CI: {self.contrato_individual.numero_contrato or self.contrato_individual_id}"
        elif self.contrato_colectivo:
            contrato_str = f"CC: {self.contrato_colectivo.numero_contrato or self.contrato_colectivo_id}"

        estatus_display = self.get_estatus_pago_comision_display() if hasattr(
            self, 'get_estatus_pago_comision_display') else self.estatus_pago_comision

        return f"{self.get_tipo_comision_display()} para {self.intermediario.nombre_completo if self.intermediario else 'N/A'} - {self.monto_comision} (Cont: {contrato_str}) - Estado: {estatus_display}"

    def save(self, *args, **kwargs):
        # Para fecha_calculo (DateTimeField con auto_now_add=True):
        # Django debería manejar esto correctamente usando timezone.now() al crear.
        # Esta verificación es más una medida de seguridad para actualizaciones o si auto_now_add se anula.
        # Si ya tiene un valor (ej. al actualizar o si se asignó antes de save)
        if self.fecha_calculo:
            if django_timezone.is_naive(self.fecha_calculo):
                logger_model_save.warning(
                    f"RegistroComision (PK: {self.pk or 'Nuevo'}): "
                    f"fecha_calculo ({self.fecha_calculo}) era naive. Haciéndola aware."
                )
                self.fecha_calculo = django_timezone.make_aware(
                    self.fecha_calculo, django_timezone.get_current_timezone())
        # No necesitamos un 'elif self._state.adding' aquí porque auto_now_add lo maneja
        # a menos que estés asignando explícitamente fecha_calculo en otro lugar antes de este save.

        # Para fecha_pago_a_intermediario (DateField):
        # Los DateField no almacenan información de zona horaria y no necesitan ser "aware".
        # Django los maneja como objetos `date` simples.
        # No se necesita lógica especial de zona horaria aquí para este campo.

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Registro de Comisión"
        verbose_name_plural = "Registros de Comisiones"
        ordering = ['-fecha_calculo']

# ------------------------------
# Tarifa (Optimizado)
# ------------------------------


class Tarifa(ModeloBase):
    activo = models.BooleanField(
        default=True, verbose_name="Activo",
        help_text="Indica si esta tarifa está actualmente activa y disponible para ser utilizada en cálculos."
    )
    codigo_tarifa = models.CharField(
        max_length=50,  # Ajusta si el código puede ser más largo
        unique=True,
        editable=False,
        db_index=True,
        # blank=True,
        # null=True,
        verbose_name="Código de Tarifa",
        help_text="Identificador único de la tarifa (Auto-generado)."
    )
    rango_etario = models.CharField(
        max_length=10, choices=CommonChoices.RANGO_ETARIO,
        help_text="Grupo de edad específico al que aplica esta tarifa."
    )
    ramo = models.CharField(
        max_length=50, choices=CommonChoices.RAMO,
        help_text="Tipo de seguro o servicio (ramo) al que aplica esta tarifa."
    )
    fecha_aplicacion = models.DateField(
        verbose_name="Fecha de Aplicación de la Tarifa", db_index=True,
        help_text="Fecha a partir de la cual esta tarifa entra en vigencia o es aplicable."
    )
    monto_anual = models.DecimalField(
        verbose_name="Monto Anual", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))], db_index=True,
        help_text="Monto base anual de la tarifa. Utilizado para calcular valores fraccionados. Debe ser mayor a 0."
    )
    tipo_fraccionamiento = models.CharField(
        max_length=50, verbose_name="Tipo de Fraccionamiento",
        blank=True, null=True, choices=CommonChoices.FORMA_PAGO,
        help_text="Indica si esta tarifa es específica para un pago fraccionado (ej. Mensual, Trimestral). Dejar en blanco si es la tarifa base anual."
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def _generar_codigo_tarifa(self):
        print("--- Entrando a _generar_codigo_tarifa ---")
        # monto_anual puede ser 0 pero no None
        if not all([self.ramo, self.rango_etario, self.fecha_aplicacion, self.monto_anual is not None]):
            print(
                f"ADVERTENCIA: Datos incompletos para generar código. Ramo: {self.ramo}, Rango: {self.rango_etario}, FechaApp: {self.fecha_aplicacion}, Monto: {self.monto_anual}")
            return f"TAR-INCOMPLETO-{uuid.uuid4().hex[:6].upper()}"

        ramo_abrev = RAMO_ABREVIATURAS.get(
            self.ramo, self.ramo[:3].upper() if self.ramo else "XXX")
        rango_abrev = RANGO_ETARIO_ABREVIATURAS.get(
            self.rango_etario, re.sub(r'\D', '', str(self.rango_etario))[:4])
        print(f"Abreviaturas: Ramo='{ramo_abrev}', Rango='{rango_abrev}'")

        try:
            monto_decimal = Decimal(self.monto_anual) if not isinstance(
                self.monto_anual, Decimal) else self.monto_anual
            monto_centimos = int(monto_decimal.quantize(Decimal('0.00')) * 100)
            monto_str = f"{monto_centimos:06d}"
        # AttributeError si monto_anual es None
        except (TypeError, InvalidOperation, AttributeError) as e:
            print(
                f"ADVERTENCIA: Formato de monto inválido ('{self.monto_anual}'). Error: {e}. Usando 000000")
            monto_str = "000000"
        print(f"Monto String: '{monto_str}'")

        fecha_str = self.fecha_aplicacion.strftime('%y%m%d')
        print(f"Fecha String: '{fecha_str}'")

        fraccion_code = "BASE"
        if self.tipo_fraccionamiento:
            fraccion_code = str(self.tipo_fraccionamiento)[:3].upper()
        print(f"Fraccion Code: '{fraccion_code}'")

        sequence_name = f"tar_{ramo_abrev}_{rango_abrev}_{monto_str}_{fecha_str}_{fraccion_code}"
        print(f"Nombre de Secuencia: '{sequence_name}'")

        next_val = 1  # Default si get_next_value falla
        try:
            if get_next_value:  # Verificar que la función esté disponible
                next_val = get_next_value(sequence_name, initial_value=1)
            else:
                print(
                    "ADVERTENCIA: get_next_value no está disponible, usando next_val=1 por defecto.")
        except Exception as e_seq:
            print(
                f"Error en secuencia {sequence_name}: {e_seq}. Usando next_val=1 por defecto.")
        print(f"Next Val: {next_val}")

        codigo_final = f"TAR-{ramo_abrev}-{rango_abrev}-{monto_str}-{fecha_str}-{fraccion_code}-{next_val:03d}"
        print(
            f"--- Código generado en _generar_codigo_tarifa: '{codigo_final}' ---")
        return codigo_final

    def save(self, *args, **kwargs):
        print(
            f"TARIFA SAVE - INICIO. PK: {self.pk}, _state.adding: {self._state.adding}, codigo_tarifa (entrada): '{self.codigo_tarifa}'")
        is_new = self._state.adding

        # Generar código solo si es una nueva instancia y no tiene ya un código
        if is_new and not self.codigo_tarifa:
            try:
                self.codigo_tarifa = self._generar_codigo_tarifa()
            except Exception as e:
                # Fallback definitivo si _generar_codigo_tarifa tiene un error no manejado
                logger.critical(
                    f"FALLO CRÍTICO generando codigo_tarifa para nueva Tarifa: {e}. Asignando UUID de error.")
                self.codigo_tarifa = f"TAR-CRITERR-{uuid.uuid4().hex[:6].upper()}"

        # Llenar campos de ModeloBase para una mejor representación si están vacíos
        if not self.primer_nombre and self.ramo and self.rango_etario:
            try:
                self.primer_nombre = f"Tarifa {self.get_ramo_display()}"
                self.primer_apellido = f"({self.get_rango_etario_display()})"
                if self.fecha_aplicacion:
                    self.primer_apellido += f" {self.fecha_aplicacion.strftime('%d/%m/%y')}"
                if self.tipo_fraccionamiento:
                    self.segundo_nombre = f"Fracc: {self.get_tipo_fraccionamiento_display()}"
            except Exception:  # En caso de que get_..._display falle por alguna razón
                self.primer_nombre = f"Tarifa {self.ramo or 'N/A'}"
                self.primer_apellido = f"({self.rango_etario or 'N/A'})"

        super().save(*args, **kwargs)

    @property
    def monto_semestral(self):
        return (self.monto_anual / Decimal('2')).quantize(Decimal("0.01"), ROUND_HALF_UP) if self.monto_anual else Decimal('0.00')

    @property
    def monto_trimestral(self):
        return (self.monto_anual / Decimal('4')).quantize(Decimal("0.01"), ROUND_HALF_UP) if self.monto_anual else Decimal('0.00')

    @property
    def monto_mensual(self):
        return (self.monto_anual / Decimal('12')).quantize(Decimal("0.01"), ROUND_HALF_UP) if self.monto_anual else Decimal('0.00')

    def clean(self):
        """
        Validación adicional que considera el código generado
        """
        super().clean()

        # Forzar generación de código para validar antes del save
        if not self.codigo_tarifa:
            self.codigo_tarifa = self._generar_codigo_tarifa()

        # Verificar unicidad del código generado
        if Tarifa.objects.exclude(pk=self.pk).filter(codigo_tarifa=self.codigo_tarifa).exists():
            raise ValidationError(
                {"codigo_tarifa": "El código generado ya existe. ¡Esto no debería pasar!"}
            )

    @classmethod
    def con_contratos_relacionados(cls):
        return cls.objects.prefetch_related(
            # Usando el related_name por defecto si no se especifica en el FK
            'contratoindividual_set',
            # Asumiendo related_name estándar o %(class)s_set
            'contratocolectivo_set'
        )

    def __str__(self):
        if self.codigo_tarifa:
            return self.codigo_tarifa
        return f"Tarifa (PK: {self.pk or 'Nueva'}, Código Pendiente)"

    class Meta:
        verbose_name = "Tarifa"
        verbose_name_plural = "Tarifas"
        constraints = [
            models.UniqueConstraint(
                name='unique_tarifa_base_condicional',
                fields=['ramo', 'rango_etario', 'fecha_aplicacion'],
                # Para tarifas base ANUALES (sin fraccionamiento)
                condition=Q(tipo_fraccionamiento__isnull=True),
            ),
            models.UniqueConstraint(
                name='unique_tarifa_con_fraccionamiento',    # <--- ESTA ES LA RESTRICCIÓN
                fields=['ramo', 'rango_etario',
                        'fecha_aplicacion', 'tipo_fraccionamiento'],
                # Para tarifas CON fraccionamiento
                condition=Q(tipo_fraccionamiento__isnull=False),
            )
        ]
        indexes = [
            models.Index(fields=['codigo_tarifa'], name='tarifa_code_idx'),
            models.Index(fields=['monto_anual'], name='tarifa_monto_idx'),

            models.Index(fields=['ramo', 'rango_etario', 'fecha_aplicacion']),
            models.Index(fields=['activo']),
        ] + ModeloBase.Meta.indexes  # Asegúrate de heredar índices de ModeloBase
        ordering = ['ramo', 'rango_etario', '-fecha_aplicacion']
