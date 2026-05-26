# 📦 RetailCore Logistics · Predictor de Fallos en Entrega
 
![Banner](img/banner.svg)
 
> **Tajamar Fight · Caso 01** — Sistema de predicción de fallos en entrega de última milla con IA explicable  
> **Equipo:** Alejandro Benítez · Borja Núñez · Marta Moreno · **Entrega:** 31/05/2026
 
---
 
## ✅ Tareas del proyecto
 
> **Estados:** ✅ Hecho · 🟡 En curso · ⚪ Pendiente · 🔴 AVISAR YA
 
---
 
### — DATOS —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Generar el dataset de entregas | ❓ Por asignar | ⚪ Pendiente |
| <sub>No tenemos datos reales, así que los fabricamos. Con Python generamos un fichero con ~500.000 entregas ficticias que incluyen: ciudad, zona, día de la semana, tipo de producto, si llovía, si fue primer intento o reintento, y si la entrega falló. La tasa de fallos debe rondar el 23%.</sub> | | |
| Descargar datos meteorológicos | ❓ Por asignar | ⚪ Pendiente |
| <sub>Usamos la API gratuita de AEMET para descargar lluvia y temperatura histórica en Madrid, Barcelona, Valencia y Sevilla. Luego lo unimos al dataset por fecha y ciudad.</sub> | | |
 
---
 
### — MODELO —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Preparar los datos para entrenar | ❓ Por asignar | ⚪ Pendiente |
| <sub>Los datos más antiguos serán para entrenar el modelo y los más recientes para comprobar si funciona bien. Nunca mezclamos ambos grupos, porque si no estaríamos haciendo trampa.</sub> | | |
| Entrenar y elegir el mejor modelo | ❓ Por asignar | ⚪ Pendiente |
| <sub>Probamos dos modelos (Random Forest y XGBoost) y nos quedamos con el que mejor detecte los fallos. El objetivo es que acierte en al menos el 80% de los casos (AUC-ROC ≥ 0.80). Lo guardamos en Azure ML.</sub> | | |
| Explicar por qué falla cada entrega | ❓ Por asignar | ⚪ Pendiente |
| <sub>Con una librería llamada SHAP hacemos que el modelo no solo diga "esta entrega va a fallar" sino también por qué: "porque llueve, es reintento y es viernes por la tarde". Eso es lo que verá el operador.</sub> | | |
 
---
 
### — SISTEMA —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Crear la API | ❓ Por asignar | ⚪ Pendiente |
| <sub>Construimos un servicio con FastAPI al que le mandas la lista de entregas del día y te devuelve cada una con su probabilidad de fallo y el motivo. Es lo que conecta el modelo con el dashboard y el resto del sistema.</sub> | | |
| Automatizar la predicción diaria | ❓ Por asignar | ⚪ Pendiente |
| <sub>Programamos un proceso automático en Azure que cada noche, antes de las 7:00 AM, coge las entregas del día siguiente, llama al modelo y guarda los resultados. Sin que nadie tenga que hacer nada.</sub> | | |
| Avisar a los destinatarios de riesgo | ❓ Por asignar | ⚪ Pendiente |
| <sub>Si una entrega tiene más del 70% de probabilidad de fallo, el sistema manda automáticamente un SMS al destinatario proponiéndole cambiar el horario. Lo hacemos con Azure Logic Apps.</sub> | | |
 
---
 
### — DASHBOARD —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Crear el panel para operadores | ❓ Por asignar | ⚪ Pendiente |
| <sub>Un informe en Power BI que cada mañana muestra la lista de entregas del día ordenada de mayor a menor riesgo, con un semáforo de colores y el motivo del fallo explicado en texto normal. Sin tecnicismos.</sub> | | |
| ⭐ Añadir mapa de zonas de riesgo | ❓ Por asignar | ⚪ Pendiente |
| <sub>Dentro del dashboard, un mapa de las 4 ciudades que colorea las zonas según cuántas entregas en riesgo tienen ese día. De un vistazo el operador sabe dónde se van a concentrar los problemas.</sub> | | |
 
---
 
### — ENTREGA —
 
| Tarea | Responsable | Estado |
|---|---|---|
| Hacer funcionar todo junto | ❓ Por asignar | ⚪ Pendiente |
| <sub>Ejecutar el sistema completo de principio a fin: generamos datos, el modelo predice, la API responde y el dashboard lo muestra. Si esto funciona, el proyecto está listo.</sub> | | |
| Preparar la presentación | ❓ Por asignar | ⚪ Pendiente |
| <sub>Slides y demo en directo para el jurado. Hay que explicar el problema, cómo lo resolvemos, cuánto costaría en producción y por qué nuestra solución es mejor que la del otro grupo.</sub> | | |
 
---
 
## 🗺️ Línea temporal
 
![Timeline](img/timeline.svg)
 
---
 
## 🏗️ Arquitectura de la solución
 
![Arquitectura](img/arquitectura.svg)
 
```
┌─────────────────────────────────────────────────────────────────┐
│  CAPA 1 · DATOS                                                 │
│  Datos sintéticos + scraping AEMET ──► PostgreSQL ──► Azure Blob│
├─────────────────────────────────────────────────────────────────┤
│  CAPA 2 · MACHINE LEARNING  (Azure ML)                          │
│  XGBoost / RF ──► SHAP ──► Azure ML Registry ──► Endpoint      │
├─────────────────────────────────────────────────────────────────┤
│  CAPA 3 · BACKEND                                               │
│  FastAPI ──► Azure Functions (job 7AM) ──► Logic Apps (SMS)    │
├─────────────────────────────────────────────────────────────────┤
│  CAPA 4 · SALIDA OPERATIVA                                      │
│  Power BI Dashboard · Lista priorizada · Mapa de calor ⭐       │
└─────────────────────────────────────────────────────────────────┘
```
 
---
 
## ⭐ Diferenciadores frente a la competencia
 
| Diferenciador | Qué aporta al cliente |
|---|---|
| **Explicación por entrega** | No solo "alto riesgo", sino "falla porque llueve + centro + lunes + reintento" |
| **SMS automático** | El sistema avisa al destinatario solo, sin intervención humana |
| **Mapa de zonas de riesgo** | Vista geográfica intuitiva para operadores no técnicos |
| **Dashboard sin tecnicismos** | Cualquier operador lo entiende el primer día, sin formación en IA |
 
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
│   └── schema.sql                    # Esquema PostgreSQL
│
├── 📂 ml_pipeline/
│   ├── etl_limpieza.ipynb            # ETL, exploración y limpieza
│   ├── feature_engineering.ipynb     # Feature engineering completo
│   ├── train_model.ipynb             # Entrenamiento XGBoost / RF
│   └── shap_explainability.ipynb     # SHAP
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
│   └── costes.md                     # Estimación de costes en producción
│
├── .env.example
├── requirements.txt
└── README.md
```
 
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
# Editar .env con credenciales de Azure y PostgreSQL
 
# 4. Generar datos sintéticos
python data/generate_synthetic.py
 
# 5. Lanzar la API
uvicorn api.main:app --reload
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
feat: generar dataset sintético con señales de fallo reales
fix: corregir join meteorología por ciudad
docs: añadir tabla de features a docs/features.md
```
 
