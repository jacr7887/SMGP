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
def generar_facturas_para_contrato(contrato):
    """
    Verifica si un contrato necesita una nueva factura y la crea si es necesario.
    """
    # (Tu código completo para esta función se mantiene aquí, sin cambios)
    hoy = date.today()
    if not hasattr(contrato, 'esta_vigente') or not contrato.esta_vigente:
        return 0
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
        return 0
    filtro_contrato = Q(contrato_individual=contrato) if isinstance(
        contrato, ContratoIndividual) else Q(contrato_colectivo=contrato)
    ultima_factura = Factura.objects.filter(
        filtro_contrato).order_by('-vigencia_recibo_hasta').first()
    fecha_inicio_siguiente_factura = contrato.fecha_inicio_vigencia
    if ultima_factura:
        fecha_inicio_siguiente_factura = ultima_factura.vigencia_recibo_hasta + \
            timedelta(days=1)
    if fecha_inicio_siguiente_factura > hoy:
        return 0
    fecha_fin_siguiente_factura = fecha_inicio_siguiente_factura + \
        intervalo - timedelta(days=1)
    if fecha_fin_siguiente_factura > contrato.fecha_fin_vigencia:
        fecha_fin_siguiente_factura = contrato.fecha_fin_vigencia
    if fecha_inicio_siguiente_factura > fecha_fin_siguiente_factura:
        return 0
    if Factura.objects.filter(filtro_contrato, vigencia_recibo_desde=fecha_inicio_siguiente_factura).exists():
        logger.warning(
            f"Factura para contrato {contrato.numero_contrato} y período desde {fecha_inicio_siguiente_factura} ya existe. Omitiendo.")
        return 0
    try:
        monto_factura = contrato.monto_cuota_estimada
        if monto_factura is None or monto_factura <= 0:
            logger.error(
                f"Error: Monto de cuota es None o cero para contrato {contrato.numero_contrato}. No se puede crear factura.")
            return 0
        with transaction.atomic():
            nueva_factura = Factura.objects.create(contrato_individual=contrato if isinstance(contrato, ContratoIndividual) else None, contrato_colectivo=contrato if isinstance(
                contrato, ContratoColectivo) else None, monto=monto_factura, vigencia_recibo_desde=fecha_inicio_siguiente_factura, vigencia_recibo_hasta=fecha_fin_siguiente_factura, intermediario=contrato.intermediario, estatus_factura='GENERADA')
        logger.info(
            f"ÉXITO: Factura {nueva_factura.numero_recibo} creada para contrato {contrato.numero_contrato} para el período {fecha_inicio_siguiente_factura} a {fecha_fin_siguiente_factura}.")
        return 1
    except Exception as e:
        logger.error(
            f"Error creando factura para contrato {contrato.numero_contrato}: {e}", exc_info=True)
        return 0


# --- 7. Tarea Principal para la Automatización ---
@background(schedule=0)
def generar_facturas_periodicas_task():
    """
    Tarea principal que se registrará y ejecutará en segundo plano.
    """
    logger.info(
        "--- INICIANDO TAREA: Generación de Facturas (django-background-tasks) ---")
    contratos_a_procesar = list(ContratoIndividual.objects.filter(activo=True, estatus='VIGENTE').exclude(forma_pago='CONTADO')) + \
        list(ContratoColectivo.objects.filter(activo=True,
             estatus='VIGENTE').exclude(forma_pago='CONTADO'))
    total_facturas_creadas = 0
    for contrato in contratos_a_procesar:
        total_facturas_creadas += generar_facturas_para_contrato(contrato)
    logger.info(
        f"--- TAREA FINALIZADA: Se crearon {total_facturas_creadas} nuevas facturas. ---")
    print(
        f"Tarea de facturación completada. Se crearon {total_facturas_creadas} facturas.")


# --- 8. Función para Programar la Tarea desde el Shell ---
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


# --- 9. Bloque de ejecución directa ---
if __name__ == "__main__":
    import django
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    django.setup()
    result = clear_graph_cache()
    print(f"Entradas eliminadas: {result or 0}")
