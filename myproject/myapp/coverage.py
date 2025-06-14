from datetime import date, timedelta
from myapp.models import Pago, Reclamacion, Factura
from datetime import date
from myapp.models import Tarifa, ContratoBase
from django.test import TestCase
from myapp.models import *


class ModeloBaseTest(TestCase):
    def test_subclasses_inherit_fields(self):
        usuario = Usuario.objects.create(
            username='juanperez',
            password='password123',
            first_name='Juan',
            last_name='Pérez',
            email='juan.perez@example.com',
            tipo_usuario='ADMIN',
            fecha_nacimiento='1990-01-01',
            departamento='Ventas',
            telefono='123456789',
            direccion='Calle Falsa 123',
            intermediario=None,
            cuenta_activa=True,
            nivel_acceso=5
        )
        self.assertIsNotNone(usuario.fecha_creacion)
        self.assertIsNotNone(usuario.fecha_modificacion)
        self.assertTrue(usuario.activo)


class UsuarioModelTest(TestCase):
    def test_crear_usuario(self):
        usuario = Usuario.objects.create(
            username='juanperez',
            password='password123',
            first_name='Juan',
            last_name='Pérez',
            email='juan.perez@example.com',
            tipo_usuario='ADMIN',
            fecha_nacimiento='1990-01-01',
            departamento='Ventas',
            telefono='123456789',
            direccion='Calle Falsa 123',
            intermediario=None,
            cuenta_activa=True,
            nivel_acceso=5
        )
        self.assertEqual(usuario.username, 'juanperez')
        self.assertEqual(usuario.email, 'juan.perez@example.com')
        self.assertEqual(usuario.tipo_usuario, 'ADMIN')
        self.assertTrue(usuario.cuenta_activa)
        self.assertEqual(usuario.nivel_acceso, 5)

    def test_usuario_str(self):
        usuario = Usuario.objects.create(
            username='juanperez',
            password='password123',
            first_name='Juan',
            last_name='Pérez',
            email='juan.perez@example.com'
        )
        self.assertEqual(str(usuario), 'Juan Pérez (juanperez)')


class IntermediarioModelTest(TestCase):
    def test_crear_intermediario(self):
        intermediario = Intermediario.objects.create(
            codigo='INT-001',
            nombre_completo='Intermediario Uno',
            rif='J-123456789',
            direccion_fiscal='Calle Falsa 123',
            telefono_contacto='123456789',
            email_contacto='intermediario@example.com',
            porcentaje_comision=5.00
        )
        self.assertEqual(intermediario.codigo, 'INT-001')
        self.assertEqual(intermediario.nombre_completo, 'Intermediario Uno')
        self.assertEqual(intermediario.rif, 'J-123456789')
        self.assertEqual(intermediario.porcentaje_comision, 5.00)

    def test_intermediario_str(self):
        intermediario = Intermediario.objects.create(
            codigo='INT-001',
            nombre_completo='Intermediario Uno'
        )
        self.assertEqual(str(intermediario), 'Intermediario Uno (INT-001)')


class AfiliadoIndividualModelTest(TestCase):
    def test_crear_afiliado_individual(self):
        afiliado = AfiliadoIndividual.objects.create(
            tipo_identificacion='CEDULA',
            cedula='123456789',
            primer_nombre='Juan',
            primer_apellido='Pérez',
            fecha_nacimiento='1990-01-01',
            nacionalidad='Venezolano',
            sexo='MASCULINO',
            parentesco='TITULAR',
            fecha_ingreso='2023-01-01',
            direccion_habitacion='Calle Falsa 123',
            telefono_habitacion='123456789',
            direccion_oficina='Calle Verdadera 456',
            telefono_oficina='987654321',
            codigo_validacion='ABC123'
        )
        self.assertEqual(afiliado.tipo_identificacion, 'CEDULA')
        self.assertEqual(afiliado.cedula, '123456789')
        self.assertEqual(afiliado.primer_nombre, 'Juan')
        self.assertEqual(afiliado.primer_apellido, 'Pérez')
        self.assertEqual(afiliado.fecha_nacimiento, date(1990, 1, 1))
        # Asumiendo que la fecha actual es 2025-03-07
        self.assertEqual(afiliado.edad, 35)

    def test_afiliado_str(self):
        afiliado = AfiliadoIndividual.objects.create(
            tipo_identificacion='CEDULA',
            cedula='123456789',
            primer_nombre='Juan',
            primer_apellido='Pérez'
        )
        self.assertEqual(str(afiliado), 'Juan Pérez - 123456789')


