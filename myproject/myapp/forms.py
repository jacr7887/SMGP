# myapp/forms.py
from django_select2.forms import Select2Widget
from .form_mixin import AwareDateInputMixinVE  # Asumiendo que este mixin existe
from .models import Pago, Factura, Reclamacion
from decimal import Decimal, InvalidOperation
from django import forms
from django.http import JsonResponse
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, EmailValidator, MinValueValidator, MaxValueValidator
from django.db.models import Sum
from django_select2.forms import Select2Widget, Select2MultipleWidget
# Necesario para cálculos de fechas
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta, datetime  # Python's datetime
import logging
import hashlib
from django.apps import apps
# TUS IMPORTS LOCALES
from .licensing import MIN_KEY_LENGTH
from .models import (
    ContratoColectivo, AfiliadoColectivo, AfiliadoIndividual, Intermediario, Tarifa, Usuario,
    ContratoIndividual, Reclamacion, Pago, Factura, AuditoriaSistema,
    get_modelo_choices, RegistroComision
)
from .validators import (
    validate_rif, validate_cedula, validate_file_size, validate_codigo_postal_ve,
    validate_direccion_ve, validate_tipo_empresa, validate_telefono_internacional,
    validate_telefono_venezuela, validate_file_type, validate_email_domain,
    validate_positive_decimal, validate_percentage, validate_fecha_nacimiento,
    validate_numero_contrato, validate_metodo_pago
)
from .commons import CommonChoices
# from .utils import get_tarifa_aplicable # Comentado si no se usa en este archivo
# from django.conf import settings # No parece usarse directamente aquí settings.DATE_INPUT_FORMATS

# IMPORTA TU MIXIN (ajusta la ruta si es necesario)
# Asumiendo que está en myapp/form_mixin.py
from .form_mixin import AwareDateInputMixinVE
# Necesario para comparaciones en clean()
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)

# ------------------------------
# Formulario Base (Estilos CSS personalizados)
# ------------------------------
# STRICT_DATE_INPUT_FORMAT y PLACEHOLDER_DATE_STRICT son para DateField, nosotros usaremos CharField
PLACEHOLDER_DATE_STRICT = 'DD/MM/AAAA'  # Lo mantenemos para los placeholders


# Asegúrate que esta clase esté definida o importada
class BaseModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (Select2Widget, forms.SelectMultiple, forms.CheckboxInput, forms.RadioSelect, forms.FileInput)):
                continue
            is_date_charfield_handled_by_mixin = hasattr(self, 'aware_date_fields_config') and \
                any(d['name'] == field_name for d in self.aware_date_fields_config) and \
                isinstance(field, forms.CharField)
            if isinstance(widget, (forms.TextInput, forms.NumberInput, forms.EmailInput,
                                   forms.PasswordInput, forms.URLInput, forms.Textarea)) \
                    and 'placeholder' not in widget.attrs and not is_date_charfield_handled_by_mixin:
                placeholder_text = str(field.label) if field.label else field_name.replace(
                    '_', ' ').capitalize()
                widget.attrs.setdefault('placeholder', placeholder_text)


# ------------------------------
# Formulario Base Modelo
# ------------------------------
class ModeloBaseForm(forms.ModelForm):
    class Meta:
        abstract = True
        fields = [
            'primer_nombre', 'segundo_nombre',
            'primer_apellido', 'segundo_apellido',
            # 'fecha_creacion', 'fecha_modificacion' # Generalmente auto_now o auto_now_add
        ]
        widgets = {}
        exclude = ['fecha_creacion', 'fecha_modificacion']


# ------------------------------
# Formularios Específicos
# ------------------------------

class AfiliadoColectivoForm(BaseModelForm):
    # Este formulario no parece tener campos de fecha que necesiten el mixin
    intermediario = forms.ModelChoiceField(
        queryset=Intermediario.objects.filter(
            activo=True).order_by('nombre_completo'),
        required=False,
        widget=Select2Widget(
            attrs={'data-placeholder': 'Buscar Intermediario...'}),
        label="Intermediario Asignado"
    )

    class Meta:
        model = AfiliadoColectivo
        fields = [
            'activo', 'rif', 'email_contacto', 'razon_social', 'tipo_empresa',
            'direccion_comercial', 'estado', 'municipio', 'ciudad', 'zona_postal',
            'telefono_contacto',
            'intermediario',
        ]
        widgets = {
            'tipo_empresa': forms.Select(attrs={'class': 'select2-enable'}),
            'direccion_comercial': forms.Textarea(attrs={'rows': 3}),
            'estado': forms.Select(attrs={'class': 'select2-enable'}),
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
            'rif': forms.TextInput(attrs={'placeholder': 'Formato: J-12345678-9'}),
            'email_contacto': forms.EmailInput(attrs={'placeholder': 'ejemplo@dominio.com'}),
            'razon_social': forms.TextInput(attrs={'placeholder': 'Ingrese la razón social'}),
            'municipio': forms.TextInput(attrs={'placeholder': 'Ingrese el municipio'}),
            'ciudad': forms.TextInput(attrs={'placeholder': 'Ingrese la ciudad'}),
            'zona_postal': forms.TextInput(attrs={'placeholder': 'Ingrese la zona postal'}),
            'telefono_contacto': forms.TextInput(attrs={'placeholder': 'Ingrese el teléfono'}),
        }
        help_texts = {
            'intermediario': 'Seleccione el intermediario que registró/gestionó esta empresa.',
        }
        exclude = ['fecha_creacion', 'fecha_modificacion',
                   'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido'
                   ]

# En AfiliadoColectivoForm

    def clean_rif(self):
        rif = self.cleaned_data.get('rif')
        if rif:
            try:
                validate_rif(rif)  # Primero, valida el formato
            except ValidationError as e:
                raise forms.ValidationError("Formato de RIF inválido.") from e

            # Ahora, valida la unicidad usando el hash
            rif_hash = hashlib.sha256(rif.encode('utf-8')).hexdigest()

            # Construimos la consulta base
            qs = AfiliadoColectivo.objects.filter(rif_hash=rif_hash)

            # Si estamos editando, excluimos el objeto actual de la búsqueda
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    "Este RIF ya está registrado para otro afiliado colectivo.")

        return rif

    def clean_zona_postal(self):
        codigo = self.cleaned_data.get('zona_postal')
        if codigo:
            validate_codigo_postal_ve(codigo)
        return codigo

    def clean_direccion_comercial(self):
        direccion = self.cleaned_data.get('direccion_comercial')
        if direccion:
            validate_direccion_ve(direccion)
        return direccion

    def clean_tipo_empresa(self):
        tipo = self.cleaned_data.get('tipo_empresa')
        validate_tipo_empresa(tipo)
        return tipo

    def clean_telefono_contacto(self):
        telefono = self.cleaned_data.get('telefono_contacto')
        if telefono:
            validate_telefono_venezuela(telefono)
        return telefono

# ===================================================================
# ===          FORMULARIO DE CREACIÓN DE USUARIO (CORREGIDO)       ===
# ===================================================================


# myapp/forms.py

