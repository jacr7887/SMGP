# commons.py
import re
import logging
from datetime import timedelta, date
from django.core.exceptions import ValidationError
logger = logging.getLogger(__name__)

# =================================================================
# CLASE PRINCIPAL DE ELECCIONES COMUNES
# =================================================================


class CommonChoices:
    """Centraliza todas las opciones de elección reutilizables en el sistema"""

    # ------------------------------------------
    # Niveles de Acceso
    # ------------------------------------------
    NIVEL_ACCESO = [
        (1, ('Básico')),
        (2, ('Intermedio')),
        (3, ('Avanzado')),
        (4, ('Supervisor')),
        (5, ('Administrador')),
    ]

    # ------------------------------------------
    # Tipos de Acción
    # ------------------------------------------
    TIPO_ACCION = [
        ('LOGIN', ('Inicio de Sesión')),
        ('LOGOUT', ('Cierre de Sesión')),
        ('CREACION', ('Creación de Registro')),
        ('MODIFICACION', ('Modificación de Registro')),
        ('ELIMINACION', ('Eliminación de Registro')),
        ('CONSULTA', ('Consulta de Registro')),
        ('EXPORTACION', ('Exportación de Datos')),
        ('IMPORTACION', ('Importación de Datos')),
        ('ERROR', ('Error del Sistema')),
        ('OTRO', ('Otra Acción')),
    ]

    # ------------------------------------------
    # Tipo de Cédula
    # ------------------------------------------
    TIPO_CEDULA = [
        ('V', 'Venezolano'),
        ('E', 'Extranjero'),
        ('J', 'Jurídica'),
        ('G', 'Gobierno'),
    ]

    # ------------------------------------------
    # Resultado de Acción
    # ------------------------------------------
    RESULTADO_ACCION = [
        ('EXITO', ('Éxito')),
        ('ERROR', ('Error')),
    ]

    # ------------------------------------------
    # Tipos de Identificación
    # ------------------------------------------
    TIPO_IDENTIFICACION = [
        ('CEDULA', ('Cédula de Identidad')),
        ('PASAPORTE', ('Pasaporte')),
        ('RIF', ('Registro de Información Fiscal (RIF)')),
    ]

    # ------------------------------------------
    # Parentesco
    # ------------------------------------------
    PARENTESCO = [
        ('TITULAR', ('Titular')),
        ('CONYUGE', ('Cónyuge')),
        ('HIJO', ('Hijo(a)')),
        ('PADRE', ('Padre')),
        ('MADRE', ('Madre')),
        ('HERMANO', ('Hermano(a)')),
        ('OTRO', ('Otro Parentesco')),
    ]

    # ------------------------------------------
    # Ramos de Seguros
    # ------------------------------------------
    RAMO = [
        ('HCM', ('Hospitalización, Cirugía y Maternidad (HCM)')),
        ('VIDA', ('Vida')),
        ('VEHICULOS', ('Vehículos')),
        ('HOGAR', ('Hogar')),
        ('PYME', ('Pequeña y Mediana Empresa (PYME)')),
        ('ACCIDENTES_PERSONALES', ('Accidentes Personales')),
        ('SEPELIO', ('Sepelio')),
        ('VIAJES', ('Viajes')),
        ('EDUCATIVO', ('Educativo')),
        ('MASCOTAS', ('Mascotas')),
        ('OTROS', ('Otros Ramos')),
    ]

    # ------------------------------------------
    # Departamento
    # ------------------------------------------
    DEPARTAMENTO = [
        ('VENTAS', 'Ventas'),
        ('ADMINISTRACION', 'Administración'),
        ('OPERACIONES', 'Operaciones'),
        ('TECNOLOGIA', 'Tecnología'),
        ('LEGAL', 'Legal'),
        ('RECURSOS_HUMANOS', 'Recursos Humanos'),
        ('FINANZAS', 'Finanzas'),
        ('MERCADEO', 'Mercadeo'),
        ('SUSCRIPCION', 'Suscripción'),
        ('RECLAMOS', 'Reclamos'),
        ('AUDITORIA', 'Auditoría'),
        ('SERVICIO_AL_CLIENTE', 'Servicio al Cliente'),
        ('ACTUARIA', 'Actuaría'),
        ('CONTRALORIA', 'Contraloría'),
        ('OTRO', 'Otro'),
    ]

    # ------------------------------------------
    # Estado del Contrato
    # ------------------------------------------
    ESTADO_CONTRATO = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
        ('PENDIENTE', 'Pendiente'),
        ('VENCIDO', 'Vencido'),
        ('ANULADO', 'Anulado'),
        ('EN_REVISION', 'En Revisión'),
        ('BLOQUEADO', 'Bloqueado'),
        ('PRE_APROBADO', 'Pre-Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('SUSPENDIDO', 'Suspendido'),
        ('EN_TRAMITE_RENOVACION', 'En Trámite de Renovación'),
    ]

    # ------------------------------------------
    # Estados Civiles
    # ------------------------------------------
    ESTADO_CIVIL = [
        ('S', 'Soltero/a'),
        ('C', 'Casado/a'),
        ('V', 'Viudo/a'),
        ('D', 'Divorciado/a'),
        ('O', 'Otro'),
    ]

    # ------------------------------------------
    # Estados de Vigencia
    # ------------------------------------------
    ESTADOS_VIGENCIA = [
        ('NO_VIGENTE_AUN', ('No Vigente Aún')),
        ('VIGENTE', ('Vigente')),
        ('VENCIDO', ('Vencido')),
    ]

    # ------------------------------------------
    # Estados de Venezuela
    # ------------------------------------------
    ESTADOS_VE = [
        ('Amazonas', 'Amazonas'),
        ('Anzoátegui', 'Anzoátegui'),
        ('Apure', 'Apure'),
        ('Aragua', 'Aragua'),
        ('Barinas', 'Barinas'),
        ('Bolívar', 'Bolívar'),
        ('Carabobo', 'Carabobo'),
        ('Cojedes', 'Cojedes'),
        ('Delta Amacuro', 'Delta Amacuro'),
        ('Falcón', 'Falcón'),
        ('Guárico', 'Guárico'),
        ('Lara', 'Lara'),
        ('Mérida', 'Mérida'),
        ('Miranda', 'Miranda'),
        ('Monagas', 'Monagas'),
        ('Nueva Esparta', 'Nueva Esparta'),
        ('Portuguesa', 'Portuguesa'),
        ('Sucre', 'Sucre'),
        ('Táchira', 'Táchira'),
        ('Trujillo', 'Trujillo'),
        ('Vargas', 'Vargas'),
        ('Yaracuy', 'Yaracuy'),
        ('Zulia', 'Zulia'),
        ('Distrito Capital', 'Distrito Capital'),
    ]

    # ------------------------------------------
    # Estatus de la Factura
    # ------------------------------------------
    ESTATUS_FACTURA = [
        ('PENDIENTE', ('Pendiente')),
        ('PAGADA', ('Pagada')),
        ('VENCIDA', ('Vencida')),
    ]

    # ------------------------------------------
    # Emisión de Recibo
    # ------------------------------------------
    EMISION_RECIBO = [
        ('SIN_EMITIR', 'Sin Emitir'),
        ('EMITIDO', 'Emitido'),
    ]

    # ------------------------------------------
    # Sexo
    # ------------------------------------------
    SEXO = [
        ('M', ('Masculino')),
        ('F', ('Femenino')),
        ('OTRO', ('Otro')),
        ('NO_BINARIO', ('No Binario')),
        ('SIN_ESPECIFICAR', ('Sin Especificar')),
    ]

    # ------------------------------------------
    # Tipos de Usuario
    # ------------------------------------------
    TIPO_USUARIO = [
        ('ADMIN', ('Administrador')),
        ('INTERMEDIARIO', ('Intermediario')),
        ('CLIENTE', ('Cliente')),
        ('AUDITOR', ('Auditor')),
    ]

    # ------------------------------------------
    # Formas de Pago
    # ------------------------------------------
    FORMA_PAGO = [
        ('MENSUAL', ('Mensual')),
        ('TRIMESTRAL', ('Trimestral')),
        ('SEMESTRAL', ('Semestral')),
        ('ANUAL', ('Anual')),
        ('CONTADO', ('Contado (Pago único)')),
    ]

    # ------------------------------------------
    # Tipos de Empresa
    # ------------------------------------------
    TIPO_EMPRESA = [
        ('PUBLICA', ('Pública')),
        ('PRIVADA', ('Privada')),
        ('MIXTA', ('Mixta')),
        ('ONG', ('Organización No Gubernamental (ONG)')),
        ('COOPERATIVA', ('Cooperativa')),
        ('OTRA', ('Otra Tipo de Empresa')),
        ('SA', 'Sociedad Anónima'),
        ('CA', 'Compañía Anónima'),
        ('RL', 'Responsabilidad Limitada'),
    ]

    # ------------------------------------------
    # Estados de Reclamación
    # ------------------------------------------
    ESTADO_RECLAMACION = [
        ('ABIERTA', ('Abierta')),
        ('EN_PROCESO', ('En Proceso')),
        ('APROBADA', ('Aprobada')),
        ('RECHAZADA', ('Rechazada')),
        ('CERRADA', ('Cerrada')),
        ('PENDIENTE_DOCS', ('Pendiente de Documentos')),
        ('EN_ANALISIS', ('En Análisis')),
        ('ESCALADA', ('Escalada a Nivel Superior')),
        ('EN_ARBITRAJE', ('En Arbitraje')),
        ('SUSPENDIDA', ('Suspendida')),
        ('INVESTIGACION', ('En Investigación')),
    ]

    # ------------------------------------------
    # Tipos de Reclamación
    # ------------------------------------------
    TIPO_RECLAMACION = [
        ('MEDICA', ('Reclamación Médica')),
        ('ADMINISTRATIVA', ('Reclamación Administrativa')),
        ('LEGAL', ('Reclamación Legal')),
        ('FINANCIERA', ('Reclamación Financiera')),
        ('SERVICIO', ('Reclamación de Servicio')),
        ('OTRA', ('Otro Tipo de Reclamación')),
    ]

    # ------------------------------------------
    # Formas de Pago de Reclamaciones
    # ------------------------------------------
    FORMA_PAGO_RECLAMACION = [
        ('TRANSFERENCIA', ('Transferencia Bancaria')),
        ('CHEQUE', ('Cheque')),
        ('EFECTIVO', ('Efectivo')),
        ('TARJETA_CREDITO', ('Tarjeta de Crédito')),
        ('TARJETA_DEBITO', ('Tarjeta de Débito')),
        ('PAGO_MOVIL', ('Pago Móvil')),
        ('OTRO', ('Otro Medio de Pago')),
    ]

    # ------------------------------------------
    # Rangos Etarios para Tarifas
    # ------------------------------------------
    RANGO_ETARIO = [
        ('0-17', ('0-17 años')),
        ('18-25', ('18-25 años')),
        ('26-35', ('26-35 años')),
        ('36-45', ('36-45 años')),
        ('46-55', ('46-55 años')),
        ('56-65', ('56-65 años')),
        ('66-70', ('66-70 años')),
        ('71-75', ('71-75 años')),
        ('76-80', ('76-80 años')),
        ('81-89', ('81-89 años')),
        ('90-99', ('90-99 años')),
    ]