class AfiliadoColectivoModelTest(TestCase):
    def test_crear_afiliado_colectivo(self):
        contrato = ContratoColectivo.objects.create(
            numero_contrato='CTO-002',
            razon_social='Empresa Ejemplo',
            rif='J-987654321'
        )
        afiliado = AfiliadoColectivo.objects.create(
            tipo_identificacion='CEDULA',
            cedula='987654321',
            primer_nombre='María',
            primer_apellido='Gómez',
            fecha_nacimiento='1985-05-15',
            nacionalidad='Venezolano',
            sexo='FEMENINO',
            parentesco='TITULAR',
            fecha_ingreso='2023-01-01',
            direccion_habitacion='Calle Verdadera 456',
            telefono_habitacion='555555555',
            contrato_colectivo=contrato,
            celular='444444444',
            email_contacto='maria.gomez@example.com',
            estado_civil='CASADA'
        )
        self.assertEqual(afiliado.tipo_identificacion, 'CEDULA')
        self.assertEqual(afiliado.cedula, '987654321')
        self.assertEqual(afiliado.primer_nombre, 'María')
        self.assertEqual(afiliado.primer_apellido, 'Gómez')
        self.assertEqual(afiliado.contrato_colectivo, contrato)

    def test_afiliado_colectivo_str(self):
        contrato = ContratoColectivo.objects.create(
            numero_contrato='CTO-002',
            razon_social='Empresa Ejemplo',
            rif='J-987654321'
        )
        afiliado = AfiliadoColectivo.objects.create(
            tipo_identificacion='CEDULA',
            cedula='987654321',
            primer_nombre='María',
            primer_apellido='Gómez',
            contrato_colectivo=contrato
        )
        self.assertEqual(str(afiliado), 'María Gómez - 987654321')


class ContratoIndividualModelTest(TestCase):
    def test_crear_contrato_individual(self):
        afiliado = AfiliadoIndividual.objects.create(
            tipo_identificacion='CEDULA',
            cedula='123456789',
            primer_nombre='Juan',
            primer_apellido='Pérez',
            fecha_nacimiento='1990-01-01'
        )
        contrato = ContratoIndividual.objects.create(
            numero_contrato='CTO-001',
            contratante_nombre='Juan Pérez',
            contratante_cedula='123456789',
            ramo='SALUD',
            fecha_emision='2023-01-01',
            fecha_inicio_vigencia='2023-01-01',
            fecha_fin_vigencia='2024-01-01',
            forma_pago='MENSUAL',
            monto_total=1000.00,
            intermediario=None,
            afiliado=afiliado,
            estatus='VIGENTE'
        )
        self.assertEqual(contrato.numero_contrato, 'CTO-001')
        self.assertEqual(contrato.ramo, 'SALUD')
        self.assertEqual(contrato.afiliado, afiliado)
        self.assertEqual(contrato.estatus, 'VIGENTE')

    def test_contrato_individual_str(self):
        afiliado = AfiliadoIndividual.objects.create(
            tipo_identificacion='CEDULA',
            cedula='123456789',
            primer_nombre='Juan',
            primer_apellido='Pérez'
        )
        contrato = ContratoIndividual.objects.create(
            numero_contrato='CTO-001',
            contratante_nombre='Juan Pérez',
            contratante_cedula='123456789',
            ramo='SALUD',
            fecha_emision='2023-01-01'
        )
        self.assertEqual(str(contrato), 'CTO-001')


