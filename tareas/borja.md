# ⚙️ Borja Núñez — Data Engineer

← [Volver al README principal](../README.md)

**Rol:** Data Engineering · Generación de datos sintéticos · ETL · PostgreSQL · Azure Blob

---

## 🎯 Responsabilidad en el proyecto

Borja es el responsable de que los datos existan, sean limpios y estén disponibles para el modelo. Como no tenemos datos históricos reales del cliente, Borja diseña y genera un dataset sintético realista que replica el comportamiento operativo de RetailCore.

---

## 📋 Tareas detalladas

### 📊 Diseño y generación del dataset

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 1 | Diseño del esquema de datos | Definir columnas del dataset: entrega_id, fecha, zona, destinatario_id, tipo_producto, repartidor_id, franja_horaria, resultado (0/1) | ⚪ Pendiente |
| 2 | Generación sintética base | Script Python: 18.000 paquetes/día × 180 días históricos = ~3.2M registros | ⚪ Pendiente |
| 3 | Inyección de señales reales de fallo | Ajustar probabilidades de fallo por zona (centro histórico +8%), día (lunes -5%, viernes +12%), tipo producto (requiere firma +15%), etc. | ⚪ Pendiente |
| 4 | Generación de historial de destinatarios | Crear tabla de destinatarios con su historial de fallos anterior | ⚪ Pendiente |
| 5 | Generación de datos de repartidores | Tabla de repartidores con su carga media y zonas asignadas | ⚪ Pendiente |
| 6 | Validar distribución 23% de fallos | Verificar que el dataset generado tiene una tasa de fallo ~23% como la real | ⚪ Pendiente |

### 🌤️ Datos externos

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 7 | Scraping meteorológico AEMET | Extraer datos históricos de lluvia, temperatura y viento en Madrid, BCN, Valencia y Sevilla para las fechas del dataset | ⚪ Pendiente |
| 8 | Unir meteorología con entregas | Join por fecha + ciudad en el dataset principal | ⚪ Pendiente |

### 🗄️ Base de datos y almacenamiento

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 9 | Diseñar esquema PostgreSQL | Tablas: `entregas`, `destinatarios`, `repartidores`, `zonas`, `meteorologia` | ⚪ Pendiente |
| 10 | Crear base de datos local | Docker + PostgreSQL 16 para desarrollo local | ⚪ Pendiente |
| 11 | Script de carga a PostgreSQL | `load_to_postgres.py`: carga el dataset generado con control de errores | ⚪ Pendiente |
| 12 | Subida a Azure Blob Storage | Subir los CSVs a `raw/` en el Blob. Organización: `raw/YYYY-MM-DD/entregas.csv` | ⚪ Pendiente |

### 🔧 ETL y limpieza

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 13 | Notebook ETL principal | `etl_limpieza.ipynb`: exploración, % nulos, outliers, distribuciones | ⚪ Pendiente |
| 14 | Limpieza de nulos | Estrategia por columna: imputar mediana, imputar moda o eliminar fila | ⚪ Pendiente |
| 15 | Detección y tratamiento de outliers | Tiempos de entrega anómalos, coordenadas erróneas | ⚪ Pendiente |
| 16 | Dataset limpio a Azure Blob | Subir a `processed/` una vez limpio el dataset | ⚪ Pendiente |

---

## 📦 Ficheros que genera Borja

```
data/
├── generate_synthetic.py         ← Generación del dataset completo
├── scraping_aemet.py             ← Scraping meteorológico AEMET
├── load_to_postgres.py           ← Carga a PostgreSQL
└── schema.sql                    ← Esquema de tablas

ml_pipeline/
└── etl_limpieza.ipynb            ← ETL y limpieza exploratoria
```

---

## 🛠️ Stack técnico de Borja

- **Python:** pandas, numpy, faker, requests (AEMET API)
- **PostgreSQL 16:** Base de datos operativa (Docker local + Azure PostgreSQL Flexible en prod)
- **Azure Blob Storage:** Almacenamiento de datos raw y procesados
- **Jupyter:** Notebooks de exploración y ETL

---

## 📌 Criterios de éxito

- Dataset sintético con ≥ 500.000 registros y distribución de fallo ~23%
- Las señales de fallo son realistas y correlacionadas (ej: lluvia → más fallos en centro histórico)
- Esquema PostgreSQL documentado y funcional
- Pipeline ETL reproducible: ejecutar `generate_synthetic.py` + `load_to_postgres.py` desde cero sin errores

---

## 🔗 Dependencias con el resto del equipo

- **→ Alejandro:** Borja entrega el dataset limpio en `processed/` para que Alejandro haga el feature engineering
- **→ Marta:** Borja entrega el esquema de PostgreSQL para que Marta lo conecte a la API
