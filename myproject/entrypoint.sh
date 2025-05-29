#!/bin/sh

# Salir inmediatamente si un comando falla
set -e

echo "RUNNING: Django MPC Entrypoint Script..."
echo "----------------------------------------"
echo "INFO: Current working directory: $(pwd)"
echo "INFO: Listing files in current directory (/app):"
ls -la
echo "----------------------------------------"

# Verificar si manage.py existe en la ubicación esperada
if [ ! -f "manage.py" ]; then
    echo "CRITICAL ERROR: manage.py not found in $(pwd) (expected in /app). Check your COPY commands in Containerfile."
    # Listar contenido de /app para depuración
    echo "INFO: Listing /app/ directory content:"
    ls -la /app/
    exit 1
fi

# 1. Aplicar migraciones de la base de datos
echo "RUNNING: Applying database migrations..."
python manage.py migrate --noinput
echo "COMPLETED: Migrations (or no_input if already up-to-date)."
echo "----------------------------------------"

# 2. Crear/Asegurar el superusuario (usará las variables de entorno)
echo "RUNNING: Ensuring superuser exists..."
python manage.py ensure_superuser
echo "COMPLETED: Superuser check/creation."
echo "----------------------------------------"

# 3. Poblar con datos de demostración (seed_db)
echo "INFO: Checking if database needs seeding..."
# Usar --skip-checks para acelerar la ejecución del shell si es posible y no hay dependencias de settings completas
# Capturar la salida de forma más robusta
PYTHON_SHELL_COMMAND="from myapp.models import ContratoIndividual, ContratoColectivo; print(ContratoIndividual.objects.count() + ContratoColectivo.objects.count())"
NUM_CONTRATOS=$(python manage.py shell --command="$PYTHON_SHELL_COMMAND" 2>/dev/null)

# Verificar si NUM_CONTRATOS es un número
if ! echo "$NUM_CONTRATOS" | grep -Eq '^[0-9]+$'; then
    echo "WARNING: Could not reliably determine contract count (Output: '$NUM_CONTRATOS'). Assuming 0 for seeding decision."
    NUM_CONTRATOS_INT=0
else
    NUM_CONTRATOS_INT=$NUM_CONTRATOS
fi

echo "INFO: Current number of contracts found (integer): '$NUM_CONTRATOS_INT'"

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

# 4. Recolectar archivos estáticos (MUY IMPORTANTE si DEBUG=False y Gunicorn los va a servir o un proxy)
# Si usas WhiteNoise, a menudo no necesitas un collectstatic explícito aquí si tus
# archivos estáticos ya están en la imagen y WhiteNoise los encuentra.
# Pero si vas a servir estáticos con Nginx o Gunicorn directamente (menos común para Django),
# necesitas collectstatic.
# Si tu Containerfile ya hace esto, puedes comentarlo aquí.
# Si DEBUG=True, el servidor de desarrollo de Django maneja los estáticos.
if [ "$DEBUG" = "False" ] || [ "$DJANGO_COLLECTSTATIC_ON_STARTUP" = "true" ] ; then
    echo "RUNNING: Collecting static files (DEBUG is False or DJANGO_COLLECTSTATIC_ON_STARTUP is true)..."
    python manage.py collectstatic --noinput --clear
    echo "COMPLETED: Static files collected."
    echo "----------------------------------------"
else
    echo "INFO: Skipping collectstatic (DEBUG is True and DJANGO_COLLECTSTATIC_ON_STARTUP is not 'true')."
    echo "----------------------------------------"
fi


# 5. Iniciar el servidor de aplicación Gunicorn
echo "RUNNING: Starting Gunicorn server..."
echo "INFO: About to execute Gunicorn."
echo "INFO: WSGI application path: myproject_config.wsgi:application" # AJUSTA ESTO
echo "INFO: Binding to 0.0.0.0:8000"
# sleep 10 # Descomenta para depurar si el contenedor se cierra muy rápido

# ¡¡¡ASEGÚRATE DE QUE 'myproject_config' SEA EL NOMBRE CORRECTO DE LA CARPETA!!!
# (la carpeta que contiene tu wsgi.py, creada por "django-admin startproject myproject_config .")
# Si tu manage.py está en /app/manage.py y tu wsgi.py está en /app/myproject_config/wsgi.py,
# entonces Gunicorn necesita poder encontrar 'myproject_config.wsgi'.
# El WORKDIR /app se añade al PYTHONPATH por defecto.
exec gunicorn myproject_config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --log-level ${GUNICORN_LOG_LEVEL:-debug} \
    --access-logfile '-' \
    --error-logfile '-'

# Si el script llega aquí, significa que 'exec gunicorn' no reemplazó el proceso del shell.
echo "CRITICAL ERROR: Gunicorn exec command did not take over. Gunicorn likely failed to start or is misconfigured."
echo "Check Gunicorn installation and WSGI application path."
exit 1