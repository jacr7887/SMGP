from myapp.commons import CommonChoices
from myapp.licensing import (
    activate_or_update_license, check_license, _parse_and_validate_license_key,
    # Asegúrate que MIN_EXPECTED_KEY_LENGTH esté definido en licensing.py
    MIN_KEY_LENGTH, MIN_EXPECTED_KEY_LENGTH
)
from myapp.validators import (
    validate_rif, validate_cedula, validate_numero_contrato, validate_fecha_nacimiento,
    validate_file_size, validate_file_type, validate_email_domain, RIF_PATTERN,
    CEDULA_PATTERN_PROCESSED, CONTRATO_PATTERN
)
from myapp.forms import (
    LoginForm, AfiliadoIndividualForm, AfiliadoColectivoForm, IntermediarioForm,
    ContratoIndividualForm, ContratoColectivoForm, ReclamacionForm, PagoForm,
    FacturaForm, TarifaForm, LicenseActivationForm, FormularioCreacionUsuario,
    FormularioEdicionUsuario, RegistroComisionForm
)
from myapp.models import (
    Usuario, Intermediario, AfiliadoIndividual, AfiliadoColectivo,
    Tarifa, ContratoIndividual, ContratoColectivo, Reclamacion,
    Factura, Pago, AuditoriaSistema, Notificacion, LicenseInfo, RegistroComision
)
# import environ # No parece usarse, se puede quitar
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import Permission  # Para asignar permisos
# Para obtener el ContentType del modelo
from django.contrib.contenttypes.models import ContentType

from django.urls import reverse, reverse_lazy
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.conf import settings
from django.test.utils import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
import uuid
import re

# Importaciones específicas para pruebas y lógica de prueba
from dateutil.relativedelta import relativedelta
import nacl.signing
import nacl.encoding
import json
# import base64 # No se usa directamente, nacl.encoding lo maneja
from unittest import mock
import logging

logger_tests = logging.getLogger("myapp.tests")  # Logger específico para tests
logging.getLogger('myapp.tests').setLevel(logging.DEBUG)
logging.getLogger('myapp.licensing').setLevel(
    logging.DEBUG)  # Específico para el módulo de licencias
logging.getLogger('myapp.tests').setLevel(
    logging.DEBUG)  # Para ver los logs de tests.py

RAMO_ABREVIATURAS = {
    'HCM': 'HCM', 'VIDA': 'VID', 'VEHICULOS': 'VEH', 'HOGAR': 'HOG',
    'PYME': 'PYM', 'ACCIDENTES_PERSONALES': 'AP', 'SEPELIO': 'SEP',
    'VIAJES': 'VIA', 'EDUCATIVO': 'EDU', 'MASCOTAS': 'MAS', 'OTROS': 'OTR',
}

RANGO_ETARIO_ABREVIATURAS = {
    '0-17': '0017', '18-25': '1825', '26-35': '2635', '36-45': '3645',
    '46-55': '4655', '56-65': '5665', '66-70': '6670', '71-75': '7175',
    '76-80': '7680', '81-89': '8189', '90-99': '9099',
}
TEST_PUBLIC_KEY_B64 = "7cwRaQZ3q01wzRIUq1ck+ZfCQ8/YYdQt7azozaFgkH8="
TEST_PRIVATE_KEY_B64 = "RCFuK3Jgq+uMJN7R0FwA00gY/oT/N9pbiAxQZtpyRJSf2IZ9TmAkvThkNWhsMMwsOE9SJt+3G8eHmamJv+JEeA=="
ED25519_SEED_SIZE = 32
ED25519_SIGNING_KEY_SIZE = 64


class SimplestCryptoPairTest(TestCase):
    """
    Esta clase de test se enfoca ÚNICAMENTE en verificar si el par de claves
    TEST_PRIVATE_KEY_B64 y TEST_PUBLIC_KEY_B64 funcionan juntas directamente
    usando PyNaCl, imitando la lógica de tu aplicación.
    """

    def test_direct_crypto_operations_with_test_keys(self):
        logger_tests.info(
            "--- Iniciando test_direct_crypto_operations_with_test_keys ---")

        private_b64_from_constant = TEST_PRIVATE_KEY_B64
        expected_public_b64_from_constant = TEST_PUBLIC_KEY_B64

        logger_tests.info(
            f"Usando TEST_PRIVATE_KEY_B64 para firmar (primeros 10): {private_b64_from_constant[:10]}...")
        logger_tests.info(
            f"Clave pública ESPERADA (TEST_PUBLIC_KEY_B64): {expected_public_b64_from_constant}")

        message_to_sign_bytes = b"Este es un mensaje de prueba directo para verificar el par de claves."

        try:
            decoded_private_bytes = nacl.encoding.Base64Encoder.decode(
                private_b64_from_constant.encode('utf-8'))
            seed_for_signing: bytes

            if len(decoded_private_bytes) == ED25519_SEED_SIZE:
                seed_for_signing = decoded_private_bytes
            elif len(decoded_private_bytes) == ED25519_SIGNING_KEY_SIZE:
                seed_for_signing = decoded_private_bytes[:ED25519_SEED_SIZE]
            else:
                self.fail(
                    f"Longitud de TEST_PRIVATE_KEY_B64 decodificada ({len(decoded_private_bytes)}) es inválida.")
                return

            signing_key = nacl.signing.SigningKey(seed_for_signing)
            derived_verify_key_object = signing_key.verify_key
            derived_public_b64 = nacl.encoding.Base64Encoder.encode(
                derived_verify_key_object.encode()).decode('utf-8')

            logger_tests.info(
                f"Clave pública DERIVADA de TEST_PRIVATE_KEY_B64: {derived_public_b64}")
            self.assertEqual(derived_public_b64, expected_public_b64_from_constant,
                             "La TEST_PUBLIC_KEY_B64 en la constante no coincide con la derivada de TEST_PRIVATE_KEY_B64.")

            verify_key_to_use = derived_verify_key_object
            signature_bytes = signing_key.sign(message_to_sign_bytes).signature
            self.assertEqual(len(signature_bytes), 64,
                             "La firma generada no tiene 64 bytes.")
            logger_tests.info(
                f"Mensaje original (bytes): {message_to_sign_bytes}")
            logger_tests.info(f"Firma generada (hex): {signature_bytes.hex()}")

            verified_message = verify_key_to_use.verify(
                message_to_sign_bytes, signature_bytes)
            self.assertEqual(verified_message, message_to_sign_bytes,
                             "La verificación directa del par de claves (mensaje vs firma) falló.")
            logger_tests.info(
                "¡Verificación directa del par de claves (mensaje vs firma) EXITOSA!")

        except nacl.exceptions.BadSignatureError:
            logger_tests.error(
                "¡BadSignatureError en test_direct_crypto_operations_with_test_keys!", exc_info=True)
            self.fail(
                "BadSignatureError ocurrió en la prueba directa del par de claves.")
        except Exception as e:
            logger_tests.error(
                f"Error inesperado en test_direct_crypto_operations_with_test_keys: {type(e).__name__} - {e}", exc_info=True)
            self.fail(
                f"Error inesperado en test_direct_crypto_operations_with_test_keys: {e}")

        logger_tests.info(
            "--- Finalizando test_direct_crypto_operations_with_test_keys ---")


