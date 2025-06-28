# myapp/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

# Importa todos tus modelos
from .models import (
    LicenseInfo, Notificacion, Usuario, AfiliadoIndividual, AfiliadoColectivo,
    ContratoIndividual, ContratoColectivo, Intermediario, Factura,
    AuditoriaSistema, Reclamacion, Pago, RegistroComision, Tarifa
)

# -----------------------------------------------------------------------------
# INLINES: Para mostrar modelos relacionados dentro de otros
# -----------------------------------------------------------------------------


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0
    fields = ('fecha_pago', 'monto_pago', 'forma_pago',
              'referencia_pago', 'activo')
    readonly_fields = fields
    can_delete = False
    show_change_link = True
    def has_add_permission(self, request, obj=None): return False


class FacturaInline(admin.TabularInline):
    model = Factura
    extra = 0
    fields = ('numero_recibo', 'estatus_factura',
              'monto', 'monto_pendiente', 'pagada')
    readonly_fields = fields
    show_change_link = True
    def has_add_permission(self, request, obj=None): return False


class ReclamacionInline(admin.TabularInline):
    model = Reclamacion
    extra = 0
    fields = ('numero_reclamacion', 'estado',
              'monto_reclamado', 'fecha_reclamo')
    readonly_fields = fields
    show_change_link = True
    def has_add_permission(self, request, obj=None): return False

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DEL ADMIN PARA CADA MODELO
# -----------------------------------------------------------------------------

# --- Modelos del Núcleo y Sistema ---


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    list_display = ('email', 'get_full_name', 'tipo_usuario',
                    'nivel_acceso', 'activo', 'is_staff')
    # La búsqueda en nombres/apellidos no funcionará por el cifrado, pero dejamos los campos.
    search_fields = ('email', 'primer_nombre', 'primer_apellido')
    list_filter = ('activo', 'is_staff', 'is_superuser',
                   'nivel_acceso', 'tipo_usuario', 'groups')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información Personal', {'fields': ('primer_nombre', 'segundo_nombre',
         'primer_apellido', 'segundo_apellido', 'fecha_nacimiento', 'telefono', 'direccion')}),
        ('Permisos y Clasificación', {'fields': ('activo', 'is_staff', 'is_superuser',
         'nivel_acceso', 'tipo_usuario', 'departamento', 'groups', 'user_permissions')}),
        ('Asociaciones', {'fields': ('intermediario',)}),
        ('Fechas Importantes', {'fields': (
            'last_login', 'date_joined', 'fecha_creacion', 'fecha_modificacion')}),
    )
    readonly_fields = ('last_login', 'date_joined',
                       'fecha_creacion', 'fecha_modificacion')
    raw_id_fields = ('intermediario',)


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'mensaje_corto',
                    'tipo', 'leida', 'fecha_creacion')
    list_filter = ('leida', 'tipo', 'fecha_creacion')
    # No se puede buscar en 'mensaje' cifrado
    search_fields = ('usuario__email',)
    raw_id_fields = ('usuario',)
    readonly_fields = ('fecha_creacion',)

    def mensaje_corto(self, obj):
        try:
            mensaje_str = str(obj.mensaje)
            return (mensaje_str[:75] + '...') if len(mensaje_str) > 75 else mensaje_str
        except Exception:
            return "[Mensaje Cifrado]"
    mensaje_corto.short_description = 'Mensaje'


@admin.register(LicenseInfo)
class LicenseInfoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'license_key', 'expiry_date',
                    'is_valid', 'last_updated')
    readonly_fields = ('last_updated',)
    def has_add_permission(
        self, request): return not LicenseInfo.objects.exists()

    def has_delete_permission(self, request, obj=None): return False


@admin.register(AuditoriaSistema)
class AuditoriaSistemaAdmin(admin.ModelAdmin):
    list_display = ('tiempo_inicio', 'tipo_accion', 'usuario',
                    'tabla_afectada', 'registro_id_afectado', 'resultado_accion')
    list_filter = ('tipo_accion', 'resultado_accion',
                   'tabla_afectada', 'tiempo_inicio')
    search_fields = ('usuario__email', 'detalle_accion',
                     'direccion_ip', 'registro_id_afectado')
    readonly_fields = [f.name for f in AuditoriaSistema._meta.fields]
    raw_id_fields = ('usuario',)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

# --- Modelos de Afiliados e Intermediarios ---


