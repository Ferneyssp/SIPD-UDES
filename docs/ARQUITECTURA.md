# Documentación técnica — SIPD

## 1. Arquitectura

```
                ┌─────────────────────┐
                │  React + Vite (SPA) │  services/api.js → axios + JWT (refresh automático)
                └──────────┬──────────┘
                           │ REST /api (JSON)
                ┌──────────▼──────────┐
                │  Django + DRF        │  permisos por rol, ámbito por programa, auditoría
                └──────┬───────┬──────┘
                       │       │
              ┌────────▼──┐ ┌──▼────────────────────────┐
              │PostgreSQL │ │ backend/ml/services.py     │ carga el modelo activo 1 vez (caché)
              └───────────┘ │   └─ sipd_ml.inference     │ misma transformación que en entrenamiento
                            └──────────▲────────────────┘
                                       │ artefactos .joblib
                            ml/scripts/train.py (offline)
```

Decisiones:

- **Paquete `sipd_ml` compartido**: entrenamiento e inferencia importan las mismas definiciones de variables
  (`config.py`) y la misma función de variables derivadas (`features.py`). El paquete vive en
  `backend/sipd_ml` (importable directamente por Django) y los scripts de `ml/` lo importan desde ahí, sin
  duplicar código.
- **Umbrales centralizados**: `backend/config/risk.py` es la única fuente; el frontend los lee de `/api/config/`.
- **Predicciones inmutables**: cada ejecución crea un registro; la anterior del mismo estudiante/periodo pasa a
  estado `REEMPLAZADA`.
- **Normalización**: `Student` guarda datos estables (código, programa, semestre y estado actuales);
  la información por periodo está en `AcademicRecord` (único por estudiante+periodo). Por eso el
  `academic_period` del requerimiento se modela como `Student.current_period` + `AcademicRecord.academic_period`.
- **Módulo Seguimiento**: el requerimiento pide registrar seguimiento (sección 24) y los diseños de referencia lo
  incluyen en el menú, por lo que se agregó como sección propia además de estar disponible en el detalle del estudiante.

## 2. Modelo de datos

| Entidad | Campos principales |
|---|---|
| `User` | username, email (único), password (hash), role (ADMIN/COORDINATOR), programs (M2M), can_manage_users, is_active, password_changed_at, created_at, updated_at |
| `Program` | code, name, is_active |
| `AcademicPeriod` | code (AAAA-T), year, term, start_date, end_date, is_current |
| `Student` | anonymous_code (E001), program, semester, academic_status, current_period, is_active, timestamps |
| `AcademicRecord` | student, academic_period, semester, gpa, credits_enrolled/approved/failed, failed_subjects, attendance_percentage, course_repetitions, variables de encuesta (nullable), extra_survey_data (JSON), source_upload |
| `ModelVersion` | name, algorithm, version, metrics (JSON), trained_at, active, artifact_dir, is_synthetic, selected, dataset_rows, evaluation (JSON: conjunto, partición, tamaños), artifact_checksums (SHA-256), training_run, approval_status (PENDIENTE/APROBADO/RECHAZADO/NO_REQUERIDA), acceptance (JSON), approved_by, approved_at, approval_notes |
| `TrainingDataset` | source (CARGA/REFERENCIA), filename, content (bytes), checksum, size_bytes, rows, status (VALIDO; los rechazados no se guardan), report (JSON), is_synthetic, uploaded_by, created_at |
| `TrainingRun` | dataset, requested_by, status (PENDIENTE…COMPLETADO/FALLIDO/CANCELADO), stage_message, events (JSON), algorithms, selection_metric, threshold, version, selected_algorithm, ranking, error_message, in_progress (restricción única parcial = una ejecución a la vez), created_at, started_at, finished_at, heartbeat_at |
| `ModelActivationLog` | action (INICIAL/ACTIVACION/RECUPERACION), previous_version, new_version, etiquetas, performed_by, created_at |
| `Alert` | student, academic_period (único juntos), prediction, reason (NIVEL_ALTO/AUMENTO/ALTO_Y_AUMENTO), priority, probability, previous_probability, status (ABIERTA/EN_ATENCION/CERRADA), assigned_to, closed_by, closing_observation, followup (seguimiento con el que se gestiona), created_at, updated_at, closed_at |
| `AlertComment` | alert, author, text, created_at |
| `Notification` | recipient, type, level, title, message, link (ruta interna), entity, entity_id, dedupe_key (único por destinatario), created_at, read_at |
| `Prediction` | student, academic_record, academic_period, model_version, model_name, probability, risk_level, status (VIGENTE/REEMPLAZADA), input_features, explanation, prediction_date, created_by |
| `FollowUp` | student, user (responsable), created_by, academic_period, intervention_type, status (PENDIENTE/EN_SEGUIMIENTO/ATENDIDO/CERRADO), observation, follow_up_date |
| `DataUpload` | uploaded_by, file, filename, checksum, records_found/valid/failed/processed, predictions_generated, errors (JSON), status, upload_date |
| `AuditLog` | user, action, entity, entity_id, description, metadata, ip_address, created_at |

