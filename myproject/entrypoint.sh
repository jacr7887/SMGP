#!/bin/sh

# Salir inmediatamente si un comando falla
set -e

echo "RUNNING: Django MPC Entrypoint Script..."
echo "----------------------------------------"

# 1. Aplicar migraciones de la base de datos
echo "RUNNING: Applying database migrations..."
python manage.py migrate --noinput
echo "COMPLETED: Migrations (or noinput if already up-to-date)."
echo "----------------------------------------"

# 2. Crear/Asegurar el superusuario (usará las variables de entorno)
echo "RUNNING: Ensuring superuser exists..."
python manage.py ensure_superuser
echo "COMPLETED: Superuser check/creation."
echo "----------------------------------------"

# 3. Poblar con datos de demostración (seed_db)
echo "INFO: Checking if database needs seeding..."
NUM_CONTRATOS=$(python manage.py shell -c "from myapp.models import ContratoIndividual, ContratoColectivo; print(ContratoIndividual.objects.count() + ContratoColectivo.objects.count())" 2>/dev/null || echo "Error_Checking_Contracts")
# El "2>/dev/null || echo "Error_Checking_Contracts" es para capturar errores si el comando shell falla
# y asignar un valor no numérico a NUM_CONTRATOS para que el if siguiente no falle por sintaxis.

echo "INFO: Current number of contracts found: '$NUM_CONTRATOS'"

# Intentar convertir a entero para la comparación, si falla, asumir 0
if ! [ "$NUM_CONTRATOS" -eq "$NUM_CONTRATOS" ] 2>/dev/null || [ -z "$NUM_CONTRATOS" ] || [ "$NUM_CONTRATOS" = "Error_Checking_Contracts" ]; then
    echo "WARNING: Could not reliably determine contract count, assuming 0 for seeding decision."
    NUM_CONTRATOS_INT=0
else
    NUM_CONTRATOS_INT=$NUM_CONTRATOS
fi

# Ajusta este umbral según sea necesario
UMBRAL_CONTRATOS_PARA_SEED=5 

if [ "$NUM_CONTRATOS_INT" -lt "$UMBRAL_CONTRATOS_PARA_SEED" ]; then
    echo "RUNNING: Number of contracts ($NUM_CONTRATOS_INT) is less than $UMBRAL_CONTRATOS_PARA_SEED. Seeding database..."
    python manage.py seed_db \
        --users 10 --intermediarios 5 --afiliados_ind 15 --afiliados_col 5 \
        --tarifas 10 --contratos_ind 12 --contratos_col 5 --facturas 30 \
        --reclamaciones 10 --pagos 20 --igtf_chance 25 --pago_parcial_chance 30
    echo "COMPLETED: Database seeding."
else
    echo "INFO: Database appears to be already seeded (Contracts: $NUM_CONTRATOS_INT). Skipping seed."
fi
echo "----------------------------------------"

# 4. Recolectar archivos estáticos (DESCOMENTA SI NO LO HACES EN EL CONTAINERFILE)
# echo "RUNNING: Collecting static files..."
# python manage.py collectstatic --noinput --clear
# echo "COMPLETED: Static files collected."
# echo "----------------------------------------"

# 5. Iniciar el servidor de aplicación Gunicorn
echo "RUNNING: Starting Gunicorn server..."
echo "INFO: About to execute Gunicorn. If container exits now, Gunicorn failed to start or an earlier script command failed and exited due to 'set -e'."
# sleep 10 # Descomenta esta línea temporalmente si quieres una pausa para revisar los logs antes de que Gunicorn intente iniciar y potencialmente falle rápido.

# Asegúrate de que la ruta a tu aplicación WSGI sea correcta.
# Si tu WORKDIR es /app y tu proyecto Django se llama 'myproject' (la carpeta que contiene settings.py y wsgi.py),
# y esa carpeta 'myproject' está directamente bajo /app (ej. /app/myproject/wsgi.py), entonces 'myproject.wsgi:application' es correcto.
# Si la carpeta del proyecto Django se llama diferente o está en otra subruta de /app, ajusta 'myproject.wsgi:application'.
exec gunicorn myproject.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --log-level=debug \
    --access-logfile '-' \
    --error-logfile '-'

# Si el script llega aquí, significa que 'exec gunicorn' no reemplazó el proceso del shell, lo cual es un problema.
echo "ERROR: Gunicorn exec command did not take over as expected. Script is finishing, but Gunicorn is likely not running correctly."
exit 1 # Salir con error si exec no funcionó