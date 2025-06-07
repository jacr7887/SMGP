# myapp/forms.py
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, EmailValidator
from django.db.models import Sum
from django_select2.forms import Select2Widget, Select2MultipleWidget
# Necesario para cálculos de fechas
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta, datetime  # Python's datetime
import logging
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


class BaseModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (Select2Widget, Select2MultipleWidget)):
                continue

            is_date_charfield_handled_by_mixin = hasattr(self, 'aware_date_fields') and \
                field_name in self.aware_date_fields and \
                isinstance(field, forms.CharField)

            # Aplicar placeholder a inputs que no sean de fecha manejados por el mixin y que no tengan ya placeholder
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
            'tipo_empresa': forms.Select(),
            'direccion_comercial': forms.Textarea(attrs={'rows': 3}),
            'estado': forms.Select(),
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

    def clean_rif(self):
        rif = self.cleaned_data['rif']
        try:
            validate_rif(rif)
        except ValidationError as e:
            raise forms.ValidationError("RIF inválido") from e
        if self.instance.pk:
            if AfiliadoColectivo.objects.filter(rif=rif).exclude(pk=self.instance.pk).exists():
                raise ValidationError("Este RIF ya está registrado.")
        elif AfiliadoColectivo.objects.filter(rif=rif).exists():
            raise ValidationError("Este RIF ya está registrado.")
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

# ------------------------------
# Formulario para Usuario
# ------------------------------


class FormularioCreacionUsuario(AwareDateInputMixinVE, UserCreationForm, BaseModelForm):
    aware_date_fields = ['fecha_nacimiento']

    email = forms.EmailField(label="Correo Electrónico", required=True)
    primer_nombre = forms.CharField(
        max_length=100, label="Primer Nombre", required=True)
    primer_apellido = forms.CharField(
        max_length=100, label="Primer Apellido", required=True)
    segundo_nombre = forms.CharField(
        max_length=100, label="Segundo Nombre", required=False)
    segundo_apellido = forms.CharField(
        max_length=100, label="Segundo Apellido", required=False)
    nivel_acceso = forms.ChoiceField(
        choices=CommonChoices.NIVEL_ACCESO, label="Nivel de Acceso", initial=1)
    tipo_usuario = forms.ChoiceField(
        choices=CommonChoices.TIPO_USUARIO, label="Tipo de Usuario")

    fecha_nacimiento = forms.CharField(
        label="Fecha de Nacimiento",
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}),
    )
    departamento = forms.ChoiceField(
        choices=CommonChoices.DEPARTAMENTO, required=False, label="Departamento")
    telefono = forms.CharField(max_length=15, required=False, label="Teléfono")
    direccion = forms.CharField(widget=forms.Textarea(
        attrs={'rows': 3}), required=False, label="Dirección")
    intermediario = forms.ModelChoiceField(
        queryset=Intermediario.objects.filter(
            activo=True).order_by('nombre_completo'),
        required=False,
        widget=Select2Widget(attrs={
                             'data-placeholder': 'Seleccione un intermediario...', 'class': 'form-control django-select2'}),
        label="Intermediario Asociado"
    )
    activo = forms.BooleanField(
        required=False, initial=True, label="Cuenta Activa (Soft Delete)")

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('email', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
                  'tipo_usuario', 'fecha_nacimiento', 'departamento', 'telefono', 'direccion',
                  'intermediario', 'nivel_acceso', 'activo')

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        return user