class ContratoColectivoModelTest(TestCase):
    def test_crear_contrato_colectivo(self):
        contrato = ContratoColectivo.objects.create(
            numero_contrato='CTO-002',
            razon_social='Empresa Ejemplo',
            rif='J-987654321',
            tipo_empresa='PRIVADA',
            cantidad_empleados=100,
            ramo='VEHICULOS',
            fecha_emision='2023-01-01',
            fecha_inicio_vigencia='2023-01-01',
            fecha_fin_vigencia='2024-01-01',
            forma_pago='ANUAL',
            monto_total=50000.00,
            intermediario=None,
            estatus='VIGENTE'
        )
        self.assertEqual(contrato.numero_contrato, 'CTO-002')
        self.assertEqual(contrato.razon_social, 'Empresa Ejemplo')
        self.assertEqual(contrato.rif, 'J-987654321')
        self.assertEqual(contrato.tipo_empresa, 'PRIVADA')
        self.assertEqual(contrato.cantidad_empleados, 100)
        self.assertEqual(contrato.ramo, 'VEHICULOS')
        self.assertEqual(contrato.estatus, 'VIGENTE')

    def test_contrato_colectivo_str(self):
        contrato = ContratoColectivo.objects.create(
            numero_contrato='CTO-002',
            razon_social='Empresa Ejemplo',
            rif='J-987654321'
        )
        self.assertEqual(str(contrato), 'Empresa Ejemplo (RIF: J-987654321)')


class FacturaModelTest(TestCase):
    def test_crear_factura(self):
        contrato = ContratoIndividual.objects.create(
            numero_contrato='CTO-001',
            contratante_nombre='Juan Pérez',
            contratante_cedula='123456789',
            ramo='SALUD',
            fecha_emision='2023-01-01',
            fecha_inicio_vigencia='2023-01-01',
            fecha_fin_vigencia='2024-01-01',
            forma_pago='MENSUAL',
            monto_total=1000.00,
            intermediario=None,
            afiliado=None,
            estatus='VIGENTE'
        )
        factura = Factura.objects.create(
            contrato_individual=contrato,
            contrato_colectivo=None,
            vigencia_recibo_desde='2023-01-01',
            vigencia_recibo_hasta='2023-02-01',
            monto=1000.00,
            numero_recibo='REC-001',
            dias_periodo_cobro=30,
            estatus_emision='EMITIDO',
            pagada=False
        )
        self.assertEqual(factura.contrato_individual, contrato)
        self.assertEqual(factura.vigencia_recibo_desde, date(2023, 1, 1))
        self.assertEqual(factura.vigencia_recibo_hasta, date(2023, 2, 1))
        self.assertEqual(factura.monto, 1000.00)
        self.assertEqual(factura.numero_recibo, 'REC-001')
        self.assertEqual(factura.estatus_emision, 'EMITIDO')
        self.assertFalse(factura.pagada)

    def test_factura_str(self):
        contrato = ContratoIndividual.objects.create(
            numero_contrato='CTO-001',
            contratante_nombre='Juan Pérez',
            contratante_cedula='123456789'
        )
        factura = Factura.objects.create(
            contrato_individual=contrato,
            contrato_colectivo=None,
            numero_recibo='REC-001'
        )
        self.assertEqual(str(factura), 'Factura REC-001 - 1000.00')


class AuditoriaSistemaModelTest(TestCase):
    def test_crear_auditoria_sistema(self):
        usuario = Usuario.objects.create(
            username='juanperez',
            password='password123',
            first_name='Juan',
            last_name='Pérez',
            email='juan.perez@example.com'
        )
        auditoria = AuditoriaSistema.objects.create(
            usuario=usuario,
            tipo_accion='LOGIN',
            tabla_afectada='auth_user',
            registro_id_afectado=1,
            detalle_accion='Inicio de sesión exitoso',
            direccion_ip='192.168.1.1',
            agente_usuario='Mozilla/5.0',
            resultado_accion='EXITO'
        )
        self.assertEqual(auditoria.usuario, usuario)
        self.assertEqual(auditoria.tipo_accion, 'LOGIN')
        self.assertEqual(auditoria.tabla_afectada, 'auth_user')
        self.assertEqual(auditoria.registro_id_afectado, 1)
        self.assertEqual(auditoria.detalle_accion, 'Inicio de sesión exitoso')
        self.assertEqual(auditoria.direccion_ip, '192.168.1.1')
        self.assertEqual(auditoria.agente_usuario, 'Mozilla/5.0')
        self.assertEqual(auditoria.resultado_accion, 'EXITO')

    def test_auditoria_sistema_str(self):
        usuario = Usuario.objects.create(
            username='juanperez',
            password='password123',
            first_name='Juan',
            last_name='Pérez',
            email='juan.perez@example.com'
        )
        auditoria = AuditoriaSistema.objects.create(
            usuario=usuario,
            tipo_accion='LOGIN',
            tabla_afectada='auth_user',
            registro_id_afectado=1,
            detalle_accion='Inicio de sesión exitoso'
        )
        self.assertEqual(
            str(auditoria), 'LOGIN - auth_user - 1 - Inicio de sesión exitoso')


