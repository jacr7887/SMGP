# models.py
# Needed for dynamic model fetching if used in Meta or methods
# Tus validadores
from .validators import validate_past_date, validate_telefono_venezuela, validate_pasaporte
# Donde defines NIVEL_ACCESO, TIPO_USUARIO, DEPARTAMENTO
from .commons import CommonChoices, RAMO_ABREVIATURAS, RANGO_ETARIO_ABREVIATURAS
import logging  # Para logging
import uuid  # Para _generate_unique_username
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
# <--- Esto está bien, le diste un alias
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
    mensaje = models.TextField(verbose_name="Mensaje")
    tipo = models.CharField(
        max_length=10,
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
    primer_nombre = models.CharField(
        max_length=100,
        verbose_name="Primer Nombre",
        db_index=True
    )
    segundo_nombre = models.CharField(
        max_length=100,
        verbose_name="Segundo Nombre",
        blank=True,
        null=True,
        db_index=True
    )
    primer_apellido = models.CharField(
        max_length=100,
        verbose_name="Primer Apellido",
        db_index=True
    )
    segundo_apellido = models.CharField(
        max_length=100,
        verbose_name="Segundo Apellido",
        blank=True,
        null=True,
        db_index=True
    )
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
        base_username_cleaned = "".join(
            filter(str.isalnum, base_username))[:20]
        base_part = base_username_cleaned[:20]
        unique_part = uuid.uuid4().hex[:6]
        return (f"{base_part}_{unique_part}")[:150]

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        email = self.normalize_email(email)
        if 'username' not in extra_fields or not extra_fields.get('username'):
            base_username = email.split('@')[0]
            extra_fields['username'] = self._generate_unique_username(
                base_username)
        extra_fields.setdefault('nivel_acceso', 1)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        if 'tipo_usuario' not in extra_fields:
            tipo_cliente = next(
                (c[0] for c in CommonChoices.TIPO_USUARIO if c[0] == 'CLIENTE'), None)
            extra_fields.setdefault('tipo_usuario', tipo_cliente or (
                CommonChoices.TIPO_USUARIO[0][0] if CommonChoices.TIPO_USUARIO else "TIPO_DEFECTO"))
        nivel = extra_fields.get('nivel_acceso')
        is_staff = extra_fields.get('is_staff')
        is_superuser = extra_fields.get('is_superuser')
        if nivel == 5 and not (is_staff and is_superuser):
            raise ValueError("Nivel 5 debe ser staff y superuser.")
        if nivel == 4 and not is_staff:
            raise ValueError("Nivel 4 debe ser staff.")
        if nivel < 4 and is_staff:
            raise ValueError(f"Nivel {nivel} no puede ser staff.")
        if nivel < 5 and is_superuser:
            raise ValueError(f"Nivel {nivel} no puede ser superuser.")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        # El save() del modelo asignará grupo/permisos
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('nivel_acceso', 5)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('activo', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')
        if extra_fields.get('nivel_acceso') != 5:
            raise ValueError('Superuser debe tener nivel_acceso=5.')
        if 'tipo_usuario' not in extra_fields:
            tipo_admin = next(
                (c[0] for c in CommonChoices.TIPO_USUARIO if c[0] == 'ADMIN'), None)
            extra_fields['tipo_usuario'] = tipo_admin or (
                CommonChoices.TIPO_USUARIO[0][0] if CommonChoices.TIPO_USUARIO else "ADMIN_FALLBACK")
        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractUser, ModeloBase):
    # --- Indicar que los campos de AbstractUser no se usen directamente en la BD ---
    # Django no creará columnas para estos en la tabla myapp_usuario.
    # Seguirán existiendo en el objeto Python, pero no se persistirán directamente.
    # Tú usarás primer_nombre, primer_apellido de ModeloBase.
    first_name = None
    last_name = None
    # ---------------------------------------------------------------------------

    # Tus campos personalizados
    email = models.EmailField("Correo Electrónico", unique=True, error_messages={
                              'unique': "Este correo electrónico ya está registrado."}, help_text="Correo electrónico único.", validators=[validate_email])
    nivel_acceso = models.PositiveIntegerField("Nivel de Acceso", choices=CommonChoices.NIVEL_ACCESO, default=1, validators=[
                                               MinValueValidator(1), MaxValueValidator(5)], db_index=True, help_text="Define los permisos base.")
    tipo_usuario = models.CharField("Tipo de Usuario", max_length=50, choices=CommonChoices.TIPO_USUARIO,
                                    db_index=True, help_text="Clasificación funcional del usuario.")
    activo = models.BooleanField("Cuenta Activa (Personalizado)", default=True,
                                 help_text="Controla si el usuario puede iniciar sesión (fuente de verdad).")
    fecha_nacimiento = models.DateField("Fecha de Nacimiento", validators=[
                                        validate_past_date], db_index=True, null=True, blank=True)
    departamento = models.CharField(
        "Departamento", max_length=50, choices=CommonChoices.DEPARTAMENTO, blank=True, null=True, db_index=True)
    telefono = models.CharField("Teléfono", max_length=15, validators=[
                                validate_telefono_venezuela], blank=True, null=True)
    direccion = models.TextField("Dirección", blank=True, null=True)
    intermediario = models.ForeignKey('Intermediario', on_delete=models.SET_NULL, blank=True, null=True,
                                      related_name='usuarios_asignados', verbose_name="Intermediario Asociado", db_index=True)
    username = models.CharField("Nombre de usuario (interno)", max_length=150, unique=True, help_text="Requerido. Generado automáticamente si se omite.", error_messages={
                                'unique': "Un usuario con ese nombre de usuario ya existe.", }, editable=False)

    USERNAME_FIELD = 'email'
    # Estos vienen de ModeloBase
    REQUIRED_FIELDS = ['primer_nombre', 'primer_apellido']

    objects = UsuarioManager()
    all_objects = models.Manager()

    # Mapeo Nivel -> Nombre Grupo (si lo usas para _assign_group_based_on_level)
    NIVEL_A_GRUPO_NOMBRE = {
        1: "SMGP - Nivel 1 (Solo Ver)",
        2: "SMGP - Nivel 2 (Ver y Crear)",
        3: "SMGP - Nivel 3 (Ver, Crear, Editar)",
        4: "SMGP - Nivel 4 (Gestión Total Datos)",
    }

    def save(self, *args, **kwargs):
        self.is_active = self.activo

        is_new = self._state.adding

        if hasattr(self, 'nivel_acceso'):
            if self.nivel_acceso == 5:
                self.is_staff = True
                self.is_superuser = True
            elif self.nivel_acceso == 4:
                self.is_staff = True
                self.is_superuser = False
            else:
                self.is_staff = False
                self.is_superuser = False

            if self.is_superuser and self.nivel_acceso != 5:
                self.nivel_acceso = 5
                self.is_staff = True

        if is_new and not self.username:
            if hasattr(self.__class__.objects, '_generate_unique_username'):
                self.username = self.__class__.objects._generate_unique_username(
                    self.email.split('@')[0])
            else:
                self.username = self.email.split(
                    '@')[0] + "_" + uuid.uuid4().hex[:4]

        # Sincronizar los campos de nombre de AbstractUser con los de ModeloBase
        # ANTES de llamar a super().save() para que AbstractUser.get_full_name() funcione
        # si alguna parte de Django lo usa internamente.
        # Esto es opcional si solo usas tu propio get_full_name().
        # setattr(self, AbstractUser.first_name.field.name, self.primer_nombre or "")
        # setattr(self, AbstractUser.last_name.field.name, self.primer_apellido or "")

        super().save(*args, **kwargs)

        if hasattr(self, '_assign_group_based_on_level'):
            old_nivel_acceso_para_grupo = None
            if not is_new and self.pk:
                try:
                    old_instance = type(self).objects.only(
                        'nivel_acceso').get(pk=self.pk)
                    old_nivel_acceso_para_grupo = old_instance.nivel_acceso
                except type(self).DoesNotExist:
                    logger.warning(
                        f"Usuario PK {self.pk} no encontrado para obtener old_nivel_acceso en save().")

            nivel_actual = self.nivel_acceso
            if is_new or (old_nivel_acceso_para_grupo is not None and old_nivel_acceso_para_grupo != nivel_actual):
                self._assign_group_based_on_level(
                    old_level_acceso=old_nivel_acceso_para_grupo)
            elif old_nivel_acceso_para_grupo is None and not is_new and self.pk:
                self._assign_group_based_on_level(old_level_acceso=None)

    def _assign_group_based_on_level(self, old_level_acceso=None):
        # Tu lógica de asignación de grupos
        if not self.pk:
            return
        # Importar aquí para evitar circularidad
        from django.contrib.auth.models import Group
        current_group_name = self.NIVEL_A_GRUPO_NOMBRE.get(self.nivel_acceso)
        groups_managed_by_level = set(self.NIVEL_A_GRUPO_NOMBRE.values())
        groups_to_remove = [g for g in self.groups.all(
        ) if g.name in groups_managed_by_level and g.name != current_group_name]
        if groups_to_remove:
            self.groups.remove(*groups_to_remove)
        if current_group_name:
            try:
                group_obj, created = Group.objects.get_or_create(
                    name=current_group_name)
                if created:
                    logger.warning(
                        f"Grupo '{current_group_name}' CREADO automáticamente.")
                if not self.groups.filter(pk=group_obj.pk).exists():
                    self.groups.add(group_obj)
            except Exception as e:
                logger.error(
                    f"Error asignando/creando grupo '{current_group_name}': {e}", exc_info=True)

    def get_full_name(self):  # Tu método personalizado
        parts = [self.primer_apellido, self.segundo_apellido]
        apellidos = " ".join(p for p in parts if p).strip()
        parts = [self.primer_nombre, self.segundo_nombre]
        nombres = " ".join(p for p in parts if p).strip()
        if apellidos and nombres:
            return f"{apellidos}, {nombres}"
        return nombres or apellidos or self.email

    # Sobrescribir get_short_name de AbstractUser para usar tu primer_nombre
    def get_short_name(self):
        return self.primer_nombre or self.email.split('@')[0]

    def __str__(self):
        return self.get_full_name() or self.email

    class Meta:
        verbose_name = "Usuario del Sistema"
        verbose_name_plural = "Usuarios del Sistema"
        indexes = [
            models.Index(fields=['nivel_acceso', 'activo']),
            models.Index(fields=['departamento', 'activo']),
            models.Index(fields=['email'])
        ] + (ModeloBase.Meta.indexes if hasattr(ModeloBase, 'Meta') and hasattr(ModeloBase.Meta, 'indexes') else [])
        ordering = ['primer_apellido', 'primer_nombre', 'email']
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
        editable=False,
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
        default=timezone.now,
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
        db_index=True,
        help_text="Costo total del contrato para el período de vigencia especificado."
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

    def save(self, *args, **kwargs):
        # La lógica de fechas (periodo_vigencia_meses vs fecha_fin_vigencia)
        # se manejará en las clases hijas (ContratoIndividual, ContratoColectivo)
        # antes de llamar a este super().save().

        # Cálculo de monto_total:
        # Si el monto_total no fue provisto o es inválido, intentar calcularlo.
        # Las clases hijas pueden haber pre-calculado un monto_total más específico.
        if not hasattr(self, '_monto_total_pre_calculado_por_hijo') or not self._monto_total_pre_calculado_por_hijo:
            calculated_monto = self._calculate_monto_total_base()
            if calculated_monto is not None and not calculated_monto.is_nan():
                self.monto_total = calculated_monto
            elif self.monto_total is None or (isinstance(self.monto_total, Decimal) and self.monto_total.is_nan()):
                self.monto_total = Decimal('0.00')
                logger.info(
                    f"ContratoBase {self.numero_contrato or self.pk or 'Nuevo'}: monto_total no calculado y era None/NaN, establecido a 0.00.")

        # Asegurar que monto_total no sea None antes del save final
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
    cedula = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Cédula de Identidad",
        db_index=True,
        help_text=(
            "Cédula de Identidad del afiliado. Formato: V-12345678 o E-8765432 (guion opcional)."),
        validators=[validate_cedula]
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
    fecha_nacimiento = models.DateField(
        verbose_name="Fecha de Nacimiento",
        validators=[validate_past_date],
        db_index=True,
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
    direccion_habitacion = models.TextField(
        verbose_name="Dirección Habitación",
        blank=True,
        null=True,
        help_text=("Dirección completa de residencia. Mínimo 10 caracteres.")
    )
    telefono_habitacion = models.CharField(
        max_length=15,
        verbose_name="Teléfono Habitación",
        blank=True,
        null=True,
        help_text="Teléfono de contacto residencial. Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",
    )
    email = models.EmailField(
        verbose_name="Correo Electrónico",
        blank=True,
        null=True,
        help_text="Correo electrónico personal del afiliado (opcional)."
    )
    direccion_oficina = models.TextField(
        verbose_name="Dirección Oficina",
        blank=True,
        null=True,
        help_text="Dirección del lugar de trabajo del afiliado (opcional)."
    )
    telefono_oficina = models.CharField(
        max_length=15,
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

    def save(self, *args, **kwargs):

        is_new = self._state.adding
        # Generar/actualizar codigo_validacion si está vacío o si es una actualización
        # y quieres que se regenere (esto último es opcional).
        # Por ahora, solo si está vacío al crear.
        if is_new and not self.codigo_validacion:
            # El PK no estará disponible aquí, así que el código tendrá "NVO"
            # Se actualizará post-save si es necesario.
            self.codigo_validacion = self._generar_codigo_validacion()
            self._cv_needs_update_post_save = True  # Flag para actualizar post-save
        else:
            self._cv_needs_update_post_save = False

        super().save(*args, **kwargs)

        if hasattr(self, '_cv_needs_update_post_save') and self._cv_needs_update_post_save and self.pk:
            new_cv = self._generar_codigo_validacion()  # Ahora self.pk existe
            if self.codigo_validacion != new_cv:  # Solo actualizar si es diferente
                AfiliadoIndividual.objects.filter(
                    pk=self.pk).update(codigo_validacion=new_cv)
                self.codigo_validacion = new_cv  # Actualizar instancia en memoria
            del self._cv_needs_update_post_save  # Limpiar flag

    class Meta:
        verbose_name = "Afiliado Individual"
        verbose_name_plural = "Afiliados Individuales"
        indexes = [
            models.Index(fields=['tipo_identificacion', 'cedula']),
            models.Index(fields=['primer_apellido', 'primer_nombre']),
            models.Index(fields=['fecha_nacimiento']),
            models.Index(fields=['fecha_ingreso']),
        ]
        ordering = ['primer_apellido', 'primer_nombre']

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

    razon_social = models.CharField(
        max_length=255,  # Aumentado para nombres largos
        verbose_name="Razón Social",
        db_index=True,
        null=False,
        blank=False,
        help_text="Nombre legal completo de la empresa o institución."
    )

    rif = models.CharField(
        max_length=12,
        unique=True,
        verbose_name="RIF",
        null=True,
        blank=True,
        default=None,
        validators=[validate_rif],
        help_text="RIF de la empresa. Formato Requerido: Letra-8Números-1Número (Ej: J-12345678-9).",
    )
    tipo_empresa = models.CharField(
        max_length=50,
        choices=CommonChoices.TIPO_EMPRESA,
        verbose_name="Tipo de Empresa",
        default='PRIVADA',
        help_text="Clasificación de la empresa (ej. Pública, Privada)."
    )

    # === Dirección comercial ===
    direccion_comercial = models.TextField(
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
    telefono_contacto = models.CharField(
        max_length=15,
        verbose_name="Teléfono Principal",
        validators=[validate_telefono_venezuela],
        blank=True,
        help_text="Número de teléfono principal de contacto. Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",  # <-- MODIFICADO
        null=True
    )
    email_contacto = models.EmailField(
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
        is_new = self._state.adding
        if not self.primer_nombre and self.razon_social:
            self.primer_nombre = self.razon_social[:100]
        if not self.primer_apellido:
            self.primer_apellido = "(Colectivo)"

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Afiliado Colectivo"
        verbose_name_plural = "Afiliados Colectivos"
        indexes = [
            models.Index(fields=['rif']),
            models.Index(fields=['razon_social']),
            models.Index(fields=['rif', 'razon_social']),
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
    activo = models.BooleanField(default=True, verbose_name="Estado activo",
                                 help_text="Indica si este registro de contrato individual está activo en el sistema.")
    tipo_identificacion_contratante = models.CharField(
        max_length=20,
        choices=CommonChoices.TIPO_IDENTIFICACION,
        verbose_name="Tipo de Identificación del Contratante",

        help_text="Tipo de documento (Cédula o RIF) de la persona o entidad que paga el contrato."
    )
    contratante_cedula = models.CharField(
        max_length=15,
        verbose_name="Cédula/RIF del Contratante",
        # <-- MODIFICADO
        help_text="Cédula o RIF de quien paga. Introduzca V/E + 7-8 dígitos (Cédula) o J/G/V/E + 8 dígitos + verificador (RIF, formato con guiones requerido).",
        db_index=True,
    )
    contratante_nombre = models.CharField(
        max_length=255,
        verbose_name="Nombre del Contratante",
        help_text="Nombre completo o razón social de quien paga el contrato."
    )
    direccion_contratante = models.TextField(
        verbose_name="Dirección del Contratante",
        blank=True,
        null=True,
        help_text="Dirección fiscal o principal del contratante."
    )
    telefono_contratante = models.CharField(
        max_length=15,
        verbose_name="Teléfono del Contratante",
        blank=True,
        null=True,
        help_text="Teléfono de contacto del contratante. Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",  # <-- MODIFICADO
    )
    email_contratante = models.EmailField(
        verbose_name="Email del Contratante",
        blank=True,
        null=True,
        help_text="Correo electrónico principal del contratante."
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
    comision_anual = models.DecimalField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        max_digits=5,
        decimal_places=2,
        verbose_name="Comisión Anual (%)",
        # <-- MODIFICADO
        help_text="Porcentaje de comisión anual para el intermediario. Entre 0.00 y 100.00.",
        blank=True,
        null=True
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

    @property
    def monto_comision_intermediario_estimada(self):
        """
        Suma los montos de todas las comisiones (DIRECTA y OVERRIDE si aplica al intermediario del contrato)
        que están PENDIENTES o PAGADAS para este contrato individual.
        """
        # Necesitamos el modelo RegistroComision. Si está en el mismo archivo, no hay problema.
        # Si está en otro, asegúrate de la importación.
        # from .models import RegistroComision # Descomentar si es necesario y no causa circularidad

        # Comisiones directas para el intermediario de este contrato
        comisiones_directas = RegistroComision.objects.filter(
            contrato_individual=self,
            intermediario=self.intermediario,  # El intermediario principal del contrato
            tipo_comision='DIRECTA',
            estatus_pago_comision__in=['PENDIENTE', 'PAGADA']
        ).aggregate(total=Coalesce(Sum('monto_comision'), Value(Decimal('0.00')), output_field=DecimalField()))['total']

        # Comisiones de override donde este contrato fue la venta original
        # y el beneficiario del override es el padre del intermediario de este contrato.
        # Esto es un poco más complejo si el intermediario del contrato no tiene padre,
        # o si el override se paga a alguien más arriba en la jerarquía.
        # Por simplicidad, si solo te interesa la comisión directa generada por este contrato
        # para su intermediario principal, puedes omitir la parte de override aquí
        # o ajustarla a tu estructura de comisiones.

        # Ejemplo simplificado: solo comisiones directas para el intermediario del contrato
        # Si quieres incluir overrides donde este contrato es la fuente y el intermediario
        # del contrato es el VENDEDOR, y su PADRE recibe el override, la lógica sería:
        # comisiones_override_para_padre = RegistroComision.objects.filter(
        #     contrato_individual=self,
        #     intermediario_vendedor=self.intermediario, # Este intermediario hizo la venta
        #     intermediario=self.intermediario.intermediario_relacionado, # El padre recibe
        #     tipo_comision='OVERRIDE',
        #     estatus_pago_comision__in=['PENDIENTE', 'PAGADA']
        # ).aggregate(total=Coalesce(Sum('monto_comision'), Value(Decimal('0.00')), output_field=DecimalField()))['total']
        # total_comisiones = comisiones_directas + comisiones_override_para_padre

        # Por ahora, nos enfocaremos en la comisión directa generada por este contrato
        # para el intermediario asignado a este contrato.
        # Si el campo "Comisión Intermediario (Estimada)" en tu detalle se refiere
        # solo a la comisión directa del intermediario principal del contrato:
        return comisiones_directas.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _generar_recibo_inicial_contrato(self):
        # print(f"    CI (PK:{self.pk or 'Nuevo'}) GENERANDO RECIBO INICIAL...")
        fecha_em = self.fecha_emision or timezone.now()
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
        self._monto_total_pre_calculado_por_hijo = False  # Flag para ContratoBase

        # --- MANEJO DE fecha_emision (DateTimeField) ---
        if self.fecha_emision:  # Si fecha_emision ya tiene un valor
            if timezone.is_naive(self.fecha_emision):
                logger_model_save.warning(
                    f"ContratoIndividual (PK: {self.pk or 'Nuevo'}, Num: {self.numero_contrato or 'N/A'}): "
                    f"fecha_emision ({self.fecha_emision}) era naive. Haciéndola aware con current_timezone."
                )
                self.fecha_emision = timezone.make_aware(
                    self.fecha_emision, timezone.get_current_timezone())
        elif is_new:  # Si es nuevo y fecha_emision no fue provista, usar timezone.now()
            logger_model_save.info(
                f"ContratoIndividual (PK: {self.pk or 'Nuevo'}, Num: {self.numero_contrato or 'N/A'}): "
                f"fecha_emision no provista y es nuevo. Usando timezone.now()."
            )
            self.fecha_emision = timezone.now()
        # Si no es nuevo y fecha_emision es None, se permite (asumiendo que el campo permite null=True o blank=True)
        # aunque para fecha_emision usualmente no sería el caso.

        # --- INICIO DE MODIFICACIONES PARA GENERACIÓN DE CÓDIGOS ÚNICOS ---
        if is_new:
            if not self.numero_contrato:
                self.numero_contrato = f"CONT-IND-{uuid.uuid4().hex[:12].upper()}"
                logger_model_save.info(
                    f"ContratoIndividual nuevo, numero_contrato generado (UUID): {self.numero_contrato}")

            if not self.numero_poliza:
                self.numero_poliza = f"POL-IND-{uuid.uuid4().hex[:12].upper()}"
                logger_model_save.info(
                    f"ContratoIndividual nuevo, numero_poliza generado (UUID): {self.numero_poliza}")

            if not self.certificado:
                self.certificado = f"CERT-IND-{uuid.uuid4().hex[:12].upper()}"
                logger_model_save.info(
                    f"ContratoIndividual nuevo, certificado generado (UUID): {self.certificado}")

            if not self.numero_recibo:
                # self.fecha_emision ya es aware aquí
                fecha_recibo_str = (
                    self.fecha_emision or timezone.now()).strftime("%y%m%d")
                self.numero_recibo = f"REC-IND-{fecha_recibo_str}-{uuid.uuid4().hex[:10].upper()}"
                logger_model_save.info(
                    f"ContratoIndividual nuevo, numero_recibo generado (UUID): {self.numero_recibo}")
        # --- FIN DE MODIFICACIONES PARA GENERACIÓN DE CÓDIGOS ÚNICOS ---

        if self.afiliado:
            if is_new or not self.primer_nombre:
                self.primer_nombre = self.afiliado.primer_nombre
                self.segundo_nombre = self.afiliado.segundo_nombre
                self.primer_apellido = self.afiliado.primer_apellido
                self.segundo_apellido = self.afiliado.segundo_apellido

        # Asegurar que fecha_inicio_vigencia (DateField) se base en una fecha consciente si es necesario
        if not self.fecha_inicio_vigencia and self.fecha_emision:
            # self.fecha_emision esDateTimeField aware, .date() lo convierte a objeto date
            self.fecha_inicio_vigencia = self.fecha_emision.date()

        # Sincronizar periodo_vigencia_meses y fecha_fin_vigencia (DateField)
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
                else:
                    self.fecha_fin_vigencia = None

        # dias_transcurridos_ingreso
        if self.afiliado and self.afiliado.fecha_ingreso and self.fecha_emision:
            fecha_ing_afiliado = self.afiliado.fecha_ingreso  # DateField
            # Convertir fecha_emision (DateTimeField aware) a objeto date para comparar
            fecha_emi_contrato_date = self.fecha_emision.date()

            if isinstance(fecha_ing_afiliado, date) and isinstance(fecha_emi_contrato_date, date):
                self.dias_transcurridos_ingreso = (
                    fecha_emi_contrato_date - fecha_ing_afiliado).days if fecha_emi_contrato_date >= fecha_ing_afiliado else 0
            else:
                # Esto no debería pasar si los tipos son correctos
                self.dias_transcurridos_ingreso = None
                logger_model_save.warning(
                    f"ContratoIndividual {self.numero_contrato or self.pk or 'Nuevo'}: No se pudo calcular dias_transcurridos_ingreso. fecha_ing_afiliado: {fecha_ing_afiliado}, fecha_emi_contrato_date: {fecha_emi_contrato_date}")
        else:
            self.dias_transcurridos_ingreso = None

        # La lógica de monto_total se maneja en ContratoBase.save() o si la sobreescribes aquí
        # y activas el flag self._monto_total_pre_calculado_por_hijo = True

        super().save(*args, **kwargs)  # Llama a ContratoBase.save()

    def generate_contract_number(self):
        with transaction.atomic():  # Transacción atómica completa
            try:
                current_date = timezone.now().strftime("%y%m%d")
                seq_name = f'ci_{current_date}'

                logger.debug(
                    f"[Generate Contract Num - Ind] Secuencia: {seq_name}")
                next_val = get_next_value(seq_name, initial_value=1)

                return f"CONT-IND-{timezone.now().strftime('%Y%m%d')}-{next_val:04d}"

            except Exception as e:
                logger.exception(
                    f"Error generando número de contrato individual: {e}")
                timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
                unique_id = uuid.uuid4().hex[:6]  # ID más corto pero único
                return f"ERR-CI-{timestamp}-{unique_id}"

    def generate_policy_number(self):
        with transaction.atomic():  # Transacción atómica completa
            try:
                current_date = timezone.now().strftime("%y%m%d")
                seq_name = f'pi_{current_date}'

                logger.debug(
                    f"[Generate Policy Num - Ind] Secuencia: {seq_name}")
                next_val = get_next_value(seq_name, initial_value=1)

                return f"POL-IND-{timezone.now().strftime('%Y%m%d')}-{next_val:04d}"

            except Exception as e:
                logger.exception(
                    f"Error generando número de póliza individual: {e}")
                timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
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
    def total_pagado_a_facturas(self):
        # Suma los Pago.monto_pago de las Facturas activas de este contrato
        if hasattr(self, 'factura_set'):  # 'factura_set' es el related_name por defecto
            pagos = self.factura_set.filter(activo=True, pagos__activo=True).aggregate(
                total=Coalesce(Sum('pagos__monto_pago'), Decimal(
                    '0.00'), output_field=DecimalField())
            )['total']
            return pagos.quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal('0.00')

    @property
    def saldo_pendiente_contrato(self):
        if not self.monto_total or self.monto_total < Decimal('0.00'):
            return Decimal('0.00')
        pendiente = self.monto_total - self.total_pagado_a_facturas
        return max(Decimal('0.00'), pendiente).quantize(Decimal("0.01"), ROUND_HALF_UP)

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
    razon_social = models.CharField(
        max_length=255,
        verbose_name="Razón Social de la Empresa",
        db_index=True,
        null=True,
        help_text="Nombre legal completo de la empresa contratante."
    )
    rif = models.CharField(
        max_length=12,
        verbose_name="RIF de la Empresa (Copiado)",
        validators=[validate_rif],
        help_text="RIF de la empresa contratante (copiado automáticamente).",
        db_index=True,
        blank=True,
        null=True
    )
    cantidad_empleados = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Cantidad de Empleados",
        db_index=True,
        help_text="Número total de empleados cubiertos o elegibles bajo este contrato."
    )
    direccion_comercial = models.TextField(
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
        fecha_em = self.fecha_emision or timezone.now()
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

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        self._monto_total_pre_calculado_por_hijo = False

        # --- MANEJO DE fecha_emision (DateTimeField) ---
        if self.fecha_emision:
            if timezone.is_naive(self.fecha_emision):
                logger_model_save.warning(
                    f"ContratoColectivo (PK: {self.pk or 'Nuevo'}, Num: {self.numero_contrato or 'N/A'}): "
                    f"fecha_emision ({self.fecha_emision}) era naive. Haciéndola aware con current_timezone."
                )
                self.fecha_emision = timezone.make_aware(
                    self.fecha_emision, timezone.get_current_timezone())
        elif is_new:
            logger_model_save.info(
                f"ContratoColectivo (PK: {self.pk or 'Nuevo'}, Num: {self.numero_contrato or 'N/A'}): "
                f"fecha_emision no provista y es nuevo. Usando timezone.now()."
            )
            self.fecha_emision = timezone.now()

        # --- Generación de Códigos Únicos (como estaba) ---
        if is_new:
            if not self.numero_contrato:
                self.numero_contrato = f"CONT-COL-{uuid.uuid4().hex[:12].upper()}"
                logger_model_save.info(
                    f"ContratoColectivo nuevo, numero_contrato generado (UUID): {self.numero_contrato}")
            if not self.numero_poliza:
                self.numero_poliza = f"POL-COL-{uuid.uuid4().hex[:12].upper()}"
                logger_model_save.info(
                    f"ContratoColectivo nuevo, numero_poliza generado (UUID): {self.numero_poliza}")
            if not self.certificado:
                self.certificado = f"CERT-COL-{uuid.uuid4().hex[:8].upper()}"
                logger_model_save.info(
                    f"ContratoColectivo nuevo, certificado generado (UUID): {self.certificado}")
            if not self.numero_recibo:
                fecha_recibo_str = (
                    self.fecha_emision or timezone.now()).strftime("%y%m%d")
                self.numero_recibo = f"REC-COL-{fecha_recibo_str}-{uuid.uuid4().hex[:10].upper()}"
                logger_model_save.info(
                    f"ContratoColectivo nuevo, numero_recibo generado (UUID): {self.numero_recibo}")
            if not self.codigo_validacion:  # Asumo que este también debe ser único o generado
                self.codigo_validacion = f"VAL-CCC-{uuid.uuid4().hex[:12].upper()}"
                logger_model_save.info(
                    f"ContratoColectivo nuevo, codigo_validacion generado (UUID): {self.codigo_validacion}")

        # Llenar campos de ModeloBase
        if not self.primer_nombre and self.razon_social:
            parts = self.razon_social.split(maxsplit=1)
            self.primer_nombre = parts[0][:100]
            self.primer_apellido = f"(Colectivo {self.rif or ''})"[
                :100] if len(parts) > 1 else "(Colectivo)"
        elif not self.primer_nombre:  # Fallback si no hay razon_social
            self.primer_nombre = "Colectivo Sin Razón Social"
            self.primer_apellido = "(Colectivo)"

        # Asegurar que fecha_inicio_vigencia (DateField) se base en una fecha consciente
        if not self.fecha_inicio_vigencia and self.fecha_emision and is_new:
            self.fecha_inicio_vigencia = self.fecha_emision.date()

        # Sincronizar periodo_vigencia_meses y fecha_fin_vigencia (DateField)
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
                else:
                    self.fecha_fin_vigencia = None

        # Cálculo de monto_total específico para ContratoColectivo
        monto_colectivo_calculado = self._calculate_monto_total_colectivo()
        if monto_colectivo_calculado is not None:
            self.monto_total = monto_colectivo_calculado
            self._monto_total_pre_calculado_por_hijo = True
        elif self.monto_total is None:  # Si no se pudo calcular y no se proveyó
            self.monto_total = Decimal('0.00')

        super().save(*args, **kwargs)  # Llama a ContratoBase.save()

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
    def monto_comision_intermediario_estimada(self):
        """
        Calcula la comisión estimada para el intermediario basada en el monto total del contrato
        y el porcentaje de comisión de la tarifa aplicada.
        ContratoColectivo no tiene un campo 'comision_anual' directo como ContratoIndividual.
        """
        if self.monto_total and self.tarifa_aplicada and self.tarifa_aplicada.comision_intermediario is not None:
            try:
                comision = (Decimal(str(self.monto_total)) * Decimal(
                    str(self.tarifa_aplicada.comision_intermediario))) / Decimal('100.00')
                return comision.quantize(Decimal("0.01"), ROUND_HALF_UP)
            except (InvalidOperation, TypeError):
                return None  # O Decimal('0.00')
        return None  # O Decimal('0.00')

    @property
    def total_pagado_a_facturas(self):  # Para el "Resumen Financiero"
        if hasattr(self, 'factura_set'):
            pagos = self.factura_set.filter(activo=True, pagos__activo=True).aggregate(
                total=Coalesce(Sum('pagos__monto_pago'), Decimal(
                    '0.00'), output_field=DecimalField())
            )['total']
            return pagos.quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal('0.00')

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
    nombre_completo = models.CharField(
        max_length=255,
        verbose_name="Nombre Completo del Intermediario",
        db_index=True,
        help_text="Nombre completo o razón social del intermediario."
    )
    rif = models.CharField(
        max_length=12,
        verbose_name="RIF",
        blank=True,
        null=True,
        db_index=True,
        help_text="Formato Requerido: Letra-8Números-1Número (Ej: J-12345678-9).",
        validators=[validate_rif]  # Asegúrate que validate_rif esté definido
    )
    direccion_fiscal = models.TextField(
        verbose_name="Dirección Fiscal",
        blank=True,
        null=True,
        help_text="Dirección fiscal registrada del intermediario."
    )
    telefono_contacto = models.CharField(
        max_length=15,
        verbose_name="Teléfono de Contacto",
        blank=True,
        null=True,
        help_text="Formato: 04XX-XXXXXXX o 02XX-XXXXXXX.",
        # validators=[validate_telefono_venezuela] # Descomentar si se aplica
    )
    email_contacto = models.EmailField(
        verbose_name="Email de Contacto",
        blank=True,
        null=True,
        # Asegúrate que validate_email esté definido
        validators=[validate_email],
        db_index=True,
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
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(
            Decimal('20.00'))],  # Límite para override
        verbose_name="Porcentaje de Override",
        help_text="Porcentaje adicional que este intermediario gana sobre las ventas de sus intermediarios subordinados (si aplica).",
        blank=True,  # Puede ser opcional
        null=False  # Default 0.00 es mejor que Null para cálculos
    )
    # Asegúrate que settings.AUTH_USER_MODEL esté importado o usa settings.AUTH_USER_MODEL
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
        is_new = self._state.adding

        if is_new and not self.codigo:
            # ----- INICIO CAMBIO TEMPORAL Y DIRECTO PARA Intermediario.codigo -----
            # Generar un código único usando UUID para evitar problemas con django-sequences
            # para este modelo específico durante el seeding.

            prefijo_temp = "INT-"
            # El max_length del campo 'codigo' es 15.
            # "INT-" ocupa 4 caracteres.
            # Quedan 15 - 4 = 11 caracteres para la parte del UUID.
            uuid_hex_length = 11

            # Intentar generar un código único hasta que se encuentre uno que no exista
            # (extremadamente improbable que haya colisión con UUID, pero es una buena práctica)
            max_attempts = 5
            for _ in range(max_attempts):
                generated_code = f"{prefijo_temp}{uuid.uuid4().hex[:uuid_hex_length].upper()}"
                # Usar all_objects para la verificación
                if not Intermediario.all_objects.filter(codigo=generated_code).exists():
                    self.codigo = generated_code
                    break
            else:
                # Si después de varios intentos no se encuentra uno único (casi imposible con UUID)
                # recurrir a un UUID más largo y truncar, o lanzar un error.
                # Por simplicidad para el seeder, si esto falla, es un problema mayor.
                logger.error(
                    f"No se pudo generar un código UUID único para Intermediario después de {max_attempts} intentos. Usando UUID completo truncado.")
                self.codigo = uuid.uuid4().hex[:self._meta.get_field(
                    'codigo').max_length]  # Trunca al max_length del campo

            logger.info(
                f"Intermediario nuevo (PK: {self.pk or 'Pre-save'}), código generado (UUID): {self.codigo}")
            # ----- FIN CAMBIO TEMPORAL -----

        # Lógica opcional para llenar nombres/apellidos (mantenla si la tienes)
        if not self.primer_nombre and self.nombre_completo:
            parts = self.nombre_completo.split(maxsplit=1)
            self.primer_nombre = parts[0][:100]
            if len(parts) > 1:
                self.primer_apellido = parts[1][:100]
            else:
                self.primer_apellido = "(Intermediario)"

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


class Factura(ModeloBase):  # Asegúrate que herede de ModeloBase si lo necesita
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
        help_text="Estado del ciclo de vida de la factura (ej. Generada, Cobranza, Pagada, Anulada)."
    )
    contrato_individual = models.ForeignKey(
        'ContratoIndividual',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='factura_set',
        help_text="Contrato individual al que corresponde esta factura (si aplica)."
    )
    contrato_colectivo = models.ForeignKey(
        'ContratoColectivo',
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
        'Intermediario',
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
        validators=[MinValueValidator(Decimal('0.01'))],
        default=Decimal('0.00'),
        help_text="Monto base (subtotal) de la factura. Debe ser mayor a 0."
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
        validators=[MinValueValidator(1)],
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
        # unique=True, # Comentado - Revisar si realmente debe ser único
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

    # --- Managers ---
    objects = SoftDeleteManager()  # Usar SoftDeleteManager si aplica
    all_objects = models.Manager()  # Manager estándar siempre disponible

    def _generar_numero_recibo_factura(self):
        # Intenta mantener algo de información si es útil
        fecha_actual_str = timezone.now().strftime("%y%m%d")
        tipo_contrato_str = "UNK"
        id_contrato_ref_simple = "NA"

        contrato_obj = self.contrato_individual or self.contrato_colectivo
        if contrato_obj:
            tipo_contrato_str = "IND" if self.contrato_individual else "COL"
            # Usar el PK del contrato si ya existe, de lo contrario un placeholder
            id_contrato_ref_simple = str(
                contrato_obj.pk) if contrato_obj.pk else "NEW"

        # Generar una parte UUID para asegurar unicidad
        # "REC-" (4) + tipo (3) + "-" (1) + id_contrato (hasta ~5 si es PK) + "-" (1) + fecha (6) + "-" (1) + UUID (variable)
        # Ejemplo: REC-COL-12345-250513-UUIDPART
        # Max length de numero_recibo es 50.
        # Longitud base sin UUID: 4+3+1+5+1+6+1 = 21 (asumiendo PK de 5 dígitos)
        # Quedan 50 - 21 = 29 caracteres para el UUID. Es más que suficiente.
        # 12 caracteres de UUID son muy únicos
        uuid_part = uuid.uuid4().hex[:12].upper()

        return f"REC-{tipo_contrato_str}-{id_contrato_ref_simple}-{fecha_actual_str}-{uuid_part}"

    def _generar_relacion_ingreso_factura(self):
        fecha_actual = timezone.now()
        fecha_str_completa = fecha_actual.strftime("%Y%m%d")
        seq_name = f"fact_ri_{fecha_actual.strftime('%y%m')}"
        prefijo = f"RI-{fecha_str_completa}-"
        return generar_codigo_unico(seq_name, prefijo, 5, fallback_prefix=f"RI-ERR-{fecha_str_completa}")

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        update_fields = kwargs.get('update_fields', None)

        if is_new:
            if not self.numero_recibo:
                self.numero_recibo = self._generar_numero_recibo_factura()
            if not self.relacion_ingreso:
                self.relacion_ingreso = self._generar_relacion_ingreso_factura()
            # Para nuevas facturas, el monto pendiente es el monto total
            self.monto_pendiente = self.monto or Decimal('0.00')
            self.pagada = False  # Una nueva factura no está pagada

        # Siempre recalcular monto_pendiente y pagada si no se están actualizando específicamente
        # y si el objeto ya tiene un PK (es decir, no es la primera vez que se guarda y es un update).
        # O si es nuevo y no se inicializaron arriba.
        # La señal se encargará de actualizar estos campos después de un pago.
        # Esta lógica aquí es más para guardados manuales o cuando no interviene la señal de Pago.
        if self.pk and (update_fields is None or ('monto_pendiente' not in update_fields and 'pagada' not in update_fields)):
            try:
                # Usar self.pagos.all() es correcto aquí para reflejar el estado actual de los pagos asociados
                total_pagado_actual = self.pagos.filter(activo=True).aggregate(
                    total=Coalesce(Sum('monto_pago'), Decimal('0.00'), output_field=DecimalField()))['total']
                self.monto_pendiente = max(
                    Decimal('0.00'), (self.monto or Decimal('0.00')) - total_pagado_actual)
                self.pagada = (self.monto_pendiente <= self.TOLERANCE)
            except Exception as e:  # Fallback si hay error con la agregación
                logger.error(
                    f"Error calculando monto_pendiente/pagada en Factura.save() para PK {self.pk}: {e}")
                if self.monto_pendiente is None:  # Si no se pudo calcular y era None
                    self.monto_pendiente = self.monto or Decimal('0.00')
                if not hasattr(self, 'pagada'):  # Si pagada no estaba definida
                    self.pagada = False

        # Lógica para estatus_factura (basada en self.pagada y vigencia)
        # Esta lógica se ejecutará siempre, usando el valor de self.pagada (ya sea el recién calculado o el que venía)
        estatus_actual_instancia = self.estatus_factura
        estatus_deberia_ser = self.estatus_factura  # Por defecto, mantener el actual

        if self.pagada:
            estatus_deberia_ser = 'PAGADA'
        elif estatus_actual_instancia != 'ANULADA':  # No cambiar si ya está anulada
            esta_vencida = False
            if self.vigencia_recibo_hasta and isinstance(self.vigencia_recibo_hasta, date):
                # Considerar un umbral de vencimiento, ej. 30 días después de vigencia_hasta
                if django_timezone.now().date() > (self.vigencia_recibo_hasta + timedelta(days=CommonChoices.DIAS_VENCIMIENTO_FACTURA if hasattr(CommonChoices, 'DIAS_VENCIMIENTO_FACTURA') else 30)):  # Usar constante si existe
                    esta_vencida = True

            if esta_vencida:
                estatus_deberia_ser = 'VENCIDA'
            # Si es nueva o ya pendiente, y no pagada/vencida
            elif estatus_actual_instancia == 'GENERADA' or estatus_actual_instancia == 'PENDIENTE':
                estatus_deberia_ser = 'PENDIENTE'
            # Si estaba PAGADA pero ahora no (ej. pago inactivado), y no vencida, pasa a PENDIENTE
            elif estatus_actual_instancia == 'PAGADA' and not self.pagada and not esta_vencida:
                estatus_deberia_ser = 'PENDIENTE'

        # Aplicar el nuevo estatus solo si es diferente y válido
        if estatus_actual_instancia != estatus_deberia_ser and any(choice[0] == estatus_deberia_ser for choice in CommonChoices.ESTATUS_FACTURA):
            self.estatus_factura = estatus_deberia_ser

        super().save(*args, **kwargs)

    def __str__(self):
        contrato_info = "N/A"
        if self.contrato_individual and self.contrato_individual.numero_contrato:
            contrato_info = f"CI:{self.contrato_individual.numero_contrato}"
        elif self.contrato_individual:
            contrato_info = f"CI_PK:{self.contrato_individual.pk}"
        elif self.contrato_colectivo and self.contrato_colectivo.numero_contrato:
            contrato_info = f"CC:{self.contrato_colectivo.numero_contrato}"
        elif self.contrato_colectivo:
            contrato_info = f"CC_PK:{self.contrato_colectivo.pk}"

        recibo = self.numero_recibo or "REC_PENDIENTE"
        return f"Factura {recibo} ({contrato_info}) Monto: {self.monto:.2f} Pend: {self.monto_pendiente:.2f}"

    def clean(self):
        super().clean()
        if not self.contrato_individual and not self.contrato_colectivo:
            raise ValidationError(
                "La factura debe estar vinculada a un Contrato Individual o Colectivo.")
        if self.contrato_individual and self.contrato_colectivo:
            raise ValidationError(
                "La factura no puede estar vinculada a ambos tipos de contrato.")
        contrato = self.contrato_individual or self.contrato_colectivo
        if contrato:
            if self.vigencia_recibo_desde and self.vigencia_recibo_hasta:
                if self.vigencia_recibo_hasta < self.vigencia_recibo_desde:
                    raise ValidationError(
                        {'vigencia_recibo_hasta': "La fecha de fin de vigencia del recibo debe ser igual o posterior a la de inicio."})
                if contrato.fecha_inicio_vigencia and self.vigencia_recibo_desde < contrato.fecha_inicio_vigencia:
                    raise ValidationError(
                        {'vigencia_recibo_desde': "La vigencia del recibo no puede iniciar antes que la del contrato."})
                if contrato.fecha_fin_vigencia and self.vigencia_recibo_hasta > contrato.fecha_fin_vigencia:
                    raise ValidationError(
                        {'vigencia_recibo_hasta': "La vigencia del recibo no puede terminar después que la del contrato."})
            elif self.vigencia_recibo_desde and not self.vigencia_recibo_hasta:
                raise ValidationError(
                    {'vigencia_recibo_hasta': "Debe especificar la fecha de fin de vigencia del recibo."})
            elif not self.vigencia_recibo_desde and self.vigencia_recibo_hasta:
                raise ValidationError(
                    {'vigencia_recibo_desde': "Debe especificar la fecha de inicio de vigencia del recibo."})

    @classmethod
    def con_relaciones(cls):
        try:
            PagoModel = apps.get_model('myapp', 'Pago')
            pago_qs = PagoModel.objects.all()
        except LookupError:
            pago_qs = None
        prefetch_args = []
        if pago_qs is not None:
            prefetch_args.append(Prefetch('pagos', queryset=pago_qs))
        return cls.objects.select_related('contrato_individual', 'contrato_colectivo', 'intermediario').prefetch_related(*prefetch_args)

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
    detalle_accion = models.TextField(
        verbose_name=("Detalle de la Acción"),
        blank=True,
        null=True,
        help_text="Descripción detallada de la acción realizada o del error ocurrido."
    )
    direccion_ip = models.GenericIPAddressField(
        verbose_name=("Dirección IP"),
        blank=True,
        null=True,
        db_index=True,
        help_text="Dirección IP desde la cual se originó la acción."
    )
    agente_usuario = models.TextField(
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
            'contrato_individual__afiliado',  # Optimizar carga anidada
            'contrato_colectivo__intermediario',  # Optimizar carga anidada
            'usuario_asignado'
        ).prefetch_related('pagos')


class Reclamacion(ModeloBase):
    objects = ReclamacionManager()
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
        blank=False,
        null=False,
        verbose_name=("Estado de la Reclamación"),
        db_index=True,

        help_text="Estado actual del proceso de la reclamación (ej. Abierta, Aprobada, Pagada)."
    )
    descripcion_reclamo = models.TextField(
        verbose_name=("Descripción del Reclamo"),
        blank=False,
        null=False,
        help_text="Descripción detallada del motivo de la reclamación realizada por el cliente."
    )
    monto_reclamado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto Reclamado",
        validators=[MinValueValidator(0.01)],  # Asegura que sea positivo
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
        Usuario,
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
            # OJO: difiere de otros forms (doc, docx)
            FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'png']),
            validate_file_size
        ],
        verbose_name="Documentos Adjuntos",
        blank=True,
        # <-- MODIFICADO
        help_text="Archivos PDF, JPG, PNG que soportan la reclamación. Tamaño máx: 10MB.",
        null=True
    )
    observaciones_internas = models.TextField(
        verbose_name=("Observaciones Internas"),
        blank=True,
        null=True,

        help_text="Notas o comentarios internos del personal sobre la reclamación (no visibles al cliente)."
    )
    observaciones_cliente = models.TextField(
        verbose_name=("Observaciones para el Cliente"),
        blank=True,
        null=True,
        help_text="Comentarios o respuestas proporcionadas al cliente sobre el estado o resolución de la reclamación."
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def get_estado_display_valor(self, valor_estado=None):
        """Devuelve el display de un valor de estado específico."""
        estado_a_buscar = valor_estado if valor_estado is not None else self.estado
        # Asegurarse que CommonChoices.ESTADO_RECLAMACION sea un diccionario o se convierta
        estado_map = dict(CommonChoices.ESTADO_RECLAMACION)
        # Devuelve el display o la clave si no se encuentra
        return estado_map.get(estado_a_buscar, estado_a_buscar)

    def get_contrato_asociado_display(self):
        """Devuelve una cadena identificando el contrato asociado."""
        if self.contrato_individual:
            # Usar __str__ del contrato si existe, o el número/pk
            return f"CI: {self.contrato_individual.numero_contrato or f'ID {self.contrato_individual.pk}'}"
        elif self.contrato_colectivo:
            return f"CC: {self.contrato_colectivo.numero_contrato or f'ID {self.contrato_colectivo.pk}'}"
        return "Sin Contrato"

    # --- MÉTODO CLEAN CORREGIDO ---
    def clean(self):
        super().clean()
        error_dict = {}
        contrato = self.contrato_individual or self.contrato_colectivo

        if not contrato:
            # Usar add_error es más directo que error_dict para errores simples
            raise ValidationError(
                {"contrato_individual": "Debe seleccionar un contrato individual o colectivo."})
        elif self.contrato_individual and self.contrato_colectivo:
            raise ValidationError(
                {"contrato_individual": "No puede seleccionar ambos tipos de contrato."})

        # Si hay contrato, validar montos y fechas
        if contrato and self.monto_reclamado is not None:
            # Validar vs Suma Asegurada
            if hasattr(contrato, 'suma_asegurada') and contrato.suma_asegurada is not None:
                try:
                    monto_reclamado_dec = Decimal(
                        self.monto_reclamado)  # Conversión segura
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
                    f"Contrato {contrato.pk} sin suma asegurada para validar Reclamación {self.pk}.")

        # Validar fechas (como estaba)
        if self.fecha_reclamo:
            if contrato and hasattr(contrato, 'fecha_inicio_vigencia') and contrato.fecha_inicio_vigencia and self.fecha_reclamo < contrato.fecha_inicio_vigencia:
                error_dict.setdefault('fecha_reclamo', []).append(
                    'Fecha reclamación anterior a inicio vigencia.')
        else:  # fecha_reclamo es obligatoria
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
    # --- FIN MÉTODO CLEAN ---

    def save(self, *args, **kwargs):
        is_updating = not self._state.adding
        original_estado = None
        if is_updating:
            try:
                original = Reclamacion.objects.get(pk=self.pk)
                original_estado = original.estado
                if original_estado != self.estado:
                    validate_estado_reclamacion(original_estado, self.estado)
            except Reclamacion.DoesNotExist:
                pass
            except ValidationError as e:
                raise ValidationError(
                    f"Transición de estado inválida: {e.message}")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = ("Reclamación")
        verbose_name_plural = ("Reclamaciones")
        indexes = [
            models.Index(fields=['tipo_reclamacion', 'estado']),
            models.Index(fields=['fecha_reclamo', 'fecha_cierre_reclamo']),
            models.Index(fields=['contrato_individual']),
            models.Index(fields=['contrato_colectivo']),
            models.Index(fields=['usuario_asignado']),
            models.Index(fields=['monto_reclamado']),
            models.Index(fields=['activo']),
        ]  # Faltaba heredar de ModeloBase.Meta.indexes si ModeloBase los tiene
        ordering = ['-fecha_reclamo']

    def __str__(self):
        identificador = "N/A"  # Inicializar
        if self.contrato_individual:
            # Usar el número de contrato si existe, si no el PK
            numero_ci = self.contrato_individual.numero_contrato or f"ID {self.contrato_individual.pk}"
            identificador = f"CI:{numero_ci}"
        elif self.contrato_colectivo:
            # Usar el número de contrato si existe, si no el PK
            numero_cc = self.contrato_colectivo.numero_contrato or f"ID {self.contrato_colectivo.pk}"
            identificador = f"CC:{numero_cc}"
        # Devuelve usando la variable identificador calculada
        return f"Reclamo #{self.pk} ({identificador}) - {self.get_estado_display()}"


# ------------------------------
# Pago (Modelo Completo Corregido)
# ------------------------------


class Pago(ModeloBase):  # Heredar de ModeloBase si aplica
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
    referencia_pago = models.CharField(
        max_length=100, verbose_name="Referencia de Pago", blank=True,
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
            if timezone.is_naive(self.fecha_calculo):
                logger_model_save.warning(
                    f"RegistroComision (PK: {self.pk or 'Nuevo'}): "
                    f"fecha_calculo ({self.fecha_calculo}) era naive. Haciéndola aware."
                )
                self.fecha_calculo = timezone.make_aware(
                    self.fecha_calculo, timezone.get_current_timezone())
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
    comision_intermediario = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Comisión Intermediario (%)",
        # Ajustado MaxValue
        blank=True, null=True, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Porcentaje de comisión para el intermediario asociado a contratos que usen esta tarifa (0.00-100.00)."
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
