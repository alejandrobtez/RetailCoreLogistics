"""
utils.py — Utilidades compartidas por todos los módulos del pipeline
"""
import logging
import yaml
import pickle
from pathlib import Path
from typing import Any
from datetime import datetime


# =============================================================================
# LOGGING
# =============================================================================
def get_logger(name: str) -> logging.Logger:
    """Logger estándar con formato consistente para todo el pipeline."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# =============================================================================
# CONFIG
# =============================================================================
def load_config(config_path: str = "configs/config.yaml") -> dict:
    """Carga el archivo YAML de configuración."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# =============================================================================
# PERSISTENCIA
# =============================================================================
def save_pickle(obj: Any, path: Path, protocol: int = 5) -> None:
    """Serializa cualquier objeto Python a pkl."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=protocol)


def load_pickle(path: Path) -> Any:
    """Deserializa un objeto desde pkl."""
    with open(path, "rb") as f:
        return pickle.load(f)


# =============================================================================
# TIMESTAMPS
# =============================================================================
def now_str(fmt: str = "%Y%m%d_%H%M%S") -> str:
    return datetime.now().strftime(fmt)


def today_str(fmt: str = "%Y-%m-%d") -> str:
    return datetime.now().strftime(fmt)