def generate_test_license_key(private_key_b64, days_valid=30, activation_days_limit=7):
    try:
        decoded_private_key_bytes = nacl.encoding.Base64Encoder.decode(
            private_key_b64.encode('utf-8'))
        key_len = len(decoded_private_key_bytes)

        if key_len == ED25519_SEED_SIZE:
            signing_key = nacl.signing.SigningKey(decoded_private_key_bytes)
        elif key_len == ED25519_SIGNING_KEY_SIZE:
            signing_key = nacl.signing.SigningKey(
                decoded_private_key_bytes[:ED25519_SEED_SIZE])
        else:
            raise ValueError(
                f"Decoded private key is {key_len} bytes. Expected {ED25519_SEED_SIZE} (seed) or "
                f"{ED25519_SIGNING_KEY_SIZE} (full private key)."
            )
    except Exception as e:
        logger_tests.error(
            f"Error inicializando SigningKey: {type(e).__name__} - {e}", exc_info=True)
        raise

    payload = {
        "iss": "SMGPTestIssuer", "sub": "TestLicensee",
        "exp": (date.today() + timedelta(days=days_valid)).isoformat(),
        "act_by": (date.today() + timedelta(days=activation_days_limit)).isoformat(),
        "type": "premium_test", "iat": date.today().isoformat()
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signed_payload = signing_key.sign(payload_bytes)
    # DEBUG: Verificar longitud de la firma cruda
    logger_tests.debug(
        f"generate_test_license_key: Longitud de signed_payload.signature: {len(signed_payload.signature)}")
    if len(signed_payload.signature) != 64:
        logger_tests.error(
            f"generate_test_license_key: ¡LA FIRMA CRUDA NO TIENE 64 BYTES! Tiene {len(signed_payload.signature)}")

    payload_b64_final = nacl.encoding.Base64Encoder.encode(
        payload_bytes).decode('utf-8')
    signature_b64_final = nacl.encoding.Base64Encoder.encode(
        signed_payload.signature).decode('utf-8')

    signed_payload = signing_key.sign(payload_bytes)
    logger_tests.info(
        # DEBE SER 64
        f"generate_test_license_key: RAW signature bytes length: {len(signed_payload.signature)}")
    logger_tests.info(
        f"generate_test_license_key: RAW signature bytes (hex): {signed_payload.signature.hex()}")

    payload_b64_final = nacl.encoding.Base64Encoder.encode(
        payload_bytes).decode('utf-8')
    signature_b64_final = nacl.encoding.Base64Encoder.encode(
        signed_payload.signature).decode('utf-8')
    logger_tests.info(
        f"generate_test_license_key: Encoded B64 signature: {signature_b64_final}")

    return f"SMGP-{payload_b64_final}.{signature_b64_final}"


VALID_TEST_LICENSE_KEY = generate_test_license_key(TEST_PRIVATE_KEY_B64)
EXPIRED_TEST_LICENSE_KEY = generate_test_license_key(
    TEST_PRIVATE_KEY_B64, days_valid=-5)
UNACTIVATABLE_LICENSE_KEY = generate_test_license_key(
    TEST_PRIVATE_KEY_B64, activation_days_limit=-2)


UserModel = get_user_model()


@override_settings(
    # Asegúrate que esta constante exista
    SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64,
    WHITENOISE_AUTOREFRESH=True,  # Opcional, para tests de staticfiles
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'  # Opcional
)
@override_settings(
    SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64,
    WHITENOISE_AUTOREFRESH=True,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)
class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = UserModel.objects.create_superuser(
            email='admin@example.com', password='adminpassword',
            primer_nombre='Admin', primer_apellido='User', tipo_usuario='ADMIN'
        )
        cls.normal_user = UserModel.objects.create_user(
            email='user@example.com', password='userpassword',
            primer_nombre='Normal', primer_apellido='User',
            nivel_acceso=1, tipo_usuario='CLIENTE'
        )
        try:
            content_type = ContentType.objects.get_for_model(LicenseInfo)
            permission_codename = 'change_licenseinfo'
            if Permission.objects.filter(content_type=content_type, codename=permission_codename).exists():
                permission = Permission.objects.get(
                    content_type=content_type, codename=permission_codename)
                cls.superuser.user_permissions.add(permission)
            else:
                logger_tests.warning(
                    f"Permiso '{permission_codename}' no encontrado para LicenseInfo.")
        except Exception as e:
            logger_tests.error(
                f"Error asignando permiso 'change_licenseinfo': {e}")

        cls.intermediario = Intermediario.objects.create(
            nombre_completo="Intermediario de Prueba", rif="J-12345678-9",
            porcentaje_comision=Decimal('10.00'),
            primer_nombre="Inter", primer_apellido="Mediario"
        )
        cls.tarifa = Tarifa.objects.create(
            ramo='HCM', rango_etario='18-25',
            fecha_aplicacion=date.today() - timedelta(days=30),
            monto_anual=Decimal('1200.00'),
            primer_nombre="Tarifa", primer_apellido="Prueba"
        )
        cls.afiliado_individual = AfiliadoIndividual.objects.create(
            primer_nombre="Juan", primer_apellido="Perez",
            tipo_identificacion=CommonChoices.TIPO_IDENTIFICACION[0][
                0] if CommonChoices.TIPO_IDENTIFICACION else 'CEDULA',
            cedula="V-12345678", fecha_nacimiento=date(1990, 1, 1),
            sexo='M', estado_civil='S', nacionalidad='Venezolano',
            estado='Distrito Capital', intermediario=cls.intermediario
        )
        cls.afiliado_colectivo_empresa = AfiliadoColectivo.objects.create(
            razon_social="Empresa de Prueba S.A.", rif="J-98765432-1",
            tipo_empresa='PRIVADA', estado='Miranda', intermediario=cls.intermediario
        )
        if VALID_TEST_LICENSE_KEY:  # Asegúrate que VALID_TEST_LICENSE_KEY esté definido
            LicenseInfo.objects.update_or_create(
                pk=LicenseInfo.SINGLETON_ID,
                defaults={'license_key': VALID_TEST_LICENSE_KEY,
                          'expiry_date': date.today() + timedelta(days=30)}
            )

# --- MODEL TESTS ---


class UsuarioModelTests(BaseTestCase):
    def test_create_superuser(self):
        self.assertTrue(self.superuser.is_superuser)
        self.assertTrue(self.superuser.is_staff)
        self.assertEqual(self.superuser.nivel_acceso, 5)
        self.assertEqual(str(self.superuser), "User, Admin")

    def test_create_normal_user(self):
        self.assertFalse(self.normal_user.is_superuser)
        self.assertFalse(self.normal_user.is_staff)
        self.assertEqual(self.normal_user.nivel_acceso, 1)
        self.assertEqual(str(self.normal_user), "User, Normal")

    def test_get_full_name(self):
        user = UserModel.objects.create_user(  # Usar create_user para que se llame el manager
            email='testfullname@example.com',
            password='password',  # create_user requiere password
            primer_nombre='Maria',
            segundo_nombre='De Los Angeles',
            primer_apellido='Gonzalez',
            segundo_apellido='Pirela'
        )
        self.assertEqual(user.get_full_name(),
                         "Gonzalez Pirela, Maria De Los Angeles")

    def test_username_generation(self):
        user = UserModel.objects.create_user(
            email='anotheruser@example.com',
            password='password',
            primer_nombre='Otro',
            primer_apellido='Usuario'
        )
        self.assertTrue(user.username.startswith("anotheruser_"))
        self.assertTrue(len(user.username) <= 150)  # Chequear max_length


class LicenseInfoModelTests(BaseTestCase):
    def test_singleton_behavior(self):
        # LicenseInfo.objects.all().delete() # No es necesario, setUpTestData ya crea una
        lic1 = LicenseInfo.objects.get(pk=LicenseInfo.SINGLETON_ID)
        self.assertEqual(lic1.pk, LicenseInfo.SINGLETON_ID)

        # Probar que clean() previene crear otra si ya existe la SINGLETON_ID con un pk diferente
        another_instance = LicenseInfo(
            pk=2, license_key="another", expiry_date=date.today())
        with self.assertRaises(ValidationError) as cm:
            another_instance.clean()
        self.assertIn(
            f"Solo puede existir una configuración de licencia con ID={LicenseInfo.SINGLETON_ID}", str(cm.exception))

    def test_is_valid_property(self):
        # LicenseInfo.objects.all().delete() # No es necesario
        valid_license, _ = LicenseInfo.objects.update_or_create(
            pk=LicenseInfo.SINGLETON_ID,
            defaults={
                'license_key': "validkey",
                'expiry_date': date.today() + timedelta(days=1)
            }
        )
        self.assertTrue(valid_license.is_valid)

        expired_license, _ = LicenseInfo.objects.update_or_create(
            pk=LicenseInfo.SINGLETON_ID,
            defaults={
                'license_key': "expiredkey",
                'expiry_date': date.today() - timedelta(days=1)
            }
        )
        self.assertFalse(expired_license.is_valid)

        today_license, _ = LicenseInfo.objects.update_or_create(
            pk=LicenseInfo.SINGLETON_ID,
            defaults={
                'license_key': "todaykey",
                'expiry_date': date.today()
            }
        )
        self.assertTrue(today_license.is_valid)


class NotificacionModelTests(BaseTestCase):
    def test_create_notificacion(self):
        # Notificacion.objects.all().delete() # No es necesario si no hay conflictos de PK
        notif = Notificacion.objects.create(
            usuario=self.normal_user,
            mensaje="Esta es una notificación de prueba.",
            tipo='info'
        )
        self.assertEqual(Notificacion.objects.filter(
            pk=notif.pk).count(), 1)  # Ser más específico
        self.assertEqual(str(
            notif), f"Para {self.normal_user.email}: Esta es una notificación de prueba.... (No Leída)")


class AfiliadoIndividualModelTests(BaseTestCase):
    def test_create_afiliado_individual(self):
        self.assertEqual(AfiliadoIndividual.objects.filter(
            cedula="V-12345678").count(), 1)
        afiliado = AfiliadoIndividual.objects.get(cedula="V-12345678")
        self.assertEqual(afiliado.primer_nombre, "Juan")
        self.assertEqual(str(afiliado), "Juan Perez (V-12345678)")
        self.assertTrue(afiliado.activo)
        self.assertIsNotNone(afiliado.codigo_validacion)
        self.assertTrue(afiliado.codigo_validacion.startswith("VAL-AFI"))

    def test_afiliado_edad_property(self):
        test_date = date(1990, 1, 1)
        # AfiliadoIndividual.objects.filter(cedula="V-87654321").delete() # Para evitar colisiones si se corre varias veces
        afiliado = AfiliadoIndividual.objects.create(
            primer_nombre="EdadTest", primer_apellido="User",
            tipo_identificacion=CommonChoices.TIPO_IDENTIFICACION[0][0], cedula="V-87654321",
            fecha_nacimiento=test_date, sexo='M', estado_civil='S',
            nacionalidad='Venezolano', estado='Lara'
        )
        expected_age = (date.today().year - test_date.year) - \
                       ((date.today().month, date.today().day)
                        < (test_date.month, test_date.day))
        self.assertEqual(afiliado.edad, expected_age)

    def test_afiliado_nombre_completo(self):
        # AfiliadoIndividual.objects.filter(cedula="E-11223344").delete()
        afiliado = AfiliadoIndividual.objects.create(
            primer_nombre="Ana", segundo_nombre="Maria",
            primer_apellido="Gomez", segundo_apellido="Lopez",
            # 'CEDULA'
            tipo_identificacion=CommonChoices.TIPO_IDENTIFICACION[0][0],
            cedula="E-11223344",  # Asumiendo que validate_cedula permite 'E'
            fecha_nacimiento=date(1985, 5, 5), sexo='F', estado_civil='S',
            nacionalidad='Extranjera', estado='Carabobo'
        )
        self.assertEqual(afiliado.nombre_completo, "Gomez Lopez, Ana Maria")


class AfiliadoColectivoModelTests(BaseTestCase):
    def test_create_afiliado_colectivo(self):
        # self.afiliado_colectivo_empresa se crea en setUpTestData
        self.assertEqual(AfiliadoColectivo.objects.filter(
            rif="J-98765432-1").count(), 1)
        empresa = AfiliadoColectivo.objects.get(rif="J-98765432-1")
        self.assertEqual(empresa.razon_social, "Empresa de Prueba S.A.")
        self.assertEqual(
            str(empresa), "Empresa de Prueba S.A. (RIF: J-98765432-1)")
        self.assertTrue(empresa.activo)
        # Verificar los campos de ModeloBase según la lógica de save()
        self.assertEqual(empresa.primer_nombre, "Empresa de Prueba S.A."[:100])
        self.assertEqual(empresa.primer_apellido, "(Colectivo)")

    def test_afiliado_colectivo_nombre_completo(self):
        empresa = AfiliadoColectivo.objects.get(rif="J-98765432-1")
        self.assertEqual(empresa.nombre_completo, "Empresa de Prueba S.A.")


class IntermediarioModelTests(BaseTestCase):
    def test_create_intermediario(self):
        self.assertEqual(Intermediario.objects.filter(
            pk=self.intermediario.pk).count(), 1)
        inter = Intermediario.objects.get(pk=self.intermediario.pk)
        self.assertEqual(inter.nombre_completo, "Intermediario de Prueba")
        self.assertTrue(inter.codigo.startswith("INT-"))
        self.assertTrue(len(inter.codigo) <= 15)  # Chequear max_length
        self.assertEqual(
            str(inter), f"{inter.codigo} - Intermediario de Prueba")

    def test_intermediario_codigo_generation_on_save(self):
        inter_new = Intermediario.objects.create(
            nombre_completo="Nuevo Inter",
            primer_nombre="Nuevo", primer_apellido="Inter"
        )
        self.assertIsNotNone(inter_new.codigo)
        self.assertTrue(inter_new.codigo.startswith("INT-"))
        self.assertTrue(len(inter_new.codigo) <= 15)


class TarifaModelTests(BaseTestCase):
    def test_create_tarifa(self):
        self.assertEqual(Tarifa.objects.filter(pk=self.tarifa.pk).count(), 1)
        tarifa = Tarifa.objects.get(pk=self.tarifa.pk)
        self.assertEqual(tarifa.ramo, 'HCM')
        self.assertTrue(tarifa.codigo_tarifa.startswith("TAR-"))
        self.assertIn(RAMO_ABREVIATURAS[tarifa.ramo], tarifa.codigo_tarifa)
        self.assertIn(
            RANGO_ETARIO_ABREVIATURAS[tarifa.rango_etario], tarifa.codigo_tarifa)
        # La validación de la comisión se elimina porque el campo ya no existe en Tarifa.

    def test_tarifa_montos_fraccionados(self):
        tarifa = Tarifa.objects.get(pk=self.tarifa.pk)
        self.assertEqual(tarifa.monto_mensual, Decimal('100.00'))
        self.assertEqual(tarifa.monto_trimestral, Decimal('300.00'))
        self.assertEqual(tarifa.monto_semestral, Decimal('600.00'))


class ContratoIndividualModelTests(BaseTestCase):
    def test_create_contrato_individual(self):
        contrato = ContratoIndividual.objects.create(
            afiliado=self.afiliado_individual,
            intermediario=self.intermediario,
            tarifa_aplicada=self.tarifa,
            ramo='HCM',
            forma_pago='MENSUAL',
            fecha_inicio_vigencia=date.today(),
            periodo_vigencia_meses=12,
            suma_asegurada=Decimal('50000.00'),
            contratante_cedula=self.afiliado_individual.cedula,
            tipo_identificacion_contratante='V',
            contratante_nombre=self.afiliado_individual.nombre_completo
        )
        self.assertEqual(ContratoIndividual.objects.filter(
            pk=contrato.pk).count(), 1)
        self.assertTrue(contrato.numero_contrato.startswith("CONT-IND-"))
        self.assertEqual(contrato.monto_total, Decimal('1200.00'))
        self.assertEqual(
            str(contrato), f"CI: {contrato.numero_contrato} - Juan Perez")

    def test_contrato_individual_monto_total_6_meses(self):
        # ContratoIndividual.objects.all().delete()
        contrato = ContratoIndividual.objects.create(
            afiliado=self.afiliado_individual,
            intermediario=self.intermediario,
            tarifa_aplicada=self.tarifa,
            ramo='HCM',
            forma_pago='MENSUAL',
            fecha_inicio_vigencia=date.today(),
            periodo_vigencia_meses=6,  # Cambio aquí
            suma_asegurada=Decimal('50000.00'),
            contratante_cedula=self.afiliado_individual.cedula,
            tipo_identificacion_contratante='V',
            contratante_nombre=self.afiliado_individual.nombre_completo
        )
        self.assertEqual(contrato.monto_total,
                         Decimal('600.00'))  # (1200/12)*6


class ContratoColectivoModelTests(BaseTestCase):
    def test_create_contrato_colectivo(self):
        # Crear el contrato. En este punto, rif y razon_social del contrato pueden ser None.
        contrato = ContratoColectivo.objects.create(
            intermediario=self.intermediario,
            tarifa_aplicada=self.tarifa,
            ramo='HCM',
            forma_pago='ANUAL',
            fecha_inicio_vigencia=date.today(),
            periodo_vigencia_meses=12,
            suma_asegurada=Decimal('200000.00'),
            cantidad_empleados=50,
            tipo_empresa='PRIVADA'
            # No pasamos rif ni razon_social aquí, asumimos que se derivarán o se establecerán después
        )

        # Verificar que los códigos se generen en el primer save (create)
        self.assertIsNotNone(contrato.numero_contrato,
                             "numero_contrato no se generó en el create")
        self.assertTrue(contrato.numero_contrato.startswith("CONT-COL-"))
        self.assertIsNotNone(contrato.numero_poliza,
                             "numero_poliza no se generó en el create")
        self.assertTrue(contrato.numero_poliza.startswith("POL-COL-"))
        self.assertIsNotNone(contrato.certificado,
                             "certificado no se generó en el create")
        self.assertTrue(contrato.certificado.startswith("CERT-COL-"))

        # Añadir el afiliado colectivo
        contrato.afiliados_colectivos.add(self.afiliado_colectivo_empresa)

        # Ahora, explícitamente tomar los datos del afiliado y asignarlos al contrato
        # Esto simula lo que harías en una vista o un form después de seleccionar los afiliados.
        primer_afiliado = contrato.afiliados_colectivos.first()
        if primer_afiliado:
            contrato.rif = primer_afiliado.rif
            contrato.razon_social = primer_afiliado.razon_social
            # Si también quieres que primer_nombre/apellido del contrato se actualicen:
            if contrato.razon_social:
                parts = contrato.razon_social.split(maxsplit=1)
                contrato.primer_nombre = parts[0][:100]
                contrato.primer_apellido = f"(Colectivo {contrato.rif or ''})"[
                    :100] if len(parts) > 1 else "(Colectivo)"

        # Guardar los cambios hechos explícitamente (RIF, razon_social, etc.)
        # Especificar update_fields es una buena práctica si solo quieres guardar esos.
        update_fields_list = ['rif', 'razon_social']
        if primer_afiliado:  # Solo añadir nombres si se actualizaron
            update_fields_list.extend(['primer_nombre', 'primer_apellido'])
        contrato.save(update_fields=update_fields_list)

        # Refrescar la instancia desde la BD para asegurar que tenemos los últimos datos
        contrato.refresh_from_db()

        self.assertEqual(ContratoColectivo.objects.filter(
            pk=contrato.pk).count(), 1)
        self.assertEqual(contrato.rif, self.afiliado_colectivo_empresa.rif)
        self.assertEqual(contrato.razon_social,
                         self.afiliado_colectivo_empresa.razon_social)
        # Asumiendo que monto_anual es correcto para 12 meses
        self.assertEqual(contrato.monto_total, self.tarifa.monto_anual)
        self.assertEqual(str(
            contrato), f"CC: {contrato.numero_contrato} - {contrato.razon_social} ({contrato.rif})")

    def test_contrato_colectivo_sin_afiliados_inicialmente(self):
        contrato = ContratoColectivo.objects.create(
            intermediario=self.intermediario,
            tarifa_aplicada=self.tarifa,
            ramo='PYME',
            forma_pago='MENSUAL',
            fecha_inicio_vigencia=date.today(),
            periodo_vigencia_meses=6,
            suma_asegurada=Decimal('10000.00'),
            cantidad_empleados=5,
            tipo_empresa='PRIVADA'
        )
        self.assertIsNone(contrato.rif)
        self.assertIsNone(contrato.razon_social)
        self.assertEqual(contrato.monto_total, self.tarifa.monto_anual / 2)


class ReclamacionModelTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Reclamacion.objects.all().delete() # No es necesario si no hay colisiones
        # ContratoIndividual.objects.all().delete() # No es necesario si no hay colisiones
        cls.contrato_ind_para_reclamacion = ContratoIndividual.objects.create(
            afiliado=cls.afiliado_individual,
            intermediario=cls.intermediario,
            tarifa_aplicada=cls.tarifa,
            ramo='HCM',
            fecha_inicio_vigencia=date.today() - timedelta(days=30),
            periodo_vigencia_meses=12,
            suma_asegurada=Decimal('10000.00'),
            tipo_identificacion_contratante='V',
            contratante_cedula=cls.afiliado_individual.cedula,
            contratante_nombre=cls.afiliado_individual.nombre_completo,
        )

    def test_create_reclamacion(self):
        # Reclamacion.objects.all().delete()
        reclamacion = Reclamacion.objects.create(
            contrato_individual=self.contrato_ind_para_reclamacion,
            fecha_reclamo=date.today(),
            tipo_reclamacion='MEDICA',
            descripcion_reclamo="Consulta médica por fiebre.",
            monto_reclamado=Decimal('150.00'),
            diagnostico_principal='SAL-CON-001',  # Clave de CommonChoices.DIAGNOSTICOS
            usuario_asignado=self.normal_user
        )
        self.assertEqual(Reclamacion.objects.filter(
            pk=reclamacion.pk).count(), 1)
        self.assertEqual(reclamacion.estado, 'ABIERTA')  # Default del modelo
        self.assertIn(
            self.contrato_ind_para_reclamacion.numero_contrato, str(reclamacion))


class FacturaPagoModelTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Factura.objects.all().delete()
        # Pago.objects.all().delete()
        # ContratoIndividual.objects.all().delete()

        cls.contrato_factura = ContratoIndividual.objects.create(
            afiliado=cls.afiliado_individual,
            intermediario=cls.intermediario,
            tarifa_aplicada=cls.tarifa,
            ramo='HCM',
            fecha_inicio_vigencia=date.today() - timedelta(days=60),
            periodo_vigencia_meses=12,
            # monto_total se calcula en save, no es necesario aquí
            suma_asegurada=Decimal('10000.00'),
            tipo_identificacion_contratante='V',
            contratante_cedula=cls.afiliado_individual.cedula,
            contratante_nombre=cls.afiliado_individual.nombre_completo,
        )
        cls.factura = Factura.objects.create(
            contrato_individual=cls.contrato_factura,
            vigencia_recibo_desde=date.today() - timedelta(days=30),
            # Asegurar que sea antes de hoy para PENDIENTE
            vigencia_recibo_hasta=date.today() - timedelta(days=1),
            monto=Decimal('100.00')
        )

    def test_create_factura(self):
        self.assertEqual(Factura.objects.filter(pk=self.factura.pk).count(), 1)
        # Más genérico por si cambia el formato interno
        self.assertTrue(self.factura.numero_recibo.startswith("REC-"))
        self.assertEqual(self.factura.monto_pendiente, Decimal('100.00'))
        self.assertFalse(self.factura.pagada)
        # El estatus se actualiza en save()
        # Si vigencia_recibo_hasta es < hoy - DIAS_VENCIMIENTO_FACTURA, será VENCIDA
        # Si no, será PENDIENTE. Asumamos PENDIENTE para este test.
        # Para que sea PENDIENTE, vigencia_recibo_hasta no debe estar muy en el pasado.
        # Si DIAS_VENCIMIENTO_FACTURA es 30, y vigencia_recibo_hasta es ayer, hoy > ayer + 30 es FALSO.
        # Entonces debería ser PENDIENTE.
        self.assertEqual(self.factura.estatus_factura, 'PENDIENTE')
        self.assertTrue(self.factura.relacion_ingreso.startswith("RI-"))

    def test_create_pago_para_factura_updates_factura(self):
        # Pago.objects.all().delete() # Limpiar pagos para este test
        pago1 = Pago.objects.create(
            factura=self.factura,
            fecha_pago=date.today(),
            monto_pago=Decimal('50.00'),
            forma_pago='TRANSFERENCIA',
            referencia_pago='REF123'
        )
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.monto_pendiente, Decimal('50.00'))
        self.assertFalse(self.factura.pagada)
        self.assertEqual(self.factura.estatus_factura, 'PENDIENTE')

        pago2 = Pago.objects.create(
            factura=self.factura,
            fecha_pago=date.today(),
            monto_pago=Decimal('50.00'),
            forma_pago='TRANSFERENCIA',
            referencia_pago='REF456'
        )
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.monto_pendiente, Decimal('0.00'))
        self.assertTrue(self.factura.pagada)
        self.assertEqual(self.factura.estatus_factura, 'PAGADA')
        self.assertEqual(Pago.objects.filter(factura=self.factura).count(), 2)


