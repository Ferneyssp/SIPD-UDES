#!/bin/sh
# Arranque del backend en Docker: espera PostgreSQL, migra, prepara modelos y datos demo.
set -e

echo "Esperando a PostgreSQL en ${DB_HOST:-postgres}:${DB_PORT:-5432}..."
python - <<'PY'
import os, time, psycopg
for attempt in range(60):
    try:
        psycopg.connect(
            dbname=os.environ.get("DB_NAME", "sipd"), user=os.environ.get("DB_USER", "sipd"),
            password=os.environ.get("DB_PASSWORD", ""), host=os.environ.get("DB_HOST", "postgres"),
            port=os.environ.get("DB_PORT", "5432"), connect_timeout=3,
        ).close()
        break
    except psycopg.OperationalError:
        time.sleep(2)
else:
    raise SystemExit("PostgreSQL no respondió a tiempo.")
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null

if [ ! -f "${ML_MODELS_DIR}/model.joblib" ]; then
  echo "No hay modelo entrenado: se entrena con el dataset SINTÉTICO de ejemplo."
  python /app/ml/scripts/train.py
fi
python manage.py sync_models

if [ "${SEED_DEMO:-false}" = "true" ]; then
  if python manage.py shell -c "from students.models import Student; import sys; sys.exit(0 if Student.objects.exists() else 1)"; then
    echo "La base de datos ya tiene estudiantes: no se cargan datos demo."
  else
    python manage.py seed_demo
  fi
fi

exec "$@"
