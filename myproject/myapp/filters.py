# filters.py
import django_filters
from django_filters import (
    FilterSet, CharFilter, BooleanFilter, DateFilter, DateFromToRangeFilter,
    ModelChoiceFilter, ModelMultipleChoiceFilter, NumberFilter,
    ChoiceFilter, NumericRangeFilter
)
from django_filters.widgets import RangeWidget, DateRangeWidget
from django import forms
from django_select2.forms import Select2Widget, Select2MultipleWidget

from django.utils import timezone as django_timezone
from datetime import date, timedelta, datetime
from django.db.models import Q
from django.apps import apps
import logging

from .models import (
    ContratoIndividual, AfiliadoIndividual, ContratoColectivo, AfiliadoColectivo,
    Factura, AuditoriaSistema, Pago,
    Reclamacion, Tarifa, Intermediario, Usuario, LicenseInfo, Notificacion, RegistroComision
)
from .commons import CommonChoices

logger = logging.getLogger(__name__)


def get_modelo_choices():
    choices = []
    app_name = 'myapp'
    try:
        app_models = apps.get_app_config(app_name).get_models()
        for model in app_models:
            choices.append(
                (model._meta.db_table, model._meta.verbose_name.capitalize()))
        choices.sort(key=lambda x: x[1])
    except LookupError:
        logger.error(
            f"La aplicación '{app_name}' no fue encontrada para get_modelo_choices en filters.py.")
    except Exception as e:
        logger.error(f"Error generando get_modelo_choices en filters.py: {e}")
    return choices


date_range_widget = DateRangeWidget(
    attrs={'type': 'date', 'class': 'form-control'})
numeric_range_widget = RangeWidget(
    attrs={'type': 'number', 'step': 'any', 'class': 'form-control'})


class AwareDateTimeFromToRangeFilter(django_filters.DateFromToRangeFilter):
    def filter(self, qs, value):
        if value:
            params = {}
            if value.start:
                naive_dt_desde = datetime.combine(
                    value.start, datetime.min.time())
                aware_dt_desde = django_timezone.make_aware(naive_dt_desde)
                params[f'{self.field_name}__gte'] = aware_dt_desde
            if value.stop:
                naive_dt_hasta = datetime.combine(
                    value.stop, datetime.max.time())
                aware_dt_hasta = django_timezone.make_aware(naive_dt_hasta)
                params[f'{self.field_name}__lte'] = aware_dt_hasta
            if params:
                return qs.filter(**params)
        return qs


