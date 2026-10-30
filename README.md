# SIPD — Sistema de Predicción y Seguimiento del Riesgo de Deserción Estudiantil

MVP académico (proyecto de grado) que estima el **riesgo de deserción** de estudiantes mediante modelos de
Machine Learning y apoya el **seguimiento** por parte de coordinadores académicos y administradores.

> El sistema presenta **estimaciones probabilísticas** ("riesgo estimado", "nivel de riesgo",
> "estudiante identificado para seguimiento"). **Nunca** afirma que un estudiante vaya a desertar.

```
Frontend (React + Vite) ──REST/JWT──▶ Backend (Django + DRF) ──▶ PostgreSQL
                                              │
                                              ▼
                                  Inferencia ML (sipd_ml, modelo .joblib ya entrenado)
                                              ▲
      Entrenamiento: offline (ml/scripts, notebooks) o desde la web (Admin, en segundo plano)
```

Menú agrupado por tarea: **Analizar** (Inicio · Estudiantes · Predicciones (Admin) · Historial · Reportes) ·
**Atender** (Alertas · Seguimiento) · **Administrar** (Carga de datos · Reentrenamiento · Usuarios; Admin) ·
**Cuenta** (Notificaciones · Perfil). **No existe** módulo "Dashboard" ni "Estadísticas": el resumen vive en **Inicio**.
Ver [§21](#21-referencia-civitas-learning-y-cambios-de-la-versión) para la relación con *Institutional Impact Platform*.

---

## Contenido

1. [Requisitos](#1-requisitos)
2. [Instalación](#2-instalación)
3. [Configuración de PostgreSQL](#3-configuración-de-postgresql)
4. [Variables de entorno](#4-variables-de-entorno)
5. [Migraciones](#5-migraciones)
6. [Creación de superusuario](#6-creación-de-superusuario)
7. [Ejecución del backend](#7-ejecución-del-backend)
8. [Ejecución del frontend](#8-ejecución-del-frontend)
9. [Instalación de dependencias](#9-instalación-de-dependencias)
10. [Modelos de Machine Learning](#10-modelos-de-machine-learning)
11. [Carga de datos](#11-carga-de-datos)
12. [Pruebas](#12-pruebas)
13. [Docker](#13-docker)
14. [Estructura del proyecto](#14-estructura-del-proyecto)
15. [Roles y permisos](#15-roles-y-permisos)
16. [Privacidad y seguridad](#16-privacidad-y-seguridad)
17. [Despliegue en Vercel](#17-despliegue-en-vercel)
18. [Reentrenamiento desde la web](#18-reentrenamiento-desde-la-web)
19. [Notificaciones](#19-notificaciones)
20. [Reportes y exportación](#20-reportes-y-exportación)
21. [Referencia Civitas Learning y cambios de la versión](#21-referencia-civitas-learning-y-cambios-de-la-versión)
22. [Recuperación de contraseña por correo (Gmail)](#22-recuperación-de-contraseña-por-correo-gmail)
23. [Entrenador en GitHub Actions](#23-entrenador-en-github-actions)

---

## 1. Requisitos

| Herramienta | Versión probada |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ (probado con 22) |
| PostgreSQL | 14+ (probado con 16) |
| Docker + Docker Compose (opcional) | 24+ |

## 2. Instalación

```bash
git clone <repositorio> sipd && cd sipd

# Backend + ML
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt   # incluye las dependencias de ML

# Frontend
cd frontend && npm install && cd ..
```

## 3. Configuración de PostgreSQL

```sql
-- psql -U postgres
CREATE USER sipd WITH PASSWORD 'una_contraseña_segura' CREATEDB;  -- CREATEDB es necesario para las pruebas
CREATE DATABASE sipd OWNER sipd;
```

## 4. Variables de entorno

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Complete en `backend/.env` como mínimo `SECRET_KEY` y `DB_PASSWORD`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"   # genera SECRET_KEY
```

| Variable | Descripción |
|---|---|
| `DEBUG` | `True` sólo en desarrollo |
| `SECRET_KEY` | Clave de Django (obligatoria si `DEBUG=False`) |
| `DATABASE_URL` | Alternativa a `DB_*` (p. ej. `postgres://sipd:clave@localhost:5432/sipd`) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Conexión PostgreSQL |
| `JWT_ACCESS_TOKEN_LIFETIME`, `JWT_REFRESH_TOKEN_LIFETIME` | Vigencia de tokens (minutos) |
| `CORS_ALLOWED_ORIGINS` | Orígenes permitidos del frontend |
| `RISK_LOW_THRESHOLD`, `RISK_MEDIUM_THRESHOLD` | **Umbrales de riesgo** (0.30 / 0.60 por defecto) |
| `ALERT_RISE_THRESHOLD` | Aumento de probabilidad que genera alerta temprana (0.15 = 15 puntos; parámetro de diseño, no validado) |
| `SECURE_COOKIES` | Cookies `Secure` (por defecto activas si `DEBUG=False`) |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | HTTPS obligatorio y HSTS en producción (por defecto: redirección activa y HSTS de 1 año si `DEBUG=False`) |
| `TRUSTED_PROXY_COUNT` | Proxies inversos de confianza: sólo entonces se usa `X-Forwarded-For` para la IP (0 por defecto; 1 en Vercel y en Docker con Nginx) |
| `GPA_MIN`, `GPA_MAX` | Escala de promedio institucional (0–5) |
| `UPLOAD_MAX_BYTES`, `UPLOAD_MAX_ROWS` | Límites de carga CSV |
| `ML_MODELS_DIR` | Carpeta de modelos (por defecto `backend/ml_models`) |
| `ML_TRAINING_EXECUTOR` | Reentrenamiento web: `thread` (defecto), `worker`, `github` (GitHub Actions, [§23](#23-entrenador-en-github-actions)) o `disabled` (defecto en Vercel). Ver [§18](#18-reentrenamiento-desde-la-web) |
| `ML_TRAINING_STALE_MINUTES` | Minutos sin latido para dar por interrumpida una ejecución (10) |
| `ML_TRAINING_MIN_ROWS`, `ML_TRAINING_MIN_CLASS_ROWS` | Mínimos técnicos del dataset de entrenamiento (100 / 10 por clase) |
| `ML_ACCEPTANCE_MIN_F1`, `_RECALL`, `_PRECISION`, `_ROC_AUC` | Mínimos **opcionales** de aceptación (vacíos = sin mínimo) |
| `INSTITUTION_NAME` | Nombre institucional de los PDF |
| `REPORT_EXPORT_MAX_ROWS` | Límite de filas por exportación CSV (50000) |
| `DEMO_PASSWORD` | Contraseña de los usuarios demo creados por `seed_demo` |
| `VITE_API_URL` (frontend) | URL de la API (`/api` usa el proxy de Vite) |
| `VITE_APP_NAME`, `VITE_INSTITUTION_NAME` (frontend) | Identidad institucional mostrada |

**Umbrales de riesgo.** Se definen únicamente en `backend/config/risk.py` (leídos de las variables anteriores).
El frontend los consulta en `GET /api/config/`; no están codificados en React.

```
0% ───────── 30% ───────── 60% ───────── 100%
      Bajo          Medio          Alto
```

## 5. Migraciones

```bash
cd backend
python manage.py migrate
```

## 6. Creación de superusuario

```bash
python manage.py createsuperuser        # queda con rol Administrador
```

Datos de demostración **sintéticos** (programas, periodos 2025-1…2026-2, 240 estudiantes E001…E240,
predicciones históricas, seguimientos y 4 usuarios de prueba):

```bash
python manage.py seed_demo              # --students 400 --reset para regenerar
```

| Usuario | Rol | Ámbito |
|---|---|---|
| `admin` | Administrador | Todos los estudiantes |
| `coordinador` | Coordinador académico | Ing. de Sistemas, Ing. de Software |
| `coordinador2` | Coordinador académico | Ing. Civil, Ing. Industrial, Ing. Electrónica |

La contraseña es el valor de `DEMO_PASSWORD`. **No existe una contraseña por defecto**: si la variable está vacía,
`seed_demo` genera una aleatoria y la muestra **una sola vez** en la salida del comando. El usuario `admin` tiene
acceso a `/admin` (`is_staff`) pero no es superusuario. **No use estas cuentas en un entorno real.**

## 7. Ejecución del backend

```bash
cd backend
python manage.py runserver          # http://localhost:8000/api/
```

Comandos útiles:

| Comando | Qué hace |
|---|---|
| `python manage.py sync_models` | Registra en BD los modelos de `backend/ml_models/` |
| `python manage.py run_predictions --period 2026-2` | Genera predicciones de un periodo |
| `python manage.py seed_demo` | Carga datos sintéticos de demostración |
| `python manage.py process_training_runs` | Ejecuta reentrenamientos pendientes (sólo con `ML_TRAINING_EXECUTOR=worker`; `--once` para una pasada) |
| `python manage.py prune_model_dirs` | Borra de `ML_MODELS_DIR` las carpetas de versiones rechazadas (`--dry-run` para sólo listarlas) |

## 8. Ejecución del frontend

```bash
cd frontend
npm run dev                          # http://localhost:5173
```

Vite redirige `/api` hacia `VITE_PROXY_TARGET` (por defecto `http://localhost:8000`). Compilación: `npm run build`.

## 9. Instalación de dependencias

| Parte | Archivo | Comando |
|---|---|---|
| Backend | `backend/requirements.txt` | `pip install -r backend/requirements.txt` |
| Notebooks | `ml/requirements-notebooks.txt` | `pip install -r ml/requirements-notebooks.txt` |
| Frontend | `frontend/package.json` | `npm install` |

## 10. Modelos de Machine Learning

El pipeline vive en `ml/` y está **separado** del backend y del frontend:

```
ML Training (ml/scripts/train.py) → Saved Model (backend/ml_models/*.joblib) → Inference Service (sipd_ml.inference)
      → Django API (backend/ml/services.py) → React
```

```bash
python ml/scripts/generate_synthetic_data.py      # dataset SINTÉTICO → data/sample/
python ml/scripts/train.py                        # entrena LR, RF y XGBoost; evalúa; guarda
python ml/scripts/train.py --select-by recall     # criterio: f1 | recall | roc_auc | precision
python ml/scripts/train.py --force-model random_forest
python ml/scripts/train.py --data ruta/datos_institucionales.csv
python ml/scripts/evaluate.py                     # evalúa el modelo guardado
python ml/scripts/validate.py --data data/private/synthetic_students.csv --label C500 --figures
                                                  # validación cruzada 5x5, línea base, calibración, umbrales
                                                  # (resultados en ml/results/; --figures requiere matplotlib)
cd backend && python manage.py sync_models        # registra versiones; activa la seleccionada
```

- **Preprocesamiento**: `ColumnTransformer` (imputación de faltantes, escalamiento, one-hot) ajustado sólo
  con datos de entrenamiento y guardado como `preprocessor.joblib`; en inferencia se usa el **mismo objeto**.
- **Artefactos**: `backend/ml_models/<algoritmo>_<versión>/{model.joblib, preprocessor.joblib, metadata.json}` y una
  copia del seleccionado en `backend/ml_models/`.
- **Selección**: no se asume un modelo ganador; se ordena por la métrica elegida (F1 por defecto), con ROC-AUC y
  Recall como desempate. Accuracy se reporta pero **no** se usa como criterio único. El administrador puede
  activar otra versión desde *Predicciones → Modelos disponibles*.
- **Métricas**: se calculan con el umbral `CLASSIFICATION_THRESHOLD = 0.30` (inicio del nivel Medio); cámbielo con `--threshold`.
- **Probabilidades calibradas**: los modelos se entrenan sin reponderar clases para que la probabilidad sea
  interpretable frente a los umbrales.
- **Explicabilidad**: cada predicción guarda las variables con mayor peso (coeficientes para Regresión Logística,
  contribuciones SHAP nativas de XGBoost, importancia ponderada en Random Forest). Se presentan como
  *"variables asociadas al resultado"*, sin afirmar causalidad.
- **Nunca se reentrena dentro de una petición**: las predicciones sólo cargan artefactos y los mantienen en memoria;
  el reentrenamiento desde la web corre en segundo plano ([§18](#18-reentrenamiento-desde-la-web)).
- **Versiones inmutables**: cada versión se escribe en una carpeta temporal oculta y se renombra al terminar
  (nunca queda una versión a medio escribir); una carpeta existente no se sobrescribe. Cada versión registra
  las sumas SHA-256 de sus artefactos.

> ⚠️ Las métricas incluidas se obtuvieron con **datos sintéticos** y sirven sólo para pruebas técnicas.
> No son resultados académicos. Reemplace el dataset por datos institucionales anonimizados para el proyecto.

Notebooks (`ml/notebooks/`): `01_exploracion`, `02_preprocesamiento`, `03_entrenamiento`, `04_evaluacion`,
`05_guardado_modelo` (se regeneran con `python ml/scripts/build_notebooks.py`).

Variables del modelo (definidas en `backend/sipd_ml/config.py`): programa, semestre, promedio, promedio anterior,
variación del promedio, créditos matriculados/aprobados/reprobados, asignaturas perdidas, tasa de aprobación,
asistencia, asignaturas repetidas y variables opcionales de encuesta (trabaja, estrato, dificultad financiera,
motivación). El riesgo previo se almacena en el historial pero **no** es variable de entrada, para evitar que el
modelo se retroalimente con sus propias salidas.

## 11. Carga de datos

Menú **Carga de datos** (Administrador): 1) seleccionar CSV, 2) validar, 3) revisar resumen y errores,
4) confirmar (opcionalmente generando predicciones). La validación **no modifica** datos; las filas con
errores **nunca** se cargan en silencio y se reportan con fila, columna y motivo. **Sólo se guardan las cargas
validadas y procesadas**: un archivo rechazado muestra su informe pero no se conserva, y una carga validada que se
cancela ("Cancelar / nueva carga") se descarta. Lo mismo aplica a los datasets de entrenamiento rechazados.

- Plantilla: botón *Descargar plantilla* o `GET /api/uploads/template/`.
- Ejemplos sintéticos: `data/sample/carga_ejemplo_valida.csv` y `data/sample/carga_ejemplo_con_errores.csv`
  (`python ml/scripts/generate_sample_uploads.py`).
- Columnas obligatorias: `student_code, program_code, academic_period, semester, gpa, credits_enrolled,
  credits_approved, credits_failed, failed_subjects, attendance_percentage, academic_status`.
- Opcionales: `course_repetitions, works_while_studying, socioeconomic_stratum, financial_difficulty, motivation_level`.
- Validaciones: extensión/tamaño/codificación UTF-8, columnas requeridas, tipos, faltantes, rangos
  (asistencia 0–100, promedio `GPA_MIN`–`GPA_MAX`, estrato 1–6…), coherencia de créditos, duplicados, formato de
  identificador (`E001`) y periodo (`AAAA-1`/`AAAA-2`), programa registrado.

## 12. Pruebas

```bash
cd backend && python manage.py test        # 110 pruebas (PostgreSQL con permiso CREATEDB)
cd ml && python -m pytest                  # 7 pruebas del pipeline ML
cd frontend && npm test                    # 39 pruebas (Vitest + Testing Library)
```

Sin PostgreSQL local, la batería del backend también corre con SQLite (así se verificó esta versión):
`DATABASE_URL=sqlite:///ruta/temporal.sqlite3 python manage.py test`.

Cobertura: login/JWT/logout, permisos por rol y ámbito, CRUD de estudiantes, predicciones e historial,
umbrales, validación y flujo de carga CSV, seguimiento, carga del modelo, preprocesamiento, predicción,
protección de rutas, Inicio, tabla y filtros de estudiantes, visualización accesible del riesgo; reentrenamiento
(permisos, validación del dataset, entrenamiento real, fallos, concurrencia, ejecuciones interrumpidas, aprobación,
activación, integridad de artefactos, recuperación), notificaciones (aislamiento por usuario, lectura, filtros,
duplicados) y reportes (cifras, ámbito, CSV con protección de fórmulas, PDF, permisos).

## 13. Docker

```bash
cp .env.example .env        # complete SECRET_KEY, DB_PASSWORD (y DEMO_PASSWORD)
docker compose up --build
```

- Aplicación: <http://localhost:5173> · API: <http://localhost:8000/api/>
- Servicios: `postgres`, `backend` (Gunicorn), `frontend` (Nginx con proxy `/api`).
- Al iniciar, el backend espera a PostgreSQL, migra, entrena el modelo si no existe, sincroniza versiones y,
  sólo con `SEED_DEMO=true` (por defecto `false`), carga los datos sintéticos si la base está vacía.
- Docker local se sirve por http: `docker-compose.yml` desactiva la redirección HTTPS y HSTS, declara a Nginx como
  único proxy de confianza (`TRUSTED_PROXY_COUNT=1`) y publica el puerto 8000 sólo en `127.0.0.1`. En un servidor
  real detrás de HTTPS, elimine `SECURE_SSL_REDIRECT` y `SECURE_HSTS_SECONDS` del archivo.
- No se añadió un servicio separado de ML: la inferencia es liviana y se ejecuta dentro del backend. El
  reentrenamiento web corre en un hilo en segundo plano del backend y guarda las versiones en el volumen
  `ml_models` (persisten entre reinicios y reconstrucciones).

## 14. Estructura del proyecto

```
├── backend/            Django + DRF  (+ notifications/, reports/)
│   ├── config/         settings, urls, risk.py (umbrales), manejo de errores
│   ├── users/          usuarios, roles, autenticación JWT, permisos
│   ├── academic/       programas, periodos, registros académicos
│   ├── students/       estudiantes, ámbito por rol, seed_demo
│   ├── predictions/    predicciones, historial, resumen de Inicio
│   ├── ml/             versiones de modelo, inferencia, reentrenamiento web (training_service.py)
│   ├── notifications/  notificaciones internas persistentes
│   ├── reports/        reportes, exportación CSV y PDF
│   ├── sipd_ml/        pipeline ML: preprocesamiento, entrenamiento, evaluación, inferencia
│   ├── ml_models/      artefactos .joblib + metadata.json
│   ├── uploads/        carga y validación CSV
│   ├── followups/      seguimiento / intervenciones
│   └── audit/          registro interno de acciones (sin pantalla ni API)
├── frontend/           React + Vite
│   └── src/{components,pages,layouts,services,hooks,context,utils,config,styles,test}
├── ml/                 entrenamiento offline (importa backend/sipd_ml)
│   ├── scripts/        train, evaluate, generate_* , build_notebooks
│   ├── notebooks/      01–05
│   └── tests/
├── data/sample/        datos SINTÉTICOS
├── docs/ARQUITECTURA.md
└── docker-compose.yml
```

Detalles de arquitectura, modelo de datos y API: [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## 15. Roles y permisos

Dos roles (el rol Profesor se eliminó; la migración `users.0002` convirtió a esos usuarios en coordinadores con
los mismos programas):

| Acción | Administrador | Coordinador académico |
|---|:-:|:-:|
| Inicio, estudiantes, historial, ficha | ✅ todos los estudiantes | ✅ sólo los de sus programas asignados (sin programas: ninguno) |
| Módulo Predicciones | ✅ | — |
| Alertas tempranas (consulta) y su gestión mediante el seguimiento | ✅ | ✅ (sus programas) |
| Registrar / editar seguimiento | ✅ (eligiendo un coordinador como responsable) | ✅ (sus programas) |
| Ser responsable de un seguimiento o alerta | — nunca | ✅ (coordinador del programa del estudiante) |
| Editar datos de estudiantes | — (sólo con la carga CSV) | — |
| Ejecutar predicciones, activar modelos, reentrenar | ✅ | — |
| Reportes agregados y exportación del listado (CSV) | ✅ | ✅ (su ámbito) |
| Listado individual de riesgo (CSV) | ✅ | — |
| Carga de datos | ✅ | — |
| Gestión de usuarios | ✅ | Sólo con permiso explícito y limitada (ver abajo) |

**Gestión de usuarios sin escalada de privilegios.** Sólo un Administrador crea o modifica administradores,
asigna el rol Administrador o el permiso de gestionar usuarios y restablece contraseñas de administradores. Nadie
cambia su propio rol, permisos ni estado. Un coordinador con permiso de gestión sólo ve y modifica coordinadores
sin ese permiso cuyos programas estén dentro de los suyos, y sólo asigna sus propios programas.

**Ficha de sólo lectura.** Los datos de los estudiantes no se editan desde la interfaz ni por la API
(`/api/students/` es de sólo lectura): se crean y actualizan únicamente con la carga CSV validada, que deja
trazabilidad por registro.

Los usuarios no se eliminan físicamente: se desactivan para conservar la trazabilidad (y se revocan sus sesiones).

## 16. Privacidad y seguridad

- Estudiantes identificados sólo con códigos seudonimizados (`E001`); no se almacenan nombres ni documentos.
- Datos de desarrollo 100 % sintéticos; `.gitignore` excluye `data/raw/` y `data/private/`.
- Contraseñas con hash PBKDF2 y validadores de robustez; JWT con rotación y lista negra de refresh tokens.
- **Sesión:** el refresh token viaja sólo en una cookie `HttpOnly`, `Secure`, `SameSite=Strict` limitada a
  `/api/auth/` (JavaScript no puede leerlo); el access token (30 min) vive sólo en memoria y se renueva con la
  cookie, también al recargar la página. Refresh y logout exigen la cabecera `X-Requested-With` (anti-CSRF).
  "Recordar sesión" decide si la cookie es persistente o de sesión.
- **Cambio o restablecimiento de contraseña y desactivación:** se revocan todos los refresh tokens del usuario y
  se rechazan los access tokens emitidos antes del cambio.
- **Producción (`DEBUG=False`):** redirección a HTTPS, HSTS y cookies seguras por defecto.
- **IP de auditoría y límite de intentos:** `X-Forwarded-For` sólo se considera con `TRUSTED_PROXY_COUNT` > 0.
- **Registro interno de acciones:** inicios de sesión, consultas a fichas, gestión de alertas, cambios de modelo y
  exportaciones quedan en la tabla `AuditLog` (consultable desde `/admin`). No hay módulo de auditoría en la interfaz.
- Límite de intentos de login (10/min por defecto), CORS restringido, cabeceras de seguridad, validación de
  archivos (extensión, tamaño, contenido binario, UTF-8, número de filas).
- Auditoría de inicios de sesión, cargas, predicciones, cambios de usuarios y seguimientos, sin datos
  sensibles en los registros.
- Secretos sólo en variables de entorno; `.env` excluido de Git.

## 17. Despliegue en Vercel

El repositorio se despliega como **un proyecto de Vercel con servicios** (`services` en `vercel.json`),
con un único dominio:

| Servicio | Carpeta | Ruta pública | Qué es |
|---|---|---|---|
| `backend` | `backend/` | `/api/*`, `/admin/*`, `/static/*` | Django (preset `django`, función Python) |
| `frontend` | `frontend/` | todo lo demás (`/*`) | React + Vite (estático, con *fallback* SPA a `index.html`) |

El ML **no es un servicio**: el paquete `backend/sipd_ml` y los artefactos `backend/ml_models` viven dentro
del servicio `backend` y Django los importa en el mismo proceso (el modelo se carga una vez por instancia y
nunca se reentrena en una petición). Están dentro de `backend/` porque Vercel construye cada servicio a partir
de su carpeta `root` y no documenta que se incluyan carpetas hermanas como `ml/`. No hay *bindings*: el
navegador llama a `/api` en el mismo dominio, por lo que tampoco hace falta CORS.

`/admin` exige iniciar sesión con un usuario `is_staff` (sólo el rol Administrador). `/static` sirve los
archivos del admin de Django (Vercel ejecuta `collectstatic` en el build del servicio `backend`).

| Archivo | Función |
|---|---|
| `vercel.json` | Define los servicios y las reescrituras públicas |
| `backend/config/vercel.py` | En cada arranque en frío: migraciones, registro de modelos ML y (opcional) datos demo |
| `backend/requirements.txt` | Dependencias autocontenidas (XGBoost sólo-CPU, scikit-learn fijo en 1.9.0) |
| `frontend/.env.production` | Nombre de la app e institución usados en el build |

### Pasos

1. Suba el repositorio a GitHub (incluida la carpeta `backend/ml_models/` con los modelos entrenados).
2. En [vercel.com/new](https://vercel.com/new) importe el repositorio con:
   - **Root Directory**: la raíz del repositorio (`./`), no `backend/` ni `frontend/`.
   - **Framework Preset**: **Services**. Vercel sólo usa el bloque `services` de `vercel.json` con este preset;
     con otro preset lo ignora.
   - **Servicios**: sólo `backend` (Django, carpeta `backend/`) y `frontend` (Vite, carpeta `frontend/`). Si la
     pantalla propone un servicio `ml`, quítelo: `ml/` es entrenamiento offline y no se despliega.
   - **Environment Variables**: agregue ya `SECRET_KEY` (y las demás del paso 4); sin ella el build del backend
     falla.
   - Rutas, *build commands* y *output directories*: no los configure en la pantalla; salen de `vercel.json`.
3. En el proyecto, pestaña **Storage**, cree/conecte una base **Postgres (Neon)**. Esto define `DATABASE_URL`
   automáticamente.
4. En **Settings → Environment Variables** agregue:

   | Variable | Valor |
   |---|---|
   | `SECRET_KEY` | Obligatoria. `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `SEED_DEMO` | `true` para crear usuarios y datos **sintéticos** de demostración en el primer arranque |
   | `DEMO_PASSWORD` | Contraseña de los usuarios demo (`admin`, `coordinador`, `coordinador2`). Obligatoria si `SEED_DEMO=true` |
   | `ALLOWED_HOSTS` | Opcional: dominios propios (los `*.vercel.app` ya están permitidos) |

   Opcionales: `RISK_LOW_THRESHOLD`, `RISK_MEDIUM_THRESHOLD`, `JWT_ACCESS_TOKEN_LIFETIME`,
   `JWT_REFRESH_TOKEN_LIFETIME`, `SEED_DEMO_STUDENTS` (120 por defecto), `AUTO_MIGRATE=false` para no migrar al arrancar.
5. **Redeploy** (pestaña *Deployments*) para que tome las variables. Cada `git push` a `main` vuelve a desplegar.

Para probar todo junto en local: `vercel dev`.

Si no usa datos demo, cree el primer administrador desde su equipo apuntando a la base de Vercel:

```bash
cd backend
DATABASE_URL="<url de Neon>" SECRET_KEY=x python manage.py createsuperuser
```

### Limitaciones en Vercel

- La carga de CSV admite hasta **4 MB** (límite de Vercel de 4,5 MB por petición). El archivo se guarda en la
  base de datos, no en disco (el disco de las funciones es temporal).
- El **reentrenamiento no se ejecuta dentro de Vercel**: el disco de las funciones es efímero (las versiones nuevas
  se perderían) y cada función tiene un tiempo máximo. Por defecto está desactivado (`ML_TRAINING_EXECUTOR=disabled`);
  con `ML_TRAINING_EXECUTOR=github` se entrena en GitHub Actions y se publica con un commit
  ([§23](#23-entrenador-en-github-actions)). Reportes y notificaciones sí funcionan en Vercel.
- **El archivo `backend/.env` no se despliega** (está en `.gitignore` y `.vercelignore`) y **la base de datos de Vercel
  es otra** (Neon), no la local. Las contraseñas o correos cambiados en local no llegan a producción: cámbielos en la
  aplicación desplegada (Perfil, Usuarios o *¿Olvidó su contraseña?*). Las variables (`EMAIL_HOST_USER`,
  `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, etc.) se definen en *Vercel → Settings → Environment Variables* y
  sólo se aplican **después de un nuevo despliegue**. Sin `EMAIL_HOST_USER` en Vercel no se envía el correo de
  recuperación (queda un error en los logs); `FRONTEND_URL` toma por defecto el dominio de producción del proyecto.
- Los modelos se cargan con la versión fijada de scikit-learn (1.9.0, la usada al entrenar). Si reentrena con
  otra versión, actualice `backend/requirements.txt`.
- Supuesto no verificado en Vercel: la detección automática del preset `django` (lee `manage.py` y
  `WSGI_APPLICATION`) y la ejecución de `collectstatic`. Se probó localmente el build de producción, no un
  despliegue real.
- La primera petición tras un periodo de inactividad tarda más (arranque en frío: carga de Django y del modelo).

## 18. Reentrenamiento desde la web

Menú **Reentrenamiento** (sólo Administrador; los endpoints también exigen el rol en el backend).

1. **Datos**: cargar un CSV. Se valida extensión, tamaño, UTF-8,
   columnas obligatorias (las de `sipd_ml/config.py`: variables del modelo sin las derivadas + `dropout`), tipos,
   rangos (los mismos del validador de cargas), valores faltantes, etiquetas 0/1, coherencia de créditos y
   mínimos técnicos (100 registros y 10 por clase). Las variables de encuesta son opcionales (se imputan).
   El archivo validado se guarda en BD con su SHA-256 y se entrena exactamente con ese contenido.
2. **Configuración**: algoritmos del procedimiento (Regresión Logística, Random Forest y XGBoost si está
   instalado). El candidato recomendado es el de mejor F1-score; la partición estratificada 75/25, la semilla 42 y
   el umbral de evaluación 0,30 son fijos para conservar la comparabilidad. El formulario de nuevo
   reentrenamiento está al inicio de la página.
3. **Confirmación** con resumen (datos, registros, algoritmos, advertencias, consecuencias). Una restricción en
   BD impide dos entrenamientos simultáneos y un dataset ya entrenado no se reutiliza por accidente.
4. **Ejecución** en segundo plano con `sipd_ml.pipeline.run_training_pipeline` (el mismo de `train.py`). Estados
   reales: Pendiente → Validando datos → Preparando datos → Entrenando (n de N) → Evaluando → Registrando →
   Completado / Fallido / Cancelado (sólo antes de empezar). La interfaz consulta el estado cada 3 s, muestra
   etapa y tiempo transcurrido (sin porcentajes inventados) y recupera el estado al volver a la página.
5. **Evaluación**: al terminar, cada modelo se muestra como una *flashcard*: el frente compara sus métricas de
   **prueba** con las del modelo activo (con la diferencia) e incluye las acciones; al voltearla se ven la matriz de
   confusión, los criterios de aceptación y las advertencias de comparabilidad.
6. **Aprobación y activación** separadas: las versiones nuevas quedan *pendientes* y sólo se ven en su
   entrenamiento. **Sólo se guardan los modelos aprobados**: aprobar la deja disponible (si cumple los criterios);
   rechazar la elimina por completo (artefactos y registro); al iniciar un nuevo entrenamiento se descartan las
   versiones de entrenamientos anteriores que quedaron sin decidir. Activar es siempre una acción explícita. Las versiones entrenadas offline y registradas con
   `sync_models` figuran como "Registrado sin flujo de aprobación" y pueden activarse como antes.
7. **Recuperación**: cualquier versión que haya estado activa puede volver a activarse. Las versiones aprobadas o
   que estuvieron activas nunca se borran.

**Criterios de aceptación.** Técnicos (obligatorios): métricas calculadas, ambas clases en el conjunto de prueba,
mismas variables que el servicio de predicción y artefactos íntegros (SHA-256) que cargan y predicen. El proyecto
**no define umbrales de rendimiento aprobados**, así que los mínimos por métrica son opcionales
(`ML_ACCEPTANCE_MIN_*`) y deben fijarlos la institución; sin ellos, la decisión es del administrador.

**Activación segura.** Se verifica ubicación (dentro de `ML_MODELS_DIR`), sumas SHA-256, metadatos y una
predicción de prueba **antes** de cambiar la referencia en BD (transacción con bloqueo). Si algo falla, sigue
activo el modelo anterior. Las predicciones en curso usan el modelo que ya tenían cargado.

**Ejecución en segundo plano (`ML_TRAINING_EXECUTOR`).**

| Valor | Uso | Limitaciones |
|---|---|---|
| `thread` (defecto) | Local y Docker: hilo del proceso web | Si el proceso se reinicia durante el entrenamiento, la ejecución se marca *Fallida* al dejar de recibir latidos (`ML_TRAINING_STALE_MINUTES`) y se puede relanzar; no se activa nada |
| `worker` | La API sólo encola; `python manage.py process_training_runs` ejecuta | Requiere mantener ese proceso con el mismo `ML_MODELS_DIR` y la misma BD |
| `github` | Vercel: la API encola y lanza el flujo de GitHub Actions, que entrena y publica los artefactos con un commit ([§23](#23-entrenador-en-github-actions)) | Tarda unos minutos más (arranque del ejecutor y redespliegue); la aprobación se habilita cuando termina el despliegue |
| `disabled` | Defecto en Vercel | No se puede reentrenar desde la web |

No se agregaron Celery ni Redis: el entrenamiento es esporádico, de un único administrador y dura segundos o
minutos; un registro persistente con latido y una restricción de unicidad cubren estado, historial y concurrencia.

## 19. Notificaciones

Campana en la barra superior (contador de no leídas, consulta cada 60 s y al volver a la ventana) y centro de
notificaciones (**Notificaciones**) con filtros por estado, categoría y tipo, marcar una / todas como leídas y
enlace a la operación. Se guardan en BD, cada usuario sólo ve las suyas y leer no las borra.

| Evento | Destinatarios |
|---|---|
| Inicio, finalización o fallo del reentrenamiento; nueva versión evaluada; aprobación/rechazo; activación; recuperación | Administradores activos |
| Dataset rechazado, columnas ausentes, problemas de formato, datos insuficientes; error al preparar datos | Quien cargó el archivo (errores de preparación: administradores) |
| Carga académica rechazada | Quien la cargó |
| Proceso de predicción por lotes (o desde una carga) finalizado | Quien lo ejecutó y, sin cifras, los usuarios con acceso a esos programas |

Se crean al confirmarse la transacción, con clave de deduplicación, sin trazas internas ni datos personales.
No hay correo electrónico en esta versión. Los reportes se generan al instante, por lo que no existen
notificaciones de "reporte disponible".

## 20. Reportes y exportación

Menú **Reportes**: reporte de **riesgo estudiantil** (todos los roles, dentro de su ámbito): estudiantes analizados, distribución y porcentaje
  por nivel, por programa y por semestre, versión(es) del modelo usadas; filtros por periodo, programa,
  semestre y fechas. Fuente: predicciones **vigentes** almacenadas. El listado individual (CSV, códigos
  seudonimizados, sin variables socioeconómicas) es sólo para el Administrador. Las métricas de los modelos se
  consultan en Reentrenamiento y en Predicciones (Administrador).

**PDF** (reportlab): título, filtros, resumen ejecutivo, tablas, gráfico de barras, fuente, versión del modelo,
advertencias y "Página X de Y". **CSV**: UTF-8 con BOM, mismos filtros y cálculos que la pantalla, celdas vacías
para valores nulos, protección contra fórmulas (`=`, `+`, `-`, `@`) y límite `REPORT_EXPORT_MAX_ROWS`. Cada
exportación queda en el registro interno de acciones. Sin datos, el reporte lo indica en lugar de rellenarse.

## 21. Referencia Civitas Learning y cambios de la versión

Tomando como referencia la investigación sobre *Institutional Impact Platform* (Civitas Learning), se adoptó su
cadena **dato → predicción con nivel y cambio → lista priorizada → ficha con factores → acción registrada**, sin
copiar su escala ni cambiar el modelo, los umbrales (0,30 / 0,60) ni el sentido del puntaje (alto = riesgo):

| Civitas (documentado) | SIPD |
|---|---|
| Cambio semanal de la predicción como dato y filtro | **Cambio frente a la predicción vigente del periodo anterior** (puntos porcentuales) en listado, ficha, Inicio y alertas; filtro *Tendencia* y orden *Mayor aumento* |
| Lista de trabajo priorizada y filtros avanzados | Listado ordenado por defecto de mayor a menor riesgo, filtros como etiquetas removibles, exportación CSV del listado filtrado |
| Ficha con *Inspiration* / *Intervention* | Factores separados en "asociadas a mayor riesgo" y "a menor riesgo"; icono ℹ con los rangos vigentes; leyenda "estimación, no certeza" |
| Alertas con responsable, comentario y resolución | **Alertas tempranas** automáticas (nivel Alto o aumento ≥ `ALERT_RISE_THRESHOLD`), una por estudiante y periodo, gestionadas **con el seguimiento del estudiante** ("Gestionar seguimiento" abre el formulario de intervención): al registrarlo la alerta pasa a *En atención* con el coordinador responsable, y al marcarlo *Atendido* o *Cerrado* la alerta se cierra con su observación; aviso agregado a los coordinadores del programa |
| Buscador en el encabezado | Búsqueda global por código que abre la ficha |
| Menú por tareas (*Connect / Advise / Report*) | Menú agrupado en Analizar / Atender / Administrar / Cuenta |
| Visibilidad por rol y unidad, *fail-closed* | Coordinador limitado a sus programas; sin programas no ve estudiantes |
| No mostrar la predicción al estudiante | Aviso en la gestión de alertas |
| Trazabilidad | Bitácora de consultas a fichas y de la gestión de alertas |

No se implementaron (prioridad media o baja en la investigación, o requieren infraestructura externa): cinco
bandas, citas y calendario, mensajería por correo o SMS y análisis de impacto de iniciativas.

**Inicio.** El filtro *Nivel de riesgo* ofrece Todos (por defecto), Alto, Medio y Bajo, y se aplica a las tarjetas,
los gráficos y la tabla de estudiantes que requieren atención.

**Seguimiento e historial.** *Seguimiento* muestra un registro por estudiante (su último seguimiento, con el estado
actual) y *Editar* lo actualiza. El historial completo de intervenciones se consulta en *Historial* (al buscar un
estudiante) y en la ficha, donde sólo se puede **registrar** un seguimiento nuevo, no editar los anteriores.

**Modelos disponibles (Predicciones).** Una fila por algoritmo (Regresión Logística, Random Forest, XGBoost) con un
selector de versión; las métricas y el botón *Activar* corresponden a la versión elegida.

## 22. Recuperación de contraseña por correo (Gmail)

En el inicio de sesión, **¿Olvidó su contraseña?** pide el correo institucional y envía un enlace para crear una
nueva contraseña. El enlace es válido 30 minutos y de un solo uso; al usarlo se cierran todas las sesiones del
usuario. La respuesta es siempre la misma (no revela qué correos existen) y hay un límite de 5 solicitudes por hora.
Al cambiar la contraseña desde *Perfil*, la sesión se cierra y el inicio de sesión confirma que el cambio se hizo.

**Configurar el envío con Gmail**

1. Cree una cuenta dedicada (por ejemplo `sipd.udes@gmail.com`); evite usar un correo personal.
2. En *Cuenta de Google → Seguridad*, active la **Verificación en dos pasos**.
3. En *Seguridad → Contraseñas de aplicaciones*, cree una para "SIPD". Google muestra 16 caracteres: esa es la
   contraseña que usará el sistema (no la de la cuenta).
4. Defina las variables en `backend/.env` (o en Vercel / el servidor):

   | Variable | Valor |
   |---|---|
   | `EMAIL_HOST_USER` | `sipd.udes@gmail.com` |
   | `EMAIL_HOST_PASSWORD` | la contraseña de aplicación (sin espacios) |
   | `DEFAULT_FROM_EMAIL` | `SIPD UDES <sipd.udes@gmail.com>` |
   | `FRONTEND_URL` | dirección pública de la aplicación (va en el enlace), p. ej. `https://sipd.vercel.app` |
   | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | ya vienen como `smtp.gmail.com`, `587`, `True` |

5. Pruebe el envío: `cd backend && python manage.py sendtestemail su-correo@dominio.com`.

Sin `EMAIL_HOST_USER`, los correos se escriben en la consola del backend (útil en desarrollo). Gmail admite del
orden de 500 destinatarios por día en cuentas personales; si cambia la contraseña de la cuenta de Gmail, la
contraseña de aplicación deja de servir y hay que generar otra.

**Identidad visual.** El escudo de la Universidad de Santander (`frontend/public/escudo-udes.png`) aparece en el
menú, el inicio de sesión, el ícono de la pestaña y el correo de recuperación.

## 23. Entrenador en GitHub Actions

Vercel no puede entrenar (disco efímero y tiempo máximo por función), así que el entrenamiento corre gratis en
GitHub Actions con el flujo [`.github/workflows/train-models.yml`](.github/workflows/train-models.yml):

1. En **Reentrenamiento** el administrador valida el CSV e inicia el entrenamiento. El dataset y la ejecución quedan
   en la base de datos (Neon) y el backend lanza el flujo.
2. El flujo instala las mismas dependencias que el backend (Python 3.12, scikit-learn 1.9.0), ejecuta
   `process_training_runs --once` contra la base de datos de producción y registra las versiones como
   **pendientes de aprobación**. La pantalla muestra el avance real (validación, entrenamiento, evaluación).
3. Publica sólo los artefactos (`backend/ml_models/`) con un commit de `github-actions[bot]`; Vercel redespliega
   (2-3 minutos) y entonces el administrador puede **aprobar** o **rechazar**. Hasta que termina el despliegue, la
   aprobación avisa que faltan los artefactos.
4. Al rechazar, la versión se borra de la base de datos y no vuelve a registrarse; la siguiente ejecución del flujo
   elimina su carpeta del repositorio (`prune_model_dirs`). Sólo se conservan los modelos aprobados.

Los datos de estudiantes se leen en memoria desde la base de datos; **nunca se escriben en el repositorio** (en
`backend/ml_models/` sólo hay `model.joblib`, `preprocessor.joblib` y `metadata.json` con métricas).

**Configuración (una sola vez)**

| Dónde | Variable / secreto | Valor |
|---|---|---|
| GitHub → *Settings → Secrets and variables → Actions* | `DATABASE_URL` (secreto) | Cadena **directa** de Neon (la de `DATABASE_URL_UNPOOLED` en Vercel) |
| GitHub → *Settings → Actions → General* | *Workflow permissions* | *Read and write permissions* (el flujo hace commit de los modelos) |
| Vercel → *Environment Variables* | `ML_TRAINING_EXECUTOR` | `github` |
| Vercel | `GITHUB_TRAINING_REPOSITORY` | `usuario/repositorio`, p. ej. `Ferneyssp/SIPD-UDES` |
| Vercel | `GITHUB_TRAINING_TOKEN` (opcional) | Token *fine-grained* sólo de este repositorio con permiso **Actions: Read and write** |
| Vercel | `GITHUB_TRAINING_WORKFLOW`, `GITHUB_TRAINING_REF` | Opcionales: `train-models.yml` y `main` por defecto |

Sin `GITHUB_TRAINING_TOKEN` el entrenamiento queda en cola y la pantalla indica ejecutarlo a mano: *GitHub →
Actions → Entrenar modelos → Run workflow* (procesa todas las ejecuciones pendientes). Si nadie lo lanza en
`ML_TRAINING_STALE_MINUTES` (30 min con `github`), la ejecución se marca fallida sin tocar el modelo activo.
Después de cambiar variables en Vercel, haga *Redeploy*. En repositorios privados, GitHub Actions incluye
2.000 minutos gratis al mes; un entrenamiento de los tres algoritmos tarda del orden de 3-5 minutos.
