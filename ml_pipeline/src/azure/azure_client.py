"""
azure/azure_client.py — Cliente centralizado para todos los recursos Azure
=============================================================================
Encapsula:
  - Azure Blob Storage  → datos, modelos, reports
  - Azure SQL Database  → historial de predicciones y métricas
  - Azure Key Vault     → secretos (AEMET key, connection strings)

Autenticación:
  - Local/dev:       variables de entorno (AZURE_STORAGE_CONNECTION_STRING, etc.)
  - Producción/AML:  DefaultAzureCredential → Managed Identity automática

No hay credenciales en código. Nunca.
=============================================================================
"""
import io
import os
import sys
import pickle
import tempfile
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, date

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger

logger = get_logger("azure_client")

# ── Imports Azure SDK (con guards por si no están instalados) ─────────────────
try:
    from azure.storage.blob import BlobServiceClient, BlobClient
    from azure.identity import DefaultAzureCredential
    BLOB_AVAILABLE = True
except ImportError:
    BLOB_AVAILABLE = False
    logger.warning("azure-storage-blob no instalado. Blob Storage no disponible.")

try:
    import pyodbc
    SQL_AVAILABLE = True
except ImportError:
    SQL_AVAILABLE = False
    logger.warning("pyodbc no instalado. Azure SQL no disponible.")

try:
    from azure.keyvault.secrets import SecretClient
    KEYVAULT_AVAILABLE = True
except ImportError:
    KEYVAULT_AVAILABLE = False
    logger.warning("azure-keyvault-secrets no instalado. Key Vault no disponible.")


# =============================================================================
# KEY VAULT CLIENT
# =============================================================================
class KeyVaultClient:
    """
    Lee secretos desde Azure Key Vault.
    Fallback: busca el secreto como variable de entorno si KV no está disponible.
    """

    def __init__(self, vault_name: str):
        self.vault_url = f"https://{vault_name}.vault.azure.net"
        self._client = None
        if KEYVAULT_AVAILABLE:
            try:
                credential = DefaultAzureCredential()
                self._client = SecretClient(vault_url=self.vault_url, credential=credential)
                logger.info(f"🔑 Key Vault conectado: {vault_name}")
            except Exception as e:
                logger.warning(f"No se pudo conectar a Key Vault ({e}). Usando env vars.")

    def get_secret(self, secret_name: str, env_fallback: Optional[str] = None) -> Optional[str]:
        """
        Obtiene un secreto. Orden de prioridad:
          1. Azure Key Vault
          2. Variable de entorno (env_fallback o secret_name en mayúsculas)
        """
        # Intentar Key Vault
        if self._client:
            try:
                return self._client.get_secret(secret_name).value
            except Exception as e:
                logger.warning(f"Key Vault: no se pudo leer '{secret_name}': {e}")

        # Fallback a variable de entorno
        env_var = env_fallback or secret_name.upper().replace("-", "_")
        value = os.environ.get(env_var)
        if value:
            logger.debug(f"Secreto '{secret_name}' leído desde env var {env_var}")
            return value

        logger.error(f"Secreto '{secret_name}' no encontrado en Key Vault ni en env vars")
        return None