class ContratoIndividualFilter(django_filters.FilterSet):
    primer_nombre = django_filters.CharFilter(
        lookup_expr='icontains', label="Primer Nombre (Afiliado)")
    primer_apellido = django_filters.CharFilter(
        lookup_expr='icontains', label="Primer Apellido (Afiliado)")
    ramo = ChoiceFilter(choices=CommonChoices.RAMO,
                        label="Ramo", widget=Select2Widget)
    forma_pago = ChoiceFilter(
        choices=CommonChoices.FORMA_PAGO, label="Forma de Pago", widget=Select2Widget)
    estatus = ChoiceFilter(choices=CommonChoices.ESTADOS_VIGENCIA,
                           label="Estatus Vigencia", widget=Select2Widget)
    numero_contrato = CharFilter(lookup_expr='icontains', label="N° Contrato")
    numero_poliza = CharFilter(lookup_expr='icontains', label="N° Póliza")
    certificado = CharFilter(lookup_expr='icontains', label="Certificado")
    intermediario = ModelChoiceFilter(queryset=Intermediario.objects.filter(
        activo=True).order_by('nombre_completo'), label="Intermediario", widget=Select2Widget)
    tarifa_aplicada = ModelChoiceFilter(queryset=Tarifa.objects.filter(activo=True).order_by(
        'ramo', 'rango_etario', '-fecha_aplicacion'), label="Tarifa Aplicada", widget=Select2Widget)
    afiliado = ModelChoiceFilter(queryset=AfiliadoIndividual.objects.filter(activo=True).order_by(
        'primer_apellido', 'primer_nombre'), label="Afiliado Individual", widget=Select2Widget)
    contratante_cedula = CharFilter(
        lookup_expr='icontains', label="Cédula/RIF Contratante")
    contratante_nombre = CharFilter(
        lookup_expr='icontains', label="Nombre Contratante")
    plan_contratado = CharFilter(
        lookup_expr='icontains', label="Plan Contratado")
    numero_recibo = CharFilter(lookup_expr='icontains', label="N° Recibo")
    estatus_emision_recibo = ChoiceFilter(
        choices=CommonChoices.EMISION_RECIBO, label="Estatus Emisión Recibo", widget=Select2Widget)
    activo = BooleanFilter(field_name='activo', label="Contrato Activo")
    fecha_emision_range = AwareDateTimeFromToRangeFilter(
        field_name='fecha_emision', widget=date_range_widget, label="Emitido Entre")
    fecha_vigencia_range = DateFromToRangeFilter(
        field_name='fecha_inicio_vigencia', widget=date_range_widget, label="Vigente Entre (Inicio)")
    fecha_fin_vigencia_range = DateFromToRangeFilter(
        field_name='fecha_fin_vigencia', widget=date_range_widget, label="Vigente Entre (Fin)")
    monto_total_range = NumericRangeFilter(
        field_name='monto_total', widget=numeric_range_widget, label="Monto Total Entre")

    class Meta:
        model = ContratoIndividual
        fields = ['primer_nombre', 'primer_apellido', 'ramo', 'forma_pago', 'estatus', 'numero_contrato', 'numero_poliza', 'intermediario', 'tarifa_aplicada', 'afiliado', 'contratante_cedula', 'contratante_nombre',
                  'plan_contratado', 'numero_recibo', 'estatus_emision_recibo', 'activo', 'fecha_emision_range', 'fecha_vigencia_range', 'fecha_fin_vigencia_range', 'monto_total_range', 'certificado']


class AfiliadoIndividualFilter(django_filters.FilterSet):
    primer_nombre = CharFilter(lookup_expr='icontains', label="Primer Nombre")
    primer_apellido = CharFilter(
        lookup_expr='icontains', label="Primer Apellido")
    cedula = CharFilter(lookup_expr='icontains', label="Cédula")
    tipo_identificacion = ChoiceFilter(
        choices=CommonChoices.TIPO_IDENTIFICACION, label="Tipo ID", widget=Select2Widget)
    estado_civil = ChoiceFilter(
        choices=CommonChoices.ESTADO_CIVIL, label="Estado Civil", widget=Select2Widget)
    sexo = ChoiceFilter(choices=CommonChoices.SEXO,
                        label="Sexo", widget=Select2Widget)
    parentesco = ChoiceFilter(
        choices=CommonChoices.PARENTESCO, label="Parentesco", widget=Select2Widget)
    fecha_nacimiento_range = DateFromToRangeFilter(
        field_name='fecha_nacimiento', widget=date_range_widget, label="Nacido Entre")
    nacionalidad = CharFilter(lookup_expr='icontains', label="Nacionalidad")
    estado = ChoiceFilter(choices=CommonChoices.ESTADOS_VE,
                          label="Estado (VE)", widget=Select2Widget)
    municipio = CharFilter(lookup_expr='icontains', label="Municipio")
    ciudad = CharFilter(lookup_expr='icontains', label="Ciudad")
    fecha_ingreso_range = DateFromToRangeFilter(
        field_name='fecha_ingreso', widget=date_range_widget, label="Ingresó Entre")
    email = CharFilter(lookup_expr='icontains', label="Email")
    intermediario = ModelChoiceFilter(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), field_name='intermediario', label="Intermediario Asignado", widget=Select2Widget)
    activo = django_filters.ChoiceFilter(field_name='activo', label="Estado (Activo/Inactivo)", choices=[
                                         ('', 'Todos'), (True, 'Sí'), (False, 'No')], empty_label='Todos', widget=forms.Select)
    edad = NumberFilter(method='filter_by_edad', label="Edad (años)")
    edad_range = NumericRangeFilter(
        method='filter_by_edad_range', widget=numeric_range_widget, label="Edad Entre")

    class Meta:
        model = AfiliadoIndividual
        fields = ['primer_nombre', 'primer_apellido', 'cedula', 'tipo_identificacion', 'estado_civil', 'sexo', 'parentesco', 'nacionalidad',
                  'estado', 'municipio', 'ciudad', 'email', 'intermediario', 'activo', 'fecha_nacimiento_range', 'fecha_ingreso_range', 'edad', 'edad_range']

    def filter_by_edad(self, queryset, name, value):
        if value:
            try:
                edad_exacta = int(value)
                today = date.today()
                fecha_max = today.replace(year=today.year - edad_exacta)
                fecha_min = today.replace(
                    year=today.year - edad_exacta - 1) + timedelta(days=1)
                return queryset.filter(fecha_nacimiento__range=(fecha_min, fecha_max))
            except (ValueError, TypeError):
                return queryset
        return queryset

    def filter_by_edad_range(self, queryset, name, value):
        if value and (value.start is not None or value.stop is not None):
            today = date.today()
            q_filter = Q()
            if value.start is not None:
                try:
                    edad_min = int(value.start)
                    fecha_max = today.replace(year=today.year - edad_min)
                    q_filter &= Q(fecha_nacimiento__lte=fecha_max)
                except (ValueError, TypeError):
                    pass
            if value.stop is not None:
                try:
                    edad_max = int(value.stop)
                    fecha_min = today.replace(
                        year=today.year - edad_max - 1) + timedelta(days=1)
                    q_filter &= Q(fecha_nacimiento__gte=fecha_min)
                except (ValueError, TypeError):
                    pass
            return queryset.filter(q_filter)
        return queryset

