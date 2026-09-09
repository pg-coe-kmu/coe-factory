"""
BC2 · Eingangsbuch — die Naht zwischen Endpunkt und Datenbank.

Der Endpunkt kennt nur das Protokoll ``Eingangsbuch``. Dahinter liegen zwei
Umsetzungen: ``PostgresEingangsbuch`` gegen die gemeinsame Datenbank und
``SpeicherEingangsbuch`` im Arbeitsspeicher für die Tests.

**Warum die Naht hier liegt und nicht tiefer:** BC2 liest 26 Tabellen und 22
Views fremden Schemas, das es nicht besitzt. Ein Test, der eine echte
Postgres-Verbindung braucht, wäre in der Vorschleife nicht bezahlbar; ein Test,
der SQLite unterschiebt, würde eine andere Datenbank prüfen als die, gegen die
gelaufen wird. Also: die Ablagelogik ist austauschbar, und das eine, was
**wirklich** an Postgres hängt — dass ``paket_id`` Primärschlüssel ist und damit
die Idempotenz durchsetzt — wird in ``tests/test_vertrag_postgres.py`` von Hand
gegen die echte Datenbank geprüft. Der Speicher-Doppelgänger ahmt die Semantik
nach; die **Garantie** gibt nur die Datenbank.

(Das ist der Vorschlag aus dem Nebel der Karte #158, „Testnaht gegen fremdes
Schema", hier zum ersten Mal angewandt.)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class Paket:
    """Ein Paket-Anstoß, so wie er abgelegt wird."""

    paket_id: str
    company_id: str
    uebergeben_am: datetime
    nutzlast: dict[str, Any]
    quelle: str = "push"  # 'push' | 'nachgeholt'


class Eingangsbuch(Protocol):
    """Was der Endpunkt von seiner Ablage braucht — mehr nicht."""

    def eintragen(self, paket: Paket) -> bool:
        """Legt das Paket ab.

        Gibt ``True`` zurück, wenn es neu war, und ``False``, wenn diese
        ``paket_id`` schon lag. Kein Prüf-dann-Schreib: die Entscheidung fällt
        in **einer** Anweisung, sonst könnten zwei gleichzeitige Aufrufe sich
        überholen.
        """
        ...

    def offene_pakete_von_bc0(self) -> list[Paket]:
        """Pakete aus ``public.v_uebergabe_offen``, die hier noch nicht liegen."""
        ...

    def erreichbar(self) -> bool:
        """Für die Bereitschaftsprüfung: antwortet die Ablage?"""
        ...


# ----------------------------------------------------------------------------
# Postgres
# ----------------------------------------------------------------------------

# Ein Paket je Zeile — die View liefert eine Zeile je Teilprozess, hier wird
# zusammengefasst.
#
# `anfrage_id` hängt in v_uebergabe_offen am **Teilprozess**, nicht am Paket
# (sie kommt aus gate_paket_inhalt). Ein Paket kann darum mehrere tragen. Trägt
# es genau eine, wird sie übernommen; trägt es mehrere, bleibt das Feld leer —
# lieber keine Angabe als eine willkürlich gegriffene. Dasselbe steht so im
# Vertrag unter contracts/bc0-to-bc2/.
_SQL_OFFEN = """
SELECT v.paket_id,
       v.company_id,
       v.uebergeben_am,
       max(v.hinweis)                                        AS hinweis,
       array_agg(DISTINCT v.sub_process_id)                  AS teilprozesse,
       array_remove(array_agg(DISTINCT v.anfrage_id), NULL)  AS anfrage_ids
  FROM public.v_uebergabe_offen v
  LEFT JOIN bc2.eingang e ON e.paket_id = v.paket_id
 WHERE e.paket_id IS NULL
 GROUP BY v.paket_id, v.company_id, v.uebergeben_am
 ORDER BY v.uebergeben_am