class FormularioEdicionUsuario(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = ['fecha_nacimiento']

    primer_nombre = forms.CharField(
        max_length=100, label="Primer Nombre", required=True)
    primer_apellido = forms.CharField(
        max_length=100, label="Primer Apellido", required=True)
    segundo_nombre = forms.CharField(
        max_length=100, label="Segundo Nombre", required=False)
    segundo_apellido = forms.CharField(
        max_length=100, label="Segundo Apellido", required=False)

    fecha_nacimiento = forms.CharField(
        label="Fecha de Nacimiento",
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}),
    )
    telefono = forms.CharField(max_length=15, required=False, label="Teléfono")
    direccion = forms.CharField(widget=forms.Textarea(
        attrs={'rows': 3}), required=False, label="Dirección")
    tipo_usuario = forms.ChoiceField(
        choices=CommonChoices.TIPO_USUARIO, label="Tipo de Usuario")
    nivel_acceso = forms.ChoiceField(
        choices=CommonChoices.NIVEL_ACCESO, label="Nivel de Acceso")
    departamento = forms.ChoiceField(
        choices=CommonChoices.DEPARTAMENTO, required=False, label="Departamento")
    intermediario = forms.ModelChoiceField(
        queryset=Intermediario.objects.filter(
            activo=True).order_by('nombre_completo'),
        required=False,
        widget=Select2Widget(attrs={
                             'data-placeholder': 'Seleccione un intermediario...', 'class': 'form-control django-select2'}),
        label="Intermediario Asociado"
    )
    activo = forms.BooleanField(
        required=False, label="Cuenta Activa (Soft Delete)")
    is_staff = forms.BooleanField(
        required=False, label="Acceso al Panel de Admin")
    is_superuser = forms.BooleanField(
        required=False, label="Superusuario (Django)")
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by('name'),
        widget=Select2MultipleWidget(
            attrs={'data-placeholder': 'Seleccionar grupos...', 'class': 'django-select2'}),
        required=False, label="Grupos de Permisos"
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').all().order_by(
            'content_type__app_label', 'content_type__model', 'name'),
        widget=Select2MultipleWidget(
            attrs={'data-placeholder': 'Seleccionar permisos...', 'class': 'django-select2'}),
        required=False, label="Permisos Específicos"
    )

    class Meta:
        model = Usuario
        fields = [
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'fecha_nacimiento', 'telefono', 'direccion',
            'tipo_usuario', 'nivel_acceso', 'departamento', 'intermediario', 'activo',
            'is_staff', 'is_superuser', 'groups', 'user_permissions',
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        user_being_edited = self.instance
        if user_being_edited and user_being_edited.pk:
            self.fields['email_display'] = forms.CharField(label="Correo Electrónico", initial=user_being_edited.email, disabled=True, required=False, widget=forms.TextInput(
                attrs={'readonly': True, 'class': 'form-control-plaintext'}))
            self.fields['username_display'] = forms.CharField(label="Nombre de usuario (interno)", initial=user_being_edited.username,
                                                              disabled=True, required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'form-control-plaintext'}))
            field_order = ['email_display', 'username_display'] + [
                f_name for f_name in self.fields if f_name not in ['email_display', 'username_display']]
            self.fields = {k: self.fields[k]
                           for k in field_order if k in self.fields}
        if self.request_user and user_being_edited and user_being_edited.pk:
            is_editing_self = self.request_user.pk == user_being_edited.pk
            if user_being_edited.is_superuser and not self.request_user.is_superuser:
                for field_name in self.Meta.fields:
                    if field_name in self.fields:
                        self.fields[field_name].disabled = True
                if 'email_display' in self.fields:
                    self.fields['email_display'].disabled = True
                if 'username_display' in self.fields:
                    self.fields['username_display'].disabled = True
                return
            if 'is_superuser' in self.fields and not self.request_user.is_superuser:
                self.fields['is_superuser'].disabled = True
            if 'nivel_acceso' in self.fields:
                if not self.request_user.is_superuser:
                    self.fields['nivel_acceso'].choices = [
                        c for c in CommonChoices.NIVEL_ACCESO if c[0] != 5]
                    if user_being_edited.nivel_acceso == 5:
                        self.fields['nivel_acceso'].disabled = True
                    elif not is_editing_self and self.request_user.nivel_acceso < 5:
                        self.fields['nivel_acceso'].choices = [
                            c for c in CommonChoices.NIVEL_ACCESO if c[0] <= self.request_user.nivel_acceso and c[0] != 5]
            if not self.request_user.is_superuser:
                if 'is_staff' in self.fields:
                    self.fields['is_staff'].disabled = True
                    self.fields['is_staff'].help_text = "Gestionado por Nivel de Acceso. Solo Superusuarios pueden modificar directamente."
                if self.request_user.nivel_acceso < 4:
                    if 'groups' in self.fields:
                        self.fields['groups'].disabled = True
                    if 'user_permissions' in self.fields:
                        self.fields['user_permissions'].disabled = True

    def clean_nivel_acceso(self):
        nivel_acceso_str = self.cleaned_data.get('nivel_acceso')
        try:
            nivel_acceso = int(
                nivel_acceso_str) if nivel_acceso_str is not None else None
        except (ValueError, TypeError):
            raise forms.ValidationError("Nivel de acceso inválido.")
        user_being_edited = self.instance
        request_user = self.request_user
        if user_being_edited and user_being_edited.pk and request_user and nivel_acceso is not None:
            is_editing_self = request_user.pk == user_being_edited.pk
            if is_editing_self and user_being_edited.is_superuser and nivel_acceso < 5 and Usuario.objects.filter(is_superuser=True, activo=True).exclude(pk=user_being_edited.pk).count() == 0:
                raise forms.ValidationError(
                    "No se puede remover el estado de Administrador/Superusuario del único superusuario activo.")
            if not request_user.is_superuser and nivel_acceso == 5:
                raise forms.ValidationError(
                    "No tiene permiso para asignar el nivel de Administrador/Superusuario.")
            if not request_user.is_superuser and user_being_edited.nivel_acceso == 5 and nivel_acceso != 5:
                raise forms.ValidationError(
                    "No tiene permiso para cambiar el nivel de un Administrador/Superusuario.")
            if not request_user.is_superuser and not is_editing_self and nivel_acceso > request_user.nivel_acceso:
                raise forms.ValidationError(
                    "No puede asignar a otro usuario un nivel de acceso superior al suyo.")
        elif nivel_acceso is None and self.fields['nivel_acceso'].required:
            raise forms.ValidationError("Este campo es requerido.")
        return nivel_acceso

    # El mixin lo hace aware, aquí validaciones adicionales
    def clean_fecha_nacimiento(self):
        fecha_nac_aware = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nac_aware:
            # El validador espera un objeto date, no datetime
            validate_fecha_nacimiento(fecha_nac_aware.date())
        return fecha_nac_aware