# ----------------------------------------------------
# AfiliadoColectivoFilter (AHORA SÍ ESTÁ DEFINIDO)
# ----------------------------------------------------


class AfiliadoColectivoFilter(django_filters.FilterSet):
    razon_social = CharFilter(lookup_expr='icontains', label="Razón Social")
    rif = CharFilter(lookup_expr='icontains', label="RIF")
    tipo_empresa = ChoiceFilter(
        choices=CommonChoices.TIPO_EMPRESA, label="Tipo Empresa", widget=Select2Widget)
    estado = ChoiceFilter(choices=CommonChoices.ESTADOS_VE,
                          label="Estado (VE)", widget=Select2Widget)
    municipio = CharFilter(lookup_expr='icontains', label="Municipio")
    ciudad = CharFilter(lookup_expr='icontains', label="Ciudad")
    email_contacto = CharFilter(
        lookup_expr='icontains', label="Email Contacto")
    intermediario = ModelChoiceFilter(
        queryset=Intermediario.objects.filter(
            activo=True).order_by('nombre_completo'),
        field_name='intermediario',
        label="Intermediario Asignado",
        widget=Select2Widget
    )
    activo = BooleanFilter(field_name='activo', label="Afiliado Activo")

    class Meta:
        model = AfiliadoColectivo
        fields = [
            'razon_social', 'rif', 'tipo_empresa', 'estado', 'municipio',
            'ciudad', 'email_contacto', 'intermediario', 'activo'
        ]
# ----------------------------------------------------


