# myapp/signals.py
import logging
from datetime import date, timedelta
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone
import threading
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction, models
from django.db.models import Sum, F, Value, DecimalField, Q  # Value no se usa aquí
from django.db.models.functions import Coalesce
from django.apps import apps
# Para generar URLs y manejar si no existe
from django.urls import reverse, NoReverseMatch
# <--- Esto está bien, le diste un alias
from django.utils import timezone as django_timezone


# Modelos de tu app
from .models import (
    Usuario, ContratoIndividual, ContratoColectivo,
    AfiliadoIndividual, AfiliadoColectivo, Intermediario,
    Reclamacion, Tarifa, AuditoriaSistema, Pago, RegistroComision, Factura, Notificacion
)
# Validadores (asegúrate que estas importaciones sean correctas y necesarias aquí)
from .validators import (
    validate_rif,
    validate_cedula,
    validate_telefono_venezuela,
    # validate_numero_contrato, # Probablemente no necesario en señales si el modelo ya lo valida
    validate_email_domain
)
from .commons import CommonChoices


_signal_stack = threading.local()


def prevent_recursion(signal_handler):
    def wrapper(*args, **kwargs):
        signal_name = f"{signal_handler.__module__}.{signal_handler.__name__}"
        sender_model = kwargs.get('sender', None)
        instance_pk = getattr(kwargs.get('instance'), 'pk', None)

        # Construir una clave más robusta para la recursión
        signal_key_parts = [signal_name]
        if sender_model:
            signal_key_parts.append(sender_model.__name__)
        if instance_pk:
            signal_key_parts.append(str(instance_pk))

        # Identificador único para esta ejecución de la señal y la instancia
        # Esto ayuda si la misma señal se dispara para la misma instancia varias veces
        # en una pila de llamadas compleja (aunque el objetivo es evitar la recursión directa).
        # Podríamos añadir un contador o un UUID si fuera necesario para una granularidad aún mayor.
        signal_key = "_".join(signal_key_parts)

        if not hasattr(_signal_stack, 'stack'):
            _signal_stack.stack = set()

        if signal_key in _signal_stack.stack:
            # logger.debug(f"Recursion prevented for signal: {signal_key}") # Descomentar para depurar recursión
            return

        _signal_stack.stack.add(signal_key)
        try:
            return signal_handler(*args, **kwargs)
        finally:
            _signal_stack.stack.discard(signal_key)
            # Limpiar el stack si está vacío para liberar memoria
            if not _signal_stack.stack:  # No usar hasattr aquí, solo chequear si está vacío
                delattr(_signal_stack, 'stack')
    return wrapper


@receiver(post_save, sender=Usuario)
@prevent_recursion
def configurar_usuario(sender, instance, created, **kwargs):
    if created:
        try:
            logger.info(
                f"Usuario {instance.email} creado (PK: {instance.pk}).")
        except Exception as e:
            logger.error(
                f"Error en post_save Usuario (PK: {instance.pk}): {e}", exc_info=True)


@receiver(pre_save, sender=AfiliadoColectivo)
# @prevent_recursion # Generalmente no necesario para pre_save si no modifican la misma instancia
def validar_afiliado_colectivo(sender, instance, **kwargs):
    error_dict = {}
    try:
        if instance.rif:
            try:
                validate_rif(instance.rif)
            except ValidationError as e:
                error_dict['rif'] = e.messages

        if instance.telefono_contacto:
            try:
                validate_telefono_venezuela(instance.telefono_contacto)
            except ValidationError as e:
                error_dict['telefono_contacto'] = e.messages

        if instance.email_contacto:
            try:
                validate_email_domain(instance.email_contacto)
            except ValidationError as e:
                error_dict.setdefault('email_contacto', []).extend(e.messages)

        if instance.tipo_empresa == 'PUBLICA' and not instance.rif:
            error_dict.setdefault('rif', []).append(
                'Las empresas públicas deben tener RIF registrado.')

        if error_dict:
            raise ValidationError(error_dict)
    except ValidationError as ve:
        logger.warning(
            f"Validación pre_save fallida AfiliadoColectivo (PK: {instance.pk}): {ve.message_dict}")
        raise


@receiver(pre_save, sender=ContratoIndividual)
@receiver(pre_save, sender=ContratoColectivo)
# @prevent_recursion
def validar_formatos_basicos_contrato(sender, instance, **kwargs):
    error_dict = {}
    # ... (tu lógica de validación existente) ...
    try:
        if isinstance(instance, ContratoIndividual):
            if instance.contratante_cedula:
                try:
                    tipo_id = instance.tipo_identificacion_contratante
                    cedula_rif = instance.contratante_cedula
                    if tipo_id in ['V', 'E']:
                        validate_cedula(cedula_rif)
                    elif tipo_id in ['J', 'G']:
                        validate_rif(cedula_rif)
                except ValidationError as e:
                    error_dict.setdefault(
                        'contratante_cedula', []).extend(e.messages)

        elif isinstance(instance, ContratoColectivo):
            if instance.rif:
                try:
                    validate_rif(instance.rif)
                except ValidationError as e:
                    error_dict.setdefault('rif', []).extend(e.messages)

            if hasattr(instance, 'estatus'):
                estatus_validos = [choice[0]
                                   for choice in CommonChoices.ESTADOS_VIGENCIA]
                if instance.estatus not in estatus_validos:
                    error_dict.setdefault('estatus', []).append(
                        f"El estatus '{instance.estatus}' no es válido. Válidos: {', '.join(estatus_validos)}")

        if error_dict:
            raise ValidationError(error_dict)

    except ValidationError as ve:
        logger.warning(
            f"Validación pre_save fallida {sender.__name__} (PK:{instance.pk}): {ve.message_dict}")
        raise
    except Exception as e:
        logger.exception(
            f"Error inesperado pre_save {sender.__name__} (PK:{instance.pk}): {e}")
        raise