# --- Formulario de Login - SIN CAMBIOS ---
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
    intermediario_relacionado = forms.ModelChoiceField(queryset=Intermediario.objects.filter(activo=True).order_by('nombre_completo'), required=False, widget=Select2Widget(
        attrs={'data-placeholder': 'Buscar Intermediario Padre...', 'class': 'form-control select2-field'}), label="Intermediario Padre (si aplica)")
    usuarios = forms.ModelMultipleChoiceField(queryset=Usuario.objects.filter(activo=True).order_by('primer_apellido', 'primer_nombre', 'email'), required=False, widget=Select2MultipleWidget(
        attrs={'data-placeholder': 'Seleccionar Usuarios Gestores...', 'class': 'form-control select2-field'}), label="Usuarios Gestores Asignados")

    class Meta:
        model = Intermediario
        fields = ['activo', 'nombre_completo', 'rif', 'direccion_fiscal', 'telefono_contacto', 'email_contacto',
                  'porcentaje_comision', 'porcentaje_override', 'intermediario_relacionado', 'usuarios']
        exclude = ['codigo', 'fecha_creacion', 'fecha_modificacion',
                   'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido']
        widgets = {'direccion_fiscal': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), 'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}), 'rif': forms.TextInput(attrs={'class': 'form-control'}), 'email_contacto': forms.EmailInput(attrs={'class': 'form-control'}), 'telefono_contacto': forms.TextInput(attrs={'class': 'form-control'}),
                   'porcentaje_comision': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}), 'porcentaje_override': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}), 'intermediario_relacionado': forms.Select(attrs={'class': 'form-select select2-field'}), 'usuarios': forms.SelectMultiple(attrs={'class': 'form-select select2-field'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            validate_rif(rif)
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


class AfiliadoIndividualForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = ['fecha_nacimiento', 'fecha_ingreso']

    intermediario = forms.ModelChoiceField(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Intermediario...'}), label="Intermediario Asignado")

    fecha_nacimiento = forms.CharField(label="Fecha de Nacimiento", required=True, widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}))
    fecha_ingreso = forms.CharField(label="Fecha Ingreso", required=False, widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}))

    primer_nombre = forms.CharField(max_length=100, widget=forms.TextInput(
        attrs={'placeholder': 'Primer Nombre'}))
    segundo_nombre = forms.CharField(max_length=100, required=False)
    primer_apellido = forms.CharField(max_length=100, widget=forms.TextInput(
        attrs={'placeholder': 'Primer Apellido'}))
    segundo_apellido = forms.CharField(max_length=100, required=False)
    tipo_identificacion = forms.ChoiceField(
        choices=CommonChoices.TIPO_IDENTIFICACION, widget=forms.Select())
    cedula = forms.CharField(max_length=20, widget=forms.TextInput(
        attrs={'placeholder': 'Ej: V-12345678'}))
    estado_civil = forms.ChoiceField(
        choices=CommonChoices.ESTADO_CIVIL, widget=forms.Select())
    sexo = forms.ChoiceField(choices=CommonChoices.SEXO, widget=forms.Select())
    parentesco = forms.ChoiceField(
        choices=CommonChoices.PARENTESCO, widget=forms.Select())
    nacionalidad = forms.CharField(
        max_length=50, initial='Venezolana')  # Default
    zona_postal = forms.CharField(max_length=10, required=False, widget=forms.TextInput(
        attrs={'placeholder': 'Ej: 1010'}))
    estado = forms.ChoiceField(
        choices=CommonChoices.ESTADOS_VE, widget=forms.Select())
    municipio = forms.CharField(max_length=100)
    ciudad = forms.CharField(max_length=100)
    direccion_habitacion = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}))
    telefono_habitacion = forms.CharField(max_length=20, required=False)
    email = forms.EmailField(required=False, widget=forms.EmailInput(
        attrs={'placeholder': 'correo@ejemplo.com'}))
    direccion_oficina = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False)
    telefono_oficina = forms.CharField(max_length=20, required=False)
    activo = forms.BooleanField(
        required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'switch'}))

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
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
            'estado_civil': forms.Select(), 'sexo': forms.Select(),
            'parentesco': forms.Select(), 'tipo_identificacion': forms.Select(),
            'estado': forms.Select(),
            'direccion_habitacion': forms.Textarea(attrs={'rows': 3}),
            'direccion_oficina': forms.Textarea(attrs={'rows': 3}),
            'cedula': forms.TextInput(attrs={'placeholder': 'Ej: V-12345678'}),
            'primer_nombre': forms.TextInput(attrs={'placeholder': 'Primer Nombre'}),
            'primer_apellido': forms.TextInput(attrs={'placeholder': 'Primer Apellido'}),
            'email': forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
        }
        help_texts = {
            'intermediario': 'Seleccione el intermediario que registró/gestionó a este afiliado.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'intermediario' in self.fields:
            self.fields['intermediario'].empty_label = "--- Seleccione Intermediario ---"

    def clean_cedula(self):
        tipo = self.cleaned_data.get('tipo_identificacion')
        cedula_str = self.cleaned_data.get('cedula')
        if not cedula_str:
            raise ValidationError("El campo cédula es obligatorio.")
        cedula = cedula_str.upper().strip()
        try:
            if tipo in ['V', 'E']:
                validate_cedula(cedula)
            elif tipo in ['J', 'G']:
                validate_rif(cedula)
            is_updating = self.instance and self.instance.pk
            query = self._meta.model.objects.filter(
                cedula=cedula, tipo_identificacion=tipo)  # Añadir tipo_identificacion
            if is_updating:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError(
                    "Esta identificación ya está registrada para este tipo.")
        except ValidationError as e:
            raise e
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

    def clean(self):
        cleaned_data = super().clean()
        fecha_nacimiento_aware = cleaned_data.get('fecha_nacimiento')
        fecha_ingreso_aware = cleaned_data.get('fecha_ingreso')
        hoy_aware = django_timezone.now()

        if fecha_nacimiento_aware:
            validate_fecha_nacimiento(fecha_nacimiento_aware.date())
            if fecha_ingreso_aware and fecha_ingreso_aware < fecha_nacimiento_aware:
                self.add_error('fecha_ingreso',
                               "Ingreso no puede ser antes de nacimiento.")
        if fecha_ingreso_aware and fecha_ingreso_aware > hoy_aware:
            self.add_error('fecha_ingreso', "Ingreso no puede ser futuro.")
        return cleaned_data

# ------------------------------
# ContratoIndividualForm
# ------------------------------


class ContratoIndividualForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = [
        'fecha_emision',
        'fecha_inicio_vigencia',
        'fecha_fin_vigencia',
        'fecha_inicio_vigencia_recibo',
        'fecha_fin_vigencia_recibo'
    ]

    afiliado = forms.ModelChoiceField(queryset=AfiliadoIndividual.objects.filter(activo=True).order_by('primer_apellido', 'primer_nombre'),
                                      required=True, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Afiliado Titular...'}), label="Afiliado Individual Titular")
    intermediario = forms.ModelChoiceField(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), required=True, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Intermediario...'}), label="Intermediario")
    tarifa_aplicada = forms.ModelChoiceField(queryset=Tarifa.objects.filter(activo=True).order_by(
        'ramo', '-fecha_aplicacion'), required=True, widget=Select2Widget(attrs={'data-placeholder': 'Seleccionar Tarifa Aplicable...'}), label="Tarifa Aplicada")

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

    ramo = forms.ChoiceField(
        choices=CommonChoices.RAMO, widget=Select2Widget())
    forma_pago = forms.ChoiceField(
        choices=CommonChoices.FORMA_PAGO, widget=Select2Widget())
    estatus = forms.ChoiceField(
        choices=CommonChoices.ESTADOS_VIGENCIA, widget=Select2Widget())
    estado_contrato = forms.ChoiceField(
        choices=CommonChoices.ESTADO_CONTRATO, widget=Select2Widget())
    periodo_vigencia_meses = forms.IntegerField(
        min_value=1, widget=forms.NumberInput(attrs={'min': '1'}), required=False)
    tipo_identificacion_contratante = forms.ChoiceField(
        choices=CommonChoices.TIPO_IDENTIFICACION,
        widget=Select2Widget(),
        label="Tipo Identificación Contratante"
    )
    contratante_cedula = forms.CharField(max_length=20)
    contratante_nombre = forms.CharField(max_length=200)
    direccion_contratante = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False)
    telefono_contratante = forms.CharField(max_length=20, required=False)
    email_contratante = forms.EmailField(required=False)
    plan_contratado = forms.CharField(max_length=100, required=False)
    suma_asegurada = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal(
        '0.01'), widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}))
    comision_anual = forms.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal(
        '100'), widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}), required=False)
    estatus_emision_recibo = forms.ChoiceField(
        choices=CommonChoices.EMISION_RECIBO, widget=Select2Widget(), required=False)
    criterio_busqueda = forms.CharField(max_length=255, required=False)
    estatus_detalle = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}), required=False)
    consultar_afiliados_activos = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    activo = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(
        attrs={'class': 'form-check-input'}))

    class Meta:
        model = ContratoIndividual
        fields = [
            'activo', 'ramo', 'forma_pago', 'estatus', 'estado_contrato',
            'fecha_emision', 'fecha_inicio_vigencia', 'fecha_fin_vigencia',
            'periodo_vigencia_meses', 'intermediario', 'tipo_identificacion_contratante',
            'contratante_cedula', 'contratante_nombre', 'direccion_contratante',
            'telefono_contratante', 'email_contratante', 'afiliado', 'plan_contratado',
            'suma_asegurada', 'fecha_inicio_vigencia_recibo', 'fecha_fin_vigencia_recibo',
            'comision_anual', 'tarifa_aplicada', 'estatus_emision_recibo',
            'criterio_busqueda', 'estatus_detalle', 'consultar_afiliados_activos',
        ]
        # Excluir campos autogenerados o no deseados en el form
        exclude = [
            'numero_contrato', 'numero_poliza', 'certificado', 'monto_total',
            'pagos_realizados', 'comision_recibo', 'importe_anual_contrato',
            'importe_recibo_contrato', 'dias_transcurridos_ingreso',
            'fecha_creacion', 'fecha_modificacion',  # De ModeloBase
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',  # De ModeloBase
        ]
        widgets = {  # Widgets para campos NO de fecha CharField, o si quieres anular el TextInput por defecto
            'ramo': Select2Widget,
            'forma_pago': Select2Widget,
            'estatus': Select2Widget,
            'estado_contrato': Select2Widget,
            'tipo_identificacion_contratante': Select2Widget,
            'estatus_emision_recibo': Select2Widget,
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consultar_afiliados_activos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'suma_asegurada': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'periodo_vigencia_meses': forms.NumberInput(attrs={'min': '1'}),
            'comision_anual': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'direccion_contratante': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'fecha_fin_vigencia': "Opcional. Si se provee la Duración, esta fecha se calculará. Si ingresa ambas, deben ser consistentes.",
            'periodo_vigencia_meses': "Opcional. Si se provee la Fecha Fin, esta duración se calculará. Si ingresa ambas, deben ser consistentes.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            self.initial.setdefault('estatus', 'VIGENTE')
            self.initial.setdefault('activo', True)
            # No establecer initial para CharFields de fecha aquí, placeholder es suficiente

    def clean(self):  # Adaptado para fechas aware
        cleaned_data = super().clean()
        fecha_emision = cleaned_data.get("fecha_emision")
        fecha_inicio_vigencia = cleaned_data.get("fecha_inicio_vigencia")
        fecha_fin_vigencia_form = cleaned_data.get("fecha_fin_vigencia")
        periodo_meses_form = cleaned_data.get("periodo_vigencia_meses")
        fecha_inicio_recibo = cleaned_data.get("fecha_inicio_vigencia_recibo")
        fecha_fin_recibo = cleaned_data.get("fecha_fin_vigencia_recibo")

        if fecha_emision and fecha_inicio_vigencia and fecha_emision > fecha_inicio_vigencia:
            self.add_error(
                'fecha_emision', "La emisión no puede ser después del inicio de vigencia.")

        if fecha_inicio_vigencia:
            if periodo_meses_form is not None and fecha_fin_vigencia_form is not None:
                if periodo_meses_form < 1:
                    self.add_error('periodo_vigencia_meses',
                                   "Duración debe ser al menos 1 mes.")
                else:
                    try:
                        fin_calc = fecha_inicio_vigencia.date() + relativedelta(months=+
                                                                                periodo_meses_form) - timedelta(days=1)
                        if fin_calc != fecha_fin_vigencia_form.date():
                            self.add_error(None, forms.ValidationError(
                                f"Inconsistencia Fecha Fin ({fecha_fin_vigencia_form.strftime('%d/%m/%Y')}) vs Duración {periodo_meses_form} meses (resulta en {fin_calc.strftime('%d/%m/%Y')}).", code='inconsistencia_fecha_duracion'))
                    except Exception as e:
                        self.add_error(None, f"Error verificando fechas: {e}")
            elif fecha_fin_vigencia_form is not None:
                if fecha_fin_vigencia_form < fecha_inicio_vigencia:
                    self.add_error('fecha_fin_vigencia',
                                   'Fin no puede ser antes de inicio.')
            elif periodo_meses_form is None and (not self.instance or not self.instance.pk):
                self.add_error('periodo_vigencia_meses',
                               "Debe ingresar Duración o Fecha Fin.")
        elif not self.instance or not self.instance.pk:
            self.add_error('fecha_inicio_vigencia',
                           "Fecha de inicio de vigencia es obligatoria.")

        tipo_id_contratante = cleaned_data.get(
            'tipo_identificacion_contratante')
        cedula_contratante = cleaned_data.get('contratante_cedula')
        if cedula_contratante and tipo_id_contratante:
            try:
                if tipo_id_contratante in ['V', 'E']:
                    validate_cedula(cedula_contratante)
                elif tipo_id_contratante in ['J', 'G']:
                    validate_rif(cedula_contratante)
            except ValidationError as e:
                self.add_error('contratante_cedula', e)
        elif not cedula_contratante and tipo_id_contratante:
            self.add_error('contratante_cedula',
                           'Requerido si se especifica tipo de ID.')

        if fecha_inicio_recibo and fecha_inicio_vigencia and fecha_inicio_recibo < fecha_inicio_vigencia:
            self.add_error('fecha_inicio_vigencia_recibo',
                           "Inicio recibo no puede ser antes de inicio contrato.")

        final_fecha_fin_contrato_aware = fecha_fin_vigencia_form
        if not final_fecha_fin_contrato_aware and fecha_inicio_vigencia and periodo_meses_form:
            try:
                final_fecha_fin_contrato_date_part = fecha_inicio_vigencia.date(
                ) + relativedelta(months=+periodo_meses_form) - timedelta(days=1)
                final_fecha_fin_contrato_aware = django_timezone.make_aware(datetime.datetime.combine(
                    final_fecha_fin_contrato_date_part, datetime.datetime.min.time()))
            except:
                pass

        if fecha_fin_recibo and final_fecha_fin_contrato_aware and fecha_fin_recibo > final_fecha_fin_contrato_aware:
            self.add_error('fecha_fin_vigencia_recibo',
                           "Fin recibo no puede ser después de fin contrato.")
        if fecha_inicio_recibo and fecha_fin_recibo and fecha_fin_recibo < fecha_inicio_recibo:
            self.add_error('fecha_fin_vigencia_recibo',
                           "Fin recibo no puede ser antes de inicio recibo.")
        return cleaned_data

# ------------------------------
# ContratoColectivoForm
# ------------------------------


class ContratoColectivoForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = [
        'fecha_emision', 'fecha_inicio_vigencia', 'fecha_fin_vigencia',
    ]
    afiliados_colectivos = forms.ModelMultipleChoiceField(queryset=AfiliadoColectivo.objects.filter(activo=True).order_by('razon_social'), required=True, widget=Select2MultipleWidget(
        attrs={'data-placeholder': 'Buscar Empresas/Colectivos...'}), label='Empresa(s) o Colectivo(s) Asegurado(s)', help_text="Seleccione al menos una empresa. La Razón Social y RIF se tomarán del primer seleccionado.")
    intermediario = forms.ModelChoiceField(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), required=True, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Intermediario...'}), label="Intermediario")
    tarifa_aplicada = forms.ModelChoiceField(queryset=Tarifa.objects.filter(activo=True).order_by('ramo', '-fecha_aplicacion', 'rango_etario'),
                                             required=True, widget=Select2Widget(attrs={'data-placeholder': 'Seleccionar Tarifa Aplicable...'}), label="Tarifa Aplicada al Contrato")

    fecha_emision = forms.CharField(label="Fecha de Emisión", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_inicio_vigencia = forms.CharField(label="Fecha Inicio Vigencia", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_fin_vigencia = forms.CharField(label="Fecha Fin Vigencia", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=False)

    activo = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(
        attrs={'class': 'form-check-input'}))
    consultar_afiliados_activos = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    tipo_empresa = forms.ChoiceField(
        choices=CommonChoices.TIPO_EMPRESA, widget=Select2Widget(), required=False)
    ramo = forms.ChoiceField(
        choices=CommonChoices.RAMO, widget=Select2Widget())
    forma_pago = forms.ChoiceField(
        choices=CommonChoices.FORMA_PAGO, widget=Select2Widget())
    estatus = forms.ChoiceField(
        choices=CommonChoices.ESTADOS_VIGENCIA, widget=Select2Widget())
    estado_contrato = forms.ChoiceField(
        choices=CommonChoices.ESTADO_CONTRATO, widget=Select2Widget())
    periodo_vigencia_meses = forms.IntegerField(
        min_value=1, widget=forms.NumberInput(attrs={'min': '1'}), required=False)
    cantidad_empleados = forms.IntegerField(
        min_value=1, widget=forms.NumberInput(attrs={'min': '1'}), required=False)
    suma_asegurada = forms.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal(
        '0.01'), widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}))
    direccion_comercial = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False)
    zona_postal = forms.CharField(max_length=10, widget=forms.TextInput(
        attrs={'placeholder': 'Ej: 1010'}), required=False)
    plan_contratado = forms.CharField(max_length=100, widget=forms.TextInput(
        attrs={'placeholder': 'Nombre o Código'}), required=False)
    criterio_busqueda = forms.CharField(max_length=255, widget=forms.TextInput(
        attrs={'placeholder': 'Etiquetas...'}), required=False)

    class Meta:
        model = ContratoColectivo
        fields = [
            'activo', 'ramo', 'forma_pago', 'estatus', 'estado_contrato',
            'fecha_emision', 'fecha_inicio_vigencia', 'fecha_fin_vigencia',
            'periodo_vigencia_meses', 'suma_asegurada', 'intermediario',
            'tarifa_aplicada', 'tipo_empresa', 'cantidad_empleados',
            'direccion_comercial', 'zona_postal', 'plan_contratado',
            'criterio_busqueda', 'afiliados_colectivos', 'consultar_afiliados_activos',
        ]
        exclude = [
            'certificado', 'numero_contrato', 'numero_poliza', 'numero_recibo',
            'rif', 'razon_social', 'pagos_realizados', 'monto_total', 'comision_recibo',
            'fecha_creacion', 'fecha_modificacion',
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'historial_cambios',
        ]
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consultar_afiliados_activos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_empresa': Select2Widget(), 'ramo': Select2Widget(),
            'forma_pago': Select2Widget(), 'estatus': Select2Widget(),
            'estado_contrato': Select2Widget(),
            'periodo_vigencia_meses': forms.NumberInput(attrs={'min': '1'}),
            'cantidad_empleados': forms.NumberInput(attrs={'min': '1'}),
            'suma_asegurada': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'direccion_comercial': forms.Textarea(attrs={'rows': 3}),
            'zona_postal': forms.TextInput(attrs={'placeholder': 'Ej: 1010'}),
            'plan_contratado': forms.TextInput(attrs={'placeholder': 'Nombre o Código'}),
            'criterio_busqueda': forms.TextInput(attrs={'placeholder': 'Etiquetas...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            self.initial.setdefault('estatus', 'VIGENTE')
            self.initial.setdefault('activo', True)
        if 'tarifa_aplicada' in self.fields:
            logger.debug(
                f"ContratoColectivoForm.__init__ FINAL: Queryset tarifa_aplicada. Count: {self.fields['tarifa_aplicada'].queryset.count()}")

    def clean(self):  # Adaptado para fechas aware
        cleaned_data = super().clean()
        fecha_emision = cleaned_data.get("fecha_emision")
        fecha_inicio_vigencia = cleaned_data.get("fecha_inicio_vigencia")
        fecha_fin_vigencia_form = cleaned_data.get("fecha_fin_vigencia")
        periodo_meses_form = cleaned_data.get("periodo_vigencia_meses")
        afiliados_seleccionados = cleaned_data.get('afiliados_colectivos')
        if not afiliados_seleccionados or not afiliados_seleccionados.exists():
            if self.fields.get('afiliados_colectivos') and self.fields['afiliados_colectivos'].required:
                self.add_error('afiliados_colectivos',
                               "Debe seleccionar al menos una empresa.")
        if fecha_emision and fecha_inicio_vigencia and fecha_emision > fecha_inicio_vigencia:
            self.add_error(
                'fecha_emision', "Emisión no puede ser después del inicio de vigencia.")
        if fecha_inicio_vigencia:
            if periodo_meses_form is not None and periodo_meses_form < 1:
                self.add_error('periodo_vigencia_meses',
                               "Duración debe ser al menos 1 mes.")
            if fecha_fin_vigencia_form and fecha_fin_vigencia_form < fecha_inicio_vigencia:
                self.add_error('fecha_fin_vigencia',
                               'Fin no puede ser antes de inicio.')
            if periodo_meses_form is not None and fecha_fin_vigencia_form is not None:
                try:
                    fin_calc = fecha_inicio_vigencia.date() + relativedelta(months=+
                                                                            periodo_meses_form) - timedelta(days=1)
                    if fin_calc != fecha_fin_vigencia_form.date():
                        self.add_error(None, forms.ValidationError(
                            f"Inconsistencia Fecha Fin ({fecha_fin_vigencia_form.strftime('%d/%m/%Y')}) vs Duración {periodo_meses_form} meses (resulta en {fin_calc.strftime('%d/%m/%Y')}).", code='inconsistencia_fecha_duracion'))
                except Exception as e:
                    logger.error(f"Error verificando consistencia fechas: {e}")
                    self.add_error(
                        None, "Error procesando fechas de vigencia.")
            elif periodo_meses_form is None and (not self.instance or not self.instance.pk):
                self.add_error('periodo_vigencia_meses',
                               "Debe ingresar Duración o Fecha Fin.")
        elif not self.instance or not self.instance.pk:
            if self.fields.get('fecha_inicio_vigencia') and self.fields['fecha_inicio_vigencia'].required:
                self.add_error('fecha_inicio_vigencia',
                               "Fecha de inicio es obligatoria.")
        tarifa_seleccionada = cleaned_data.get('tarifa_aplicada')
        if self.fields.get('tarifa_aplicada') and self.fields['tarifa_aplicada'].required and not tarifa_seleccionada:
            self.add_error('tarifa_aplicada', 'Debe seleccionar una tarifa.')
        return cleaned_data

    def save(self, commit=True):  # Como estaba
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
            self.save_m2m()
        return instance
# ------------------------------
# ReclamacionForm
# ------------------------------


class ReclamacionForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = ['fecha_reclamo', 'fecha_cierre_reclamo']

    contrato_individual = forms.ModelChoiceField(queryset=ContratoIndividual.objects.filter(activo=True).select_related('afiliado').order_by(
        '-fecha_emision', 'numero_contrato'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Contrato Individual...'}), label="Contrato Individual Asociado")
    contrato_colectivo = forms.ModelChoiceField(queryset=ContratoColectivo.objects.filter(activo=True).order_by(
        '-fecha_emision', 'numero_contrato'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Contrato Colectivo...'}), label="Contrato Colectivo Asociado")
    usuario_asignado = forms.ModelChoiceField(queryset=Usuario.objects.filter(is_active=True, is_staff=True).order_by(
        'email'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Usuario Asignado...'}), label="Usuario Asignado")
    diagnostico_principal = forms.ChoiceField(choices=CommonChoices.DIAGNOSTICOS, required=True, widget=Select2Widget(
        attrs={'data-placeholder': 'Buscar Diagnóstico Principal...'}), label="Diagnóstico Principal (Médico/Técnico)")
    documentos_adjuntos = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=[
                                          'pdf', 'jpg', 'png']), validate_file_size], required=False, help_text="Formatos: PDF, JPG, PNG. Max 10MB.")

    fecha_reclamo = forms.CharField(label="Fecha de Reclamo", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_cierre_reclamo = forms.CharField(label="Fecha Cierre Reclamo", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=False)

    tipo_reclamacion = forms.ChoiceField(
        choices=CommonChoices.TIPO_RECLAMACION, widget=forms.Select())
    descripcion_reclamo = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}))
    estado = forms.ChoiceField(
        choices=CommonChoices.ESTADO_RECLAMACION, widget=forms.Select())
    monto_reclamado = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, widget=forms.NumberInput(attrs={'step': '0.01'}))
    observaciones_internas = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False)
    observaciones_cliente = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False)
    activo = forms.BooleanField(
        required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'switch'}))

    class Meta:
        model = Reclamacion
        fields = [
            'activo', 'contrato_individual', 'contrato_colectivo',
            'fecha_reclamo', 'tipo_reclamacion', 'descripcion_reclamo', 'estado',
            'monto_reclamado', 'fecha_cierre_reclamo', 'usuario_asignado',
            'diagnostico_principal', 'observaciones_internas', 'observaciones_cliente',
            'documentos_adjuntos',
        ]
        exclude = ['fecha_creacion', 'fecha_modificacion', 'primer_nombre',
                   'segundo_nombre', 'primer_apellido', 'segundo_apellido']
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
            'estado': forms.Select(), 'tipo_reclamacion': forms.Select(),
            'descripcion_reclamo': forms.Textarea(attrs={'rows': 4}),
            'monto_reclamado': forms.NumberInput(attrs={'step': '0.01'}),
            'observaciones_internas': forms.Textarea(attrs={'rows': 3}),
            'observaciones_cliente': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_tipo_reclamacion(self):
        tipo = self.cleaned_data.get('tipo_reclamacion')
        if tipo not in dict(CommonChoices.TIPO_RECLAMACION):
            raise ValidationError(("Tipo de reclamación inválido"))
        return tipo

    def clean(self):
        cleaned_data = super().clean()
        contrato_individual = cleaned_data.get('contrato_individual')
        contrato_colectivo = cleaned_data.get('contrato_colectivo')
        fecha_reclamo_aware = cleaned_data.get('fecha_reclamo')
        fecha_cierre_aware = cleaned_data.get('fecha_cierre_reclamo')
        hoy_aware = django_timezone.now()

        if not contrato_individual and not contrato_colectivo:
            raise ValidationError(
                ("Debe seleccionar un contrato individual o colectivo."))
        if contrato_individual and contrato_colectivo:
            raise ValidationError(("No puede seleccionar ambos contratos."))

        if fecha_reclamo_aware and fecha_cierre_aware and fecha_cierre_aware < fecha_reclamo_aware:
            self.add_error('fecha_cierre_reclamo',
                           "Cierre no puede ser antes del reclamo.")
        if fecha_reclamo_aware and fecha_reclamo_aware > hoy_aware:
            self.add_error('fecha_reclamo',
                           "Fecha del reclamo no puede ser futura.")
        return cleaned_data