## 3. API REST

Autenticación: `Authorization: Bearer <access>`. Respuestas de error: `{"detail": "...", "errors": {...}}`.
Paginación: `?page=&page_size=` (máx. 100).

| Método | Ruta | Descripción | Rol |
|---|---|---|---|
| POST | `/api/auth/login/` | Usuario o correo + contraseña (+ `remember`) → `access` y `user`; el refresh token va en la cookie HttpOnly `sipd_refresh` | Público |
| POST | `/api/auth/refresh/` | Renueva el access token con la cookie (rotación); exige `X-Requested-With: XMLHttpRequest` | Cookie |
| POST | `/api/auth/logout/` | Invalida el refresh token de la cookie y la borra; exige `X-Requested-With` | Cookie |
| GET | `/api/auth/me/` | Perfil | Autenticado |
| POST | `/api/auth/password-reset/` | `{email}` → envía un enlace de recuperación (respuesta siempre igual; 5 solicitudes/hora) | Público |
| POST | `/api/auth/password-reset/confirm/` | `{uid, token, new_password, confirm_password}` → cambia la contraseña y cierra las sesiones | Público (enlace de un solo uso, 30 min) |
| POST | `/api/auth/change-password/` | Cambio de contraseña | Autenticado |
| GET | `/api/config/` | Umbrales, catálogos, etiquetas de variables | Autenticado |
| GET/POST/PATCH | `/api/users/` | Gestión de usuarios (DELETE = desactivar) | Admin |
| GET | `/api/programs/`, `/api/periods/` | Catálogos | Autenticado |
| GET | `/api/students/` | Sólo lectura. Filtros: `search, program, semester, academic_status, risk_level, period, followup_status, trend=up\|down, alert=open, ordering=-current_probability (defecto)\|-risk_change\|anonymous_code`. Incluye `risk_change_points` y `open_alert_status` | Según ámbito |
| GET | `/api/students/{id\|E001}/` | Detalle con historial académico; cada consulta se registra (`STUDENT_VIEWED`) | Según ámbito |
| GET | `/api/students/export/` | CSV del listado con los mismos filtros | Según ámbito |
| GET | `/api/alerts/` | `status=pending (defecto en la interfaz)\|ABIERTA\|EN_ATENCION\|CERRADA\|all, priority, reason, program, period, student, assigned=me\|none` | Admin, Coordinador (ámbito) |
| GET | `/api/alerts/{id}/` · `/api/alerts/summary/` | Detalle con comentarios · conteos y recientes | Admin, Coordinador (ámbito) |
| — | (sin acciones propias) | Las alertas se gestionan con `POST/PATCH /api/followups/`: registrar el seguimiento las pone *En atención*; marcarlo ATENDIDO o CERRADO las cierra con su observación | Admin, Coordinador (ámbito) |
| GET | `/api/predictions/` | Filtros: `period, program, risk_level, model, date_from, date_to, student, status` | Según ámbito |
| GET | `/api/predictions/{id}/` | Incluye variables de entrada y explicación | Según ámbito |
| POST | `/api/predictions/` | `{student, academic_period?}` → predicción | Admin |
| POST | `/api/predictions/run-batch/` | `{academic_period, program?}` | Admin |
| GET | `/api/predictions/history/?student=E001` | Evolución temporal | Según ámbito |
| GET | `/api/predictions/trend/` | % por nivel en cada periodo | Según ámbito |
| GET | `/api/predictions/summary/` | Datos de **Inicio**; `risk_level` filtra tarjetas, gráficos y tabla | Según ámbito |
| GET | `/api/models/` · POST `/api/models/{id}/activate/` · POST `/api/models/sync/` | Versiones de modelos | Lectura: todos · Escritura: Admin |
| GET/POST | `/api/uploads/` | Validar CSV (multipart `file`) / historial | Admin |
| POST | `/api/uploads/{id}/confirm/` | Procesar registros válidos | Admin |
| POST | `/api/uploads/{id}/discard/` | Descartar una carga validada no confirmada (las rechazadas nunca se guardan) | Admin |
| GET | `/api/uploads/template/` | Plantilla CSV | Admin |
| GET/POST/PATCH | `/api/followups/` | Seguimiento (sin eliminación); `latest=true` devuelve sólo el último de cada estudiante | Todos (ámbito) |
| GET | `/api/followups/responsibles/?student=E001` | Coordinadores con acceso al programa del estudiante (nunca administradores) | Todos (ámbito) |
| GET | `/api/training/overview/` | Estado de modelos, configuración, ejecución en curso | Admin |
| POST | `/api/training/datasets/` | Validar dataset (multipart `file`) → 201 / 422 | Admin |
| GET | `/api/training/datasets/{id}/` | Informe de validación | Admin |
| GET/POST | `/api/training/runs/` | Historial (`status, algorithm, date_from, date_to`) / iniciar `{dataset, algorithms, confirm: true}` (`selection_metric` opcional, `f1` por defecto) → 202, 409 si hay otra en curso, 503 si está desactivado | Admin |
| GET | `/api/training/runs/{id}/` · `/api/training/runs/active/` | Estado real, etapas, versiones, comparaciones | Admin |
| POST | `/api/training/runs/{id}/cancel/` | Cancelar (sólo PENDIENTE) | Admin |
| POST | `/api/models/{id}/approve/` · `/reject/` | Revisión `{notes}`; aprobar exige criterios de aceptación | Admin |
| POST | `/api/models/{id}/activate/` · `/rollback/` | Activación verificada / recuperación de una versión que estuvo activa | Admin |
| GET | `/api/models/{id}/evaluation/` · `/api/models/activations/` | Evaluación y comparación / historial y candidatas a recuperar | Admin |
| GET | `/api/notifications/` | Propias; filtros `is_read, type, category` | Autenticado |
| GET | `/api/notifications/unread-count/` | Contador | Autenticado |
| POST | `/api/notifications/{id}/read/` · `/api/notifications/read-all/` | Marcar leída(s) | Autenticado |
| GET | `/api/reports/risk/` (+ `csv/`, `pdf/`) | Riesgo agregado: `period, program, semester, date_from, date_to` | Todos (ámbito) |
| GET | `/api/reports/risk/students/csv/` | Listado individual seudonimizado | Admin |

