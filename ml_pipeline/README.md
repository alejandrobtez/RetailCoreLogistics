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
| Descargar datos meteorológicos | Marta | 🟡 En curso |
| <sub>Usamos la API gratuita de AEMET para descargar lluvia y temperatura histórica en Madrid, Barcelona, Valencia y Sevilla. La API key se guarda en **Azure Key Vault** (`aemet-api-key`). Script: `data/scraping_aemet.py`</sub> | | |
| Subir dataset a Azure Blob Storage | Marta | ⚪ Pendiente |
| <sub>Una vez generado el CSV, subirlo al container `raw-data` de la cuenta `stretailcoreml`. Comando: `az storage blob upload --container-name raw-data --name deliveries_features.csv --file deliveries_features.csv`</sub> | | |

---

### — MODELO —

| Tarea | Responsable | Estado |
|---|---|---|
| Preparar los datos para entrenar | ❓ Por asignar | ⚪ Pendiente |
| <sub>Los datos más antiguos se usan para entrenar y los más recientes para validar. Split estratificado en `ml_pipeline/src/preprocessing/preprocess.py`. Los artefactos (scaler_stats, feature_cols) se guardan en Blob container `processed/`.</sub> | | |
| Entrenar y elegir el mejor modelo | ❓ Por asignar | ⚪ Pendiente |
| <sub>Probamos Logistic Regression, Random Forest y XGBoost. Nos quedamos con el que mejor detecte fallos (métrica: Average Precision). Objetivo AUC-ROC ≥ 0.80. El modelo ganador se guarda en Blob `models/best_model.pkl` y se registra en **Azure ML Model Registry** vía MLflow. Ejecutar: `python pipeline.py`</sub> | | |
| Explicar por qué falla cada entrega | Alejandro | ⚪ Pendiente |
| <sub>Con SHAP el modelo no solo dice "esta entrega va a fallar" sino también por qué: "porque llueve, es reintento y es viernes por la tarde". Notebook: `ml_pipeline/shap_explainability.ipynb`. Eso es lo que verá el operador en el dashboard.</sub> | | |

---

### — SISTEMA —

| Tarea | Responsable | Estado |
|---|---|---|
| Crear la API | Borja | ⚪ Pendiente |
| <sub>FastAPI en `api/main.py`. Recibe la lista de entregas del día, llama al modelo cargado desde Blob Storage y devuelve probabilidad de fallo + motivo SHAP. Es el puente entre el modelo y el dashboard/SMS. Arrancar: `uvicorn api.main:app --reload`</sub> | | |
| Automatizar la predicción diaria | Alejandro | ⚪ Pendiente |
| <sub>Azure Function (o cron) que cada noche antes de las 7:00 AM lee los paquetes del día desde Blob `raw-data/`, llama a `src/inference/predict.py`, guarda resultados en Blob `reports/` y en **Azure SQL** tabla `delivery_predictions`. Sin intervención manual. Ver sección "Producción" más abajo.</sub> | | |
| Avisar a los destinatarios de riesgo | Marta | ⚪ Pendiente |
| <sub>Si prob_fallo > 0.70 (nivel HIGH), **Azure Logic Apps** manda automáticamente un SMS al destinatario proponiéndole cambiar de franja horaria. Se dispara leyendo la tabla `delivery_predictions` de Azure SQL tras cada batch.</sub> | | |

---

### — DASHBOARD —

| Tarea | Responsable | Estado |
|---|---|---|
| Crear el panel para operadores | Alejandro | ⚪ Pendiente |
| <sub>Power BI conectado a **Azure SQL** (`delivery_predictions`). Cada mañana muestra la lista de entregas del día ordenada de mayor a menor riesgo, con semáforo de colores y motivo del fallo en texto normal. Sin tecnicismos. Fichero: `dashboard/retailcore.pbix`</sub> | | |
| ⭐ Añadir mapa de zonas de riesgo | Borja | ⚪ Pendiente |
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
│  CAPA 1 · DATOS                                                 │
│  Datos sintéticos + AEMET ──► Azure Blob Storage (raw-data/)   │
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

## 🛠️ Setup rápido

```bash
# 1. Clonar el repo
git clone https://github.com/team/retailcore-predictor.git
cd retailcore-predictor

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales Azure (o usar Key Vault, ver más abajo)

# 4. Generar datos sintéticos
python data/generate_synthetic.py

# 5. Subir dataset a Blob Storage
az storage blob upload \
  --container-name raw-data \
  --name deliveries_features.csv \
  --file deliveries_features.csv

# 6. Entrenar el modelo (lee desde Blob, guarda en Blob + Azure SQL + MLflow)
python pipeline.py

# 7. Lanzar la API
uvicorn api.main:app --reload

# 8. Ver experimentos MLflow
mlflow ui --backend-store-uri mlruns   # → http://localhost:5000
```

---

## ☁️ Recursos Azure necesarios

| Recurso | Nombre sugerido | Para qué |
|---|---|---|
| Resource Group | `rg-retailcore-ml` | Contenedor de todos los recursos |
| Storage Account | `stretailcoreml` | Datos, modelos, reports |
| Azure SQL Server | `sql-retailcore-ml` | Historial de predicciones y métricas |
| Azure SQL Database | `retailcore-predictions` | Tablas de resultados |
| Key Vault | `kv-retailcore-ml` | Secretos: AEMET key, connection strings |
| Azure ML Workspace | `mlw-retailcore` | MLflow tracking + Model Registry |
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
│   ├── pipeline.py                   # Orquestador principal (Azure)
│   ├── configs/config.yaml           # Configuración centralizada
│   ├── src/
│   │   ├── azure/azure_client.py     # Blob Storage + Azure SQL + Key Vault
│   │   ├── ingestion/ingest.py       # Paso 1: lee desde Blob
│   │   ├── preprocessing/            # Paso 2: split + artefactos a Blob
│   │   ├── training/                 # Paso 3+5: entrenamiento + guardado
│   │   ├── evaluation/               # Paso 4: métricas + reporte a Blob
│   │   ├── inference/predict.py      # Paso 6: batch 6:50 AM + AEMET
│   │   ├── aemet/aemet_client.py     # API AEMET (key desde Key Vault)
│   │   └── monitoring/drift.py       # PSI drift → alertas Azure SQL
│   └── tests/test_pipeline.py        # 10 tests unitarios
│
├── 📂 api/
│   ├── main.py                       # FastAPI app
│   ├── predict.py                    # Endpoint /predict
│   └── scheduler.py                  # Job automático 6:45 AM
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