@receiver(pre_save, sender=AfiliadoIndividual)
# @prevent_recursion
def validar_formato_afiliado_individual(sender, instance, **kwargs):
    error_dict = {}
    # ... (tu lógica de validación existente) ...
    try:
        if instance.fecha_nacimiento:
            try:
                if not isinstance(instance.fecha_nacimiento, date):
                    raise ValidationError(
                        "Formato de fecha de nacimiento inválido.")
                if instance.fecha_nacimiento > django_timezone.now().date():  # Usar timezone.now().date()
                    raise ValidationError(
                        "Fecha de nacimiento no puede ser futura.")
            except ValidationError as e:
                error_dict.setdefault('fecha_nacimiento', []).extend(
                    e.messages if isinstance(e.messages, list) else [e.message])

        if instance.cedula:
            try:
                validate_cedula(instance.cedula)
            except ValidationError as e:
                error_dict.setdefault('cedula', []).extend(e.messages)

        if instance.telefono_habitacion:
            try:
                validate_telefono_venezuela(instance.telefono_habitacion)
            except ValidationError as e:
                error_dict.setdefault(
                    'telefono_habitacion', []).extend(e.messages)
        if instance.telefono_oficina:
            try:
                validate_telefono_venezuela(instance.telefono_oficina)
            except ValidationError as e:
                error_dict.setdefault('telefono_oficina',
                                      []).extend(e.messages)

        if instance.email:
            try:
                validate_email_domain(instance.email)
            except ValidationError as e:
                error_dict.setdefault('email', []).extend(e.messages)

        if error_dict:
            raise ValidationError(error_dict)
    except ValidationError as ve:
        logger.warning(
            f"Validación pre_save fallida AfiliadoIndividual (PK: {instance.pk}): {ve.message_dict}")
        raise


@receiver(pre_save, sender=Reclamacion)
# @prevent_recursion
def validar_reclamacion_basica(sender, instance, **kwargs):
    error_dict = {}
    # ... (tu lógica de validación existente) ...
    try:
        contrato = instance.contrato_individual or instance.contrato_colectivo
        if not contrato:
            error_dict['contrato'] = 'La reclamación debe estar asociada a un contrato.'

        if instance.monto_reclamado is not None and instance.monto_reclamado < Decimal('0.00'):
            error_dict['monto_reclamado'] = "Monto reclamado no puede ser negativo."

        if instance.fecha_reclamo:
            if instance.fecha_reclamo > django_timezone.now().date():
                error_dict.setdefault('fecha_reclamo', []).append(
                    'La fecha de reclamación no puede ser futura.')
        else:
            error_dict.setdefault('fecha_reclamo', []).append(
                'La fecha de reclamación es obligatoria.')

        if instance.fecha_cierre_reclamo and instance.fecha_reclamo and instance.fecha_cierre_reclamo < instance.fecha_reclamo:
            error_dict.setdefault('fecha_cierre_reclamo', []).append(
                'La fecha de cierre debe ser posterior o igual a la fecha de reclamo.')

        if error_dict:
            raise ValidationError(error_dict)
    except ValidationError as ve:
        logger.warning(
            f"Validación pre_save fallida Reclamacion (PK: {instance.pk}): {ve.message_dict}")
        raise


@receiver(post_save, sender=Reclamacion)
@prevent_recursion
def manejar_estado_reclamacion(sender, instance, created, **kwargs):
    # ... (tu lógica existente) ...
    try:
        needs_save = False
        update_fields = []
        today = django_timezone.now().date()

        if instance.estado in ['APROBADA', 'RECHAZADA', 'CERRADA'] and not instance.fecha_cierre_reclamo:
            instance.fecha_cierre_reclamo = today
            update_fields.append('fecha_cierre_reclamo')
            needs_save = True
            logger.info(
                f"Reclamación ID {instance.pk} cerrada automáticamente (Estado: {instance.estado}). Fecha cierre: {today}")

        elif instance.estado in ['ABIERTA', 'EN_PROCESO'] and instance.fecha_cierre_reclamo:
            instance.fecha_cierre_reclamo = None
            update_fields.append('fecha_cierre_reclamo')
            needs_save = True
            logger.info(
                f"Reclamación ID {instance.pk} reabierta automáticamente (Estado: {instance.estado}). Fecha cierre eliminada.")

        if needs_save:
            # Usar queryset.update para evitar recursión si el modelo tiene lógica en save()
            Reclamacion.objects.filter(pk=instance.pk).update(
                **{field: getattr(instance, field) for field in update_fields})

    except Exception as e:
        logger.error(
            f"Error en post_save Reclamacion (ID: {instance.pk}) al manejar estado: {e}", exc_info=True)


@receiver(pre_save, sender=Intermediario)
# @prevent_recursion
def validar_intermediario_basico(sender, instance, **kwargs):
    error_dict = {}
    # ... (tu lógica de validación existente) ...
    try:
        if instance.rif:
            try:
                validate_rif(instance.rif)
            except ValidationError as e:
                error_dict.setdefault('rif', []).extend(e.messages)

        if instance.telefono_contacto:
            try:
                validate_telefono_venezuela(instance.telefono_contacto)
            except ValidationError as e:
                error_dict.setdefault(
                    'telefono_contacto', []).extend(e.messages)

        if instance.email_contacto:
            try:
                validate_email_domain(instance.email_contacto)
            except ValidationError as e:
                error_dict.setdefault('email_contacto', []).extend(e.messages)

        if instance.porcentaje_comision is not None:
            if not (0 <= instance.porcentaje_comision <= 100):  # O 50 si ese es tu límite real
                error_dict.setdefault('porcentaje_comision', []).append(
                    'El porcentaje de comisión debe estar entre 0 y 100.')

        if instance.porcentaje_override is not None:
            if not (0 <= instance.porcentaje_override <= 20):  # O tu límite real para override
                error_dict.setdefault('porcentaje_override', []).append(
                    'El porcentaje de override debe estar entre 0 y 20.')

        if error_dict:
            raise ValidationError(error_dict)
    except ValidationError as ve:
        logger.warning(
            f"Validación pre_save fallida Intermediario (PK: {instance.pk}): {ve.message_dict}")
        raise