@admin.register(AfiliadoIndividual)
class AfiliadoIndividualAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'cedula', 'email',
                    'fecha_nacimiento', 'edad', 'activo')
    search_fields = ('cedula', 'email')  # Solo campos no cifrados
    list_filter = ('activo', 'estado_civil', 'sexo', 'estado')
    readonly_fields = ('fecha_creacion', 'fecha_modificacion',
                       'edad', 'nombre_completo')
    fieldsets = (
        ('Información Principal', {'fields': (
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido', 'nombre_completo')}),
        ('Identificación y Demografía', {'fields': (
            'tipo_identificacion', 'cedula', 'fecha_nacimiento', 'edad', 'sexo', 'estado_civil', 'nacionalidad')}),
        ('Contacto y Ubicación', {'fields': ('email', 'telefono_habitacion',
         'direccion_habitacion', 'estado', 'ciudad', 'municipio', 'zona_postal')}),
        ('Datos del Sistema', {'fields': ('activo', 'intermediario',
         'fecha_ingreso', 'fecha_creacion', 'fecha_modificacion')}),
    )
    raw_id_fields = ('intermediario',)


@admin.register(AfiliadoColectivo)
class AfiliadoColectivoAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'rif', 'email_contacto',
                    'tipo_empresa', 'activo')
    search_fields = ('razon_social', 'rif', 'email_contacto')
    list_filter = ('activo', 'tipo_empresa', 'estado')
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')
    fieldsets = (
        ('Información de la Empresa', {
         'fields': ('razon_social', 'rif', 'tipo_empresa')}),
        ('Contacto y Ubicación', {'fields': ('email_contacto', 'telefono_contacto',
         'direccion_comercial', 'estado', 'ciudad', 'municipio', 'zona_postal')}),
        ('Datos del Sistema', {'fields': (
            'activo', 'intermediario', 'fecha_creacion', 'fecha_modificacion')}),
    )
    raw_id_fields = ('intermediario',)


@admin.register(Intermediario)
class IntermediarioAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre_completo', 'rif',
                    'email_contacto', 'porcentaje_comision', 'activo')
    search_fields = ('codigo', 'nombre_completo', 'rif', 'email_contacto')
    list_filter = ('activo',)
    readonly_fields = ('codigo', 'fecha_creacion', 'fecha_modificacion')
    fieldsets = (
        ('Información Principal', {
         'fields': ('codigo', 'nombre_completo', 'rif', 'activo')}),
        ('Contacto', {'fields': ('email_contacto',
         'telefono_contacto', 'direccion_fiscal')}),
        ('Estructura y Comisiones', {'fields': (
            'intermediario_relacionado', 'porcentaje_comision', 'porcentaje_override')}),
        ('Gestión', {'fields': ('usuarios',)}),
        ('Auditoría', {'fields': ('fecha_creacion', 'fecha_modificacion')}),
    )
    raw_id_fields = ('intermediario_relacionado',)
    # Dejamos esto comentado como medida de precaución.
    # filter_horizontal = ('usuarios',)

# --- Modelos de Contratos ---


class ContratoBaseAdmin(admin.ModelAdmin):
    """Clase base para no repetir código entre ContratoIndividual y Colectivo."""
    list_display = ('numero_contrato', 'ramo', 'estatus',
                    'fecha_inicio_vigencia', 'fecha_fin_vigencia', 'monto_total')
    search_fields = ('numero_contrato', 'numero_poliza', 'certificado')
    list_filter = ('estatus', 'ramo', 'forma_pago',
                   ('fecha_emision', admin.DateFieldListFilter))
    readonly_fields = ('numero_contrato', 'numero_poliza',
                       'certificado', 'fecha_creacion', 'fecha_modificacion')
    raw_id_fields = ('intermediario', 'tarifa_aplicada')
    inlines = [FacturaInline, ReclamacionInline]


@admin.register(ContratoIndividual)
class ContratoIndividualAdmin(ContratoBaseAdmin):
    list_display = ('numero_contrato', 'get_afiliado_link',
                    'ramo', 'estatus', 'monto_total')
    search_fields = ContratoBaseAdmin.search_fields + \
        ('afiliado__cedula', 'contratante_cedula')
    raw_id_fields = ContratoBaseAdmin.raw_id_fields + ('afiliado',)
    fieldsets = (
        ('Información Principal', {'fields': (
            'numero_contrato', 'numero_poliza', 'certificado', 'afiliado', 'ramo', 'plan_contratado')}),
        ('Contratante (Pagador)', {'fields': ('tipo_identificacion_contratante', 'contratante_cedula',
         'contratante_nombre', 'telefono_contratante', 'email_contratante', 'direccion_contratante')}),
        ('Vigencia y Estatus', {'fields': ('estatus', 'fecha_emision',
         'fecha_inicio_vigencia', 'fecha_fin_vigencia', 'periodo_vigencia_meses')}),
        ('Montos y Pagos', {'fields': ('tarifa_aplicada',
         'forma_pago', 'monto_total', 'suma_asegurada')}),
        ('Asociaciones y Auditoría', {'fields': (
            'intermediario', 'activo', 'fecha_creacion', 'fecha_modificacion')}),
    )

    def get_afiliado_link(self, obj):
        if obj.afiliado:
            url = reverse('admin:myapp_afiliadoindividual_change',
                          args=[obj.afiliado.pk])
            return mark_safe(f'<a href="{url}">{obj.afiliado}</a>')
        return "N/A"
    get_afiliado_link.short_description = 'Afiliado'


@admin.register(ContratoColectivo)
class ContratoColectivoAdmin(ContratoBaseAdmin):
    list_display = ('numero_contrato', 'razon_social',
                    'ramo', 'estatus', 'cantidad_empleados')
    search_fields = ContratoBaseAdmin.search_fields + ('razon_social', 'rif')
    filter_horizontal = ('afiliados_colectivos',)
    fieldsets = (
        ('Información Principal', {'fields': ('numero_contrato', 'numero_poliza',
         'certificado', 'razon_social', 'rif', 'ramo', 'plan_contratado')}),
        ('Detalles del Colectivo', {
         'fields': ('cantidad_empleados', 'afiliados_colectivos')}),
        ('Vigencia y Estatus', {'fields': ('estatus', 'fecha_emision',
         'fecha_inicio_vigencia', 'fecha_fin_vigencia', 'periodo_vigencia_meses')}),
        ('Montos y Pagos', {'fields': ('tarifa_aplicada',
         'forma_pago', 'monto_total', 'suma_asegurada')}),
        ('Asociaciones y Auditoría', {'fields': (
            'intermediario', 'activo', 'fecha_creacion', 'fecha_modificacion')}),
    )

# --- Modelos Financieros ---


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero_recibo', 'get_contrato_link',
                    'estatus_factura', 'monto', 'monto_pendiente', 'pagada')
    list_filter = ('estatus_factura', 'pagada', 'activo',
                   ('fecha_creacion', admin.DateFieldListFilter))
    search_fields = ('numero_recibo', 'contrato_individual__numero_contrato',
                     'contrato_colectivo__numero_contrato')
    readonly_fields = ('monto_pendiente', 'pagada', 'fecha_creacion',
                       'fecha_modificacion', 'get_contrato_link')
    raw_id_fields = ('contrato_individual',
                     'contrato_colectivo', 'intermediario')
    inlines = [PagoInline]

    def get_contrato_link(self, obj):
        contrato = obj.get_contrato_asociado
        if contrato:
            url = reverse(
                f'admin:myapp_{contrato._meta.model_name}_change', args=[contrato.pk])
            return mark_safe(f'<a href="{url}">{contrato}</a>')
        return "N/A"
    get_contrato_link.short_description = 'Contrato Asociado'


