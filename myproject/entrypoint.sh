#!/bin/sh

# Salir inmediatamente si un comando falla
set -e

echo "Running Django MPC Entrypoint Script..."

# 1. Esperar a que la base de datos esté lista (si es un contenedor separado)
# Esta parte es opcional pero muy recomendada si tu BD corre en otro contenedor.
# Necesitarías una herramienta como `wait-for-it.sh` o una lógica similar.
# Ejemplo (si DB_HOST y DB_PORT están definidos como variables de entorno):
# if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
#     echo "Waiting for database at $DB_HOST:$DB_PORT..."
#     # Asume que tienes wait-for-it.sh en tu imagen
#     # ./wait-for-it.sh "$DB_HOST:$DB_PORT" --timeout=30 --strict -- echo "Database is up."
# fi

# 2. Aplicar migraciones de la base de datos
echo "Applying database migrations..."
python manage.py migrate --noinput

# 3. Crear el superusuario (usará las variables de entorno)
echo "Ensuring superuser exists..."
python manage.py ensure_superuser

# 4. Poblar con datos de demostración (seed_db)
# Puedes decidir si esto se ejecuta siempre, o solo bajo una condición (ej. una variable de entorno)
# Para una demo, probablemente quieras que se ejecute siempre si la BD está "vacía"
# o si una variable de entorno específica lo indica.

# Ejemplo: Ejecutar seed solo si una variable de entorno lo pide
# if [ "$DJANGO_SEED_DB_ON_STARTUP" = "true" ]; then
#     echo "Seeding database with demonstration data..."
#     # Ajusta los argumentos de seed_db según la cantidad de datos que quieras para la demo
#     # Podrías tener un conjunto de argumentos "demo" predefinidos.
#     python manage.py seed_db \
#         --users 5 \
#         --intermediarios 3 \
#         --afiliados_ind 10 \
#         --afiliados_col 3 \
#         --tarifas 5 \
#         --contratos_ind 8 \
#         --contratos_col 3 \
#         --facturas 15 \
#         --reclamaciones 5 \
#         --pagos 10 \
#         --igtf_chance 25 \
#         --pago_parcial_chance 30
#     echo "Database seeding complete."
# else
#     echo "Skipping database seeding (DJANGO_SEED_DB_ON_STARTUP not 'true')."
# fi

# Alternativa más simple para la demo: Siempre ejecutar el seed si no hay datos
# (Esto requiere que tu `seed_db` sea idempotente o que el `--clean` funcione bien
# si quieres evitar duplicados masivos en reinicios).
# O una forma de marcar que ya se hizo el seed inicial.
# Una forma simple es chequear si ya existen, por ejemplo, Contratos:
NUM_CONTRATOS=$(python manage.py shell -c "from myapp.models import ContratoIndividual, ContratoColectivo; print(ContratoIndividual.objects.count() + ContratoColectivo.objects.count())")

if [ "$NUM_CONTRATOS" -lt "5" ]; then # Ejecutar seed si hay menos de 5 contratos (ajusta este umbral)
    echo "Número de contratos ($NUM_CONTRATOS) es bajo. Seeding database with demonstration data..."
    python manage.py seed_db \
        --users 10 --intermediarios 5 --afiliados_ind 15 --afiliados_col 5 \
        --tarifas 10 --contratos_ind 12 --contratos_col 5 --facturas 30 \
        --reclamaciones 10 --pagos 20 --igtf_chance 25 --pago_parcial_chance 30
    echo "Database seeding complete."
else
    echo "Database appears to be already seeded (Contratos: $NUM_CONTRATOS). Skipping seed."
fi

# 5. Recolectar archivos estáticos (si no lo haces en el build de la imagen)
# echo "Collecting static files..."
# python manage.py collectstatic --noinput --clear

# 6. Iniciar el servidor de aplicación Gunicorn/uWSGI
# Reemplaza esto con tu comando real para iniciar el servidor de producción
echo "Starting Gunicorn server..."
exec gunicorn myproject.wsgi:application --bind 0.0.0.0:8000 --workers 3
# O si usas Daphne para ASGI:
# exec daphne -b 0.0.0.0 -p 8000 myproject.asgi:application