class AuditoriaSistemaModelTest(BaseTestCase):
    def test_create_auditoria(self):
        # AuditoriaSistema.objects.all().delete()
        auditoria = AuditoriaSistema.objects.create(
            usuario=self.normal_user,
            tipo_accion='CREACION',
            resultado_accion='EXITO',
            tabla_afectada='myapp_afiliadoindividual',
            registro_id_afectado=self.afiliado_individual.pk,
            detalle_accion='Creación de nuevo afiliado.',
            direccion_ip='127.0.0.1'
        )
        self.assertEqual(AuditoriaSistema.objects.filter(
            pk=auditoria.pk).count(), 1)


class RegistroComisionModelTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Configurar un intermediario padre para probar el override
        cls.intermediario_padre = Intermediario.objects.create(
            nombre_completo="Intermediario Padre de Prueba",
            # El padre también puede vender
            porcentaje_comision=Decimal('5.00'),
            porcentaje_override=Decimal('2.50'),  # Porcentaje de override
            primer_nombre="Padre", primer_apellido="Inter"
        )
        # Asignar el padre al intermediario vendedor
        cls.intermediario.intermediario_relacionado = cls.intermediario_padre
        cls.intermediario.save()

        cls.contrato_comision = ContratoIndividual.objects.create(
            afiliado=cls.afiliado_individual,
            intermediario=cls.intermediario,  # Venta hecha por el intermediario hijo
            tarifa_aplicada=cls.tarifa,
            ramo='HCM',
            fecha_inicio_vigencia=date.today() - timedelta(days=90),
            periodo_vigencia_meses=12,
            suma_asegurada=Decimal('10000.00'),
            tipo_identificacion_contratante='V',
            contratante_cedula=cls.afiliado_individual.cedula,
            contratante_nombre=cls.afiliado_individual.nombre_completo,
        )
        cls.factura_comision = Factura.objects.create(
            contrato_individual=cls.contrato_comision,
            monto=Decimal('100.00'),
            vigencia_recibo_desde=date.today() - timedelta(days=30),
            vigencia_recibo_hasta=date.today() - timedelta(days=1)
        )
        # El pago se crea en el test para disparar la señal

    def test_comisiones_creadas_por_signal_de_pago(self):
        # Crear el pago aquí para disparar la señal post_save
        pago_comision = Pago.objects.create(
            factura=self.factura_comision,
            monto_pago=Decimal('100.00'),
            fecha_pago=date.today()
        )

        # 1. Verificar la comisión DIRECTA para el vendedor
        comision_directa = RegistroComision.objects.filter(
            pago_cliente=pago_comision,
            tipo_comision='DIRECTA'
        ).first()

        self.assertIsNotNone(
            comision_directa, "La señal no creó la comisión DIRECTA.")
        self.assertEqual(comision_directa.intermediario, self.intermediario)
        # La nueva lógica toma el % del intermediario vendedor
        expected_percentage_directa = self.intermediario.porcentaje_comision  # 10.00%
        self.assertEqual(comision_directa.porcentaje_aplicado,
                         expected_percentage_directa)
        expected_monto_directa = (pago_comision.monto_pago * expected_percentage_directa /
                                  Decimal('100.00')).quantize(Decimal('0.01'), ROUND_HALF_UP)
        self.assertEqual(comision_directa.monto_comision,
                         expected_monto_directa)
        self.assertEqual(comision_directa.estatus_pago_comision, 'PENDIENTE')

        # 2. Verificar la comisión de OVERRIDE para el padre
        comision_override = RegistroComision.objects.filter(
            pago_cliente=pago_comision,
            tipo_comision='OVERRIDE'
        ).first()

        self.assertIsNotNone(
            comision_override, "La señal no creó la comisión de OVERRIDE.")
        self.assertEqual(comision_override.intermediario,
                         self.intermediario_padre)
        # La nueva lógica toma el % de override del intermediario padre
        expected_percentage_override = self.intermediario_padre.porcentaje_override  # 2.50%
        self.assertEqual(comision_override.porcentaje_aplicado,
                         expected_percentage_override)
        expected_monto_override = (pago_comision.monto_pago * expected_percentage_override /
                                   Decimal('100.00')).quantize(Decimal('0.01'), ROUND_HALF_UP)
        self.assertEqual(comision_override.monto_comision,
                         expected_monto_override)
        self.assertEqual(comision_override.intermediario_vendedor,
                         self.intermediario)  # Verifica quién vendió