class ContratoColectivoFilter(django_filters.FilterSet):
    ramo = ChoiceFilter(choices=CommonChoices.RAMO,
                        label="Ramo", widget=Select2Widget)
    forma_pago = ChoiceFilter(
        choices=CommonChoices.FORMA_PAGO, label="Forma de Pago", widget=Select2Widget)
    estatus = ChoiceFilter(choices=CommonChoices.ESTADOS_VIGENCIA,
                           label="Estatus Vigencia", widget=Select2Widget)
    numero_contrato = CharFilter(lookup_expr='icontains', label="N° Contrato")
    numero_poliza = CharFilter(lookup_expr='icontains', label="N° Póliza")
    intermediario = ModelChoiceFilter(queryset=Intermediario.objects.filter(
        activo=True).order_by('nombre_completo'), label="Intermediario", widget=Select2Widget)
    certificado = CharFilter(lookup_expr='icontains', label="Certificado")
    tarifa_aplicada = ModelChoiceFilter(queryset=Tarifa.objects.filter(activo=True).order_by(
        'ramo', 'rango_etario', '-fecha_aplicacion'), label="Tarifa Aplicada", widget=Select2Widget)
    tipo_empresa = ChoiceFilter(
        choices=CommonChoices.TIPO_EMPRESA, label="Tipo Empresa", widget=Select2Widget)
    razon_social = CharFilter(lookup_expr='icontains', label="Razón Social")
    rif = CharFilter(lookup_expr='icontains', label="RIF")
    plan_contratado = CharFilter(
        lookup_expr='icontains', label="Plan Contratado")
    numero_recibo = CharFilter(lookup_expr='icontains', label="N° Recibo")
    activo = BooleanFilter(field_name='activo', label="Contrato Activo")
    afiliados_colectivos = ModelMultipleChoiceFilter(queryset=AfiliadoColectivo.objects.filter(
        activo=True).order_by('razon_social'), label="Afiliados Colectivos", widget=Select2MultipleWidget)
    fecha_emision_range = AwareDateTimeFromToRangeFilter(
        field_name='fecha_emision', widget=date_range_widget, label="Emitido Entre")
    fecha_vigencia_range = DateFromToRangeFilter(
        field_name='fecha_inicio_vigencia', widget=date_range_widget, label="Vigente Entre (Inicio)")
    fecha_fin_vigencia_range = DateFromToRangeFilter(
        field_name='fecha_fin_vigencia', widget=date_range_widget, label="Vigente Entre (Fin)")
    monto_total_range = NumericRangeFilter(
        field_name='monto_total', widget=numeric_range_widget, label="Monto Total Entre")
    cantidad_empleados_range = NumericRangeFilter(
        field_name='cantidad_empleados', widget=numeric_range_widget, label="N° Empleados Entre")

    class Meta:
        model = ContratoColectivo
        fields = ['ramo', 'forma_pago', 'estatus', 'numero_contrato', 'numero_poliza', 'intermediario', 'certificado', 'tarifa_aplicada', 'tipo_empresa', 'razon_social', 'rif', 'plan_contratado',
                  'numero_recibo', 'activo', 'afiliados_colectivos', 'fecha_emision_range', 'fecha_vigencia_range', 'fecha_fin_vigencia_range', 'monto_total_range', 'cantidad_empleados_range']


