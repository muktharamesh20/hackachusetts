"""Central configuration, loaded from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    return float(val) if val is not None else default


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    return int(val) if val is not None else default


@dataclass(frozen=True)
class SimConfig:
    time_step: float = _get_float("PANTRYSORT_SIM_TIME_STEP", 1e-3)
    realtime_rate: float = _get_float("PANTRYSORT_SIM_REALTIME_RATE", 1.0)
    meshcat: bool = _get_bool("PANTRYSORT_MESHCAT", True)
    # Render a gripper camera and identify items by decoding their QR stickers.
    qr_scanner: bool = _get_bool("PANTRYSORT_QR_SCANNER", True)


@dataclass(frozen=True)
class PolicyConfig:
    backend: str = os.getenv("PANTRYSORT_POLICY_BACKEND", "scripted")
    lerobot_policy_path: str = os.getenv("PANTRYSORT_LEROBOT_POLICY_PATH", "")
    device: str = os.getenv("PANTRYSORT_DEVICE", "cpu")


@dataclass(frozen=True)
class InventoryConfig:
    db_url: str = os.getenv("PANTRYSORT_DB_URL", "sqlite:///pantry.db")
    expiry_warn_days: int = _get_int("PANTRYSORT_EXPIRY_WARN_DAYS", 14)


@dataclass(frozen=True)
class Config:
    sim: SimConfig
    policy: PolicyConfig
    inventory: InventoryConfig
    log_level: str = os.getenv("PANTRYSORT_LOG_LEVEL", "INFO")

    @classmethod
    def load(cls) -> "Config":
        return cls(
            sim=SimConfig(),
            policy=PolicyConfig(),
            inventory=InventoryConfig(),
        )


CONFIG = Config.load()
