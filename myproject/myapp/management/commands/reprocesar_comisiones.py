# myapp/management/commands/reprocesar_comisiones.py

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from myapp.models import Pago, RegistroComision
# Importamos la función de lógica de negocio que ya funciona
from myapp.signals import calcular_y_registrar_comisiones

# Configurar un logger específico para este comando
logger = logging.getLogger('comandos_gestion')


class Command(BaseCommand):
    help = (
        'Reprocesa las comisiones para pagos existentes que no las tengan generadas. '
        'Puede operar sobre pagos específicos, todos los pagos, o los de las últimas X horas.'
    )

    def add_arguments(self, parser):
        # Opción para reprocesar TODOS los pagos con factura
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Reprocesa las comisiones para TODOS los pagos asociados a una factura.',
        )
        # Opción para reprocesar pagos por IDs específicos
        parser.add_argument(
            '--pago_ids',
            nargs='+',
            type=int,
            help='Una lista de IDs de Pagos específicos para reprocesar. Ejemplo: --pago_ids 1130 1134',
        )
        # Opción para reprocesar pagos recientes
        parser.add_argument(
            '--horas_recientes',
            type=int,
            help='Reprocesa los pagos creados en las últimas X horas.',
        )
        # Opción para forzar el borrado de comisiones existentes antes de recalcular
        parser.add_argument(
            '--forzar',
            action='store_true',
            help='Borra las comisiones existentes para los pagos seleccionados antes de recalcular. ¡USAR CON PRECAUCIÓN!',
        )

    def handle(self, *args, **options):
        """
        Lógica principal del comando.
        """
        pago_ids = options['pago_ids']
        todos = options['todos']
        horas_recientes = options['horas_recientes']
        forzar = options['forzar']

        if not any([pago_ids, todos, horas_recientes]):
            self.stdout.write(self.style.ERROR(
                'Error: Debes proporcionar una opción. Usa --pago_ids, --todos, o --horas_recientes.'
            ))
            self.stdout.write('Usa --help para más información.')
            return

        # Construir el queryset base
        queryset = Pago.objects.filter(factura__isnull=False, activo=True)

        if pago_ids:
            queryset = queryset.filter(pk__in=pago_ids)
            self.stdout.write(
                f"Se procesarán {queryset.count()} pagos por los IDs proporcionados: {pago_ids}")
        elif horas_recientes:
            from django.utils import timezone
            from datetime import timedelta
            tiempo_limite = timezone.now() - timedelta(hours=horas_recientes)
            queryset = queryset.filter(fecha_creacion__gte=tiempo_limite)
            self.stdout.write(
                f"Se procesarán {queryset.count()} pagos de las últimas {horas_recientes} horas.")
        elif todos:
            self.stdout.write(self.style.WARNING(
                'Se procesarán TODOS los pagos. Esto puede tardar.'))

        if not queryset.exists():
            self.stdout.write(self.style.SUCCESS(
                'No se encontraron pagos que coincidan con los criterios. Nada que hacer.'))
            return

        # Bucle principal de procesamiento
        comisiones_creadas = 0
        comisiones_borradas = 0
        pagos_procesados = 0

        for pago in queryset.iterator():
            self.stdout.write(f"Procesando Pago ID: {pago.pk}...")

            try:
                with transaction.atomic():
                    # Si se usa la opción --forzar, se borran las comisiones existentes
                    if forzar:
                        comisiones_existentes = RegistroComision.objects.filter(
                            pago_cliente=pago)
                        count, _ = comisiones_existentes.delete()
                        if count > 0:
                            comisiones_borradas += count
                            self.stdout.write(
                                f"  -> Se borraron {count} comisiones existentes (opción --forzar).")

                    # Llamar a la lógica de negocio centralizada
                    # La función `calcular_y_registrar_comisiones` ya usa get_or_create,
                    # por lo que no creará duplicados a menos que se use --forzar.
                    calcular_y_registrar_comisiones(pago)
                    pagos_procesados += 1

            except Exception as e:
                raise CommandError(
                    f"Error procesando el Pago ID {pago.pk}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"\n¡Proceso completado! "
            f"Pagos revisados: {pagos_procesados}. "
            f"Comisiones borradas (si se forzó): {comisiones_borradas}."
        ))