class ReclamacionModelTest(TestCase):
    def test_crear_reclamacion(self):
        contrato = ContratoIndividual.objects.create(
            numero_contrato='CTO-001',
            contratante_nombre='Juan Pérez',
            contratante_cedula='123456789',
            ramo='SALUD',
            fecha_emision='2023-01-01',
            fecha_inicio_vigencia='2023-01-01',
            fecha_fin_vigencia='2024-01-01',
            forma_pago='MENSUAL',
            monto_total=1000.00,
            intermediario=None,
            afiliado=None,
            estatus='VIGENTE'
        )
        reclamacion = Reclamacion.objects.create(
            contrato_individual=contrato,
            contrato_colectivo=None,
            fecha_reclamo='2023-01-15',
            tipo_reclamacion='MEDICA',
            descripcion_reclamo='Reclamación por servicio',
            estado='ABIERTA',
            fecha_cierre_reclamo=None,
            usuario_asignado=None,
            documentos_adjuntos=None,
            observaciones_internas='Observaciones internas',
            observaciones_cliente='Observaciones para el cliente'
        )
        self.assertEqual(reclamacion.contrato_individual, contrato)
        self.assertEqual(reclamacion.fecha_reclamo, date(2023, 1, 15))
        self.assertEqual(reclamacion.tipo_reclamacion, 'MEDICA')
        self.assertEqual(reclamacion.descripcion_reclamo,
                         'Reclamación por servicio')
        self.assertEqual(reclamacion.estado, 'ABIERTA')
        self.assertIsNone(reclamacion.fecha_cierre_reclamo)
        self.assertIsNone(reclamacion.usuario_asignado)
        self.assertIsNone(reclamacion.documentos_adjuntos)
        self.assertEqual(reclamacion.observaciones_internas,
                         'Observaciones internas')
        self.assertEqual(reclamacion.observaciones_cliente,
                         'Observaciones para el cliente')

    def test_reclamacion_str(self):
        contrato = ContratoIndividual.objects.create(
            numero_contrato='CTO-001',
            contratante_nombre='Juan Pérez',
            contratante_cedula='123456789'
        )
        reclamacion = Reclamacion.objects.create(
            contrato_individual=contrato,
            contrato_colectivo=None,
            fecha_reclamo='2023-01-15',
            tipo_reclamacion='MEDICA',
            descripcion_reclamo='Reclamación por servicio'
        )
        self.assertEqual(str(reclamacion), 'Reclamación 1 - CTO-001')