# --- FORM TESTS ---


class LoginFormTests(BaseTestCase):
    def test_login_form_valid(self):
        form_data = {'username': 'user@example.com',
                     'password': 'userpassword'}
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_login_form_invalid_credentials(self):
        form_data = {'username': 'user@example.com',
                     'password': 'wrongpassword'}
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        # CORRECCIÓN: El mensaje de error específico del form.clean()
        self.assertIn("Correo electrónico o contraseña incorrectos.",
                      form.errors['__all__'][0])

    def test_login_form_inactive_user(self):
        user_to_test = Usuario.objects.get(email=self.normal_user.email)
        user_to_test.activo = False
        user_to_test.save()
        user_to_test.refresh_from_db()

        # print(f"DEBUG TEST (form): Usuario {user_to_test.email} TU campo 'activo': {user_to_test.activo}, Django 'is_active': {user_to_test.is_active}")
        self.assertFalse(user_to_test.activo)
        self.assertFalse(user_to_test.is_active)

        form_data = {'username': user_to_test.email,
                     'password': 'userpassword'}

        factory = RequestFactory()
        request_obj = factory.post('/dummy-login/')
        form = LoginForm(request=request_obj, data=form_data)

        is_form_valid_result = form.is_valid()
        # print(f"DEBUG TEST (form): form.is_valid() devolvió: {is_form_valid_result}")
        # if not is_form_valid_result:
        #     print(f"DEBUG TEST (form): Errores del form: {form.errors.as_json()}")

        self.assertFalse(is_form_valid_result)
        self.assertIn('__all__', form.errors)
        # CAMBIO: Esperar el mensaje de credenciales incorrectas, porque authenticate devuelve None
        self.assertIn("Correo electrónico o contraseña incorrectos.",
                      form.errors['__all__'][0])

        user_to_test.activo = True
        user_to_test.save()