Errores: 400 validación, 401 sin sesión, 403 permisos, 404 inexistente, 409 conflicto de estado (entrenamiento en
curso, versión no aprobada, artefactos alterados…), 422 archivo rechazado, 503 función no disponible. Nunca se
devuelven trazas internas.

Ejemplo de respuesta de `POST /api/predictions/`:

```json
{
  "student_id": "E001",
  "academic_period": "2026-2",
  "risk_probability": 0.82,
  "risk_percentage": 82.0,
  "risk_level": "Alto",
  "model": "Random Forest",
  "model_version": "20260927221150",
  "prediction_date": "2026-08-26"
}
```

## 4. Frontend

- `context/AuthContext` (sesión, login/logout, sesión expirada) y `context/ConfigContext` (catálogos del backend).
- `services/apiClient.js`: interceptor que adjunta el token y renueva el access token con el refresh (una sola
  renovación concurrente); si falla, cierra sesión y muestra "Sesión expirada.".
- `hooks/useApi` gestiona estados *loading / error / data* e ignora respuestas obsoletas; `hooks/useFilters`
  sincroniza filtros con la URL.
- Componentes reutilizables: Sidebar, Topbar, Card/StatCard, DataTable, SearchBar, Filter, RiskBadge/RiskBar,
  StatusBadge, Modal, ConfirmationModal, Button, Input, Select, Pagination, Loading, EmptyState, ErrorMessage,
  Alert, ErrorBoundary (evita pantallas en blanco).