class FacturaFilter(django_filters.FilterSet):
    estatus_factura = ChoiceFilter(
        choices=CommonChoices.ESTATUS_FACTURA, label="Estatus Factura", widget=Select2Widget)
    contrato_individual = ModelChoiceFilter(queryset=ContratoIndividual.objects.filter(
        activo=True).order_by('numero_contrato'), label="Contrato Individual", widget=Select2Widget)
    contrato_colectivo = ModelChoiceFilter(queryset=ContratoColectivo.objects.filter(
        activo=True).order_by('numero_contrato'), label="Contrato Colectivo", widget=Select2Widget)
    ramo = ChoiceFilter(choices=CommonChoices.RAMO, method='filter_by_ramo',
                        label="Ramo (Contrato)", widget=Select2Widget)
    vigencia_recibo_desde_range = DateFromToRangeFilter(
        field_name='vigencia_recibo_desde', widget=date_range_widget, label="Vigencia Recibo Desde")
    vigencia_recibo_hasta_range = DateFromToRangeFilter(
        field_name='vigencia_recibo_hasta', widget=date_range_widget, label="Vigencia Recibo Hasta")
    intermediario = ModelChoiceFilter(queryset=Intermediario.objects.filter(
        activo=True).order_by('nombre_completo'), label="Intermediario", widget=Select2Widget)
    monto_range = NumericRangeFilter(
        field_name='monto', widget=numeric_range_widget, label="Monto Entre")
    monto_pendiente_range = NumericRangeFilter(
        field_name='monto_pendiente', widget=numeric_range_widget, label="Monto Pendiente Entre")
    numero_recibo = CharFilter(lookup_expr='icontains', label="N° Recibo")
    relacion_ingreso = CharFilter(
        lookup_expr='icontains', label="N° Relación Ingreso")
    estatus_emision = ChoiceFilter(
        choices=CommonChoices.EMISION_RECIBO, label="Estatus Emisión", widget=Select2Widget)
    pagada = BooleanFilter(field_name='pagada', label="Pagada")
    aplica_igtf = BooleanFilter(field_name='aplica_igtf', label="Aplica IGTF")
    activo = BooleanFilter(field_name='activo', label="Factura Activa")

    def filter_by_ramo(self, queryset, name, value):
        if value:
            return queryset.filter(Q(contrato_individual__ramo=value) | Q(contrato_colectivo__ramo=value))
        return queryset

    class Meta:
        model = Factura
        fields = ['estatus_factura', 'contrato_individual', 'contrato_colectivo', 'ramo', 'vigencia_recibo_desde_range', 'vigencia_recibo_hasta_range',
                  'intermediario', 'monto_range', 'monto_pendiente_range', 'numero_recibo', 'relacion_ingreso', 'estatus_emision', 'pagada', 'aplica_igtf', 'activo']


class AuditoriaSistemaFilter(django_filters.FilterSet):
    tipo_accion = ChoiceFilter(
        choices=CommonChoices.TIPO_ACCION, label="Tipo Acción", widget=Select2Widget)
    resultado_accion = ChoiceFilter(
        choices=CommonChoices.RESULTADO_ACCION, label="Resultado", widget=Select2Widget)
    usuario = ModelChoiceFilter(queryset=Usuario.objects.filter(
        activo=True).order_by('email'), label="Usuario", widget=Select2Widget)
    tabla_afectada = ChoiceFilter(
        choices=[], label="Tabla Afectada", widget=Select2Widget, empty_label="Todas")
    registro_id_afectado = NumberFilter(label="ID Registro Afectado")
    detalle_accion = CharFilter(
        lookup_expr='icontains', label="Detalle Acción")
    direccion_ip = CharFilter(lookup_expr='icontains', label="Dirección IP")
    tiempo_inicio_range = AwareDateTimeFromToRangeFilter(
        field_name='tiempo_inicio', widget=date_range_widget, label="Ocurrido Entre")

    class Meta:
        model = AuditoriaSistema
        fields = ['tipo_accion', 'resultado_accion', 'usuario', 'tabla_afectada',
                  'registro_id_afectado', 'detalle_accion', 'direccion_ip', 'tiempo_inicio_range']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'tabla_afectada' in self.filters:
            try:
                self.filters['tabla_afectada'].extra['choices'] = [
                    ('', 'Todas')] + get_modelo_choices()
            except Exception as e:
                logger.warning(
                    f"Error poblando choices para tabla_afectada en AuditoriaSistemaFilter: {e}")
                self.filters['tabla_afectada'].extra['choices'] = [
                    ('', 'Todas')]