@receiver(post_save, sender=AuditoriaSistema)
@prevent_recursion
def registrar_accion_auditoria(sender, instance, created, **kwargs):
    if created:
        logger.debug(
            f"Registro Auditoría (ID: {instance.pk}) guardado: Acción={instance.tipo_accion}, Tabla={instance.tabla_afectada}, Resultado={instance.resultado_accion}")


@receiver(pre_save, sender=Tarifa)
def validar_tarifa(sender, instance, **kwargs):
    """
    Valida los datos de una instancia de Tarifa antes de guardarla.
    Ya no valida la comisión, ya que ese campo fue eliminado.
    """
    error_dict = {}
    try:
        # Validación de la fecha de aplicación
        if instance.fecha_aplicacion and instance.fecha_aplicacion > django_timezone.now().date():
            error_dict['fecha_aplicacion'] = "La fecha de aplicación no puede ser futura."

        # Validación del monto anual
        if instance.monto_anual is not None and instance.monto_anual <= 0:
            error_dict['monto_anual'] = "El monto anual debe ser un valor positivo."

        # Si se encontraron errores, lanzar una única excepción de validación
        if error_dict:
            raise ValidationError(error_dict)

    except ValidationError as ve:
        # Registrar el error de validación y relanzarlo para que el formulario lo capture
        logger.warning(
            f"Validación pre_save fallida para Tarifa (PK: {instance.pk}): {ve.message_dict}")
        raise

# =============================================================================
# SEÑALES PARA PAGOS Y COMISIONES
# =============================================================================


@transaction.atomic
def calcular_y_registrar_comisiones(pago_instance):
    """
    Calcula y registra comisiones (Directa y Override) y envía notificaciones
    al intermediario correspondiente solo si la comisión se acaba de crear.
    """
    logger.info(f"[COMISIONES] Iniciando para Pago PK: {pago_instance.pk}")

    if not pago_instance.factura_id:
        logger.info("[COMISIONES] Pago no asociado a factura. Finalizando.")
        return

    monto_base_calculo = pago_instance.monto_pago
    if not monto_base_calculo or monto_base_calculo <= Decimal('0.00'):
        logger.info("[COMISIONES] Monto base es cero o None. Finalizando.")
        return

    try:
        factura = Factura.objects.select_related(
            'contrato_individual__intermediario__intermediario_relacionado',
            'contrato_colectivo__intermediario__intermediario_relacionado'
        ).get(pk=pago_instance.factura_id)
    except Factura.DoesNotExist:
        logger.error(
            f"[COMISIONES] ERROR: Factura {pago_instance.factura_id} no encontrada.")
        return

    contrato = factura.contrato_individual or factura.contrato_colectivo
    if not contrato or not contrato.intermediario:
        logger.info(
            f"[COMISIONES] Factura {factura.pk} sin contrato o intermediario. Finalizando.")
        return

    intermediario_venta = contrato.intermediario

    # --- 1. COMISIÓN DIRECTA ---
    porcentaje_directa = intermediario_venta.porcentaje_comision or Decimal(
        '0.00')
    if porcentaje_directa > Decimal('0.00'):
        monto_comision = (monto_base_calculo *
                          porcentaje_directa) / Decimal('100.00')
        rc_directa, created = RegistroComision.objects.get_or_create(
            pago_cliente=pago_instance,
            intermediario=intermediario_venta,
            tipo_comision='DIRECTA',
            defaults={
                'contrato_individual': factura.contrato_individual,
                'contrato_colectivo': factura.contrato_colectivo,
                'factura_origen': factura,
                'porcentaje_aplicado': porcentaje_directa,
                'monto_base_calculo': monto_base_calculo,
                'monto_comision': monto_comision.quantize(Decimal('0.01'), ROUND_HALF_UP),
                'intermediario_vendedor': intermediario_venta
            }
        )
        if created:
            logger.info(
                f"[COMISIONES] Creada comisión DIRECTA de ${rc_directa.monto_comision} para {intermediario_venta.nombre_completo}.")
            # === NOTIFICACIÓN PARA INTERMEDIARIO DIRECTO ===
            mensaje_directa = f"¡Felicidades! Has ganado una comisión directa de ${rc_directa.monto_comision:,.2f} por el pago de la factura {factura.numero_recibo}."
            usuarios_a_notificar = intermediario_venta.usuarios_asignados.filter(
                is_active=True)
            if usuarios_a_notificar.exists():
                crear_notificacion(
                    usuario_destino=usuarios_a_notificar,
                    mensaje=mensaje_directa,
                    tipo='success',
                    url_path_name='myapp:mis_comisiones_list'
                )
        else:
            logger.warning(
                f"[COMISIONES] Comisión DIRECTA para Pago {pago_instance.pk} ya existía.")

    # --- 2. COMISIÓN DE OVERRIDE ---
    intermediario_padre = intermediario_venta.intermediario_relacionado
    if intermediario_padre:
        porcentaje_override = intermediario_padre.porcentaje_override or Decimal(
            '0.00')
        if porcentaje_override > Decimal('0.00'):
            monto_comision_override = (
                monto_base_calculo * porcentaje_override) / Decimal('100.00')
            rc_override, created_override = RegistroComision.objects.get_or_create(
                pago_cliente=pago_instance,
                intermediario=intermediario_padre,
                tipo_comision='OVERRIDE',
                defaults={
                    'contrato_individual': factura.contrato_individual,
                    'contrato_colectivo': factura.contrato_colectivo,
                    'factura_origen': factura,
                    'porcentaje_aplicado': porcentaje_override,
                    'monto_base_calculo': monto_base_calculo,
                    'monto_comision': monto_comision_override.quantize(Decimal('0.01'), ROUND_HALF_UP),
                    'intermediario_vendedor': intermediario_venta
                }
            )
            if created_override:
                logger.info(
                    f"[COMISIONES] Creada comisión OVERRIDE de ${rc_override.monto_comision} para {intermediario_padre.nombre_completo}.")
                # === NOTIFICACIÓN PARA INTERMEDIARIO PADRE ===
                mensaje_override = f"¡Has ganado una comisión de override de ${rc_override.monto_comision:,.2f} por una venta de {intermediario_venta.nombre_completo}!"
                usuarios_padre_a_notificar = intermediario_padre.usuarios_asignados.filter(
                    is_active=True)
                if usuarios_padre_a_notificar.exists():
                    crear_notificacion(
                        usuario_destino=usuarios_padre_a_notificar,
                        mensaje=mensaje_override,
                        tipo='success',
                        url_path_name='myapp:mis_comisiones_list'
                    )
            else:
                logger.warning(
                    f"[COMISIONES] Comisión OVERRIDE para Pago {pago_instance.pk} ya existía.")

    logger.info(f"[COMISIONES] Finalizado para Pago PK: {pago_instance.pk}\n")