- Accesibilidad: el nivel de riesgo siempre se muestra con texto y forma (rombo/cuadrado/círculo) además del color;
  las gráficas tienen leyenda con valores y existe siempre una tabla equivalente.

## 5. Extender el sistema

- **Nueva variable del modelo**: agregarla a `backend/sipd_ml/config.py` (+ etiqueta), al modelo `AcademicRecord`,
  a `AcademicRecord.to_model_input`, al validador CSV y reentrenar.
- **Cambiar umbrales**: variables `RISK_LOW_THRESHOLD` / `RISK_MEDIUM_THRESHOLD`. Las predicciones existentes
  conservan el nivel con que se generaron; ejecute un nuevo proceso de predicción para reclasificar.
- **Datos reales**: dataset con las columnas de `MODEL_FEATURES` (sin derivadas) y `dropout` (0/1), anonimizado,
  fuera del repositorio (`data/private/`).

## 6. Reentrenamiento, notificaciones y reportes (actualización)

### Diagnóstico previo

| | Hallazgo |
|---|---|
| Reutilizable | `sipd_ml.pipeline.run_training_pipeline` (partición, preprocesador, algoritmos, evaluación, guardado), `RiskPredictor`, `ModelVersion` + `sync_model_versions`, caché del predictor por versión activa, validadores de archivo de `uploads`, roles (`IsAdminRole`), ámbito por programa, `AuditLog`, componentes React (Card, DataTable, ConfirmationModal, Filter, StatusBadge, gráficos Recharts) |
| Modificado | Pipeline: callback de etapas reales y opción de no publicar la copia raíz; persistencia: escritura atómica y SHA-256; `ModelVersion`: aprobación, evaluación, integridad; activación: verificación previa y registro; vistas de predicción/carga: notificaciones |
| Nuevo | `ml/training_service.py`, `sipd_ml/dataset_validation.py`, `TrainingDataset`, `TrainingRun`, `ModelActivationLog`, apps `notifications` y `reports`, comando `process_training_runs`, páginas Reentrenamiento, Reportes y Notificaciones, campana |
| Riesgos resueltos | Sin sistema de tareas (hilo + latido + restricción única); disco efímero en Vercel (desactivado y documentado); versiones a medio escribir (carpeta temporal + `os.replace`); artefactos manipulados o rutas fuera de `ML_MODELS_DIR` (SHA-256 y validación de ruta antes de cargar con joblib); activación con fallo (verificación antes de la transacción) |
| Dependencias | `reportlab` (PDF con tablas, gráficos y numeración, sin dependencias de sistema). Nada más: sin Celery, Redis ni WebSockets |

### Flujo

```
Admin ─ CSV ─▶ POST /training/datasets/ ─▶ validate_training_dataset ─▶ TrainingDataset (sólo si es VALIDO)
      ─ confirmar ─▶ POST /training/runs/ ─▶ TrainingRun(PENDIENTE, in_progress=True) ─▶ hilo / worker
                         execute_run: VALIDANDO → PREPARANDO → ENTRENANDO → EVALUANDO → REGISTRANDO
                         run_training_pipeline(publish_default=False) → carpetas <algoritmo>_<versión>/
                         ModelVersion(PENDIENTE, checksums, acceptance) → COMPLETADO + notificaciones
      ─ aprobar ─▶ evaluate_acceptance → APROBADO
      ─ activar ─▶ verify_artifacts (ruta, SHA-256, carga, predicción de prueba) → transacción → caché limpia
```

Las predicciones toman siempre la versión activa de la BD (`ml.services.get_predictor`): la siguiente predicción tras
una activación carga la versión nueva y las que ya estaban en curso terminan con la anterior.