class FormularioCreacionUsuario(AwareDateInputMixinVE, UserCreationForm, BaseModelForm):
    aware_date_fields = ['fecha_nacimiento']

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = (
            'email', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'tipo_usuario',  # <--- ¡SE QUEDA! Es la nueva fuente de verdad.
            'fecha_nacimiento', 'departamento', 'telefono', 'direccion',
            'intermediario',
            'activo'
        )

        widgets = {
            'tipo_usuario': forms.Select(attrs={'class': 'select2-enable'}),
            'departamento': forms.Select(attrs={'class': 'select2-enable'}),
            'intermediario': Select2Widget(attrs={'data-placeholder': 'Seleccione un intermediario...', 'class': 'select2-enable'}),
            'fecha_nacimiento': forms.DateInput(
                format='%d/%m/%Y',
                attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY',
                       'class': 'form-control date-input'}
            ),
            'direccion': forms.Textarea(attrs={'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        # La lógica de is_staff/is_superuser ahora está en el modelo, así que no se necesita aquí.
        if commit:
            user.save()
            # El método save del modelo se encargará de asignar los grupos.
        return user

# ===================================================================
# ===          FORMULARIO DE EDICIÓN DE USUARIO                   ===
# ===================================================================


class FormularioEdicionUsuario(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = ['fecha_nacimiento']

    class Meta:
        model = Usuario
        # --- LISTA DE CAMPOS CORREGIDA ---
        fields = [
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'fecha_nacimiento', 'telefono', 'direccion',
            'tipo_usuario', 'departamento', 'intermediario', 'activo',
            'is_staff', 'is_superuser', 'groups', 'user_permissions',
        ]

        # --- WIDGETS CORREGIDOS ---
        widgets = {
            'tipo_usuario': forms.Select(attrs={'class': 'select2-enable'}),
            'departamento': forms.Select(attrs={'class': 'select2-enable'}),
            'intermediario': Select2Widget(attrs={'data-placeholder': 'Seleccione un intermediario...', 'class': 'select2-enable'}),
            'groups': Select2MultipleWidget(attrs={'data-placeholder': 'Seleccionar grupos...', 'class': 'select2-enable'}),
            'user_permissions': Select2MultipleWidget(attrs={'data-placeholder': 'Seleccionar permisos...', 'class': 'select2-enable'}),
            'fecha_nacimiento': forms.DateInput(
                format='%d/%m/%Y',
                attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY',
                       'class': 'form-control date-input'}
            ),
            'direccion': forms.Textarea(attrs={'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'switch'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        user_being_edited = self.instance

        # Añadir campos de solo lectura para email y username
        if user_being_edited and user_being_edited.pk:
            self.fields['email_display'] = forms.CharField(label="Correo Electrónico", initial=user_being_edited.email, disabled=True, required=False, widget=forms.TextInput(
                attrs={'readonly': True, 'class': 'form-control-plaintext'}))
            self.fields['username_display'] = forms.CharField(label="Nombre de usuario (interno)", initial=user_being_edited.username,
                                                              disabled=True, required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'form-control-plaintext'}))
            # Reordenar para que aparezcan primero
            field_order = ['email_display', 'username_display'] + \
                [f for f in self.fields if f not in [
                    'email_display', 'username_display']]
            self.fields = {k: self.fields[k]
                           for k in field_order if k in self.fields}

        # --- LÓGICA DE PERMISOS SIMPLIFICADA Y CORREGIDA ---
        if self.request_user and user_being_edited and user_being_edited.pk:
            # Un usuario no puede editar a un superusuario si él mismo no lo es.
            if user_being_edited.is_superuser and not self.request_user.is_superuser:
                for field_name in self.fields:
                    self.fields[field_name].disabled = True
                return

            # Un no-superusuario no puede hacer a otros (o a sí mismo) superusuario.
            if 'is_superuser' in self.fields and not self.request_user.is_superuser:
                self.fields['is_superuser'].disabled = True

            # Un no-superusuario no puede cambiar el rol de un ADMIN.
            if 'tipo_usuario' in self.fields and not self.request_user.is_superuser and user_being_edited.tipo_usuario == 'ADMIN':
                self.fields['tipo_usuario'].disabled = True

            # Un no-superusuario no puede asignar el rol de ADMIN.
            if 'tipo_usuario' in self.fields and not self.request_user.is_superuser:
                # Excluimos la opción 'ADMIN' de las choices
                self.fields['tipo_usuario'].choices = [
                    (key, value) for key, value in CommonChoices.TIPO_USUARIO if key != 'ADMIN'
                ]

    # El método clean_fecha_nacimiento se mantiene igual
    def clean_fecha_nacimiento(self):
        fecha_nacimiento_obj = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nacimiento_obj:
            validate_fecha_nacimiento(fecha_nacimiento_obj)
        return fecha_nacimiento_obj


class LoginForm(forms.Form):
    username = forms.EmailField(label="Correo Electrónico", required=True, widget=forms.EmailInput(
        attrs={'placeholder': 'Correo Electrónico', 'class': 'login__input', 'autofocus': True}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(
        attrs={'placeholder': 'Contraseña', 'class': 'login__input'}), required=True, strip=False)
    request = None
    user_cache = None

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        self.user_cache = None
        if email and password:
            # print(f"DEBUG LoginForm.clean: Intentando autenticar a {email} con request: {self.request}")
            self.user_cache = authenticate(
                request=self.request, username=email, password=password)
            if self.user_cache is None:
                # print(f"DEBUG LoginForm.clean: authenticate devolvió None para {email}")
                raise ValidationError(
                    "Correo electrónico o contraseña incorrectos.", code='invalid_login')
            # print(f"DEBUG LoginForm.clean: Usuario autenticado: {self.user_cache.email}, Django 'is_active': {self.user_cache.is_active}, TU campo 'activo': {getattr(self.user_cache, 'activo', 'N/A')}")
            if not self.user_cache.is_active:
                # print(f"DEBUG LoginForm.clean: Usuario {self.user_cache.email} NO ACTIVO (is_active es False), lanzando error 'inactive'")
                raise ValidationError(
                    "Esta cuenta de usuario está inactiva.", code='inactive')
            # else:
                # print(f"DEBUG LoginForm.clean: Usuario {self.user_cache.email} SÍ ACTIVO (is_active es True).")
        # else:
            # print(f"DEBUG LoginForm.clean: Email o Password faltantes en cleaned_data. Email: '{email}', Password presente: {bool(password)}")
        return self.cleaned_data

    def get_user(self):
        return self.user_cache


# ------------------------------
# Formulario para Importación de Datos
# ------------------------------
MODELO_CHOICES = [
    ('', '---------'), ('usuario', 'Usuarios'), ('intermediario', 'Intermediarios'),
    ('afiliadoindividual', 'Afiliados Individuales'), ('afiliadocolectivo',
                                                       'Afiliados Colectivos (Empresas)'),
    ('contratoindividual', 'Contratos Individuales'), ('contratocolectivo',
                                                       'Contratos Colectivos'),
    ('tarifa', 'Tarifas'), ('reclamacion',
                            'Reclamaciones'), ('factura', 'Facturas'), ('pago', 'Pagos'),
]
MAX_LICENSE_DURATION_DAYS = 30


class LicenseActivationForm(forms.Form):
    license_key = forms.CharField(label="Clave de Licencia", required=True, min_length=MIN_KEY_LENGTH, widget=forms.TextInput(
        attrs={'placeholder': 'Ingrese su clave de licencia completa', 'class': 'search-input'}))

# ------------------------------
# Intermediario
# ------------------------------


class IntermediarioForm(BaseModelForm):
    # Definimos los campos que usan widgets de Select2 aquí
    intermediario_relacionado = forms.ModelChoiceField(
        queryset=Intermediario.objects.filter(
            activo=True).order_by('nombre_completo'),
        required=False,
        widget=Select2Widget(attrs={
            'data-placeholder': 'Buscar Intermediario Padre...',
            'class': 'select2-enable'  # <-- CLASE AÑADIDA
        }),
        label="Intermediario Padre (si aplica)"
    )

    usuarios = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(activo=True).order_by(
            'primer_apellido', 'primer_nombre', 'email'),
        required=False,
        widget=Select2MultipleWidget(attrs={
            'data-placeholder': 'Seleccionar Usuarios Gestores...',
            'class': 'select2-enable'  # <-- CLASE AÑADIDA
        }),
        label="Usuarios Gestores Asignados"
    )

    class Meta:
        model = Intermediario
        fields = [
            'activo', 'nombre_completo', 'rif', 'direccion_fiscal',
            'telefono_contacto', 'email_contacto', 'porcentaje_comision',
            'porcentaje_override', 'intermediario_relacionado', 'usuarios'
        ]
        # No necesitamos la sección 'exclude' si ya definimos 'fields'

        # Definimos los widgets para los campos que no son Select2
        widgets = {
            'direccion_fiscal': forms.Textarea(attrs={'rows': 3}),
            'porcentaje_comision': forms.NumberInput(attrs={'step': '0.01'}),
            'porcentaje_override': forms.NumberInput(attrs={'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tu lógica __init__ se mantiene igual
        if self.instance and self.instance.pk:
            if 'intermediario_relacionado' in self.fields:
                self.fields['intermediario_relacionado'].queryset = Intermediario.objects.exclude(
                    pk=self.instance.pk).order_by('nombre_completo')
        elif 'intermediario_relacionado' in self.fields:
            self.fields['intermediario_relacionado'].queryset = Intermediario.objects.all(
            ).order_by('nombre_completo')

        if 'usuarios' in self.fields:
            self.fields['usuarios'].queryset = Usuario.objects.filter(
                is_active=True).order_by('email')

    def clean_porcentaje_comision(self):
        porcentaje = self.cleaned_data['porcentaje_comision']
        if porcentaje is not None and (porcentaje < Decimal(0) or porcentaje > Decimal(100)):
            raise ValidationError(
                "El porcentaje debe estar entre 0.00 y 100.00")
        return porcentaje

    def clean_email_contacto(self):
        email = self.cleaned_data.get('email_contacto')
        if email:
            try:
                EmailValidator()(email)
            except ValidationError as e:
                raise ValidationError("Email inválido") from e
        return email

    def clean_rif(self):
        rif = self.cleaned_data.get('rif')
        if rif:
            try:
                validate_rif(rif)  # Primero, valida el formato
            except ValidationError as e:
                raise forms.ValidationError("Formato de RIF inválido.") from e

            # Ahora, valida la unicidad usando el hash
            rif_hash = hashlib.sha256(rif.encode('utf-8')).hexdigest()

            # Construimos la consulta base
            qs = Intermediario.objects.filter(rif_hash=rif_hash)

            # Si estamos editando, excluimos el objeto actual de la búsqueda
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    "Este RIF ya está registrado para otro afiliado colectivo.")

        return rif

    def clean_direccion_fiscal(self):
        direccion = self.cleaned_data.get('direccion_fiscal')
        if direccion:
            validate_direccion_ve(direccion)
        return direccion

    def clean_telefono_contacto(self):
        telefono = self.cleaned_data.get('telefono_contacto')
        if telefono:
            validate_telefono_venezuela(telefono)
        return telefono

# ------------------------------
# AfiliadoIndividualForm
# ------------------------------


# Asegúrate que herede del mixin
class AfiliadoIndividualForm(AwareDateInputMixinVE, BaseModelForm):
    # CONFIGURACIÓN PARA EL MIXIN
    aware_date_fields_config = [
        {'name': 'fecha_nacimiento', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_ingreso', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
    ]

    # Definición de campos (como los tenías, asegurando que los de fecha sean CharField)
    intermediario = forms.ModelChoiceField(
        queryset=Intermediario.objects.filter(
            activo=True).order_by('nombre_completo'),
        required=False,
        widget=Select2Widget(
            attrs={'data-placeholder': 'Buscar Intermediario...'}),
        label="Intermediario Asignado"
    )

    # Campos de fecha como CharField
    fecha_nacimiento = forms.CharField(
        label="Fecha de Nacimiento",
        required=True,  # Asumo que es requerido
        widget=forms.TextInput(
            attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'})
    )
    fecha_ingreso = forms.CharField(
        label="Fecha Ingreso",
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'})
    )

    # Re-declarar otros campos para asegurar consistencia de widgets y labels si es necesario
    primer_nombre = forms.CharField(label="Primer Nombre", max_length=100, widget=forms.TextInput(
        attrs={'placeholder': 'Primer Nombre', 'class': 'form-control'}))
    segundo_nombre = forms.CharField(label="Segundo Nombre", max_length=100,
                                     required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    primer_apellido = forms.CharField(label="Primer Apellido", max_length=100, widget=forms.TextInput(
        attrs={'placeholder': 'Primer Apellido', 'class': 'form-control'}))
    segundo_apellido = forms.CharField(label="Segundo Apellido", max_length=100,
                                       required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    tipo_identificacion = forms.ChoiceField(
        label="Tipo de Identificación", choices=CommonChoices.TIPO_IDENTIFICACION, widget=forms.Select(attrs={'class': 'select2-enable'}))
    cedula = forms.CharField(label="Cédula", max_length=20, widget=forms.TextInput(
        attrs={'placeholder': 'Ej: V-12345678', 'class': 'form-control'}))
    estado_civil = forms.ChoiceField(
        label="Estado Civil", choices=CommonChoices.ESTADO_CIVIL, widget=forms.Select(attrs={'class': 'select2-enable'}))
    sexo = forms.ChoiceField(label="Sexo", choices=CommonChoices.SEXO,
                             widget=forms.Select(attrs={'class': 'select2-enable'}))
    parentesco = forms.ChoiceField(label="Parentesco", choices=CommonChoices.PARENTESCO,
                                   widget=forms.Select(attrs={'class': 'select2-enable'}))
    nacionalidad = forms.CharField(label="Nacionalidad", max_length=50,
                                   initial='Venezolana', widget=forms.TextInput(attrs={'class': 'form-control'}))
    zona_postal = forms.CharField(label="Zona Postal", max_length=10, required=False, widget=forms.TextInput(
        attrs={'placeholder': 'Ej: 1010', 'class': 'form-control'}))
    estado = forms.ChoiceField(label="Estado", choices=CommonChoices.ESTADOS_VE,
                               widget=forms.Select(attrs={'class': 'select2-enable'}))
    municipio = forms.CharField(label="Municipio", max_length=100, widget=forms.TextInput(
        attrs={'class': 'form-control'}))  # Asumo requerido
    ciudad = forms.CharField(label="Ciudad", max_length=100, widget=forms.TextInput(
        attrs={'class': 'form-control'}))  # Asumo requerido
    direccion_habitacion = forms.CharField(label="Dirección Habitación", widget=forms.Textarea(
        attrs={'rows': 3, 'class': 'form-control'}))
    telefono_habitacion = forms.CharField(label="Teléfono Habitación", max_length=20,
                                          required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="Correo Electrónico", required=False, widget=forms.EmailInput(
        attrs={'placeholder': 'correo@ejemplo.com', 'class': 'form-control'}))
    direccion_oficina = forms.CharField(label="Dirección Oficina", widget=forms.Textarea(
        attrs={'rows': 3, 'class': 'form-control'}), required=False)
    telefono_oficina = forms.CharField(label="Teléfono Oficina", max_length=20,
                                       required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    activo = forms.BooleanField(label="Afiliado Activo", required=False, initial=True,
                                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = AfiliadoIndividual
        fields = [
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'tipo_identificacion', 'cedula', 'estado_civil', 'sexo', 'parentesco',
            'fecha_nacimiento', 'nacionalidad', 'zona_postal', 'estado', 'municipio',
            'ciudad', 'fecha_ingreso', 'direccion_habitacion', 'telefono_habitacion',
            'email', 'direccion_oficina', 'telefono_oficina',
            'intermediario', 'activo',
        ]
        exclude = ['fecha_creacion', 'fecha_modificacion', 'codigo_validacion']
        # Widgets para campos no definidos explícitamente arriba o para anular BaseModelForm.
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'intermediario': 'Seleccione el intermediario que registró/gestionó a este afiliado.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:  # Modo Edición
            if hasattr(self, 'aware_date_fields_config'):
                for config in self.aware_date_fields_config:
                    field_name = config['name']
                    display_format = config['format']

                    if field_name in self.fields and hasattr(self.instance, field_name):
                        model_value = getattr(self.instance, field_name, None)
                        if model_value:
                            if isinstance(model_value, date):  # Modelo tiene DateField
                                self.initial[field_name] = model_value.strftime(
                                    display_format)
                        elif self.fields[field_name].required is False:
                            self.initial[field_name] = ''
        # else: # Modo Creación
            # Puedes setear defaults aquí si es necesario

    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula')
        if cedula:
            try:
                validate_cedula(cedula)  # Valida el formato primero
            except ValidationError as e:
                raise forms.ValidationError(
                    "Formato de Cédula inválido.") from e

            # Valida la unicidad usando el hash
            cedula_hash = hashlib.sha256(cedula.encode('utf-8')).hexdigest()

            qs = AfiliadoIndividual.objects.filter(cedula_hash=cedula_hash)

            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    "Esta cédula ya está registrada para otro afiliado.")

        return cedula

    def clean_telefono_habitacion(self):
        telefono = self.cleaned_data.get('telefono_habitacion')
        if telefono:
            validate_telefono_venezuela(telefono)
        return telefono

    def clean_telefono_oficina(self):
        telefono = self.cleaned_data.get('telefono_oficina')
        if telefono:
            validate_telefono_venezuela(telefono)
        return telefono

    def clean_zona_postal(self):
        codigo = self.cleaned_data.get('zona_postal')
        if codigo:
            validate_codigo_postal_ve(codigo)
        return codigo

    def clean_direccion_habitacion(self):
        direccion = self.cleaned_data.get('direccion_habitacion')
        if direccion:
            validate_direccion_ve(direccion)
        return direccion

    def clean_direccion_oficina(self):
        direccion = self.cleaned_data.get('direccion_oficina')
        if direccion:
            validate_direccion_ve(direccion)
        return direccion

    def clean(self):  # Tu validación existente
        cleaned_data = super().clean()

        # Gracias al mixin, estos ya deberían ser objetos 'date' o None
        fecha_nacimiento_obj = cleaned_data.get('fecha_nacimiento')
        fecha_ingreso_obj = cleaned_data.get('fecha_ingreso')

        hoy_date = django_timezone.now().date()  # Para comparar con objetos date

        if fecha_nacimiento_obj:
            # validate_fecha_nacimiento ya se llama desde el campo del modelo o el clean_<field> del mixin
            # Aquí solo validaciones cruzadas
            validate_fecha_nacimiento(fecha_nacimiento_obj)

        return cleaned_data

# ------------------------------
# ContratoIndividualForm
# ------------------------------


class ContratoIndividualForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields_config = [
        {'name': 'fecha_emision', 'is_datetime': True,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_inicio_vigencia', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_fin_vigencia', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_inicio_vigencia_recibo', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_fin_vigencia_recibo', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
    ]

    afiliado = forms.ModelChoiceField(queryset=AfiliadoIndividual.objects.filter(activo=True).order_by('primer_apellido', 'primer_nombre'), required=True, widget=Select2Widget(
        attrs={'data-placeholder': 'Buscar Afiliado Titular...', 'class': 'form-control'}), label="Afiliado Individual Titular")
    intermediario = forms.ModelChoiceField(queryset=Intermediario.objects.filter(activo=True).order_by('nombre_completo'), required=True, widget=Select2Widget(
        attrs={'data-placeholder': 'Buscar Intermediario...', 'class': 'form-control'}), label="Intermediario")
    tarifa_aplicada = forms.ModelChoiceField(queryset=Tarifa.objects.filter(activo=True).order_by('ramo', '-fecha_aplicacion'), required=True,
                                             widget=Select2Widget(attrs={'data-placeholder': 'Seleccionar Tarifa Aplicable...', 'class': 'form-control'}), label="Tarifa Aplicada")

    fecha_emision = forms.CharField(label="Fecha de Emisión", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_inicio_vigencia = forms.CharField(label="Fecha Inicio Vigencia", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_fin_vigencia = forms.CharField(label="Fecha Fin Vigencia", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=False)
    fecha_inicio_vigencia_recibo = forms.CharField(label="Inicio Vigencia Recibo", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=False)
    fecha_fin_vigencia_recibo = forms.CharField(label="Fin Vigencia Recibo", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=False)

    ramo = forms.ChoiceField(label="Ramo", choices=CommonChoices.RAMO,
                             widget=Select2Widget(attrs={'class': 'form-control'}))
    forma_pago = forms.ChoiceField(label="Forma de Pago", choices=CommonChoices.FORMA_PAGO, widget=Select2Widget(
        attrs={'class': 'form-control', 'id': 'id_forma_pago'}))
    estatus = forms.ChoiceField(label="Estatus Vigencia", choices=CommonChoices.ESTADOS_VIGENCIA,
                                widget=Select2Widget(attrs={'class': 'form-control'}))
    estado_contrato = forms.ChoiceField(label="Estado Admin. Contrato", choices=CommonChoices.ESTADO_CONTRATO,
                                        widget=Select2Widget(attrs={'class': 'form-control'}), required=False)
    periodo_vigencia_meses = forms.IntegerField(label="Duración Contrato (Meses)", min_value=1, widget=forms.NumberInput(
        attrs={'min': '1', 'class': 'form-control', 'id': 'id_periodo_vigencia_meses'}), required=False, help_text="Si se indica, la Fecha Fin se calcula.")

    cantidad_cuotas_display = forms.CharField(label="Cantidad de Cuotas Estimadas", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_cantidad_cuotas_display'}))
    monto_cuota_display = forms.CharField(label="Monto Estimado por Cuota/Recibo", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_monto_cuota_display'}))

    tipo_identificacion_contratante = forms.ChoiceField(choices=CommonChoices.TIPO_IDENTIFICACION, widget=Select2Widget(
        attrs={'class': 'form-control'}), label="Tipo Identificación Contratante")
    contratante_cedula = forms.CharField(
        label="Cédula/RIF del Contratante", max_length=15, widget=forms.TextInput(attrs={'class': 'form-control'}))
    contratante_nombre = forms.CharField(
        label="Nombre del Contratante", max_length=255, widget=forms.TextInput(attrs={'class': 'form-control'}))
    direccion_contratante = forms.CharField(label="Dirección del Contratante", widget=forms.Textarea(
        attrs={'rows': 3, 'class': 'form-control'}), required=False)
    telefono_contratante = forms.CharField(label="Teléfono del Contratante", max_length=20,
                                           required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email_contratante = forms.EmailField(
        label="Email del Contratante", required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    plan_contratado = forms.CharField(label="Plan Contratado", max_length=255,
                                      required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    suma_asegurada = forms.DecimalField(label="Suma Asegurada / Monto Cobertura", max_digits=17, decimal_places=2, min_value=Decimal(
        '0.01'), widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'class': 'form-control'}), required=True)
    estatus_emision_recibo = forms.ChoiceField(label="Estatus de Emisión del Recibo", choices=CommonChoices.EMISION_RECIBO, widget=Select2Widget(
        attrs={'class': 'form-control'}), required=False)
    criterio_busqueda = forms.CharField(label="Criterio de Búsqueda", max_length=255,
                                        required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    estatus_detalle = forms.CharField(label="Estatus Detallado", widget=forms.Textarea(
        attrs={'rows': 2, 'class': 'form-control'}), required=False)
    consultar_afiliados_activos = forms.BooleanField(
        label="Consultar en data de afiliados activos", required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    activo = forms.BooleanField(label="Contrato Activo", required=False, initial=True,
                                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = ContratoIndividual
        fields = [
            'activo', 'ramo', 'forma_pago', 'estatus', 'estado_contrato',
            'fecha_emision', 'fecha_inicio_vigencia', 'fecha_fin_vigencia',
            'periodo_vigencia_meses',
            'intermediario', 'tipo_identificacion_contratante',
            'contratante_cedula', 'contratante_nombre', 'direccion_contratante',
            'telefono_contratante', 'email_contratante', 'afiliado', 'plan_contratado',
            'suma_asegurada', 'tarifa_aplicada',
            'fecha_inicio_vigencia_recibo', 'fecha_fin_vigencia_recibo',
            'estatus_emision_recibo',
            'criterio_busqueda', 'estatus_detalle', 'consultar_afiliados_activos',
        ]
        exclude = [
            'numero_contrato', 'numero_poliza', 'certificado',
            'pagos_realizados', 'comision_recibo',
            'dias_transcurridos_ingreso',
            'fecha_creacion', 'fecha_modificacion',
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'historial_cambios', 'numero_recibo'
        ]
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consultar_afiliados_activos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'fecha_fin_vigencia': "Opcional. Si se provee la Duración, esta fecha se calculará.",
            'periodo_vigencia_meses': "Opcional. Si se provee la Fecha Fin, esta duración se calculará.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cantidad_cuotas_display'] = forms.CharField(label="Cantidad de Cuotas Estimadas", required=False, widget=forms.TextInput(
            attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_cantidad_cuotas_display'}))
        self.fields['monto_cuota_display'] = forms.CharField(label="Monto Estimado por Cuota/Recibo", required=False, widget=forms.TextInput(
            attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_monto_cuota_display'}))

        if self.instance and self.instance.pk:
            if hasattr(self, 'aware_date_fields_config'):
                for config in self.aware_date_fields_config:
                    field_name = config['name']
                    display_format = config['format']
                    if field_name in self.fields and hasattr(self.instance, field_name):
                        model_value = getattr(self.instance, field_name, None)
                        if model_value:
                            if isinstance(model_value, datetime):
                                date_to_format = django_timezone.localtime(
                                    model_value) if django_timezone.is_aware(model_value) else model_value
                                self.initial[field_name] = date_to_format.strftime(
                                    display_format)
                            elif isinstance(model_value, date):
                                self.initial[field_name] = model_value.strftime(
                                    display_format)
                        elif self.fields[field_name].required is False:
                            self.initial[field_name] = ''

            if 'fecha_emision' in self.fields and self.instance.fecha_emision:
                self.fields['fecha_emision'].widget.attrs['readonly'] = True
                self.fields['fecha_emision'].widget.attrs['class'] += ' form-control-plaintext dark-input-plaintext'
                self.fields['fecha_emision'].help_text = "La fecha de emisión original no se puede modificar."
        else:
            self.initial.setdefault('estatus', 'VIGENTE')
            self.initial.setdefault('activo', True)

    def clean(self):
        cleaned_data = super().clean()
        fecha_emision = cleaned_data.get("fecha_emision")
        fecha_inicio_vigencia = cleaned_data.get("fecha_inicio_vigencia")
        fecha_fin_vigencia_form = cleaned_data.get("fecha_fin_vigencia")
        periodo_meses_form = cleaned_data.get("periodo_vigencia_meses")
        fecha_inicio_recibo = cleaned_data.get("fecha_inicio_vigencia_recibo")
        fecha_fin_recibo = cleaned_data.get("fecha_fin_vigencia_recibo")

        fecha_emision_date_part = fecha_emision.date() if isinstance(
            fecha_emision, datetime) else fecha_emision

        if fecha_emision_date_part and fecha_inicio_vigencia and fecha_emision_date_part > fecha_inicio_vigencia:
            self.add_error(
                'fecha_emision', "La fecha de emisión no puede ser posterior a la fecha de inicio de vigencia.")

        if fecha_inicio_vigencia:
            if periodo_meses_form is not None and fecha_fin_vigencia_form is not None:
                if periodo_meses_form < 1:
                    self.add_error('periodo_vigencia_meses',
                                   "La duración debe ser de al menos 1 mes.")
                else:
                    try:
                        fin_calculado_desde_periodo = fecha_inicio_vigencia + \
                            relativedelta(
                                months=+periodo_meses_form) - timedelta(days=1)
                        if fin_calculado_desde_periodo != fecha_fin_vigencia_form:
                            self.add_error(None, forms.ValidationError(
                                f"Inconsistencia: La Fecha Fin ({fecha_fin_vigencia_form.strftime('%d/%m/%Y')}) vs Duración {periodo_meses_form} meses (resulta en {fin_calculado_desde_periodo.strftime('%d/%m/%Y')}). Ajuste una o deje una en blanco.", code='inconsistencia_fecha_duracion'))
                    except TypeError as te:
                        logger.error(
                            f"TypeError en validación de consistencia de fechas (CI clean): {te}", exc_info=True)
                        self.add_error(
                            None, f"Error de tipo al verificar fechas de vigencia: {str(te)}")
                    except Exception as e:
                        logger.error(
                            f"Excepción en validación de consistencia de fechas (CI clean): {e}", exc_info=True)
                        self.add_error(
                            None, f"Error verificando consistencia de fechas: {str(e)}")
            elif fecha_fin_vigencia_form is not None:
                if fecha_fin_vigencia_form < fecha_inicio_vigencia:
                    self.add_error('fecha_fin_vigencia',
                                   'Fin no puede ser antes de inicio.')
            elif periodo_meses_form is not None:
                if periodo_meses_form < 1:
                    self.add_error('periodo_vigencia_meses',
                                   "La duración debe ser de al menos 1 mes.")
            elif not (self.instance and self.instance.pk):
                if not self.fields['fecha_fin_vigencia'].required and not self.fields['periodo_vigencia_meses'].required:
                    self.add_error(
                        None, "Debe ingresar la Duración del Contrato (en meses) o la Fecha Fin de Vigencia.")

        tipo_id_contratante = cleaned_data.get(
            'tipo_identificacion_contratante')
        cedula_contratante = cleaned_data.get('contratante_cedula')
        if cedula_contratante and tipo_id_contratante:
            try:
                if tipo_id_contratante == 'CEDULA':
                    validate_cedula(cedula_contratante)
                elif tipo_id_contratante == 'RIF':
                    validate_rif(cedula_contratante)
            except ValidationError as e:
                self.add_error('contratante_cedula', e)
        elif not cedula_contratante and tipo_id_contratante:
            self.add_error(
                'contratante_cedula', 'Este campo es requerido si se especifica un tipo de identificación.')

        if fecha_inicio_recibo and fecha_inicio_vigencia and fecha_inicio_recibo < fecha_inicio_vigencia:
            self.add_error('fecha_inicio_vigencia_recibo',
                           "El inicio de vigencia del recibo no puede ser anterior al inicio de vigencia del contrato.")

        final_fecha_fin_contrato_efectiva = fecha_fin_vigencia_form
        if not final_fecha_fin_contrato_efectiva and fecha_inicio_vigencia and periodo_meses_form:
            try:
                final_fecha_fin_contrato_efectiva = fecha_inicio_vigencia + \
                    relativedelta(months=+periodo_meses_form) - \
                    timedelta(days=1)
            except:
                pass

        if fecha_fin_recibo and final_fecha_fin_contrato_efectiva and fecha_fin_recibo > final_fecha_fin_contrato_efectiva:
            self.add_error('fecha_fin_vigencia_recibo',
                           "El fin de vigencia del recibo no puede ser posterior al fin de vigencia del contrato.")

        if fecha_inicio_recibo and fecha_fin_recibo and fecha_fin_recibo < fecha_inicio_recibo:
            self.add_error('fecha_fin_vigencia_recibo',
                           "La fecha de fin de vigencia del recibo no puede ser anterior a su fecha de inicio.")

        return cleaned_data

# --- ContratoColectivoForm ---


class ContratoColectivoForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields_config = [
        {'name': 'fecha_emision', 'is_datetime': True,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_inicio_vigencia', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_fin_vigencia', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
    ]

    afiliados_colectivos = forms.ModelMultipleChoiceField(queryset=AfiliadoColectivo.objects.filter(activo=True).order_by('razon_social'), required=True, widget=Select2MultipleWidget(
        attrs={'data-placeholder': 'Buscar Empresas/Colectivos...', 'class': 'form-control'}), label='Empresa(s) o Colectivo(s) Asegurado(s)', help_text="Seleccione al menos una empresa. La Razón Social y RIF se tomarán del primer seleccionado.")
    intermediario = forms.ModelChoiceField(queryset=Intermediario.objects.filter(activo=True).order_by('nombre_completo'), required=True, widget=Select2Widget(
        attrs={'data-placeholder': 'Buscar Intermediario...', 'class': 'form-control'}), label="Intermediario")
    tarifa_aplicada = forms.ModelChoiceField(queryset=Tarifa.objects.filter(activo=True).order_by('ramo', '-fecha_aplicacion', 'rango_etario'), required=True,
                                             widget=Select2Widget(attrs={'data-placeholder': 'Seleccionar Tarifa Aplicable...', 'class': 'form-control'}), label="Tarifa Aplicada al Contrato")

    fecha_emision = forms.CharField(label="Fecha de Emisión", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_inicio_vigencia = forms.CharField(label="Fecha Inicio Vigencia", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_fin_vigencia = forms.CharField(label="Fecha Fin Vigencia", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=False)

    activo = forms.BooleanField(label="Contrato Activo", required=False, initial=True,
                                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    ramo = forms.ChoiceField(label="Ramo", choices=CommonChoices.RAMO,
                             widget=Select2Widget(attrs={'class': 'form-control'}))
    forma_pago = forms.ChoiceField(label="Forma de Pago", choices=CommonChoices.FORMA_PAGO, widget=Select2Widget(
        attrs={'class': 'form-control', 'id': 'id_forma_pago'}))
    estatus = forms.ChoiceField(label="Estatus Vigencia", choices=CommonChoices.ESTADOS_VIGENCIA,
                                widget=Select2Widget(attrs={'class': 'form-control'}))
    estado_contrato = forms.ChoiceField(label="Estado Admin. Contrato", choices=CommonChoices.ESTADO_CONTRATO,
                                        widget=Select2Widget(attrs={'class': 'form-control'}), required=False)
    periodo_vigencia_meses = forms.IntegerField(label="Duración Contrato (Meses)", min_value=1, widget=forms.NumberInput(
        attrs={'min': '1', 'class': 'form-control', 'id': 'id_periodo_vigencia_meses'}), required=False, help_text="Si se indica, la Fecha Fin se calcula.")

    cantidad_cuotas_display = forms.CharField(label="Cantidad de Cuotas Estimadas", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_cantidad_cuotas_display'}))
    monto_cuota_display = forms.CharField(label="Monto Estimado por Cuota/Recibo", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_monto_cuota_display'}))

    suma_asegurada = forms.DecimalField(label="Suma Asegurada", max_digits=17, decimal_places=2, min_value=Decimal(
        '0.01'), widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'class': 'form-control'}), required=True)
    tipo_empresa = forms.ChoiceField(label="Tipo de Empresa Contratante", choices=CommonChoices.TIPO_EMPRESA,
                                     widget=Select2Widget(attrs={'class': 'form-control'}), required=False)
    cantidad_empleados = forms.IntegerField(label="Cantidad de Empleados Cubiertos", min_value=1, widget=forms.NumberInput(
        attrs={'min': '1', 'class': 'form-control'}), required=True)
    direccion_comercial = forms.CharField(label="Dirección Comercial (Empresa)", widget=forms.Textarea(
        attrs={'rows': 3, 'class': 'form-control'}), required=False)
    zona_postal = forms.CharField(label="Zona Postal (Empresa)", max_length=10, widget=forms.TextInput(
        attrs={'placeholder': 'Ej: 1010', 'class': 'form-control'}), required=False)
    plan_contratado = forms.CharField(label="Plan Contratado", max_length=255, widget=forms.TextInput(
        attrs={'placeholder': 'Nombre o Código', 'class': 'form-control'}), required=False)
    criterio_busqueda = forms.CharField(label="Criterio de Búsqueda", max_length=255, widget=forms.TextInput(
        attrs={'placeholder': 'Etiquetas...', 'class': 'form-control'}), required=False)
    consultar_afiliados_activos = forms.BooleanField(
        label="Consultar en data de afiliados activos", required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = ContratoColectivo
        fields = [
            'activo', 'ramo', 'forma_pago', 'estatus', 'estado_contrato',
            'fecha_emision', 'fecha_inicio_vigencia', 'fecha_fin_vigencia',
            'periodo_vigencia_meses', 'suma_asegurada',
            'intermediario', 'tarifa_aplicada', 'tipo_empresa', 'cantidad_empleados',
            'direccion_comercial', 'zona_postal', 'plan_contratado',
            'criterio_busqueda', 'afiliados_colectivos', 'consultar_afiliados_activos',
        ]
        exclude = [
            'certificado', 'numero_contrato', 'numero_poliza', 'numero_recibo',
            'rif', 'razon_social', 'pagos_realizados', 'comision_recibo',
            'codigo_validacion', 'fecha_creacion', 'fecha_modificacion',
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'historial_cambios'
        ]
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consultar_afiliados_activos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'fecha_fin_vigencia': "Opcional. Si se provee la Duración, esta fecha se calculará.",
            'periodo_vigencia_meses': "Opcional. Si se provee la Fecha Fin, esta duración se calculará.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cantidad_cuotas_display'] = forms.CharField(label="Cantidad de Cuotas Estimadas", required=False, widget=forms.TextInput(
            attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_cantidad_cuotas_display'}))
        self.fields['monto_cuota_display'] = forms.CharField(label="Monto Estimado por Cuota/Recibo", required=False, widget=forms.TextInput(
            attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext', 'id': 'id_monto_cuota_display'}))

        if self.instance and self.instance.pk:
            if hasattr(self, 'aware_date_fields_config'):
                for config in self.aware_date_fields_config:
                    field_name = config['name']
                    display_format = config['format']
                    if field_name in self.fields and hasattr(self.instance, field_name):
                        model_value = getattr(self.instance, field_name, None)
                        if model_value:
                            if isinstance(model_value, datetime):
                                date_to_format = django_timezone.localtime(
                                    model_value) if django_timezone.is_aware(model_value) else model_value
                                self.initial[field_name] = date_to_format.strftime(
                                    display_format)
                            elif isinstance(model_value, date):
                                self.initial[field_name] = model_value.strftime(
                                    display_format)
                        elif self.fields[field_name].required is False:
                            self.initial[field_name] = ''

            if 'fecha_emision' in self.fields and self.instance.fecha_emision:
                self.fields['fecha_emision'].widget.attrs['readonly'] = True
                self.fields['fecha_emision'].widget.attrs['class'] += ' form-control-plaintext dark-input-plaintext'
                self.fields['fecha_emision'].help_text = "La fecha de emisión original no se puede modificar."
        else:
            self.initial.setdefault('estatus', 'VIGENTE')
            self.initial.setdefault('activo', True)

    def clean(self):
        cleaned_data = super().clean()
        fecha_emision = cleaned_data.get("fecha_emision")
        fecha_inicio_vigencia = cleaned_data.get("fecha_inicio_vigencia")
        fecha_fin_vigencia_form = cleaned_data.get("fecha_fin_vigencia")
        periodo_meses_form = cleaned_data.get("periodo_vigencia_meses")
        afiliados_seleccionados = cleaned_data.get('afiliados_colectivos')

        if self.fields['afiliados_colectivos'].required and (not afiliados_seleccionados or not afiliados_seleccionados.exists()):
            self.add_error('afiliados_colectivos',
                           "Debe seleccionar al menos una empresa o colectivo.")

        fecha_emision_date_part = fecha_emision.date() if isinstance(
            fecha_emision, datetime) else fecha_emision

        if fecha_emision_date_part and fecha_inicio_vigencia and fecha_emision_date_part > fecha_inicio_vigencia:
            self.add_error(
                'fecha_emision', "La emisión no puede ser después del inicio de vigencia.")

        if fecha_inicio_vigencia:
            if periodo_meses_form is not None and fecha_fin_vigencia_form is not None:
                if periodo_meses_form < 1:
                    self.add_error('periodo_vigencia_meses',
                                   "Duración debe ser al menos 1 mes.")
                else:
                    try:
                        fin_calc = fecha_inicio_vigencia + \
                            relativedelta(
                                months=+periodo_meses_form) - timedelta(days=1)
                        if fin_calc != fecha_fin_vigencia_form:
                            self.add_error(None, forms.ValidationError(
                                f"Inconsistencia Fecha Fin ({fecha_fin_vigencia_form.strftime('%d/%m/%Y')}) vs Duración {periodo_meses_form} meses (resulta en {fin_calc.strftime('%d/%m/%Y')}). Ajuste una o deje una en blanco.", code='inconsistencia_fecha_duracion'))
                    except TypeError as te:
                        logger.error(
                            f"TypeError en validación de consistencia de fechas (CC clean): {te}", exc_info=True)
                        self.add_error(
                            None, f"Error de tipo al verificar fechas de vigencia: {str(te)}")
                    except Exception as e:
                        logger.error(
                            f"Excepción en validación de consistencia de fechas (CC clean): {e}", exc_info=True)
                        self.add_error(
                            None, f"Error verificando consistencia de fechas: {str(e)}")
            elif fecha_fin_vigencia_form is not None:
                if fecha_fin_vigencia_form < fecha_inicio_vigencia:
                    self.add_error('fecha_fin_vigencia',
                                   'Fin no puede ser antes de inicio.')
            elif periodo_meses_form is not None:
                if periodo_meses_form < 1:
                    self.add_error('periodo_vigencia_meses',
                                   "La duración debe ser de al menos 1 mes.")
            elif not (self.instance and self.instance.pk):
                if not self.fields['fecha_fin_vigencia'].required and not self.fields['periodo_vigencia_meses'].required:
                    self.add_error(
                        None, "Debe ingresar la Duración del Contrato (en meses) o la Fecha Fin de Vigencia.")

        tarifa_seleccionada = cleaned_data.get('tarifa_aplicada')
        if self.fields['tarifa_aplicada'].required and not tarifa_seleccionada:
            self.add_error('tarifa_aplicada', 'Debe seleccionar una tarifa.')

        return cleaned_data

    def save(self, commit=True):
        afiliados_seleccionados = self.cleaned_data.get('afiliados_colectivos')
        if afiliados_seleccionados and afiliados_seleccionados.exists():
            afiliado_principal_colectivo = afiliados_seleccionados.first()
            if afiliado_principal_colectivo.rif:
                self.instance.rif = afiliado_principal_colectivo.rif
            if afiliado_principal_colectivo.razon_social:
                self.instance.razon_social = afiliado_principal_colectivo.razon_social

        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()  # Importante para guardar las relaciones ManyToMany
        return instance

# ------------------------------
# ReclamacionForm
# ------------------------------


class ReclamacionForm(AwareDateInputMixinVE, BaseModelForm):
    # Configuración para el mixin AwareDateInputMixinVE
    aware_date_fields_config = [
        {'name': 'fecha_reclamo', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'fecha_cierre_reclamo', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
    ]

    # Definición explícita de campos para control total
    contrato_individual = forms.ModelChoiceField(
        queryset=ContratoIndividual.objects.filter(activo=True).select_related(
            'afiliado').order_by('-fecha_emision', 'numero_contrato'),
        required=False,
        widget=Select2Widget(attrs={
                             'data-placeholder': 'Buscar Contrato Individual...', 'class': 'form-control'}),
        label="Contrato Individual Asociado"
    )
    contrato_colectivo = forms.ModelChoiceField(
        queryset=ContratoColectivo.objects.filter(
            activo=True).order_by('-fecha_emision', 'numero_contrato'),
        required=False,
        widget=Select2Widget(attrs={
                             'data-placeholder': 'Buscar Contrato Colectivo...', 'class': 'form-control'}),
        label="Contrato Colectivo Asociado"
    )
    usuario_asignado = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(
            is_active=True, is_staff=True).order_by('email'),
        required=False,
        widget=Select2Widget(
            attrs={'data-placeholder': 'Buscar Usuario Asignado...', 'class': 'form-control'}),
        label="Usuario Asignado"
    )
    diagnostico_principal = forms.ChoiceField(
        choices=CommonChoices.DIAGNOSTICOS,
        required=True,
        widget=Select2Widget(attrs={
                             'data-placeholder': 'Buscar Diagnóstico Principal...', 'class': 'form-control'}),
        label="Diagnóstico Principal (Médico/Técnico)"
    )
    documentos_adjuntos = forms.FileField(
        label="Documentos Adjuntos",
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'png']), validate_file_size],
        required=False,
        help_text="Formatos: PDF, JPG, PNG. Max 10MB.",
        # Widget estándar para FileField
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

    # Campos de fecha como CharField, manejados por el mixin
    fecha_reclamo = forms.CharField(
        label="Fecha de Reclamo",
        widget=forms.TextInput(
            attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}),
        required=True
    )
    fecha_cierre_reclamo = forms.CharField(
        label="Fecha Cierre Reclamo",
        widget=forms.TextInput(
            attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}),
        required=False
    )

    # Otros campos del formulario
    tipo_reclamacion = forms.ChoiceField(
        label="Tipo de Reclamación",
        choices=CommonChoices.TIPO_RECLAMACION,
        # Usar select2-enable para Bootstrap
        widget=forms.Select(attrs={'class': 'select2-enable'})
    )
    descripcion_reclamo = forms.CharField(
        label="Descripción del Reclamo",
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'})
    )
    estado = forms.ChoiceField(
        label="Estado de la Reclamación",
        choices=CommonChoices.ESTADO_RECLAMACION,
        widget=forms.Select(attrs={'class': 'select2-enable'})
    )
    monto_reclamado = forms.DecimalField(
        label="Monto Reclamado",
        max_digits=15,  # Coincidir con el modelo
        decimal_places=2,
        required=True,  # Asumo que es requerido, si no, cambiar a False
        widget=forms.NumberInput(
            attrs={'step': '0.01', 'class': 'form-control'}),
        validators=[MinValueValidator(Decimal('0.01'))]  # Del modelo
    )
    observaciones_internas = forms.CharField(
        label="Observaciones Internas",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )
    observaciones_cliente = forms.CharField(
        label="Observaciones para el Cliente",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )
    activo = forms.BooleanField(
        label="Reclamación Activa",
        required=False,
        initial=True,
        # Para estilo Bootstrap de switch
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Reclamacion
        fields = [  # Lista explícita de campos en el orden deseado
            'activo', 'contrato_individual', 'contrato_colectivo',
            'fecha_reclamo', 'tipo_reclamacion', 'descripcion_reclamo', 'estado',
            'monto_reclamado', 'fecha_cierre_reclamo', 'usuario_asignado',
            'diagnostico_principal', 'observaciones_internas', 'observaciones_cliente',
            'documentos_adjuntos',
        ]
        # Campos excluidos (los que son auto-generados o no deben ser editados aquí)
        exclude = [
            'numero_reclamacion',  # Se genera en el modelo
            'fecha_creacion', 'fecha_modificacion',
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido'  # De ModeloBase
        ]
        # Widgets para campos que no fueron definidos explícitamente arriba
        # o para anular los defaults de ModelForm si es necesario.
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Los widgets para Select2 y TextInput de fecha ya están en la definición de campos.
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Formatear fechas para la visualización en modo edición
        if self.instance and self.instance.pk:  # Modo Edición
            if hasattr(self, 'aware_date_fields_config'):
                for config in self.aware_date_fields_config:
                    field_name = config['name']
                    display_format = config['format']  # Formato DD/MM/YYYY

                    if field_name in self.fields and hasattr(self.instance, field_name):
                        model_value = getattr(self.instance, field_name, None)
                        if model_value:
                            # Como los campos del modelo son DateField, model_value será date
                            if isinstance(model_value, date):
                                self.initial[field_name] = model_value.strftime(
                                    display_format)
                        elif self.fields[field_name].required is False:
                            self.initial[field_name] = ''
        # else: # Modo Creación
            # Puedes setear defaults aquí si es necesario, ej:
            # self.initial.setdefault('estado', 'ABIERTA')

    def clean_tipo_reclamacion(self):
        tipo = self.cleaned_data.get('tipo_reclamacion')
        # Validar contra las claves de los choices
        if tipo not in [choice[0] for choice in CommonChoices.TIPO_RECLAMACION]:
            raise ValidationError(("Tipo de reclamación inválido."))
        return tipo

    def clean(self):
        cleaned_data = super().clean()
        contrato_individual = cleaned_data.get('contrato_individual')
        contrato_colectivo = cleaned_data.get('contrato_colectivo')
        fecha_reclamo_obj = cleaned_data.get('fecha_reclamo')
        fecha_cierre_obj = cleaned_data.get('fecha_cierre_reclamo')
        monto_reclamado_val = cleaned_data.get('monto_reclamado')

        # --- INICIO DE LA LÓGICA DE VALIDACIÓN CORRECTA ---

        # 1. Validar que se haya seleccionado un contrato, pero no ambos.
        if not contrato_individual and not contrato_colectivo:
            # Añade el error a un campo específico si es posible, o como non-field error.
            self.add_error(
                None, "La reclamación debe estar asociada a un Contrato Individual o Colectivo.")

        if contrato_individual and contrato_colectivo:
            self.add_error(
                None, "No puede seleccionar un Contrato Individual y uno Colectivo a la vez.")

        # 2. Validar fechas
        if fecha_reclamo_obj and fecha_cierre_obj and fecha_cierre_obj < fecha_reclamo_obj:
            self.add_error('fecha_cierre_reclamo',
                           "La fecha de cierre no puede ser anterior a la fecha del reclamo.")

        if fecha_reclamo_obj and fecha_reclamo_obj > django_timezone.now().date():
            self.add_error('fecha_reclamo',
                           "La fecha del reclamo no puede ser futura.")

        if cleaned_data.get('estado') == 'CERRADA' and not fecha_cierre_obj:
            self.add_error('fecha_cierre_reclamo',
                           "Debe indicar la fecha de cierre si el estado es 'CERRADA'.")

        # 3. Validar monto contra la suma asegurada del contrato seleccionado
        contrato_seleccionado = contrato_individual or contrato_colectivo
        if contrato_seleccionado and monto_reclamado_val is not None:
            if hasattr(contrato_seleccionado, 'suma_asegurada') and contrato_seleccionado.suma_asegurada is not None:
                if monto_reclamado_val > contrato_seleccionado.suma_asegurada:
                    self.add_error('monto_reclamado',
                                   f"El monto reclamado (${monto_reclamado_val:,.2f}) excede la suma asegurada del contrato (${contrato_seleccionado.suma_asegurada:,.2f})."
                                   )


# ------------------------------
# PagoForm
# ------------------------------

class PagoForm(AwareDateInputMixinVE, forms.ModelForm):
    aware_date_fields_config = [
        {'name': 'fecha_pago', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': 'DD/MM/AAAA'},
        {'name': 'fecha_notificacion_pago', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': 'DD/MM/AAAA'},
    ]
    factura = forms.ModelChoiceField(
        queryset=Factura.objects.none(),  # El queryset real se define en __init__
        required=False,
        widget=Select2Widget(
            attrs={'data-placeholder': 'Buscar Factura Pendiente...'}),
        label="Factura Asociada"
    )

    reclamacion = forms.ModelChoiceField(
        queryset=Reclamacion.objects.none(),  # El queryset real se define en __init__
        required=False,
        widget=Select2Widget(
            attrs={'data-placeholder': 'Buscar Reclamación Pendiente...'}),
        label="Reclamación Asociada"
    )

    fecha_pago = forms.CharField(
        label="Fecha de Pago",
        widget=forms.TextInput(
            attrs={'placeholder': 'DD/MM/AAAA', 'class': 'form-control date-input'}),
        required=True
    )

    fecha_notificacion_pago = forms.CharField(
        label="Fecha Notificación Pago",
        widget=forms.TextInput(
            attrs={'placeholder': 'DD/MM/AAAA', 'class': 'form-control date-input'}),
        required=False
    )

    monto_pago = forms.DecimalField(
        label="Monto del Pago",
        max_digits=15, decimal_places=2, localize=True,
        widget=forms.NumberInput(
            attrs={'placeholder': 'Ej: 1234,56', 'class': 'form-control', 'step': '0.01'}),
        required=True
    )

    forma_pago = forms.ChoiceField(
        label="Forma de Pago",
        choices=CommonChoices.FORMA_PAGO_RECLAMACION,
        widget=forms.Select(attrs={'class': 'select2-enable'})
    )

    referencia_pago = forms.CharField(
        label="Referencia de Pago",
        max_length=100, required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'Nro. Transferencia, Zelle, etc.'})
    )

    observaciones_pago = forms.CharField(
        label="Observaciones del Pago",
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )

    documentos_soporte_pago = forms.FileField(
        label="Documento de Soporte",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

    activo = forms.BooleanField(
        label="Pago Activo",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    aplica_igtf_pago = forms.BooleanField(
        label="¿Pago sujeto a IGTF?",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Pago
        fields = [
            'activo', 'factura', 'reclamacion', 'fecha_pago', 'monto_pago',
            'forma_pago', 'referencia_pago', 'aplica_igtf_pago',
            'fecha_notificacion_pago', 'documentos_soporte_pago', 'observaciones_pago'
        ]
        widgets = {
            'factura': Select2Widget(attrs={'data-placeholder': 'Buscar Factura Pendiente...'}),
            'reclamacion': Select2Widget(attrs={'data-placeholder': 'Buscar Reclamación Pendiente...'}),
            'forma_pago': forms.Select(attrs={'class': 'select2-enable'}),
            'observaciones_pago': forms.Textarea(attrs={'rows': 3}),
            'fecha_pago': forms.TextInput(attrs={'placeholder': 'DD/MM/AAAA', 'class': 'form-control date-input'}),
            'fecha_notificacion_pago': forms.TextInput(attrs={'placeholder': 'DD/MM/AAAA', 'class': 'form-control date-input'}),
            'referencia_pago': forms.TextInput(attrs={'placeholder': 'Nro. Transferencia, Zelle, etc.'}),
            # --- CORRECCIÓN: Hacemos el monto de solo lectura ---
            'monto_pago': forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext dark-input-plaintext'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- LÓGICA DE FILTRADO DE FACTURAS Y RECLAMACIONES ---
        estados_factura_pagables = ['GENERADA', 'PENDIENTE', 'VENCIDA']
        self.fields['factura'].queryset = Factura.objects.filter(
            pagada=False, estatus_factura__in=estados_factura_pagables
        ).select_related('contrato_individual__afiliado', 'contrato_colectivo').order_by('-fecha_creacion')

        estados_reclamacion_pagables = ['ABIERTA', 'EN_PROCESO', 'APROBADA']
        self.fields['reclamacion'].queryset = Reclamacion.objects.filter(
            estado__in=estados_reclamacion_pagables
        ).select_related('contrato_individual__afiliado', 'contrato_colectivo').order_by('-fecha_reclamo')

        # --- CORRECCIÓN: Marcamos el monto como no requerido ---
        self.fields['monto_pago'].required = False

        if hasattr(self, 'setup_aware_date_fields'):
            self.setup_aware_date_fields()

        # --- INICIO DE LA CORRECCIÓN QUIRÚRGICA ---
        if self.instance and self.instance.pk:
            # Si estamos editando un pago existente...
            if self.instance.factura:
                # ... y está asociado a una factura, nos aseguramos de que esa factura
                # esté en las opciones, sin importar su estado actual.
                current_factura_qs = Factura.objects.filter(
                    pk=self.instance.factura.pk)
                self.fields['factura'].queryset = (
                    self.fields['factura'].queryset | current_factura_qs).distinct()
                self.fields['reclamacion'].disabled = True

            elif self.instance.reclamacion:
                # ... y lo mismo para la reclamación.
                current_reclamacion_qs = Reclamacion.objects.filter(
                    pk=self.instance.reclamacion.pk)
                self.fields['reclamacion'].queryset = (
                    self.fields['reclamacion'].queryset | current_reclamacion_qs).distinct()
                self.fields['factura'].disabled = True

    def clean(self):
        # Tu lógica de clean es correcta y se mantiene.
        return super().clean()
# ------------------------------
# TarifaForm
# ------------------------------


class TarifaForm(AwareDateInputMixinVE, BaseModelForm):
    # CONFIGURACIÓN PARA EL MIXIN
    aware_date_fields_config = [
        {'name': 'fecha_aplicacion', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
    ]

    # No definimos los campos aquí. Lo haremos todo en la clase Meta
    # para máxima claridad y para evitar conflictos.

    class Meta:
        model = Tarifa
        fields = ['ramo', 'rango_etario', 'fecha_aplicacion', 'monto_anual',
                  'tipo_fraccionamiento', 'activo']

        exclude = ['codigo_tarifa', 'fecha_creacion', 'fecha_modificacion',
                   'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido']

        # === ESTA ES LA CORRECCIÓN CLAVE ===
        # Usamos forms.Select estándar de Django y le añadimos nuestra clase mágica.
        # NO usamos Select2Widget de la librería django-select2.
        widgets = {
            'ramo': Select2Widget,
            'rango_etario': Select2Widget,
            'tipo_fraccionamiento': Select2Widget,

            # Widgets para otros campos
            'fecha_aplicacion': forms.TextInput(
                attrs={'placeholder': PLACEHOLDER_DATE_STRICT,
                       'class': 'form-control'}
            ),
            'monto_anual': forms.NumberInput(
                attrs={'step': '0.01', 'class': 'form-control'}
            ),
            'activo': forms.CheckboxInput(
                # O 'class': 'switch' si prefieres ese estilo
                attrs={'class': 'form-check-input'}
            ),
        }

    # El resto de tus métodos se mantienen exactamente igual
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            if hasattr(self, 'aware_date_fields_config'):
                for config in self.aware_date_fields_config:
                    field_name = config['name']
                    display_format = config['format']

                    if field_name == 'fecha_aplicacion' and field_name in self.fields and hasattr(self.instance, field_name):
                        model_value = getattr(self.instance, field_name, None)
                        if model_value:
                            if isinstance(model_value, date):
                                self.initial[field_name] = model_value.strftime(
                                    display_format)
                        elif self.fields[field_name].required is False:
                            self.initial[field_name] = ''

    def clean_monto_anual(self):
        monto = self.cleaned_data.get('monto_anual')
        if monto is not None and monto <= Decimal('0.00'):
            raise ValidationError('El monto anual debe ser positivo.')
        return monto

    def clean_tipo_fraccionamiento(self):
        tipo = self.cleaned_data.get('tipo_fraccionamiento')
        valid_keys = [choice[0]
                      for choice in CommonChoices.FORMA_PAGO if choice[0]]
        if tipo and tipo not in valid_keys:
            raise ValidationError(
                f"Seleccione una opción válida. '{tipo}' no es permitida.")
        return tipo

    def clean(self):
        cleaned_data = super().clean()
        fecha_aplicacion_obj = cleaned_data.get('fecha_aplicacion')
        hoy_date_para_comparar = django_timezone.now().date()

        if fecha_aplicacion_obj and fecha_aplicacion_obj > hoy_date_para_comparar:
            self.add_error('fecha_aplicacion',
                           "La fecha de aplicación no puede ser futura.")
        return cleaned_data

# ------------------------------
# FacturaForm
# ------------------------------


class FacturaForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields_config = [
        {'name': 'vigencia_recibo_desde', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
        {'name': 'vigencia_recibo_hasta', 'is_datetime': False,
            'format': '%d/%m/%Y', 'placeholder': PLACEHOLDER_DATE_STRICT},
    ]

    class Meta:
        model = Factura
        fields = [
            'activo', 'contrato_individual', 'contrato_colectivo', 'intermediario',
            'estatus_factura', 'estatus_emision', 'aplica_igtf',
            'monto', 'dias_periodo_cobro',
            'vigencia_recibo_desde', 'vigencia_recibo_hasta',
            'observaciones',
        ]
        widgets = {
            'contrato_individual': Select2Widget(attrs={'data-placeholder': 'Buscar Contrato Individual...'}),
            'contrato_colectivo': Select2Widget(attrs={'data-placeholder': 'Buscar Contrato Colectivo...'}),
            'intermediario': Select2Widget(attrs={'data-placeholder': 'Buscar Intermediario...'}),
            'estatus_factura': forms.Select(attrs={'class': 'select2-enable'}),
            'estatus_emision': forms.Select(attrs={'class': 'select2-enable'}),
            'observaciones': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Añadir notas...'}),

            # Hacemos que los campos calculados sean de solo lectura en el HTML
            'monto': forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext dark-input-plaintext'}),
            'dias_periodo_cobro': forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext dark-input-plaintext'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Los campos calculados no son requeridos por el formulario, la vista los llenará.
        self.fields['monto'].required = False
        self.fields['dias_periodo_cobro'].required = False

        if hasattr(self, 'setup_aware_date_fields'):
            self.setup_aware_date_fields()

    def clean(self):
        cleaned_data = super().clean()
        contrato_individual = cleaned_data.get('contrato_individual')
        contrato_colectivo = cleaned_data.get('contrato_colectivo')
        f_desde = cleaned_data.get('vigencia_recibo_desde')
        f_hasta = cleaned_data.get('vigencia_recibo_hasta')
        if not contrato_individual and not contrato_colectivo:
            raise forms.ValidationError(
                "Debe seleccionar un Contrato Individual o un Contrato Colectivo.", code='contrato_requerido')
        if contrato_individual and contrato_colectivo:
            raise forms.ValidationError(
                "Solo puede seleccionar un tipo de contrato (Individual o Colectivo).", code='multiples_contratos')
        if f_desde and f_hasta:
            if isinstance(f_desde, date) and isinstance(f_hasta, date) and f_hasta < f_desde:
                self.add_error(
                    'vigencia_recibo_hasta', 'La fecha "Hasta" de vigencia del recibo no puede ser anterior a la fecha "Desde".')
        contrato_seleccionado = contrato_individual or contrato_colectivo
        if contrato_seleccionado and f_desde and f_hasta and isinstance(f_desde, date) and isinstance(f_hasta, date):
            fecha_inicio_contrato = contrato_seleccionado.fecha_inicio_vigencia
            if isinstance(fecha_inicio_contrato, datetime):
                fecha_inicio_contrato = django_timezone.localtime(fecha_inicio_contrato).date(
                ) if django_timezone.is_aware(fecha_inicio_contrato) else fecha_inicio_contrato.date()
            fecha_fin_contrato = contrato_seleccionado.fecha_fin_vigencia
            if isinstance(fecha_fin_contrato, datetime):
                fecha_fin_contrato = django_timezone.localtime(fecha_fin_contrato).date(
                ) if django_timezone.is_aware(fecha_fin_contrato) else fecha_fin_contrato.date()
            if fecha_inicio_contrato and f_desde < fecha_inicio_contrato:
                self.add_error(
                    'vigencia_recibo_desde', f"La vigencia del recibo ({f_desde.strftime('%d/%m/%Y')}) no puede iniciar antes que la del contrato ({fecha_inicio_contrato.strftime('%d/%m/%Y')}).")
            if fecha_fin_contrato and f_hasta > fecha_fin_contrato:
                self.add_error(
                    'vigencia_recibo_hasta', f"La vigencia del recibo ({f_hasta.strftime('%d/%m/%Y')}) no puede terminar después que la del contrato ({fecha_fin_contrato.strftime('%d/%m/%Y')}).")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.monto_pendiente = instance.monto
            if not instance.monto or instance.monto <= Decimal('0.00'):
                instance.pagada = True
                instance.monto_pendiente = Decimal('0.00')
                instance.estatus_factura = 'PAGADA'
        if commit:
            instance.save()
        return instance


# ------------------------------
# AuditoriaSistemaForm
# ------------------------------


# No hay campos de fecha que el usuario ingrese
class AuditoriaSistemaForm(BaseModelForm):
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.filter(is_active=True).order_by(
        'email'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Usuario...'}), label="Usuario")

    class Meta:
        model = AuditoriaSistema
        fields = ['tipo_accion', 'resultado_accion', 'usuario', 'tabla_afectada',
                  'registro_id_afectado', 'detalle_accion', 'direccion_ip', 'agente_usuario']
        exclude = ['tiempo_inicio', 'tiempo_final',
                   'control_fecha_actual']  # tiempo_final es auto_now
        widgets = {'tipo_accion': forms.Select(), 'resultado_accion': forms.Select(), 'tabla_afectada': forms.Select(
        ), 'detalle_accion': forms.Textarea(attrs={'rows': 3}), 'agente_usuario': forms.Textarea(attrs={'rows': 2}), }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields['tabla_afectada'].choices = [
                ('', '---------')] + get_modelo_choices()
        except NameError:
            logger.warning(
                "Función get_modelo_choices no encontrada para AuditoriaSistemaForm")
            self.fields['tabla_afectada'].choices = [('', '---------')]

# ------------------------------
# BusquedaAvanzadaForm
# ------------------------------


# No es ModelForm, el mixin no aplica. El parseo se hace en la vista.
class BusquedaAvanzadaForm(forms.Form):
    MODELOS_DESTINO = [('ContratoIndividual', ("Contratos Individuales")), ('ContratoColectivo', ("Contratos Colectivos")), ('AfiliadoIndividual', ("Afiliados Individuales")), ('AfiliadoColectivo',
                                                                                                                                                                                 ("Afiliados Colectivos")), ('Reclamacion', ("Reclamaciones")), ('Pago', ("Pagos")), ('Tarifa', ("Tarifas")), ('Factura', ("Facturas")), ('AuditoriaSistema', ("Auditoría del Sistema")),]
    modelo_destino = forms.ChoiceField(
        choices=MODELOS_DESTINO, label=("Modelo Destino"))
    termino_busqueda = forms.CharField(
        max_length=255, label=("Término de Búsqueda"))
    campo_busqueda = forms.CharField(
        max_length=255, label=("Campo de Búsqueda"), required=False)
    fecha_desde = forms.DateField(label=("Fecha Desde"), required=False, widget=forms.DateInput(
        # Mantenido como DateField, la vista debe hacer make_aware
        attrs={'type': 'date', 'class': 'form-control'}))
    fecha_hasta = forms.DateField(label=("Fecha Hasta"), required=False, widget=forms.DateInput(
        # Mantenido como DateField, la vista debe hacer make_aware
        attrs={'type': 'date', 'class': 'form-control'}))

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error(
                'fecha_hasta', "La fecha final debe ser posterior a la inicial")
        return cleaned_data

# ------------------------------
# RegistroComisionForm
# ------------------------------


class RegistroComisionForm(AwareDateInputMixinVE, forms.ModelForm):
    aware_date_fields = ['fecha_pago_a_intermediario']

    intermediario_display = forms.CharField(label="Intermediario Beneficiario", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    tipo_comision_display = forms.CharField(label="Tipo de Comisión", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    monto_comision_display = forms.CharField(label="Monto Comisión", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    porcentaje_aplicado_display = forms.CharField(label="Porcentaje Aplicado (%)", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    monto_base_calculo_display = forms.CharField(label="Monto Base Cálculo", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    fecha_calculo_display = forms.CharField(label="Fecha de Cálculo", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    contrato_individual_display = forms.CharField(label="Contrato Individual Origen", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    contrato_colectivo_display = forms.CharField(label="Contrato Colectivo Origen", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    pago_cliente_display = forms.CharField(label="Pago Cliente Origen", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    factura_origen_display = forms.CharField(label="Factura Origen", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))
    intermediario_vendedor_display = forms.CharField(label="Intermediario Vendedor (Override)", required=False, widget=forms.TextInput(
        attrs={'readonly': True, 'class': 'form-control-plaintext dark-input-plaintext'}))

    estatus_pago_comision = forms.ChoiceField(choices=RegistroComision.ESTATUS_PAGO_CHOICES, widget=Select2Widget(
        attrs={'class': 'select2-dark', 'data-placeholder': 'Seleccione estado...'}), label="Estado del Pago de Comisión")
    fecha_pago_a_intermediario = forms.CharField(
        widget=forms.TextInput(
            attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}),
        required=False,
        label="Fecha de Pago a Intermediario"
    )

    class Meta:
        model = RegistroComision
        fields = ['estatus_pago_comision', 'fecha_pago_a_intermediario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['intermediario_display'].initial = str(
                self.instance.intermediario) if self.instance.intermediario else "N/A"
            self.fields['tipo_comision_display'].initial = self.instance.get_tipo_comision_display()
            self.fields['monto_comision_display'].initial = f"${self.instance.monto_comision:,.2f}" if self.instance.monto_comision is not None else "N/A"
            self.fields['porcentaje_aplicado_display'].initial = f"{self.instance.porcentaje_aplicado:.2f}%" if self.instance.porcentaje_aplicado is not None else "N/A"
            self.fields['monto_base_calculo_display'].initial = f"${self.instance.monto_base_calculo:,.2f}" if self.instance.monto_base_calculo is not None else "N/A"
            # Formatear fecha_calculo que es DateTimeField
            if self.instance.fecha_calculo:
                if django_timezone.is_aware(self.instance.fecha_calculo):
                    fecha_calculo_local = django_timezone.localtime(
                        self.instance.fecha_calculo)
                    self.fields['fecha_calculo_display'].initial = fecha_calculo_local.strftime(
                        '%d/%m/%Y %H:%M:%S')
                else:  # Si fuera naive, aunque no debería serlo si viene de la BD con USE_TZ=True
                    self.fields['fecha_calculo_display'].initial = self.instance.fecha_calculo.strftime(
                        '%d/%m/%Y %H:%M:%S')
            else:
                self.fields['fecha_calculo_display'].initial = "N/A"

            self.fields['contrato_individual_display'].initial = str(
                self.instance.contrato_individual) if self.instance.contrato_individual else "N/A"
            self.fields['contrato_colectivo_display'].initial = str(
                self.instance.contrato_colectivo) if self.instance.contrato_colectivo else "N/A"
            self.fields['pago_cliente_display'].initial = str(
                self.instance.pago_cliente) if self.instance.pago_cliente else "N/A"
            self.fields['factura_origen_display'].initial = str(
                self.instance.factura_origen) if self.instance.factura_origen else "N/A"
            self.fields['intermediario_vendedor_display'].initial = str(
                self.instance.intermediario_vendedor) if self.instance.intermediario_vendedor else "N/A"
            if self.instance.estatus_pago_comision == 'PENDIENTE' or self.instance.estatus_pago_comision == 'ANULADA':
                # Si el campo fecha_pago_a_intermediario es CharField, su 'initial' debe ser string
                # O None, el widget lo manejará
                self.fields['fecha_pago_a_intermediario'].initial = ''
        field_order = ['intermediario_display', 'tipo_comision_display', 'monto_comision_display', 'porcentaje_aplicado_display', 'monto_base_calculo_display', 'fecha_calculo_display',
                       'contrato_individual_display', 'contrato_colectivo_display', 'pago_cliente_display', 'factura_origen_display', 'intermediario_vendedor_display', 'estatus_pago_comision', 'fecha_pago_a_intermediario']
        self.order_fields(field_order)

    def clean(self):
        cleaned_data = super().clean()
        estatus = cleaned_data.get('estatus_pago_comision')
        fecha_pago_aware = cleaned_data.get('fecha_pago_a_intermediario')
        if estatus == 'PAGADA' and not fecha_pago_aware:
            self.add_error('fecha_pago_a_intermediario',
                           "Debe ingresar la fecha de pago si la comisión está marcada como PAGADA.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.estatus_pago_comision != 'PAGADA':
            instance.fecha_pago_a_intermediario = None  # El modelo debe permitir null=True
        if commit:
            instance.save()
        return instance
