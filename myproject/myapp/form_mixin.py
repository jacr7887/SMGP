# myapp/form_mixins.py (Versión simplificada para Venezuela)

from django import forms
from django.utils import timezone as django_timezone
import datetime
import logging

logger = logging.getLogger(__name__)


class AwareDateInputMixinVE:  # Nombre específico para VE
    """
    Mixin para ModelForms en un contexto venezolano.
    Maneja campos de fecha como CharField con entrada DD/MM/AAAA
    y los convierte a datetimes 'aware'.
    """

    # Formato principal y único esperado del usuario
    VENEZUELAN_DATE_INPUT_FORMAT = '%d/%m/%Y'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'aware_date_fields') and isinstance(self.aware_date_fields, (list, tuple)):
            for field_name in self.aware_date_fields:
                if field_name in self.fields:
                    if isinstance(self.fields[field_name], forms.CharField):
                        setattr(
                            self, f'clean_{field_name}', self._create_clean_method_for_field(field_name))
                    else:
                        logger.warning(
                            f"Mixin VE Advertencia: Campo '{field_name}' en {self.__class__.__name__} no es CharField. "
                            f"El método clean_{field_name} del mixin no será adjuntado."
                        )
                else:
                    logger.warning(
                        f"Mixin VE Advertencia: Campo '{field_name}' en aware_date_fields "
                        f"no existe en el formulario {self.__class__.__name__}."
                    )
        elif hasattr(self, 'aware_date_fields'):
            logger.error(
                f"Error en Mixin VE: 'aware_date_fields' en {self.__class__.__name__} debe ser una lista o tupla."
            )

    def _create_clean_method_for_field(self, field_name):
        def _clean_specific_date_field():
            date_str = self.cleaned_data.get(field_name)
            return self._parse_and_make_aware(date_str, field_name)
        return _clean_specific_date_field

    def _parse_and_make_aware(self, date_str, field_name_for_error_msg):
        if not date_str:
            if field_name_for_error_msg in self.fields and not self.fields[field_name_for_error_msg].required:
                return None

        processed_date_str = str(
            date_str).strip() if date_str is not None else ''
        if not processed_date_str:
            if field_name_for_error_msg in self.fields and not self.fields[field_name_for_error_msg].required:
                return None

        try:
            date_obj = datetime.datetime.strptime(
                processed_date_str, self.VENEZUELAN_DATE_INPUT_FORMAT).date()
            naive_dt = datetime.datetime.combine(
                date_obj, datetime.datetime.min.time())
            aware_dt = django_timezone.make_aware(naive_dt)
            return aware_dt
        except ValueError:
            # Error de formato
            pass  # Se manejará abajo

        field_label = field_name_for_error_msg
        if field_name_for_error_msg in self.fields and self.fields[field_name_for_error_msg].label:
            field_label = self.fields[field_name_for_error_msg].label

        raise forms.ValidationError(
            f"Formato de fecha inválido para '{field_label}'. Use DD/MM/AAAA.",
            code=f'invalid_date_format_{field_name_for_error_msg}'
        )