# ------------------------------
# PagoForm
# ------------------------------


class PagoForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = ['fecha_pago', 'fecha_notificacion_pago']

    reclamacion = forms.ModelChoiceField(queryset=Reclamacion.objects.filter(activo=True).exclude(estado__in=['PAGADA', 'CERRADA', 'ANULADA']).order_by(
        '-fecha_reclamo'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Reclamación ...'}), label="Reclamación Asociada")
    factura = forms.ModelChoiceField(queryset=Factura.objects.filter(activo=True, pagada=False).order_by(
        '-fecha_creacion'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Factura Pendiente...'}), label="Factura Asociada")
    documentos_soporte_pago = forms.FileField(validators=[
                                              validate_file_size, validate_file_type], required=False, help_text="Formatos: PDF, JPG, PNG. Max 10MB.")

    fecha_pago = forms.CharField(label="Fecha de Pago", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    fecha_notificacion_pago = forms.CharField(label="Fecha Notificación Pago", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=False)

    monto_pago = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(
        attrs={'step': '0.01', 'required': 'required'}))
    forma_pago = forms.ChoiceField(
        choices=CommonChoices.FORMA_PAGO_RECLAMACION, widget=forms.Select())
    referencia_pago = forms.CharField(max_length=100, required=False, widget=forms.TextInput(
        attrs={'placeholder': 'Nro. Transferencia, Zelle, etc.'}))
    observaciones_pago = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False)
    activo = forms.BooleanField(
        required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'switch'}))
    aplica_igtf_pago = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = Pago
        fields = [
            'activo', 'reclamacion', 'factura', 'fecha_pago', 'monto_pago',
            'forma_pago', 'referencia_pago', 'fecha_notificacion_pago',
            'observaciones_pago', 'documentos_soporte_pago', 'aplica_igtf_pago'
        ]
        exclude = ['fecha_creacion', 'fecha_modificacion', 'primer_nombre',
                   'segundo_nombre', 'primer_apellido', 'segundo_apellido']
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
            'aplica_igtf_pago': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'forma_pago': forms.Select(),
            'observaciones_pago': forms.Textarea(attrs={'rows': 3}),
            'monto_pago': forms.NumberInput(attrs={'step': '0.01', 'required': 'required'}),
            'referencia_pago': forms.TextInput(attrs={'placeholder': 'Nro. Transferencia, Zelle, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_forma_pago(self):
        metodo = self.cleaned_data.get('forma_pago')
        return metodo

    def clean_monto_pago(self):
        monto = self.cleaned_data.get('monto_pago')
        if monto is not None and monto <= Decimal('0.00'):
            raise ValidationError('El monto del pago debe ser positivo.')
        return monto

    def clean(self):
        cleaned_data = super().clean()
        factura = cleaned_data.get('factura')
        reclamacion = cleaned_data.get('reclamacion')
        monto_pago = cleaned_data.get('monto_pago')
        fecha_pago_aware = cleaned_data.get('fecha_pago')
        instance = self.instance
        hoy_aware = django_timezone.now()

        if not factura and not reclamacion:
            raise ValidationError(
                "El pago debe estar asociado a una Factura o a una Reclamación.", code='missing_association')
        if factura and reclamacion:
            raise ValidationError(
                "El pago no puede estar asociado a una Factura y a una Reclamación a la vez.", code='multiple_associations')

        if fecha_pago_aware and fecha_pago_aware > hoy_aware:
            self.add_error(
                'fecha_pago', "La fecha de pago no puede ser futura.")

        if monto_pago:
            TOLERANCE = Decimal('0.01')
            if factura:
                pagos_previos = factura.pagos.filter(activo=True)
                if instance.pk:
                    pagos_previos = pagos_previos.exclude(pk=instance.pk)
                total_pagado_previo = pagos_previos.aggregate(total=Sum('monto_pago'))[
                    'total'] or Decimal('0.00')
                pendiente_factura = (factura.monto or Decimal(
                    '0.00')) - total_pagado_previo
                if monto_pago > pendiente_factura + TOLERANCE:
                    self.add_error('monto_pago', ValidationError(
                        f"El monto (${monto_pago:.2f}) excede el pendiente actual (${pendiente_factura:.2f}) de la Factura {factura.numero_recibo}."))
            elif reclamacion:
                pagos_previos = reclamacion.pagos.filter(activo=True)
                if instance.pk:
                    pagos_previos = pagos_previos.exclude(pk=instance.pk)
                total_pagado_previo = pagos_previos.aggregate(total=Sum('monto_pago'))[
                    'total'] or Decimal('0.00')
                pendiente_reclamacion = (
                    reclamacion.monto_reclamado or Decimal('0.00')) - total_pagado_previo
                if monto_pago > pendiente_reclamacion + TOLERANCE:
                    self.add_error('monto_pago', ValidationError(
                        f"El monto (${monto_pago:.2f}) excede el pendiente actual (${pendiente_reclamacion:.2f}) de la Reclamación #{reclamacion.pk}."))
        return cleaned_data

# ------------------------------
# TarifaForm
# ------------------------------


class TarifaForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = ['fecha_aplicacion']

    fecha_aplicacion = forms.CharField(label="Fecha Aplicación", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    ramo = forms.ChoiceField(choices=CommonChoices.RAMO, widget=forms.Select())
    rango_etario = forms.ChoiceField(
        choices=CommonChoices.RANGO_ETARIO, widget=forms.Select())
    monto_anual = forms.DecimalField(
        max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01'}))
    tipo_fraccionamiento = forms.ChoiceField(
        choices=CommonChoices.FORMA_PAGO, widget=forms.Select())
    comision_intermediario = forms.DecimalField(max_digits=5, decimal_places=2, widget=forms.NumberInput(
        attrs={'step': '0.01', 'min': '0', 'max': '100'}), required=False)
    activo = forms.BooleanField(
        required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'switch'}))

    class Meta:
        model = Tarifa
        fields = ['ramo', 'rango_etario', 'fecha_aplicacion', 'monto_anual',
                  'tipo_fraccionamiento', 'comision_intermediario', 'activo']
        exclude = ['fecha_creacion', 'fecha_modificacion', 'primer_nombre',
                   'segundo_nombre', 'primer_apellido', 'segundo_apellido']
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'switch'}),
            'monto_anual': forms.NumberInput(attrs={'step': '0.01'}),
            'comision_intermediario': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Formatear el valor inicial para los campos de fecha CharField
        if self.instance and self.instance.pk:
            if 'fecha_aplicacion' in self.fields and isinstance(self.instance.fecha_aplicacion, date):
                self.initial['fecha_aplicacion'] = self.instance.fecha_aplicacion.strftime(
                    '%d/%m/%Y')

    def clean_monto_anual(self):
        monto = self.cleaned_data.get('monto_anual')
        if monto is not None and monto <= Decimal('0.00'):
            raise ValidationError('El monto anual debe ser positivo.')
        return monto

    def clean_comision_intermediario(self):
        comision = self.cleaned_data.get('comision_intermediario')
        if comision is not None:
            if not (Decimal('0.00') <= comision <= Decimal('100.00')):
                raise ValidationError(
                    'La comisión debe estar entre 0.00 y 100.00.')
        return comision

    def clean_tipo_fraccionamiento(self):
        tipo = self.cleaned_data.get('tipo_fraccionamiento')
        valid_keys = [key for key, _ in CommonChoices.FORMA_PAGO if key]
        if tipo and tipo not in valid_keys:
            raise ValidationError(
                f"Seleccione una opción válida. '{tipo}' no es permitida.")
        return tipo

    def clean(self):
        cleaned_data = super().clean()
        fecha_aplicacion_aware = cleaned_data.get('fecha_aplicacion')
        if fecha_aplicacion_aware and fecha_aplicacion_aware > django_timezone.now():
            self.add_error('fecha_aplicacion',
                           "La fecha de aplicación no puede ser futura.")
        return cleaned_data

# ------------------------------
# FacturaForm
# ------------------------------


class FacturaForm(AwareDateInputMixinVE, BaseModelForm):
    aware_date_fields = ['vigencia_recibo_desde', 'vigencia_recibo_hasta']

    contrato_individual = forms.ModelChoiceField(queryset=ContratoIndividual.objects.filter(activo=True).select_related('afiliado').order_by(
        '-fecha_emision'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Contrato Individual...'}), label="Contrato Individual")
    contrato_colectivo = forms.ModelChoiceField(queryset=ContratoColectivo.objects.filter(activo=True).order_by(
        '-fecha_emision'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Contrato Colectivo...'}), label="Contrato Colectivo")
    intermediario = forms.ModelChoiceField(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), required=False, widget=Select2Widget(attrs={'data-placeholder': 'Buscar Intermediario...'}), label="Intermediario")

    vigencia_recibo_desde = forms.CharField(label="Vigencia Recibo Desde", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)
    vigencia_recibo_hasta = forms.CharField(label="Vigencia Recibo Hasta", widget=forms.TextInput(
        attrs={'placeholder': PLACEHOLDER_DATE_STRICT, 'class': 'form-control'}), required=True)

    estatus_factura = forms.ChoiceField(
        choices=CommonChoices.ESTATUS_FACTURA, widget=forms.Select())
    monto = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(
        attrs={'step': '0.01', 'min': '0.01'}))
    dias_periodo_cobro = forms.IntegerField(
        min_value=1, widget=forms.NumberInput(attrs={'min': '1'}), required=False)
    estatus_emision = forms.ChoiceField(
        choices=CommonChoices.EMISION_RECIBO, widget=forms.Select())
    aplica_igtf = forms.BooleanField(
        required=False, widget=forms.CheckboxInput())
    observaciones = forms.CharField(widget=forms.Textarea(
        attrs={'rows': 3, 'placeholder': 'Añadir notas...'}), required=False)
    activo = forms.BooleanField(
        required=False, initial=True, widget=forms.CheckboxInput())

    class Meta:
        model = Factura
        fields = [
            'activo', 'estatus_factura', 'contrato_individual', 'contrato_colectivo',
            'intermediario', 'vigencia_recibo_desde', 'vigencia_recibo_hasta', 'monto',
            'dias_periodo_cobro', 'estatus_emision', 'aplica_igtf', 'observaciones',
        ]
        exclude = ['numero_recibo', 'relacion_ingreso', 'monto_pendiente', 'pagada', 'recibos_pendientes_cache',
                   'fecha_creacion', 'fecha_modificacion', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido']
        widgets = {
            'activo': forms.CheckboxInput(), 'aplica_igtf': forms.CheckboxInput(),
            'estatus_factura': forms.Select(), 'estatus_emision': forms.Select(),
            'monto': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'dias_periodo_cobro': forms.NumberInput(attrs={'min': '1'}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'observaciones' in self.fields:
            self.fields['observaciones'].widget.attrs.setdefault(
                'placeholder', 'Añadir notas...')

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is not None and monto <= Decimal('0.00'):
            raise ValidationError('El monto debe ser positivo.')
        return monto

    def clean_dias_periodo_cobro(self):
        dias = self.cleaned_data.get('dias_periodo_cobro')
        if dias is not None and dias < 1:
            raise ValidationError('Los días del período deben ser al menos 1.')
        return dias

    def clean(self):
        cleaned_data = super().clean()
        contrato_individual = cleaned_data.get('contrato_individual')
        contrato_colectivo = cleaned_data.get('contrato_colectivo')
        f_desde_aware = cleaned_data.get('vigencia_recibo_desde')
        f_hasta_aware = cleaned_data.get('vigencia_recibo_hasta')

        if not contrato_individual and not contrato_colectivo:
            raise forms.ValidationError(
                "Debe seleccionar un Contrato Individual o un Contrato Colectivo.")
        if contrato_individual and contrato_colectivo:
            raise forms.ValidationError(
                "Solo puede seleccionar un tipo de contrato.")

        if f_desde_aware and f_hasta_aware and f_hasta_aware < f_desde_aware:
            self.add_error('vigencia_recibo_hasta',
                           'Fecha "Hasta" no puede ser anterior a "Desde".')

        contrato = contrato_individual or contrato_colectivo
        if contrato and f_desde_aware and f_hasta_aware:
            # Asumir que fecha_inicio_vigencia y fecha_fin_vigencia en el contrato son DateField o DateTimeField aware
            fecha_inicio_contrato_date = contrato.fecha_inicio_vigencia
            if isinstance(fecha_inicio_contrato_date, datetime):  # Si es DateTimeField (aware)
                fecha_inicio_contrato_date = fecha_inicio_contrato_date.date()

            fecha_fin_contrato_date = contrato.fecha_fin_vigencia
            if isinstance(fecha_fin_contrato_date, datetime):  # Si es DateTimeField (aware)
                fecha_fin_contrato_date = fecha_fin_contrato_date.date()

            if fecha_inicio_contrato_date and f_desde_aware.date() < fecha_inicio_contrato_date:
                self.add_error(
                    'vigencia_recibo_desde', "Vigencia recibo no puede iniciar antes que contrato.")
            if fecha_fin_contrato_date and f_hasta_aware.date() > fecha_fin_contrato_date:
                self.add_error(
                    'vigencia_recibo_hasta', "Vigencia recibo no puede terminar después que contrato.")
        return cleaned_data

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