class AfiliadoIndividualFormTests(BaseTestCase):
    def test_afiliado_individual_form_valid(self):
        form_data = {
            'primer_nombre': "Carlos", 'primer_apellido': "Rodriguez",
            # 'CEDULA'
            'tipo_identificacion': CommonChoices.TIPO_IDENTIFICACION[0][0],
            'cedula': "V-20123456",
            'fecha_nacimiento': "05/03/1988", 'sexo': 'M', 'estado_civil': 'C',
            'nacionalidad': 'Venezolano', 'estado': 'Aragua',
            'parentesco': 'TITULAR',
            'intermediario': self.intermediario.pk,
            'activo': True,
        }
        form = AfiliadoIndividualForm(data=form_data)
        if not form.is_valid():
            logger_tests.error(
                f"AfiliadoIndividualForm errors: {form.errors.as_json(escape_html=False)}")
        self.assertTrue(form.is_valid())

    def test_afiliado_individual_form_invalid_cedula(self):
        form_data = {
            'primer_nombre': "Test", 'primer_apellido': "User",
            # 'CEDULA'
            'tipo_identificacion': CommonChoices.TIPO_IDENTIFICACION[0][0],
            'cedula': "V-123",  # Cédula inválida
            'fecha_nacimiento': "01/01/1990", 'sexo': 'M', 'estado_civil': 'S',
            'nacionalidad': 'Venezolano', 'estado': 'Zulia',
            'parentesco': 'TITULAR',
        }
        form = AfiliadoIndividualForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('cedula', form.errors)
        # CORREGIDO: El mensaje exacto que produce el validador
        self.assertIn(
            "Longitud inválida para cédula 'V-123'. Debe tener 7 u 8 dígitos después de V/E.", form.errors['cedula'][0])


class ContratoIndividualFormTests(BaseTestCase):
    def test_contrato_individual_form_valid_with_periodo(self):
        # ContratoIndividual.objects.all().delete() # No es necesario si no hay colisiones
        form_data = {
            'afiliado': self.afiliado_individual.pk,
            'intermediario': self.intermediario.pk,
            'tarifa_aplicada': self.tarifa.pk,
            'ramo': 'HCM', 'forma_pago': 'MENSUAL', 'estatus': 'VIGENTE',
            'fecha_inicio_vigencia': date.today().strftime('%d/%m/%Y'),
            'periodo_vigencia_meses': 12,
            # fecha_fin_vigencia no se envía, se calculará
            'suma_asegurada': '10000.00',
            'tipo_identificacion_contratante': 'V',  # Clave de CommonChoices.TIPO_CEDULA
            'contratante_cedula': self.afiliado_individual.cedula,
            'contratante_nombre': 'Juan Perez',
            'activo': True,
            'consultar_afiliados_activos': False,
            'estatus_emision_recibo': 'SIN_EMITIR',
        }
        form = ContratoIndividualForm(data=form_data)
        if not form.is_valid():
            print("ContratoIndividualForm errors (periodo):",
                  form.errors.as_json(escape_html=False))
        self.assertTrue(form.is_valid())
        contrato = form.save()
        self.assertIsNotNone(contrato.fecha_fin_vigencia)
        self.assertEqual(contrato.fecha_fin_vigencia, date.today(
        ) + relativedelta(months=+12) - timedelta(days=1))

    def test_contrato_individual_form_valid_with_fecha_fin(self):
        # ContratoIndividual.objects.all().delete()
        fecha_inicio = date.today()
        fecha_fin = fecha_inicio + relativedelta(months=+6) - timedelta(days=1)
        form_data = {
            'afiliado': self.afiliado_individual.pk,
            'intermediario': self.intermediario.pk,
            'tarifa_aplicada': self.tarifa.pk,
            'ramo': 'HCM', 'forma_pago': 'TRIMESTRAL', 'estatus': 'VIGENTE',
            'fecha_inicio_vigencia': fecha_inicio.strftime('%d/%m/%Y'),
            'fecha_fin_vigencia': fecha_fin.strftime('%d/%m/%Y'),
            # periodo_vigencia_meses no se envía, se calculará
            'suma_asegurada': '25000.00',
            'tipo_identificacion_contratante': 'V',
            'contratante_cedula': self.afiliado_individual.cedula,
            'contratante_nombre': 'Juan Perez',
            'activo': True,
            'consultar_afiliados_activos': False,
            'estatus_emision_recibo': 'SIN_EMITIR',
        }
        form = ContratoIndividualForm(data=form_data)
        if not form.is_valid():
            print("ContratoIndividualForm errors (fecha_fin):",
                  form.errors.as_json(escape_html=False))
        self.assertTrue(form.is_valid())
        contrato = form.save()
        self.assertIsNotNone(contrato.periodo_vigencia_meses)
        self.assertEqual(contrato.periodo_vigencia_meses, 6)

    def test_contrato_individual_form_inconsistent_dates(self):
        # ContratoIndividual.objects.all().delete()
        form_data = {
            'afiliado': self.afiliado_individual.pk,
            'intermediario': self.intermediario.pk,
            'tarifa_aplicada': self.tarifa.pk,
            'ramo': 'HCM', 'forma_pago': 'MENSUAL', 'estatus': 'VIGENTE',
            'fecha_inicio_vigencia': date.today().strftime('%d/%m/%Y'),
            'periodo_vigencia_meses': 12,  # Inconsistente con fecha_fin_vigencia
            'fecha_fin_vigencia': (date.today() + relativedelta(months=+6) - timedelta(days=1)).strftime('%d/%m/%Y'),
            'suma_asegurada': '10000.00',
            'tipo_identificacion_contratante': 'V',
            'contratante_cedula': self.afiliado_individual.cedula,
            'contratante_nombre': 'Juan Perez',
            'activo': True,
            'consultar_afiliados_activos': False,
            'estatus_emision_recibo': 'SIN_EMITIR',
        }
        form = ContratoIndividualForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)  # El error es non-field
        # CORRECCIÓN: El mensaje de error específico del form.clean()
        self.assertTrue(
            any('Inconsistencia: La Fecha Fin' in error for error in form.errors['__all__']))