# =================================================================
# DIAGNOSTICOS
# =================================================================

# En commons.py, dentro de la clase CommonChoices:

    DIAGNOSTICOS = [
        ('', '--------- SELECCIONE ---------'),

        # === SECCIÓN: SALUD (HCM) - CONSULTAS Y ESTUDIOS ===
        ('SAL-CON-001', 'Consulta Médica General / Atención Primaria'),
        ('SAL-CON-002', 'Consulta Médica Especializada (Cardiología)'),
        ('SAL-CON-003', 'Consulta Médica Especializada (Dermatología)'),
        ('SAL-CON-004', 'Consulta Médica Especializada (Endocrinología)'),
        ('SAL-CON-005', 'Consulta Médica Especializada (Gastroenterología)'),
        ('SAL-CON-006', 'Consulta Médica Especializada (Ginecología/Obstetricia)'),
        ('SAL-CON-007', 'Consulta Médica Especializada (Infectología)'),
        ('SAL-CON-008', 'Consulta Médica Especializada (Neumología)'),
        ('SAL-CON-009', 'Consulta Médica Especializada (Neurología)'),
        ('SAL-CON-010', 'Consulta Médica Especializada (Oftalmología)'),
        ('SAL-CON-011', 'Consulta Médica Especializada (Oncología)'),
        ('SAL-CON-012', 'Consulta Médica Especializada (Otorrinolaringología - ORL)'),
        ('SAL-CON-013', 'Consulta Médica Especializada (Pediatría)'),
        ('SAL-CON-014', 'Consulta Médica Especializada (Psiquiatría)'),
        ('SAL-CON-015', 'Consulta Médica Especializada (Reumatología)'),
        ('SAL-CON-016', 'Consulta Médica Especializada (Traumatología/Ortopedia)'),
        ('SAL-CON-017', 'Consulta Médica Especializada (Urología)'),
        ('SAL-CON-018', 'Consulta Médica Especializada (Nefrología)'),
        ('SAL-CON-019', 'Consulta Médica Especializada (Nutrición/Dietética)'),
        ('SAL-CON-020', 'Consulta Médica Domiciliaria'),
        ('SAL-CON-021', 'Consulta Preoperatoria / Evaluación Cardiovascular'),
        ('SAL-CON-022', 'Consulta Postoperatoria'),
        ('SAL-CON-023', 'Consulta de Emergencia / Sala de Urgencias'),
        ('SAL-CON-024', 'Consulta de Salud Mental / Psicología'),
        ('SAL-CON-025', 'Segunda Opinión Médica'),
        ('SAL-CON-026', 'Consulta Médica Especializada (Angiología/Cirugía Vascular)'),
        ('SAL-CON-027', 'Consulta Médica Especializada (Alergología/Inmunología)'),
        ('SAL-CON-028', 'Consulta Médica Especializada (Geriatría)'),
        ('SAL-CON-029', 'Consulta Medicina del Deporte'),
        ('SAL-EST-001', 'Exámenes de Laboratorio (Hematología, Química, Orina, Heces)'),
        ('SAL-EST-002', 'Perfil Lipídico / Perfil 20 / Renal / Hepático'),
        ('SAL-EST-003', 'Hemoglobina Glicosilada (HbA1c) / Glucemia'),
        ('SAL-EST-004', 'Pruebas de Función Tiroidea (TSH, T3, T4, Anticuerpos)'),
        ('SAL-EST-005', 'Marcadores Tumorales (CEA, PSA, CA-125, etc.)'),
        ('SAL-EST-006', 'Pruebas de Coagulación (TP, TPT, INR, Fibrinógeno)'),
        ('SAL-EST-007', 'Cultivos (Urocultivo, Hemocultivo, Coprocultivo, Secreciones)'),
        ('SAL-EST-008', 'Radiografía (Rayos X - Tórax, Huesos, Abdomen, etc.)'),
        ('SAL-EST-009', 'Ecografía / Ultrasonido (Abdominal, Pélvico, Tiroideo, Doppler, etc.)'),
        ('SAL-EST-010', 'Tomografía Axial Computarizada (TAC/TC - Con/Sin Contraste)'),
        ('SAL-EST-011', 'Resonancia Magnética Nuclear (RMN - Con/Sin Contraste)'),
        ('SAL-EST-012', 'Mamografía / Ecosonograma Mamario / Tomosíntesis'),
        ('SAL-EST-013', 'Densitometría Ósea (DEXA)'),
        ('SAL-EST-014', 'Electrocardiograma (ECG/EKG) en Reposo'),
        ('SAL-EST-015', 'Ecocardiograma Transtorácico / Transesofágico'),
        ('SAL-EST-016', 'Prueba de Esfuerzo / Ergometría Cardiológica'),
        ('SAL-EST-017', 'Holter de Ritmo (24/48h) / Holter de Tensión (MAPA)'),
        ('SAL-EST-018', 'Endoscopia Digestiva Superior / Gastroscopia (con Biopsia)'),
        ('SAL-EST-019', 'Colonoscopia / Rectosigmoidoscopia (con Biopsia/Polipectomía)'),
        ('SAL-EST-020', 'Espirometría Basal y Post-Broncodilatador / DLCO'),
        ('SAL-EST-021', 'Electroencefalograma (EEG) / Mapeo Cerebral'),
        ('SAL-EST-022', 'Electromiografía (EMG) / Neuroconducción / Potenciales Evocados'),
        ('SAL-EST-023', 'Biopsia Percutánea / Endoscópica / Quirúrgica (Especificar)'),
        ('SAL-EST-024', 'Estudios Oftalmológicos (Fondo de Ojo, Campo Visual, OCT, Angiografía)'),
        ('SAL-EST-025', 'Estudios Auditivos (Audiometría, Impedanciometría, Otoemisiones)'),
        ('SAL-EST-026', 'Papanicolaou / Citología Ginecológica / Colposcopia / Test VPH'),
        ('SAL-EST-027', 'Estudios Genéticos / Cariotipo / Pruebas de Paternidad'),
        ('SAL-EST-028', 'Pruebas Alérgicas (Prick Test, Patch Test, IgE Específica)'),
        ('SAL-EST-029', 'Gammagrafía / Estudios Medicina Nuclear (Ósea, Tiroidea, Renal)'),
        ('SAL-EST-030', 'PET-Scan / PET-CT Oncológico'),
        ('SAL-EST-031', 'Dímero-D / Productos Degradación Fibrina'),
        ('SAL-EST-032', 'Estudios Inmunológicos (ANA, FR, Complemento, etc.)'),
        ('SAL-EST-033', 'Video-Nistagmografía (VNG - Estudio Vértigo)'),
        ('SAL-EST-034', 'Polisomnografía (Estudio del Sueño)'),
        ('SAL-EST-035', 'AngioTAC / AngioResonancia'),
        ('SAL-EST-036', 'Manometría Esofágica / pHmetría'),

        # === SECCIÓN: SALUD (HCM) - Procedimientos y Tratamientos ===
        ('SAL-PRO-001', 'Tratamiento Médico Ambulatorio (Farmacia)'),
        ('SAL-PRO-002', 'Hospitalización (Médica)'),
        ('SAL-PRO-003', 'Hospitalización (Quirúrgica)'),
        ('SAL-PRO-004', 'Cirugía Mayor (Especificar Procedimiento)'),
        ('SAL-PRO-005', 'Cirugía Menor / Ambulatoria (Especificar Procedimiento)'),
        ('SAL-PRO-006', 'Quimioterapia (Ciclos, Medicamentos)'),
        ('SAL-PRO-007', 'Radioterapia (Sesiones, Tipo)'),
        ('SAL-PRO-008', 'Inmunoterapia / Terapia Biológica'),
        ('SAL-PRO-009', 'Diálisis / Hemodiálisis / Diálisis Peritoneal'),
        ('SAL-PRO-010', 'Fisioterapia / Rehabilitación Física'),
        ('SAL-PRO-011', 'Terapia Respiratoria / Oxigenoterapia'),
        ('SAL-PRO-012', 'Terapia Ocupacional'),
        ('SAL-PRO-013', 'Terapia del Lenguaje / Fonoaudiología'),
        ('SAL-PRO-014', 'Psicoterapia / Terapia Psicológica'),
        ('SAL-PRO-015', 'Administración de Medicamentos (IV, IM, SC)'),
        ('SAL-PRO-016', 'Curación de Heridas Complejas / Escaras'),
        ('SAL-PRO-017', 'Colocación / Retiro de Yeso / Férula'),
        ('SAL-PRO-018', 'Colocación / Retiro de Sonda / Catéter / Drenaje'),
        ('SAL-PRO-019', 'Transfusión Sanguínea / Hemoderivados'),
        ('SAL-PRO-020', 'Nutrición Parenteral / Enteral Especializada'),
        ('SAL-PRO-021', 'Manejo del Dolor Crónico / Unidad del Dolor'),
        ('SAL-PRO-022', 'Cuidados Paliativos / Hospicio'),
        ('SAL-PRO-023', 'Procedimientos Dermatológicos (Crioterpia, Láser, etc.)'),
        ('SAL-PRO-024', 'Procedimientos Oftalmológicos (Inyección Intravítrea, Láser)'),
        ('SAL-PRO-025', 'Procedimientos Cardiológicos (Cateterismo, Angioplastia)'),
        ('SAL-PRO-026', 'Adquisición/Alquiler Equipos Médicos (CPAP, Silla Ruedas)'),
        ('SAL-PRO-027', 'Tratamiento de Fertilidad (Si cubierto)'),
        ('SAL-PRO-028', 'Trasplante de Órganos / Médula Ósea'),
        ('SAL-PRO-029', 'Cirugía Laparoscópica / Mínimamente Invasiva (Especificar)'),
        ('SAL-PRO-030', 'Cirugía Robótica (Especificar)'),
        ('SAL-PRO-031', 'Cirugía Bariátrica (Bypass, Manga Gástrica - Si cubierto)'),
        ('SAL-PRO-032', 'Procedimientos de Radiología Intervencionista (Angioplastia, Embolización)'),
        ('SAL-PRO-033', 'Infiltraciones Articulares / Bloqueos Nerviosos'),
        ('SAL-PRO-034', 'Terapias Alternativas / Complementarias (Acupuntura, Quiropráctica - Si cubierto)'),
        ('SAL-PRO-035', 'Implante / Explante de Dispositivos Médicos (Marcapasos, DIU, etc.)'),

        # === SECCIÓN: SALUD (HCM) - Maternidad ===
        ('SAL-MAT-001', 'Control Prenatal'),
        ('SAL-MAT-002', 'Parto Normal / Cesárea'),
        ('SAL-MAT-003', 'Complicaciones del Embarazo (Preeclampsia, Diabetes Gestacional, etc.)'),
        ('SAL-MAT-004', 'Atención Neonatal / Retén / UCI Neonatal'),
        ('SAL-MAT-005', 'Aborto (Espontáneo / Terapéutico / Inducido)'),
        ('SAL-MAT-006', 'Embarazo Ectópico / Molar'),

        # === SECCIÓN: SALUD (HCM) - Diagnósticos Comunes (Agrupados - Ampliado) ===
        ('SAL-DXG-001', 'Enfermedad Cardiovascular (Hipertensión, Cardiopatía Isquémica, Arritmia)'),
        ('SAL-DXG-002', 'Enfermedad Respiratoria (Asma, EPOC, Neumonía, Bronquitis)'),
        ('SAL-DXG-003', 'Enfermedad Digestiva (Gastritis, Úlcera, Reflujo, Colon Irritable, Enf. Inflamatoria)'),
        ('SAL-DXG-004', 'Enfermedad Neurológica (Migraña, ACV, Epilepsia, Parkinson, Alzheimer)'),
        ('SAL-DXG-005', 'Enfermedad Endocrina/Metabólica (Diabetes Mellitus, Hipotiroidismo, Hipertiroidismo)'),
        ('SAL-DXG-006', 'Enfermedad Renal/Urológica (Insuficiencia Renal, Litiasis, ITU, Próstata)'),
        ('SAL-DXG-007', 'Enfermedad Ginecológica (Miomas, Endometriosis, SOP, Infecciones)'),
        ('SAL-DXG-008', 'Enfermedad Oncológica (Cáncer - Especificar Tipo/Localización Inicial)'),
        ('SAL-DXG-009', 'Enfermedad Reumatológica/Autoinmune (Artritis Reumatoide, Lupus, Fibromialgia)'),
        ('SAL-DXG-010', 'Enfermedad Infecciosa/Parasitaria (Viral, Bacteriana, Fúngica, Parasitaria)'),
        ('SAL-DXG-011', 'Trastorno Mental/Psiquiátrico (Depresión, Ansiedad, Bipolaridad, Esquizofrenia)'),
        ('SAL-DXG-012', 'Enfermedad Dermatológica (Psoriasis, Eczema, Dermatitis, Acné Severo, Infecciones Cutáneas)'),
        ('SAL-DXG-013', 'Enfermedad Oftalmológica (Cataratas, Glaucoma, Retinopatía, Deg. Macular)'),
        ('SAL-DXG-014', 'Enfermedad Otorrinolaringológica (ORL - Sinusitis, Otitis, Vértigo, Amigdalitis)'),
        ('SAL-DXG-015', 'Enfermedad Hematológica (Anemia, Trastornos Coagulación, Leucemia, Linfoma)'),
        ('SAL-DXG-016', 'Traumatismo / Lesión Aguda (Contusión, Herida, Quemadura Leve)'),
        ('SAL-DXG-017', 'Condición Relacionada con Embarazo/Parto (Diagnóstico específico)'),
        ('SAL-DXG-018', 'Enfermedad Congénita / Genética (Síndrome específico)'),
        ('SAL-DXG-019', 'Enfermedad del Hígado / Hepatopatía (Hepatitis, Cirrosis)'),
        ('SAL-DXG-020', 'Trastornos del Sueño (Apnea, Insomnio Crónico)'),
        ('SAL-DXG-021', 'Obesidad Mórbida (Si es diagnóstico primario)'),
        ('SAL-DXG-022', 'Enfermedades de Transmisión Sexual (ETS - VIH, Sífilis, etc.)'),
        ('SAL-DXG-023', 'Trastornos de la Alimentación (Anorexia, Bulimia)'),
        ('SAL-DXG-024', 'Dependencia / Abuso de Sustancias (Alcoholismo, Drogadicción)'),
        ('SAL-DXG-025', 'Dolor Crónico No Oncológico (Lumbalgia, Neuralgia)'),
        ('SAL-DXG-026', 'Enfermedad Vascular Periférica (Insuficiencia Venosa, Arteriopatía)'),  # NUEVO

        # === SECCIÓN: ODONTOLOGÍA (Ampliado) ===
        ('ODN-CON-001', 'Consulta / Revisión / Diagnóstico Odontológico'),
        ('ODN-PRO-001', 'Profilaxis / Limpieza Dental'),
        ('ODN-PRO-002', 'Aplicación de Flúor / Remineralización'),
        ('ODN-PRO-003', 'Sellantes de Fosas y Fisuras'),
        ('ODN-PRO-004', 'Radiografía Dental (Periapical, Panorámica, Cefálica, CBCT)'),
        ('ODN-PRO-005', 'Tartrectomía / Eliminación de Cálculo Supragingival'),
        ('ODN-DXG-001', 'Caries Dental (Especificar Superficie/Diente)'),
        ('ODN-TRT-001', 'Obturación / Restauración (Resina, Amalgama, Ionómero)'),
        ('ODN-DXG-002', 'Pulpitis / Necrosis Pulpar / Dolor Dental Agudo'),
        ('ODN-TRT-002', 'Tratamiento de Conducto / Endodoncia (Uni/Multi Radicular)'),
        ('ODN-TRT-003', 'Apicoformación / Apexificación / Pulpotomía'),
        ('ODN-TRT-004', 'Recubrimiento Pulpar (Directo/Indirecto)'),
        ('ODN-TRT-018', 'Retratamiento Endodóntico'),
        ('ODN-TRT-019', 'Cirugía Apical / Apicectomía'),
        ('ODN-DXG-003', 'Gingivitis / Inflamación Gingival'),
        ('ODN-DXG-004', 'Periodontitis (Leve, Moderada, Severa)'),
        ('ODN-TRT-005', 'Curetaje / Alisado Radicular / Raspado Periodontal'),
        ('ODN-TRT-006', 'Cirugía Periodontal (Colgajo, Injerto)'),
        ('ODN-TRT-007', 'Extracción Dental Simple'),
        ('ODN-TRT-008', 'Extracción Dental Quirúrgica / Tercer Molar / Diente Impactado'),
        ('ODN-TRT-009', 'Drenaje de Absceso Dental / Celulitis Facial'),
        ('ODN-TRT-010', 'Corona Dental (Metal-Porc, Zirconio, Emax, Temporal)'),
        ('ODN-TRT-011', 'Puente Fijo Dental (Especificar Unidades/Material)'),
        ('ODN-TRT-012', 'Prótesis Parcial Removible (Acrílica, Metálica)'),
        ('ODN-TRT-013', 'Prótesis Total Removible (Superior/Inferior)'),
        ('ODN-TRT-014', 'Implante Dental (Fase Quirúrgica / Fase Protésica)'),
        ('ODN-TRT-015', 'Ortodoncia (Instalación, Control, Retiro Aparatología)'),
        ('ODN-TRT-016', 'Férula Oclusal / Placa de Descarga / Guarda Nocturna'),
        ('ODN-TRT-017', 'Biopsia Oral / Estudio Histopatológico'),
        ('ODN-TRT-020', 'Blanqueamiento Dental (Si cubierto estético)'),
        ('ODN-TRT-021', 'Mantenimiento Periodontal'),
        ('ODN-DXG-005', 'Bruxismo / Apretamiento Dental'),
        ('ODN-DXG-006', 'Trastorno Temporomandibular (ATM) / Disfunción'),
        ('ODN-DXG-007', 'Lesiones Orales (Leucoplasia, Aftas, Mucocele, Liquen Plano)'),
        ('ODN-DXG-008', 'Maloclusión / Problema Ortodóntico'),
        ('ODN-DXG-009', 'Traumatismo Dental / Fractura Dental / Avulsión'),
        ('ODN-DXG-010', 'Quiste / Tumor Odontogénico'),  # NUEVO
        ('ODN-DXG-011', 'Halitosis (Diagnóstico Causa Oral)'),  # NUEVO

        # === SECCIÓN: ACCIDENTES PERSONALES (Ampliado) ===
        ('ACC-TRA-001', 'Fractura (Especificar hueso y tipo: cerrada, abierta, etc.)'),
        ('ACC-TRA-002', 'Luxación / Dislocación Articular (Especificar articulación)'),
        ('ACC-TRA-003', 'Esguince / Distensión / Desgarro (Ligamento, Músculo, Tendón)'),
        ('ACC-TRA-004', 'Herida Abierta / Laceración / Abrasión / Avulsión'),
        ('ACC-TRT-001', 'Sutura de Herida / Cierre Quirúrgico / Grapas'),
        ('ACC-TRA-005', 'Contusión / Hematoma Severo / Aplastamiento'),
        ('ACC-TRA-006', 'Traumatismo Craneoencefálico (TCE - Leve, Moderado, Severo, Conmoción)'),
        ('ACC-TRA-007', 'Traumatismo de Columna Vertebral / Lesión Medular / Hernia Discal Traumática'),
        ('ACC-TRA-008', 'Quemadura (Especificar grado, extensión y agente: térmica, química, eléctrica)'),
        ('ACC-TRA-009', 'Amputación Traumática'),
        ('ACC-TRA-010', 'Lesión por Cuerpo Extraño (Ojo, Piel, Vía aérea, Digestiva)'),
        ('ACC-TRA-011', 'Mordedura (Animal / Humana)'),
        ('ACC-TRA-012', 'Picadura / Reacción Alérgica Grave (Insecto, Alimento, Medicamento)'),
        ('ACC-TRA-013', 'Asfixia / Ahogamiento / Estrangulamiento / Inhalación Humo'),
        ('ACC-TRA-014', 'Intoxicación / Envenenamiento Accidental (Químicos, Alimentos, Gases)'),
        ('ACC-TRA-015', 'Lesión por Esfuerzo Repetitivo / Sobrecarga Laboral/Deportiva'),  # NUEVO
        ('ACC-TRA-016', 'Caída de Altura / Accidente Laboral Específico'),  # NUEVO
        ('ACC-TRA-017', 'Electrocución'),  # NUEVO
        # NUEVO (Ver VEH)
        ('ACC-TRA-018', 'Accidente de Tránsito (Peatón, Ciclista, Ocupante - Lesiones)'),
        ('ACC-DXG-001', 'Invalidez Permanente Parcial por Accidente'),
        ('ACC-DXG-002', 'Invalidez Permanente Total por Accidente'),
        ('ACC-DXG-003', 'Muerte Accidental'),
        ('ACC-GAS-001', 'Gastos Médicos por Accidente (Consulta, Estudios, Terapia)'),
        ('ACC-GAS-002', 'Gastos de Rehabilitación Física / Ocupacional por Accidente'),
        ('ACC-GAS-003', 'Gastos de Traslado / Ambulancia Terrestre/Aérea por Accidente'),
        ('ACC-GAS-004', 'Renta Diaria por Hospitalización Accidental'),
        ('ACC-GAS-005', 'Gastos Dentales por Accidente'),
        # NUEVO (Puede duplicar con SEP/VID)
        ('ACC-GAS-006', 'Gastos Funerarios por Muerte Accidental'),

        # === SECCIÓN: VIDA (Ampliado) ===
        ('VID-FAL-001', 'Fallecimiento por Enfermedad'),
        ('VID-FAL-002', 'Fallecimiento por Causa Natural (Vejez)'),
        ('VID-INV-001', 'Invalidez Total y Permanente por Enfermedad'),
        ('VID-INV-002', 'Enfermedad Grave / Crítica (Diagnóstico - Ej: Cáncer, ACV, IAM, Renal Crónico)'),
        ('VID-ADE-001', 'Adelanto de Suma Asegurada por Enfermedad Grave/Terminal'),
        ('VID-GAS-001', 'Gastos Funerarios (Cobertura Adicional Póliza Vida)'),
        ('VID-SOB-001', 'Beneficio por Sobrevivencia / Dotal'),
        # NUEVO (ligado a Educativo)
        ('VID-EDU-001', 'Fondo Educativo (por fallecimiento/invalidez tomador)'),

        # === SECCIÓN: SEPELIO (Ampliado) ===
        ('SEP-SER-001', 'Servicios Funerarios Básicos (Ataúd, Sala, Traslado Local)'),
        ('SEP-SER-002', 'Servicios Funerarios Completos (Incluye Trámites, Religioso, Recordatorios)'),
        ('SEP-SER-003', 'Cremación y Urna Básica / Especial'),
        ('SEP-SER-004', 'Inhumación / Entierro (Apertura/Cierre Fosa)'),
        ('SEP-SER-005', 'Traslado Nacional / Internacional del Cuerpo / Cenizas'),
        ('SEP-SER-006', 'Adquisición / Alquiler / Mantenimiento de Parcela / Nicho'),
        ('SEP-SER-007', 'Gastos de Exhumación / Traslado de Restos'),
        ('SEP-REM-001', 'Reembolso Gastos Funerarios (Presentando Facturas)'),
        ('SEP-SER-008', 'Preparación / Embalsamamiento / Tanatopraxia'),
        ('SEP-SER-009', 'Servicios Adicionales (Flores, Coro, Catering, Obituario)'),
        ('SEP-SER-010', 'Asistencia Psicológica Duelo'),  # NUEVO

        # === SECCIÓN: MASCOTAS (Ampliado) ===
        ('MAS-CON-001', 'Consulta Veterinaria por Enfermedad (Diagnóstico/Tratamiento)'),
        ('MAS-CON-002', 'Consulta Veterinaria por Accidente'),
        ('MAS-CON-003', 'Consulta Veterinaria de Emergencia / Hospitalización'),
        ('MAS-EST-001', 'Exámenes de Laboratorio Veterinario (Sangre, Orina, Heces, Biopsia)'),
        ('MAS-EST-002', 'Imagenología Veterinaria (Rayos X, Eco, TAC, RMN)'),
        ('MAS-TRT-001', 'Tratamiento Médico Ambulatorio (Medicamentos, Fluidos, Curas)'),
        ('MAS-TRT-002', 'Hospitalización Veterinaria (UCI, Monitoreo)'),
        ('MAS-TRT-003', 'Cirugía Veterinaria (Esterilización, Ortopédica, Tejidos Blandos, Ocular)'),
        ('MAS-TRT-004', 'Medicamentos Recetados Post-Consulta / Post-Operatorios'),
        ('MAS-TRT-005', 'Tratamiento por Envenenamiento / Intoxicación (Mascota)'),
        ('MAS-TRT-006', 'Eutanasia Humanitaria (Por razones médicas justificadas)'),
        ('MAS-PRE-001', 'Medicina Preventiva (Consulta Rutina, Vacunas, Desparasitación - Si cubierto)'),
        ('MAS-ODN-001', 'Tratamiento Odontológico Veterinario (Limpieza, Extracción, Endodoncia)'),
        ('MAS-REH-001', 'Fisioterapia / Rehabilitación Veterinaria'),
        ('MAS-CIV-001', 'Responsabilidad Civil (Daños materiales/lesiones causados por la mascota a terceros)'),
        ('MAS-HOS-001', 'Gastos de Guardería/Hospedaje por hospitalización del dueño'),
        ('MAS-EXT-001', 'Gastos por Extravío (Publicidad, Recompensa - Si cubierto)'),
        ('MAS-COMPORT-001',
         'Terapia de Comportamiento / Adiestramiento (Si cubierto)'),  # NUEVO
        ('MAS-DERMA-001', 'Tratamiento Dermatológico Veterinario (Alergias, Infecciones)'),  # NUEVO

        # === SECCIÓN: VEHÍCULOS (Ampliado) ===
        ('VEH-COL-001', 'Colisión / Choque Leve (Daños propios)'),
        ('VEH-COL-002', 'Colisión / Choque Grave (Pérdida Parcial / Total Daños Propios)'),
        ('VEH-VOL-001', 'Volcamiento (Daños propios)'),
        ('VEH-ROB-001', 'Robo Total del Vehículo'),
        ('VEH-ROB-002', 'Robo Parcial / Hurto de Piezas / Accesorios (Sonido, Rines, Batería)'),
        ('VEH-INC-001', 'Incendio / Explosión del Vehículo (Parcial / Total)'),
        ('VEH-NAT-001', 'Daños por Fenómeno Natural (Inundación, Granizo, Viento, Sismo, Caída Árbol)'),
        ('VEH-CRI-001', 'Rotura / Reparación de Cristales (Parabrisas, Laterales, Techo Solar, Espejos)'),
        ('VEH-RCV-MAT-001',
         'Responsabilidad Civil - Daños Materiales a Terceros (Vehículo, Propiedad)'),
        ('VEH-RCV-LES-001', 'Responsabilidad Civil - Lesiones / Muerte a Terceros (Peatones, Ocupantes otro vehículo)'),
        ('VEH-RCV-EXC-001', 'Responsabilidad Civil - Exceso de Límite (Si contratado)'),
        ('VEH-ASIS-001', 'Servicio de Grúa / Remolque (Local / Nacional)'),
        ('VEH-ASIS-002', 'Asistencia Vial (Cambio Neumático, Combustible, Batería, Cerrajería)'),
        ('VEH-ASIS-003', 'Asistencia Legal / Defensa Jurídica Accidente Tránsito'),
        ('VEH-ACC-PER-001', 'Accidentes Personales Ocupantes del Vehículo Asegurado'),
        ('VEH-GAS-MED-001', 'Gastos Médicos Ocupantes del Vehículo Asegurado'),
        ('VEH-PER-TOT-001', 'Pérdida Total por Daños Materiales Graves'),
        ('VEH-VAND-001', 'Actos Vandálicos / Malintencionados (Rayones, Roturas deliberadas)'),
        ('VEH-MOT-001', 'Avería Mecánica (Garantía Extendida / Cobertura Específica Motor/Caja)'),
        ('VEH-LLAN-001', 'Daño Accidental a Llantas / Rines'),
        ('VEH-CER-001', 'Gastos de Cerrajería Vehicular (Pérdida / Robo Llaves)'),
        ('VEH-REP-001', 'Vehículo de Reemplazo / Gastos de Movilización'),  # NUEVO

        # === SECCIÓN: HOGAR (Ampliado) ===
        ('HOG-INC-001', 'Daños por Incendio / Rayo / Explosión (Edificación / Contenidos)'),
        ('HOG-AGU-001', 'Daños por Agua Accidental (Fuga Interna, Tuberías, Filtraciones Techo/Pared)'),
        ('HOG-AGU-002', 'Daños por Agua (Inundación Externa, Lluvias Intensas, Desbordamiento)'),
        ('HOG-ROB-001', 'Robo / Hurto dentro de la Vivienda (Con/Sin Forzamiento - Contenidos)'),
        ('HOG-ROB-002', 'Daños a Edificación durante Robo/Intento'),  # NUEVO
        ('HOG-CRI-001', 'Rotura Accidental de Cristales (Ventanas, Puertas, Mesas, Vitrinas)'),
        ('HOG-EQU-001', 'Daño Accidental Equipo Electrónico / Línea Blanca (TV, Nevera, Lavadora)'),
        ('HOG-CIV-001', 'Responsabilidad Civil Familiar (Daños materiales/lesiones a terceros causados por habitantes/mascotas)'),
        ('HOG-NAT-001', 'Daños por Fenómeno Natural (Viento Fuerte, Granizo, Impacto Rayo, Deslizamiento)'),
        ('HOG-TERR-001', 'Daños por Terremoto / Temblor / Erupción Volcánica'),
        ('HOG-ELEC-001', 'Daños Eléctricos (Sobretensión, Cortocircuito - Aparatos Eléctricos)'),
        ('HOG-ASIS-001', 'Asistencia Domiciliaria Urgente (Plomería, Electricidad, Cerrajería, Vidriería)'),
        ('HOG-COL-001', 'Colapso Estructural / Daños a la Edificación (Causas Cubiertas)'),
        ('HOG-REM-001', 'Gastos de Remoción de Escombros post-siniestro'),
        ('HOG-ALO-001', 'Gastos de Alojamiento Temporal / Pérdida de Alquileres por Siniestro'),
        ('HOG-JAR-001', 'Daños a Jardines / Muros / Cercas Exteriores'),
        ('HOG-PLG-001', 'Control / Exterminación de Plagas (Si cubierto)'),
        ('HOG-VAND-001', 'Actos Vandálicos / Malintencionados (Grafiti, Daños a Fachada)'),
        ('HOG-ALIM-001', 'Daño a Alimentos Refrigerados por Falla Eléctrica'),  # NUEVO

        # === SECCIÓN: COMERCIO / PYME (Ampliado) ===
        ('PYM-INC-001', 'Daños Materiales por Incendio (Edificio, Mobiliario, Existencias, Maquinaria)'),
        ('PYM-ROB-001', 'Pérdidas por Robo con Forzamiento / Asalto (Mercancía, Dinero en Caja/Tránsito)'),
        ('PYM-ROB-002', 'Pérdidas por Asalto a Transportista de Valores / Empleado'),
        ('PYM-EQU-001', 'Daño / Avería Equipos Electrónicos (Computadoras, Servidores, POS, Equipos Médicos/Oficina)'),
        ('PYM-MAQ-001', 'Daño / Avería de Maquinaria Fija / Móvil'),
        ('PYM-CIV-GEN-001', 'Responsabilidad Civil General / Explotación (Daños a terceros en local/por operaciones)'),
        ('PYM-CIV-PRO-001',
         'Responsabilidad Civil Productos (Daños causados por producto defectuoso)'),
        ('PYM-CIV-PAT-001', 'Responsabilidad Civil Patronal (Accidente laboral empleado)'),
        ('PYM-TRA-001', 'Pérdida o Daño de Mercancía en Tránsito (Transporte Propio / Contratado)'),
        ('PYM-LUC-001', 'Pérdida de Beneficios / Lucro Cesante (Interrupción del Negocio por siniestro cubierto)'),
        ('PYM-ROT-001', 'Rotura de Cristales / Avisos / Letreros / Fachadas'),
        ('PYM-FID-001', 'Infidelidad de Empleados / Deshonestidad (Robo interno)'),
        ('PYM-EQU-ROT-001', 'Rotura Accidental de Maquinaria (Cobertura Específica)'),
        ('PYM-ACC-CLI-001', 'Accidentes Personales Clientes / Visitantes en Local'),
        ('PYM-PAR-MAQ-001', 'Paralización de Maquinaria (Pérdida de Beneficios asociada)'),
        ('PYM-PER-ALQ-001', 'Pérdida de Alquileres (Inmueble Comercial arrendado)'),
        ('PYM-CONTAM-001', 'Contaminación Accidental (RC Ambiental PYME)'),  # NUEVO

        # === SECCIÓN: RESPONSABILIDAD CIVIL (General y Profesional) ===
        ('RC-GEN-001', 'RC General - Daños Materiales a Terceros'),
        ('RC-GEN-002', 'RC General - Lesiones Corporales / Muerte a Terceros'),
        ('RC-PRO-MED-001', 'RC Profesional Médica / Sanitaria (Mala Praxis)'),
        ('RC-PRO-ABO-001', 'RC Profesional Abogados / Asesores Legales'),
        ('RC-PRO-ING-001', 'RC Profesional Ingenieros / Arquitectos / Constructores'),
        ('RC-PRO-CON-001', 'RC Profesional Contadores / Auditores / Consultores Financieros'),
        ('RC-PRO-TEC-001', 'RC Profesional Tecnológica / Errores y Omisiones TI (E&O)'),
        ('RC-D&O-001', 'RC Directores y Administradores (D&O - Decisiones Gerenciales)'),
        ('RC-EMP-001', 'RC Prácticas Laborales Indebidas (EPLI - Acoso, Discriminación)'),
        ('RC-PROD-001', 'RC Productos Defectuosos / Retiro de Productos'),
        ('RC-AMB-001', 'RC Ambiental / Contaminación Accidental Gradual/Súbita'),
        ('RC-CONDOM-001', 'RC Condominios / Juntas de Condominio (Áreas Comunes, Decisiones)'),
        ('RC-EVENTO-001', 'RC Eventos Temporales (Públicos/Privados)'),
        ('RC-CYBER-001', 'RC por Violación de Datos / Ciberseguridad (Frente a Terceros)'),  # NUEVO

        # === SECCIÓN: FINANCIERO Y ESPECIALIZADO ===
        ('FIN-FID-001', 'Fraude / Deshonestidad Empleados (Póliza Fidelity / BBB)'),
        ('FIN-CYB-001', 'Ciberataque / Violación de Datos (Gastos propios: forense, notificación, PR)'),
        ('FIN-CYB-002', 'Extorsión Cibernética / Ransomware (Pago rescate, restauración)'),
        ('FIN-CYB-003', 'Interrupción de Negocio por Ciberataque (Pérdida beneficios)'),
        ('FIN-CRED-001', 'Seguro de Crédito (Impago de Deudas Comerciales Cliente)'),
        ('FIN-CAU-001', 'Seguro de Caución / Garantía (Cumplimiento Contrato, Judicial, Aduanera)'),
        ('SPEC-MAR-CAR-001',
         'Marítimo - Daño / Pérdida de Carga (Transporte Marítimo/Aéreo/Terrestre)'),
        ('SPEC-MAR-HUL-001', 'Marítimo - Daño Casco y Maquinaria Buques'),
        ('SPEC-AVI-001', 'Aviación - Daño Casco Aeronave / RC Pasajeros / Carga'),
        ('SPEC-ENG-CAR-001', 'Ingeniería - Todo Riesgo Construcción (CAR)'),
        ('SPEC-ENG-EAR-001', 'Ingeniería - Todo Riesgo Montaje (EAR)'),
        ('SPEC-AGR-001', 'Agrícola - Daño Cosecha / Pérdida Ganado (Clima, Plaga, Enfermedad)'),
        ('SPEC-EVE-001', 'Cancelación / Aplazamiento de Eventos (Causas Cubiertas)'),
        ('SPEC-LEG-001', 'Seguro de Defensa Jurídica / Gastos Legales'),
        ('SPEC-ARTE-001', 'Seguro de Obras de Arte / Colecciones Valiosas'),
        ('SPEC-TITU-001', 'Seguro de Títulos de Propiedad (Property Title Insurance)'),  # NUEVO
        ('SPEC-K&R-001', 'Seguro de Secuestro y Rescate (Kidnap & Ransom)'),  # NUEVO

        # === SECCIÓN: VIAJES (Ampliado) ===
        ('VIA-MED-001', 'Emergencia Médica / Enfermedad en Viaje (Gastos Médicos, Hospitalización)'),
        ('VIA-ACC-001', 'Accidente Personal en Viaje (Gastos Médicos, Incapacidad, Muerte)'),
        ('VIA-ODN-001', 'Emergencia Odontológica en Viaje (Dolor Agudo, Infección, Fractura)'),
        ('VIA-CAN-001', 'Cancelación / Interrupción de Viaje (Causas Cubiertas: Enfermedad, Familiar, etc.)'),
        ('VIA-EQU-PER-001', 'Pérdida Total / Parcial de Equipaje Facturado'),
        ('VIA-EQU-DEM-001', 'Demora en Entrega de Equipaje (Gastos Primera Necesidad)'),
        ('VIA-VUE-DEM-001', 'Demora de Vuelo (Gastos Alojamiento/Comida)'),
        ('VIA-VUE-CAN-001', 'Cancelación de Vuelo (Reembolso / Gastos Alternativos)'),
        ('VIA-VUE-CON-001', 'Pérdida de Conexión (Gastos Alojamiento/Transporte)'),
        ('VIA-REP-MED-001', 'Repatriación Sanitaria / Evacuación Médica Urgente'),
        ('VIA-REP-FUN-001', 'Repatriación Funeraria / Traslado de Restos Mortales'),
        ('VIA-DOC-001', 'Pérdida / Robo de Documentos / Pasaporte (Gastos Reposición)'),
        ('VIA-LEG-001', 'Asistencia Legal en Viaje (Civil / Penal Básico)'),
        ('VIA-ADE-001', 'Adelanto de Fondos / Pago de Fianza'),
        ('VIA-CIV-001', 'Responsabilidad Civil en Viaje (Daños a Terceros)'),  # NUEVO

        # === OTROS / ADMINISTRATIVOS (Ampliado) ===
        ('ADM-REM-001', 'Reembolso General (No especificado - Usar con precaución)'),
        ('ADM-AVA-001', 'Solicitud / Trámite / Emisión Carta Aval'),
        ('ADM-ERR-001', 'Corrección / Ajuste Administrativo Póliza/Recibo/Datos'),
        ('ADM-INF-001', 'Solicitud de Información / Estado de Cuenta / Certificado Cobertura'),
        ('ADM-INV-001', 'Reclamación en Proceso de Investigación (Pendiente Dictamen)'),
        ('ADM-FRA-001', 'Reclamación Rechazada por Fraude / Exclusión Contractual'),
        ('ADM-WIT-001', 'Reclamación Retirada / Desistida por el Asegurado'),
        ('ADM-COM-001', 'Queja / Reclamo sobre Servicio / Atención al Cliente'),
        ('ADM-PAG-001', 'Problema / Consulta Relacionada con Pago de Prima / Cobranza'),
        ('ADM-CAN-POL-001', 'Solicitud de Cancelación de Póliza'),
        ('ADM-END-001', 'Solicitud de Endoso / Modificación de Póliza (Cambio Datos, Coberturas)'),
        # Mantener como último recurso
        ('OTR-NOCLASIF', 'Otro Diagnóstico / Causa No Clasificada (REQUIERE DESCRIPCIÓN DETALLADA)')
    ]


