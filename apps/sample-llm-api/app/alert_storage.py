import asyncio
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


Comparator = Literal["gt", "lt"]
MetricKey = Literal[
    "request_rate_per_min",
    "token_rate_per_min",
    "p95_latency_seconds",
    "error_rate_percent",
    "estimated_cost_rate_per_hour",
    "retrieve_p95_seconds",
]
EvalWindow = Literal["1m", "5m", "15m"]


@dataclass
class AlertRule:
    id: str
    name: str
    metric: MetricKey
    comparator: Comparator
    threshold: float
    window: EvalWindow
    cooldown_seconds: int
    webhook_url: str
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_fired_at: float = 0.0
    last_value: float = 0.0


DEFAULT_STORE_PATH = Path(os.getenv("ALERT_RULES_PATH", "/var/lib/olly/alert_rules.json"))


class AlertStore:
    def __init__(self, path: Path = DEFAULT_STORE_PATH) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def list_rules(self) -> list[AlertRule]:
        async with self._lock:
            return self._read_all()

    async def get(self, rule_id: str) -> AlertRule | None:
        async with self._lock:
            for rule in self._read_all():
                if rule.id == rule_id:
                    return rule
        return None

    async def create(
        self,
        name: str,
        metric: MetricKey,
        comparator: Comparator,
        threshold: float,
        window: EvalWindow,
        cooldown_seconds: int,
        webhook_url: str,
    ) -> AlertRule:
        rule = AlertRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            name=name,
            metric=metric,
            comparator=comparator,
            threshold=threshold,
            window=window,
            cooldown_seconds=cooldown_seconds,
            webhook_url=webhook_url,
        )
        async with self._lock:
            rules = self._read_all()
            rules.append(rule)
            self._write_all(rules)
        return rule

    async def update_fired(self, rule_id: str, fired_at: float, last_value: float) -> None:
        async with self._lock:
            rules = self._read_all()
            for rule in rules:
                if rule.id == rule_id:
                    rule.last_fired_at = fired_at
                    rule.last_value = last_value
                    break
            self._write_all(rules)

    async def set_enabled(self, rule_id: str, enabled: bool) -> AlertRule | None:
        async with self._lock:
            rules = self._read_all()
            updated: AlertRule | None = None
            for rule in rules:
                if rule.id == rule_id:
                    rule.enabled = enabled
                    updated = rule
                    break
            self._write_all(rules)
        return updated

    async def delete(self, rule_id: str) -> bool:
        async with self._lock:
            rules = self._read_all()
            remaining = [rule for rule in rules if rule.id != rule_id]
            if len(remaining) == len(rules):
                return False
            self._write_all(remaining)
        return True

    def _read_all(self) -> list[AlertRule]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [AlertRule(**item) for item in payload]

    def _write_all(self, rules: list[AlertRule]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([asdict(rule) for rule in rules], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self._path)
