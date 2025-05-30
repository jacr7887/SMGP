#!/bin/sh

# Salir inmediatamente si un comando falla
set -e

echo "RUNNING: Django MPC Entrypoint Script..."
echo "----------------------------------------"
echo "INFO: Current working directory: $(pwd)" # Debería ser /app
echo "INFO: Listing files in /app:"
ls -la /app
echo "----------------------------------------"

# Verificar si manage.py existe en /app/manage.py
if [ ! -f "/app/manage.py" ]; then
    echo "CRITICAL ERROR: /app/manage.py not found. WORKDIR or COPY commands in Containerfile might be incorrect."
    echo "INFO: Listing /app/ directory content for debugging:"
    ls -la /app/
    exit 1
fi
echo "INFO: manage.py found at /app/manage.py"

# 1. Aplicar migraciones de la base de datos
echo "RUNNING: Applying database migrations..."
python /app/manage.py migrate --noinput
echo "COMPLETED: Migrations (or 'No migrations to apply.' if already up-to-date)."
echo "----------------------------------------"

# 2. Crear/Asegurar el superusuario usando createsuperuser --noinput
echo "RUNNING: Attempting to create superuser with 'createsuperuser --noinput'..."
# Django's createsuperuser --noinput leerá las variables de entorno
# DJANGO_SUPERUSER_USERNAME (si USERNAME_FIELD no es email), DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD
# Asegúrate de tener DJANGO_SUPERUSER_EMAIL y DJANGO_SUPERUSER_PASSWORD en tu deploy.env
# Si tu USERNAME_FIELD es 'email', Django usará DJANGO_SUPERUSER_EMAIL para el username.
# Si no, y no defines DJANGO_SUPERUSER_USERNAME, podría fallar o usar un default.
# Para estar seguros, podemos definir DJANGO_SUPERUSER_USERNAME en deploy.env también si es necesario.
python /app/manage.py createsuperuser --noinput || echo "INFO: createsuperuser --noinput either failed or superuser already exists."
echo "COMPLETED: Attempted 'createsuperuser --noinput'."
echo "----------------------------------------"

# Comentamos temporalmente tu comando personalizado ensure_superuser
# echo "RUNNING: Ensuring superuser exists (custom command)..."
# python /app/manage.py ensure_superuser 
# echo "COMPLETED: Custom superuser check/creation."
# echo "----------------------------------------"

# 3. Poblar con datos de demostración (seed_db)
echo "INFO: Checking if database needs seeding..."
PYTHON_SHELL_COMMAND="from myapp.models import ContratoIndividual, ContratoColectivo; print(ContratoIndividual.objects.count() + ContratoColectivo.objects.count())"
NUM_CONTRATOS_OUTPUT=$(python /app/manage.py shell --command="$PYTHON_SHELL_COMMAND" 2>/dev/null || echo "0_ErrorDetecting") # Añadido fallback
NUM_CONTRATOS=$(echo "$NUM_CONTRATOS_OUTPUT" | grep -oE '[0-9]+$' | tail -n 1)

if [ -z "$NUM_CONTRATOS" ] || ! echo "$NUM_CONTRATOS" | grep -Eq '^[0-9]+$'; then
    echo "WARNING: Could not reliably determine contract count (Raw output: '$NUM_CONTRATOS_OUTPUT', Extracted: '$NUM_CONTRATOS'). Assuming 0 for seeding."
    NUM_CONTRATOS_INT=0
else
    NUM_CONTRATOS_INT=$NUM_CONTRATOS
fi
echo "INFO: Current number of contracts found (integer): '$NUM_CONTRATOS_INT'"

UMBRAL_CONTRATOS_PARA_SEED=5
if [ "$NUM_CONTRATOS_INT" -lt "$UMBRAL_CONTRATOS_PARA_SEED" ]; then
    echo "RUNNING: Number of contracts ($NUM_CONTRATOS_INT) is less than $UMBRAL_CONTRATOS_PARA_SEED. Seeding database..."
    python /app/manage.py seed_db \
        --users 10 --intermediarios 5 --afiliados_ind 15 --afiliados_col 5 \
        --tarifas 10 --contratos_ind 12 --contratos_col 5 --facturas 30 \
        --reclamaciones 10 --pagos 20 --igtf_chance 25 --pago_parcial_chance 30
    echo "COMPLETED: Database seeding."
else
    echo "INFO: Database appears to be already seeded (Contracts: $NUM_CONTRATOS_INT). Skipping seed."
fi
echo "----------------------------------------"

# 4. Recolectar archivos estáticos
if [ "$DEBUG" = "False" ] || [ "$DJANGO_COLLECTSTATIC_ON_STARTUP" = "true" ] ; then
    echo "RUNNING: Collecting static files..."
    python /app/manage.py collectstatic --noinput --clear
    echo "COMPLETED: Static files collected."
    echo "----------------------------------------"
else
    echo "INFO: Skipping collectstatic (DEBUG is likely True and DJANGO_COLLECTSTATIC_ON_STARTUP is not 'true')."
    echo "----------------------------------------"
fi

# 5. Iniciar el servidor de aplicación Gunicorn
echo "RUNNING: Starting Gunicorn server..."
echo "INFO: WSGI application path will be: myproject.wsgi:application"
echo "INFO: Gunicorn will bind to 0.0.0.0:8000"

exec gunicorn myproject.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --log-level ${GUNICORN_LOG_LEVEL:-debug} \
    --access-logfile '-' \
    --error-logfile '-'

echo "CRITICAL ERROR (ENTRYPOINT): Gunicorn did not take over or exited unexpectedly."
echo "Check Gunicorn installation, WSGI application path, and Gunicorn logs above."
exit 