# admin.py
from django.db.models import Sum
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
# from django.http import HttpResponseRedirect # Ya no es necesario para la acción eliminada
# from django.shortcuts import render # Ya no es necesario para la acción eliminada
from django.contrib.admin import DateFieldListFilter
from rangefilter.filters import NumericRangeFilter
from django.shortcuts import render
from django.contrib.admin import SimpleListFilter
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
# <--- Esto está bien, le diste un alias
from django.utils import timezone as django_timezone
from django.db.models import Q  # Sigue siendo útil para filtros personalizados
# Sigue siendo útil para filtros personalizados
from .commons import CommonChoices
from .models import (
    Usuario,
    Intermediario,
    AfiliadoIndividual,
    AfiliadoColectivo,
    ContratoIndividual,
    ContratoColectivo,
    Reclamacion,
    Pago,
    Tarifa,
    Factura,
    AuditoriaSistema,
    RegistroComision,
    LicenseInfo
)
from django.contrib.admin.views.main import ChangeList
from .forms import RegistroComisionForm
from datetime import date
import logging

# Configuración del logger
logger = logging.getLogger(__name__)

# --- REGISTRO DE MODELOS ---


class CustomChangeList(ChangeList):
    def get_results(self, request):
        logger.info(
            f"--- [DebugChangeList for {self.model_admin.model.__name__}] ---")
        logger.info(
            f"1. Queryset INICIAL (pasado desde ModelAdmin.get_queryset):")
        if self.queryset is not None:
            logger.info(f"   Query: {self.queryset.query}")
            # Debería ser 321 al entrar aquí
            logger.info(f"   Count: {self.queryset.count()}")
        else:
            logger.warning("   Queryset inicial es None.")

        # Llamar al método get_results original para que haga su trabajo (aplicar filtros, etc.)
        super().get_results(request)

        logger.info(f"2. Después de super().get_results(request):")
        logger.info(f"   Filtros aplicados (params): {self.params}")
        logger.info(
            f"   Queryset DESPUÉS de filtros de ChangeList (self.queryset):")
        if self.queryset is not None:  # self.queryset es modificado por super().get_results
            logger.info(f"      Query: {self.queryset.query}")
            # Este es el count después de filtros
            logger.info(f"      Count: {self.queryset.count()}")
        else:
            logger.warning("      Queryset después de filtros es None.")

        # Total de elementos que coinciden con filtros
        logger.info(
            f"   Full result count (total después de filtros): {self.full_result_count}")
        logger.info(
            f"   Result count (elementos en la página actual): {self.result_count}")
        logger.info(
            f"   Multi page: {self.multi_page}, Can show all: {self.can_show_all}")
        logger.info(
            f"   len(result_list) (objetos en la página actual): {len(self.result_list) if self.result_list else 'N/A'}")
        logger.info(
            f"--- [DebugChangeList for {self.model_admin.model.__name__}] FIN ---")