# =============================================================================
# BLOB STORAGE CLIENT
# =============================================================================
class BlobStorageClient:
    """
    Interfaz para Azure Blob Storage.
    Todas las operaciones de lectura/escritura de datos y modelos pasan por aquí.
    """

    def __init__(self, connection_string: str):
        if not BLOB_AVAILABLE:
            raise ImportError("Instala azure-storage-blob: pip install azure-storage-blob")
        self._service = BlobServiceClient.from_connection_string(connection_string)
        logger.info("📦 Blob Storage conectado")

    # ── Descarga ──────────────────────────────────────────────────────────────

    def download_csv(self, container: str, blob_name: str) -> pd.DataFrame:
        """Descarga un CSV desde Blob y lo devuelve como DataFrame."""
        logger.info(f"⬇️  Blob → CSV: {container}/{blob_name}")
        blob = self._service.get_blob_client(container=container, blob=blob_name)
        data = blob.download_blob().readall()
        return pd.read_csv(io.BytesIO(data))

    def download_pickle(self, container: str, blob_name: str) -> Any:
        """Descarga un .pkl desde Blob y lo deserializa."""
        logger.info(f"⬇️  Blob → PKL: {container}/{blob_name}")
        blob = self._service.get_blob_client(container=container, blob=blob_name)
        data = blob.download_blob().readall()
        return pickle.loads(data)

    def download_to_file(self, container: str, blob_name: str, local_path: Path) -> Path:
        """Descarga un blob a disco local (para archivos grandes)."""
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob = self._service.get_blob_client(container=container, blob=blob_name)
        with open(local_path, "wb") as f:
            f.write(blob.download_blob().readall())
        logger.info(f"⬇️  Blob → Local: {container}/{blob_name} → {local_path}")
        return local_path

    # ── Subida ────────────────────────────────────────────────────────────────

    def upload_csv(self, df: pd.DataFrame, container: str, blob_name: str) -> None:
        """Sube un DataFrame como CSV a Blob Storage."""
        logger.info(f"⬆️  CSV → Blob: {container}/{blob_name} ({len(df):,} filas)")
        blob = self._service.get_blob_client(container=container, blob=blob_name)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        blob.upload_blob(csv_bytes, overwrite=True)

    def upload_pickle(self, obj: Any, container: str, blob_name: str) -> None:
        """Serializa y sube un objeto Python a Blob Storage como .pkl."""
        logger.info(f"⬆️  PKL → Blob: {container}/{blob_name}")
        blob = self._service.get_blob_client(container=container, blob=blob_name)
        blob.upload_blob(pickle.dumps(obj, protocol=5), overwrite=True)

    def upload_file(self, local_path: Path, container: str, blob_name: str) -> None:
        """Sube un archivo local a Blob Storage."""
        logger.info(f"⬆️  Local → Blob: {local_path} → {container}/{blob_name}")
        blob = self._service.get_blob_client(container=container, blob=blob_name)
        with open(local_path, "rb") as f:
            blob.upload_blob(f, overwrite=True)

    def blob_exists(self, container: str, blob_name: str) -> bool:
        blob = self._service.get_blob_client(container=container, blob=blob_name)
        return blob.exists()

    def list_blobs(self, container: str, prefix: str = "") -> list[str]:
        container_client = self._service.get_container_client(container)
        return [b.name for b in container_client.list_blobs(name_starts_with=prefix)]


