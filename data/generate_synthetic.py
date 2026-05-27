"""
generate_synthetic.py — Generación del dataset sintético de RetailCore Logistics
=================================================================================
Genera un CSV con ~500.000 entregas ficticias que replican el esquema del
dataset real del proyecto (deliveries_synthetic.csv).

Columnas generadas:
  delivery_id, date, hour, day_of_week, is_holiday, zone, zone_type,
  recipient_id, recipient_failure_rate, num_previous_attempts,
  driver_id, driver_quality_score, driver_delivery_load,
  product_type, requires_signature, is_fragile, is_bulky, weight_kg,
  weather_rain, weather_wind_speed, weather_temperature,
  is_retry, delivery_failed

Lógica del target (delivery_failed):
  El fallo NO es aleatorio. Se modela con una probabilidad logística que
  combina los factores reales que causan fallos en última milla:
    - Lluvia intensa → más fallos
    - Viento fuerte → más fallos
    - Temperatura extrema (frío o calor) → más fallos
    - Zona de centro histórico → muchos más fallos (acceso difícil)
    - Zona industrial → pocos fallos (acceso fácil, horario amplio)
    - Hora punta (13-15h) → más fallos (tráfico)
    - Es un reintento → más fallos (destinatario problemático)
    - Alta tasa histórica del destinatario → más fallos
    - Bajo score del conductor → más fallos
    - Producto frágil o bulky → más fallos (requiere más cuidado)
    - Festivo → más fallos (destinatario puede no estar)
    - Lunes y viernes → más fallos (picos de volumen)

  La tasa de fallos resultante está calibrada para rondar el 23%.

Uso:
    python data/generate_synthetic.py
    python data/generate_synthetic.py --rows 500000 --output data/raw/deliveries_synthetic.csv
    python data/generate_synthetic.py --rows 50000 --seed 42  # versión rápida para pruebas
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================================
# CONFIGURACIÓN POR DEFECTO
# =============================================================================
DEFAULT_ROWS   = 500_000
DEFAULT_OUTPUT = "data/raw/deliveries_synthetic.csv"
DEFAULT_SEED   = 42

# Ciudades y sus tipos de zona con pesos de distribución
CITIES = {
    "madrid":    {"residential": 0.40, "historic_center": 0.20, "offices": 0.25, "industrial": 0.15},
    "barcelona": {"residential": 0.42, "historic_center": 0.22, "offices": 0.22, "industrial": 0.14},
    "valencia":  {"residential": 0.45, "historic_center": 0.18, "offices": 0.20, "industrial": 0.17},
    "sevilla":   {"residential": 0.43, "historic_center": 0.25, "offices": 0.18, "industrial": 0.14},
}

PRODUCT_TYPES = ["standard", "fragile", "bulky", "high_value", "signature_required"]
PRODUCT_WEIGHTS = [0.45, 0.20, 0.12, 0.13, 0.10]

# Festivos nacionales España 2024 (ampliados para cubrir festivos locales aprox.)
HOLIDAYS_2024 = {
    "01-01", "01-06", "03-28", "03-29", "04-01",  # Año nuevo, Reyes, Semana Santa
    "05-01", "08-15", "10-12", "11-01", "12-06",   # Lab, Asunción, Hispanidad, Todos los Santos, Constitución
    "12-08", "12-25",                               # Inmaculada, Navidad
}

# Franja horaria de reparto: 8h a 18h
HOURS = list(range(8, 19))   # [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

# Clima sintético por ciudad y mes (medias históricas aproximadas)
# (mes → (prob_lluvia, media_viento_m/s, media_temp_°C, std_temp))
CLIMATE = {
    "madrid": {
        1:  (0.10, 3.5, 5.0,  4.0),  2:  (0.09, 4.0, 7.0,  4.0),
        3:  (0.10, 4.5, 10.0, 4.5),  4:  (0.12, 4.0, 13.0, 4.0),
        5:  (0.10, 3.5, 17.0, 4.0),  6:  (0.05, 3.0, 23.0, 3.5),
        7:  (0.03, 3.0, 27.0, 3.0),  8:  (0.03, 2.8, 26.5, 3.0),
        9:  (0.07, 3.0, 21.0, 3.5),  10: (0.10, 3.5, 15.0, 4.0),
        11: (0.12, 3.8, 9.0,  4.0),  12: (0.11, 3.5, 5.5,  4.0),
    },
    "barcelona": {
        1:  (0.10, 4.5, 8.0,  3.5),  2:  (0.09, 5.0, 9.0,  3.5),
        3:  (0.10, 5.0, 11.0, 3.5),  4:  (0.12, 4.5, 14.0, 3.5),
        5:  (0.10, 4.0, 18.0, 3.5),  6:  (0.06, 3.5, 23.0, 3.0),
        7:  (0.04, 3.0, 26.5, 2.5),  8:  (0.06, 3.0, 27.0, 2.5),
        9:  (0.11, 3.5, 23.0, 3.0),  10: (0.13, 4.0, 18.0, 3.5),
        11: (0.13, 4.5, 12.0, 3.5),  12: (0.12, 4.5, 9.0,  3.5),
    },
    "valencia": {
        1:  (0.08, 3.5, 10.0, 3.5),  2:  (0.08, 4.0, 11.0, 3.5),
        3:  (0.08, 4.0, 13.0, 3.5),  4:  (0.10, 3.5, 16.0, 3.5),
        5:  (0.08, 3.0, 20.0, 3.5),  6:  (0.04, 2.5, 25.0, 3.0),
        7:  (0.02, 2.5, 28.0, 2.5),  8:  (0.04, 2.5, 28.5, 2.5),
        9:  (0.10, 3.0, 24.0, 3.0),  10: (0.13, 3.5, 19.0, 3.5),
        11: (0.12, 4.0, 14.0, 3.5),  12: (0.10, 3.5, 11.0, 3.5),
    },
    "sevilla": {
        1:  (0.10, 3.5, 10.0, 4.0),  2:  (0.09, 4.0, 12.0, 4.0),
        3:  (0.10, 4.0, 15.0, 4.0),  4:  (0.10, 3.5, 18.0, 4.0),
        5:  (0.07, 3.0, 23.0, 4.0),  6:  (0.03, 2.5, 29.0, 3.5),
        7:  (0.01, 2.5, 34.0, 3.0),  8:  (0.01, 2.5, 33.5, 3.0),
        9:  (0.06, 3.0, 27.0, 3.5),  10: (0.10, 3.5, 21.0, 4.0),
        11: (0.12, 4.0, 15.0, 4.0),  12: (0.11, 3.5, 11.0, 4.0),
    },
}


# =============================================================================
# GENERADORES DE ENTIDADES
# =============================================================================

def _generate_dates(n: int, rng: np.random.Generator) -> pd.Series:
    """Genera fechas aleatorias dentro del año 2024."""
    start = pd.Timestamp("2024-01-01")
    end   = pd.Timestamp("2024-12-31")
    days  = (end - start).days
    offsets = rng.integers(0, days + 1, size=n)
    return pd.to_datetime(start) + pd.to_timedelta(offsets, unit="D")


def _is_holiday(date: pd.Timestamp) -> int:
    return int(date.strftime("%m-%d") in HOLIDAYS_2024)


def _generate_weather(city: str, month: int, n: int, rng: np.random.Generator) -> tuple:
    """
    Genera clima sintético coherente con la climatología real de cada ciudad.
    La lluvia es binaria (llovió ese día o no). El viento y temperatura
    siguen distribuciones normales calibradas por ciudad y mes.
    """
    prob_lluvia, media_viento, media_temp, std_temp = CLIMATE[city][month]

    rain  = rng.binomial(1, prob_lluvia, n).astype(int)
    wind  = np.clip(rng.normal(media_viento, media_viento * 0.4, n), 0.01, None).round(2)
    temp  = rng.normal(media_temp, std_temp, n).round(1)

    # En días de lluvia, el viento es ligeramente mayor y la temp más baja
    wind  = np.where(rain == 1, wind * rng.uniform(1.1, 1.4, n), wind).round(2)
    temp  = np.where(rain == 1, temp - rng.uniform(1, 3, n), temp).round(1)

    return rain, wind, temp


def _failure_probability(row: dict) -> float:
    """
    Calcula la probabilidad de fallo para una entrega usando una función
    logística que combina múltiples señales reales. Los coeficientes están
    calibrados para producir una tasa media de ~23%.

    Cada término suma o resta al logit (log-odds) del fallo.
    """
    logit = -2.8  # intercepto → baseline ~5.7% antes de factores

    # ── Clima ──────────────────────────────────────────────────────────────
    logit += row["weather_rain"] * 1.1         # lluvia: factor más fuerte
    if row["weather_wind_speed"] > 10:
        logit += 0.5                            # viento fuerte
    elif row["weather_wind_speed"] > 7:
        logit += 0.2
    if abs(row["weather_temperature"]) < 2:    # helada
        logit += 0.6
    elif row["weather_temperature"] > 35:      # calor extremo
        logit += 0.3

    # ── Zona ───────────────────────────────────────────────────────────────
    zone_effect = {
        "historic_center": 0.9,   # casco histórico: muy difícil acceso
        "residential":     0.0,   # neutro
        "offices":        -0.1,   # oficinas: acceso relativamente fácil en horario
        "industrial":     -0.5,   # industrial: porteros, plataformas, fácil
    }
    logit += zone_effect.get(row["zone_type"], 0.0)

    # ── Hora del día ───────────────────────────────────────────────────────
    hour = row["hour"]
    if hour in (13, 14):           # hora de comer: menos gente en casa
        logit += 0.5
    elif hour in (8, 9):           # temprano: bueno
        logit -= 0.2
    elif hour in (17, 18):         # tarde-noche: algo mejor
        logit -= 0.1

    # ── Día de la semana ───────────────────────────────────────────────────
    dow = row["day_of_week"]
    if dow == 0:                   # lunes: volumen alto post-fin de semana
        logit += 0.3
    elif dow == 4:                 # viernes: gente sale antes de casa
        logit += 0.2
    elif dow in (5, 6):            # fin de semana: destinatarios en casa
        logit -= 0.3

    # ── Festivo ────────────────────────────────────────────────────────────
    if row["is_holiday"]:
        logit += 0.4               # destinatario puede haber salido

    # ── Historial del destinatario ─────────────────────────────────────────
    logit += row["recipient_failure_rate"] * 2.5  # tasa histórica alta → mal señal

    # ── Conductor ─────────────────────────────────────────────────────────
    logit -= row["driver_quality_score"] * 1.5    # score alto → baja prob fallo
    if row["driver_delivery_load"] > 40:
        logit += 0.4               # sobrecargado → más fallos

    # ── Reintento ─────────────────────────────────────────────────────────
    if row["is_retry"]:
        logit += 0.7               # ya falló antes → más probable que falle de nuevo

    # ── Tipo de producto ──────────────────────────────────────────────────
    product_effect = {
        "fragile":           0.3,
        "bulky":             0.4,
        "high_value":        0.2,   # destinatario suele estar esperando
        "signature_required":0.5,   # requiere firma → fácil que no esté
        "standard":          0.0,
    }
    logit += product_effect.get(row["product_type"], 0.0)

    if row["requires_signature"]:
        logit += 0.2               # si hay firma requerida encima del tipo
    if row["is_bulky"]:
        logit += 0.1
    if row["weight_kg"] > 20:
        logit += 0.2               # paquetes muy pesados: más tiempo, más fallos

    # ── Número de intentos previos ────────────────────────────────────────
    logit += row["num_previous_attempts"] * 0.5

    # Convertir logit a probabilidad
    return 1.0 / (1.0 + np.exp(-logit))


# =============================================================================
# GENERACIÓN PRINCIPAL
# =============================================================================

def generate(n_rows: int = DEFAULT_ROWS, seed: int = DEFAULT_SEED) -> pd.DataFrame:
    print(f"Generando {n_rows:,} entregas sintéticas (seed={seed})...")
    rng = np.random.default_rng(seed)

    # ── Listas de entidades ────────────────────────────────────────────────
    n_recipients = max(2000, n_rows // 25)
    n_drivers    = max(200,  n_rows // 250)

    recipient_ids    = np.arange(n_recipients)
    recipient_rates  = rng.beta(2, 8, n_recipients)   # sesgo hacia tasas bajas (~0.2 media)

    driver_ids       = [f"driver_{i:04d}" for i in range(n_drivers)]
    driver_scores    = np.clip(rng.normal(0.65, 0.15, n_drivers), 0.1, 1.0)  # 0-1, media ~0.65

    # ── Fechas ─────────────────────────────────────────────────────────────
    dates = _generate_dates(n_rows, rng)

    # ── Ciudades y zonas ───────────────────────────────────────────────────
    city_names = list(CITIES.keys())
    city_idx   = rng.integers(0, len(city_names), n_rows)
    zones      = [city_names[i] for i in city_idx]

    zone_types = []
    for city in zones:
        zt_names   = list(CITIES[city].keys())
        zt_weights = list(CITIES[city].values())
        zone_types.append(rng.choice(zt_names, p=zt_weights))

    # ── Clima (vectorizado por lotes fecha+ciudad para eficiencia) ─────────
    rain_arr  = np.zeros(n_rows, dtype=int)
    wind_arr  = np.zeros(n_rows)
    temp_arr  = np.zeros(n_rows)

    for city in city_names:
        for month in range(1, 13):
            mask = np.array(
                [(dates[i].month == month and zones[i] == city) for i in range(n_rows)]
            )
            idx = np.where(mask)[0]
            if len(idx) == 0:
                continue
            r, w, t = _generate_weather(city, month, len(idx), rng)
            rain_arr[idx] = r
            wind_arr[idx] = w
            temp_arr[idx] = t

    # ── Otras features ─────────────────────────────────────────────────────
    hours           = rng.choice(HOURS, n_rows)
    day_of_week     = np.array([d.dayofweek for d in dates])
    is_holiday      = np.array([_is_holiday(d) for d in dates])
    rec_idx         = rng.integers(0, n_recipients, n_rows)
    rec_failure_rates = np.round(recipient_rates[rec_idx], 3)
    num_prev_attempts = rng.choice([0, 1, 2, 3], n_rows, p=[0.70, 0.20, 0.07, 0.03])
    drv_idx         = rng.integers(0, n_drivers, n_rows)
    drv_scores      = np.round(driver_scores[drv_idx], 3)
    drv_load        = rng.integers(5, 60, n_rows)
    product_types   = rng.choice(PRODUCT_TYPES, n_rows, p=PRODUCT_WEIGHTS)
    requires_sig    = (product_types == "signature_required").astype(int)
    is_fragile      = (product_types == "fragile").astype(int)
    is_bulky        = (product_types == "bulky").astype(int)
    weight_kg       = np.round(np.where(
        is_bulky == 1,
        rng.uniform(10, 35, n_rows),
        rng.exponential(3.5, n_rows) + 0.2
    ), 2)
    is_retry        = (num_prev_attempts > 0).astype(int)

    # ── Calcular delivery_failed con la función logística ──────────────────
    print("  Calculando probabilidades de fallo...")
    probs = np.zeros(n_rows)
    for i in range(n_rows):
        if i % 100_000 == 0 and i > 0:
            print(f"    {i:,}/{n_rows:,} ({i/n_rows:.0%})")
        probs[i] = _failure_probability({
            "weather_rain":          rain_arr[i],
            "weather_wind_speed":    wind_arr[i],
            "weather_temperature":   temp_arr[i],
            "zone_type":             zone_types[i],
            "hour":                  hours[i],
            "day_of_week":           day_of_week[i],
            "is_holiday":            is_holiday[i],
            "recipient_failure_rate":rec_failure_rates[i],
            "driver_quality_score":  drv_scores[i],
            "driver_delivery_load":  drv_load[i],
            "is_retry":              is_retry[i],
            "product_type":          product_types[i],
            "requires_signature":    requires_sig[i],
            "is_bulky":              is_bulky[i],
            "weight_kg":             weight_kg[i],
            "num_previous_attempts": num_prev_attempts[i],
        })

    delivery_failed = rng.binomial(1, probs).astype(int)
    actual_rate = delivery_failed.mean()
    print(f"  Tasa de fallos generada: {actual_rate:.2%}")

    # ── Construir DataFrame ────────────────────────────────────────────────
    df = pd.DataFrame({
        "delivery_id":             [f"dlv_{i:08d}" for i in range(n_rows)],
        "date":                    [d.strftime("%Y-%m-%d") for d in dates],
        "hour":                    hours,
        "day_of_week":             day_of_week,
        "is_holiday":              is_holiday,
        "zone":                    zones,
        "zone_type":               zone_types,
        "recipient_id":            recipient_ids[rec_idx],
        "recipient_failure_rate":  rec_failure_rates,
        "num_previous_attempts":   num_prev_attempts,
        "driver_id":               [driver_ids[i] for i in drv_idx],
        "driver_quality_score":    drv_scores,
        "driver_delivery_load":    drv_load,
        "product_type":            product_types,
        "requires_signature":      requires_sig,
        "is_fragile":              is_fragile,
        "is_bulky":                is_bulky,
        "weight_kg":               weight_kg,
        "weather_rain":            rain_arr,
        "weather_wind_speed":      wind_arr,
        "weather_temperature":     temp_arr,
        "is_retry":                is_retry,
        "delivery_failed":         delivery_failed,
    })

    return df


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="RetailCore — Generador de dataset sintético de entregas"
    )
    parser.add_argument("--rows",   type=int,  default=DEFAULT_ROWS,
                        help=f"Número de entregas a generar (default: {DEFAULT_ROWS:,})")
    parser.add_argument("--output", type=str,  default=DEFAULT_OUTPUT,
                        help=f"Ruta de salida del CSV (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--seed",   type=int,  default=DEFAULT_SEED,
                        help=f"Semilla aleatoria para reproducibilidad (default: {DEFAULT_SEED})")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = generate(n_rows=args.rows, seed=args.seed)

    print(f"\nGuardando en {output_path}...")
    df.to_csv(output_path, index=False)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n✅ Dataset generado:")
    print(f"   Filas:         {len(df):,}")
    print(f"   Columnas:      {df.shape[1]}")
    print(f"   Tasa de fallos:{df['delivery_failed'].mean():.2%}")
    print(f"   Fichero:       {output_path} ({size_mb:.1f} MB)")
    print(f"\n   Distribución por ciudad:")
    city_stats = df.groupby("zone")["delivery_failed"].agg(["count", "mean"])
    city_stats.columns = ["entregas", "tasa_fallos"]
    print(city_stats.to_string())
    print(f"\n   Top 5 correlaciones con delivery_failed:")
    corrs = df.select_dtypes(include="number").corr()["delivery_failed"].drop("delivery_failed")
    print(corrs.abs().sort_values(ascending=False).head(5).to_string())


if __name__ == "__main__":
    main()
