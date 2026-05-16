from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "seed" / "domain_config.json"


@dataclass(frozen=True)
class GeometryInput:
    label: str
    key: str
    minimum: float
    maximum: float
    default: float


@dataclass(frozen=True)
class PartTemplate:
    domain: str
    name: str
    topology: str
    constraint: str
    search_suffix: str
    geometry_inputs: tuple[GeometryInput, ...]

    @property
    def display_name(self) -> str:
        return f"{self.domain} / {self.name}"


class Catalog:
    """Reads the legacy domain config as seed catalog data."""

    def __init__(self, path: Path | str = DEFAULT_CATALOG_PATH) -> None:
        self.path = Path(path)
        self._raw = self._load()
        self._parts = self._flatten_parts()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Catalog seed not found: {self.path}")
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _flatten_parts(self) -> list[PartTemplate]:
        parts: list[PartTemplate] = []
        for domain, domain_config in self._raw.items():
            for name, part_config in domain_config.get("parts", {}).items():
                geometry_inputs = tuple(
                    GeometryInput(
                        label=item["label"],
                        key=item["key"],
                        minimum=float(item["min"]),
                        maximum=float(item["max"]),
                        default=float(item["default"]),
                    )
                    for item in part_config.get("ui_inputs", [])
                )
                parts.append(
                    PartTemplate(
                        domain=domain,
                        name=name,
                        topology=part_config["topology"],
                        constraint=part_config.get("constraint", ""),
                        search_suffix=part_config.get("search_suffix", ""),
                        geometry_inputs=geometry_inputs,
                    )
                )
        return parts

    @property
    def domains(self) -> list[str]:
        return list(self._raw.keys())

    @property
    def parts(self) -> list[PartTemplate]:
        return list(self._parts)

    def parts_for_domain(self, domain: str) -> list[PartTemplate]:
        return [part for part in self._parts if part.domain == domain]

    def get_part(self, domain: str, name: str) -> PartTemplate:
        for part in self._parts:
            if part.domain == domain and part.name == name:
                return part
        raise KeyError(f"Part template not found: {domain} / {name}")

    def mvp_parts(self) -> list[PartTemplate]:
        preferred = {
            ("人形机器人核心骨架", "下肢大扭矩管状连杆"),
            ("智能穿戴与柔性外骨骼", "智能穿戴承力外壳"),
            ("智能穿戴与柔性外骨骼", "柔性外骨骼助力带"),
        }
        return [part for part in self._parts if (part.domain, part.name) in preferred]