# @receiver(post_save, sender=Pago, dispatch_uid="pago_post_save_main_handler")
@prevent_recursion
def pago_post_save_handler(sender, instance, created, **kwargs):
    """
    Handler principal que se ejecuta después de guardar un Pago.
    Orquesta todas las acciones necesarias:
    1. Actualiza la Factura o Reclamación asociada.
    2. Calcula y registra las comisiones.
    3. Envía notificaciones.
    """
    logger.info(
        f"--- SEÑAL POST_SAVE PARA PAGO PK: {instance.pk} (Creado: {created}, Activo: {instance.activo}) ---")

    if not instance.activo:
        logger.info(
            "--> Pago está INACTIVO. Reajustando saldos y anulando comisiones pendientes.")
        # Lógica para cuando un pago se inactiva
        if instance.factura_id:
            actualizar_factura_post_pago(instance.factura_id)
        if instance.reclamacion_id:
            actualizar_reclamacion_post_pago(instance.reclamacion_id)

        # Anular comisiones pendientes asociadas a este pago
        comisiones_a_anular = RegistroComision.objects.filter(
            pago_cliente=instance, estatus_pago_comision='PENDIENTE')
        updated_count = comisiones_a_anular.update(
            estatus_pago_comision='ANULADA', fecha_pago_a_intermediario=None)
        if updated_count > 0:
            logger.info(
                f"--> {updated_count} comisiones pendientes ANULADAS para Pago {instance.pk}.")
        return  # Termina la ejecución si el pago no está activo

    # --- El pago está ACTIVO ---

    # Actualizar Factura o Reclamación
    if instance.factura_id:
        logger.info(
            f"--> Pago asociado a Factura {instance.factura_id}. Actualizando factura y calculando comisiones.")
        actualizar_factura_post_pago(instance.factura_id)
        # Las comisiones solo se calculan para facturas
        calcular_y_registrar_comisiones(instance)
    elif instance.reclamacion_id:
        logger.info(
            f"--> Pago asociado a Reclamación {instance.reclamacion_id}. Actualizando reclamación.")
        actualizar_reclamacion_post_pago(instance.reclamacion_id)

    # Enviar notificación solo si es un pago nuevo y activo
    if created:
        logger.info(f"--> Es un pago nuevo. Enviando notificación.")
        try:
            enviar_notificacion_creacion_pago(instance)
        except Exception as e:
            logger.error(
                f"Error al intentar enviar notificación para Pago {instance.pk}: {e}", exc_info=True)


@receiver(post_delete, sender=Pago, dispatch_uid="pago_post_delete_main_handler")
@prevent_recursion
def pago_post_delete_handler(sender, instance, **kwargs):
    """
    Handler que se ejecuta después de eliminar un Pago.
    """
    logger.info(f"--- SEÑAL POST_DELETE PARA PAGO PK: {instance.pk} ---")

    # Anular comisiones asociadas
    comisiones_afectadas = RegistroComision.objects.filter(
        pago_cliente=instance)
    updated_count = comisiones_afectadas.update(
        estatus_pago_comision='ANULADA', fecha_pago_a_intermediario=None)
    if updated_count > 0:
        logger.info(
            f"--> {updated_count} comisiones ANULADAS para Pago eliminado {instance.pk}.")

    # Reajustar saldos
    if instance.factura_id:
        actualizar_factura_post_pago(instance.factura_id)
    elif instance.reclamacion_id:
        actualizar_reclamacion_post_pago(instance.reclamacion_id)


def enviar_notificacion_creacion_pago(pago):
    """Función helper para crear y enviar notificaciones de pago."""
    monto_pago_str = f"{pago.monto_pago:.2f}" if isinstance(
        pago.monto_pago, Decimal) else str(pago.monto_pago or "0.00")
    mensaje = f"Nuevo Pago Registrado (Ref: {pago.referencia_pago or pago.pk}) por ${monto_pago_str}. "

    if pago.factura:
        mensaje += f"Asociado a Factura '{pago.factura.numero_recibo or pago.factura.pk}'."
    elif pago.reclamacion:
        mensaje += f"Asociado a Reclamación #{pago.reclamacion.pk}."