class TarifaModelTest(TestCase):
    def setUp(self):
        self.tarifa = Tarifa.objects.create(
            ramo='SALUD',
            rango_etario='26-35',
            fecha_aplicacion='2023-01-01',
            monto_anual=1200.00,
            tipo_fraccionamiento='ANUAL',
            monto_semestral=600.00,
            monto_trimestral=300.00,
            monto_mensual=100.00
        )

    def test_crear_tarifa(self):
        self.assertEqual(self.tarifa.ramo, 'SALUD')
        self.assertEqual(self.tarifa.rango_etario, '26-35')
        self.assertEqual(self.tarifa.fecha_aplicacion, date(2023, 1, 1))
        self.assertEqual(self.tarifa.monto_anual, 1200.00)
        self.assertEqual(self.tarifa.tipo_fraccionamiento, 'ANUAL')
        self.assertEqual(self.tarifa.monto_semestral, 600.00)
        self.assertEqual(self.tarifa.monto_trimestral, 300.00)
        self.assertEqual(self.tarifa.monto_mensual, 100.00)

    def test_tarifa_str(self):
        expected_str = f"Tarifa SALUD - 26-35 - 2023-01-01"
        self.assertEqual(str(self.tarifa), expected_str)

    def test_actualizar_tarifa(self):
        nuevo_monto_anual = 1500.00
        self.tarifa.monto_anual = nuevo_monto_anual
        self.tarifa.save()
        self.tarifa.refresh_from_db()
        self.assertEqual(self.tarifa.monto_anual, nuevo_monto_anual)
        self.assertEqual(self.tarifa.monto_semestral, nuevo_monto_anual / 2)
        self.assertEqual(self.tarifa.monto_trimestral, nuevo_monto_anual / 4)
        self.assertEqual(self.tarifa.monto_mensual, nuevo_monto_anual / 12)

    def test_validacion_fecha_aplicacion_futura(self):
        with self.assertRaises(ValidationError) as context:
            Tarifa.objects.create(
                ramo='SALUD',
                rango_etario='26-35',
                fecha_aplicacion='2100-01-01',  # Fecha futura
                monto_anual=1200.00,
                tipo_fraccionamiento='ANUAL',
                monto_semestral=600.00,
                monto_trimestral=300.00,
                monto_mensual=100.00
            )
        self.assertIn('fecha_aplicacion', context.exception.message_dict)
        self.assertEqual(
            context.exception.message_dict['fecha_aplicacion'][0], 'La fecha de aplicación no puede ser futura.')

    def test_validacion_montos_fraccionados(self):
        tarifa = Tarifa.objects.create(
            ramo='SALUD',
            rango_etario='26-35',
            fecha_aplicacion='2023-01-01',
            monto_anual=1200.00,
            tipo_fraccionamiento='ANUAL',
            # No especificamos los montos fraccionados
        )
        self.assertEqual(tarifa.monto_semestral, 600.00)
        self.assertEqual(tarifa.monto_trimestral, 300.00)
        self.assertEqual(tarifa.monto_mensual, 100.00)

    def test_contratos_relacionados(self):
        tarifa = self.tarifa
        contrato = ContratoBase.objects.create(
            numero_contrato='CTO-001',
            numero_poliza='POL-001',
            ramo='SALUD',
            fecha_emision='2023-01-01',
            fecha_inicio_vigencia='2023-01-01',
            fecha_fin_vigencia='2024-01-01',
            forma_pago='MENSUAL',
            monto_total=1000.00,
            intermediario=None,
            consultar_afiliados_activos=False,
            estatus='VIGENTE'
        )
        self.assertIn(contrato, tarifa.contratoindividual_set.all())
        self.assertIn(contrato, tarifa.contratocolectivo_set.all())

    def test_tarifa_con_contratos_relacionados(self):
        tarifa = Tarifa.objects.create(
            ramo='SALUD',
            rango_etario='26-35',
            fecha_aplicacion='2023-01-01',
            monto_anual=1200.00,
            tipo_fraccionamiento='ANUAL',
            monto_semestral=600.00,
            monto_trimestral=300.00,
            monto_mensual=100.00
        )
        contrato = ContratoBase.objects.create(
            numero_contrato='CTO-001',
            numero_poliza='POL-001',
            ramo='SALUD',
            fecha_emision='2023-01-01',
            fecha_inicio_vigencia='2023-01-01',
            fecha_fin_vigencia='2024-01-01',
            forma_pago='MENSUAL',
            monto_total=1000.00,
            intermediario=None,
            consultar_afiliados_activos=False,
            estatus='VIGENTE'
        )
        tarifa.contratoindividual_set.add(contrato)
        tarifa.contratocolectivo_set.add(contrato)
        self.assertEqual(tarifa.contratoindividual_set.count(), 1)
        self.assertEqual(tarifa.contratocolectivo_set.count(), 1)


