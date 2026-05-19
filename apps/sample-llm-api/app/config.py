import os
from dataclasses import dataclass


def _float_from_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number, got {raw_value!r}") from exc


@dataclass(frozen=True)
class Settings:
    llm_backend: str
    local_compute_resource: str
    local_compute_hourly_usd: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_backend=os.getenv("LLM_BACKEND", "mock").lower(),
            local_compute_resource=os.getenv("LOCAL_COMPUTE_RESOURCE", "cpu").lower(),
            local_compute_hourly_usd=_float_from_env("LOCAL_COMPUTE_HOURLY_USD", 0.05),
        )