@transaction.atomic
def actualizar_factura_post_pago(factura_id):
    if not factura_id:
        return
    logger.debug(
        f"[Signal actualizar_factura] Iniciando para Factura ID: {factura_id}")
    try:
        FacturaModel = apps.get_model('myapp', 'Factura')
        PagoModel = apps.get_model('myapp', 'Pago')
        ContratoIndividualModel = apps.get_model('myapp', 'ContratoIndividual')
        ContratoColectivoModel = apps.get_model('myapp', 'ContratoColectivo')

        factura = FacturaModel.objects.select_for_update().get(pk=factura_id)
        logger.debug(
            f"[Signal actualizar_factura] Factura {factura_id} obtenida. Monto: {factura.monto}, Pendiente actual: {factura.monto_pendiente}, Pagada actual: {factura.pagada}")

        monto_total_factura = factura.monto or Decimal('0.00')
        pagada_antes_de_recalcular = factura.pagada

        total_pagado_activo = PagoModel.objects.filter(
            factura_id=factura_id, activo=True
        ).aggregate(
            total=Coalesce(Sum('monto_pago'), Decimal(
                '0.00'), output_field=DecimalField())
        )['total']
        logger.debug(
            f"[Signal actualizar_factura] Factura {factura_id}: Total pagado activo: {total_pagado_activo}")

        nuevo_pendiente = max(
            Decimal('0.00'), monto_total_factura - total_pagado_activo)
        nueva_pagada = nuevo_pendiente <= FacturaModel.TOLERANCE

        logger.debug(
            f"[Signal actualizar_factura] Factura {factura_id}: Nuevo pendiente calculado: {nuevo_pendiente}, Nueva pagada calculada: {nueva_pagada}")

        campos_a_actualizar_factura = {}
        if factura.monto_pendiente != nuevo_pendiente:
            campos_a_actualizar_factura['monto_pendiente'] = nuevo_pendiente
        if factura.pagada != nueva_pagada:
            campos_a_actualizar_factura['pagada'] = nueva_pagada

        # Determinar el nuevo estatus de la factura
        estatus_factura_calculado = factura.estatus_factura  # Mantener actual por defecto
        if nueva_pagada:
            estatus_factura_calculado = 'PAGADA'
        elif factura.estatus_factura != 'ANULADA':  # No cambiar si ya está anulada
            esta_vencida = False
            if factura.vigencia_recibo_hasta and isinstance(factura.vigencia_recibo_hasta, date):
                dias_vencimiento = getattr(
                    CommonChoices, 'DIAS_VENCIMIENTO_FACTURA', 30)
                if django_timezone.now().date() > (factura.vigencia_recibo_hasta + timedelta(days=dias_vencimiento)):
                    esta_vencida = True

            if esta_vencida:
                estatus_factura_calculado = 'VENCIDA'
            # Si estaba pagada y ya no, o generada/pendiente
            elif factura.estatus_factura in ['GENERADA', 'PENDIENTE', 'PAGADA']:
                estatus_factura_calculado = 'PENDIENTE'

        if factura.estatus_factura != estatus_factura_calculado:
            campos_a_actualizar_factura['estatus_factura'] = estatus_factura_calculado

        logger.debug(
            f"[Signal actualizar_factura] Factura {factura_id}: Campos a actualizar: {campos_a_actualizar_factura}")

        if campos_a_actualizar_factura:
            FacturaModel.objects.filter(pk=factura_id).update(
                **campos_a_actualizar_factura)
            logger.info(
                f"[Signal actualizar_factura] Factura {factura_id} actualizada con: {campos_a_actualizar_factura}")

            # === [CORRECCIÓN CLAVE] ===
            # Actualizar contador de pagos en contrato si el estado 'pagada' cambió
            contrato_pk = factura.contrato_individual_id or factura.contrato_colectivo_id
            contrato_model_class = ContratoIndividualModel if factura.contrato_individual_id else ContratoColectivoModel if factura.contrato_colectivo_id else None

            # En lugar de hasattr, comprobamos si el modelo y el pk existen.
            # El campo 'pagos_realizados' está en ambos modelos Contrato, así que la comprobación es segura.
            if contrato_pk and contrato_model_class:
                if nueva_pagada and not pagada_antes_de_recalcular:
                    contrato_model_class.objects.filter(pk=contrato_pk).update(
                        pagos_realizados=F('pagos_realizados') + 1)
                    logger.info(
                        f"[Signal] Contrato {contrato_pk} ({contrato_model_class.__name__}): Contador pagos_realizados ++.")
                elif not nueva_pagada and pagada_antes_de_recalcular:
                    contrato_model_class.objects.filter(pk=contrato_pk, pagos_realizados__gt=0).update(
                        pagos_realizados=F('pagos_realizados') - 1)
                    logger.info(
                        f"[Signal] Contrato {contrato_pk} ({contrato_model_class.__name__}): Contador pagos_realizados --.")
        else:
            logger.debug(
                f"[Signal actualizar_factura] Factura {factura_id} no requirió actualización.")

    except FacturaModel.DoesNotExist:
        logger.error(
            f"[Signal actualizar_factura] Factura {factura_id} no encontrada en BD.")
    except Exception as e:
        logger.exception(
            f"[Signal actualizar_factura] Error general para Factura ID {factura_id}: {e}")


TOLERANCE = Decimal('0.01')


