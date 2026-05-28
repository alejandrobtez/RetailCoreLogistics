# 📦 RetailCore Logistics · Predictor de Fallos en Entrega ☁️
 
![Banner](img/banner.svg)
 
> **Tajamar Fight · Caso 01** — Sistema de predicción de fallos en entrega de última milla con IA explicable  
> **Equipo:** Alejandro Benítez · Borja Núñez · Marta Moreno · **Entrega:** 31/05/2026
 
Pipeline de ML desplegado sobre **Microsoft Azure**: datos en Blob Storage, historial en Azure SQL, secretos en Key Vault, experimentos en MLflow.
 
**18.000 paquetes/día · Madrid · Barcelona · Valencia · Sevilla · Datos AEMET en tiempo real**
 
---
 
## ✅ Tareas del proyecto
 
> **Estados:** ✅ Hecho · 🟡 En curso · ⚪ Pendiente · 🔴 AVISAR YA
 
---
 
### — DATOS —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Generar el dataset de entregas | Marta | ✅ Hecho |
| <sub>Con Python generamos un fichero con ~500.000 entregas ficticias que incluyen: ciudad, zona, día de la semana, tipo de producto, si llovía, si fue primer intento o reintento, y si la entrega falló. La tasa de fallos ronda el 23%. Script: `data/generate_synthetic.py`</sub> | | |
| Descargar datos meteorológicos | Marta | ✅ Hecho |
| <sub>Usamos la API gratuita de AEMET para descargar lluvia y temperatura histórica en Madrid, Barcelona, Valencia y Sevilla. La API key se guarda en **Azure Key Vault** (`aemet-api-key`). Script: `data/scraping_aemet.py`</sub> | | |
| Subir dataset a Azure Blob Storage | Alejandro | ✅ Hecho |
| <sub>Una vez generado el CSV, subirlo al container `raw` dentro de `data`</sub> | | |
 
---
 
### — MODELO —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Preparar los datos para entrenar | Marta | ✅ Hecho |
| <sub>Arquitectura medallion en `ml_pipeline/src/data/`: **Bronze** → carga cruda y validación de esquema; **Silver** → conversión de tipos, nulos y dedup; **Gold** → feature selection, split estratificado 70/10/20, class weights y scaler stats. Artefactos (scaler_stats, feature_cols) en Blob `processed/`.</sub> | | |
| Entrenar y elegir el mejor modelo | Borja | ✅ Hecho |
| <sub>Probamos Logistic Regression, Random Forest y XGBoost con 39 features (OHE de zona/producto, encodings cíclicos, interacciones). **Ganador: XGBoost** — AUC-ROC 0.744, Average Precision 0.489, Recall fallos 64%. El modelo se guarda en `models/best_model.pkl` y se registra en MLflow. Ejecutar: `cd ml_pipeline && python pipeline.py`</sub> | | |
| Explicar por qué falla cada entrega | Alejandro | ⚪ Pendiente |
| <sub>Con SHAP el modelo no solo dice "esta entrega va a fallar" sino también por qué: "porque llueve, es reintento y es viernes por la tarde". Notebook: `ml_pipeline/shap_explainability.ipynb`. Eso es lo que verá el operador en el dashboard.</sub> | | |
 
---
 
### — SISTEMA —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Crear la API | Borja | ✅ Hecho |
| <sub>FastAPI en `api/main.py`. Endpoints: `POST /api/v1/predict` (batch con AEMET opcional), `GET /api/v1/health`, `GET /api/v1/model/info`. El modelo se carga desde Blob Storage al arrancar (fallback local en `ml_pipeline/tmp/`). El predictor aplica el mismo feature engineering que el pipeline. SHAP pendiente de integrar (campo `shap_reason` reservado). Arrancar: `uvicorn api.main:app --reload`</sub> | | |
| Automatizar la predicción diaria | Alejandro | ⚪ Pendiente |
| <sub>Azure Function (o cron) que cada noche antes de las 7:00 AM lee los paquetes del día desde Blob `raw-data/`, llama a `src/inference/predict.py`, guarda resultados en Blob `reports/` y en **Azure SQL** tabla `delivery_predictions`. Sin intervención manual. Ver sección "Producción" más abajo.</sub> | | |
| Avisar a los destinatarios de riesgo | Marta | ⚪ Pendiente |
| <sub>Si prob_fallo > 0.70 (nivel HIGH), **Azure Logic Apps** manda automáticamente un SMS al destinatario proponiéndole cambiar de franja horaria. Se dispara leyendo la tabla `delivery_predictions` de Azure SQL tras cada batch.</sub> | | |
 
---
 
