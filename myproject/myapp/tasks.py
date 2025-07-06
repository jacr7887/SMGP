# myapp/tasks.py

# --- 1. Importaciones de Terceros y de Django ---
from typing import Optional
import logging
import warnings
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError
from django.db import transaction
from django.db.models import Q

# --- 2. Importaciones de la librería de tareas en segundo plano ---
from background_task import background
from background_task.models import Task

# --- 3. Importaciones de tu Propia App ---
from .models import ContratoIndividual, ContratoColectivo, Factura

# --- 4. Configuración del Logger ---
logger = logging.getLogger(__name__)
warnings.simplefilter("ignore", ResourceWarning)


# --- 5. Lógica de Gestión de Caché (SIMPLIFICADA Y CORRECTA) ---
def clear_graph_cache(backend_name: str = 'default') -> Optional[int]:
    """
    Elimina todas las entradas de caché de gráficos para el backend de caché de archivos.
    """
    try:
        backend = caches[backend_name]

        # Como solo usas FileBasedCache, esta es la única lógica que necesitas.
        keys = backend.keys("graph_*")
        if not keys:
            logger.debug(
                "No se encontraron claves de caché de gráficos para limpiar.")
            return 0

        backend.delete_many(keys)
        logger.info(
            f"Se eliminaron {len(keys)} entradas de la caché de gráficos.")
        return len(keys)

    except (KeyError, InvalidCacheBackendError) as e:
        logger.critical(
            f"Backend de caché '{backend_name}' no encontrado o inválido: {e}")
        return None
    except Exception as e:
        logger.error(
            f"Error inesperado al limpiar la caché de gráficos: {e}", exc_info=True)
        return None


# --- 6. Función Helper para la Lógica de un Contrato (sin cambios) ---

@background(schedule=0, name='generar_factura_para_contrato_especifico')
def generar_factura_para_contrato_especifico(contrato_id: int, tipo_contrato: str):
    """
    Verifica y genera una factura para UN SOLO contrato.
    Esta es la tarea que se ejecuta en el worker.
    """
    logger.info(f"Procesando {tipo_contrato} ID: {contrato_id}")

    try:
        if tipo_contrato == 'individual':
            ContratoModel = ContratoIndividual
        elif tipo_contrato == 'colectivo':
            ContratoModel = ContratoColectivo
        else:
            logger.error(
                f"Tipo de contrato desconocido '{tipo_contrato}' para ID {contrato_id}")
            return

        # REHIDRATACIÓN: Obtenemos el objeto desde la BD aquí.
        # El ORM se encargará de desencriptar los campos.
        contrato = ContratoModel.objects.get(pk=contrato_id)
    except ContratoModel.DoesNotExist:
        logger.error(
            f"Contrato {tipo_contrato} con ID {contrato_id} no encontrado. La tarea finaliza.")
        return

    # --- Lógica de generación (la misma que tenías, ahora dentro de esta tarea) ---
    hoy = date.today()
    if not contrato.esta_vigente:
        logger.debug(
            f"Contrato {contrato.numero_contrato} no está vigente. Omitiendo.")
        return

    intervalo = None
    if contrato.forma_pago == 'MENSUAL':
        intervalo = relativedelta(months=1)
    elif contrato.forma_pago == 'TRIMESTRAL':
        intervalo = relativedelta(months=3)
    elif contrato.forma_pago == 'SEMESTRAL':
        intervalo = relativedelta(months=6)
    elif contrato.forma_pago == 'ANUAL':
        intervalo = relativedelta(years=1)

    if not intervalo:
        logger.debug(
            f"Contrato {contrato.numero_contrato} con forma de pago no periódica. Omitiendo.")
        return

    filtro_contrato = Q(contrato_individual=contrato) if tipo_contrato == 'individual' else Q(
        contrato_colectivo=contrato)
    ultima_factura = Factura.objects.filter(
        filtro_contrato).order_by('-vigencia_recibo_hasta').first()

    fecha_inicio_siguiente_factura = contrato.fecha_inicio_vigencia
    if ultima_factura:
        fecha_inicio_siguiente_factura = ultima_factura.vigencia_recibo_hasta + \
            timedelta(days=1)

    if fecha_inicio_siguiente_factura > contrato.fecha_fin_vigencia:
        logger.debug(
            f"Contrato {contrato.numero_contrato} ha completado su ciclo de facturación. Omitiendo.")
        return

    # Verificar si ya es tiempo de generar la siguiente factura
    if fecha_inicio_siguiente_factura > hoy:
        logger.debug(
            f"Aún no es tiempo de generar la siguiente factura para {contrato.numero_contrato}. Próxima: {fecha_inicio_siguiente_factura}")
        return

    fecha_fin_siguiente_factura = min(
        fecha_inicio_siguiente_factura + intervalo - timedelta(days=1),
        contrato.fecha_fin_vigencia
    )

    if Factura.objects.filter(filtro_contrato, vigencia_recibo_desde=fecha_inicio_siguiente_factura).exists():
        logger.warning(
            f"Factura para contrato {contrato.numero_contrato} y período desde {fecha_inicio_siguiente_factura} ya existe. Omitiendo.")
        return

    try:
        # El acceso a .monto_cuota_estimada ahora funcionará porque el objeto fue rehidratado.
        monto_factura = contrato.monto_cuota_estimada
        if monto_factura is None or monto_factura <= 0:
            logger.error(
                f"Error: Monto de cuota es None o cero para contrato {contrato.numero_contrato}. No se puede crear factura.")
            return

        with transaction.atomic():
            nueva_factura = Factura.objects.create(
                contrato_individual=contrato if tipo_contrato == 'individual' else None,
                contrato_colectivo=contrato if tipo_contrato == 'colectivo' else None,
                monto=monto_factura,
                vigencia_recibo_desde=fecha_inicio_siguiente_factura,
                vigencia_recibo_hasta=fecha_fin_siguiente_factura,
                intermediario=contrato.intermediario,  # Esto también funcionará
                estatus_factura='GENERADA'
            )
        logger.info(
            f"ÉXITO: Factura {nueva_factura.numero_recibo} creada para contrato {contrato.numero_contrato}.")
    except Exception as e:
        logger.error(
            f"Error creando factura para contrato {contrato.numero_contrato}: {e}", exc_info=True)