@transaction.atomic
def actualizar_reclamacion_post_pago(reclamacion_id):
    """
    Actualiza el estado de una Reclamación. VERSIÓN DE DEPURACIÓN FINAL.
    """
    if not reclamacion_id:
        return

    logger.info("=============================================================")
    logger.info(
        f"== INICIANDO ACTUALIZACIÓN PARA RECLAMACIÓN ID: {reclamacion_id} ==")
    logger.info("=============================================================")

    try:
        reclamacion = Reclamacion.objects.select_for_update().get(pk=reclamacion_id)

        monto_reclamado = reclamacion.monto_reclamado or Decimal('0.00')

        # Vamos a ser explícitos con la consulta de pagos
        pagos_activos = reclamacion.pagos.filter(activo=True)
        total_pagado = pagos_activos.aggregate(
            total=Coalesce(Sum('monto_pago'), Decimal('0.00'))
        )['total']

        # LOGGING DE DIAGNÓSTICO
        logger.info(f"ESTADO ACTUAL: '{reclamacion.estado}'")
        logger.info(f"MONTO RECLAMADO: {monto_reclamado}")
        logger.info(f"PAGOS ACTIVOS ENCONTRADOS: {pagos_activos.count()}")
        for p in pagos_activos:
            logger.info(f"  -> Pago PK: {p.pk}, Monto: {p.monto_pago}")
        logger.info(f"SUMA TOTAL PAGADA CALCULADA: {total_pagado}")

        # Comprobación de la condición
        condicion_cumplida = total_pagado >= monto_reclamado - TOLERANCE
        logger.info(
            f"¿Total pagado >= Monto reclamado? -> {condicion_cumplida}")

        if condicion_cumplida:
            if reclamacion.estado not in ['PAGADA', 'CERRADA', 'ANULADA']:
                logger.warning(
                    f"¡CONDICIÓN CUMPLIDA! Actualizando estado a 'PAGADA'.")
                reclamacion.estado = 'PAGADA'
                reclamacion.fecha_cierre_reclamo = reclamacion.fecha_cierre_reclamo or timezone.now().date()
                reclamacion.save(
                    update_fields=['estado', 'fecha_cierre_reclamo'])
                logger.warning(
                    f"¡GUARDADO REALIZADO! El estado ahora debería ser 'PAGADA' en la BD.")
            else:
                logger.info(
                    f"Condición cumplida, pero el estado actual '{reclamacion.estado}' ya es final. No se hacen cambios.")
        else:
            # Lógica de reversión si es necesario
            if reclamacion.estado == 'PAGADA':
                logger.warning(
                    f"¡REVERSIÓN! El total pagado es menor. Revirtiendo estado a 'APROBADA'.")
                reclamacion.estado = 'APROBADA'
                reclamacion.fecha_cierre_reclamo = None
                reclamacion.save(
                    update_fields=['estado', 'fecha_cierre_reclamo'])
            else:
                logger.info(
                    "Condición no cumplida y estado no es 'PAGADA'. No se hacen cambios.")

    except Reclamacion.DoesNotExist:
        logger.error(
            f"ERROR CRÍTICO: Reclamación con ID {reclamacion_id} no encontrada en la señal.")
    except Exception as e:
        logger.exception(
            f"ERROR INESPERADO en la señal para Reclamación ID {reclamacion_id}: {e}")

    logger.info(
        f"== FINALIZADA ACTUALIZACIÓN PARA RECLAMACIÓN ID: {reclamacion_id} ==")
    logger.info(
        "=============================================================\n")


def prevent_recursion(signal_handler):
    def wrapper(*args, **kwargs):
        signal_name = f"{signal_handler.__module__}.{signal_handler.__name__}"
        sender_model = kwargs.get('sender', None)
        instance_pk = getattr(kwargs.get('instance'), 'pk', None)
        signal_key_parts = [signal_name]
        if sender_model:
            signal_key_parts.append(sender_model.__name__)
        if instance_pk:
            signal_key_parts.append(str(instance_pk))
        signal_key = "_".join(signal_key_parts)
        if not hasattr(_signal_stack, 'stack'):
            _signal_stack.stack = set()
        if signal_key in _signal_stack.stack:
            return
        _signal_stack.stack.add(signal_key)
        try:
            return signal_handler(*args, **kwargs)
        finally:
            _signal_stack.stack.discard(signal_key)
            if not _signal_stack.stack:
                delattr(_signal_stack, 'stack')
    return wrapper


logger = logging.getLogger(__name__)

# --- FUNCIÓN HELPER PARA CREAR NOTIFICACIONES ---


def crear_notificacion_para_usuarios_relevantes(mensaje, tipo_notif='info', url_destino=None, usuarios_destino=None, request_user=None):
    logger.info(f"[NOTIF_HELPER] Iniciando para mensaje: {mensaje[:70]}...")

    if usuarios_destino is None:
        query = Q(is_staff=True) | Q(is_superuser=True)
        target_users_qs = Usuario.objects.filter(
            query, activo=True)  # Renombrado para claridad
        if request_user and request_user.is_authenticated:
            target_users_qs = target_users_qs.exclude(pk=request_user.pk)

        # Log detallado de usuarios
        logger.info(
            f"[NOTIF_HELPER] Usuarios por defecto. QuerySet: {target_users_qs.query}")
        logger.info(
            f"[NOTIF_HELPER] Usuarios encontrados: {target_users_qs.count()}")
        # for u_idx, u_obj in enumerate(target_users_qs):
        #    logger.debug(f"[NOTIF_HELPER] Usuario {u_idx + 1}: {u_obj.email} (PK: {u_obj.pk}, Staff: {u_obj.is_staff}, Superuser: {u_obj.is_superuser}, Activo: {u_obj.activo})")
        final_target_users = target_users_qs  # Asignar al nombre final
    else:
        final_target_users = usuarios_destino
        count_log = final_target_users.count() if hasattr(
            final_target_users, 'count') else len(final_target_users)
        logger.info(
            f"[NOTIF_HELPER] Usuarios provistos. Cantidad: {count_log}")

    if not final_target_users.exists() if hasattr(final_target_users, 'exists') else not final_target_users:
        logger.warning(
            f"[NOTIF_HELPER] No se encontraron usuarios destino para la notificación: {mensaje[:70]}...")
        return

    notificaciones_a_crear = []
    for usuario_obj in final_target_users:  # Renombrado para claridad
        notificaciones_a_crear.append(
            Notificacion(
                usuario=usuario_obj,
                mensaje=mensaje,
                tipo=tipo_notif,
                url_destino=url_destino
            )
        )
    if notificaciones_a_crear:
        try:
            Notificacion.objects.bulk_create(notificaciones_a_crear)
            logger.info(
                f"Creadas {len(notificaciones_a_crear)} notificaciones: {mensaje[:70]}...")
        except Exception as e:
            logger.error(
                f"Error en bulk_create de notificaciones: {e}", exc_info=True)