# =================================================================
# Para Crear Tarifas
# =================================================================

RAMO_ABREVIATURAS = {
    'HCM': 'HCM',
    'VIDA': 'VID',
    'VEHICULOS': 'VEH',
    'HOGAR': 'HOG',
    'PYME': 'PYM',
    'ACCIDENTES_PERSONALES': 'AP',
    'SEPELIO': 'SEP',
    'VIAJES': 'VIA',
    'EDUCATIVO': 'EDU',
    'MASCOTAS': 'MAS',
    'OTROS': 'OTR',
}

# Para rangos, podemos tomar los números directamente y unirlos
# o crear un mapeo si las claves no son numéricas o queremos algo diferente
RANGO_ETARIO_ABREVIATURAS = {
    '0-17': '0017',
    '18-25': '1825',
    '26-35': '2635',
    '36-45': '3645',
    '46-55': '4655',
    '56-65': '5665',
    '66-70': '6670',
    '71-75': '7175',
    '76-80': '7680',
    '81-89': '8189',
    '90-99': '9099',
}


# =================================================================
# CLASE DE VALIDACIONES COMUNES
# =================================================================
DIAS_VENCIMIENTO_FACTURA = 30


class CommonValidators:
    """Validadores comunes reutilizables en múltiples modelos"""

    @staticmethod
    def validate_file_size(value):
        """Valida que el tamaño del archivo no exceda 5MB"""
        limit = 5 * 1024 * 1024
        if value.size > limit:
            raise ValidationError(('El archivo no puede exceder los 5MB'))

    @staticmethod
    def validate_cedula_format(value):
        """Valida formato de cédula: V/E-12345678"""
        if not re.match(r'^[VE]-\d{7,8}$', value):
            raise ValidationError(('Formato inválido. Use: V-12345678'))

    @staticmethod
    def validate_rif_format(value):
        """Valida formato de RIF: J/G/V-12345678-9"""
        if not re.match(r'^[JGV]-\d{8}-\d$', value):
            raise ValidationError(('Formato inválido. Use: J-12345678-9'))

    @staticmethod
    def validate_fecha_nacimiento(value):
        hoy = date.today()
        if value < date(1900, 1, 1):
            raise ValidationError("Fecha de nacimiento demasiado antigua")
        if value > hoy:
            raise ValidationError("Fecha de nacimiento no puede ser futura")

