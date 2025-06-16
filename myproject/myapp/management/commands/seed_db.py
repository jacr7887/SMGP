# myapp/management/commands/seed_db.py

import random
import logging
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date, timedelta, datetime  # Python's datetime
import collections

from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone  # <--- IMPORTANTE
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models.deletion import ProtectedError
from django.db.models import Sum, Q, DecimalField, F
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, post_delete

try:
    from faker import Faker
except ImportError:
    Faker = None

# Importar los handlers de señales específicos
from myapp.signals import (
    pago_post_save_handler,
    pago_post_delete_handler,
)
from myapp.models import (
    LicenseInfo, Notificacion, AfiliadoIndividual, AfiliadoColectivo,
    Intermediario, ContratoIndividual, ContratoColectivo, Factura,
    Reclamacion, Pago, Tarifa, AuditoriaSistema, RegistroComision
)
from myapp.commons import CommonChoices

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populates the database with mock data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Borra los datos existentes antes de poblar la base de datos.'
        )
        # Valores multiplicados por 5
        parser.add_argument('--users', type=int, default=150)  # Original: 30
        parser.add_argument('--intermediarios', type=int,
                            default=75)   # Original: 15
        parser.add_argument('--afiliados_ind', type=int,
                            default=150)  # Original: 30
        parser.add_argument('--afiliados_col', type=int,
                            default=75)   # Original: 15
        parser.add_argument('--tarifas', type=int, default=150)  # Original: 30
        parser.add_argument('--contratos_ind', type=int,
                            default=120)  # Original: 24
        parser.add_argument('--contratos_col', type=int,
                            default=60)   # Original: 12
        parser.add_argument('--facturas', type=int,
                            default=300)  # Original: 60
        parser.add_argument('--reclamaciones', type=int,
                            default=150)  # Original: 30
        parser.add_argument('--pagos', type=int, default=225)  # Original: 45
        parser.add_argument('--notificaciones', type=int,
                            default=300)  # Original: 60
        parser.add_argument('--auditorias', type=int,
                            default=300)  # Original: 60

        parser.add_argument('--igtf_chance', type=int, default=20,
                            choices=range(0, 101), metavar="[0-100]")
        parser.add_argument('--pago_parcial_chance',
                            type=int, default=40, metavar="[0-100]")

    def _initialize_stats(self, options):
        stats = collections.defaultdict(
            lambda: {'requested': 0, 'created': 0, 'failed': 0, 'errors': collections.Counter()})
        stats['LicenseInfo']['requested'] = 1

        stats['Tarifa']['requested'] = options.get('tarifas')
        stats['User']['requested'] = options.get('users')
        stats['Intermediario']['requested'] = options.get('intermediarios')
        stats['AfiliadoIndividual']['requested'] = options.get('afiliados_ind')
        stats['AfiliadoColectivo']['requested'] = options.get('afiliados_col')
        stats['ContratoIndividual']['requested'] = options.get('contratos_ind')
        stats['ContratoColectivo']['requested'] = options.get('contratos_col')
        stats['Factura']['requested'] = options.get('facturas')
        stats['Reclamacion']['requested'] = options.get('reclamaciones')
        stats['Pago']['requested'] = options.get('pagos')
        stats['Notificacion']['requested'] = options.get('notificaciones')
        stats['AuditoriaSistema']['requested'] = options.get('auditorias')

        # CORRECCIÓN FINAL: Aseguramos que se soliciten comisiones
        stats['RegistroComision']['requested'] = options.get('pagos')

        return stats

    def _disconnect_signals_for_clean(self):
        # ... (tu código actual para _disconnect_signals_for_clean, sin cambios) ...
        disconnected_info = []
        signals_to_manage = [
            (post_delete, pago_post_delete_handler, Pago),
        ]
        for signal_type, handler, sender_model in signals_to_manage:
            try:
                was_disconnected = signal_type.disconnect(
                    receiver=handler, sender=sender_model)
                if was_disconnected:
                    self.stdout.write(self.style.NOTICE(
                        f"    Disconnected {handler.__name__} from {sender_model.__name__}."))
                    disconnected_info.append(
                        {'signal': signal_type, 'receiver': handler, 'sender': sender_model})
                else:
                    self.stdout.write(self.style.WARNING(
                        f"    Signal {handler.__name__} for {sender_model.__name__} was not found or already disconnected."))
            except Exception as e_disc:
                self.stdout.write(self.style.ERROR(
                    f"    ERROR during disconnect of {handler.__name__} from {sender_model.__name__}: {e_disc}"))
        return disconnected_info

    def _reconnect_signals(self, disconnected_signals_info):
        # ... (tu código actual para _reconnect_signals, sin cambios) ...
        self.stdout.write(self.style.NOTICE(
            "  Signal reconnection will be handled by Django's AppConfig.ready() on next full app load."))

    def _get_aware_fake_datetime(self, fake_instance, start_date_aware=None, end_date_aware=None, default_start_days_ago=730):
        # ... (tu código actual para _get_aware_fake_datetime, sin cambios) ...
        current_tz = timezone.get_current_timezone()
        if start_date_aware and timezone.is_naive(start_date_aware):
            start_date_aware = timezone.make_aware(
                start_date_aware, current_tz)
        if end_date_aware and timezone.is_naive(end_date_aware):
            end_date_aware = timezone.make_aware(end_date_aware, current_tz)
        if start_date_aware:
            naive_start = start_date_aware.astimezone(
                current_tz).replace(tzinfo=None)
        else:
            naive_start = (datetime.now() -
                           timedelta(days=default_start_days_ago))
        if end_date_aware:
            naive_end = end_date_aware.astimezone(
                current_tz).replace(tzinfo=None)
        else:
            naive_end = datetime.now()
        if naive_start > naive_end:
            naive_start = naive_end - timedelta(days=1)
        try:
            naive_dt = fake_instance.date_time_between(
                start_date=naive_start, end_date=naive_end)
        except Exception as e:
            logger.warning(
                f"Faker date_time_between falló ({e}), usando past_datetime como fallback.")
            naive_dt = fake_instance.past_datetime(
                start_date=f"-{default_start_days_ago}d")
        return timezone.make_aware(naive_dt, current_tz)

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting database seeding..."))

        if Faker is None:
            self.stderr.write(self.style.ERROR(
                "Faker not found. pip install Faker"))
            return

        faker_locale = 'es_ES'
        try:
            fake = Faker(faker_locale)
        except Exception:
            self.stderr.write(self.style.ERROR(
                f"Faker locale '{faker_locale}' failed. Trying 'en_US'."))
            fake = Faker('en_US')

        # Acceder a las opciones de forma segura usando .get() con los defaults de add_arguments
        # action='store_true' por defecto es False si no se pasa
        should_clean = options.get('clean', False)

        # Inicializar stats DESPUÉS de haber recuperado las opciones de forma segura si es necesario,
        # o pasar `options` a `_initialize_stats` y que use .get() internamente (como se hizo arriba).
        stats = self._initialize_stats(options)

        # Recuperar otras opciones para usarlas directamente en handle si es necesario
        igtf_chance = options.get('igtf_chance', 20)
        pago_parcial_chance = options.get('pago_parcial_chance', 40)
        # No es necesario recuperar todas las opciones numéricas aquí si solo se usan en _initialize_stats

        user_ids_created, intermediario_ids_created, afiliado_ind_ids_created, afiliado_col_ids_created = [], [], [], []
        tarifa_ids_created, contrato_ind_ids_created, contrato_col_ids_created = [], [], []
        factura_ids_created, reclamacion_ids_created, pago_ids_created = [], [], []

        user_ids_db, intermediario_ids_db, afiliado_ind_ids_db, afiliado_col_ids_db = [], [], [], []
        tarifa_ids_db, contrato_ind_ids_db, contrato_col_ids_db = [], [], []
        factura_ids_db, reclamacion_ids_db, pago_ids_db = [], [], []

        if should_clean:  # Usar la variable recuperada de forma segura
            self.stdout.write(self.style.WARNING(
                "Attempting to delete existing data in specific order..."))
            disconnected_signals_info = []
            clean_failed = False
            try:
                disconnected_signals_info = self._disconnect_signals_for_clean()
                with transaction.atomic():
                    # ... (tu lógica de borrado detallada, sin cambios)
                    models_to_delete_ordered = [
                        (Notificacion, "Notificacion"), (AuditoriaSistema,
                                                         "AuditoriaSistema"),
                        (RegistroComision, "RegistroComision"), (Pago, "Pago"),
                        (Factura, "Factura"), (Reclamacion, "Reclamacion")
                    ]
                    for model_class, model_name_str in models_to_delete_ordered:
                        self.stdout.write(
                            f"  Deleting {model_name_str} objects...")
                        model_class.objects.all().delete()

                    self.stdout.write(
                        "  Deleting M2M for ContratoColectivo.afiliados_colectivos...")
                    if hasattr(ContratoColectivo.afiliados_colectivos, 'through') and ContratoColectivo.afiliados_colectivos.through._meta.auto_created:
                        ContratoColectivo.afiliados_colectivos.through.objects.all().delete()

                    self.stdout.write(
                        "  Deleting ContratoIndividual objects...")
                    ContratoIndividual.objects.all().delete()
                    self.stdout.write(
                        "  Deleting ContratoColectivo objects...")
                    ContratoColectivo.objects.all().delete()

                    self.stdout.write(
                        "  Deleting AfiliadoIndividual objects...")
                    AfiliadoIndividual.objects.all().delete()
                    self.stdout.write(
                        "  Deleting AfiliadoColectivo objects...")
                    AfiliadoColectivo.objects.all().delete()

                    self.stdout.write(
                        "  Deleting M2M for Intermediario.usuarios...")
                    if hasattr(Intermediario.usuarios, 'through') and Intermediario.usuarios.through._meta.auto_created:
                        Intermediario.usuarios.through.objects.all().delete()
                    self.stdout.write("  Deleting Intermediario objects...")
                    Intermediario.objects.all().delete()

                    self.stdout.write("  Deleting Tarifa objects...")
                    Tarifa.objects.all().delete()

                    self.stdout.write(
                        "  Deleting User objects (excluding specified superuser)...")
                    User.objects.filter(is_superuser=False).delete()
                    # Asumiendo que este es el admin que quieres mantener o recrear
                    User.objects.filter(is_superuser=True,
                                        email='admin@example.com').delete()

                    self.stdout.write("  Deleting LicenseInfo objects...")
                    LicenseInfo.objects.all().delete()

                self.stdout.write(self.style.SUCCESS(
                    "Existing data deleted successfully."))
            except ProtectedError as e_protected:
                self.stderr.write(self.style.ERROR(
                    f"\nCLEAN FAILED (ProtectedError): {e_protected}"))
                logger.exception("ProtectedError during clean phase")
                clean_failed = True
            except Exception as e_clean:
                self.stderr.write(self.style.ERROR(
                    f"\nUNEXPECTED ERROR during clean: {e_clean}"))
                logger.exception("Unexpected error during clean phase")
                clean_failed = True
            finally:
                self._reconnect_signals(disconnected_signals_info)
                if clean_failed:
                    self.stderr.write(self.style.ERROR(
                        "Exiting due to errors during clean phase."))
                    return
        else:
            user_ids_db = list(User.objects.values_list('pk', flat=True))
            intermediario_ids_db = list(
                Intermediario.objects.values_list('pk', flat=True))
            afiliado_ind_ids_db = list(
                AfiliadoIndividual.objects.values_list('pk', flat=True))
            afiliado_col_ids_db = list(
                AfiliadoColectivo.objects.values_list('pk', flat=True))
            tarifa_ids_db = list(Tarifa.objects.values_list('pk', flat=True))
            contrato_ind_ids_db = list(
                ContratoIndividual.objects.values_list('pk', flat=True))
            contrato_col_ids_db = list(
                ContratoColectivo.objects.values_list('pk', flat=True))
            factura_ids_db = list(Factura.objects.values_list('pk', flat=True))
            reclamacion_ids_db = list(
                Reclamacion.objects.values_list('pk', flat=True))
            pago_ids_db = list(Pago.objects.values_list('pk', flat=True))

        # --- Funciones generadoras (sin cambios significativos aquí, el cambio es en la llamada) ---
        def generate_rif(
        ): return f"{random.choice(['J', 'G', 'V', 'E', 'P'])}-{fake.numerify('########')}-{fake.numerify('#')}"
        def generate_cedula(
        ): return f"{random.choice(['V', 'E'])}-{fake.numerify('#' * random.choice([7, 8]))}"

        def generate_phone_ve(): prefix = random.choice(['0412', '0414', '0416', '0424', '0426'] if random.random(
        ) > 0.3 else [f"02{fake.numerify('##')}"]); return f"{prefix}-{fake.numerify('#######')}"

        def generate_historial_contrato():  # Esta función ya usa timezone.get_current_timezone()
            historial = []
            num_entries = random.randint(0, 2) if fake.boolean(
                chance_of_getting_true=30) else 0
            ids_for_historial = list(set(user_ids_created + user_ids_db))
            for _ in range(num_entries):
                campo = random.choice(
                    ['suma_asegurada', 'estatus', 'forma_pago', 'plan_contratado'])
                val_ant = str(fake.pydecimal(left_digits=5, right_digits=2)
                              ) if campo == 'suma_asegurada' else fake.word()
                val_nue = str(fake.pydecimal(left_digits=5, right_digits=2)
                              ) if campo == 'suma_asegurada' else fake.word()
                usuario_id_historial = random.choice(
                    ids_for_historial) if ids_for_historial else None
                # FAKER USA AWARE DATETIME SI tzinfo ESTÁ PRESENTE
                historial_timestamp = fake.past_datetime(
                    start_date="-1y", tzinfo=timezone.get_current_timezone())
                historial.append({'timestamp': historial_timestamp.isoformat(
                ), 'usuario_id': usuario_id_historial, 'campo': campo, 'anterior': val_ant, 'nuevo': val_nue, 'motivo': fake.sentence(nb_words=4)})
            return historial

        def get_random_pk_from_lists(created_list, db_list, allow_none=False, model_name_for_error="Entidad"):
            candidate_pks = list(set(created_list + db_list))
            if not candidate_pks:
                if allow_none:
                    return None
                logger.warning(
                    f"Seeder Warning: Lista de PKs para '{model_name_for_error}' está vacía. Devolviendo None.")
                return None
            choices_list = candidate_pks[:]
            if allow_none:
                choices_list.append(None)
            return random.choice(choices_list)

        self.stdout.write(self.style.NOTICE("Starting data creation phase..."))
        try:
            with transaction.atomic():
                # --- 1. License Info ---
                # --- 1. License Info ---
                model_name = 'LicenseInfo'
                stats_m = stats[model_name]

                fecha_actual = timezone.localdate()
                fecha_expiracion_7_dias = fecha_actual + timedelta(days=7)
                nueva_license_key = fake.uuid4()

                logger.info(
                    f"--- seed_db: Intentando asegurar LicenseInfo con ID {LicenseInfo.SINGLETON_ID} ---")
                logger.info(
                    f"--- seed_db: Nueva license_key: {nueva_license_key}, Nueva expiry_date: {fecha_expiracion_7_dias} ---")

                try:
                    # Intentar obtener la instancia única.
                    # El método save() del modelo se encargará de forzar pk=SINGLETON_ID.
                    # El método clean() del modelo se encargará de la unicidad.
                    license_obj, created = LicenseInfo.objects.get_or_create(
                        # Usar pk en lugar de id para get_or_create es más estándar
                        pk=LicenseInfo.SINGLETON_ID,
                        defaults={
                            'license_key': nueva_license_key,
                            'expiry_date': fecha_expiracion_7_dias
                        }
                    )

                    if created:
                        # Ya se creó con los defaults, no es necesario guardar de nuevo a menos que modifiques más.
                        self.stdout.write(self.style.SUCCESS(
                            f"  {model_name}: Licencia de prueba CREADA, expira el {fecha_expiracion_7_dias}."))
                        logger.info(
                            f"--- seed_db: LicenseInfo CREADA (PK: {license_obj.pk}), expira: {fecha_expiracion_7_dias} ---")
                    else:
                        # Si ya existía, actualizamos los campos necesarios.
                        logger.info(
                            f"--- seed_db: LicenseInfo ENCONTRADA (PK: {license_obj.pk}). Actualizando...")
                        license_obj.license_key = nueva_license_key
                        license_obj.expiry_date = fecha_expiracion_7_dias
                        # Esto llamará a tu save() personalizado que fuerza el PK.
                        license_obj.save()
                        self.stdout.write(self.style.SUCCESS(
                            f"  {model_name}: Licencia de prueba ACTUALIZADA, expira el {fecha_expiracion_7_dias}."))
                        logger.info(
                            f"--- seed_db: LicenseInfo ACTUALIZADA (PK: {license_obj.pk}), expira: {fecha_expiracion_7_dias} ---")

                    stats_m['created'] += 1

                except ValidationError as ve:  # Capturar ValidationError de tu método clean()
                    logger.error(
                        f"--- seed_db: ValidationError creando/actualizando {model_name}: {ve} ---", exc_info=True)
                    stats_m['failed'] += 1
                    stats_m['errors']["ValidationError_LicenseInfo"] += 1
                    self.stderr.write(self.style.ERROR(
                        f"  Error de validación con {model_name}: {ve}"))
                except IntegrityError as ie:  # Por si unique=True en license_key causa problemas
                    logger.error(
                        f"--- seed_db: IntegrityError creando/actualizando {model_name}: {ie} ---", exc_info=True)
                    stats_m['failed'] += 1
                    stats_m['errors']["IntegrityError_LicenseInfo"] += 1
                    self.stderr.write(self.style.ERROR(
                        f"  Error de integridad con {model_name}: {ie}"))
                except Exception as e_lic:  # Captura general para otros errores
                    logger.error(
                        f"--- seed_db: ERROR GENERAL creando/actualizando {model_name}: {e_lic} ---", exc_info=True)
                    stats_m['failed'] += 1
                    stats_m['errors'][e_lic.__class__.__name__ +
                                      "_LicenseInfo_Gen"] += 1
                    self.stderr.write(self.style.ERROR(
                        f"  Error con {model_name}: {e_lic}"))

                # --- 2. Tarifas ---
                model_name = 'Tarifa'
                stats_m = stats[model_name]
                if stats_m['requested'] > 0:
                    possible_ramos = [c[0] for c in CommonChoices.RAMO]
                    possible_rangos = [c[0]
                                       for c in CommonChoices.RANGO_ETARIO]
                    possible_fraccionamientos = [
                        None] + [c[0] for c in CommonChoices.FORMA_PAGO if c[0] != 'CONTADO']
                    for _ in range(stats_m['requested']):
                        try:
                            ramo = random.choice(possible_ramos)
                            rango = random.choice(possible_rangos)
                            fecha_app = fake.past_date(
                                start_date="-3y")  # DateField
                            tipo_f = random.choice(possible_fraccionamientos)
                            defaults = {
                                'monto_anual': fake.pydecimal(left_digits=6, right_digits=2, positive=True, min_value=Decimal('500.00'), max_value=Decimal('15000.00')),
                                'activo': fake.boolean(chance_of_getting_true=95)
                            }

                            tarifa, _ = Tarifa.objects.update_or_create(
                                ramo=ramo, rango_etario=rango, fecha_aplicacion=fecha_app, tipo_fraccionamiento=tipo_f, defaults=defaults)
                            if tarifa.pk not in tarifa_ids_created:
                                tarifa_ids_created.append(tarifa.pk)
                            stats_m['created'] += 1
                        except IntegrityError:
                            stats_m['failed'] += 1
                            stats_m['errors']['IntegrityError_Tarifa_Unique'] += 1
                        except Exception as e:
                            stats_m['failed'] += 1
                            stats_m['errors'][e.__class__.__name__] += 1
                            logger.error(
                                f"Error creando {model_name}: {e}", exc_info=True)
                    if not (tarifa_ids_created + tarifa_ids_db) and stats_m['requested'] > 0:
                        try:
                            emergency_tarifa = Tarifa.objects.create(ramo=CommonChoices.RAMO[0][0], rango_etario=CommonChoices.RANGO_ETARIO[0][0], fecha_aplicacion=date.today(
                            ) - timedelta(days=30), monto_anual=Decimal("100.00"), activo=True)
                            tarifa_ids_created.append(emergency_tarifa.pk)
                            stats_m['created'] += 1
                        except Exception as e:
                            self.stderr.write(self.style.ERROR(
                                f"Failed to create emergency tariff: {e}"))

                # --- 3. Usuarios ---
                model_name = 'User'
                stats_m = stats[model_name]
                try:
                    admin_email = 'admin@example.com'
                    admin_user, created = User.objects.get_or_create(email=admin_email, defaults={
                                                                     # DateField
                                                                     'primer_nombre': 'Admin', 'primer_apellido': 'User', 'nivel_acceso': 5, 'tipo_usuario': 'ADMIN', 'fecha_nacimiento': fake.date_of_birth(minimum_age=30, maximum_age=60), 'activo': True})
                    if created:
                        admin_user.set_password('password')
                        admin_user.save()
                    if admin_user.pk not in user_ids_created:
                        user_ids_created.append(admin_user.pk)
                    stats_m['created'] += 1
                except Exception as e:
                    stats_m['failed'] += 1
                    stats_m['errors'][e.__class__.__name__] += 1
                    logger.error(
                        f"Error creando usuario admin: {e}", exc_info=True)

                for _ in range(max(0, stats_m['requested'] - 1 if stats_m['requested'] > 0 else 0)):
                    user_email = None
                    try:
                        for _ in range(5):
                            user_email_raw = fake.unique.email()
                            if not User.objects.filter(email=user_email_raw).exists():
                                user_email = user_email_raw
                                break
                        if not user_email:
                            stats_m['failed'] += 1
                            stats_m['errors']['UniqueEmailFail_User'] += 1
                            continue

                        user_obj = User(email=user_email, primer_nombre=fake.first_name(), segundo_nombre=fake.first_name() if fake.boolean(chance_of_getting_true=60) else None, primer_apellido=fake.last_name(), segundo_apellido=fake.last_name() if fake.boolean(chance_of_getting_true=50) else None,
                                        # DateField
                                        tipo_usuario=random.choice([c[0] for c in CommonChoices.TIPO_USUARIO]), fecha_nacimiento=fake.date_of_birth(minimum_age=18, maximum_age=75),
                                        departamento=random.choice([c[0] for c in CommonChoices.DEPARTAMENTO] + [None]*2), telefono=generate_phone_ve() if fake.boolean(chance_of_getting_true=85) else None,
                                        direccion=fake.address() if fake.boolean(chance_of_getting_true=80) else None, nivel_acceso=random.randint(1, 5), activo=fake.boolean(chance_of_getting_true=95))
                        user_obj.set_password('password')
                        user_obj.save()
                        if user_obj.pk not in user_ids_created:
                            user_ids_created.append(user_obj.pk)
                        stats_m['created'] += 1
                    except IntegrityError as e:
                        stats_m['failed'] += 1
                        stats_m['errors'][e.__class__.__name__] += 1
                        fake.unique.clear()
                        logger.warning(f"IntegrityError creando User: {e}")
                    except Exception as e:
                        stats_m['failed'] += 1
                        stats_m['errors'][e.__class__.__name__] += 1
                        logger.error(f"Error creando User: {e}", exc_info=True)

                # --- 4. Intermediarios ---
                model_name = 'Intermediario'
                stats_m = stats[model_name]
                parent_intermediario_pks_this_run = []
                num_intermediarios_total = stats_m['requested']
                num_potential_parents = max(
                    1, num_intermediarios_total // 3) if num_intermediarios_total >= 3 else 0

                for i in range(max(0, num_intermediarios_total)):
                    inter = None
                    try:
                        has_rif = fake.boolean(chance_of_getting_true=90)
                        comision_directa_propia = fake.pydecimal(
                            left_digits=2, right_digits=2, min_value=Decimal('1.00'), max_value=Decimal('25.00'))
                        intermediario_rif = None
                        if has_rif or comision_directa_propia > 10:
                            for _ in range(3):
                                intermediario_rif_raw = generate_rif()
                                if not Intermediario.objects.filter(rif=intermediario_rif_raw).exists():
                                    intermediario_rif = intermediario_rif_raw
                                    break
                            if not intermediario_rif and comision_directa_propia > 10:
                                stats_m['failed'] += 1
                                stats_m['errors']['UniqueRIF_Intermediario_Fail'] += 1
                                continue
                            elif not intermediario_rif:
                                has_rif = False

                        porc_override_inter = Decimal('0.00')
                        padre_id_inter = None
                        if len(parent_intermediario_pks_this_run) < num_potential_parents:
                            if fake.boolean(chance_of_getting_true=80):
                                porc_override_inter = fake.pydecimal(
                                    left_digits=1, right_digits=2, min_value=Decimal('1.00'), max_value=Decimal('10.00'))
                        elif parent_intermediario_pks_this_run:
                            if fake.boolean(chance_of_getting_true=70):
                                padre_id_inter = random.choice(
                                    parent_intermediario_pks_this_run)

                        inter_email = None
                        if fake.boolean(chance_of_getting_true=95):
                            for _ in range(5):
                                temp_email = fake.unique.email()
                                if not Intermediario.objects.filter(email_contacto=temp_email).exists():
                                    inter_email = temp_email
                                    break
                            if not inter_email:
                                logger.warning(
                                    f"Intermediario (iter {i}): No se pudo generar email único. Se omitirá.")

                        inter = Intermediario(nombre_completo=fake.company() + " " + fake.company_suffix(), rif=intermediario_rif if has_rif else None,
                                              direccion_fiscal=fake.address() if fake.boolean(chance_of_getting_true=85) else None, telefono_contacto=generate_phone_ve() if fake.boolean(chance_of_getting_true=95) else None,
                                              email_contacto=inter_email, porcentaje_comision=comision_directa_propia,
                                              porcentaje_override=porc_override_inter, intermediario_relacionado_id=padre_id_inter, activo=fake.boolean(chance_of_getting_true=95))
                        inter.save()
                        stats_m['created'] += 1
                        if inter.pk not in intermediario_ids_created:
                            intermediario_ids_created.append(inter.pk)
                        if porc_override_inter > Decimal('0.00') and padre_id_inter is None:
                            parent_intermediario_pks_this_run.append(inter.pk)

                        ids_for_m2m_user = list(
                            set(user_ids_created + user_ids_db))
                        if ids_for_m2m_user:
                            k = random.randint(
                                0, min(3, len(ids_for_m2m_user)))
                            usuarios_a_asignar_pks = random.sample(
                                ids_for_m2m_user, k=k)
                            usuarios_existentes = User.objects.filter(
                                pk__in=usuarios_a_asignar_pks)
                            if usuarios_existentes.exists():
                                inter.usuarios.set(usuarios_existentes)
                    except IntegrityError as e:
                        stats_m['failed'] += 1
                        error_key = 'IntegrityError_Interm_Unknown'
                        if 'email' in str(e).lower():
                            error_key = 'IntegrityError_Interm_Email'
                        elif 'rif' in str(e).lower():
                            error_key = 'IntegrityError_Interm_RIF'
                        elif 'codigo' in str(e).lower():
                            error_key = 'IntegrityError_Interm_Codigo'
                        stats_m['errors'][error_key] += 1
                        fake.unique.clear()
                        logger.warning(
                            f"Intermediario (iter {i}) - IntegrityError: {e}")
                    except Exception as e:
                        stats_m['failed'] += 1
                        stats_m['errors'][e.__class__.__name__] += 1
                        logger.error(
                            f"Intermediario (iter {i}) - EXCEPTION: {e.__class__.__name__} - {e}", exc_info=True)
                if not (intermediario_ids_created + intermediario_ids_db) and stats_m['requested'] > 0:
                    try:
                        emergency_intermediario, created = Intermediario.objects.get_or_create(nombre_completo="Intermediario Emergencia", defaults={
                                                                                               'porcentaje_comision': Decimal("5.00"), 'activo': True, 'porcentaje_override': Decimal("0.00")})
                        if created:
                            intermediario_ids_created.append(
                                emergency_intermediario.pk)
                            stats_m['created'] += 1
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(
                            f"Failed to create emergency intermediario: {e}"))
                all_intermediario_ids_combined = list(
                    set(intermediario_ids_created + intermediario_ids_db))
                if all_intermediario_ids_combined:
                    users_to_assign = User.objects.filter(pk__in=list(set(
                        user_ids_created + user_ids_db)), tipo_usuario='INTERMEDIARIO', intermediario__isnull=True)
                    for user_obj_assign in users_to_assign:
                        if fake.boolean(chance_of_getting_true=85):
                            try:
                                user_obj_assign.intermediario_id = random.choice(
                                    all_intermediario_ids_combined)
                                user_obj_assign.save(
                                    update_fields=['intermediario'])
                            except Exception as e_assign:
                                logger.warning(
                                    f"Error asignando intermediario a usuario {user_obj_assign.pk}: {e_assign}")

                # --- 5. Afiliados Individuales ---
                model_name = 'AfiliadoIndividual'
                stats_m = stats[model_name]
                for _ in range(max(0, stats_m['requested'])):
                    afiliado = None
                    try:
                        afiliado_cedula = None
                        for _ in range(5):
                            afiliado_cedula_raw = generate_cedula()
                            if not AfiliadoIndividual.objects.filter(cedula=afiliado_cedula_raw).exists():
                                afiliado_cedula = afiliado_cedula_raw
                                break
                        if not afiliado_cedula:
                            stats_m['failed'] += 1
                            stats_m['errors']['UniqueCedula_AfiInd_Fail'] += 1
                            continue
                        nacimiento = fake.date_of_birth(
                            minimum_age=0, maximum_age=90)  # DateField
                        ingreso = fake.date_between(
                            start_date=nacimiento, end_date='today')  # DateField
                        intermediario_afiliado_id = get_random_pk_from_lists(
                            intermediario_ids_created, intermediario_ids_db, allow_none=True, model_name_for_error="Intermediario para AfiInd")
                        afiliado_email = None
                        if fake.boolean(chance_of_getting_true=85):
                            for _ in range(5):
                                temp_email_afi = fake.unique.email()
                                if not AfiliadoIndividual.objects.filter(email=temp_email_afi).exists():
                                    afiliado_email = temp_email_afi
                                    break
                            if not afiliado_email:
                                logger.warning(
                                    f"AfiliadoInd: No se pudo generar email único. Se omitirá.")
                        afiliado = AfiliadoIndividual(primer_nombre=fake.first_name(), segundo_nombre=fake.first_name() if fake.boolean(chance_of_getting_true=60) else None, primer_apellido=fake.last_name(), segundo_apellido=fake.last_name() if fake.boolean(chance_of_getting_true=50) else None, tipo_identificacion=afiliado_cedula[0], cedula=afiliado_cedula, estado_civil=random.choice([c[0] for c in CommonChoices.ESTADO_CIVIL]), sexo=random.choice([c[0] for c in CommonChoices.SEXO]), parentesco=random.choice([c[0] for c in CommonChoices.PARENTESCO]), fecha_nacimiento=nacimiento, nacionalidad='Venezolano' if afiliado_cedula.startswith('V') else fake.country(), zona_postal=fake.numerify('1###') if fake.boolean(
                            chance_of_getting_true=80) else None, estado=random.choice([c[0] for c in CommonChoices.ESTADOS_VE]), municipio=fake.city() if fake.boolean(chance_of_getting_true=85) else None, ciudad=fake.city() if fake.boolean(chance_of_getting_true=95) else None, fecha_ingreso=ingreso, direccion_habitacion=fake.address(), telefono_habitacion=generate_phone_ve() if fake.boolean(chance_of_getting_true=80) else None, email=afiliado_email, direccion_oficina=fake.address() if fake.boolean(chance_of_getting_true=40) else None, telefono_oficina=generate_phone_ve() if fake.boolean(chance_of_getting_true=40) else None, activo=fake.boolean(chance_of_getting_true=95), intermediario_id=intermediario_afiliado_id)
                        afiliado.save()
                        stats_m['created'] += 1
                        if afiliado.pk not in afiliado_ind_ids_created:
                            afiliado_ind_ids_created.append(afiliado.pk)
                    except IntegrityError as e:
                        stats_m['failed'] += 1
                        stats_m['errors'][e.__class__.__name__] += 1
                        fake.unique.clear()
                        logger.warning(
                            f"IntegrityError creando AfiliadoIndividual: {e}")
                    except Exception as e:
                        stats_m['failed'] += 1
                        stats_m['errors'][e.__class__.__name__] += 1
                        logger.error(
                            f"Error creando AfiliadoIndividual: {e}", exc_info=True)
                if not (afiliado_ind_ids_created + afiliado_ind_ids_db) and stats_m['requested'] > 0:
                    try:
                        emergency_cedula_ind = None
                        for _ in range(10):
                            temp_cedula = generate_cedula()
                            if not AfiliadoIndividual.objects.filter(cedula=temp_cedula).exists():
                                emergency_cedula_ind = temp_cedula
                                break
                        if not emergency_cedula_ind:
                            emergency_cedula_ind = f"V-EM{fake.numerify('#######')}"
                        emergency_af_ind = AfiliadoIndividual.objects.create(primer_nombre="Emergencia", primer_apellido="AfiliadoInd", tipo_identificacion=emergency_cedula_ind[0], cedula=emergency_cedula_ind, fecha_nacimiento=date.today(
                            # DateField
                        ) - timedelta(days=365*30), estado=CommonChoices.ESTADOS_VE[0][0], sexo=CommonChoices.SEXO[0][0], parentesco='TITULAR', activo=True)
                        afiliado_ind_ids_created.append(emergency_af_ind.pk)
                        stats_m['created'] += 1
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(
                            f"Failed to create emergency AfiliadoIndividual: {e}"))

                # --- 6. Afiliados Colectivos ---
                model_name = 'AfiliadoColectivo'
                stats_m = stats[model_name]
                for _ in range(max(0, stats_m['requested'])):
                    af_col = None
                    try:
                        afiliado_col_rif = None
                        for _ in range(5):
                            afiliado_col_rif_raw = generate_rif()
                            if not AfiliadoColectivo.objects.filter(rif=afiliado_col_rif_raw).exists():
                                afiliado_col_rif = afiliado_col_rif_raw
                                break
                        if not afiliado_col_rif:
                            stats_m['failed'] += 1
                            stats_m['errors']['UniqueRIF_AfiCol_Fail'] += 1
                            continue
                        af_col_email = None
                        if fake.boolean(chance_of_getting_true=95):
                            for _ in range(5):
                                temp_email_afcol = fake.unique.company_email()
                                if not AfiliadoColectivo.objects.filter(email_contacto=temp_email_afcol).exists():
                                    af_col_email = temp_email_afcol
                                    break
                            if not af_col_email:
                                logger.warning(
                                    f"AfiliadoCol: No se pudo generar email único. Se omitirá.")
                        intermediario_afiliado_col_id = get_random_pk_from_lists(
                            intermediario_ids_created, intermediario_ids_db, allow_none=True, model_name_for_error="Intermediario para AfiCol")
                        af_col = AfiliadoColectivo(razon_social=fake.company(), rif=afiliado_col_rif, tipo_empresa=random.choice([c[0] for c in CommonChoices.TIPO_EMPRESA]), direccion_comercial=fake.address(), estado=random.choice([c[0] for c in CommonChoices.ESTADOS_VE]), municipio=fake.city() if fake.boolean(chance_of_getting_true=85) else None, ciudad=fake.city() if fake.boolean(
                            chance_of_getting_true=95) else None, zona_postal=fake.numerify('1###') if fake.boolean(chance_of_getting_true=80) else None, telefono_contacto=generate_phone_ve() if fake.boolean(chance_of_getting_true=95) else None, email_contacto=af_col_email, activo=fake.boolean(chance_of_getting_true=95), intermediario_id=intermediario_afiliado_col_id)
                        af_col.save()
                        stats_m['created'] += 1
                        if af_col.pk not in afiliado_col_ids_created:
                            afiliado_col_ids_created.append(af_col.pk)
                    except IntegrityError as e:
                        stats_m['failed'] += 1
                        stats_m['errors'][e.__class__.__name__] += 1
                        fake.unique.clear()
                        logger.warning(
                            f"IntegrityError creando AfiliadoColectivo: {e}")
                    except Exception as e:
                        stats_m['failed'] += 1
                        stats_m['errors'][e.__class__.__name__] += 1
                        logger.error(
                            f"Error creando AfiliadoColectivo: {e}", exc_info=True)
                if not (afiliado_col_ids_created + afiliado_col_ids_db) and stats_m['requested'] > 0:
                    try:
                        emergency_rif_col = None
                        for _ in range(10):
                            temp_rif = generate_rif()
                            if not AfiliadoColectivo.objects.filter(rif=temp_rif).exists():
                                emergency_rif_col = temp_rif
                                break
                        if not emergency_rif_col:
                            emergency_rif_col = f"J-EM{fake.numerify('#######')}-{fake.numerify('#')}"
                        emergency_af_col = AfiliadoColectivo.objects.create(
                            razon_social="Empresa Colectiva Emergencia", rif=emergency_rif_col, tipo_empresa=CommonChoices.TIPO_EMPRESA[0][0], estado=CommonChoices.ESTADOS_VE[0][0], activo=True)
                        afiliado_col_ids_created.append(emergency_af_col.pk)
                        stats_m['created'] += 1
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(
                            f"Failed to create emergency AfiliadoColectivo: {e}"))

                # --- 7. Contratos Individuales ---
                model_name = 'ContratoIndividual'
                stats_m = stats[model_name]

                if not all([AfiliadoIndividual.objects.exists(), Intermediario.objects.exists(), Tarifa.objects.exists()]):
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: Faltan prerrequisitos."))
                    stats_m['failed'] = stats_m['requested']
                    stats_m['errors']['MissingPrerequisitesAtStart_ContInd'] = stats_m['requested']
                else:
                    for i in range(max(0, stats_m['requested'])):
                        try:
                            afiliado = AfiliadoIndividual.objects.order_by(
                                '?').first()
                            tarifa = Tarifa.objects.order_by('?').first()
                            intermediario = Intermediario.objects.order_by(
                                '?').first()

                            # >>> INICIO DE LA LÓGICA DE ESCENARIOS DE FECHA CORREGIDA <<<
                            scenario = random.choice(
                                ['VENCIDO', 'VIGENTE', 'VIGENTE', 'FUTURO'])

                            if scenario == 'VENCIDO':
                                fecha_fin = fake.date_between(
                                    start_date="-3y", end_date="-45d")
                                fecha_inicio = fecha_fin - timedelta(days=365)
                                estatus = 'VENCIDO'
                            elif scenario == 'FUTURO':
                                fecha_inicio = fake.date_between(
                                    start_date="+45d", end_date="+2y")
                                fecha_fin = fecha_inicio + timedelta(days=365)
                                # CORRECCIÓN: Usar el valor correcto de tus choices
                                estatus = 'NO_VIGENTE_AUN'
                            else:  # VIGENTE
                                fecha_inicio = fake.date_between(
                                    start_date="-2y", end_date="-45d")
                                fecha_fin = fecha_inicio + timedelta(days=365)
                                estatus = 'VIGENTE'

                            fecha_emision_dt_aware = timezone.make_aware(
                                datetime.combine(fecha_inicio, datetime.min.time()))
                            # >>> FIN DE LA LÓGICA DE ESCENARIOS DE FECHA <<<

                            contrato_ind = ContratoIndividual(
                                ramo=tarifa.ramo,
                                forma_pago=random.choice(
                                    [c[0] for c in CommonChoices.FORMA_PAGO]),
                                estatus=estatus,
                                suma_asegurada=fake.pydecimal(
                                    left_digits=6, right_digits=2, positive=True, min_value=Decimal('5000.00')),
                                fecha_emision=fecha_emision_dt_aware,
                                fecha_inicio_vigencia=fecha_inicio,
                                fecha_fin_vigencia=fecha_fin,
                                intermediario=intermediario,
                                tarifa_aplicada=tarifa,
                                afiliado=afiliado,
                                tipo_identificacion_contratante=afiliado.tipo_identificacion,
                                contratante_cedula=afiliado.cedula,
                                contratante_nombre=afiliado.nombre_completo,
                                activo=True
                            )
                            contrato_ind.save()
                            stats_m['created'] += 1
                            if contrato_ind.pk not in contrato_ind_ids_created:
                                contrato_ind_ids_created.append(
                                    contrato_ind.pk)
                        except Exception as e_ci_gen:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_ci_gen.__class__.__name__ +
                                              "_ContInd_Gen"] += 1
                            logger.error(
                                f"Error GENERAL creando ContratoIndividual (Iter {i+1}): {e_ci_gen}", exc_info=True)

                # --- 8. Contratos Colectivos ---
                model_name = 'ContratoColectivo'
                stats_m = stats[model_name]
                if not all([AfiliadoColectivo.objects.exists(), Intermediario.objects.exists(), Tarifa.objects.exists()]):
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: Missing prerequisites."))
                else:
                    for _ in range(max(0, stats_m['requested'])):
                        try:
                            af_col_principal = AfiliadoColectivo.objects.order_by(
                                '?').first()
                            tarifa_cc = Tarifa.objects.order_by('?').first()
                            intermediario_cc = Intermediario.objects.order_by(
                                '?').first()

                            scenario = random.choice(
                                ['VENCIDO', 'VIGENTE', 'VIGENTE', 'FUTURO'])
                            if scenario == 'VENCIDO':
                                fecha_fin = fake.date_between(
                                    start_date="-3y", end_date="-45d")
                                fecha_inicio = fecha_fin - timedelta(days=365)
                                estatus = 'VENCIDO'
                            elif scenario == 'FUTURO':
                                fecha_inicio = fake.date_between(
                                    start_date="+45d", end_date="+2y")
                                fecha_fin = fecha_inicio + timedelta(days=365)
                                # CORRECCIÓN: Usar el valor correcto de tus choices
                                estatus = 'NO_VIGENTE_AUN'
                            else:  # VIGENTE
                                fecha_inicio = fake.date_between(
                                    start_date="-2y", end_date="-45d")
                                fecha_fin = fecha_inicio + timedelta(days=365)
                                estatus = 'VIGENTE'

                            fecha_emision_dt_aware_cc = timezone.make_aware(
                                datetime.combine(fecha_inicio, datetime.min.time()))

                            contrato_col = ContratoColectivo(
                                ramo=tarifa_cc.ramo,
                                forma_pago=random.choice(
                                    [c[0] for c in CommonChoices.FORMA_PAGO]),
                                estatus=estatus,
                                suma_asegurada=fake.pydecimal(
                                    left_digits=7, right_digits=2, positive=True, min_value=Decimal('50000.00')),
                                fecha_emision=fecha_emision_dt_aware_cc,
                                fecha_inicio_vigencia=fecha_inicio,
                                fecha_fin_vigencia=fecha_fin,
                                intermediario=intermediario_cc,
                                tarifa_aplicada=tarifa_cc,
                                razon_social=af_col_principal.razon_social,
                                rif=af_col_principal.rif,
                                cantidad_empleados=random.randint(5, 200),
                                activo=True
                            )
                            contrato_col.save()
                            contrato_col.afiliados_colectivos.add(
                                af_col_principal)
                            stats_m['created'] += 1
                            if contrato_col.pk not in contrato_col_ids_created:
                                contrato_col_ids_created.append(
                                    contrato_col.pk)
                        except Exception as e_cc:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_cc.__class__.__name__] += 1
                            logger.error(
                                f"Error creando ContratoColectivo: {e_cc}", exc_info=True)
                # --- 9. Facturas ---
                model_name = 'Factura'
                stats_m = stats[model_name]

                # >>> CORRECCIÓN: Filtrar ANTES para asegurar que tenemos contratos válidos <<<
                contratos_facturables = list(ContratoIndividual.objects.filter(estatus__in=['VIGENTE', 'VENCIDO'])) + \
                    list(ContratoColectivo.objects.filter(
                        estatus__in=['VIGENTE', 'VENCIDO']))

                if not contratos_facturables:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No hay Contratos VIGENTES o VENCIDOS para crear Facturas."))
                    stats_m['failed'] = stats_m['requested']
                    stats_m['errors']['NoContractsForFacturas'] = stats_m['requested']
                else:
                    for _ in range(max(0, stats_m['requested'])):
                        try:
                            # Ahora cada elección es garantizada de un contrato válido
                            contrato_obj_fact = random.choice(
                                contratos_facturables)

                            es_vencida = contrato_obj_fact.estatus == 'VENCIDO'

                            if es_vencida:
                                fecha_inicio_vigencia = contrato_obj_fact.fecha_inicio_vigencia
                                fecha_fin_vigencia = contrato_obj_fact.fecha_fin_vigencia
                                estatus_factura = 'VENCIDA'
                            else:
                                fecha_inicio_vigencia = fake.date_between(
                                    start_date=contrato_obj_fact.fecha_inicio_vigencia, end_date=date.today())
                                fecha_fin_vigencia = fecha_inicio_vigencia + \
                                    timedelta(days=29)
                                estatus_factura = 'GENERADA'

                            factura_instance = Factura(
                                contrato_individual=contrato_obj_fact if isinstance(
                                    contrato_obj_fact, ContratoIndividual) else None,
                                contrato_colectivo=contrato_obj_fact if isinstance(
                                    contrato_obj_fact, ContratoColectivo) else None,
                                vigencia_recibo_desde=fecha_inicio_vigencia,
                                vigencia_recibo_hasta=fecha_fin_vigencia,
                                intermediario=contrato_obj_fact.intermediario,
                                monto=contrato_obj_fact.monto_cuota_estimada or Decimal(
                                    '100.00'),
                                dias_periodo_cobro=30,
                                estatus_factura=estatus_factura,
                                activo=True
                            )
                            factura_instance.save()
                            stats_m['created'] += 1
                            if factura_instance.pk not in factura_ids_created:
                                factura_ids_created.append(factura_instance.pk)
                        except Exception as e_f:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_f.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Factura: {e_f}", exc_info=True)

                # --- 10. Reclamaciones ---
                model_name = 'Reclamacion'
                stats_m = stats[model_name]

                # >>> CORRECCIÓN: Filtrar ANTES para asegurar que tenemos contratos válidos <<<
                contratos_reclamables = list(ContratoIndividual.objects.filter(estatus__in=['VIGENTE', 'VENCIDO'])) + \
                    list(ContratoColectivo.objects.filter(
                        estatus__in=['VIGENTE', 'VENCIDO']))

                if not contratos_reclamables:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No Contratos VIGENTES o VENCIDOS para Reclamaciones."))
                    stats_m['failed'] = stats_m['requested']
                    stats_m['errors']['NoContractsForReclamaciones'] = stats_m['requested']
                else:
                    for i_rec in range(max(0, stats_m['requested'])):
                        try:
                            # Ahora cada elección es garantizada de un contrato válido
                            contrato_obj_rec = random.choice(
                                contratos_reclamables)

                            fecha_inicio_valida = contrato_obj_rec.fecha_inicio_vigencia
                            fecha_fin_valida = min(
                                date.today(), contrato_obj_rec.fecha_fin_vigencia)

                            if fecha_inicio_valida > fecha_fin_valida:
                                # Si por alguna razón el contrato vigente tiene un inicio en el futuro (no debería pasar con el filtro)
                                # o si el vencido es tan reciente que el rango es inválido, reintentamos con otro contrato.
                                contrato_obj_rec = random.choice(
                                    contratos_reclamables)
                                fecha_inicio_valida = contrato_obj_rec.fecha_inicio_vigencia
                                fecha_fin_valida = min(
                                    date.today(), contrato_obj_rec.fecha_fin_vigencia)
                                if fecha_inicio_valida > fecha_fin_valida:
                                    continue  # Saltamos esta iteración si sigue fallando

                            fecha_reclamo_val = fake.date_between_dates(
                                date_start=fecha_inicio_valida,
                                date_end=fecha_fin_valida
                            )

                            estado_actual_rec = random.choice(
                                [c[0] for c in CommonChoices.ESTADO_RECLAMACION])
                            fecha_cierre_rec = None

                            estados_que_implican_cierre = [
                                'CERRADA', 'PAGADA', 'RECHAZADA', 'APROBADA']
                            if estado_actual_rec in estados_que_implican_cierre:
                                fecha_cierre_rec = fake.date_between_dates(
                                    date_start=fecha_reclamo_val,
                                    date_end=date.today()
                                )

                            suma_asegurada_contrato = contrato_obj_rec.suma_asegurada or Decimal(
                                '1000.00')
                            monto_reclamado_val = fake.pydecimal(
                                left_digits=int(len(str(int(suma_asegurada_contrato)))) - 1 if len(
                                    str(int(suma_asegurada_contrato))) > 1 else 1,
                                right_digits=2,
                                positive=True,
                                min_value=Decimal('50.00')
                            )
                            if monto_reclamado_val >= suma_asegurada_contrato:
                                monto_reclamado_val = suma_asegurada_contrato * \
                                    Decimal('0.5')

                            reclamacion_instance = Reclamacion(
                                contrato_individual=contrato_obj_rec if isinstance(
                                    contrato_obj_rec, ContratoIndividual) else None,
                                contrato_colectivo=contrato_obj_rec if isinstance(
                                    contrato_obj_rec, ContratoColectivo) else None,
                                tipo_reclamacion=random.choice(
                                    [c[0] for c in CommonChoices.TIPO_RECLAMACION]),
                                estado=estado_actual_rec,
                                descripcion_reclamo=fake.paragraph(
                                    nb_sentences=3),
                                monto_reclamado=monto_reclamado_val.quantize(
                                    Decimal('0.01')),
                                fecha_reclamo=fecha_reclamo_val,
                                fecha_cierre_reclamo=fecha_cierre_rec,
                                primer_nombre=f"Reclamo para Contrato",
                                primer_apellido=f"{contrato_obj_rec.numero_contrato or contrato_obj_rec.pk}"
                            )
                            reclamacion_instance.full_clean()
                            reclamacion_instance.save()
                            stats_m['created'] += 1
                            if reclamacion_instance.pk not in reclamacion_ids_created:
                                reclamacion_ids_created.append(
                                    reclamacion_instance.pk)
                        except Exception as e_r_gen:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_r_gen.__class__.__name__] += 1
                            logger.error(
                                f"Error GENERAL creando Reclamacion (Iter {i_rec+1}): {e_r_gen}", exc_info=True)

                # --- 11. Pagos ---
                model_name = 'Pago'
                stats_m = stats[model_name]
                # Recuperar la probabilidad
                igtf_chance = options.get('igtf_chance', 20)

                facturas_pagables = Factura.objects.filter(
                    pk__in=factura_ids_created)

                if not facturas_pagables.exists():
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No hay facturas pagables creadas en esta ejecución."))
                    stats_m['failed'] = stats_m['requested']
                    stats_m['errors']['NoPayableInvoicesFound'] = stats_m['requested']
                else:
                    for _ in range(max(0, stats_m['requested'])):
                        try:
                            factura_a_pagar = facturas_pagables.order_by(
                                '?').first()
                            if not factura_a_pagar:
                                continue

                            pendiente = factura_a_pagar.monto_pendiente
                            fecha_ref = factura_a_pagar.vigencia_recibo_desde

                            fecha_hoy = date.today()
                            if fecha_ref > fecha_hoy:
                                fecha_pago = fake.date_between_dates(
                                    date_start=fecha_ref, date_end=fecha_ref + timedelta(days=30))
                            else:
                                fecha_pago = fake.date_between_dates(
                                    date_start=fecha_ref, date_end=fecha_hoy)

                            es_parcial = random.random() < (pago_parcial_chance / 100.0)
                            monto_pago = (pendiente * Decimal(random.uniform(0.2, 0.8))
                                          ).quantize(Decimal('0.01')) if es_parcial else pendiente
                            monto_pago = max(Decimal('0.01'), monto_pago)

                            # >>> INICIO DE LA CORRECCIÓN PARA IGTF <<<
                            aplica_igtf = random.random() < (igtf_chance / 100.0)
                            # >>> FIN DE LA CORRECCIÓN <<<

                            pago = Pago.objects.create(
                                factura=factura_a_pagar,
                                monto_pago=monto_pago,
                                fecha_pago=fecha_pago,
                                forma_pago=random.choice(
                                    [c[0] for c in CommonChoices.FORMA_PAGO_RECLAMACION]),
                                referencia_pago=fake.bothify(
                                    text='REF-?#?#?#?#'),
                                aplica_igtf_pago=aplica_igtf,  # Asignar el valor de IGTF
                                activo=True
                            )

                            stats_m['created'] += 1
                            if pago.pk not in pago_ids_created:
                                pago_ids_created.append(pago.pk)

                        except Exception as e_p:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_p.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Pago: {e_p}", exc_info=True)
                # --- 12. Registro de Comisiones ---
                model_name = 'RegistroComision'
                stats_m = stats[model_name]

                # Usamos los pagos que se crearon exitosamente en esta ejecución
                pagos_validos_para_comision = Pago.objects.filter(
                    pk__in=pago_ids_created, factura__isnull=False)

                if not pagos_validos_para_comision.exists():
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No valid Payments with Invoices were created in this run."))
                else:
                    self.stdout.write(
                        f"--- Creating Comisiones for {pagos_validos_para_comision.count()} valid payments ---")
                    for pago in pagos_validos_para_comision.select_related('factura__intermediario__intermediario_relacionado'):
                        try:
                            if not pago.factura or not pago.factura.intermediario:
                                continue

                            intermediario_directo = pago.factura.intermediario

                            # 1. Crear comisión DIRECTA
                            if intermediario_directo.porcentaje_comision > 0:
                                monto_comision = pago.monto_pago * \
                                    (intermediario_directo.porcentaje_comision / Decimal(100))
                                RegistroComision.objects.create(
                                    intermediario=intermediario_directo,
                                    pago_cliente=pago,
                                    factura_origen=pago.factura,
                                    contrato_individual=pago.factura.contrato_individual,
                                    contrato_colectivo=pago.factura.contrato_colectivo,
                                    tipo_comision='DIRECTA',
                                    porcentaje_aplicado=intermediario_directo.porcentaje_comision,
                                    monto_base_calculo=pago.monto_pago,
                                    monto_comision=monto_comision.quantize(
                                        Decimal('0.01'))
                                )
                                stats_m['created'] += 1

                            # 2. Crear comisión de OVERRIDE si aplica
                            intermediario_padre = intermediario_directo.intermediario_relacionado
                            if intermediario_padre and intermediario_padre.porcentaje_override > 0:
                                monto_override = pago.monto_pago * \
                                    (intermediario_padre.porcentaje_override / Decimal(100))
                                RegistroComision.objects.create(
                                    intermediario=intermediario_padre,
                                    pago_cliente=pago,
                                    factura_origen=pago.factura,
                                    contrato_individual=pago.factura.contrato_individual,
                                    contrato_colectivo=pago.factura.contrato_colectivo,
                                    tipo_comision='OVERRIDE',
                                    porcentaje_aplicado=intermediario_padre.porcentaje_override,
                                    monto_base_calculo=pago.monto_pago,
                                    monto_comision=monto_override.quantize(
                                        Decimal('0.01')),
                                    intermediario_vendedor=intermediario_directo
                                )
                                stats_m['created'] += 1

                        except Exception as e_rc:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_rc.__class__.__name__] += 1
                            logger.error(
                                f"Error creando RegistroComision para Pago PK {pago.pk}: {e_rc}", exc_info=True)

                # --- 13. Notificaciones ---
                # (Sin cambios, fecha_creacion es DateTimeField con auto_now_add=True, que usa timezone.now())
                model_name = 'Notificacion'
                stats_m = stats[model_name]
                available_user_pks_noti = list(
                    set(user_ids_created + user_ids_db))
                if not available_user_pks_noti:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No Users found."))
                else:
                    for _ in range(max(0, stats_m['requested'])):
                        try:
                            user_destino_pk = random.choice(
                                available_user_pks_noti)
                            noti = Notificacion(usuario_id=user_destino_pk, mensaje=fake.sentence(nb_words=random.randint(
                                8, 15)), tipo=random.choice([t[0] for t in Notificacion.TIPO_NOTIFICACION_CHOICES]))
                            noti.save()
                            stats_m['created'] += 1
                        except Exception as e:
                            stats_m['failed'] += 1
                            stats_m['errors'][e.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Notificacion: {e}", exc_info=True)

                # --- 13. AuditoriaSistema ---
                # (Sin cambios, tiempo_inicio y control_fecha_actual son auto_now_add=True)
                # tiempo_final es DateTimeField nullable, si se asigna, debe ser aware
                model_name = 'AuditoriaSistema'
                stats_m = stats[model_name]
                available_user_pks_audit = list(
                    set(user_ids_created + user_ids_db))
                if not available_user_pks_audit:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No Users for audit."))
                else:
                    for _ in range(max(0, stats_m['requested'])):
                        try:
                            usuario_audit_id = random.choice(
                                available_user_pks_audit)
                            # tiempo_final si se asigna, debería ser aware
                            audit_tiempo_final = None
                            if fake.boolean(chance_of_getting_true=50):
                                audit_tiempo_final = self._get_aware_fake_datetime(
                                    fake, timezone.now() - timedelta(hours=1), timezone.now())

                            audit = AuditoriaSistema(
                                usuario_id=usuario_audit_id,
                                tipo_accion=random.choice(
                                    [a[0] for a in CommonChoices.TIPO_ACCION]),
                                resultado_accion=random.choice(
                                    [r[0] for r in CommonChoices.RESULTADO_ACCION]),
                                tabla_afectada=random.choice(
                                    [None, "users_usuario", "myapp_factura"]),
                                registro_id_afectado=random.randint(
                                    1, 1000) if random.choice([True, False]) else None,
                                tiempo_final=audit_tiempo_final  # Asignar el valor aware o None
                            )
                            audit.save()
                            stats_m['created'] += 1
                        except Exception as e:
                            stats_m['failed'] += 1
                            stats_m['errors'][e.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Auditoria: {e}", exc_info=True)

        except Exception as e_global_tx:
            # ... (manejo de error global no cambia) ...
            self.stderr.write(self.style.ERROR(
                f"\nUNEXPECTED ERROR during data creation transaction: {e_global_tx.__class__.__name__} - {e_global_tx}"))
            logger.exception(
                "Error critical during seeding creation phase, transaction rolled back:")
            self.stderr.write(self.style.ERROR(
                "   Seeding incomplete. Changes were rolled back."))

        # --- === RESUMEN FINAL === ---
        self.stdout.write(self.style.SUCCESS(
            "\n" + "="*25 + " Seeding Summary " + "="*25))
        col_width_model = 25
        col_width_num = 11
        header_line_1 = f"{'Model':<{col_width_model}} | {'Requested':>{col_width_num}} | {'Created':>{col_width_num}} | {'Failed':>{col_width_num}} | Errors"
        self.stdout.write(header_line_1)
        self.stdout.write("-" * len(header_line_1))
        total_requested_all, total_created_all, total_failed_all = 0, 0, 0
        model_order_display = ['LicenseInfo', 'Tarifa', 'User', 'Intermediario', 'AfiliadoIndividual', 'AfiliadoColectivo',
                               'ContratoIndividual', 'ContratoColectivo', 'Factura', 'Reclamacion', 'Pago',
                               'RegistroComision', 'Notificacion', 'AuditoriaSistema']

        _last_rc_pk_before_pagos = 0
        # Usar options.get() para 'pagos' como ya estaba
        if options.get('pagos', 0) > 0:
            # CORREGIDO: Usar la variable should_clean
            if not should_clean and not hasattr(self, '_last_rc_pk_before_pagos_val'):
                self._last_rc_pk_before_pagos_val = RegistroComision.objects.order_by(
                    '-pk').first().pk if RegistroComision.objects.exists() else 0

        current_registro_comision_count = RegistroComision.objects.count()
        # CORREGIDO: Usar la variable should_clean
        if should_clean:
            stats['RegistroComision']['created'] = current_registro_comision_count
        else:
            if hasattr(self, '_last_rc_pk_before_pagos_val'):
                stats['RegistroComision']['created'] = RegistroComision.objects.filter(
                    pk__gt=self._last_rc_pk_before_pagos_val).count()
            else:
                stats['RegistroComision']['created'] = current_registro_comision_count

        for model_key in model_order_display:
            if model_key in stats:
                s = stats[model_key]
                total_requested_all += s.get('requested', 0)
                total_created_all += s.get('created', 0)
                total_failed_all += s.get('failed', 0)
                errors_str = "None"
                if s.get('errors'):
                    errors_str = ", ".join(
                        f"{etype}: {count}" for etype, count in s['errors'].most_common())
                actual_created = s.get('created', 0)
                requested_val = s.get('requested', 0)
                line = f"{model_key:<{col_width_model}} | {requested_val:>{col_width_num}} | {actual_created:>{col_width_num}} | {s.get('failed', 0):>{col_width_num}} | {errors_str}"

                style_to_use = self.stdout.write

                if s.get('failed', 0) > 0:
                    style_to_use = self.style.WARNING
                elif requested_val > 0 and actual_created < requested_val and model_key not in ['RegistroComision', 'LicenseInfo']:
                    style_to_use = self.style.NOTICE
                elif ((requested_val > 0 and actual_created >= requested_val) or
                      (model_key == 'RegistroComision' and actual_created > 0) or
                      (model_key == 'LicenseInfo' and actual_created == 1)
                      ) and s.get('failed', 0) == 0:
                    style_to_use = self.style.SUCCESS

                if callable(style_to_use) and style_to_use in [self.style.SUCCESS, self.style.WARNING, self.style.NOTICE, self.style.ERROR]:
                    self.stdout.write(style_to_use(line))
                else:
                    self.stdout.write(line)
        self.stdout.write("-" * len(header_line_1))
        summary_line = f"{'TOTAL':<{col_width_model}} | {total_requested_all:>{col_width_num}} | {total_created_all:>{col_width_num}} | {total_failed_all:>{col_width_num}} |"
        if total_failed_all > 0:
            self.stdout.write(self.style.WARNING(summary_line))
        else:
            self.stdout.write(self.style.SUCCESS(summary_line))
        self.stdout.write("-" * len(header_line_1))
        if total_failed_all > 0:
            self.stdout.write(self.style.WARNING(
                f"\nSeeding completed with {total_failed_all} failures."))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nDatabase seeding completed successfully!"))