class PagoFilter(django_filters.FilterSet):
    forma_pago = ChoiceFilter(choices=CommonChoices.FORMA_PAGO_RECLAMACION,
                              label="Forma de Pago", widget=Select2Widget)
    reclamacion = ModelChoiceFilter(queryset=Reclamacion.objects.filter(
        activo=True).order_by('-fecha_reclamo'), label="Reclamación", widget=Select2Widget)
    factura = ModelChoiceFilter(queryset=Factura.objects.filter(
        activo=True).order_by('-fecha_creacion'), label="Factura", widget=Select2Widget)
    fecha_pago_range = DateFromToRangeFilter(
        field_name='fecha_pago', widget=date_range_widget, label="Pagado Entre")
    monto_pago_range = NumericRangeFilter(
        field_name='monto_pago', widget=numeric_range_widget, label="Monto Entre")
    referencia_pago = CharFilter(lookup_expr='icontains', label="Referencia")
    aplica_igtf_pago = BooleanFilter(
        field_name='aplica_igtf_pago', label="Sujeto a IGTF")
    fecha_notificacion_pago_range = DateFromToRangeFilter(
        field_name='fecha_notificacion_pago', widget=date_range_widget, label="Notificado Entre")
    activo = BooleanFilter(field_name='activo', label="Pago Activo")

    class Meta:
        model = Pago
        fields = ['forma_pago', 'reclamacion', 'factura', 'fecha_pago_range', 'monto_pago_range',
                  'referencia_pago', 'aplica_igtf_pago', 'fecha_notificacion_pago_range', 'activo']


class ReclamacionFilter(django_filters.FilterSet):
    tipo_reclamacion = ChoiceFilter(
        choices=CommonChoices.TIPO_RECLAMACION, label="Tipo", widget=Select2Widget)
    diagnostico_principal = ChoiceFilter(
        choices=CommonChoices.DIAGNOSTICOS, label="Diagnóstico", widget=Select2Widget)
    estado = ChoiceFilter(
        choices=CommonChoices.ESTADO_RECLAMACION, label="Estado", widget=Select2Widget)
    contrato_individual = ModelChoiceFilter(queryset=ContratoIndividual.objects.filter(
        activo=True).order_by('numero_contrato'), label="Contrato Individual", widget=Select2Widget)
    contrato_colectivo = ModelChoiceFilter(queryset=ContratoColectivo.objects.filter(
        activo=True).order_by('numero_contrato'), label="Contrato Colectivo", widget=Select2Widget)
    fecha_reclamo_range = DateFromToRangeFilter(
        field_name='fecha_reclamo', widget=date_range_widget, label="Reclamado Entre")
    fecha_cierre_reclamo_range = DateFromToRangeFilter(
        field_name='fecha_cierre_reclamo', widget=date_range_widget, label="Cerrado Entre")
    usuario_asignado = ModelChoiceFilter(queryset=Usuario.objects.filter(
        activo=True).order_by('email'), label="Usuario Asignado", widget=Select2Widget)
    monto_reclamado_range = NumericRangeFilter(
        field_name='monto_reclamado', widget=numeric_range_widget, label="Monto Reclamado Entre")
    activo = BooleanFilter(field_name='activo', label="Reclamación Activa")

    class Meta:
        model = Reclamacion
        fields = ['tipo_reclamacion', 'diagnostico_principal', 'estado', 'contrato_individual', 'contrato_colectivo',
                  'fecha_reclamo_range', 'fecha_cierre_reclamo_range', 'usuario_asignado', 'monto_reclamado_range', 'activo']


class TarifaFilter(django_filters.FilterSet):
    rango_etario = ChoiceFilter(
        choices=CommonChoices.RANGO_ETARIO, label="Rango Etario", widget=Select2Widget)
    ramo = ChoiceFilter(choices=CommonChoices.RAMO,
                        label="Ramo", widget=Select2Widget)
    fecha_aplicacion_range = DateFromToRangeFilter(
        field_name='fecha_aplicacion', widget=date_range_widget, label="Aplicable Entre")
    monto_anual_range = NumericRangeFilter(
        field_name='monto_anual', widget=numeric_range_widget, label="Monto Anual Entre")
    tipo_fraccionamiento = ChoiceFilter(
        choices=CommonChoices.FORMA_PAGO, label="Tipo Fraccionamiento", widget=Select2Widget)

    class Meta:
        model = Tarifa
        fields = ['rango_etario', 'ramo', 'tipo_fraccionamiento', 'activo',
                  'fecha_aplicacion_range', 'monto_anual_range']