class CustomModelAdmin(admin.ModelAdmin):
    def get_list_display(self, request):
        list_display = [
            field.name for field in self.model._meta.fields if field.name != 'id']
        return list_display

    def get_queryset(self, request):
        # Este es el get_queryset de la CLASE PADRE
        logger.debug(
            f"[CustomModelAdmin ({self.model.__name__})] get_queryset llamado por super()")
        qs = super().get_queryset(request)
        # Si quieres mantener el select_related genérico aquí (con precaución):
        # if hasattr(qs, 'select_related'):
        #     return qs.select_related()
        return qs


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):  # UserAdmin ya hereda de ModelAdmin
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = (
        'email',
        'get_full_name_display',  # Renombrado para claridad
        'tipo_usuario',
        'nivel_acceso',
        'departamento',
        'is_active',  # Debería ser 'activo' si ese es tu campo booleano principal
        'telefono',
        # 'direccion', # Puede ser muy largo para list_display
        'intermediario',
        # 'primer_nombre', # Ya incluido en get_full_name_display
        # 'segundo_nombre',
        # 'primer_apellido',
        # 'segundo_apellido',
    )
    list_filter = (
        'tipo_usuario',
        'activo',  # Usa tu campo 'activo'
        'nivel_acceso',
        ('groups', admin.RelatedOnlyFieldListFilter),
        'departamento'
    )
    search_fields = [
        'email',
        'primer_nombre',
        'primer_apellido',
        'telefono',
        'username'  # Es bueno buscar por username también
    ]
    filter_horizontal = ('groups', 'user_permissions')

    # Los fieldsets y add_fieldsets de UserAdmin suelen ser bastante buenos.
    # Los tuyos personalizados están bien si se ajustan a tu modelo Usuario.
    fieldsets = UserAdmin.fieldsets + (
        (('Información Personal Adicional'), {
            'fields': (
                # Ya están en UserAdmin.fieldsets si los heredas
                'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
                'fecha_nacimiento', 'departamento', 'telefono', 'direccion',
            )
        }),
        (('Configuración de App'), {
            # 'activo' en lugar de 'is_active' si ese es tu campo principal
            'fields': ('tipo_usuario', 'nivel_acceso', 'intermediario', 'activo')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {
            'fields': ('primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido', 'tipo_usuario', 'nivel_acceso', 'activo'),
        }),
    )

    def get_full_name_display(self, obj):
        return obj.get_full_name()
    get_full_name_display.short_description = 'Nombre Completo'
    # Asumiendo que primer_apellido es el campo principal para ordenar nombres
    get_full_name_display.admin_order_field = 'primer_apellido'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('intermediario').prefetch_related('groups', 'user_permissions')


@admin.register(Intermediario)
class IntermediarioAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = (
        'codigo',  # Poner el identificador principal primero
        'nombre_completo',
        'rif',
        'email_contacto',
        'telefono_contacto',
        'porcentaje_comision',
        'porcentaje_override',
        'intermediario_relacionado',
        'activo',
        # 'direccion_fiscal', # Largo para list_display
        # 'fecha_creacion',
        # 'fecha_modificacion',
    )
    list_filter = ('activo', ('porcentaje_comision', NumericRangeFilter))
    search_fields = ['codigo', 'nombre_completo', 'rif', 'email_contacto']
    # 'intermediario_relacionado' si quieres buscarlo
    autocomplete_fields = ['usuarios', 'intermediario_relacionado']
    readonly_fields = ('codigo', 'fecha_creacion', 'fecha_modificacion')


# Si NO usas CustomModelAdmin para AfiliadoIndividualAdmin para esta prueba:
@admin.register(AfiliadoIndividual)
# HEREDA DIRECTO DE admin.ModelAdmin
class AfiliadoIndividualAdmin(admin.ModelAdmin):
    list_display = ('id', 'cedula', 'nombre_completo', 'activo',
                    'fecha_creacion')  # Añade los campos que quieras ver
    list_filter = ('activo', 'estado_civil')  # El filtro 'activo' es clave
    # Para la barra de búsqueda
    search_fields = ('cedula', 'primer_nombre', 'primer_apellido')
    ordering = ('-fecha_creacion',)  # O como prefieras

    def get_queryset(self, request):
        # ESTA ES LA LÍNEA MÁS IMPORTANTE:
        # Le decimos al admin que use el manager 'all_objects'
        # para obtener el conjunto de datos base.
        qs = AfiliadoIndividual.all_objects.all()

        # Puedes añadir logs aquí si quieres verificar el conteo:
        # import logging
        # logger = logging.getLogger(__name__)
        # logger.info(f"Admin: get_queryset para AfiliadoIndividual está devolviendo {qs.count()} registros.")

        return qs

    def get_paginator(self, request, queryset, per_page, orphans=0, allow_empty_first_page=True):
        # Debería ser 321
        logger.info(
            f"[AfiliadoIndividualAdmin] get_paginator RECIBE queryset con count: {queryset.count()}")
        return super().get_paginator(request, queryset, per_page, orphans, allow_empty_first_page)

    def get_changelist(self, request, **kwargs):
        logger.info(
            f"--- [AfiliadoIndividualAdmin] get_changelist (usando DebugChangeList) ---")
        return CustomChangeList  # DEVOLVER NUESTRO CHANGELIST PERSONALIZADO


@admin.register(ContratoIndividual)
class ContratoIndividualAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = (
        'numero_contrato',
        'afiliado_link',  # Usar un método para enlazar al afiliado
        'intermediario',
        'ramo',
        'estatus',
        'monto_total',
        'fecha_inicio_vigencia',
        'fecha_fin_vigencia',
        'activo',  # El campo 'activo' del contrato
        # 'contratante_cedula',
        # 'contratante_nombre',
    )
    list_filter = ('estatus', 'ramo', 'forma_pago', 'intermediario',
                   'activo', ('fecha_emision', DateFieldListFilter))
    search_fields = ('numero_contrato', 'numero_poliza', 'contratante_cedula', 'contratante_nombre', 'afiliado__cedula',
                     'afiliado__primer_nombre', 'afiliado__primer_apellido', 'intermediario__nombre_completo', 'intermediario__codigo')
    autocomplete_fields = ['afiliado', 'intermediario',
                           'tarifa_aplicada']  # Añadir tarifa_aplicada
    date_hierarchy = 'fecha_emision'
    readonly_fields = ('fecha_creacion', 'fecha_modificacion', 'numero_contrato',
                       'numero_poliza', 'certificado', 'numero_recibo', 'fecha_emision')

    def afiliado_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.afiliado:
            link = reverse("admin:myapp_afiliadoindividual_change",
                           args=[obj.afiliado.pk])
            return format_html('<a href="{}">{}</a>', link, obj.afiliado)
        return "N/A"
    afiliado_link.short_description = 'Afiliado'
    afiliado_link.admin_order_field = 'afiliado'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('afiliado', 'intermediario', 'tarifa_aplicada')


@admin.register(ContratoColectivo)
class ContratoColectivoAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = (
        'numero_contrato',
        'razon_social',
        'rif',
        'intermediario',
        'ramo',
        'estatus',
        'monto_total',
        'activo',  # El campo 'activo' del contrato
        # 'tipo_empresa',
        # 'fecha_emision',
    )
    list_filter = ('estatus', 'ramo', 'tipo_empresa',
                   'intermediario', 'activo')
    search_fields = ('numero_contrato', 'numero_poliza', 'razon_social',
                     'rif', 'intermediario__nombre_completo', 'intermediario__codigo')
    autocomplete_fields = ['intermediario', 'tarifa_aplicada',
                           'afiliados_colectivos']  # Añadir tarifa_aplicada
    filter_horizontal = ('afiliados_colectivos',)  # Mejor para M2M
    readonly_fields = ('fecha_creacion', 'fecha_modificacion', 'numero_contrato',
                       'numero_poliza', 'certificado', 'numero_recibo', 'fecha_emision')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('intermediario', 'tarifa_aplicada').prefetch_related('afiliados_colectivos')


@admin.register(AfiliadoColectivo)
class AfiliadoColectivoAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = (
        'rif',
        'razon_social',
        'email_contacto',
        'telefono_contacto',
        'intermediario',
        'activo',
        # 'tipo_empresa',
        # 'estado',
    )
    list_filter = ('activo', 'tipo_empresa', 'estado', 'intermediario')
    search_fields = ('rif', 'razon_social', 'email_contacto',
                     'intermediario__nombre_completo', 'intermediario__codigo')
    autocomplete_fields = ['intermediario']
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')

# RamoListFilter se mantiene si la usas en algún ModelAdmin


class RamoListFilter(SimpleListFilter):
    title = 'Ramo'
    parameter_name = 'ramo'

    def lookups(self, request, model_admin):
        # Esta lógica puede ser pesada si hay muchos contratos. Considera optimizar o usar choices estáticos.
        ramos_individuales = set(
            ContratoIndividual.objects.values_list('ramo', flat=True).distinct())
        ramos_colectivos = set(ContratoColectivo.objects.values_list(
            'ramo', flat=True).distinct())
        todos_ramos = sorted(list(ramos_individuales.union(ramos_colectivos)))
        return [(ramo, dict(CommonChoices.RAMO).get(ramo, ramo)) for ramo in todos_ramos if ramo]

    def queryset(self, request, queryset):
        if self.value():
            # Asumiendo que el queryset es de un modelo que se relaciona con ContratoIndividual o ContratoColectivo
            # Este filtro es complejo y podría necesitar ajustarse según el modelo al que se aplique.
            # Si es para Factura, por ejemplo:
            return queryset.filter(
                Q(contrato_individual__ramo=self.value()) | Q(
                    contrato_colectivo__ramo=self.value())
            )
        return queryset


@admin.register(Factura)
class FacturaAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = (
        'numero_recibo',
        'contrato_display',  # Método para mostrar el contrato
        'monto',
        'estatus_factura',  # Usar tu campo
        'pagada',
        'vigencia_recibo_desde',
        'vigencia_recibo_hasta',
        'intermediario',
        'activo',  # El campo 'activo' de la factura
        # 'fecha_creacion',
    )
    list_filter = ('estatus_factura', 'pagada', 'activo',
                   'intermediario', RamoListFilter)  # Usar RamoListFilter
    search_fields = ('numero_recibo', 'contrato_individual__numero_contrato',
                     'contrato_colectivo__numero_contrato', 'intermediario__nombre_completo', 'relacion_ingreso')
    readonly_fields = ('monto_pendiente', 'pagada', 'relacion_ingreso',
                       'numero_recibo', 'fecha_creacion', 'fecha_modificacion')
    autocomplete_fields = ['contrato_individual',
                           'contrato_colectivo', 'intermediario']

    def contrato_display(self, obj):
        if obj.contrato_individual:
            return f"CI: {obj.contrato_individual.numero_contrato}"
        elif obj.contrato_colectivo:
            return f"CC: {obj.contrato_colectivo.numero_contrato}"
        return "N/A"
    contrato_display.short_description = 'Contrato'
    # contrato_display.admin_order_field = ... # Ordenar por esto es complejo

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('contrato_individual', 'contrato_colectivo', 'intermediario')


@admin.register(AuditoriaSistema)
# No suele necesitar acciones de importación
class AuditoriaSistemaAdmin(CustomModelAdmin):
    list_display = ('tiempo_inicio', 'tipo_accion', 'usuario_link', 'tabla_afectada',
                    'registro_id_afectado', 'detalle_corto', 'resultado_accion')
    list_filter = ('tipo_accion', 'resultado_accion',
                   ('tiempo_inicio', DateFieldListFilter), 'tabla_afectada')
    search_fields = ('usuario__email', 'detalle_accion',
                     'tabla_afectada', 'registro_id_afectado', 'direccion_ip')
    # Hacer todos los campos readonly
    readonly_fields = [f.name for f in AuditoriaSistema._meta.fields]
    # No permitir añadir desde el admin
    def has_add_permission(self, request): return False
    # No permitir cambiar desde el admin
    def has_change_permission(self, request, obj=None): return False
    # def has_delete_permission(self, request, obj=None): return False # Considera si se pueden borrar

    def usuario_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.usuario:
            link = reverse("admin:myapp_usuario_change", args=[
                           obj.usuario.pk])  # Ajusta 'myapp_usuario_change'
            return format_html('<a href="{}">{}</a>', link, obj.usuario.email)
        return "Sistema"
    usuario_link.short_description = 'Usuario'

    def detalle_corto(self, obj):
        return (obj.detalle_accion[:75] + '...') if obj.detalle_accion and len(obj.detalle_accion) > 75 else obj.detalle_accion
    detalle_corto.short_description = 'Detalle'


@admin.register(Reclamacion)
class ReclamacionAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = ('id', 'contrato_display', 'tipo_reclamacion', 'estado',
                    'monto_reclamado', 'fecha_reclamo', 'usuario_asignado', 'activo')
    list_filter = ('estado', 'tipo_reclamacion', 'activo',
                   ('fecha_reclamo', DateFieldListFilter), 'usuario_asignado')
    search_fields = ('id', 'descripcion_reclamo', 'diagnostico_principal', 'contrato_individual__numero_contrato',
                     'contrato_colectivo__numero_contrato', 'usuario_asignado__email')
    autocomplete_fields = ['contrato_individual',
                           'contrato_colectivo', 'usuario_asignado']
    date_hierarchy = 'fecha_reclamo'
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')

    def contrato_display(self, obj):
        if obj.contrato_individual:
            return f"CI: {obj.contrato_individual.numero_contrato}"
        elif obj.contrato_colectivo:
            return f"CC: {obj.contrato_colectivo.numero_contrato}"
        return "N/A"
    contrato_display.short_description = 'Contrato'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('contrato_individual', 'contrato_colectivo', 'usuario_asignado')


@admin.register(Pago)
class PagoAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = ('id', 'factura_link', 'reclamacion_link', 'monto_pago',
                    'fecha_pago', 'forma_pago', 'referencia_pago', 'activo')
    list_filter = ('activo', 'forma_pago', ('fecha_pago',
                   DateFieldListFilter), 'factura__estatus_factura')
    search_fields = ('referencia_pago',
                     'factura__numero_recibo', 'reclamacion__id')
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')
    ordering = ('-fecha_pago',)
    autocomplete_fields = ['factura', 'reclamacion']

    def factura_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.factura:
            link = reverse("admin:myapp_factura_change", args=[obj.factura.pk])
            return format_html('<a href="{}">{}</a>', link, obj.factura.numero_recibo)
        return "N/A"
    factura_link.short_description = 'Factura'

    def reclamacion_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.reclamacion:
            link = reverse("admin:myapp_reclamacion_change",
                           args=[obj.reclamacion.pk])
            return format_html('<a href="{}">{}</a>', link, f"Reclamo #{obj.reclamacion.pk}")
        return "N/A"
    reclamacion_link.short_description = 'Reclamación'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('factura__contrato_individual', 'factura__contrato_colectivo', 'reclamacion')


@admin.register(Tarifa)
class TarifaAdmin(CustomModelAdmin):
    # actions = [importar_datos_action] # <- ELIMINADO
    list_display = ('ramo', 'rango_etario', 'fecha_aplicacion', 'monto_anual',
                    'monto_mensual_display', 'tipo_fraccionamiento', 'activo')
    list_filter = ('ramo', 'rango_etario', 'activo', 'tipo_fraccionamiento')
    search_fields = ('ramo', 'rango_etario')
    # monto_mensual, etc. son properties
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')

    def monto_mensual_display(self, obj):
        return obj.monto_mensual  # Asume que tienes una property llamada monto_mensual
    monto_mensual_display.short_description = 'Monto Mensual (Calculado)'


class RegistroComisionAdmin(admin.ModelAdmin):
    list_display = (
        'intermediario',
        'tipo_comision',
        'monto_comision',
        'estatus_pago_comision',
        'fecha_calculo',
        'factura_origen_link',
        'pago_cliente_link',
        'intermediario_vendedor'
    )
    list_filter = ('estatus_pago_comision', 'tipo_comision',
                   'intermediario', 'fecha_calculo')
    search_fields = (
        'intermediario__nombre_completo',
        'intermediario__codigo',
        'factura_origen__numero_recibo',
        'pago_cliente__referencia_pago'
    )
    readonly_fields = ('fecha_calculo',)

    def factura_origen_link(self, obj):
        if obj.factura_origen:
            # Asegúrate que 'myapp' es el nombre de tu app
            link = reverse("admin:myapp_factura_change",
                           args=[obj.factura_origen.id])
            return format_html('<a href="{}">{}</a>', link, obj.factura_origen)
        return "-"
    factura_origen_link.short_description = 'Factura Origen'

    def pago_cliente_link(self, obj):
        if obj.pago_cliente:
            # Asegúrate que 'myapp' es el nombre de tu app
            link = reverse("admin:myapp_pago_change",
                           args=[obj.pago_cliente.id])
            return format_html('<a href="{}">{}</a>', link, obj.pago_cliente)
        return "-"
    pago_cliente_link.short_description = 'Pago Cliente'

    actions = ['marcar_como_pagadas']

    def marcar_como_pagadas(self, request, queryset):
        updated_count = queryset.update(
            estatus_pago_comision='PAGADA',
            fecha_pago_a_intermediario=django_timezone.now().date()  # Aquí se usa timezone
        )
        self.message_user(
            request, f"{updated_count} comisiones marcadas como pagadas.")
    marcar_como_pagadas.short_description = "Marcar seleccionadas como PAGADAS"


admin.site.register(RegistroComision, RegistroComisionAdmin)


@admin.register(LicenseInfo)
class LicenseInfoAdmin(admin.ModelAdmin):
    """
    Configuración personalizada para el modelo LicenseInfo en el admin de Django.
    """
    list_display = ('id', 'get_key_display', 'expiry_date',
                    'is_valid_display', 'last_updated')
    list_display_links = ('id', 'get_key_display')

    # Definir qué campos se muestran en el formulario de edición y en qué orden
    # Como es un singleton y 'id' es fijo, solo queremos editar la clave y la fecha de expiración.
    fields = ('license_key', 'expiry_date', 'last_updated')
    readonly_fields = ('id', 'expiry_date', 'last_updated')
    # Hacer que ciertos campos solo sean de lectura en el formulario de detalle/cambio
    # 'id' y 'last_updated' ya son manejados por el modelo/Django.
    # No es necesario añadirlos aquí si el modelo ya los hace no editables.

    def get_key_display(self, obj):
        """Muestra solo una parte de la clave en el listado por seguridad/brevedad."""
        if obj.license_key and len(obj.license_key) > 10:
            return f"{obj.license_key[:4]}...{obj.license_key[-4:]}"
        return obj.license_key
    get_key_display.short_description = "Clave de Licencia (Fragmento)"

    def is_valid_display(self, obj):
        """Muestra el estado de validez con un ícono."""
        return "✅ Válida" if obj.is_valid else "❌ Expirada/Inválida"
    is_valid_display.short_description = "Estado"
    # Para que no lo trate como un booleano con íconos por defecto
    is_valid_display.boolean = False

    def get_queryset(self, request):
        # Asegurar que solo se muestre la instancia singleton (ID=1)
        # Aunque con pk=1 como default y primary_key, es difícil crear otras.
        qs = super().get_queryset(request)
        return qs.filter(pk=LicenseInfo.SINGLETON_ID)

    def has_add_permission(self, request):
        # No permitir añadir nuevas instancias, solo editar la existente (ID=1)
        # Si no existe ninguna, el sistema debería permitir crear la primera
        # o se puede hacer vía una migración de datos o un comando.
        # Por simplicidad, si no existe, la vista de 'activate_license' la crearía.
        # Aquí, si ya existe una, no dejamos crear más.
        return not LicenseInfo.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # No permitir borrar la instancia de configuración de licencia
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)
