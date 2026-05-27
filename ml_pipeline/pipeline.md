# 🔧 RetailCore ML Pipeline — Documentación Técnica Completa
 
> Guía exhaustiva de cada módulo, su responsabilidad, sus entradas y salidas, y cómo ejecutar el pipeline completo.
 
---
 
## Índice
 
1. [Visión general](#1-visión-general)
2. [Cómo ejecutar el pipeline](#2-cómo-ejecutar-el-pipeline)
3. [Mapa de archivos](#3-mapa-de-archivos)
4. [configs/config.yaml](#4-configsconfigyaml)
5. [src/utils.py](#5-srcutilspy)
6. [src/azure/azure_client.py](#6-srcazureazure_clientpy)
7. [src/ingestion/ingest.py](#7-srcingestioningestpy)
8. [src/preprocessing/preprocess.py](#8-srcpreprocessingpreprocesspy)
9. [src/training/train.py](#9-srctrainingtrainpy)
10. [src/evaluation/evaluate.py](#10-srcevaluationevaluatepy)
11. [src/training/save_model.py](#11-srctrainingsave_modelpy)
12. [src/inference/predict.py](#12-srcinferencepredictpy)
13. [src/aemet/aemet_client.py](#13-srcaemetaemet_clientpy)
14. [src/monitoring/drift.py](#14-srcmonitoringdriftpy)
15. [pipeline.py](#15-pipelinepy)
16. [tests/test_pipeline.py](#16-teststest_pipelinepy)
17. [Flujo de datos de extremo a extremo](#17-flujo-de-datos-de-extremo-a-extremo)
18. [Qué falta por añadir](#18-qué-falta-por-añadir)
---
 
## 1. Visión general
 
El pipeline predice qué entregas van a fallar **antes de las 7:00 AM** del día de operación, para que los operadores puedan actuar: reagendar, cambiar franja horaria o enviar un SMS al destinatario. Procesa ~18.000 paquetes diarios en cuatro ciudades (Madrid, Barcelona, Valencia, Sevilla) combinando historial de entregas con datos meteorológicos en tiempo real de la API de AEMET.
 
La solución tiene dos modos de uso que comparten el mismo código:
 
- **Entrenamiento** (`pipeline.py`): lee el dataset histórico, entrena tres modelos, selecciona el mejor y lo guarda.
- **Inferencia** (`src/inference/predict.py`): carga el modelo guardado, enriquece los paquetes del día con datos AEMET y produce una lista priorizada de riesgos.
Todo el estado intermedio (modelos, artefactos, resultados) vive en **Azure Blob Storage**. El historial de predicciones y métricas va a **Azure SQL**. Los secretos (API keys, connection strings) viven en **Azure Key Vault**. Los experimentos de ML se registran en **MLflow**.
 
---
 
## 2. Cómo ejecutar el pipeline
 
### Requisitos previos
 
```bash
# 1. Instalar dependencias Python
pip install -r requirements.txt
 
# 2. Instalar driver ODBC para Azure SQL (Ubuntu/Debian)
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
  | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update && sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
 
# 3. Configurar credenciales Azure
# Opción A — variables de entorno (desarrollo local)
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
export AZURE_SQL_CONNECTION_STRING="Driver={ODBC Driver 18 for SQL Server};Server=tcp:..."
export AEMET_API_KEY="tu_api_key_de_aemet"
 
# Opción B — Key Vault + az login (recomendado)
az login
# El pipeline leerá los secretos automáticamente desde Key Vault
 
# 4. Tener el dataset en Blob Storage o en local
az storage blob upload \
  --container-name raw-data \
  --name deliveries_features.csv \
  --file deliveries_features.csv
# O copiarlo en: /tmp/retailcore/raw/deliveries_features.csv  (fallback local)
```
 
### Entrenamiento completo (pasos 1–5)
 
```bash
# Desde la raíz del repositorio
python pipeline.py
```
 
Esto ejecuta en orden: ingesta → preprocesado → entrenamiento → evaluación → guardado. Al terminar tendrás el modelo en `Blob Storage: models/best_model.pkl` y el experimento registrado en MLflow.
 
```bash
# Con config personalizada
python pipeline.py --config configs/config.yaml
```
 
### Entrenamiento + inferencia en un solo comando
 
```bash
# Entrena y luego predice los paquetes de hoy para Madrid con datos AEMET
python pipeline.py --infer --city madrid
 
# Para otra ciudad
python pipeline.py --infer --city barcelona
```
 
### Solo inferencia (uso diario, 6:50 AM)
 
```bash
# Con datos AEMET en tiempo real (por defecto)
python src/inference/predict.py --city madrid
 
# Especificando el nombre del blob de entrada
python src/inference/predict.py --city madrid --input-blob today_packages_2026-05-27.csv
 
# Sin AEMET (usa los datos meteorológicos que ya vienen en el CSV)
python src/inference/predict.py --city madrid --no-aemet
 
# Con fichero local en vez de Blob
python src/inference/predict.py --city sevilla --local-input /tmp/paquetes.csv
```
 
### Ver experimentos en MLflow
 
```bash
# En otra terminal mientras el pipeline corre o después
mlflow ui --backend-store-uri mlruns
# Abrir en el navegador: http://localhost:5000
```
 
### Ejecutar los tests
 
```bash
pytest tests/ -v
```
 
### Automatizar la inferencia diaria (producción)
 
```bash
# Añadir al crontab del servidor o Azure Container Instance
50 6 * * 1-6 cd /app && python src/inference/predict.py --city madrid >> logs/inference.log 2>&1
```
 
---
 
## 3. Mapa de archivos
 
```
ml_pipeline/
│
├── pipeline.py                          ← Orquestador. Punto de entrada único para entrenar.
├── configs/
│   └── config.yaml                      ← Toda la configuración. Único fichero que hay que editar.
│
├── src/
│   ├── utils.py                         ← Logger, load_config, save_pickle, timestamps.
│   │
│   ├── azure/
│   │   └── azure_client.py              ← Clientes Blob Storage, Azure SQL y Key Vault.
│   │
│   ├── ingestion/
│   │   └── ingest.py                    ← Paso 1: carga el CSV y lo valida.
│   │
│   ├── preprocessing/
│   │   └── preprocess.py                ← Paso 2: split, class weights, scaler stats, CSVs locales.
│   │
│   ├── training/
│   │   ├── train.py                     ← Paso 3: entrena LR + RF + XGBoost.
│   │   └── save_model.py                ← Paso 5: serializa y sube el mejor modelo.
│   │
│   ├── evaluation/
│   │   └── evaluate.py                  ← Paso 4: métricas, umbral óptimo, selección del mejor.
│   │
│   ├── inference/
│   │   └── predict.py                   ← Paso 6: inferencia batch diaria. Tiene su propio CLI.
│   │
│   ├── aemet/
│   │   └── aemet_client.py              ← Obtiene datos meteorológicos en tiempo real de AEMET.
│   │
│   └── monitoring/
│       └── drift.py                     ← Detecta data drift con PSI. No se llama desde pipeline.py.
│
└── tests/
    └── test_pipeline.py                 ← 10 tests unitarios de los módulos críticos.
```
 
---
 
## 4. `configs/config.yaml`
 
**Qué hace:** Es la única fuente de verdad de configuración. Todos los módulos lo leen a través de `load_config()` de `utils.py`. No hay valores hardcodeados en el código.
 
**Secciones principales:**
 
```yaml
azure:
  storage:
    account_name: "stretailcoreml"
    containers:
      raw_data: "raw-data"       # CSVs de entrada
      processed: "processed"     # artefactos de preprocesado
      models: "models"           # modelos .pkl
      reports: "reports"         # predicciones y comparativas
  sql:
    server: "sql-retailcore-ml.database.windows.net"
    database: "retailcore-predictions"
    tables:
      predictions: "delivery_predictions"
      model_metrics: "model_metrics"
      drift_alerts: "drift_alerts"
  mlflow:
    tracking_uri: ""             # vacío = usa mlruns/ local
    experiment_name: "retailcore-delivery-prediction"
    register_best_model: true
  key_vault:
    name: "kv-retailcore-ml"
    secrets:
      aemet_key: "aemet-api-key"
      sql_conn: "sql-connection-string"
      storage_conn: "storage-connection-string"
 
data:
  filename: "deliveries_features.csv"
  target: "delivery_failed"
  exclude_cols: [delivery_id, recipient_id, delivery_failed]
  test_size: 0.2
  val_size: 0.1
  random_state: 42
 
aemet:
  stations:
    madrid: "3195"
    barcelona: "0076"
    valencia: "8416"
    sevilla: "5783"
  thresholds:
    strong_wind_ms: 10.0
    adverse_weather_rain_mm: 5.0
 
models:
  candidates:
    logistic_regression: { enabled: true, C: 0.1, max_iter: 500 }
    random_forest:        { enabled: true, n_estimators: 300, max_depth: 12 }
    xgboost:              { enabled: true, n_estimators: 400, learning_rate: 0.05 }
 
evaluation:
  primary_metric: "avg_precision"
  threshold_search: { min: 0.2, max: 0.7, step: 0.02 }
 
inference:
  batch_size: 18000
  risk_levels:
    high:   { threshold_multiplier: 1.3, action: "REAGENDAR_SMS" }
    medium: { threshold_multiplier: 1.0, action: "CAMBIAR_FRANJA" }
    low:    { action: "ENTREGA_NORMAL" }
 
monitoring:
  drift_threshold: 0.05
  min_samples_for_drift: 1000
```
 
**Qué tocar para personalizar:**
- Para añadir una ciudad: agregar su estación AEMET en `aemet.stations`.
- Para deshabilitar un modelo: poner `enabled: false` en su entrada de `models.candidates`.
- Para cambiar la métrica de selección: editar `evaluation.primary_metric` (`avg_precision`, `roc_auc`, `f1_optimal`).
- Para ajustar el umbral de riesgo alto: editar `inference.risk_levels.high.threshold_multiplier`.
---
 
## 5. `src/utils.py`
 
**Qué hace:** Librería interna de utilidades usada por todos los módulos. No tiene lógica de negocio, solo infraestructura transversal.
 
**Funciones:**
 
| Función | Para qué |
|---|---|
| `get_logger(name)` | Devuelve un logger con formato `timestamp \| nivel \| módulo \| mensaje`. Todos los módulos lo usan para tener logs consistentes. |
| `load_config(path)` | Lee `config.yaml` y devuelve un dict. Se llama al inicio de `pipeline.py` y se pasa a todos los módulos. |
| `save_pickle(obj, path)` | Serializa cualquier objeto Python a `.pkl` con `protocol=5` (más rápido y compacto). Crea el directorio si no existe. |
| `load_pickle(path)` | Deserializa un `.pkl` desde disco. |
| `now_str()` | Timestamp en formato `YYYYMMDD_HHMMSS`. Se usa para nombrar artefactos. |
| `today_str()` | Fecha en formato `YYYY-MM-DD`. Se usa para nombrar CSVs de predicciones. |
 
**Quién lo usa:** Todos los módulos hacen `from src.utils import get_logger, ...` como primera importación.
 
---
 
## 6. `src/azure/azure_client.py`
 
**Qué hace:** Encapsula toda la comunicación con Azure en tres clases independientes más una fachada que las une. Es el único fichero que habla con los SDKs de Azure. El resto del código no importa nada de `azure.*` directamente.
 
**Clases:**
 
### `KeyVaultClient`
Lee secretos desde Azure Key Vault. Si Key Vault no está disponible (falta SDK o no hay conexión), busca el secreto como variable de entorno. El orden de prioridad es siempre: Key Vault → variable de entorno.
 
```python
kv = KeyVaultClient("kv-retailcore-ml")
api_key = kv.get_secret("aemet-api-key", env_fallback="AEMET_API_KEY")
```
 
### `BlobStorageClient`
Interfaz completa para Azure Blob Storage. Todas las lecturas y escrituras de ficheros del pipeline pasan por aquí.
 
| Método | Para qué |
|---|---|
| `download_csv(container, blob_name)` | Descarga un CSV y lo devuelve como DataFrame. Usado en ingesta e inferencia. |
| `download_pickle(container, blob_name)` | Descarga y deserializa un `.pkl`. Usado en inferencia para cargar el modelo. |
| `download_to_file(container, blob_name, local_path)` | Descarga a disco. Para ficheros grandes. |
| `upload_csv(df, container, blob_name)` | Sube un DataFrame como CSV. Usado en evaluate y predict. |
| `upload_pickle(obj, container, blob_name)` | Serializa y sube un objeto como `.pkl`. Usado en save_model. |
| `upload_file(local_path, container, blob_name)` | Sube un fichero local. |
| `blob_exists(container, blob_name)` | Comprueba si un blob existe antes de intentar descargarlo. |
| `list_blobs(container, prefix)` | Lista los blobs de un container con prefijo opcional. |
 
### `AzureSQLClient`
Persiste predicciones, métricas y alertas de drift en Azure SQL Database. Crea las tres tablas automáticamente si no existen (operación idempotente), por lo que no hay que ejecutar ningún DDL manual.
 
| Método | Para qué |
|---|---|
| `insert_predictions(df, city, model_version)` | Inserta el DataFrame de predicciones del día. Llamado desde `predict.py`. |
| `insert_model_metrics(metrics, model_name, mlflow_run_id)` | Guarda las métricas de evaluación del modelo. Llamado desde `save_model.py`. |
| `insert_drift_alerts(drift_result)` | Persiste las features con drift severo. Llamado externamente desde código de monitorización. |
| `get_recent_predictions(days)` | Recupera el resumen de predicciones de los últimos N días. Útil para informes y Power BI. |
 
**Tablas que crea en Azure SQL:**
 
```sql
delivery_predictions  -- una fila por paquete por día
  id, run_date, delivery_id, city, prob_fallo, risk_level, action, model_version, created_at
 
model_metrics         -- una fila por ejecución de entrenamiento
  id, run_date, model_name, roc_auc, avg_precision, f1_optimal, recall_fallo, best_threshold, mlflow_run_id, created_at
 
drift_alerts          -- una fila por feature con drift detectado
  id, alert_date, feature_name, psi_value, severity, created_at
```
 
### `AzureContext`
Fachada que inicializa los tres clientes en una sola llamada y se pasa a todos los módulos que necesitan Azure. La construcción falla de forma silenciosa: si Blob no está disponible, `ctx.blob` es `None` y el código usa el fallback local. Lo mismo para SQL y Key Vault.
 
```python
# En pipeline.py:
ctx = AzureContext.from_config(config)
# ctx.blob  → BlobStorageClient o None
# ctx.sql   → AzureSQLClient o None
# ctx.kv    → KeyVaultClient o None
```
 
**Autenticación en producción:** En Azure (VM, Container Instance, Azure Functions), `DefaultAzureCredential` detecta la Managed Identity automáticamente. No hace falta configurar nada extra ni poner credenciales en el código.
 
---
 
## 7. `src/ingestion/ingest.py`
 
**Qué hace:** Es el primer paso del pipeline. Responsabilidad única: obtener el DataFrame del dataset y garantizar que es válido antes de pasarlo al siguiente módulo.
 
**Función principal:** `run(config, azure_ctx) → pd.DataFrame`
 
**Lógica de carga (con fallback):**
1. Intenta descargar el CSV desde Blob Storage (`raw-data/deliveries_features.csv`).
2. Si falla (Blob no configurado, blob no existe), busca el fichero en disco local (`/tmp/retailcore/raw/deliveries_features.csv`).
3. Si tampoco existe en local, lanza `FileNotFoundError` con el comando exacto para subir el fichero.
**Validaciones que realiza:**
- Que existan las columnas críticas (`delivery_failed`, `recipient_failure_rate`, `driver_quality_score`, `weather_rain`, `weather_wind_speed`, `weather_temperature`).
- Que no haya nulos en esas columnas.
- Que el target `delivery_failed` tenga al menos dos clases distintas (si no, el entrenamiento no tiene sentido).
**Qué devuelve:** El DataFrame completo en memoria, sin escribir nada a disco. El módulo siguiente lo recibe directamente.
 
**Qué loguea a MLflow:** número de filas, número de columnas, tasa de fallos, fecha de ingesta, fuente de datos (blob o local).
 
**Qué NO hace:** no transforma datos, no hace split, no escala. Solo carga y valida.
 
---
 
## 8. `src/preprocessing/preprocess.py`
 
**Qué hace:** Segundo paso. Toma el DataFrame crudo y lo prepara para el entrenamiento. Produce todos los artefactos que necesitan los pasos siguientes: arrays numpy listos para sklearn, estadísticas del scaler y los pesos de clase.
 
**Función principal:** `run(df, config, azure_ctx) → dict`
 
**Transformaciones que aplica:**
 
1. **Conversión de booleanos a float32:** sklearn no acepta columnas booleanas en todos los contextos. Se convierten a 0.0 / 1.0.
2. **Separación features / target:** las columnas en `exclude_cols` (delivery_id, recipient_id, delivery_failed) se descartan. El resto son features.
3. **Cálculo de scaler stats:** para cada feature numérica se calcula la media y la desviación estándar sobre el conjunto de entrenamiento. Estas estadísticas se guardan en `scaler_stats.pkl` y se usan en inferencia para escalar los datos de AEMET al mismo espacio que el training. Si no se hiciese esto, las features meteorológicas estarían en unidades brutas (mm de lluvia, m/s de viento) mientras que el modelo espera valores z-normalizados.
4. **Split estratificado en tres conjuntos:**
   - `X_train` / `y_train`: 72% de los datos (80% × 90%). Para entrenar.
   - `X_val` / `y_val`: 8% (80% × 10%). Para early stopping o validación cruzada.
   - `X_test` / `y_test`: 20%. Solo se toca en evaluación. Nunca durante entrenamiento.
   - El split es estratificado, lo que garantiza que la proporción de fallos (~13%) es la misma en los tres conjuntos.
5. **Cálculo de class weights:** el dataset tiene un desequilibrio de ~7:1 entre éxitos y fallos. Se calculan pesos inversamente proporcionales a la frecuencia de cada clase con `compute_class_weight("balanced")`. Estos pesos se pasan a los modelos para que no ignoren la clase minoritaria.
**Guardado local:** guarda en `/tmp/retailcore/processed/` los ficheros `train.csv`, `val.csv`, `test.csv`, `scaler_stats.pkl` y `feature_cols.pkl`. La subida a Blob es **manual**: el pipeline no la hace automáticamente para que puedas inspeccionar los datos antes.
 
```bash
# Subida manual cuando estés listo
az storage blob upload-batch \
  --source /tmp/retailcore/processed \
  --destination processed
```
 
**Qué devuelve:** un dict con las claves:
 
| Clave | Tipo | Contenido |
|---|---|---|
| `X_train`, `X_val`, `X_test` | `np.ndarray` | Arrays de features |
| `y_train`, `y_val`, `y_test` | `np.ndarray` | Arrays del target |
| `feature_cols` | `list[str]` | Nombres de las features en orden |
| `class_weight` | `dict` | `{0: 1.0, 1: 6.8}` aprox. |
| `scaler_stats` | `dict` | `{"weather_rain": {"mean": 0.3, "std": 0.9}, ...}` |
| `train_df`, `val_df`, `test_df` | `pd.DataFrame` | DataFrames completos para inspección |
| `local_dir` | `Path` | Ruta donde se guardaron los CSVs locales |
 
---
 
## 9. `src/training/train.py`
 
**Qué hace:** Tercer paso. Itera sobre los modelos habilitados en `config.yaml`, construye un `sklearn.Pipeline` para cada uno y lo entrena con `X_train`.
 
**Función principal:** `run(data, config) → dict[str, Pipeline]`
 
**Modelos que entrena:**
 
### Logistic Regression
Envuelto en un `Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(...))])`. El scaler es necesario aquí porque LR es sensible a la escala de las features. Sirve como baseline y referencia de interpretabilidad.
 
Parámetros configurables en `config.yaml`: `C` (regularización), `max_iter`.
 
### Random Forest
`Pipeline([("clf", RandomForestClassifier(...))])`. No necesita scaler porque los árboles son invariantes a la escala. Maneja bien el desequilibrio de clases con `class_weight=class_weight`.
 
Parámetros configurables: `n_estimators`, `max_depth`, `min_samples_leaf`.
 
### XGBoost
`Pipeline([("clf", XGBClassifier(...))])`. El parámetro `scale_pos_weight` se calcula automáticamente como `n_negativos / n_positivos` para compensar el desequilibrio. Si XGBoost no está instalado, usa `GradientBoostingClassifier` de sklearn como fallback con un warning.
 
Parámetros configurables: `n_estimators`, `max_depth`, `learning_rate`, `subsample`, `colsample_bytree`.
 
**Gestión del desequilibrio:** los tres modelos reciben los `class_weight` calculados en preprocesado. Esto hace que penalicen más los errores en la clase minoritaria (fallos de entrega).
 
**Qué loguea a MLflow:** los hiperparámetros de cada modelo, prefijados con el nombre del modelo (ej: `random_forest__n_estimators: 300`).
 
**Qué devuelve:** `{"logistic_regression": pipeline_lr, "random_forest": pipeline_rf, "xgboost": pipeline_xgb}`. Los pipelines ya están entrenados y listos para llamar a `.predict_proba()`.
 
**Qué NO hace:** no evalúa, no selecciona, no guarda nada. Solo entrena y devuelve.
 
---
 
## 10. `src/evaluation/evaluate.py`
 
**Qué hace:** Cuarto paso. Evalúa todos los modelos entrenados sobre el test set (datos que ningún modelo ha visto durante el entrenamiento), selecciona el mejor y genera el reporte comparativo.
 
**Función principal:** `run(trained_models, data, config, azure_ctx) → dict`
 
**Por qué Average Precision y no AUC-ROC:**
Con un desequilibrio de ~7:1, el AUC-ROC puede dar valores altos incluso con un modelo que ignora los fallos. La Average Precision (área bajo la curva Precision-Recall) penaliza más los falsos negativos en la clase positiva y es más informativa con datasets desbalanceados.
 
**Búsqueda del umbral óptimo:**
En clasificación binaria, el umbral por defecto es 0.5, pero con clases desbalanceadas ese umbral suele ser demasiado conservador y produce pocos positivos predichos. El módulo barre umbrales de 0.20 a 0.70 en pasos de 0.02 y selecciona el que maximiza el F1-score en la clase de fallos. Este umbral óptimo se guarda en el artefacto del modelo y se usa en inferencia.
 
**Métricas calculadas por modelo:**
 
| Métrica | Qué mide |
|---|---|
| `roc_auc` | Capacidad discriminativa general |
| `avg_precision` | Calidad de las predicciones positivas (métrica principal) |
| `f1_optimal` | F1 con el umbral óptimo encontrado |
| `best_threshold` | Umbral que maximiza F1 en fallos |
| `recall_fallo` | % de fallos reales que el modelo detecta |
| `precision_fallo` | % de alarmas que son fallos reales |
| `tp`, `fp`, `tn`, `fn` | Valores absolutos de la matriz de confusión |
| `daily_detected` | Estimación de fallos detectados por día con 18K paquetes |
| `daily_false_alarms` | Estimación de falsas alarmas por día |
 
**Selección del mejor modelo:** el que tenga mayor `avg_precision` (configurable con `evaluation.primary_metric`).
 
**Feature importance:** para RF y XGBoost usa `feature_importances_`. Para LR usa los coeficientes absolutos. Se logrea el top 10 en consola y se guarda en `reports/feature_importance_{modelo}.json`.
 
**Outputs:**
- `reports/model_comparison.csv` (en Blob o local): tabla con todas las métricas de todos los modelos.
- Métricas del mejor modelo registradas en MLflow sin prefijo (para el resumen del experimento).
**Qué devuelve:** `{"best_name", "best_pipeline", "best_metrics", "all_metrics", "feature_importance"}`.
 
---
 
## 11. `src/training/save_model.py`
 
**Qué hace:** Quinto y último paso del entrenamiento. Serializa el mejor modelo con todos los metadatos necesarios para inferencia y lo persiste en tres lugares.
 
**Función principal:** `run(eval_result, data, config, azure_ctx) → str`
 
**Qué contiene el artefacto `.pkl`:**
 
```python
artifact = {
    "pipeline":       pipeline_sklearn,   # el modelo completo (scaler + clasificador)
    "feature_cols":   [...],              # lista ordenada de features esperadas
    "scaler_stats":   {...},              # media y std de cada feature (para AEMET)
    "best_threshold": 0.38,              # umbral óptimo calculado en evaluación
    "metrics":        {...},              # todas las métricas del test set
    "model_name":     "xgboost",         # nombre del mejor modelo
    "target":         "delivery_failed",
    "saved_at":       "20260527_065000", # timestamp de guardado
    "config_snapshot": {...}             # batch_size y risk_levels vigentes
}
```
 
Todo lo necesario para hacer inferencia está en un único fichero. No hay dependencias externas al `.pkl` en tiempo de inferencia (el scaler está dentro del pipeline de sklearn).
 
**Dónde guarda:**
 
1. **Local** (`/tmp/retailcore/models/retailcore_{modelo}.pkl`): caché inmediata para la inferencia local sin depender de Blob.
2. **Azure Blob Storage** (`models/retailcore_{modelo}.pkl` y `models/best_model.pkl`): alias canónico que siempre apunta al mejor modelo. La inferencia siempre lee `best_model.pkl`.
3. **MLflow Model Registry** (`retailcore-best-model`): para versionado y trazabilidad. Se puede deshabilitar con `azure.mlflow.register_best_model: false`.
4. **Azure SQL** (tabla `model_metrics`): las métricas del mejor modelo para consulta histórica y comparativa entre reentrenamientos.
**Qué devuelve:** el nombre del blob canónico (`"best_model.pkl"`), que `pipeline.py` puede pasar a la inferencia.
 
---
 
## 12. `src/inference/predict.py`
 
**Qué hace:** Motor de inferencia batch. Es el módulo que se ejecuta cada mañana a las 6:50 AM. Se puede lanzar solo o en cadena desde `pipeline.py`.
 
**Función principal:** `run(config, azure_ctx, city, use_aemet, input_blob, local_input) → pd.DataFrame`
 
**CLI propio:**
```bash
python src/inference/predict.py --city madrid
python src/inference/predict.py --city barcelona --no-aemet
python src/inference/predict.py --city madrid --input-blob today_packages_2026-05-27.csv
python src/inference/predict.py --city madrid --local-input /tmp/hoy.csv
```
 
**Flujo interno paso a paso:**
 
1. **Carga el modelo:** intenta descargarlo desde `Blob/models/best_model.pkl`. Si falla, lo busca en local `/tmp/retailcore/models/best_model.pkl`. Si tampoco existe, lanza error con instrucciones.
2. **Carga los paquetes del día:** busca en Blob el CSV `today_packages_YYYY-MM-DD.csv` (o el nombre que indiques con `--input-blob`). Fallback a `--local-input` si se especifica.
3. **Inyecta datos AEMET:** llama a `aemet_client.get_weather_features()` con la ciudad especificada. Los datos de lluvia, viento y temperatura se normalizan usando los `scaler_stats` guardados en el modelo (así están en el mismo espacio que durante el entrenamiento). Las columnas meteorológicas del CSV se sobreescriben con los valores actuales.
4. **Predice:** llama a `pipeline.predict_proba(X)[:, 1]` para obtener la probabilidad de fallo de cada paquete.
5. **Clasifica por nivel de riesgo:**
   - `HIGH` si `prob >= best_threshold * 1.3` → acción: `REAGENDAR_SMS`
   - `MEDIUM` si `prob >= best_threshold` → acción: `CAMBIAR_FRANJA`
   - `LOW` si `prob < best_threshold` → acción: `ENTREGA_NORMAL`
6. **Ordena el resultado** de mayor a menor probabilidad (los más urgentes primero).
7. **Guarda resultados:**
   - Blob: `reports/predictions_YYYY-MM-DD.csv` (todos los paquetes)
   - Blob: `reports/high_risk_YYYY-MM-DD.csv` (solo HIGH y MEDIUM)
   - Azure SQL: inserta todas las filas en `delivery_predictions`
   - Local: backup en `/tmp/retailcore/reports/predictions_YYYY-MM-DD.csv`
**Columnas que añade al CSV original:**
 
| Columna | Ejemplo | Descripción |
|---|---|---|
| `prob_fallo` | `0.7823` | Probabilidad predicha de fallo (0–1) |
| `risk_level` | `"HIGH"` | Nivel de riesgo (`HIGH`, `MEDIUM`, `LOW`) |
| `action` | `"REAGENDAR_SMS"` | Acción recomendada para el operador |
 
---
 
## 13. `src/aemet/aemet_client.py`
 
**Qué hace:** Cliente HTTP para la API pública de AEMET OpenData. Obtiene las condiciones meteorológicas actuales de la estación más cercana a cada ciudad y las transforma en features listas para el modelo.
 
**Clase principal:** `AEMETClient`
 
**Cómo funciona la API de AEMET (peculiaridad importante):**
La API de AEMET tiene un mecanismo en dos pasos: la primera petición devuelve una URL de datos, y hay que hacer una segunda petición a esa URL para obtener los datos reales. `_get()` gestiona esto con reintentos automáticos (3 intentos, 2 segundos de espera).
 
**Features que genera:**
 
| Feature | Fuente AEMET | Transformación |
|---|---|---|
| `weather_rain` | campo `prec` (mm) | z-score con scaler_stats del training |
| `weather_wind_speed` | campo `vv` (m/s) | z-score |
| `weather_temperature` | campo `ta` (°C) | z-score |
| `strong_wind` | `vv > 10 m/s` | binaria 0/1 |
| `adverse_weather` | `prec > 5 mm` | binaria 0/1 |
| `temp_category` | rangos de temperatura | categórica 0/1/2/3 |
 
**Función de entrada para el pipeline:** `get_weather_features(city, config, scaler_stats, api_key, use_fallback_if_error)`
 
**Fallback automático:** si la API falla (timeout, API key incorrecta, límite de peticiones), devuelve valores 0.0 para todas las features meteorológicas (equivalente a condiciones medias del training). Esto garantiza que la inferencia diaria nunca se bloquea por problemas externos.
 
**API key:** la función busca la clave en este orden: parámetro `api_key` → `AzureContext.get_aemet_key()` (Key Vault) → variable de entorno `AEMET_API_KEY`.
 
---
 
## 14. `src/monitoring/drift.py`
 
**Qué hace:** Detecta data drift, es decir, si la distribución de los datos de producción ha cambiado respecto a los datos de entrenamiento. Cuando el drift es severo, el modelo empieza a dar predicciones menos fiables y hay que reentrenar.
 
**⚠️ Importante:** este módulo NO se llama desde `pipeline.py`. Es una utilidad que hay que llamar externamente, por ejemplo desde un job periódico semanal o mensual.
 
**Ejemplo de uso:**
```python
from src.monitoring.drift import check_drift
import pickle, pandas as pd
 
with open("models/best_model.pkl", "rb") as f:
    artifact = pickle.load(f)
 
train_df = pd.read_csv("/tmp/retailcore/processed/train.csv")
current_df = pd.read_csv("data/raw/last_30_days.csv")
 
result = check_drift(train_df, current_df, artifact["feature_cols"], config)
# result["status"] → "OK" o "ALERT"
# result["features_with_drift"] → ["weather_rain", "recipient_failure_rate"]
```
 
**Métrica usada: PSI (Population Stability Index)**
 
El PSI compara la distribución de una feature en dos momentos dividiendo su rango en 10 buckets y midiendo la divergencia:
 
| PSI | Interpretación | Acción |
|---|---|---|
| < 0.10 | Sin drift | Ninguna |
| 0.10 – 0.20 | Drift moderado | Vigilar |
| > 0.20 | Drift severo | Reentrenar el modelo |
 
**Qué devuelve:**
 
```python
{
    "status": "ALERT",
    "overall_psi": 0.18,
    "features_with_drift": ["weather_rain", "driver_quality_score"],
    "details": {
        "weather_rain":          {"psi": 0.23, "severity": "ALERT"},
        "driver_quality_score":  {"psi": 0.21, "severity": "ALERT"},
        "recipient_failure_rate":{"psi": 0.04, "severity": "OK"},
        ...
    }
}
```
 
Los resultados con `severity != "OK"` se pueden insertar en Azure SQL con `azure_ctx.sql.insert_drift_alerts(result)` para trazabilidad.
 
---
 
## 15. `pipeline.py`
 
**Qué hace:** Orquestador. Ejecuta los cinco pasos del entrenamiento en orden dentro de un único `mlflow.start_run()`, de forma que todo el experimento queda registrado bajo el mismo run ID. Es el único fichero que hay que invocar para entrenar.
 
**Función `run_training_pipeline(config, azure_ctx)`:**
 
```
[1/5] ingest.run()       → df
[2/5] preprocess.run()   → data
[3/5] train.run()        → trained_models
[4/5] evaluate.run()     → eval_result
[5/5] save_model.run()   → model_blob
```
 
Cada paso recibe la salida del anterior. Si cualquier paso lanza una excepción, el MLflow run queda en estado `FAILED` y el pipeline se detiene con el error.
 
**Función `main()`:** parsea los argumentos CLI y llama a `run_training_pipeline`. Si se pasa `--infer`, después del entrenamiento llama a `predict.run()`.
 
**Argumentos CLI:**
 
| Argumento | Default | Descripción |
|---|---|---|
| `--config` | `configs/config.yaml` | Ruta al fichero de configuración |
| `--infer` | `False` | Si se activa, ejecuta inferencia tras entrenar |
| `--city` | `madrid` | Ciudad para AEMET en la inferencia post-entrenamiento |
 
**Lo que NO hace `pipeline.py`:**
- No llama a `drift.py` (eso es un job separado).
- No genera los datos sintéticos (eso es `data/generate_synthetic.py`).
- No despliega la API FastAPI (eso es `api/main.py`).
- No envía SMS (eso es Azure Logic Apps).
---
 
## 16. `tests/test_pipeline.py`
 
**Qué hace:** Suite de 10 tests unitarios que verifican los módulos más críticos sin necesitar Azure ni datos reales. Todos los tests son deterministas y rápidos (< 5 segundos en total).
 
**Cómo ejecutar:**
```bash
pytest tests/ -v
pytest tests/ -v -k "TestInference"   # solo una clase
pytest tests/ -v --tb=short           # tracebacks cortos
```
 
**Tests incluidos:**
 
| Clase | Test | Qué verifica |
|---|---|---|
| `TestIngestion` | `test_validate_ok` | Un DataFrame válido pasa la validación sin error |
| `TestIngestion` | `test_validate_missing_col` | Falta una columna crítica → `ValueError` |
| `TestIngestion` | `test_validate_only_one_class` | Target con una sola clase → `ValueError` |
| `TestInference` | `test_classify_high_risk` | `prob=0.8` con `threshold=0.5` → `HIGH, REAGENDAR_SMS` |
| `TestInference` | `test_classify_medium_risk` | `prob=0.55` → `MEDIUM, CAMBIAR_FRANJA` |
| `TestInference` | `test_classify_low_risk` | `prob=0.1` → `LOW, ENTREGA_NORMAL` |
| `TestInference` | `test_inject_weather` | Las columnas meteorológicas se sobreescriben correctamente |
| `TestMonitoring` | `test_psi_identical_distributions` | PSI de una distribución consigo misma ≈ 0 |
| `TestMonitoring` | `test_psi_different_distributions` | PSI entre N(0,1) y N(5,1) > 0.2 |
| `TestMonitoring` | `test_psi_returns_float` | `compute_psi` devuelve `float` siempre |
 
**Qué NO testean (pendiente añadir):**
- Tests de integración end-to-end con dataset real.
- Tests del cliente AEMET (requieren mock de HTTP).
- Tests del cliente Azure (requieren mock del SDK).
- Tests de `train.py` y `evaluate.py` con un dataset mínimo sintético.
---
 
## 17. Flujo de datos de extremo a extremo
 
```
ENTRENAMIENTO
─────────────
deliveries_features.csv
  (Blob: raw-data/)
        │
        ▼
[1] ingest.py
  └─ valida columnas, nulos, clases
        │ pd.DataFrame (en memoria)
        ▼
[2] preprocess.py
  └─ booleans → float
  └─ split estratificado 72/8/20
  └─ class weights {0:1.0, 1:~6.8}
  └─ scaler_stats {feature: {mean, std}}
  └─ guarda train/val/test.csv en local
        │ dict(X_train, y_train, ..., scaler_stats)
        ▼
[3] train.py
  └─ Pipeline LR (con StandardScaler)
  └─ Pipeline RF
  └─ Pipeline XGBoost
        │ dict(nombre → pipeline_entrenado)
        ▼
[4] evaluate.py
  └─ predict_proba en X_test
  └─ busca best_threshold (maximiza F1)
  └─ calcula roc_auc, avg_precision, recall...
  └─ selecciona mejor por avg_precision
  └─ sube model_comparison.csv a Blob
        │ dict(best_pipeline, best_metrics, ...)
        ▼
[5] save_model.py
  └─ artifact.pkl = {pipeline, feature_cols, scaler_stats, threshold, metrics, ...}
  └─ Blob: models/best_model.pkl          ← producción
  └─ Local: /tmp/retailcore/models/*.pkl  ← caché
  └─ MLflow Model Registry
  └─ Azure SQL: tabla model_metrics
 
 
INFERENCIA DIARIA (6:50 AM)
────────────────────────────
today_packages_YYYY-MM-DD.csv
  (Blob: raw-data/)
        │
        ▼
[6] predict.py
  ├─ descarga best_model.pkl desde Blob
  ├─ llama a aemet_client → {weather_rain: z, wind: z, temp: z, ...}
  ├─ sobreescribe columnas meteo del CSV con valores actuales
  ├─ pipeline.predict_proba(X) → prob_fallo[i]
  ├─ classify_risk(prob, threshold) → (HIGH/MEDIUM/LOW, acción)
  ├─ ordena por prob_fallo desc
  ├─ sube predictions_YYYY-MM-DD.csv a Blob (reports/)
  ├─ sube high_risk_YYYY-MM-DD.csv a Blob (reports/)
  └─ inserta en Azure SQL: tabla delivery_predictions
```
 
---
 
## 18. Qué falta por añadir
 
Estas piezas están referenciadas en el proyecto pero aún no existen como código:
 
| Módulo / fichero | Dónde encaja | Qué tiene que hacer |
|---|---|---|
| `data/generate_synthetic.py` | Antes del pipeline | Genera ~500K entregas sintéticas con tasa de fallos del 23% |
| `data/scraping_aemet.py` | Antes del pipeline | Descarga histórico meteorológico de AEMET y lo une al dataset por fecha y ciudad |
| `data/schema.sql` | Opcional | DDL completo de las tablas de Azure SQL (ya se crean automáticamente, pero sirve como documentación) |
| `api/main.py` | Después del pipeline | API FastAPI que expone el modelo para peticiones síncronas |
| `api/predict.py` | Dentro de la API | Endpoint `POST /predict` que recibe paquetes y devuelve predicciones |
| `api/scheduler.py` | Job autónomo | Llama a `predict.py` a las 6:45 AM diariamente |
| `src/monitoring/drift.py` (integración) | Job periódico | Hay que crear un script que llame a `check_drift()` y guarde alertas en SQL |
| `dashboard/retailcore.pbix` | Power BI | Informe conectado a Azure SQL con semáforo de riesgo y mapa de calor |
| `docs/metricas.md` | Documentación | Resultados del modelo con el dataset real |
| `docs/costes.md` | Documentación | Estimación de costes de los recursos Azure en producción |
| `.env.example` | Configuración | Plantilla de variables de entorno para desarrollo local |
| Tests de integración | `tests/` | Tests end-to-end con dataset sintético mínimo sin Azure |
| Tests del cliente AEMET | `tests/` | Mock de HTTP para probar `aemet_client.py` sin API key real |