# --- SEÑALES DE NOTIFICACIÓN PARA CREACIÓN DE OBJETOS ---

# 1. Usuario
@receiver(post_save, sender=Usuario)
@prevent_recursion
def notificar_creacion_usuario(sender, instance, created, **kwargs):
    if created:
        try:
            mensaje = f" Nuevo Usuario '{instance.get_full_name()}' ({instance.email}) ha sido registrado en el sistema."
            url = None
            try:
                url = reverse('myapp:usuario_detail', args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:usuario_detail' para Usuario {instance.pk}")

            # Notificar a otros admins/staff, no a sí mismo si es una auto-creación
            # (request_user no está disponible en señales post_save directamente,
            # a menos que se pase explícitamente en .save() lo cual no es común)
            # Se podría filtrar el usuario instancia si es staff/superusuario.
            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='info', url_destino=url, request_user=instance)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para Usuario {instance.pk}: {e}", exc_info=True)

# 2. Intermediario


@receiver(post_save, sender=Intermediario)
@prevent_recursion
def notificar_creacion_intermediario(sender, instance, created, **kwargs):
    if created:
        try:
            mensaje = f" Nuevo Intermediario '{instance.nombre_completo}' (Código: {instance.codigo}) ha sido añadido."
            if instance.intermediario_relacionado:
                mensaje += f" Reporta a: {instance.intermediario_relacionado.nombre_completo}."
            url = None
            try:
                url = reverse('myapp:intermediario_detail', args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:intermediario_detail' para Intermediario {instance.pk}")

            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='info', url_destino=url)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para Intermediario {instance.pk}: {e}", exc_info=True)

# 3. Tarifa


@receiver(post_save, sender=Tarifa)
@prevent_recursion
def notificar_creacion_tarifa(sender, instance, created, **kwargs):
    if created:
        try:
            mensaje = f" Nueva Tarifa '{instance.codigo_tarifa}' creada para Ramo: {instance.get_ramo_display()}, Rango Etario: {instance.get_rango_etario_display()}."
            # No hay vista de detalle para Tarifa en el frontend usualmente, pero podría haberla en el admin
            # url = reverse('admin:myapp_tarifa_change', args=[instance.pk]) # Ejemplo para admin
            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='info')  # Sin URL por ahora
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para Tarifa {instance.pk}: {e}", exc_info=True)

# 4. AfiliadoIndividual


@receiver(post_save, sender=AfiliadoIndividual)
@prevent_recursion
def notificar_creacion_afiliado_individual(sender, instance, created, **kwargs):
    if created:
        try:
            mensaje = f" Nuevo Afiliado Individual '{instance.nombre_completo}' (Cédula: {instance.cedula}) ha sido registrado."
            url = None
            try:
                url = reverse('myapp:afiliado_individual_detail',
                              args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:afiliado_individual_detail' para AfiliadoInd {instance.pk}")

            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='info', url_destino=url)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para AfiliadoIndividual {instance.pk}: {e}", exc_info=True)

# 5. AfiliadoColectivo


@receiver(post_save, sender=AfiliadoColectivo)
@prevent_recursion
def notificar_creacion_afiliado_colectivo(sender, instance, created, **kwargs):
    if created:
        try:
            mensaje = f" Nuevo Afiliado Colectivo '{instance.razon_social}' (RIF: {instance.rif}) ha sido registrado."
            url = None
            try:
                url = reverse('myapp:afiliado_colectivo_detail',
                              args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:afiliado_colectivo_detail' para AfiliadoCol {instance.pk}")

            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='info', url_destino=url)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para AfiliadoColectivo {instance.pk}: {e}", exc_info=True)

# 6. ContratoIndividual


@receiver(post_save, sender=ContratoIndividual)
@prevent_recursion
def notificar_creacion_contrato_individual(sender, instance, created, **kwargs):
    if created:
        try:
            afiliado_info = "N/A"
            if instance.afiliado:
                afiliado_info = f"'{instance.afiliado.nombre_completo}' ({instance.afiliado.cedula})"
            mensaje = f" Nuevo Contrato Individual '{instance.numero_contrato}' creado para el afiliado {afiliado_info}."
            url = None
            try:
                url = reverse('myapp:contrato_individual_detail',
                              args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:contrato_individual_detail' para ContratoInd {instance.pk}")

            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='success', url_destino=url)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para ContratoIndividual {instance.pk}: {e}", exc_info=True)

# 7. ContratoColectivo