### — DASHBOARD —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Crear el panel para operadores | Marta | ⚪ Pendiente |
| <sub>Power BI conectado a **Azure SQL** (`delivery_predictions`). Cada mañana muestra la lista de entregas del día ordenada de mayor a menor riesgo, con semáforo de colores y motivo del fallo en texto normal. Sin tecnicismos. Fichero: `dashboard/retailcore.pbix`</sub> | | |
| ⭐ Añadir mapa de zonas de riesgo | Marta | ⚪ Pendiente |
| <sub>Dentro del dashboard, un mapa de las 4 ciudades que colorea las zonas según cuántas entregas en riesgo tienen ese día. Datos del mapa desde Azure SQL, agregados por `city` + `zone`. De un vistazo el operador sabe dónde se concentran los problemas.</sub> | | |
 
---
 
### — ENTREGA —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Hacer funcionar todo junto | Borja | ⚪ Pendiente |
| <sub>Ejecutar el sistema completo de principio a fin: datos en Blob → pipeline entrena → API responde → dashboard lo muestra → SMS se envía. Si esto funciona, el proyecto está listo. Usar el setup rápido de más abajo.</sub> | | |
| Preparar la presentación | Alejandro | ⚪ Pendiente |
| <sub>Slides y demo en directo para el jurado. Explicar el problema, la solución, los recursos Azure utilizados, cuánto costaría en producción (`docs/costes.md`) y por qué somos mejores que el otro grupo.</sub> | | |
 
---
 
## 🗺️ Línea temporal
 
![Timeline](img/timeline.svg)
 
---
 
## 🏗️ Arquitectura de la solución
 
![Arquitectura](img/arquitectura.svg)
 
```
┌─────────────────────────────────────────────────────────────────┐
│  CAPA 1 · DATOS — Medallion Architecture                        │
│  🥉 Bronze → carga cruda + esquema    (raw-data/bronze/)        │
│  🥈 Silver → limpieza + validación   (raw-data/silver/)         │
│  🥇 Gold   → features + splits       (processed/)               │
├─────────────────────────────────────────────────────────────────┤
│  CAPA 2 · MACHINE LEARNING  (Azure ML + MLflow)                 │
│  XGBoost / RF ──► SHAP ──► Azure ML Registry ──► best_model.pkl│
├─────────────────────────────────────────────────────────────────┤
│  CAPA 3 · BACKEND                                               │
│  FastAPI ──► Azure Function (job 7AM) ──► Logic Apps (SMS)      │
│  Resultados ──► Azure SQL (delivery_predictions)                │
├─────────────────────────────────────────────────────────────────┤
│  CAPA 4 · SALIDA OPERATIVA                                      │
│  Power BI ←── Azure SQL · Lista priorizada · Mapa de calor ⭐  │
└─────────────────────────────────────────────────────────────────┘
```
 
---
 
## ⭐ Diferenciadores frente a la competencia
 
| Diferenciador | Qué aporta al cliente |
|---|---|
| **Explicación por entrega (SHAP)** | No solo "alto riesgo", sino "falla porque llueve + centro + lunes + reintento" |
| **SMS automático (Logic Apps)** | El sistema avisa al destinatario solo, sin intervención humana |
| **Mapa de zonas de riesgo** | Vista geográfica intuitiva para operadores no técnicos |
| **Dashboard sin tecnicismos** | Cualquier operador lo entiende el primer día, sin formación en IA |
| **Azure nativo** | Datos, modelos, secretos y alertas en la misma plataforma: sin dependencias externas |
 
---
 
## 🔌 API de predicciones

```bash
# Arrancar la API (desde la raíz del repo)
uvicorn api.main:app --reload --port 8000

# Docs interactivas → http://localhost:8000/docs
```

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Estado de la API y del modelo |
| `GET` | `/api/v1/model/info` | Metadatos del modelo en producción |
| `POST` | `/api/v1/predict` | Predicción batch con AEMET opcional |

### Ejemplo de petición

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "city": "madrid",
    "use_aemet": false,
    "deliveries": [{
      "delivery_id": "dlv_001",
      "date": "2024-05-28",
      "hour": 10,
      "day_of_week": 0,
      "is_holiday": 0,
      "zone": "madrid",
      "zone_type": "historic_center",
      "recipient_failure_rate": 0.31,
      "num_previous_attempts": 1,
      "driver_quality_score": 0.72,
      "driver_delivery_load": 22,
      "product_type": "fragile",
      "requires_signature": 0,
      "is_fragile": 1,
      "is_bulky": 0,
      "weight_kg": 4.5,
      "weather_rain": 1,
      "weather_wind_speed": 3.2,
      "weather_temperature": 11.0,
      "is_retry": 1
    }]
  }'
