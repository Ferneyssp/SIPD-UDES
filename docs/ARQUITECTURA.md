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
  (`config.py`) y la misma función de variables derivadas (`features.py`). El backend añade `ml/` al
  `sys.path` (variable `ML_DIR`), sin duplicar código.
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
| `User` | username, email (único), password (hash), role (ADMIN/COORDINATOR/PROFESSOR), programs (M2M), can_manage_users, is_active, created_at, updated_at |
| `Program` | code, name, is_active |
| `AcademicPeriod` | code (AAAA-T), year, term, start_date, end_date, is_current |
| `Student` | anonymous_code (E001), program, semester, academic_status, current_period, is_active, timestamps |
| `AcademicRecord` | student, academic_period, semester, gpa, credits_enrolled/approved/failed, failed_subjects, attendance_percentage, course_repetitions, variables de encuesta (nullable), extra_survey_data (JSON), source_upload |
| `ModelVersion` | name, algorithm, version, metrics (JSON), trained_at, active, artifact_dir, is_synthetic |
| `Prediction` | student, academic_record, academic_period, model_version, model_name, probability, risk_level, status (VIGENTE/REEMPLAZADA), input_features, explanation, prediction_date, created_by |
| `FollowUp` | student, user (responsable), created_by, academic_period, intervention_type, status (PENDIENTE/EN_SEGUIMIENTO/ATENDIDO/CERRADO), observation, follow_up_date |
| `DataUpload` | uploaded_by, file, filename, checksum, records_found/valid/failed/processed, predictions_generated, errors (JSON), status, upload_date |
| `AuditLog` | user, action, entity, entity_id, description, metadata, ip_address, created_at |

## 3. API REST

Autenticación: `Authorization: Bearer <access>`. Respuestas de error: `{"detail": "...", "errors": {...}}`.
Paginación: `?page=&page_size=` (máx. 100).

| Método | Ruta | Descripción | Rol |
|---|---|---|---|
| POST | `/api/auth/login/` | Usuario o correo + contraseña → access, refresh, user | Público |
| POST | `/api/auth/refresh/` | Renueva tokens (rotación) | Público |
| POST | `/api/auth/logout/` | Invalida el refresh token | Autenticado |
| GET | `/api/auth/me/` | Perfil | Autenticado |
| POST | `/api/auth/change-password/` | Cambio de contraseña | Autenticado |
| GET | `/api/config/` | Umbrales, catálogos, etiquetas de variables | Autenticado |
| GET/POST/PATCH | `/api/users/` | Gestión de usuarios (DELETE = desactivar) | Admin |
| GET | `/api/programs/`, `/api/periods/` | Catálogos | Autenticado |
| GET | `/api/students/` | Filtros: `search, program, semester, academic_status, risk_level, period, followup_status, ordering=-current_probability` | Según ámbito |
| GET | `/api/students/{id\|E001}/` | Detalle con historial académico | Según ámbito |
| POST/PATCH/DELETE | `/api/students/` | Registro/edición/desactivación | Admin |
| POST | `/api/students/{code}/records/` | Registro académico de un periodo | Admin |
| GET | `/api/predictions/` | Filtros: `period, program, risk_level, model, date_from, date_to, student, status` | Según ámbito |
| GET | `/api/predictions/{id}/` | Incluye variables de entrada y explicación | Según ámbito |
| POST | `/api/predictions/` | `{student, academic_period?}` → predicción | Admin |
| POST | `/api/predictions/run-batch/` | `{academic_period, program?}` | Admin |
| GET | `/api/predictions/history/?student=E001` | Evolución temporal | Según ámbito |
| GET | `/api/predictions/trend/` | % por nivel en cada periodo | Según ámbito |
| GET | `/api/predictions/summary/` | Datos de **Inicio** | Según ámbito |
| GET | `/api/models/` · POST `/api/models/{id}/activate/` · POST `/api/models/sync/` | Versiones de modelos | Lectura: todos · Escritura: Admin |
| GET/POST | `/api/uploads/` | Validar CSV (multipart `file`) / historial | Admin |
| POST | `/api/uploads/{id}/confirm/` | Procesar registros válidos | Admin |
| GET | `/api/uploads/template/` | Plantilla CSV | Admin |
| GET/POST/PATCH | `/api/followups/` | Seguimiento (sin eliminación) | Todos (ámbito) |
| GET | `/api/followups/responsibles/` | Posibles responsables | Todos |
| GET | `/api/audit/` | Auditoría | Admin |

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

- **Nueva variable del modelo**: agregarla a `ml/sipd_ml/config.py` (+ etiqueta), al modelo `AcademicRecord`,
  a `AcademicRecord.to_model_input`, al validador CSV y reentrenar.
- **Cambiar umbrales**: variables `RISK_LOW_THRESHOLD` / `RISK_MEDIUM_THRESHOLD`. Las predicciones existentes
  conservan el nivel con que se generaron; ejecute un nuevo proceso de predicción para reclasificar.
- **Datos reales**: dataset con las columnas de `MODEL_FEATURES` (sin derivadas) y `dropout` (0/1), anonimizado,
  fuera del repositorio (`data/private/`).
