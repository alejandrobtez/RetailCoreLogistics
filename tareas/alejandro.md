# 🧠 Alejandro Benítez — ML Lead

← [Volver al README principal](../README.md)

**Rol:** Machine Learning Lead · Azure ML · Modelos predictivos · Explicabilidad

---

## 🎯 Responsabilidad en el proyecto

Alejandro es el responsable de todo el pipeline de Machine Learning: desde el feature engineering hasta el registro del modelo en producción, pasando por la explicabilidad con SHAP y los diferenciadores técnicos (What-If y Counterfactuals).

---

## 📋 Tareas detalladas

### 🔧 Feature Engineering

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 1 | Variables temporales | Día de la semana (0-6), franja horaria asignada (mañana/tarde/noche), si es festivo | ⚪ Pendiente |
| 2 | Variable de zona | One-hot encoding: residencial, oficinas, polígono industrial, centro histórico | ⚪ Pendiente |
| 3 | Variable meteorológica | Unir datos AEMET: lluvia (mm), temperatura (°C), viento (km/h), niebla (0/1) | ⚪ Pendiente |
| 4 | Historial del destinatario | Tasa de fallo histórica del destinatario (últimas 10 entregas), nº intentos previos fallidos | ⚪ Pendiente |
| 5 | Tipo de producto | Flags: requiere_firma, frágil, voluminoso, alto_valor (precio > 100€) | ⚪ Pendiente |
| 6 | Primer intento vs. reintento | Variable binaria `es_reintento` (0/1) + `num_intento` (1, 2, 3...) | ⚪ Pendiente |
| 7 | Carga del repartidor | Número de entregas asignadas ese día, ratio cargas pesadas / total | ⚪ Pendiente |
| 8 | Anti-leakage | Verificar que ninguna feature usa info posterior a la fecha de la prueba | ⚪ Pendiente |
| 9 | Documentación features | Tabla en `docs/features.md`: nombre, descripción, unidad, rango, cómo se calcula | ⚪ Pendiente |

### 🤖 Entrenamiento del modelo

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 10 | Split temporal | Train: datos hasta 3 meses atrás. Test: último mes. Nunca split aleatorio | ⚪ Pendiente |
| 11 | Baseline: Random Forest | `n_estimators=200`, `max_depth=8`, validación cruzada temporal k=5 | ⚪ Pendiente |
| 12 | Modelo principal: XGBoost | `learning_rate=0.05`, `n_estimators=500`, `scale_pos_weight` para desbalanceo | ⚪ Pendiente |
| 13 | Métricas de evaluación | AUC-ROC (principal), Precision, Recall, F1, umbral de decisión óptimo | ⚪ Pendiente |
| 14 | Comparar modelos | Si diferencia AUC < 2% → Random Forest (más interpretable). Si no → XGBoost | ⚪ Pendiente |
| 15 | Registrar en Azure ML | Subir con nombre `retailcore-fallo-predictor`, versión, métricas y fecha | ⚪ Pendiente |
| 16 | Documentar métricas | Añadir tabla de resultados a `docs/metricas.md` | ⚪ Pendiente |

### 🔍 Explicabilidad — diferenciadores clave

| # | Tarea | Detalle | Estado |
|---|---|---|---|
| 17 | SHAP básico | Para cada predicción: top 3 factores con su efecto en probabilidad (+/-) | ⚪ Pendiente |
| 18 | ⭐ What-If Tool | Interfaz/función que permite cambiar una feature (ej: franja horaria) y ver cómo cambia la probabilidad de fallo sin reentrenar | ⚪ Pendiente |
| 19 | ⭐ Counterfactuals | Para cada entrega de alto riesgo: "¿qué habría que cambiar para que la prob. de fallo baje del 30%?" — usando `DiCE` o similar | ⚪ Pendiente |
| 20 | Validación operativa | Ejecutar SHAP + counterfactuals sobre 10 entregas reales y verificar que la explicación tiene sentido para un operador | ⚪ Pendiente |

---

## 📦 Ficheros que genera Alejandro

```
ml_pipeline/
├── feature_engineering.ipynb     ← Features + anti-leakage
├── train_model.ipynb             ← Training XGBoost / RF
├── shap_explainability.ipynb     ← SHAP + What-If + Counterfactuals
└── register_model.py             ← Registro en Azure ML

docs/
├── features.md                   ← Tabla de todas las features
└── metricas.md                   ← Resultados del modelo
```

---

## 🛠️ Stack técnico de Alejandro

- **Azure ML:** Workspace, Experiments, Model Registry, Online Endpoint
- **XGBoost / Scikit-learn:** Entrenamiento y evaluación
- **SHAP:** Explicabilidad local y global
- **DiCE (Diverse Counterfactual Explanations):** Counterfactuals ⭐
- **Python:** pandas, numpy, matplotlib, seaborn

---

## 📌 Criterios de éxito

- AUC-ROC ≥ 0.80 en el conjunto de test temporal
- Cada predicción incluye top 3 factores explicados en lenguaje natural
- El What-If Tool responde en < 1 segundo
- Los counterfactuals son accionables por el operador (ej: "cambiar franja a tarde reduce riesgo un 40%")
