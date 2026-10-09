"""Bounded, read-only diagnosis of the optional root GDEMU.ini.

Supported constraints: https://gdemu.wordpress.com/operation/gdemu-operation/
A missing file is not corruption; firmware may retain previous card settings.
No settings are inferred, repaired or written by this module.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re

MAX_CONFIG_BYTES = 64 * 1024
RANGES = {
    "open_time": (150, 5000), "detect_time": (150, 5000),
    "image_tests": (0, 1), "high_speed": (0, 1),
    "reset_goto": (0, 9999), "read_limit": (600, 1250),
}


@dataclass(frozen=True)
class ConfigurationFinding:
    code: str
    line: int = 0
    key: str = ""
    value: str = ""


@dataclass(frozen=True)
class ConfigurationSetting:
    key: str
    value: str
    line: int
    valid: bool


@dataclass
class GdemuConfiguration:
    path: Path
    status: str
    settings: list[ConfigurationSetting] = field(default_factory=list)
    findings: list[ConfigurationFinding] = field(default_factory=list)


def inspect_gdemu_config(root: Path) -> GdemuConfiguration:
    root = Path(root)
    path = root / "GDEMU.ini"
    try:
        matches = [p for p in root.iterdir() if p.name.lower() == "gdemu.ini"]
        if not matches:
            return GdemuConfiguration(path, "missing")
        if len(matches) != 1:
            return GdemuConfiguration(path, "review", findings=[ConfigurationFinding("ambiguous_file")])
        path = matches[0]
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            return GdemuConfiguration(path, "unreadable", findings=[ConfigurationFinding("unsafe_file")])
        with path.open("rb") as stream:
            data = stream.read(MAX_CONFIG_BYTES + 1)
        if len(data) > MAX_CONFIG_BYTES:
            return GdemuConfiguration(path, "unreadable", findings=[ConfigurationFinding("too_large")])
        if b"\0" in data:
            return GdemuConfiguration(path, "review", findings=[ConfigurationFinding("encoding")])
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252")
    except (OSError, RuntimeError, UnicodeError):
        return GdemuConfiguration(path, "unreadable", findings=[ConfigurationFinding("read_error")])
    result = GdemuConfiguration(path, "valid")
    seen = set()
    scoped = False
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = re.split(r"[;#]", raw, maxsplit=1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            scoped = True
            result.findings.append(ConfigurationFinding("section", line_number))
            continue
        if "=" not in line:
            result.findings.append(ConfigurationFinding("syntax", line_number))
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        key = key.lower()
        if scoped or key not in RANGES:
            result.findings.append(ConfigurationFinding("unknown_key", line_number, key))
            continue
        valid = bool(re.fullmatch(r"-?[0-9]+", value))
        if valid:
            # Avoid unbounded int conversion even for hostile textual values.
            valid = len(value) <= 6
        number = int(value) if valid else None
        low, high = RANGES[key]
        valid = valid and (low <= number <= high or key == "read_limit" and number in (-1, 0))
        result.settings.append(ConfigurationSetting(key, value, line_number, bool(valid)))
        if key in seen:
            result.findings.append(ConfigurationFinding("duplicate", line_number, key))
        seen.add(key)
        if not valid:
            result.findings.append(ConfigurationFinding("value", line_number, key, value))
    if result.findings:
        result.status = "invalid" if any(f.code in ("value", "duplicate") for f in result.findings) else "review"
    return result
