# BC0 → BC2 · Paket-Anstoß

Wie BC0 ein freigegebenes Paket an BC2 übergibt. Entschieden in
[#165](https://github.com/pg-coe-kmu/coe-factory/issues/165) (wer ruft wen)
und [#190](https://github.com/pg-coe-kmu/coe-factory/issues/190) (Mechanik).

Dies ist ein **Vorschlag von BC2 an BC0**, keine Vorschrift — derselbe Zuschnitt
wie bei [#184](https://github.com/pg-coe-kmu/coe-factory/issues/184). Wenn etwas
nicht passt, ändern wir es hier, nicht im Code.

## Der Aufruf

```
POST https://bc2.02da.de/api/bc0/uebergabe
Authorization: Bearer <token>
Content-Type: application/json
```

Der Token wird **von BC2 ausgestellt** — dem Betreiber des Endpunkts, nicht dem
Aufrufer. Damit kann BC2 ihn rotieren und einzeln zurückziehen. Übergabe per
SMS, wie schon die Datenbank-Zugangsdaten; er gehört **ausschließlich in eine
Umgebungsvariable**, nie in Repo, Issue oder Chat (ADR-003).

`Authorization: Bearer` und nicht `X-API-Key`: den ersten Header maskieren
Zugriffsprotokolle üblicherweise von sich aus, den zweiten nicht.

## Die Nutzlast

Feldnamen sind **BC0s eigene** aus `public.v_uebergabe_offen`. Schema:
[`trigger.schema.json`](trigger.schema.json).

```json
{
  "paket_id": "PKT-2026-0007",
  "company_id": "NOROAI",
  "uebergeben_am": "2026-09-10T14:32:11+02:00",
  "teilprozesse": ["KP-02.TP-1", "KP-02.TP-3", "KP-04.TP-2"],
  "anfrage_id": "A-2026-01",
  "hinweis": "Reisekosten sind noch handschriftlich, bitte gesondert ansehen."
}
```

Pflicht sind `paket_id`, `company_id`, `uebergeben_am` und `teilprozesse`.
`anfrage_id` und `hinweis` sind optional.

**Mehr braucht BC2 nicht.** Alles Weitere zieht es selbst aus der gemeinsamen
Datenbank — **auch die Stundensätze** (`rollen_kostensaetze`). Eine Quelle,
nicht zwei.

**Der Endpunkt ist tolerant:** unbekannte Felder werden nicht abgewiesen,
sondern roh mitprotokolliert. BC0 kann also ergänzen, ohne sich mit BC2
abzustimmen.

## Die Antworten

| Code | Wann | Rumpf |
|---|---|---|
| `202 Accepted` | Paket angenommen | `{"paket_id": "…", "status": "angenommen"}` |
| `202 Accepted` | dieselbe Paket-ID erneut | `{"paket_id": "…", "status": "bereits_angenommen"}` |
| `400 Bad Request` | Pflichtfeld fehlt oder ist unbrauchbar | `{"fehler": "Klartext, was fehlt"}` |
| `401 Unauthorized` | Token fehlt oder stimmt nicht | `{"fehler": "…"}` |
| `503 Service Unavailable` | Datenbank nicht erreichbar | `{"fehler": "…"}` — **hier lohnt ein Wiederholungsversuch**, bei 400 und 401 nicht |

**`202` und nicht `200`:** BC2 hat zum Antwortzeitpunkt nichts gerechnet, und
`202` sagt genau das — angenommen, Bearbeitung folgt.

**Doppelanstoß ist harmlos.** Zweiter Aufruf mit derselben `paket_id`: wieder
`202`, nur mit `"bereits_angenommen"`. Kein `409` — das zwänge BC0 zu einer
Sonderbehandlung für einen Fall, der keine ist. Durchgesetzt wird das von der
Datenbank (`paket_id` ist Primärschlüssel von `bc2.eingang`), nicht vom Code:
zwei gleichzeitige Aufrufe können sich damit nicht überholen.

## BC0 braucht keine Wiederholungslogik

Der Endpunkt ist der **Auslöser**, nicht der einzige Weg. BC2 gleicht beim Start
und auf Knopfdruck selbst gegen `v_uebergabe_offen` ab und holt nach, was es
nicht bekommen hat. Fällt BC2 aus, während BC0 überträgt, geht also nichts
verloren.

**Kein Dauer-Polling** — die Festlegung aus #165 bleibt. Der Abgleich läuft
beim Start und wenn er angestoßen wird, nicht im Sekundentakt.

## Was hier bewusst offen bleibt

- **Die Rückrichtung** BC2 → BC3, Gate-1-Reject und Nacherhebung: eigene
  Kante, eigenes Ticket ([#188](https://github.com/pg-coe-kmu/coe-factory/issues/188)).
- **Was zum Trigger-Zeitpunkt in der Datenbank stehen muss** — insbesondere
  BC1s vier Größen `dauer`, `haeufigkeit`, `menge`, `rollen`:
  [#184](https://github.com/pg-coe-kmu/coe-factory/issues/184).
- **Ob `uebergeben_am` ein Lesestand ist** oder bloß Protokoll. BC0s Code kennt
  `stand_zum()` und einen Kommentar, der das Erste sagt; die Antwort an #165
  sagt das Zweite. Rückfrage läuft. Für die Annahme des Pakets ist es ohne
  Belang — BC2 hebt den Wert roh auf.
