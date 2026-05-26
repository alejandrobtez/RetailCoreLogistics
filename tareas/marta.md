# 🚀 Marta Moreno — Backend & Frontend Lead

← [Volver al README principal](../README.md)

**Rol:** Backend · FastAPI · Notificaciones · Power BI Dashboard · Integración final

---

## 🎯 Responsabilidad en el proyecto

Marta es la responsable de que el modelo llegue a los operadores de una forma usable y clara. Construye la API que consume el modelo de Azure ML, el job que se ejecuta antes de las 7:00 AM y el dashboard de Power BI que los operadores ven en su pantalla cada mañana.

---

## 📋 Tareas detalladas

### 🚀 API REST (FastAPI)

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 1 | Estructura del proyecto FastAPI | Crear app con routers, models y config. Separar `/predict`, `/health`, `/report` | ⚪ Pendiente |
| 2 | Endpoint `POST /predict` | Recibe lista de entregas del día → devuelve lista priorizada con probabilidad y top 3 factores SHAP | ⚪ Pendiente |
| 3 | Endpoint `GET /report/today` | Devuelve el informe del día en formato JSON y CSV | ⚪ Pendiente |
| 4 | Conexión con Azure ML Endpoint | Llamar al Online Endpoint de Azure ML desde la API (autenticación con Managed Identity) | ⚪ Pendiente |
| 5 | Conexión con PostgreSQL | SQLAlchemy: leer entregas del día y guardar predicciones | ⚪ Pendiente |
| 6 | Documentación automática | FastAPI auto-genera `/docs` (Swagger). Verificar que es usable para un técnico externo | ⚪ Pendiente |

### ⏰ Job automático 7:00 AM

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 7 | Scheduler de predicción | Azure Functions o cron job: ejecuta el pipeline completo cada día a las 6:45 AM | ⚪ Pendiente |
| 8 | Leer entregas del día siguiente de PostgreSQL | Query para extraer todas las entregas planificadas para mañana | ⚪ Pendiente |
| 9 | Llamar al modelo y guardar predicciones | Llamar a `/predict` y guardar en tabla `predicciones_diarias` | ⚪ Pendiente |
| 10 | Control de errores y alertas | Si el job falla → email automático al equipo técnico | ⚪ Pendiente |

### 🔔 Notificaciones automáticas

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 11 | Azure Logic Apps: SMS al destinatario | Si prob. fallo > 70% → SMS automático: "Tu entrega está prevista hoy. ¿Confirmas disponibilidad?" | ⚪ Pendiente |
| 12 | Azure Logic Apps: alerta al operador | Notificación en Teams/Email con la lista de entregas de alto riesgo del día | ⚪ Pendiente |
| 13 | Lógica de umbral configurable | El umbral de notificación (70% por defecto) debe ser configurable sin tocar código | ⚪ Pendiente |

### 📊 Dashboard Power BI — diferenciador clave ⭐

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 14 | Conectar Power BI a PostgreSQL | Fuente de datos: tabla `predicciones_diarias` actualizada cada mañana | ⚪ Pendiente |
| 15 | Vista principal: lista del día | Tabla priorizada por probabilidad de fallo con colores de semáforo (verde/naranja/rojo) | ⚪ Pendiente |
| 16 | Vista por repartidor | Para cada repartidor: sus entregas de riesgo del día, ordenadas por probabilidad | ⚪ Pendiente |
| 17 | ⭐ Mapa de calor por zona | Mapa de Madrid/BCN/Valencia/Sevilla con intensidad de fallos previstos por zona | ⚪ Pendiente |
| 18 | Panel de explicación | Al hacer clic en una entrega: aparecen los 3 factores SHAP explicados en lenguaje natural | ⚪ Pendiente |
| 19 | KPIs del día | Tarjetas: total entregas, % alto riesgo, SMS enviados, comparativa con ayer | ⚪ Pendiente |
| 20 | Informe PDF/Excel automático | Exportación del informe diario para operadores sin acceso a Power BI | ⚪ Pendiente |

---

## 📦 Ficheros que genera Marta

```
api/
├── main.py                       ← FastAPI app principal
├── predict.py                    ← Endpoint /predict
├── report.py                     ← Endpoint /report
├── scheduler.py                   ← Job automático 6:45 AM
└── db.py                          ← Conexión SQLAlchemy

dashboard/
└── retailcore.pbix               ← Power BI report

docs/
└── costes.md                     ← Estimación de costes en producción
```

---

## 🛠️ Stack técnico de Marta

- **FastAPI + Uvicorn:** API REST principal
- **SQLAlchemy:** ORM para PostgreSQL
- **Azure ML SDK:** Conexión con el Online Endpoint
- **Azure Logic Apps:** Flujos de notificación SMS y email
- **Azure Functions:** Scheduler del job de 7:00 AM
- **Power BI Desktop + Power BI Service:** Dashboard operativo ⭐

---

## 📌 Criterios de éxito

- El job se ejecuta sin fallos a las 6:45 AM y las predicciones están disponibles a las 7:00 AM
- El dashboard es usable por un operador no técnico en menos de 30 segundos de onboarding
- El SMS automático se envía solo a las entregas con prob. > umbral configurable
- La API devuelve la lista priorizada en < 2 segundos para un lote de 1.000 entregas

---

## 💰 Estimación de costes — área de Marta

| Servicio | Coste estimado/mes |
|---|---|
| Azure Functions (job 7:00 AM) | ~2 € |
| Azure Logic Apps (notificaciones) | ~10 € |
| Power BI Premium Per User | ~20 € |
| Azure Container Apps (FastAPI) | ~25 € |
| **Subtotal área backend/front** | **~57 €/mes** |

---

## 🔗 Dependencias con el resto del equipo

- **← Alejandro:** Marta necesita el Azure ML Online Endpoint registrado para conectar la API
- **← Borja:** Marta necesita el esquema de PostgreSQL para leer las entregas planificadas