class LicenseActivationFormTest(BaseTestCase):
    def test_license_activation_form_valid(self):
        form = LicenseActivationForm(
            # MIN_KEY_LENGTH es 16
            data={'license_key': 'SMGP-' + 'A' * (MIN_KEY_LENGTH)})
        self.assertTrue(form.is_valid())

    def test_license_activation_form_too_short(self):
        form = LicenseActivationForm(
            data={'license_key': 'SMGP-short'})  # 10 caracteres
        self.assertFalse(form.is_valid())
        self.assertIn('license_key', form.errors)
        # CORREGIDO: Mensaje exacto del formulario
        self.assertIn(
            f"Asegúrese de que este valor tenga al menos {MIN_KEY_LENGTH} carácter(es) (tiene10).", form.errors['license_key'][0])

# --- VIEW TESTS ---


class AuthViewsTests(BaseTestCase):
    def test_login_view_get(self):
        response = self.client.get(reverse('myapp:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_login_view_post_success(self):
        response = self.client.post(reverse('myapp:login'), {
            'username': 'user@example.com', 'password': 'userpassword'
        })
        self.assertRedirects(response, reverse('myapp:home'))
        self.assertTrue(self._is_user_authenticated(email='user@example.com'))

    def _is_user_authenticated(self, email):
        user_id_in_session = self.client.session.get('_auth_user_id')
        if not user_id_in_session:
            return False
        try:
            user = UserModel.objects.get(pk=user_id_in_session)
            return user.email == email and user.is_authenticated
        except UserModel.DoesNotExist:
            return False

    def test_login_view_post_fail(self):
        response = self.client.post(reverse('myapp:login'), {
            'username': 'user@example.com', 'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._is_user_authenticated(email='user@example.com'))
        self.assertContains(
            response, "Correo electrónico o contraseña incorrectos.")

    def test_login_view_inactive_user(self):
        user_for_test = Usuario.objects.get(email=self.normal_user.email)
        user_for_test.activo = False
        user_for_test.save()
        user_for_test.refresh_from_db()

        self.assertFalse(user_for_test.is_active)
        self.assertFalse(user_for_test.activo)

        print(
            f"DEBUG TEST (view - inactive): Intentando login para {user_for_test.email} con is_active: {user_for_test.is_active}")

        response = self.client.post(reverse('myapp:login'), {
            'username': user_for_test.email,
            'password': 'userpassword'
        })

        print(
            f"DEBUG TEST (view - inactive): Response status: {response.status_code}")
        if response.status_code == 302:
            print(
                f"DEBUG TEST (view - inactive): Redirect location: {response.url}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._is_user_authenticated(
            email=user_for_test.email))
        self.assertContains(
            response, "Correo electrónico o contraseña incorrectos.")

        user_for_test.activo = True
        user_for_test.save()

    def test_logout_view(self):
        self.client.login(username='user@example.com', password='userpassword')
        self.assertTrue(self._is_user_authenticated(email='user@example.com'))
        response = self.client.post(reverse('myapp:logout'))
        self.assertRedirects(response, reverse('myapp:login'))
        self.assertFalse(self._is_user_authenticated(email='user@example.com'))


class HomeViewTests(BaseTestCase):
    def test_home_view_authenticated(self):
        self.client.login(username='user@example.com', password='userpassword')
        response = self.client.get(reverse('myapp:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_view_unauthenticated(self):
        response = self.client.get(reverse('myapp:home'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, f"{reverse('myapp:login')}?next={reverse('myapp:home')}")


class AfiliadoIndividualCRUDViewsTests(BaseTestCase):
    def setUp(self):
        self.client.login(username='admin@example.com',
                          password='adminpassword')

    def test_afiliado_individual_list_view(self):
        response = self.client.get(reverse('myapp:afiliado_individual_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'afiliado_individual_list.html')
        self.assertContains(response, self.afiliado_individual.primer_nombre)

    def test_afiliado_individual_detail_view(self):
        response = self.client.get(reverse('myapp:afiliado_individual_detail', kwargs={
                                   'pk': self.afiliado_individual.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'afiliado_individual_detail.html')
        self.assertContains(response, self.afiliado_individual.cedula)

    def test_afiliado_individual_create_view_get(self):
        response = self.client.get(reverse('myapp:afiliado_individual_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'afiliado_individual_form.html')

    def test_afiliado_individual_create_view_post(self):
        AfiliadoIndividual.objects.filter(cedula="V-22334455").delete()
        form_data = {
            'primer_nombre': "Nuevo", 'segundo_nombre': "Afiliado",
            'primer_apellido': "DePrueba", 'segundo_apellido': "Test",
            # CORRECCIÓN: Usar la clave correcta de CommonChoices.TIPO_IDENTIFICACION
            # Ej: 'CEDULA'
            'tipo_identificacion': CommonChoices.TIPO_IDENTIFICACION[0][0],
            'cedula': "V-22334455",
            'fecha_nacimiento': "15/07/1995", 'sexo': 'F', 'estado_civil': 'S',
            'nacionalidad': 'Venezolano', 'estado': 'Miranda',
            'parentesco': 'TITULAR',
            'intermediario': self.intermediario.pk,
            'activo': True,
        }
        # CORRECCIÓN: La vista de creación redirige a la lista.
        response = self.client.post(
            reverse('myapp:afiliado_individual_create'), form_data)

        if response.status_code != 302:
            form_errors = response.context.get('form').errors.as_json(
                escape_html=False) if response.context and response.context.get('form') else "No form in context or no errors."
            self.fail(
                f"Create Afiliado POST no redirigió. Status: {response.status_code}. Errores: {form_errors}")

        self.assertRedirects(response, reverse(
            'myapp:afiliado_individual_list'))
        self.assertTrue(AfiliadoIndividual.objects.filter(
            cedula="V-22334455").exists())

    def test_afiliado_individual_update_view_post(self):
        new_email = "juan.perez.updated@example.com"
        form_data = {
            'primer_nombre': self.afiliado_individual.primer_nombre,
            'segundo_nombre': self.afiliado_individual.segundo_nombre or "",
            'primer_apellido': self.afiliado_individual.primer_apellido,
            'segundo_apellido': self.afiliado_individual.segundo_apellido or "",
            'tipo_identificacion': self.afiliado_individual.tipo_identificacion,
            'cedula': self.afiliado_individual.cedula,
            'fecha_nacimiento': self.afiliado_individual.fecha_nacimiento.strftime('%d/%m/%Y'),
            'sexo': self.afiliado_individual.sexo,
            'estado_civil': self.afiliado_individual.estado_civil,
            'nacionalidad': self.afiliado_individual.nacionalidad,
            'estado': self.afiliado_individual.estado,
            'parentesco': self.afiliado_individual.parentesco,
            'email': new_email,
            'intermediario': self.afiliado_individual.intermediario.pk if self.afiliado_individual.intermediario else '',
            'activo': self.afiliado_individual.activo,
        }
        # CORRECCIÓN: La vista de actualización redirige a la lista.
        response = self.client.post(reverse('myapp:afiliado_individual_update', kwargs={
                                    'pk': self.afiliado_individual.pk}), form_data)

        if response.status_code != 302:
            form_errors = response.context.get('form').errors.as_json(
                escape_html=False) if response.context and response.context.get('form') else "No form in context or no errors."
            self.fail(
                f"Update Afiliado POST no redirigió. Status: {response.status_code}. Errores: {form_errors}")

        self.assertRedirects(response, reverse(
            'myapp:afiliado_individual_list'))
        self.afiliado_individual.refresh_from_db()
        self.assertEqual(self.afiliado_individual.email, new_email)


@override_settings(
    SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64,
    WHITENOISE_AUTOREFRESH=True,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)
@override_settings(
    # Asegúrate que esta constante exista
    SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64,
    WHITENOISE_AUTOREFRESH=True,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)
# Asumiendo que hereda de tu BaseTestCase
class LicenseViewsTests(BaseTestCase):
    def test_activate_license_view_get(self):
        # logger_tests.info(f"--- Iniciando test_activate_license_view_get ---") # Puedes mantener tus logs
        self.client.login(username='admin@example.com',
                          password='adminpassword')
        response = self.client.get(reverse('myapp:activate_license'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'activate_license.html')
        # logger_tests.info(f"--- test_activate_license_view_get PASSED ---")

    def test_activate_license_view_post_valid_key(self):
        self.client.login(username='admin@example.com',
                          password='adminpassword')
        LicenseInfo.objects.all().delete()
        key_for_this_test = generate_test_license_key(
            TEST_PRIVATE_KEY_B64, days_valid=60, activation_days_limit=5)

        # Obtener la fecha para construir el mensaje exacto que se espera
        temp_expiry_date, _ = _parse_and_validate_license_key(
            key_for_this_test)
        expected_date_str = temp_expiry_date.strftime('%d/%m/%Y')
        # Este es el mensaje completo que tu código genera
        expected_full_message = f"Licencia activada exitosamente. Válida hasta: {expected_date_str}."

        response = self.client.post(reverse('myapp:activate_license'),
                                    {'license_key': key_for_this_test},
                                    follow=True)

        self.assertRedirects(response, reverse(
            'myapp:activate_license'), status_code=302, target_status_code=200)

        html_content = response.content.decode(errors='ignore')
        print(
            f"\n--- HTML Response (test_activate_license_view_post_valid_key) ---\n{html_content}\n--------------------------------------------------\n")
        print(
            f"DEBUG: Test esperando encontrar en valid_key: '{expected_full_message}'")

        # ASEGÚRATE DE BUSCAR EL MENSAJE COMPLETO Y EXACTO, INCLUYENDO EL PUNTO FINAL
        self.assertContains(response, expected_full_message, html=True)

        li = LicenseInfo.objects.get(pk=LicenseInfo.SINGLETON_ID)
        self.assertEqual(li.license_key, key_for_this_test)
        self.assertTrue(li.is_valid)

    def test_activate_license_view_post_invalid_key_format_on_form(self):
        # logger_tests.info(f"--- Iniciando test_activate_license_view_post_invalid_key_format_on_form ---")
        self.client.login(username='admin@example.com',
                          password='adminpassword')
        short_key = 'SMGP-short'  # Clave demasiado corta para el LicenseActivationForm
        response = self.client.post(reverse('myapp:activate_license'), {
                                    'license_key': short_key})

        print(
            f"\n--- Contenido de la respuesta (test_activate_license_view_post_invalid_key_format_on_form) ---\n{response.content.decode(errors='ignore')}\n--- Fin del contenido ---\n")
        # El form es inválido, se re-renderiza la página
        self.assertEqual(response.status_code, 200)
        # Este mensaje viene de la validación del LicenseActivationForm (min_length)
        self.assertContains(
            response, f"Asegúrese de que este valor tenga al menos {MIN_KEY_LENGTH} carácter(es) (tiene10).", html=True)
        # logger_tests.info(f"--- test_activate_license_view_post_invalid_key_format_on_form PASSED ---")

    def test_activate_license_view_post_invalid_key_structure_after_form(self):
        self.client.login(username='admin@example.com',
                          password='adminpassword')
        key_bad_structure = 'SMGP-' + 'A' * MIN_EXPECTED_KEY_LENGTH
        response = self.client.post(reverse('myapp:activate_license'), {
                                    'license_key': key_bad_structure})
        self.assertEqual(response.status_code, 200)

        print(
            f"\n--- Contenido de la respuesta (test_activate_license_view_post_invalid_key_structure_after_form) ---\n{response.content.decode(errors='ignore')}\n--- Fin del contenido ---\n")

        # Este mensaje debe coincidir EXACTAMENTE con el ValidationError de _parse_and_validate_license_key
        # cuando falla por key_content.split('.', 1)
        expected_message = "Formato de clave inválido (estructura SMGP-Payload.Firma incorrecta)."
        print(
            f"DEBUG: Test esperando encontrar en invalid_key_structure: '{expected_message}'")
        self.assertContains(response, expected_message, html=True)

    def test_activate_license_view_post_unactivatable_key(self):
        self.client.login(username='admin@example.com',
                          password='adminpassword')
        key_to_test = UNACTIVATABLE_LICENSE_KEY

        # Para obtener la fecha exacta que se generará en el mensaje de error
        payload_b64 = key_to_test.split('.')[0][len("SMGP-"):]
        decoded_payload = json.loads(nacl.encoding.Base64Encoder.decode(
            payload_b64.encode('utf-8')).decode('utf-8'))
        act_by_date = date.fromisoformat(decoded_payload['act_by'])
        expected_date_str_in_error_message = act_by_date.strftime('%d/%m/%Y')
        expected_error_message = f"Esta clave de licencia ha caducado para su activación (debía activarse antes del {expected_date_str_in_error_message})."

        response = self.client.post(reverse('myapp:activate_license'), {
                                    'license_key': key_to_test})
        self.assertEqual(response.status_code, 200)

        html_content = response.content.decode(errors='ignore')
        print(
            f"\n--- Contenido de la respuesta (test_activate_license_view_post_unactivatable_key) ---\n{html_content}\n--------------------------------------------------\n")
        print(
            f"DEBUG: Test esperando encontrar en unactivatable_key: '{expected_error_message}'")

        self.assertContains(response, expected_error_message, html=True)

    def test_license_invalid_view_get(self):
        self.client.login(username='admin@example.com',
                          password='adminpassword')
        response = self.client.get(reverse('myapp:license_invalid'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'license_invalid.html')

    @override_settings(SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64)
    def test_license_middleware_redirect_if_invalid(self):
        LicenseInfo.objects.update_or_create(
            pk=LicenseInfo.SINGLETON_ID,
            defaults={'license_key': "dbkey_exp_test_middleware",
                      'expiry_date': date.today() - timedelta(days=5)}
        )
        self.client.login(username='user@example.com', password='userpassword')
        response = self.client.get(reverse('myapp:home'))
        self.assertRedirects(response, reverse('myapp:license_invalid'))


# --- LICENSING LOGIC TESTS ---
@override_settings(SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64)
# Asumiendo que hereda de tu BaseTestCase
class LicensingLogicTests(BaseTestCase):
    def test_01_parse_and_validate_valid_key(self):
        # logger_tests.info(f"--- Iniciando test_parse_and_validate_valid_key ---")
        key = VALID_TEST_LICENSE_KEY
        expiry_date, payload = _parse_and_validate_license_key(key)
        self.assertIsInstance(expiry_date, date)
        # Asumiendo default de generate_test_license_key
        self.assertEqual(expiry_date, date.today() + timedelta(days=30))
        self.assertEqual(payload['type'], "premium_test")
        # logger_tests.info(f"--- test_parse_and_validate_valid_key PASSED ---")

    def test_02_parse_and_validate_tampered_key_payload(self):
        # logger_tests.info(f"--- Iniciando test_parse_and_validate_tampered_key_payload ---")
        key = generate_test_license_key(TEST_PRIVATE_KEY_B64)
        parts = key.split('.')
        payload_b64_original = parts[0][len("SMGP-"):]
        decoded_payload_bytes = nacl.encoding.Base64Encoder.decode(
            payload_b64_original.encode('utf-8'))
        payload_dict = json.loads(decoded_payload_bytes.decode('utf-8'))
        payload_dict['sub'] = "TamperedSubject"
        tampered_payload_bytes = json.dumps(payload_dict).encode('utf-8')
        tampered_payload_b64_final = nacl.encoding.Base64Encoder.encode(
            tampered_payload_bytes).decode('utf-8')
        tampered_key = f"SMGP-{tampered_payload_b64_final}.{parts[1]}"
        with self.assertRaisesRegex(ValidationError, r"Clave de licencia inválida o ha sido manipulada \(firma no coincide\)\."):
            _parse_and_validate_license_key(tampered_key)
        # logger_tests.info(f"--- test_parse_and_validate_tampered_key_payload PASSED ---")

    def test_03_parse_and_validate_bad_signature(self):
        # logger_tests.info(f"--- Iniciando test_parse_and_validate_bad_signature ---")
        key = generate_test_license_key(TEST_PRIVATE_KEY_B64)
        parts = key.split('.')
        original_payload_part = parts[0][len("SMGP-"):]
        valid_signature_b64 = parts[1]
        temp_list = list(valid_signature_b64)
        char_index_to_change = -1
        if temp_list[-1] == '=':
            char_index_to_change = -2 if temp_list[-2] != '=' else -3
        original_char = temp_list[char_index_to_change]
        temp_list[char_index_to_change] = 'A' if original_char != 'A' else 'B'
        bad_signature_b64_final = "".join(temp_list)
        bad_sig_key = f"SMGP-{original_payload_part}.{bad_signature_b64_final}"
        with self.assertRaisesRegex(ValidationError, r"Clave de licencia inválida o ha sido manipulada \(firma no coincide\)\."):
            _parse_and_validate_license_key(bad_sig_key)
        # logger_tests.info(f"--- test_parse_and_validate_bad_signature PASSED ---")

    @override_settings(SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64)
    def test_04_parse_and_validate_expired_activation_deadline(self):
        # logger_tests.info(f"--- Iniciando test_parse_and_validate_expired_activation_deadline ---")
        key = UNACTIVATABLE_LICENSE_KEY
        payload_b64 = key.split('.')[0][len("SMGP-"):]
        decoded_payload = json.loads(nacl.encoding.Base64Encoder.decode(
            payload_b64.encode('utf-8')).decode('utf-8'))
        act_by_date = date.fromisoformat(decoded_payload['act_by'])
        # MENSAJE EXACTO que _parse_and_validate_license_key debe lanzar
        expected_msg = f"Esta clave de licencia ha caducado para su activación (debía activarse antes del {act_by_date.strftime('%d/%m/%Y')})."
        # re.escape para los paréntesis
        with self.assertRaisesRegex(ValidationError, re.escape(expected_msg)):
            _parse_and_validate_license_key(key)
        # logger_tests.info(f"--- test_parse_and_validate_expired_activation_deadline PASSED ---")

    @override_settings(SMGP_LICENSE_VERIFY_KEY_B64=TEST_PUBLIC_KEY_B64)
    def test_05_activate_or_update_license_success(self):
        # logger_tests.info(f"--- Iniciando test_activate_or_update_license_success ---")
        LicenseInfo.objects.all().delete()
        key_for_activation = generate_test_license_key(
            TEST_PRIVATE_KEY_B64, days_valid=45, activation_days_limit=10)
        success, msg = activate_or_update_license(key_for_activation)
        self.assertTrue(success, f"Activación falló: {msg}")
        # El mensaje que tu función activate_or_update_license devuelve
        self.assertIn(f"Licencia activada exitosamente. Válida hasta:", msg)
        li = LicenseInfo.objects.get(pk=LicenseInfo.SINGLETON_ID)
        self.assertEqual(li.license_key, key_for_activation)
        self.assertEqual(li.expiry_date, date.today() + timedelta(days=45))
        # logger_tests.info(f"--- test_activate_or_update_license_success PASSED ---")

    def test_06_activate_or_update_license_fail_invalid_key_format(self):
        # logger_tests.info(f"--- Iniciando test_activate_or_update_license_fail_invalid_key_format ---")
        success, msg = activate_or_update_license("INVALID-KEY-FORMAT")
        self.assertFalse(success)
        # El mensaje que tu función activate_or_update_license devuelve
        self.assertIn(
            "Formato de clave inválido (debe comenzar con SMGP-).", msg)
        # logger_tests.info(f"--- test_activate_or_update_license_fail_invalid_key_format PASSED ---")

    @override_settings(SMGP_LICENSE_VERIFY_KEY_B64=None)
    def test_07_parse_key_no_public_key_in_settings(self):
        expected_message_content = "Sistema de licencias no operativo (clave pública no configurada)."

        raised_exception = False
        actual_message = ""
        try:
            _parse_and_validate_license_key("SMGP-some.key")
            self.fail("ValidationError no fue lanzada cuando se esperaba.")
        except ValidationError as e:
            raised_exception = True
            if hasattr(e, 'messages') and isinstance(e.messages, list) and e.messages:
                actual_message = e.messages[0]
            elif hasattr(e, 'message'):
                actual_message = e.message
            else:
                actual_message = str(e)

            # ESTE PRINT ES CLAVE
            print(
                f"DEBUG test_07: Excepción capturada. Mensaje real: '{actual_message}'")
            print(
                f"DEBUG test_07: Mensaje esperado: '{expected_message_content}'")

        self.assertTrue(raised_exception, "ValidationError no fue lanzada.")
        self.assertEqual(actual_message, expected_message_content,
                         f"El mensaje de error no coincide. Esperado: '{expected_message_content}', Obtenido: '{actual_message}'")


class ValidatorTests(TestCase):
    def test_validate_rif_valid(self):
        self.assertEqual(validate_rif("J-12345678-9"), "J-12345678-9")
        self.assertEqual(validate_rif("G-87654321-0"), "G-87654321-0")

    def test_validate_rif_invalid_format(self):
        # CORRECCIÓN: El mensaje de error exacto del validador
        expected_error_msg = "Formato RIF inválido. Use Letra-8Números-1Número (Ej: J-12345678-9)."
        with self.assertRaisesRegex(ValidationError, re.escape(expected_error_msg)):
            validate_rif("J123456789")
        with self.assertRaisesRegex(ValidationError, re.escape(expected_error_msg)):
            validate_rif("J-1234567-9")  # Dígitos insuficientes
        with self.assertRaisesRegex(ValidationError, re.escape(expected_error_msg)):
            validate_rif("A-12345678-9")  # Letra inválida

    def test_validate_cedula_valid(self):
        self.assertEqual(validate_cedula("V-12345678"), "V-12345678")
        self.assertEqual(validate_cedula("E-8765432"), "E-8765432")
        self.assertEqual(validate_cedula("V1234567"), "V1234567")  # Sin guion

    def test_validate_cedula_invalid_format(self):
        # CORRECCIÓN: Mensajes de error específicos
        with self.assertRaisesRegex(ValidationError, "Longitud inválida para cédula 'V-123456'. Debe tener 7 u 8 dígitos después de V/E."):
            validate_cedula("V-123456")
        with self.assertRaisesRegex(ValidationError, "Formato de cédula 'A-12345678' inválido. Debe ser V o E seguido de 7 u 8 dígitos"):
            validate_cedula("A-12345678")
        with self.assertRaisesRegex(ValidationError, "Longitud inválida para cédula 'V123456'. Debe tener 7 u 8 dígitos después de V/E."):
            validate_cedula("V123456")

    def test_validate_numero_contrato_valid(self):
        self.assertEqual(validate_numero_contrato(
            "CONT-IND-20230101-0001"), "CONT-IND-20230101-0001")
        self.assertEqual(validate_numero_contrato(
            "CONT-COL-20241231-9999"), "CONT-COL-20241231-9999")

    def test_validate_numero_contrato_invalid(self):
        # CORRECCIÓN: Mensaje de error específico
        expected_error_msg = "Formato número contrato inválido. Debe ser CONT-TIPO-YYYYMMDD-NNNN (ej. CONT-IND-20230101-0001)."
        with self.assertRaisesRegex(ValidationError, re.escape(expected_error_msg)):
            validate_numero_contrato("CONT-XYZ-20230101-0001")  # Tipo inválido
        with self.assertRaisesRegex(ValidationError, re.escape(expected_error_msg)):
            validate_numero_contrato(
                "CONT-IND-202301-0001")  # Fecha incompleta
        with self.assertRaisesRegex(ValidationError, re.escape(expected_error_msg)):
            validate_numero_contrato(
                "CONTRATO-IND-20230101-0001")  # Prefijo incorrecto

    def test_validate_fecha_nacimiento_valid(self):
        valid_date = date(1990, 5, 15)
        self.assertEqual(validate_fecha_nacimiento(valid_date), valid_date)

    def test_validate_fecha_nacimiento_future(self):
        future_date = date.today() + timedelta(days=1)
        with self.assertRaisesRegex(ValidationError, "Fecha nacimiento no puede ser futura"):
            validate_fecha_nacimiento(future_date)

    def test_validate_fecha_nacimiento_too_old_or_invalid_year(self):
        very_old_date = date(1850, 1, 1)
        # CORRECCIÓN: El validador chequea edad > 120
        with self.assertRaisesRegex(ValidationError, "Edad máxima permitida: 120 años."):
            validate_fecha_nacimiento(very_old_date)

    @mock.patch('myapp.validators.magic', None)
    def test_validate_file_type_no_magic(self):
        mock_file_object = mock.Mock()
        mock_file_object.read.return_value = b"dummy content"
        mock_file_object.seek.return_value = 0
        mock_file_object.tell.return_value = 0

        mock_uploaded_file = mock.Mock(spec=['file', 'name'])
        mock_uploaded_file.file = mock_file_object
        mock_uploaded_file.name = "testfile.txt"

        # El validador retorna None si magic no está, no lanza error.
        self.assertIsNone(validate_file_type(mock_uploaded_file))
