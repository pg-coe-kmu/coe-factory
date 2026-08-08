from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from bc1_core.feldtypen import FREITEXT, Feldtyp

@dataclass(frozen=True)
class FieldSpec:
    name: str
    question: str
    required: bool = True
    validator: Callable[[str], bool] | None = None
    typ: Feldtyp = FREITEXT

@dataclass(frozen=True)
class UseCasePackage:
    name: str
    schema_version: str
    fields: tuple[FieldSpec, ...]
    # Rundenobergrenze ist Paket-Eigenschaft: 26 Pflichtfelder brauchen mehr
    # Runden als 3 (Spec-Ergänzung P3, dokumentiert im Plan-Kopf).
    max_rounds: int = 20

    def __post_init__(self) -> None:
        namen = [f.name for f in self.fields]
        doppelte = sorted({n for n in namen if namen.count(n) > 1})
        if doppelte:
            raise ValueError(f"Doppelte Feldnamen im Use-Case-Paket: {doppelte}")

    def required_fields(self) -> list[FieldSpec]:
        return [f for f in self.fields if f.required]

    def field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.name == name), None)

TOY_PROZESS = UseCasePackage(
    name="toy_prozess",
    schema_version="0.1",
    fields=(
        FieldSpec("prozess_name", "Wie heißt der Prozess?"),
        FieldSpec("ausloeser", "Was löst den Prozess aus?"),
        FieldSpec("haeufigkeit", "Wie oft kommt er vor?",
                  validator=lambda v: any(c.isdigit() for c in v)),
        FieldSpec("notiz", "Sonstige Hinweise?", required=False),
    ),
)