# =================================================================
# CLASE DE CONSTANTES COMUNES
# =================================================================


class CommonConstants:
    """Constantes reutilizables en todo el sistema"""

    # Regex para validaciones
    REGEX_CEDULA = r'^[VE]-\d{7,8}$'
    REGEX_RIF = r'^[JGV]-\d{8}-\d$'

    # Configuraciones de archivos
    ALLOWED_FILE_EXTENSIONS = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE_MB = 10

    # Duración predeterminada de vigencia de contratos (en días)
    DURACION_VIGENCIA_CONTRATO = timedelta(days=365)

    # Límites para validaciones
    LIMITE_COMISION_MINIMA = 0.0
    LIMITE_COMISION_MAXIMA = 100.0

    PAGINATE_BY = 30

    UPLOAD_TO_DOCUMENTOS_RECLAMOS = 'documentos_reclamos/'
    UPLOAD_TO_DOCUMENTOS_PAGOS = 'documentos_pagos/'

    # Porcentaje máximo de descuento permitido
    PORCENTAJE_DESCUENTO_MAXIMO = 20.0

    # Valor predeterminado para campos numéricos
    VALOR_PREDETERMINADO_NUMERICO = 0.00

    # Valor predeterminado para campos de texto
    VALOR_PREDETERMINADO_TEXTO = ""

    # Valor predeterminado para campos booleanos
    VALOR_PREDETERMINADO_BOOLEANO = False

    # Mensajes de Error
    MENSAJES_ERROR = {
        'CAMPO_REQUERIDO': "Este campo es obligatorio.",
        'FORMATO_INVALIDO': "El formato ingresado no es válido.",
        'FECHA_FUTURA': "La fecha no puede ser futura.",
        'MONTO_NEGATIVO': "El monto no puede ser negativo.",
        'DOCUMENTO_NO_ENCONTRADO': "El documento no fue encontrado.",
        'PERMISION_DENEGADO': "No tienes permiso para realizar esta acción.",
    }
