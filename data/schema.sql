-- Tabla para las predicciones diarias
CREATE TABLE delivery_predictions (
    id SERIAL PRIMARY KEY,
    delivery_id VARCHAR(50) NOT NULL,
    risk_level VARCHAR(20),
    probability FLOAT,
    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla para el rendimiento del modelo
CREATE TABLE model_metrics (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100),
    avg_precision FLOAT,
    roc_auc FLOAT,
    evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);