```

### Respuesta

```json
{
  "total": 1,
  "high": 0,
  "medium": 1,
  "low": 0,
  "model_name": "xgboost",
  "predictions": [{
    "delivery_id": "dlv_001",
    "prob_fallo": 0.6712,
    "risk_level": "MEDIUM",
    "action": "CAMBIAR_FRANJA",
    "shap_reason": null
  }]
}
```

> **Nota:** El campo `shap_reason` quedará relleno cuando Alejandro integre el módulo SHAP.

---

## 🛠️ Setup rápido
 
```bash
# 1. Clonar el repo
git clone https://github.com/alejandrobtez/RetailCoreLogistics.git
cd RetailCoreLogistics
 
# 2. Instalar dependencias
pip install -r ml_pipeline/requirements.txt
 
# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales Azure (o usar Key Vault, ver más abajo)
 
# 4. Generar datos sintéticos
python data/generate_synthetic.py
 
# 5. Subir dataset a Blob Storage
az storage blob upload \
  --account-name logisticstoragegenai \
  --container-name data \
  --name raw/deliveries_synthetic.csv \
  --file data/raw/deliveries_synthetic.csv
 
# 6. Entrenar el modelo (lee desde Blob, guarda en Blob + MLflow)
cd ml_pipeline && python pipeline.py
 
# 7. Lanzar la API (desde la raíz del repo)
cd ..
uvicorn api.main:app --reload
 
# 8. Ver experimentos MLflow
mlflow ui --backend-store-uri ml_pipeline/mlruns   # → http://localhost:5000
```
 
---
 
## ☁️ Recursos Azure necesarios
 
| Recurso | Nombre sugerido | Para qué |
|---|---|---|
| Resource Group | `BenitezBernaAlejandro` | Contenedor de todos los recursos |
| Storage Account | `logisticstoragegenai` | Datos, modelos, reports |
| Azure PostgreSQL | `sql-retailcore-ml` | Historial de predicciones y métricas, tablas de resultados |
| Key Vault | `?????` | Secretos: AEMET key, connection strings |
| Azure ML Workspace | `???????` | MLflow tracking + Model Registry |
| Azure Logic Apps | — | SMS automático a destinatarios de riesgo |
 
### Crear los recursos (Azure CLI)
 
```bash
RG="rg-retailcore-ml"
LOCATION="westeurope"
STORAGE="stretailcoreml"
SQL_SERVER="sql-retailcore-ml"
SQL_DB="retailcore-predictions"
KV="kv-retailcore-ml"
SQL_ADMIN="retailcoreadmin"
SQL_PASS="TuPassword123!"   # cámbiala
 
az group create --name $RG --location $LOCATION
 
# Storage + contenedores
az storage account create --name $STORAGE --resource-group $RG \
  --location $LOCATION --sku Standard_LRS --kind StorageV2
STORAGE_CONN=$(az storage account show-connection-string \
  --name $STORAGE --resource-group $RG --query connectionString -o tsv)
for container in raw-data processed models reports; do
  az storage container create --name $container --connection-string "$STORAGE_CONN"
done
 
# Azure SQL
az sql server create --name $SQL_SERVER --resource-group $RG \
  --location $LOCATION --admin-user $SQL_ADMIN --admin-password $SQL_PASS
az sql db create --name $SQL_DB --server $SQL_SERVER \
  --resource-group $RG --service-objective S1
MY_IP=$(curl -s ifconfig.me)
az sql server firewall-rule create --server $SQL_SERVER --resource-group $RG \
  --name AllowMyIP --start-ip-address $MY_IP --end-ip-address $MY_IP
 
# Key Vault + secretos
az keyvault create --name $KV --resource-group $RG --location $LOCATION
SQL_CONN="Driver={ODBC Driver 18 for SQL Server};Server=tcp:${SQL_SERVER}.database.windows.net,1433;Database=${SQL_DB};Uid=${SQL_ADMIN};Pwd=${SQL_PASS};Encrypt=yes;TrustServerCertificate=no"
az keyvault secret set --vault-name $KV --name "aemet-api-key"             --value "TU_API_KEY_AEMET"
az keyvault secret set --vault-name $KV --name "storage-connection-string" --value "$STORAGE_CONN"
az keyvault secret set --vault-name $KV --name "sql-connection-string"     --value "$SQL_CONN"
```
 
### Variables de entorno (desarrollo local)
 
```bash
# Opción A: directas
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
export AZURE_SQL_CONNECTION_STRING="Driver={ODBC Driver 18 for SQL Server};..."
export AEMET_API_KEY="tu_api_key"
 