@receiver(post_save, sender=ContratoColectivo)
@prevent_recursion
def notificar_creacion_contrato_colectivo(sender, instance, created, **kwargs):
    if created:
        try:
            mensaje = f" Nuevo Contrato Colectivo '{instance.numero_contrato}' creado para la empresa '{instance.razon_social or 'N/A'}'."
            url = None
            try:
                url = reverse('myapp:contrato_colectivo_detail',
                              args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:contrato_colectivo_detail' para ContratoCol {instance.pk}")

            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='success', url_destino=url)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para ContratoColectivo {instance.pk}: {e}", exc_info=True)

# 8. Factura


@receiver(post_save, sender=Factura)
@prevent_recursion
def notificar_creacion_factura(sender, instance, created, **kwargs):
    if created:
        try:
            contrato_info = ""
            if instance.contrato_individual:
                contrato_info = f"Contrato Individual '{instance.contrato_individual.numero_contrato or instance.contrato_individual.pk}'"
            elif instance.contrato_colectivo:
                contrato_info = f"Contrato Colectivo '{instance.contrato_colectivo.numero_contrato or instance.contrato_colectivo.pk}'"

            mensaje = f" Nueva Factura '{instance.numero_recibo}' (Monto: {instance.monto or '0.00'}) generada para {contrato_info}."
            url = None
            try:
                url = reverse('myapp:factura_detail', args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:factura_detail' para Factura {instance.pk}")

            crear_notificacion_para_usuarios_relevantes(
                mensaje=mensaje, tipo_notif='info', url_destino=url)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para Factura {instance.pk}: {e}", exc_info=True)

# 9. Reclamacion


@receiver(post_save, sender=Reclamacion)
@prevent_recursion
def notificar_creacion_reclamacion(sender, instance, created, **kwargs):
    if created:
        try:
            contrato_info = "N/A"
            if instance.contrato_individual:
                contrato_info = f"Contrato Individual '{instance.contrato_individual.numero_contrato or instance.contrato_individual.pk}'"
            elif instance.contrato_colectivo:
                contrato_info = f"Contrato Colectivo '{instance.contrato_colectivo.numero_contrato or instance.contrato_colectivo.pk}'"

            mensaje = f" Nueva Reclamación #{instance.pk} (Monto: {instance.monto_reclamado or '0.00'}) registrada para {contrato_info}."
            url = None
            try:
                url = reverse('myapp:reclamacion_detail', args=[instance.pk])
            except NoReverseMatch:
                logger.warning(
                    f"No se encontró URL 'myapp:reclamacion_detail' para Reclamacion {instance.pk}")

            crear_notificacion_para_usuarios_relevantes(
                # Warning porque requiere atención
                mensaje=mensaje, tipo_notif='warning', url_destino=url)
        except Exception as e:
            logger.error(
                f"Error en señal de notificación para Reclamacion {instance.pk}: {e}", exc_info=True)

# 10. Pago (El de comisiones ya está en pago_post_save_handler)


# Usar un logger específico para señales si quieres
logger_signals = logging.getLogger(__name__)


def sanear_para_log(mensaje_str: str, encoding='cp1252', errors='replace') -> str:
    """
    Sanea una cadena para el logging, reemplazando caracteres que no se pueden
    codificar en la codificación especificada (típicamente la de la consola/archivo de log).

    Args:
        mensaje_str (str): La cadena original a sanear.
        encoding (str): La codificación objetivo (ej. 'cp1252' para consola Windows, 'utf-8').
        errors (str): Cómo manejar errores de codificación ('replace', 'ignore', 'xmlcharrefreplace').

    Returns:
        str: La cadena saneada.
    """
    if not isinstance(mensaje_str, str):
        try:
            mensaje_str = str(mensaje_str)  # Intentar convertir a string
        except Exception:
            return "[DATO NO REPRESENTABLE EN LOG]"

    try:
        # Primero intenta codificar a la codificación deseada, manejando errores,
        # y luego decodifica de nuevo a string. Esto efectúa el reemplazo/ignorado.
        return mensaje_str.encode(encoding, errors=errors).decode(encoding)
    except Exception as e:
        # Fallback muy genérico si incluso la sanitización falla
        logger_signals.error(
            f"Error excepcional durante sanear_para_log para encoding '{encoding}': {e}")
        # Devolver una versión muy simplificada del string original sin caracteres problemáticos
        return "".join(c if ord(c) < 128 else '?' for c in mensaje_str)


@receiver(post_save, sender=Factura, dispatch_uid="actualizar_contador_pagos_contrato")
def actualizar_contador_pagos_contrato(sender, instance, **kwargs):
    """
    Señal que se dispara cada vez que una Factura se guarda.
    Su única responsabilidad es recalcular y actualizar el campo `pagos_realizados`
    en el Contrato asociado. Este es el enfoque más robusto.
    """
    factura = instance
    contrato = factura.contrato_individual or factura.contrato_colectivo

    if not contrato:
        return

    try:
        # Contamos directamente en la BD cuántas facturas de este contrato están pagadas.
        with transaction.atomic():
            numero_facturas_pagadas = Factura.objects.filter(
                contrato_individual_id=contrato.pk if isinstance(
                    contrato, ContratoIndividual) else None,
                contrato_colectivo_id=contrato.pk if isinstance(
                    contrato, ContratoColectivo) else None,
                pagada=True,
                activo=True
            ).count()

            # Comparamos con el valor actual para evitar escrituras innecesarias
            if contrato.pagos_realizados != numero_facturas_pagadas:
                contrato_model = type(contrato)
                contrato_model.objects.filter(pk=contrato.pk).update(
                    pagos_realizados=numero_facturas_pagadas)
                logger.info(
                    f"[SEÑAL] Contador de pagos para Contrato {contrato.pk} actualizado a: {numero_facturas_pagadas}")

    except Exception as e:
        logger.error(
            f"Error en la señal actualizar_contador_pagos_contrato para Factura {factura.pk}: {e}", exc_info=True)
