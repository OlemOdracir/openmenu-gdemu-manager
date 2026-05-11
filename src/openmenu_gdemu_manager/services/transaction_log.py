from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import __version__
from .sd_registry import registry_dir


TRANSACTIONS_FILE_NAME = "transactions.jsonl"


def transactions_path(root: Path) -> Path:
    return registry_dir(root) / TRANSACTIONS_FILE_NAME


def new_operation_id() -> str:
    return uuid.uuid4().hex


def append_transaction(root: Path, event: dict[str, Any]) -> Path:
    path = transactions_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "app_version": __version__,
        **event,
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return path


def read_transactions(root: Path) -> list[dict[str, Any]]:
    path = transactions_path(root)
    if not path.exists():
        return []
    result: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            result.append(json.loads(line))
    return result