class PagoModelTest(TestCase):
    def setUp(self):
        self.reclamacion = Reclamacion.objects.create(
            descripcion_reclamo='Reclamación de prueba',
            tipo_reclamacion='MEDICA',
            estado='ABIERTA',
            fecha_reclamo=date.today()
        )
        self.factura = Factura.objects.create(
            numero_recibo='REC-001',
            contrato_individual=None,
            contrato_colectivo=None,
            vigencia_recibo_desde=date.today(),
            vigencia_recibo_hasta=date.today() + timedelta(days=30),
            monto=500.00,
            estatus_emision='EMITIDO',
            pagada=False
        )
        self.pago = Pago.objects.create(
            reclamacion=self.reclamacion,
            fecha_pago=date.today(),
            monto_pago=500.00,
            forma_pago='TRANSFERENCIA',
            referencia_pago='REF-123456',
            fecha_notificacion_pago=date.today(),
            observaciones_pago='Pago realizado correctamente',
            documentos_soporte_pago='documento.pdf',
            factura=self.factura,
            activo=True
        )

    def test_crear_pago(self):
        self.assertEqual(self.pago.reclamacion, self.reclamacion)
        self.assertEqual(self.pago.fecha_pago, date.today())
        self.assertEqual(self.pago.monto_pago, 500.00)
        self.assertEqual(self.pago.forma_pago, 'TRANSFERENCIA')
        self.assertEqual(self.pago.referencia_pago, 'REF-123456')
        self.assertEqual(self.pago.fecha_notificacion_pago, date.today())
        self.assertEqual(self.pago.observaciones_pago,
                         'Pago realizado correctamente')
        self.assertEqual(self.pago.documentos_soporte_pago, 'documento.pdf')
        self.assertEqual(self.pago.factura, self.factura)
        self.assertTrue(self.pago.activo)

    def test_pago_str(self):
        expected_str = f"Pago {self.pago.id} - {self.pago.reclamacion.id} - {self.pago.monto_pago}"
        self.assertEqual(str(self.pago), expected_str)

    def test_actualizar_pago(self):
        nuevo_monto = 750.00
        self.pago.monto_pago = nuevo_monto
        self.pago.save()
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.monto_pago, nuevo_monto)

    def test_validacion_monto_pago(self):
        with self.assertRaises(ValidationError) as context:
            Pago.objects.create(
                reclamacion=self.reclamacion,
                fecha_pago=date.today(),
                monto_pago=-100.00,  # Monto de pago negativo
                forma_pago='TRANSFERENCIA',
                referencia_pago='REF-123456',
                fecha_notificacion_pago=date.today(),
                observaciones_pago='Pago realizado correctamente',
                documentos_soporte_pago='documento.pdf',
                factura=self.factura,
                activo=True
            )
        self.assertIn('monto_pago', context.exception.message_dict)
        self.assertEqual(
            context.exception.message_dict['monto_pago'][0], 'El monto del pago no puede ser negativo.')

    def test_validacion_factura_pagada(self):
        factura = Factura.objects.create(
            numero_recibo='REC-002',
            contrato_individual=None,
            contrato_colectivo=None,
            vigencia_recibo_desde=date.today(),
            vigencia_recibo_hasta=date.today() + timedelta(days=30),
            monto=500.00,
            estatus_emision='EMITIDO',
            pagada=True  # Factura ya pagada
        )
        with self.assertRaises(ValidationError) as context:
            Pago.objects.create(
                reclamacion=self.reclamacion,
                fecha_pago=date.today(),
                monto_pago=500.00,
                forma_pago='TRANSFERENCIA',
                referencia_pago='REF-123456',
                fecha_notificacion_pago=date.today(),
                observaciones_pago='Pago realizado correctamente',
                documentos_soporte_pago='documento.pdf',
                factura=factura,
                activo=True
            )
        self.assertIn('factura', context.exception.message_dict)
        self.assertEqual(
            context.exception.message_dict['factura'][0], 'La factura ya ha sido pagada.')

    def test_pago_con_reclamacion_y_factura(self):
        self.assertEqual(self.pago.reclamacion, self.reclamacion)
        self.assertEqual(self.pago.factura, self.factura)
        self.assertTrue(self.pago.activo)

    def test_pago_actualizar_estado_factura(self):
        self.pago.factura.pagada = True
        self.pago.factura.save()
        self.pago.save()
        self.pago.refresh_from_db()
        self.assertTrue(self.pago.factura.pagada)


class IntermediarioModelTest(TestCase):
    def test_crear_intermediario(self):
        intermediario = Intermediario.objects.create(
            codigo='INT-001',
            nombre_completo='Intermediario Uno',
            rif='J-123456789',
            direccion_fiscal='Calle Falsa 123',
            telefono_contacto='123456789',
            email_contacto='intermediario@example.com',
            porcentaje_comision=5.00
        )
        self.assertEqual(intermediario.codigo, 'INT-001')
        self.assertEqual(intermediario.nombre_completo, 'Intermediario Uno')
        self.assertEqual(intermediario.rif, 'J-123456789')
        self.assertEqual(intermediario.porcentaje_comision, 5.00)

    def test_intermediario_str(self):
        intermediario = Intermediario.objects.create(
            codigo='INT-001',
            nombre_completo='Intermediario Uno'
        )
        self.assertEqual(str(intermediario), 'Intermediario Uno (INT-001)')