@admin.register(Reclamacion)
class ReclamacionAdmin(admin.ModelAdmin):
    list_display = ('numero_reclamacion', 'get_contrato_asociado_display',
                    'estado', 'monto_reclamado', 'fecha_reclamo')
    list_filter = ('estado', 'tipo_reclamacion', 'activo',
                   ('fecha_reclamo', admin.DateFieldListFilter))
    search_fields = ('numero_reclamacion',)
    readonly_fields = ('numero_reclamacion',
                       'fecha_creacion', 'fecha_modificacion')
    raw_id_fields = ('contrato_individual',
                     'contrato_colectivo', 'usuario_asignado')
    inlines = [PagoInline]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_pago', 'monto_pago',
                    'get_asociacion_link', 'activo')
    list_filter = ('forma_pago', 'activo',
                   ('fecha_pago', admin.DateFieldListFilter))
    search_fields = ('referencia_pago',)
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')
    raw_id_fields = ('factura', 'reclamacion')

    def get_asociacion_link(self, obj):
        if obj.factura:
            url = reverse('admin:myapp_factura_change', args=[obj.factura.pk])
            return mark_safe(f'Factura: <a href="{url}">{obj.factura.numero_recibo}</a>')
        if obj.reclamacion:
            url = reverse('admin:myapp_reclamacion_change',
                          args=[obj.reclamacion.pk])
            return mark_safe(f'Reclamación: <a href="{url}">{obj.reclamacion.numero_reclamacion}</a>')
        return "N/A"
    get_asociacion_link.short_description = 'Asociado a'

# --- Modelos de Configuración ---


@admin.register(Tarifa)
class TarifaAdmin(admin.ModelAdmin):
    list_display = ('codigo_tarifa', 'ramo', 'rango_etario',
                    'monto_anual', 'fecha_aplicacion', 'activo')
    list_filter = ('activo', 'ramo', 'rango_etario')
    search_fields = ('codigo_tarifa',)
    readonly_fields = ('codigo_tarifa', 'fecha_creacion', 'fecha_modificacion')


@admin.register(RegistroComision)
class RegistroComisionAdmin(admin.ModelAdmin):
    list_display = ('id', 'intermediario', 'tipo_comision',
                    'monto_comision', 'estatus_pago_comision', 'fecha_calculo')
    list_filter = ('tipo_comision', 'estatus_pago_comision',
                   ('fecha_calculo', admin.DateFieldListFilter))
    search_fields = ('intermediario__nombre_completo',)
    readonly_fields = ('fecha_calculo',)
    raw_id_fields = ('intermediario', 'contrato_individual', 'contrato_colectivo',
                     'pago_cliente', 'factura_origen', 'intermediario_vendedor', 'usuario_que_liquido')