# Opción B: Key Vault (requiere az login)
az login   # el pipeline lee los secretos automáticamente
```
 
---
 
## Qué va a cada recurso Azure
 
| Dato | Recurso | Ruta / Tabla |
|---|---|---|
| Dataset original | Blob `raw-data` | `deliveries_features.csv` |
| Capa Bronze | Blob `raw-data` | `bronze/deliveries_raw_YYYYMMDD.csv` |
| Capa Silver | Blob `raw-data` | `silver/deliveries_clean_YYYYMMDD.csv` |
| Paquetes del día | Blob `raw-data` | `today_packages_YYYY-MM-DD.csv` |
| Scaler stats | Blob `processed` | `scaler_stats.pkl` |
| Modelo entrenado | Blob `models` | `best_model.pkl` |
| Predicciones del día | Blob `reports` | `predictions_YYYY-MM-DD.csv` |
| Paquetes alto riesgo | Blob `reports` | `high_risk_YYYY-MM-DD.csv` |
| Comparativa modelos | Blob `reports` | `model_comparison.csv` |
| Historial predicciones | Azure SQL | `delivery_predictions` |
| Métricas del modelo | Azure SQL | `model_metrics` |
| Alertas de drift | Azure SQL | `drift_alerts` |
| Experimentos ML | MLflow / Azure ML | UI en puerto 5000 |
| Secretos | Key Vault | `aemet-api-key`, `sql-connection-string`… |
 
---
 
## Inferencia diaria automática (6:50 AM)
 
```bash
# Subir paquetes del día
az storage blob upload \
  --container-name raw-data \
  --name today_packages_$(date +%Y-%m-%d).csv \
  --file today_packages.csv
 
# Ejecutar inferencia con AEMET en tiempo real
python src/inference/predict.py --city madrid
 
# Resultados en Blob: reports/predictions_YYYY-MM-DD.csv
# Resultados en SQL:  tabla delivery_predictions
```
 
**Automatizar con cron (VM / Azure Container Instance):**
```bash
50 6 * * 1-6 cd /app && python src/inference/predict.py --city madrid >> logs/inference.log 2>&1
```
 
---
 
## 📁 Estructura del repositorio
 
```
retailcore-predictor/
│
├── 📂 img/
│   ├── banner.svg
│   ├── arquitectura.svg
│   └── timeline.svg
│
├── 📂 data/
│   ├── generate_synthetic.py         # Generación del dataset sintético
│   ├── scraping_aemet.py             # Meteorología desde AEMET API
│   └── schema.sql                    # Esquema PostgreSQL / Azure SQL
│
├── 📂 ml_pipeline/
│   ├── pipeline.py                   # Orquestador principal — Bronze→Silver→Gold→Train→Eval→Save
│   ├── configs/config.yaml           # Configuración centralizada
│   ├── src/
│   │   ├── azure/azure_client.py     # Blob Storage + Azure SQL + Key Vault
│   │   ├── data/
│   │   │   ├── bronze.py             # Capa Bronze: carga cruda + validación esquema
│   │   │   ├── silver.py             # Capa Silver: tipos, nulos, dedup
│   │   │   └── gold.py               # Capa Gold: features, split 70/10/20, scaler stats
│   │   ├── training/                 # Entrenamiento (LR, RF, XGBoost) + guardado
│   │   ├── evaluation/               # Métricas + selección del mejor modelo
│   │   ├── inference/predict.py      # Batch 6:50 AM + AEMET en tiempo real
│   │   ├── aemet/aemet_client.py     # API AEMET (key desde Key Vault)
│   │   └── monitoring/drift.py       # PSI drift → alertas Azure SQL
│   └── tests/test_pipeline.py        # Tests unitarios: Bronze, Silver, Inferencia, Monitoring
│
├── 📂 api/
│   ├── main.py                       # FastAPI app + lifespan (carga modelo al arrancar)
│   ├── schemas.py                    # Pydantic: DeliveryRecord, BatchRequest, BatchResponse
│   ├── routers/
│   │   └── predict.py                # GET /health · GET /model/info · POST /predict
│   └── services/
│       └── predictor.py              # Singleton: carga modelo + lógica de predicción
│
├── 📂 dashboard/
│   └── retailcore.pbix               # Power BI report
│
├── 📂 docs/
│   ├── metricas.md                   # Resultados del modelo
│   └── costes.md                     # Estimación de costes Azure en producción
│
├── .env.example
├── requirements.txt
└── README.md
```
 
---
 
## 📋 Flujo de trabajo del equipo
 
```
1. git pull                          ← Siempre primero
2. Trabajar en tu rama               ← Nunca directamente en main
3. git add · git commit · git push   ← Commits pequeños y descriptivos
4. Pull Request a main               ← El otro lo revisa antes de mergear
```
 
**Formato de commits:**
```
feat: integrar azure blob storage en ingestion
fix: corregir join meteorología por ciudad
docs: añadir tabla de recursos azure al README
```
