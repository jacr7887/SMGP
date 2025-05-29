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
    echo "CRITICAL ERROR: /app/manage.py not found. Check COPY commands in Containerfile."
    exit 1
fi
echo "INFO: manage.py found at /app/manage.py"

# 1. Aplicar migraciones de la base de datos
echo "RUNNING: Applying database migrations..."
python /app/manage.py migrate --noinput
echo "COMPLETED: Migrations (or no_input if already up-to-date)."
echo "----------------------------------------"

# 2. Crear/Asegurar el superusuario (usará las variables de entorno)
echo "RUNNING: Ensuring superuser exists..."
python /app/manage.py ensure_superuser
echo "COMPLETED: Superuser check/creation."
echo "----------------------------------------"

# 3. Poblar con datos de demostración (seed_db)
echo "INFO: Checking if database needs seeding..."
PYTHON_SHELL_COMMAND="from myapp.models import ContratoIndividual, ContratoColectivo; print(ContratoIndividual.objects.count() + ContratoColectivo.objects.count())"
# Ejecutar el comando de Django y capturar la salida, redirigiendo stderr a /dev/null para suprimir errores si la BD aún no está lista para este comando
NUM_CONTRATOS=$(python /app/manage.py shell --command="$PYTHON_SHELL_COMMAND" 2>/dev/null || echo "0")

# Verificar si NUM_CONTRATOS es un número
if ! echo "$NUM_CONTRATOS" | grep -Eq '^[0-9]+$'; then
    echo "WARNING: Could not reliably determine contract count (Output: '$NUM_CONTRATOS'). Assuming 0 for seeding decision."
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
# Si DEBUG=False en tu deploy.env, collectstatic es usualmente necesario.
# WhiteNoise puede servir estáticos directamente si están en la imagen y configurado.
# Si ya los recolectas en el Containerfile (no lo veo arriba), puedes omitir esto.
if [ "$DEBUG" = "False" ] || [ "$DJANGO_COLLECTSTATIC_ON_STARTUP" = "true" ] ; then
    echo "RUNNING: Collecting static files..."
    python /app/manage.py collectstatic --noinput --clear
    echo "COMPLETED: Static files collected."
    echo "----------------------------------------"
else
    echo "INFO: Skipping collectstatic (DEBUG is True and DJANGO_COLLECTSTATIC_ON_STARTUP is not 'true')."
    echo "----------------------------------------"
fi

# 5. Iniciar el servidor de aplicación Gunicorn
echo "RUNNING: Starting Gunicorn server..."
echo "INFO: About to execute Gunicorn."
# Asumiendo que tu proyecto Django se llama 'myproject' y tu wsgi.py está en /app/myproject/wsgi.py
# Esta es la parte MÁS CRÍTICA para que Gunicorn encuentre tu aplicación.
# El WORKDIR /app se añade a PYTHONPATH, así que Gunicorn debería poder importar 'myproject.wsgi'.
echo "INFO: WSGI application path: myproject.wsgi:application" 
echo "INFO: Binding to 0.0.0.0:8000"

exec gunicorn myproject.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --log-level ${GUNICORN_LOG_LEVEL:-debug} \
    --access-logfile '-' \
    --error-logfile '-'

# Si el script llega aquí, significa que 'exec gunicorn' no reemplazó el proceso del shell.
echo "CRITICAL ERROR (ENTRYPOINT): Gunicorn did not take over or exited. Container will stop."
echo "Check Gunicorn installation and WSGI application path (myproject.wsgi:application)."
exit 1