class IntermediarioFilter(django_filters.FilterSet):
    codigo = CharFilter(lookup_expr='icontains', label="Código")
    nombre_completo = CharFilter(
        lookup_expr='icontains', label="Nombre Completo")
    rif = CharFilter(lookup_expr='icontains', label="RIF")
    email_contacto = CharFilter(
        lookup_expr='icontains', label="Email Contacto")
    porcentaje_comision_range = NumericRangeFilter(
        field_name='porcentaje_comision', widget=numeric_range_widget, label="Comisión (%) Entre")
    intermediario_relacionado = ModelChoiceFilter(queryset=Intermediario.objects.filter(
        activo=True).order_by('nombre_completo'), label="Intermediario Relacionado", widget=Select2Widget)
    activo = BooleanFilter(field_name='activo', label="Intermediario Activo")

    class Meta:
        model = Intermediario
        fields = ['codigo', 'nombre_completo', 'rif', 'email_contacto',
                  'porcentaje_comision_range', 'intermediario_relacionado', 'activo']


class UsuarioFilter(django_filters.FilterSet):
    primer_nombre = CharFilter(lookup_expr='icontains', label="Primer Nombre")
    primer_apellido = CharFilter(
        lookup_expr='icontains', label="Primer Apellido")
    email = CharFilter(lookup_expr='icontains', label="Email")
    username = CharFilter(lookup_expr='icontains', label="Username (Interno)")
    tipo_usuario = ChoiceFilter(
        choices=CommonChoices.TIPO_USUARIO, label="Tipo Usuario", widget=Select2Widget)
    fecha_nacimiento_range = DateFromToRangeFilter(
        field_name='fecha_nacimiento', widget=date_range_widget, label="Nacido Entre")
    departamento = ChoiceFilter(
        choices=CommonChoices.DEPARTAMENTO, label="Departamento", widget=Select2Widget)
    telefono = CharFilter(lookup_expr='icontains', label="Teléfono")
    intermediario = ModelChoiceFilter(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), label="Intermediario Asociado", widget=Select2Widget)
    nivel_acceso = ChoiceFilter(
        choices=CommonChoices.NIVEL_ACCESO, label="Nivel Acceso", widget=Select2Widget)
    is_active = BooleanFilter(field_name='activo', label="Cuenta Activa")
    is_staff = BooleanFilter(field_name='is_staff', label="Es Staff (Admin)")
    is_superuser = BooleanFilter(
        field_name='is_superuser', label="Es Superuser")
    date_joined_range = AwareDateTimeFromToRangeFilter(
        field_name='date_joined', widget=date_range_widget, label="Registrado Entre")
    last_login_range = AwareDateTimeFromToRangeFilter(
        field_name='last_login', widget=date_range_widget, label="Último Login Entre")

    class Meta:
        model = Usuario
        fields = ['primer_nombre', 'primer_apellido', 'email', 'username', 'tipo_usuario', 'departamento', 'telefono', 'intermediario',
                  'nivel_acceso', 'is_active', 'is_staff', 'is_superuser', 'fecha_nacimiento_range', 'date_joined_range', 'last_login_range']


