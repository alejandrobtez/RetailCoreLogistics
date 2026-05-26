# 📦 RetailCore Logistics · Predictor de Fallos en Entrega
 
![Banner](img/banner.svg)
 
> **Tajamar Fight · Caso 01** — Sistema de predicción de fallos en entrega de última milla con IA explicable  
> **Equipo:** Alejandro Benítez · Borja Núñez · Marta Moreno · **Entrega:** 31/05/2026
 
---
 
## ✅ Tareas del proyecto
 
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

> **Estados:** ✅ Hecho · 🟡 En curso · ⚪ Pendiente · 🔴 AVISAR YA
 
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
│  ⭐ What-If Tool · Counterfactuals DiCE                         │
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
| **What-If Tool** | El operador simula "¿qué pasa si cambio la franja a la tarde?" antes de decidir |
| **Counterfactuals (DiCE)** | El sistema explica qué habría que cambiar para evitar el fallo |
| **Mapa de calor Power BI** | Vista geográfica de zonas de riesgo, intuitiva para operadores no técnicos |
| **SMS proactivo antes 7:00 AM** | Notificación automática al destinatario con alternativas de horario |
| **Explicación por entrega** | No solo "alto riesgo", sino "falla porque llueve + centro + lunes + reintento" |
 
---
 
## 💰 Estimación de costes en producción
 
> Detalle completo → [`docs/costes.md`](docs/costes.md)
 
| Servicio | Coste estimado/mes |
|---|---|
| Azure ML (endpoint + compute) | ~60 € |
| Azure PostgreSQL Flexible | ~30 € |
| Azure Blob Storage | ~5 € |
| Azure Functions + Logic Apps | ~12 € |
| Power BI Premium Per User | ~20 € |
| **Total estimado** | **~127 €/mes** |
 
---
 
## 📁 Estructura del repositorio
 
```
retailcore-predictor/
│
├── 📂 assets/
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
│   └── shap_explainability.ipynb     # SHAP + What-If + Counterfactuals
│
├── 📂 api/
│   ├── main.py                       # FastAPI app
│   ├── predict.py                    # Endpoint /predict
│   ├── report.py                     # Endpoint /report/today
│   └── scheduler.py                  # Job automático 6:45 AM
│
├── 📂 dashboard/
│   └── retailcore.pbix               # Power BI report
│
├── 📂 docs/
│   ├── features.md                   # Tabla de features documentadas
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
git clone https://github.com/team# RetailCore Logistics · Predictor de Fallos en Entrega

![Banner](img/banner.svg)

> **Tajamar Fight · Caso 01** · Predicción de fallos en entrega de última milla con IA explicable  
> **Entrega:** 22/06/2026 · **Stack:** Azure ML · XGBoost · FastAPI · SHAP · Power BI

---

![Equipo](img/equipo.svg)

| Miembro | Rol | Detalle de tareas |
|---|---|---|
| Alejandro Benítez | ML Lead | [📄 ver tareas](team/alejandro.md) |
| Borja Núñez | Data Engineer | [📄 ver tareas](team/borja.md) |
| Marta Moreno | Backend & Frontend Lead | [📄 ver tareas](team/marta.md) |

---

## 🎯 El problema que resolvemos

RetailCore mueve **18.000 paquetes/día** en Madrid, Barcelona, Valencia y Sevilla. Su tasa de fallo en primer intento es del **23%** — cada fallo cuesta dinero: el repartidor vuelve al hub, el paquete se reintenta y el cliente puede devolver el pedido.

**Nuestra solución:** un sistema que, antes de las 7:00 AM, genera una lista priorizada de las entregas con mayor riesgo de fallo ese día, junto con una explicación concreta de por qué se va a fallar — para que el operador pueda actuar.

---

## 🗺️ Arquitectura de la solución

![Arquitectura](img/arquitectura.svg)

```
┌─────────────────────────────────────────────────────────────────┐
│  CAPA 1 · DATOS                                                 │
│  Datos sintéticos + scraping ──► PostgreSQL ──► Azure Blob      │
├─────────────────────────────────────────────────────────────────┤
│  CAPA 2 · MACHINE LEARNING  (Azure ML)                          │
│  XGBoost / RF ──► SHAP Explainability ──► Azure ML Registry    │
│  ⭐ What-If Tool · Counterfactuals (diferenciador)              │
├─────────────────────────────────────────────────────────────────┤
│  CAPA 3 · BACKEND                                               │
/retailcore-predictor.git
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