"""

_SQL_EINTRAGEN = """
INSERT INTO bc2.eingang (paket_id, company_id, uebergeben_am, quelle, nutzlast)
VALUES (%(paket_id)s, %(company_id)s, %(uebergeben_am)s, %(quelle)s, %(nutzlast)s)
ON CONFLICT (paket_id) DO NOTHING
"""


class PostgresEingangsbuch:
    """Ablage in der gemeinsamen Datenbank.

    Verbindet je Vorgang neu statt einen Pool zu halten. Bei der erwarteten Last
    — eine Handvoll Pakete am Tag — ist ein Pool Aufwand ohne Gegenwert, und der
    Session-Pooler von Supabase hält die Sitzung ohnehin.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or (os.environ.get("DATABASE_URL") or "").strip()
        if not self._dsn:
            raise RuntimeError(
                "DATABASE_URL ist nicht gesetzt. Die Zugangsdaten gehoeren "
                "ausschliesslich in eine Umgebungsvariable (ADR-003)."
            )

    def _verbindung(self):
        import psycopg2  # lokal importiert: die Tests brauchen den Treiber nicht

        return psycopg2.connect(self._dsn)

    def eintragen(self, paket: Paket) -> bool:
        import json

        import psycopg2.extras  # noqa: F401  (registriert den Json-Adapter)

        with self._verbindung() as conn, conn.cursor() as cur:
            cur.execute(
                _SQL_EINTRAGEN,
                {
                    "paket_id": paket.paket_id,
                    "company_id": paket.company_id,
                    "uebergeben_am": paket.uebergeben_am,
                    "quelle": paket.quelle,
                    "nutzlast": json.dumps(paket.nutzlast, ensure_ascii=False),
                },
            )
            # rowcount == 0 heisst: ON CONFLICT hat gegriffen, das Paket lag schon.
            return cur.rowcount == 1

    def offene_pakete_von_bc0(self) -> list[Paket]:
        import psycopg2.extras

        with self._verbindung() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(_SQL_OFFEN)
            zeilen = cur.fetchall()

        pakete: list[Paket] = []
        for z in zeilen:
            anfrage_ids = list(z["anfrage_ids"] or [])
            nutzlast: dict[str, Any] = {
                "paket_id": z["paket_id"],
                "company_id": z["company_id"],
                "uebergeben_am": z["uebergeben_am"].isoformat(),
                "teilprozesse": sorted(z["teilprozesse"] or []),
            }
            # Genau eine Anfrage -> uebernehmen. Mehrere -> weglassen, siehe
            # Kommentar an _SQL_OFFEN.
            if len(anfrage_ids) == 1:
                nutzlast["anfrage_id"] = anfrage_ids[0]
            if z["hinweis"]:
                nutzlast["hinweis"] = z["hinweis"]

            pakete.append(
                Paket(
                    paket_id=z["paket_id"],
                    company_id=z["company_id"],
                    uebergeben_am=z["uebergeben_am"],
                    nutzlast=nutzlast,
                    quelle="nachgeholt",
                )
            )
        return pakete

    def erreichbar(self) -> bool:
        try:
            with self._verbindung() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
        except Exception:
            return False


# ----------------------------------------------------------------------------
# Arbeitsspeicher (Tests)
# ----------------------------------------------------------------------------


@dataclass
class SpeicherEingangsbuch:
    """Doppelgänger für die Tests.

    Ahmt die Semantik von ``ON CONFLICT DO NOTHING`` nach. **Die Garantie gibt
    er nicht** — die gibt der Primärschlüssel in der Datenbank. Wer hier einen
    grünen Test sieht, hat die Idempotenz noch nicht bewiesen; das tut
    ``tests/test_vertrag_postgres.py`` gegen die echte Datenbank.
    """

    abgelegt: dict[str, Paket] = field(default_factory=dict)
    offen: list[Paket] = field(default_factory=list)
    antwortet: bool = True

    def eintragen(self, paket: Paket) -> bool:
        # Die Ausfallpruefung steht vor der Idempotenzpruefung: eine Ablage, die
        # nicht antwortet, weiss auch nicht, ob sie das Paket schon hat.
        if not self.antwortet:
            raise RuntimeError("Ablage antwortet nicht (Testfall).")
        if paket.paket_id in self.abgelegt:
            return False
        self.abgelegt[paket.paket_id] = paket
        return True

    def offene_pakete_von_bc0(self) -> list[Paket]:
        if not self.antwortet:
            raise RuntimeError("Ablage antwortet nicht (Testfall).")
        return [p for p in self.offen if p.paket_id not in self.abgelegt]

    def erreichbar(self) -> bool:
        return self.antwortet