@background(schedule=0)
def generar_facturas_periodicas_task():
    """
    Tarea orquestadora. Obtiene los IDs de los contratos y encola tareas individuales.
    """
    logger.info("--- INICIANDO TAREA ORQUESTADORA: Generación de Facturas ---")

    # Obtener solo los PKs, es mucho más eficiente
    contratos_ind_ids = ContratoIndividual.objects.filter(
        activo=True, estatus='VIGENTE'
    ).exclude(forma_pago='CONTADO').values_list('pk', flat=True)

    contratos_col_ids = ContratoColectivo.objects.filter(
        activo=True, estatus='VIGENTE'
    ).exclude(forma_pago='CONTADO').values_list('pk', flat=True)

    # Encolar una tarea por cada contrato
    for contrato_id in contratos_ind_ids:
        generar_factura_para_contrato_especifico(contrato_id, 'individual')

    for contrato_id in contratos_col_ids:
        generar_factura_para_contrato_especifico(contrato_id, 'colectivo')

    total_tareas_encoladas = len(contratos_ind_ids) + len(contratos_col_ids)
    logger.info(
        f"--- TAREA ORQUESTADORA FINALIZADA: Se encolaron {total_tareas_encoladas} tareas de facturación individuales. ---")
    print(
        f"Tarea orquestadora completada. Se encolaron {total_tareas_encoladas} tareas.")


# --- 7. Función para Programar la Tarea desde el Shell ---
def programar_generador_de_facturas():
    """
    Se ejecuta una sola vez desde el shell para registrar la tarea en la base de datos.
    """
    task_name = "myapp.tasks.generar_facturas_periodicas_task"
    verbose_name = "Generador Diario de Facturas"
    if not Task.objects.filter(task_name=task_name).exists():
        generar_facturas_periodicas_task(
            repeat=Task.DAILY, verbose_name=verbose_name, remove_existing_tasks=True)
        print(
            f"ÉXITO: Tarea '{verbose_name}' programada para ejecutarse diariamente.")
    else:
        print(f"INFO: La tarea '{verbose_name}' ya estaba programada.")


# --- 8. Bloque de ejecución directa ---
if __name__ == "__main__":
    import django
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    django.setup()
    result = clear_graph_cache()
    print(f"Entradas eliminadas: {result or 0}")
