# myapp/form_mixin.py

from django import forms
from django.utils import timezone as django_timezone
import datetime  # Importa el módulo datetime
import logging

logger = logging.getLogger(__name__)  # O un logger específico para el mixin


class AwareDateInputMixinVE:
    """
    Mixin para ModelForms.
    Maneja campos definidos como CharField en el formulario que representan fechas o datetimes.
    Convierte la entrada DD/MM/AAAA o DD/MM/AAAA HH:MM a objetos date o datetime 'aware'.

    Uso en la clase del Formulario:
    1. Heredar de este mixin.
    2. Definir un atributo de clase `aware_date_fields_config` como una lista de diccionarios.
       Cada diccionario debe tener:
       - 'name': (str) El nombre del campo del formulario (que es un CharField).
       - 'is_datetime': (bool) True si el campo del modelo subyacente es DateTimeField,
                          False si es DateField.
       - 'format': (str) El formato de string para strptime (ej. '%d/%m/%Y ).
    3. Asegúrate de que los campos listados en `aware_date_fields_config` estén definidos
       como forms.CharField en tu clase de formulario.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'aware_date_fields_config') and isinstance(self.aware_date_fields_config, (list, tuple)):
            for config in self.aware_date_fields_config:
                field_name = config.get('name')
                input_format = config.get('format')
                is_dt = config.get('is_datetime', False)

                if not field_name:
                    logger.warning(
                        f"Mixin VE Advertencia: Configuración en aware_date_fields_config sin 'name' en {self.__class__.__name__}.")
                    continue
                if not input_format:
                    logger.warning(
                        f"Mixin VE Advertencia: Configuración para '{field_name}' en {self.__class__.__name__} no tiene 'format'. Usando default.")
                    input_format = '%d/%m/%Y' if is_dt else '%d/%m/%Y'

                if field_name in self.fields:
                    if isinstance(self.fields[field_name], forms.CharField):
                        setattr(self, f'clean_{field_name}',
                                self._create_clean_method_for_field(
                                    field_name,
                                    input_format,
                                    is_dt
                        ))
                    else:
                        logger.warning(
                            f"Mixin VE Advertencia: Campo '{field_name}' en {self.__class__.__name__} no es CharField. "
                            f"El método clean_{field_name} del mixin no será adjuntado."
                        )
                else:
                    logger.warning(
                        f"Mixin VE Advertencia: Campo '{field_name}' listado en aware_date_fields_config "
                        f"no existe en el formulario {self.__class__.__name__}."
                    )
        elif hasattr(self, 'aware_date_fields_config'):
            logger.error(
                f"Error en Mixin VE: 'aware_date_fields_config' en {self.__class__.__name__} debe ser una lista o tupla de diccionarios."
            )

    def _create_clean_method_for_field(self, field_name, input_format_str, is_datetime_field):
        def _clean_specific_field():
            value_from_form = self.cleaned_data.get(field_name)

            print(
                f"DEBUG Mixin _clean_specific_field para '{field_name}': Valor RECIBIDO del form = '{value_from_form}' (Tipo: {type(value_from_form)})")

            # Obtener la instancia del campo del formulario
            field_instance = self.fields[field_name]

            if not value_from_form:  # Si es None o string vacío
                if field_instance.required:
                    # Si el campo es requerido y está vacío, lanzar ValidationError
                    print(
                        f"ERROR Mixin: Campo requerido '{field_name}' está vacío en _clean_specific_field.")
                    raise forms.ValidationError(
                        forms.fields.Field.default_error_messages['required'], code='required')
                return None  # No requerido y vacío, devuelve None

            processed_date_str = str(value_from_form).strip()
            if not processed_date_str:  # Doble chequeo por si era un string de espacios
                if field_instance.required:
                    print(
                        f"ERROR Mixin: Campo requerido '{field_name}' está vacío (después de strip) en _clean_specific_field.")
                    raise forms.ValidationError(
                        forms.fields.Field.default_error_messages['required'], code='required')
                return None

            try:
                if is_datetime_field:
                    dt_naive = datetime.datetime.strptime(
                        processed_date_str, input_format_str)
                    dt_aware = django_timezone.make_aware(
                        dt_naive, django_timezone.get_current_timezone())
                    print(
                        f"DEBUG Mixin _clean_specific_field para '{field_name}': Convertido a DATETIME AWARE = {dt_aware}")
                    return dt_aware
                else:
                    dt_date_obj = datetime.datetime.strptime(
                        processed_date_str, input_format_str).date()
                    print(
                        f"DEBUG Mixin _clean_specific_field para '{field_name}': Convertido a DATE = {dt_date_obj}")
                    return dt_date_obj
            except ValueError:
                field_label = field_instance.label or field_name
                expected_format_display = input_format_str.replace('%d', 'DD').replace('%m', 'MM').replace(
                    '%Y', 'AAAA').replace('%H', 'HH').replace('%M', 'MM').replace('%S', 'SS')
                error_msg = f"Formato de fecha inválido para '{field_label}'. Use {expected_format_display}."
                print(
                    f"DEBUG Mixin: Lanzando ValidationError para {field_name} (ValueError) con mensaje: {error_msg}")
                raise forms.ValidationError(
                    error_msg, code=f'invalid_format_{field_name}')
            except Exception as e:
                field_label = field_instance.label or field_name
                logger.error(
                    f"Mixin _clean_specific_field para '{field_name}': Excepción inesperada parseando '{processed_date_str}': {str(e)}", exc_info=True)
                raise forms.ValidationError(
                    f"Error inesperado procesando fecha para '{field_label}': {str(e)}", code=f'processing_error_{field_name}')

        return _clean_specific_field

    # Los métodos clean_<fieldname> individuales ya no son necesarios aquí,
    # se generan dinámicamente por el __init__ basado en aware_date_fields_config.
