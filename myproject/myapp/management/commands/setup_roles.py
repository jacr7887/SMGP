# myapp/management/commands/setup_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
import logging

logger = logging.getLogger(__name__)

# --- DEFINICIÓN CENTRALIZADA DE ROLES Y PERMISOS ---
# Basado en tu descripción:
ROLES_Y_PERMISOS = {
    "Rol - Auditor": [
        "view_afiliadoindividual", "view_afiliadocolectivo",
        "view_contratoindividual", "view_contratocolectivo",
        "view_intermediario", "view_factura", "view_pago",
        "view_reclamacion", "view_tarifa", "view_usuario"
    ],
    "Rol - Cliente": [
        "view_afiliadoindividual", "add_afiliadoindividual", "change_afiliadoindividual",
        "view_afiliadocolectivo", "add_afiliadocolectivo", "change_afiliadocolectivo",
        "view_contratoindividual", "add_contratoindividual", "change_contratoindividual",
        "view_contratocolectivo", "add_contratocolectivo", "change_contratocolectivo",
        "view_intermediario", "add_intermediario", "change_intermediario",
        "view_factura", "add_factura", "change_factura",
        "view_pago", "add_pago", "change_pago",
        "view_reclamacion", "add_reclamacion", "change_reclamacion",
        "view_tarifa", "add_tarifa", "change_tarifa"
        # No tienen permisos de 'delete'
    ],
    "Rol - Intermediario": [
        # Permisos para ver sus propios datos (el filtrado se hace en las vistas)
        "view_contratoindividual", "view_contratocolectivo",
        "view_afiliadoindividual", "view_afiliadocolectivo",
        # Permisos para crear registros para sus clientes
        "add_pago", "add_reclamacion"
    ],
    # El rol de Administrador no necesita un grupo, ya que es superusuario.
    # Pero lo creamos por si en el futuro quieres un admin que no sea superuser.
    "Rol - Administrador": [
        "view_auditoriasistema", "change_licenseinfo",
        # Y todos los demás permisos...
        "view_afiliadoindividual", "add_afiliadoindividual", "change_afiliadoindividual", "delete_afiliadoindividual",
        "view_afiliadocolectivo", "add_afiliadocolectivo", "change_afiliadocolectivo", "delete_afiliadocolectivo",
        "view_contratoindividual", "add_contratoindividual", "change_contratoindividual", "delete_contratoindividual",
        "view_contratocolectivo", "add_contratocolectivo", "change_contratocolectivo", "delete_contratocolectivo",
        "view_intermediario", "add_intermediario", "change_intermediario", "delete_intermediario",
        "view_factura", "add_factura", "change_factura", "delete_factura",
        "view_pago", "add_pago", "change_pago", "delete_pago",
        "view_reclamacion", "add_reclamacion", "change_reclamacion", "delete_reclamacion",
        "view_tarifa", "add_tarifa", "change_tarifa", "delete_tarifa",
        "view_usuario", "add_usuario", "change_usuario", "delete_usuario"
    ]
}


class Command(BaseCommand):
    help = 'Crea o actualiza los grupos de roles funcionales y sus permisos.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            "Iniciando configuración de roles..."))

        for group_name, perm_codenames in ROLES_Y_PERMISOS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(f"Grupo '{group_name}' CREADO.")
            else:
                self.stdout.write(
                    f"Grupo '{group_name}' ya existe, actualizando permisos.")

            group.permissions.clear()
            permissions_to_add = []
            for codename in perm_codenames:
                try:
                    perm = Permission.objects.get(codename=codename)
                    permissions_to_add.append(perm)
                except Permission.DoesNotExist:
                    self.stderr.write(self.style.ERROR(
                        f"ADVERTENCIA: Permiso '{codename}' no encontrado. Omitiendo."))

            if permissions_to_add:
                group.permissions.add(*permissions_to_add)
                self.stdout.write(
                    f"  -> Asignados {len(permissions_to_add)} permisos a '{group_name}'.")

        self.stdout.write(self.style.SUCCESS(
            "¡Configuración de roles completada!"))
