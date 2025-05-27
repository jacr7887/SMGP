# myapp/management/commands/revisar_vencimientos_contratos.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Q
from myapp.models import ContratoIndividual, ContratoColectivo, Usuario, Notificacion
from myapp.notifications import crear_notificacion
import logging
# <--- Esto está bien, le diste un alias
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Revisa contratos individuales y colectivos por vencer y genera notificaciones.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias_anticipacion',
            type=int,
            default=30,
            help='Número de días de antelación para notificar vencimientos.'
        )
        parser.add_argument(
            '--dias_repite_notif',
            type=int,
            default=7,
            help='Número de días antes de repetir una notificación de vencimiento para el mismo contrato.'
        )

    def handle(self, *args, **options):
        dias_anticipacion = options['dias_anticipacion']
        dias_repite_notif = options['dias_repite_notif']

        hoy = django_timezone.now().date()
        fecha_limite_vencimiento = hoy + timedelta(days=dias_anticipacion)

        self.stdout.write(
            f"Iniciando revisión de vencimientos de contratos (anticipación: {dias_anticipacion} días, no repetir antes de {dias_repite_notif} días)...")
        logger.info(
            f"Comando revisar_vencimientos_contratos: Iniciando con {dias_anticipacion} días de anticipación y {dias_repite_notif} días de no repetición.")

        notificaciones_creadas_total = 0

        # --- Contratos Individuales por Vencer ---
        contratos_ind_por_vencer = ContratoIndividual.objects.filter(
            activo=True,
            estatus='VIGENTE',
            fecha_fin_vigencia__gte=hoy,  # <--- CORREGIDO
            fecha_fin_vigencia__lte=fecha_limite_vencimiento  # <--- CORREGIDO
        ).select_related('intermediario', 'afiliado')

        logger.info(
            f"Encontrados {contratos_ind_por_vencer.count()} Contratos Individuales por vencer.")

        for contrato in contratos_ind_por_vencer:
            mensaje = (f"Alerta Vencimiento: Contrato Individual '{contrato.numero_contrato}' "
                       f"para '{contrato.afiliado.nombre_completo if contrato.afiliado else 'N/A'}' "
                       f"vence el {contrato.fecha_fin_vigencia.strftime('%d/%m/%Y')}.")

            notif_reciente_existe = Notificacion.objects.filter(
                mensaje__icontains=f"Contrato Individual '{contrato.numero_contrato}'"
            ).filter(
                mensaje__icontains="vence el"
            ).filter(
                tipo='warning',
                fecha_creacion__gte=timezone.now() - timedelta(days=dias_repite_notif)
            ).exists()

            if notif_reciente_existe:
                logger.info(
                    f"CI {contrato.numero_contrato}: Notificación de vencimiento ya enviada en los últimos {dias_repite_notif} días. Omitiendo.")
                continue

            usuarios_a_notificar_pks = set()
            superadmins_pks = Usuario.objects.filter(
                is_superuser=True, activo=True).values_list('pk', flat=True)
            usuarios_a_notificar_pks.update(superadmins_pks)

            if contrato.intermediario:
                usuarios_intermediario_pks = Usuario.objects.filter(
                    intermediario=contrato.intermediario, activo=True).values_list('pk', flat=True)
                usuarios_a_notificar_pks.update(usuarios_intermediario_pks)

            usuarios_obj_destino = Usuario.objects.filter(
                pk__in=list(usuarios_a_notificar_pks))

            if usuarios_obj_destino.exists():
                notifs_creadas_ahora = crear_notificacion(
                    usuario_destino=usuarios_obj_destino,
                    mensaje=mensaje,
                    tipo='warning',
                    url_path_name='myapp:contrato_individual_detail',
                    url_kwargs={'pk': contrato.pk}
                )
                if notifs_creadas_ahora:
                    notificaciones_creadas_total += len(notifs_creadas_ahora)
                    logger.info(
                        f"CI {contrato.numero_contrato}: Notificación de vencimiento creada para {len(notifs_creadas_ahora)} usuarios.")
            else:
                logger.warning(
                    f"CI {contrato.numero_contrato}: No se encontraron usuarios para notificar sobre vencimiento.")

        # --- Contratos Colectivos por Vencer ---
        contratos_col_por_vencer = ContratoColectivo.objects.filter(
            activo=True,
            estatus='VIGENTE',
            fecha_fin_vigencia__gte=hoy,  # <--- CORREGIDO
            fecha_fin_vigencia__lte=fecha_limite_vencimiento  # <--- CORREGIDO
        ).select_related('intermediario')

        logger.info(
            f"Encontrados {contratos_col_por_vencer.count()} Contratos Colectivos por vencer.")

        for contrato in contratos_col_por_vencer:
            mensaje = (f"Alerta Vencimiento: Contrato Colectivo '{contrato.numero_contrato}' "
                       f"para '{contrato.razon_social or 'N/A'}' "
                       f"vence el {contrato.fecha_fin_vigencia.strftime('%d/%m/%Y')}.")

            notif_reciente_existe = Notificacion.objects.filter(
                mensaje__icontains=f"Contrato Colectivo '{contrato.numero_contrato}'"
            ).filter(
                mensaje__icontains="vence el"
            ).filter(
                tipo='warning',
                fecha_creacion__gte=timezone.now() - timedelta(days=dias_repite_notif)
            ).exists()

            if notif_reciente_existe:
                logger.info(
                    f"CC {contrato.numero_contrato}: Notificación de vencimiento ya enviada en los últimos {dias_repite_notif} días. Omitiendo.")
                continue

            usuarios_a_notificar_pks = set()
            superadmins_pks = Usuario.objects.filter(
                is_superuser=True, activo=True).values_list('pk', flat=True)
            usuarios_a_notificar_pks.update(superadmins_pks)

            if contrato.intermediario:
                usuarios_intermediario_pks = Usuario.objects.filter(
                    intermediario=contrato.intermediario, activo=True).values_list('pk', flat=True)
                usuarios_a_notificar_pks.update(usuarios_intermediario_pks)

            usuarios_obj_destino = Usuario.objects.filter(
                pk__in=list(usuarios_a_notificar_pks))

            if usuarios_obj_destino.exists():
                notifs_creadas_ahora = crear_notificacion(
                    usuario_destino=usuarios_obj_destino,
                    mensaje=mensaje,
                    tipo='warning',
                    url_path_name='myapp:contrato_colectivo_detail',
                    url_kwargs={'pk': contrato.pk}
                )
                if notifs_creadas_ahora:
                    notificaciones_creadas_total += len(notifs_creadas_ahora)
                    logger.info(
                        f"CC {contrato.numero_contrato}: Notificación de vencimiento creada para {len(notifs_creadas_ahora)} usuarios.")
            else:
                logger.warning(
                    f"CC {contrato.numero_contrato}: No se encontraron usuarios para notificar sobre vencimiento.")

        self.stdout.write(self.style.SUCCESS(
            f"Revisión completada. Se generaron {notificaciones_creadas_total} nuevas notificaciones de vencimiento de contratos."))
        logger.info(
            f"Comando revisar_vencimientos_contratos: Finalizado. Total {notificaciones_creadas_total} notificaciones de vencimiento generadas.")
