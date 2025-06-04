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
        # ... (tus argumentos no cambian) ...
        parser.add_argument('--clean', action='store_true',
                            help='Delete existing data before seeding.')
        parser.add_argument('--users', type=int, default=10)
        parser.add_argument('--intermediarios', type=int, default=5)
        parser.add_argument('--afiliados_ind', type=int, default=10)
        parser.add_argument('--afiliados_col', type=int, default=5)
        parser.add_argument('--tarifas', type=int, default=10)
        parser.add_argument('--contratos_ind', type=int, default=8)
        parser.add_argument('--contratos_col', type=int, default=4)
        parser.add_argument('--facturas', type=int, default=20)
        parser.add_argument('--reclamaciones', type=int, default=10)
        parser.add_argument('--pagos', type=int, default=15)
        parser.add_argument('--notificaciones', type=int, default=20)
        parser.add_argument('--auditorias', type=int, default=20)
        parser.add_argument('--igtf_chance', type=int, default=20,
                            choices=range(0, 101), metavar="[0-100]")
        parser.add_argument('--pago_parcial_chance',
                            type=int, default=40, metavar="[0-100]")

    def _initialize_stats(self, options):
        stats = collections.defaultdict(
            lambda: {'requested': 0, 'created': 0, 'failed': 0, 'errors': collections.Counter()})
        stats['LicenseInfo']['requested'] = 1
        stats['Tarifa']['requested'] = options['tarifas']
        stats['User']['requested'] = options['users']
        stats['Intermediario']['requested'] = options['intermediarios']
        stats['AfiliadoIndividual']['requested'] = options['afiliados_ind']
        stats['AfiliadoColectivo']['requested'] = options['afiliados_col']
        stats['ContratoIndividual']['requested'] = options['contratos_ind']
        stats['ContratoColectivo']['requested'] = options['contratos_col']
        stats['Factura']['requested'] = options['facturas']
        stats['Reclamacion']['requested'] = options['reclamaciones']
        stats['Pago']['requested'] = options['pagos']
        stats['Notificacion']['requested'] = options['notificaciones']
        stats['AuditoriaSistema']['requested'] = options['auditorias']
        stats['RegistroComision']['requested'] = 0
        return stats

    def _disconnect_signals_for_clean(self):
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
        self.stdout.write(self.style.NOTICE(
            "  Signal reconnection will be handled by Django's AppConfig.ready() on next full app load."))

    # --- FUNCIÓN AUXILIAR PARA DATETIMES AWARE ---
    def _get_aware_fake_datetime(self, fake_instance, start_date_aware=None, end_date_aware=None, default_start_days_ago=730):
        """
        Genera un datetime consciente de la zona horaria usando Faker.
        """
        current_tz = timezone.get_current_timezone()

        if start_date_aware and timezone.is_naive(start_date_aware):
            start_date_aware = timezone.make_aware(
                start_date_aware, current_tz)
        if end_date_aware and timezone.is_naive(end_date_aware):
            end_date_aware = timezone.make_aware(end_date_aware, current_tz)

        # Convertir start y end dates a naive para Faker si son aware,
        # o usar defaults si no se proveen.
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
            naive_end = datetime.now()  # Hora actual ingenua

        # Asegurarse que naive_start no sea posterior a naive_end
        if naive_start > naive_end:
            # Ajustar si es necesario
            naive_start = naive_end - timedelta(days=1)

        try:
            # Llama a Faker con fechas ingenuas
            naive_dt = fake_instance.date_time_between(
                start_date=naive_start, end_date=naive_end)
        except Exception as e:  # Fallback si date_time_between falla por alguna razón
            logger.warning(
                f"Faker date_time_between falló ({e}), usando past_datetime como fallback.")
            naive_dt = fake_instance.past_datetime(
                start_date=f"-{default_start_days_ago}d")

        # Hacerlo aware con la zona horaria actual del proyecto
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

        stats = self._initialize_stats(options)
        igtf_chance = options['igtf_chance']
        pago_parcial_chance = options['pago_parcial_chance']

        # ... (listas de IDs no cambian) ...
        user_ids_created, intermediario_ids_created, afiliado_ind_ids_created, afiliado_col_ids_created = [], [], [], []
        tarifa_ids_created, contrato_ind_ids_created, contrato_col_ids_created = [], [], []
        factura_ids_created, reclamacion_ids_created, pago_ids_created = [], [], []

        user_ids_db, intermediario_ids_db, afiliado_ind_ids_db, afiliado_col_ids_db = [], [], [], []
        tarifa_ids_db, contrato_ind_ids_db, contrato_col_ids_db = [], [], []
        factura_ids_db, reclamacion_ids_db, pago_ids_db = [], [], []

        if options['clean']:
            # ... (lógica de clean no cambia sustancialmente, solo asegura que las desconexiones/reconexiones funcionen) ...
            self.stdout.write(self.style.WARNING(
                "Attempting to delete existing data in specific order..."))
            disconnected_signals_info = []
            clean_failed = False
            try:
                disconnected_signals_info = self._disconnect_signals_for_clean()

                with transaction.atomic():
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
            # ... (lógica de carga de IDs existentes no cambia) ...
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
                model_name = 'LicenseInfo'
                stats_m = stats[model_name]
                try:
                    # Calcular la fecha de expiración exactamente 7 días desde hoy
                    # Si expiry_date es DateField, usa date(). Si es DateTimeField, usa timezone.now().
                    # Asumamos que es DateField por tu comentario.
                    # Obtiene la fecha actual en la zona horaria del proyecto
                    fecha_actual = timezone.localdate()
                    fecha_expiracion_exacta = fecha_actual + timedelta(days=7)

                    license_defaults = {
                        'license_key': fake.uuid4(),
                        'expiry_date': fecha_expiracion_exacta,  # Usar la fecha calculada
                        'license_type': 'TRIAL',  # Podrías añadir un tipo de licencia
                        'is_active': True,
                        # 'max_users': 1, # Ejemplo de restricción para trial
                        # 'features_enabled': 'feature1,feature2' # Ejemplo
                    }

                    # Usar update_or_create para manejar si ya existe una entrada (por SINGLETON_ID)
                    license_obj, created = LicenseInfo.objects.update_or_create(
                        id=LicenseInfo.SINGLETON_ID,  # Asumiendo que tienes un ID fijo para la licencia única
                        defaults=license_defaults
                    )

                    if created:
                        self.stdout.write(self.style.SUCCESS(
                            f"  {model_name}: Licencia de prueba CREADA, expira el {fecha_expiracion_exacta}."))
                    else:
                        self.stdout.write(self.style.SUCCESS(
                            f"  {model_name}: Licencia de prueba ACTUALIZADA, expira el {fecha_expiracion_exacta}."))

                    stats_m['created'] += 1

                except Exception as e:
                    stats_m['failed'] += 1
                    stats_m['errors'][e.__class__.__name__] += 1
                    logger.error(
                        f"Error creando/actualizando {model_name}: {e}", exc_info=True)
                    self.stderr.write(self.style.ERROR(
                        f"  Error con {model_name}: {e}"))

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
                            defaults = {'monto_anual': fake.pydecimal(left_digits=4, right_digits=2, positive=True, min_value=Decimal('50.00'), max_value=Decimal('9500.00')),
                                        'comision_intermediario': fake.pydecimal(left_digits=2, right_digits=2, min_value=Decimal('1.00'), max_value=Decimal('30.00')), 'activo': fake.boolean(chance_of_getting_true=90)}
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
                            ) - timedelta(days=30), monto_anual=Decimal("100.00"), comision_intermediario=Decimal("10.00"), activo=True)
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
                available_afiliado_ind_pks_ci = list(
                    set(afiliado_ind_ids_created + afiliado_ind_ids_db))
                available_intermediario_pks_ci = list(
                    set(intermediario_ids_created + intermediario_ids_db))
                available_tarifa_pks_ci = list(
                    set(tarifa_ids_created + tarifa_ids_db))

                if not available_afiliado_ind_pks_ci or not available_intermediario_pks_ci or not available_tarifa_pks_ci:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: Missing prerequisites."))
                else:
                    for _ in range(max(0, stats_m['requested'])):
                        contrato_ind = None
                        try:
                            afiliado_pk = random.choice(
                                available_afiliado_ind_pks_ci)
                            tarifa_pk = random.choice(available_tarifa_pks_ci)
                            intermediario_pk = random.choice(
                                available_intermediario_pks_ci)

                            afiliado = AfiliadoIndividual.objects.get(
                                pk=afiliado_pk)
                            tarifa = Tarifa.objects.get(pk=tarifa_pk)
                            intermediario = Intermediario.objects.get(
                                pk=intermediario_pk)

                            start_range_ci_aware = timezone.now() - timedelta(days=365*2)
                            end_range_ci_aware = timezone.now() - timedelta(days=1)
                            # Usa la función auxiliar
                            fecha_emision_dt_aware_ci = self._get_aware_fake_datetime(
                                fake, start_range_ci_aware, end_range_ci_aware)

                            periodo_meses = random.choice([6, 12, 18, 24])
                            comision_anual_pct = fake.pydecimal(left_digits=2, right_digits=2, min_value=Decimal(
                                '1.00'), max_value=Decimal('20.00')) if fake.boolean(chance_of_getting_true=75) else None

                            contrato_ind = ContratoIndividual(
                                ramo=tarifa.ramo, forma_pago=random.choice(
                                    [c[0] for c in CommonChoices.FORMA_PAGO]),
                                estatus=random.choice(
                                    [c[0] for c in CommonChoices.ESTADOS_VIGENCIA]),
                                suma_asegurada=fake.pydecimal(left_digits=6, right_digits=2, positive=True, min_value=Decimal(
                                    '1000.00'), max_value=Decimal('500000.00')),
                                fecha_emision=fecha_emision_dt_aware_ci,  # YA ES AWARE
                                periodo_vigencia_meses=periodo_meses,
                                intermediario=intermediario, tarifa_aplicada=tarifa, afiliado=afiliado,
                                tipo_identificacion_contratante=afiliado.tipo_identificacion, contratante_cedula=afiliado.cedula,
                                contratante_nombre=afiliado.nombre_completo, comision_anual=comision_anual_pct,
                                activo=fake.boolean(chance_of_getting_true=95)
                            )
                            contrato_ind.save()
                            stats_m['created'] += 1
                            if contrato_ind.pk not in contrato_ind_ids_created:
                                contrato_ind_ids_created.append(
                                    contrato_ind.pk)
                        except ObjectDoesNotExist:
                            stats_m['failed'] += 1
                            stats_m['errors']['DoesNotExist_ContInd_Prereq'] += 1
                            continue
                        except (IntegrityError, ValidationError) as e_ci:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_ci.__class__.__name__] += 1
                            logger.warning(
                                f"Error creando ContratoIndividual: {e_ci}")
                        except TypeError as e_type_ci:
                            stats_m['failed'] += 1
                            stats_m['errors']['TypeError_ContInd_Date'] += 1
                            logger.error(
                                f"TypeError creando ContratoIndividual (fecha_emision): {e_type_ci}", exc_info=True)
                        except Exception as e_ci:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_ci.__class__.__name__] += 1
                            logger.error(
                                f"Error creando ContratoIndividual: {e_ci}", exc_info=True)

                # --- 8. Contratos Colectivos ---
                model_name = 'ContratoColectivo'
                stats_m = stats[model_name]
                available_afiliado_col_pks_cc = list(
                    set(afiliado_col_ids_created + afiliado_col_ids_db))

                if not available_afiliado_col_pks_cc or not available_intermediario_pks_ci or not available_tarifa_pks_ci:  # Reusar pks_ci
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: Missing prerequisites."))
                else:
                    for _ in range(max(0, stats_m['requested'])):
                        contrato_col = None
                        try:
                            af_col_principal = AfiliadoColectivo.objects.filter(
                                pk__in=available_afiliado_col_pks_cc).order_by('?').first()
                            tarifa_cc = Tarifa.objects.filter(
                                pk__in=available_tarifa_pks_ci).order_by('?').first()
                            intermediario_cc = Intermediario.objects.filter(
                                pk__in=available_intermediario_pks_ci).order_by('?').first()

                            if not (af_col_principal and tarifa_cc and intermediario_cc):
                                stats_m['failed'] += 1
                                stats_m['errors']['MissingPrereq_ContCol_Robust'] += 1
                                continue

                            start_range_cc_aware = timezone.now() - timedelta(days=365*2)
                            end_range_cc_aware = timezone.now() - timedelta(days=1)
                            # Usa la función auxiliar
                            fecha_emision_dt_aware_cc = self._get_aware_fake_datetime(
                                fake, start_range_cc_aware, end_range_cc_aware)

                            periodo_meses_cc = random.choice([12, 24, 36])
                            cantidad_emp_cc = random.randint(5, 200)

                            contrato_col = ContratoColectivo(
                                ramo=tarifa_cc.ramo, forma_pago=random.choice(
                                    [c[0] for c in CommonChoices.FORMA_PAGO]),
                                estatus=random.choice(
                                    [c[0] for c in CommonChoices.ESTADOS_VIGENCIA]),
                                fecha_emision=fecha_emision_dt_aware_cc,  # YA ES AWARE
                                periodo_vigencia_meses=periodo_meses_cc,
                                intermediario=intermediario_cc, tarifa_aplicada=tarifa_cc,
                                razon_social=af_col_principal.razon_social, rif=af_col_principal.rif, cantidad_empleados=cantidad_emp_cc,
                                activo=fake.boolean(chance_of_getting_true=95)
                            )
                            contrato_col.save()
                            stats_m['created'] += 1
                            if contrato_col.pk not in contrato_col_ids_created:
                                contrato_col_ids_created.append(
                                    contrato_col.pk)

                            k_m2m_cc = random.randint(
                                1, min(3, len(available_afiliado_col_pks_cc)))
                            selected_af_col_pks_m2m_cc = set()
                            if af_col_principal.pk in available_afiliado_col_pks_cc:
                                selected_af_col_pks_m2m_cc.add(
                                    af_col_principal.pk)
                            other_afiliados_pks_cc = [
                                pk for pk in available_afiliado_col_pks_cc if pk != af_col_principal.pk]
                            if k_m2m_cc > len(selected_af_col_pks_m2m_cc) and other_afiliados_pks_cc:
                                num_to_add_cc = k_m2m_cc - \
                                    len(selected_af_col_pks_m2m_cc)
                                selected_af_col_pks_m2m_cc.update(random.sample(
                                    other_afiliados_pks_cc, k=min(num_to_add_cc, len(other_afiliados_pks_cc))))
                            if selected_af_col_pks_m2m_cc:
                                af_colectivos_existentes_cc = AfiliadoColectivo.objects.filter(
                                    pk__in=list(selected_af_col_pks_m2m_cc))
                                contrato_col.afiliados_colectivos.set(
                                    af_colectivos_existentes_cc)
                        except ObjectDoesNotExist:
                            stats_m['failed'] += 1
                            stats_m['errors']['DoesNotExist_ContCol_Prereq'] += 1
                            continue
                        except (IntegrityError, ValidationError) as e_cc:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_cc.__class__.__name__] += 1
                            logger.warning(
                                f"Error creando ContratoColectivo: {e_cc}")
                        except TypeError as e_type_cc:
                            stats_m['failed'] += 1
                            stats_m['errors']['TypeError_ContCol_Date'] += 1
                            logger.error(
                                f"TypeError creando ContratoColectivo (fecha_emision): {e_type_cc}", exc_info=True)
                        except Exception as e_cc:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_cc.__class__.__name__] += 1
                            logger.error(
                                f"Error creando ContratoColectivo: {e_cc}", exc_info=True)

                # --- Resto de los modelos (Facturas, Reclamaciones, Pagos, Notificaciones, Auditoria) ---
                # Estos modelos usan DateField para sus campos de fecha principales, por lo que
                # no deberían causar advertencias de zona horaria si se les asignan objetos `date`
                # o `datetime` de Python (ya que Django los manejará convirtiéndolos a fecha si es necesario
                # para DateField, o si son DateTimeField, los métodos save() del modelo ya deberían
                # tener la lógica de `make_aware` si es necesario).
                # El campo `tiempo_inicio` de AuditoriaSistema es `auto_now_add=True` que usa `timezone.now()`
                # y `control_fecha_actual` también, por lo que son "aware" por defecto.

                # Actualizar listas de contratos disponibles DESPUÉS de crearlos todos
                current_contrato_ind_pks = list(
                    set(contrato_ind_ids_created + contrato_ind_ids_db))
                current_contrato_col_pks = list(
                    set(contrato_col_ids_created + contrato_col_ids_db))

                # --- 9. Facturas ---
                model_name = 'Factura'
                stats_m = stats[model_name]
                qs_contratos_ind_fact = ContratoIndividual.objects.filter(
                    pk__in=current_contrato_ind_pks)
                if hasattr(ContratoIndividual, 'activo'):
                    qs_contratos_ind_fact = qs_contratos_ind_fact.filter(
                        activo=True)
                qs_contratos_col_fact = ContratoColectivo.objects.filter(
                    pk__in=current_contrato_col_pks)
                if hasattr(ContratoColectivo, 'activo'):
                    qs_contratos_col_fact = qs_contratos_col_fact.filter(
                        activo=True)

                if not qs_contratos_ind_fact.exists() and not qs_contratos_col_fact.exists():
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No Contratos activos para Facturas."))
                else:
                    for i_f in range(max(0, stats_m['requested'])):
                        factura_instance = None
                        contrato_obj_fact = None
                        contrato_ind_fk_fact = None
                        contrato_col_fk_fact = None
                        try:
                            use_individual_fact = False
                            can_use_ind_fact = qs_contratos_ind_fact.exists()
                            can_use_col_fact = qs_contratos_col_fact.exists()
                            if can_use_ind_fact and can_use_col_fact:
                                use_individual_fact = random.choice(
                                    [True, False])
                            elif can_use_ind_fact:
                                use_individual_fact = True
                            elif can_use_col_fact:
                                use_individual_fact = False
                            else:
                                if i_f == 0:
                                    self.stdout.write(self.style.ERROR(
                                        f"  {model_name}: No contratos activos para iteración {i_f+1}."))
                                break

                            if use_individual_fact:
                                contrato_obj_fact = qs_contratos_ind_fact.select_related(
                                    'intermediario', 'tarifa_aplicada').order_by('?').first()
                            else:
                                contrato_obj_fact = qs_contratos_col_fact.select_related(
                                    'intermediario', 'tarifa_aplicada').order_by('?').first()

                            if not contrato_obj_fact:
                                stats_m['failed'] += 1
                                stats_m['errors']['NoValidContractSelected_Fact'] += 1
                                continue
                            if use_individual_fact:
                                contrato_ind_fk_fact = contrato_obj_fact
                            else:
                                contrato_col_fk_fact = contrato_obj_fact

                            if not contrato_obj_fact.fecha_inicio_vigencia or not contrato_obj_fact.fecha_fin_vigencia or contrato_obj_fact.fecha_inicio_vigencia > contrato_obj_fact.fecha_fin_vigencia:
                                stats_m['failed'] += 1
                                stats_m['errors']['InvalidContractDatesForFactura'] += 1
                                continue

                            start_contract_fact = contrato_obj_fact.fecha_inicio_vigencia  # DateField
                            end_contract_fact = contrato_obj_fact.fecha_fin_vigencia  # DateField
                            if start_contract_fact > end_contract_fact:
                                stats_m['failed'] += 1
                                stats_m['errors']['ContractDatesInconsistent_Fact'] += 1
                                continue
                            max_days_offset_fact = (
                                end_contract_fact - start_contract_fact).days
                            days_offset_fact = random.randint(
                                0, max_days_offset_fact) if max_days_offset_fact >= 0 else 0
                            vigencia_desde_fact = start_contract_fact + \
                                timedelta(days=days_offset_fact)  # DateField

                            period_delta_fact_days = 30
                            if contrato_obj_fact.forma_pago == 'MENSUAL':
                                period_delta_fact_days = 30
                            elif contrato_obj_fact.forma_pago == 'TRIMESTRAL':
                                period_delta_fact_days = 90
                            elif contrato_obj_fact.forma_pago == 'SEMESTRAL':
                                period_delta_fact_days = 180
                            elif contrato_obj_fact.forma_pago == 'ANUAL':
                                period_delta_fact_days = 365
                            elif contrato_obj_fact.forma_pago == 'CONTADO' or not contrato_obj_fact.forma_pago:
                                remaining_days_fact = (
                                    end_contract_fact - vigencia_desde_fact).days + 1
                                period_delta_fact_days = max(
                                    1, remaining_days_fact)

                            vigencia_hasta_fact = min(
                                # DateField
                                vigencia_desde_fact + timedelta(days=period_delta_fact_days - 1), end_contract_fact)
                            if vigencia_hasta_fact < vigencia_desde_fact:
                                vigencia_hasta_fact = vigencia_desde_fact
                            dias_cobro_fact = (
                                vigencia_hasta_fact - vigencia_desde_fact).days + 1

                            monto_factura_val = Decimal('0.00')
                            if hasattr(contrato_obj_fact, 'monto_cuota_estimada') and isinstance(contrato_obj_fact.monto_cuota_estimada, Decimal) and contrato_obj_fact.monto_cuota_estimada > Decimal('0.00'):
                                monto_factura_val = contrato_obj_fact.monto_cuota_estimada
                            elif contrato_obj_fact.monto_total and contrato_obj_fact.monto_total > Decimal('0.00') and hasattr(contrato_obj_fact, 'cantidad_cuotas_estimadas') and contrato_obj_fact.cantidad_cuotas_estimadas and contrato_obj_fact.cantidad_cuotas_estimadas > 0:
                                try:
                                    monto_factura_val = (contrato_obj_fact.monto_total / Decimal(
                                        contrato_obj_fact.cantidad_cuotas_estimadas)).quantize(Decimal("0.01"), ROUND_HALF_UP)
                                except (TypeError, InvalidOperation):
                                    monto_factura_val = Decimal('0.00')

                            if monto_factura_val <= Decimal('0.00'):
                                min_val_f, max_val_f = (Decimal('50.00'), Decimal('1500.00')) if isinstance(
                                    contrato_obj_fact, ContratoIndividual) else (Decimal('500.00'), Decimal('15000.00'))
                                num_digits_f = len(
                                    str(int(max_val_f))) if max_val_f >= 1 else 3
                                monto_factura_val = fake.pydecimal(left_digits=max(
                                    1, num_digits_f - 2 if num_digits_f > 2 else 1), right_digits=2, positive=True, min_value=min_val_f, max_value=max_val_f)

                            factura_instance = Factura(contrato_individual=contrato_ind_fk_fact, contrato_colectivo=contrato_col_fk_fact, vigencia_recibo_desde=vigencia_desde_fact, vigencia_recibo_hasta=vigencia_hasta_fact,
                                                       intermediario=contrato_obj_fact.intermediario, monto=monto_factura_val, estatus_emision=random.choice(
                                                           [c[0] for c in CommonChoices.EMISION_RECIBO]),
                                                       aplica_igtf=fake.boolean(chance_of_getting_true=igtf_chance), dias_periodo_cobro=dias_cobro_fact, activo=fake.boolean(chance_of_getting_true=95),
                                                       primer_nombre=f"Factura {contrato_obj_fact.numero_contrato or contrato_obj_fact.pk}", primer_apellido=f"Per. {vigencia_desde_fact.strftime('%d%m%y')}-{vigencia_hasta_fact.strftime('%d%m%y')}")
                            factura_instance.save()
                            stats_m['created'] += 1
                            if factura_instance.pk not in factura_ids_created:
                                factura_ids_created.append(factura_instance.pk)
                        except ObjectDoesNotExist:
                            stats_m['failed'] += 1
                            stats_m['errors']['DoesNotExist_Factura_Prereq'] += 1
                            continue
                        except (IntegrityError, ValidationError) as e_f:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_f.__class__.__name__] += 1
                            logger.warning(f"Error creando Factura: {e_f}")
                        except Exception as e_f:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_f.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Factura: {e_f}", exc_info=True)

                # --- 10. Reclamaciones ---
                model_name = 'Reclamacion'
                stats_m = stats[model_name]
                qs_contratos_ind_rec = ContratoIndividual.objects.filter(
                    pk__in=current_contrato_ind_pks)
                if hasattr(ContratoIndividual, 'activo'):
                    qs_contratos_ind_rec = qs_contratos_ind_rec.filter(
                        activo=True)
                qs_contratos_col_rec = ContratoColectivo.objects.filter(
                    pk__in=current_contrato_col_pks)
                if hasattr(ContratoColectivo, 'activo'):
                    qs_contratos_col_rec = qs_contratos_col_rec.filter(
                        activo=True)

                if not qs_contratos_ind_rec.exists() and not qs_contratos_col_rec.exists():
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No Contratos activos para Reclamaciones."))
                else:
                    diagnosticos_validos = [d[0]
                                            for d in CommonChoices.DIAGNOSTICOS if d[0]]
                    tipos_validos_rec = [t[0]
                                         for t in CommonChoices.TIPO_RECLAMACION]
                    estados_validos_rec = [e[0]
                                           for e in CommonChoices.ESTADO_RECLAMACION]
                    available_user_pks_rec = list(
                        set(user_ids_created + user_ids_db))
                    for i_rec in range(max(0, stats_m['requested'])):
                        reclamacion_instance = None
                        contrato_obj_rec = None
                        contrato_ind_fk_rec = None
                        contrato_col_fk_rec = None
                        try:
                            use_individual_rec = False
                            can_use_ind_rec = qs_contratos_ind_rec.exists()
                            can_use_col_rec = qs_contratos_col_rec.exists()
                            if can_use_ind_rec and can_use_col_rec:
                                use_individual_rec = random.choice(
                                    [True, False])
                            elif can_use_ind_rec:
                                use_individual_rec = True
                            elif can_use_col_rec:
                                use_individual_rec = False
                            else:
                                if i_rec == 0:
                                    self.stdout.write(self.style.ERROR(
                                        f"  {model_name}: No contratos activos para iteración {i_rec+1}."))
                                break

                            if use_individual_rec:
                                contrato_obj_rec = qs_contratos_ind_rec.order_by(
                                    '?').first()
                            else:
                                contrato_obj_rec = qs_contratos_col_rec.order_by(
                                    '?').first()

                            if not contrato_obj_rec:
                                stats_m['failed'] += 1
                                stats_m['errors']['NoValidContractSelected_Rec'] += 1
                                continue
                            if use_individual_rec:
                                contrato_ind_fk_rec = contrato_obj_rec
                            else:
                                contrato_col_fk_rec = contrato_obj_rec

                            if not contrato_obj_rec.fecha_inicio_vigencia or not contrato_obj_rec.fecha_fin_vigencia or contrato_obj_rec.fecha_inicio_vigencia > contrato_obj_rec.fecha_fin_vigencia:
                                stats_m['failed'] += 1
                                stats_m['errors']['InvalidContractDatesForReclamacion'] += 1
                                continue

                            fecha_evento_rec = fake.date_between_dates(
                                date_start=contrato_obj_rec.fecha_inicio_vigencia, date_end=contrato_obj_rec.fecha_fin_vigencia)  # DateField
                            fecha_rec_val = min(
                                # DateField
                                fecha_evento_rec + timedelta(days=random.randint(1, 30)), date.today())
                            monto_rec_val = fake.pydecimal(left_digits=5, right_digits=2, positive=True, min_value=Decimal(
                                '10.00'), max_value=Decimal('5000.00'))
                            if contrato_obj_rec.suma_asegurada and isinstance(contrato_obj_rec.suma_asegurada, Decimal) and contrato_obj_rec.suma_asegurada > 0 and monto_rec_val > contrato_obj_rec.suma_asegurada:
                                monto_rec_val = (contrato_obj_rec.suma_asegurada * Decimal(
                                    random.uniform(0.1, 0.9))).quantize(Decimal("0.01"), ROUND_HALF_UP)
                            if monto_rec_val <= 0:
                                monto_rec_val = Decimal('10.00')
                            estado_rec_val = random.choice(estados_validos_rec)
                            fecha_cierre_rec = None  # DateField
                            if estado_rec_val in ['APROBADA', 'RECHAZADA', 'CERRADA', 'PAGADA']:
                                fecha_cierre_rec = min(
                                    fecha_rec_val + timedelta(days=random.randint(5, 90)), date.today())
                            usuario_asignado_rec_id = get_random_pk_from_lists(available_user_pks_rec, [
                            ], allow_none=True, model_name_for_error="Usuario para Reclamacion")

                            reclamacion_instance = Reclamacion(contrato_individual=contrato_ind_fk_rec, contrato_colectivo=contrato_col_fk_rec, tipo_reclamacion=random.choice(tipos_validos_rec),
                                                               diagnostico_principal=random.choice(diagnosticos_validos) if diagnosticos_validos else None, estado=estado_rec_val,
                                                               descripcion_reclamo=fake.paragraph(nb_sentences=random.randint(2, 5)), monto_reclamado=monto_rec_val, fecha_reclamo=fecha_rec_val,
                                                               fecha_cierre_reclamo=fecha_cierre_rec, usuario_asignado_id=usuario_asignado_rec_id, activo=fake.boolean(
                                                                   chance_of_getting_true=95),
                                                               primer_nombre=f"Reclamo Cont.", primer_apellido=f"{contrato_obj_rec.numero_contrato or contrato_obj_rec.pk}-{fecha_rec_val.strftime('%d%m%y')}")
                            reclamacion_instance.save()
                            stats_m['created'] += 1
                            if reclamacion_instance.pk not in reclamacion_ids_created:
                                reclamacion_ids_created.append(
                                    reclamacion_instance.pk)
                        except ObjectDoesNotExist:
                            stats_m['failed'] += 1
                            stats_m['errors']['DoesNotExist_Reclamacion_Prereq'] += 1
                            continue
                        except (IntegrityError, ValidationError) as e_r:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_r.__class__.__name__] += 1
                            logger.warning(f"Error creando Reclamacion: {e_r}")
                        except Exception as e_r:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_r.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Reclamacion: {e_r}", exc_info=True)

                # --- 11. Pagos ---
                model_name = 'Pago'
                stats_m = stats[model_name]
                current_factura_pks_for_pago = list(
                    set(factura_ids_created + factura_ids_db))
                current_reclamacion_pks_for_pago = list(
                    set(reclamacion_ids_created + reclamacion_ids_db))

                if not current_factura_pks_for_pago and not current_reclamacion_pks_for_pago:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {model_name}: No Facturas or Reclamaciones disponibles para Pagos."))
                else:
                    pagos_creados_count = 0
                    max_attempts_find_target_pago = stats_m['requested'] * 5
                    for attempt_pago in range(max_attempts_find_target_pago):
                        if pagos_creados_count >= stats_m['requested']:
                            break
                        target_obj_pago = None
                        target_factura_id_pago = None
                        target_reclamacion_id_pago = None
                        pendiente_pago = Decimal('0.00')
                        fecha_ref_pago_val = date.today()  # DateField
                        target_found_pago = False
                        try:
                            search_factura_first_pago = random.choice([True, False]) if (
                                current_factura_pks_for_pago and current_reclamacion_pks_for_pago) else bool(current_factura_pks_for_pago)

                            if search_factura_first_pago and current_factura_pks_for_pago:
                                target_obj_pago = Factura.objects.filter(
                                    monto_pendiente__gt=Factura.TOLERANCE, activo=True, pk__in=current_factura_pks_for_pago).order_by('?').first()
                                if target_obj_pago:
                                    target_factura_id_pago = target_obj_pago.pk
                                    pendiente_pago = target_obj_pago.monto_pendiente
                                    fecha_ref_pago_val = target_obj_pago.fecha_creacion.date() if isinstance(
                                        # DateField
                                        target_obj_pago.fecha_creacion, datetime) else target_obj_pago.fecha_creacion or date.today()
                                    target_found_pago = True

                            if not target_found_pago and current_reclamacion_pks_for_pago:
                                target_obj_pago = Reclamacion.objects.annotate(total_pagado_activo=Coalesce(Sum('pagos__monto_pago', filter=Q(pagos__activo=True)), Decimal('0.00'), output_field=DecimalField())) \
                                    .filter(estado='APROBADA', activo=True, monto_reclamado__gt=F('total_pagado_activo') + Pago.TOLERANCE, pk__in=current_reclamacion_pks_for_pago).order_by('?').first()
                                if target_obj_pago:
                                    target_reclamacion_id_pago = target_obj_pago.pk
                                    pendiente_pago = max(Decimal('0.00'), (target_obj_pago.monto_reclamado or Decimal(
                                        '0.00')) - target_obj_pago.total_pagado_activo)
                                    fecha_ref_pago_val = target_obj_pago.fecha_reclamo or date.today()  # DateField
                                    target_found_pago = True

                            if not target_found_pago:
                                if not target_factura_id_pago and current_factura_pks_for_pago:
                                    target_obj_pago = Factura.objects.filter(
                                        monto_pendiente__gt=Factura.TOLERANCE, activo=True, pk__in=current_factura_pks_for_pago).order_by('?').first()
                                    if target_obj_pago:
                                        target_factura_id_pago = target_obj_pago.pk
                                        pendiente_pago = target_obj_pago.monto_pendiente
                                        fecha_ref_pago_val = target_obj_pago.fecha_creacion.date() if isinstance(
                                            # DateField
                                            target_obj_pago.fecha_creacion, datetime) else target_obj_pago.fecha_creacion or date.today()
                                        target_found_pago = True

                            if not target_found_pago or not target_obj_pago:
                                if attempt_pago > stats_m['requested'] * 2 and pagos_creados_count < stats_m['requested']:
                                    self.stdout.write(self.style.NOTICE(
                                        f"  Pago: No más objetivos después de {pagos_creados_count} creados (intento {attempt_pago + 1}/{max_attempts_find_target_pago})."))
                                if attempt_pago >= max_attempts_find_target_pago - 1 and pagos_creados_count < stats_m['requested']:
                                    self.stdout.write(self.style.WARNING(
                                        f"  Pago: Agotados intentos para encontrar objetivos para Pagos. Creados: {pagos_creados_count}/{stats_m['requested']}."))
                                    break
                                continue

                            if pendiente_pago <= (Pago.TOLERANCE if target_reclamacion_id_pago else Factura.TOLERANCE):
                                continue

                            is_partial_pago = fake.boolean(
                                chance_of_getting_true=pago_parcial_chance)
                            monto_pag_val = (pendiente_pago * Decimal(random.uniform(0.1, 0.8))).quantize(
                                Decimal("0.01"), ROUND_HALF_UP) if is_partial_pago else pendiente_pago
                            monto_pag_val = max(Decimal('0.01'), min(
                                monto_pag_val, pendiente_pago))

                            start_date_pay = min(
                                fecha_ref_pago_val, date.today())
                            try:
                                fecha_pag_val = fake.date_between_dates(
                                    date_start=start_date_pay, date_end=date.today())  # DateField
                            except ValueError:
                                fecha_pag_val = date.today()

                            aplica_igtf_para_este_pago = fake.boolean(
                                chance_of_getting_true=igtf_chance)

                            pago_instance = Pago(
                                factura_id=target_factura_id_pago,
                                reclamacion_id=target_reclamacion_id_pago,
                                forma_pago=random.choice(
                                    [c[0] for c in CommonChoices.FORMA_PAGO_RECLAMACION]),
                                fecha_pago=fecha_pag_val,
                                monto_pago=monto_pag_val,
                                aplica_igtf_pago=aplica_igtf_para_este_pago,  # <--- AÑADIDO AQUÍ
                                referencia_pago=fake.bothify(
                                    text='Ref-#####-???'),
                                activo=True,
                                primer_nombre=f"Pago Ref.",
                                primer_apellido=f"{target_obj_pago.pk if target_obj_pago else 'N/A'}-{fecha_pag_val.strftime('%d%m%y')}"
                            )
                            logger.info(
                                f"--- SEEDER: PREPARANDO PARA GUARDAR Pago para target {target_obj_pago.pk if target_obj_pago else 'N/A'} (IGTF: {aplica_igtf_para_este_pago}) ---")
                            pago_instance.save()
                            logger.info(
                                f"--- SEEDER: Pago PK {pago_instance.pk} GUARDADO ---")

                            stats_m['created'] += 1
                            pago_ids_created.append(pago_instance.pk)
                            pagos_creados_count += 1
                        except ObjectDoesNotExist:
                            stats_m['failed'] += 1
                            stats_m['errors']['DoesNotExist_Pago_Target'] += 1
                            continue
                        except (IntegrityError, InvalidOperation, ValidationError) as e_p:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_p.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Pago: {e_p}", exc_info=True)
                        except Exception as e_p:
                            stats_m['failed'] += 1
                            stats_m['errors'][e_p.__class__.__name__] += 1
                            logger.error(
                                f"Error creando Pago: {e_p}", exc_info=True)
                    if pagos_creados_count < stats_m['requested']:
                        self.stdout.write(self.style.WARNING(
                            f"  Pago: Solo se crearon {pagos_creados_count} de {stats_m['requested']}."))

                # --- 12. Notificaciones ---
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
        if options.get('pagos', 0) > 0:
            if not options['clean'] and not hasattr(self, '_last_rc_pk_before_pagos_val'):
                self._last_rc_pk_before_pagos_val = RegistroComision.objects.order_by(
                    '-pk').first().pk if RegistroComision.objects.exists() else 0

        current_registro_comision_count = RegistroComision.objects.count()
        if options['clean']:
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