class RegistroComisionFilter(django_filters.FilterSet):
    intermediario = django_filters.ModelChoiceFilter(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), label="Intermediario Beneficiario", widget=Select2Widget(attrs={'data-placeholder': 'Intermediario...'}), empty_label="Todos")
    tipo_comision = django_filters.ChoiceFilter(choices=RegistroComision.TIPO_COMISION_CHOICES, label="Tipo de Comisión", widget=Select2Widget(
        attrs={'data-placeholder': 'Tipo...'}), empty_label="Todos")
    estatus_pago_comision = django_filters.ChoiceFilter(choices=RegistroComision.ESTATUS_PAGO_CHOICES, label="Estado de Pago", widget=Select2Widget(
        attrs={'data-placeholder': 'Estado...'}), empty_label="Todos")
    intermediario_vendedor = django_filters.ModelChoiceFilter(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), label="Intermediario Vendedor (Override)", widget=Select2Widget(attrs={'data-placeholder': 'Vendedor...'}), empty_label="Todos", required=False)
    usuario_que_liquido = django_filters.ModelChoiceFilter(queryset=Usuario.objects.filter(is_active=True).order_by(
        'username'), label="Liquidada por Usuario", widget=Select2Widget(attrs={'data-placeholder': 'Usuario...'}), empty_label="Todos", required=False)
    fecha_calculo_range = AwareDateTimeFromToRangeFilter(
        field_name='fecha_calculo', widget=date_range_widget, label='F. Cálculo (Rango)')
    fecha_pago_a_intermediario_range = DateFromToRangeFilter(
        field_name='fecha_pago_a_intermediario', widget=date_range_widget, label='F. Pago Intermediario (Rango)')

    class Meta:
        model = RegistroComision
        fields = ['intermediario', 'tipo_comision', 'estatus_pago_comision', 'intermediario_vendedor',
                  'usuario_que_liquido', 'fecha_calculo_range', 'fecha_pago_a_intermediario_range']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.form.fields.items():
            if isinstance(field.widget, (Select2Widget, Select2MultipleWidget)):
                if not hasattr(field, 'empty_label') or field.empty_label is not None:
                    field.empty_label = "Todos"
                current_class = field.widget.attrs.get('class', '')
                if 'form-control' not in current_class and 'form-select' not in current_class:
                    field.widget.attrs['class'] = f'{current_class} form-control select2-field'.strip(
                    )
            elif isinstance(field.widget, (forms.TextInput, forms.DateInput, forms.Select, RangeWidget)):
                current_class = field.widget.attrs.get('class', '')
                if 'form-control' not in current_class and 'form-select' not in current_class:
                    field.widget.attrs['class'] = f'{current_class} form-control'.strip()


class HistorialComisionFilter(django_filters.FilterSet):
    intermediario = django_filters.ModelChoiceFilter(queryset=Intermediario.objects.filter(activo=True).order_by(
        'nombre_completo'), label="Intermediario Beneficiario", widget=Select2Widget(attrs={'data-placeholder': 'Intermediario...'}), empty_label="Todos")
    tipo_comision = django_filters.ChoiceFilter(choices=[choice for choice in RegistroComision.TIPO_COMISION_CHOICES if choice[0]],
                                                label="Tipo de Comisión", widget=Select2Widget(attrs={'data-placeholder': 'Tipo...'}), empty_label="Todos los Tipos")
    usuario_que_liquido = django_filters.ModelChoiceFilter(queryset=Usuario.objects.filter(is_active=True).order_by(
        'username'), label="Liquidada por Usuario", widget=Select2Widget(attrs={'data-placeholder': 'Usuario...'}), empty_label="Todos", required=False)
    fecha_pago_a_intermediario_range = DateFromToRangeFilter(
        field_name='fecha_pago_a_intermediario', widget=date_range_widget, label='Fecha Pago (Rango)')
    order_by = django_filters.OrderingFilter(fields=(('fecha_pago_a_intermediario', 'fecha_pago'), (
        'monto_comision', 'monto'), ('intermediario__nombre_completo', 'intermediario')))

    class Meta:
        model = RegistroComision
        fields = ['intermediario', 'tipo_comision',
                  'usuario_que_liquido', 'fecha_pago_a_intermediario_range']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.form.fields.items():
            if isinstance(field.widget, (Select2Widget, Select2MultipleWidget)):
                if not hasattr(field, 'empty_label') or field.empty_label is not None:
                    field.empty_label = "Todos"
                current_class = field.widget.attrs.get('class', '')
                if 'form-control' not in current_class and 'form-select' not in current_class:
                    field.widget.attrs['class'] = f'{current_class} form-control select2-field'.strip(
                    )
            elif isinstance(field.widget, (forms.TextInput, forms.DateInput, forms.Select, RangeWidget)):
                current_class = field.widget.attrs.get('class', '')
                if 'form-control' not in current_class and 'form-select' not in current_class:
                    field.widget.attrs['class'] = f'{current_class} form-control'.strip()