# =============================================================================
# AZURE SQL CLIENT
# =============================================================================
class AzureSQLClient:
    """
    Interfaz para Azure SQL Database.
    Guarda historial de predicciones, métricas y alertas de drift.
    """

    # DDL para crear las tablas si no existen
    _DDL = {
        "delivery_predictions": """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='delivery_predictions' AND xtype='U')
            CREATE TABLE delivery_predictions (
                id              BIGINT IDENTITY(1,1) PRIMARY KEY,
                run_date        DATE NOT NULL,
                delivery_id     NVARCHAR(50),
                city            NVARCHAR(50),
                prob_fallo      FLOAT,
                risk_level      NVARCHAR(10),
                action          NVARCHAR(30),
                model_version   NVARCHAR(100),
                created_at      DATETIME2 DEFAULT GETDATE()
            )
        """,
        "model_metrics": """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='model_metrics' AND xtype='U')
            CREATE TABLE model_metrics (
                id              INT IDENTITY(1,1) PRIMARY KEY,
                run_date        DATE NOT NULL,
                model_name      NVARCHAR(100),
                roc_auc         FLOAT,
                avg_precision   FLOAT,
                f1_optimal      FLOAT,
                recall_fallo    FLOAT,
                best_threshold  FLOAT,
                mlflow_run_id   NVARCHAR(100),
                created_at      DATETIME2 DEFAULT GETDATE()
            )
        """,
        "drift_alerts": """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='drift_alerts' AND xtype='U')
            CREATE TABLE drift_alerts (
                id              INT IDENTITY(1,1) PRIMARY KEY,
                alert_date      DATE NOT NULL,
                feature_name    NVARCHAR(100),
                psi_value       FLOAT,
                severity        NVARCHAR(10),
                created_at      DATETIME2 DEFAULT GETDATE()
            )
        """,
    }

    def __init__(self, connection_string: str):
        if not SQL_AVAILABLE:
            raise ImportError("Instala pyodbc: pip install pyodbc")
        self._conn_str = connection_string
        self._ensure_tables()
        logger.info("🗄️  Azure SQL conectado")

    def _get_conn(self):
        return pyodbc.connect(self._conn_str, timeout=30)

    def _ensure_tables(self) -> None:
        """Crea las tablas si no existen (idempotente)."""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                for table_name, ddl in self._DDL.items():
                    cursor.execute(ddl)
                conn.commit()
            logger.info("   ✅ Tablas SQL verificadas")
        except Exception as e:
            logger.warning(f"No se pudieron crear/verificar tablas SQL: {e}")

    def insert_predictions(self, df: pd.DataFrame, city: str, model_version: str) -> int:
        """
        Inserta el DataFrame de predicciones del día en Azure SQL.
        Devuelve el número de filas insertadas.
        """
        required = ["prob_fallo", "risk_level", "action"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.error(f"Columnas faltantes para insertar predicciones: {missing}")
            return 0

        today = date.today().isoformat()
        rows = []
        for _, row in df.iterrows():
            rows.append((
                today,
                str(row.get("delivery_id", "")),
                city,
                float(row["prob_fallo"]),
                str(row["risk_level"]),
                str(row["action"]),
                model_version,
            ))

        sql = """
            INSERT INTO delivery_predictions
                (run_date, delivery_id, city, prob_fallo, risk_level, action, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, rows)
                conn.commit()
            logger.info(f"   📝 SQL: {len(rows):,} predicciones insertadas")
            return len(rows)
        except Exception as e:
            logger.error(f"Error insertando predicciones en SQL: {e}")
            return 0

    def insert_model_metrics(self, metrics: dict, model_name: str, mlflow_run_id: str = "") -> None:
        """Guarda las métricas del modelo entrenado."""
        sql = """
            INSERT INTO model_metrics
                (run_date, model_name, roc_auc, avg_precision, f1_optimal,
                 recall_fallo, best_threshold, mlflow_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self._get_conn() as conn:
                conn.cursor().execute(sql, (
                    date.today().isoformat(),
                    model_name,
                    metrics.get("roc_auc", 0),
                    metrics.get("avg_precision", 0),
                    metrics.get("f1_optimal", 0),
                    metrics.get("recall_fallo", 0),
                    metrics.get("best_threshold", 0.5),
                    mlflow_run_id,
                ))
                conn.commit()
            logger.info(f"   📝 SQL: métricas de {model_name} guardadas")
        except Exception as e:
            logger.error(f"Error insertando métricas en SQL: {e}")

    def insert_drift_alerts(self, drift_result: dict) -> None:
        """Guarda alertas de drift en SQL para trazabilidad."""
        details = drift_result.get("details", {})
        if not details:
            return
        rows = [
            (date.today().isoformat(), feat, info["psi"], info["severity"])
            for feat, info in details.items()
            if info["severity"] != "OK"
        ]
        if not rows:
            return
        sql = """
            INSERT INTO drift_alerts (alert_date, feature_name, psi_value, severity)
            VALUES (?, ?, ?, ?)
        """
        try:
            with self._get_conn() as conn:
                conn.cursor().executemany(sql, rows)
                conn.commit()
            logger.info(f"   📝 SQL: {len(rows)} alertas de drift guardadas")
        except Exception as e:
            logger.error(f"Error insertando drift alerts en SQL: {e}")

    def get_recent_predictions(self, days: int = 7) -> pd.DataFrame:
        """Recupera predicciones de los últimos N días para monitorización."""
        sql = f"""
            SELECT run_date, city, risk_level, action, COUNT(*) as total,
                   AVG(prob_fallo) as avg_prob
            FROM delivery_predictions
            WHERE run_date >= DATEADD(day, -{days}, GETDATE())
            GROUP BY run_date, city, risk_level, action
            ORDER BY run_date DESC
        """
        try:
            with self._get_conn() as conn:
                return pd.read_sql(sql, conn)
        except Exception as e:
            logger.error(f"Error leyendo predicciones recientes: {e}")
            return pd.DataFrame()


# =============================================================================
# AZURE CONTEXT — Fachada que inicializa todos los clientes
# =============================================================================
class AzureContext:
    """
    Punto de entrada único para todos los recursos Azure.
    Se inicializa una vez en pipeline.py y se pasa a cada módulo.

    Uso:
        ctx = AzureContext.from_config(config)
        df = ctx.blob.download_csv("raw-data", "deliveries_features.csv")
        ctx.sql.insert_predictions(results_df, city="madrid", model_version="v1")
    """

    def __init__(
        self,
        blob: Optional["BlobStorageClient"] = None,
        sql: Optional["AzureSQLClient"] = None,
        kv: Optional["KeyVaultClient"] = None,
    ):
        self.blob = blob
        self.sql = sql
        self.kv = kv

    @classmethod
    def from_config(cls, config: dict) -> "AzureContext":
        """
        Construye el AzureContext leyendo credenciales en este orden:
          1. Key Vault (si está configurado)
          2. Variables de entorno
        """
        az_cfg = config["azure"]
        kv_cfg = az_cfg.get("key_vault", {})

        # ── Key Vault ─────────────────────────────────────────────────────────
        kv = None
        if kv_cfg.get("name"):
            try:
                kv = KeyVaultClient(kv_cfg["name"])
            except Exception as e:
                logger.warning(f"Key Vault no disponible: {e}")

        # ── Blob Storage ──────────────────────────────────────────────────────
        blob = None
        conn_str = _get_secret(kv, kv_cfg.get("secrets", {}).get("storage_conn"),
                               "AZURE_STORAGE_CONNECTION_STRING")
        if conn_str and BLOB_AVAILABLE:
            try:
                blob = BlobStorageClient(conn_str)
            except Exception as e:
                logger.error(f"❌ No se pudo conectar a Blob Storage: {e}")
        elif not conn_str:
            logger.warning("⚠️  AZURE_STORAGE_CONNECTION_STRING no configurada. Blob Storage desactivado.")

        # ── Azure SQL ─────────────────────────────────────────────────────────
        sql = None
        sql_conn = _get_secret(kv, kv_cfg.get("secrets", {}).get("sql_conn"),
                               "AZURE_SQL_CONNECTION_STRING")
        if sql_conn and SQL_AVAILABLE:
            try:
                sql = AzureSQLClient(sql_conn)
            except Exception as e:
                logger.error(f"❌ No se pudo conectar a Azure SQL: {e}")
        elif not sql_conn:
            logger.warning("⚠️  AZURE_SQL_CONNECTION_STRING no configurada. SQL desactivado.")

        connected = []
        if blob: connected.append("Blob Storage")
        if sql:  connected.append("Azure SQL")
        if kv:   connected.append("Key Vault")
        logger.info(f"☁️  Azure conectado: {', '.join(connected) if connected else 'ningún recurso'}")

        return cls(blob=blob, sql=sql, kv=kv)

    def get_aemet_key(self, config: dict) -> Optional[str]:
        """Obtiene la API key de AEMET desde Key Vault o env var."""
        kv_cfg = config["azure"].get("key_vault", {})
        secret_name = kv_cfg.get("secrets", {}).get("aemet_key", "aemet-api-key")
        return _get_secret(self.kv, secret_name, "AEMET_API_KEY")


def _get_secret(kv: Optional[KeyVaultClient], kv_name: Optional[str], env_var: str) -> Optional[str]:
    """Helper: busca un secreto en KV primero, luego en env var."""
    if kv and kv_name:
        val = kv.get_secret(kv_name, env_fallback=env_var)
        if val:
            return val
    return os.environ.get(env_var)
