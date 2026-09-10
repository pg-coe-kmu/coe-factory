# BC0 → BC2 · Paket-Anstoß

Wie BC0 ein freigegebenes Paket an BC2 übergibt. Entschieden in
[#165](https://github.com/pg-coe-kmu/coe-factory/issues/165) (wer ruft wen)
und [#190](https://github.com/pg-coe-kmu/coe-factory/issues/190) (Mechanik).

> **Stand 10.09.2026 — an BC0s gebauten Ruf angeglichen.**
> Die erste Fassung dieses Vertrags verlangte `Authorization: Bearer` und ein
> Pflichtfeld `teilprozesse`. BC0 hat am 10.09.2026 anders gebaut
> ([`9ddda89`](https://github.com/pg-coe-kmu/coe-factory/commit/9ddda89), „Ruf an BC2"):
> **HMAC-Signatur** statt Bearer, und **nur die Kennungen** ohne Zuschnitt.
> Beides ist das bessere Verfahren, und dieser Vertrag war ausdrücklich ein
> Vorschlag — **BC2 hat sich angeglichen, BC0 muss nichts ändern.**
> Der ältere Vorschlag funktioniert weiterhin: BC2 nimmt beide Ausweisformen an
> und beide Nutzlasten.

## Der Aufruf

```
POST https://bc2.02da.de/api/bc0/uebergabe
Content-Type: application/json
X-BC0-Timestamp: 1789041131
X-BC0-Signature: sha256=<hmac>
```

## Sich ausweisen

Es gibt **ein** Geheimnis und zwei Arten, es vorzuzeigen. Eine genügt.

**1. Signatur — was BC0 gebaut hat, und der bessere Weg.**

```
unterschrift = HMAC-SHA256(geheimnis, "<stempel>." + <roher Rumpf>)
X-BC0-Timestamp: <stempel>              Unix-Sekunden
X-BC0-Signature: sha256=<unterschrift>  hexadezimal
```

Das Geheimnis geht nie über die Leitung, und der Zeitstempel geht in die
Signatur ein — ein mitgeschnittener Ruf lässt sich damit nicht wiederholen.
BC2 prüft über die Bytes, **wie sie ankamen**, und lässt **fünf Minuten**
Versatz zu (`BC2_SIGNATUR_FENSTER_S`); das fängt ungleiche Uhren ab.

**2. `Authorization: Bearer <geheimnis>`** — dasselbe Geheimnis, direkt
vorgezeigt. Bleibt gültig, ist aber der schwächere Weg. BC2 nutzt ihn für seine
eigenen Endpunkte (`/api/intern/…`).

Das Geheimnis wird **von BC2 ausgestellt** — dem Betreiber des Endpunkts, nicht
dem Aufrufer. Damit kann BC2 es rotieren und einzeln zurückziehen. Übergabe per
SMS, wie schon die Datenbank-Zugangsdaten; es gehört **ausschließlich in eine
Umgebungsvariable**, nie in Repo, Issue oder Chat (ADR-003).

BC0 führt es als `BC2_HOOK_SECRET`, BC2 als `BC2_TRIGGER_TOKEN`. **Ein**
Geheimnis, **eine** SMS.

## Die Nutzlast

Feldnamen sind **BC0s eigene**. Schema: [`trigger.schema.json`](trigger.schema.json).

So schickt BC0 es:

```json
{
  "ereignis": "paket_uebergeben",
  "company_id": "7c2d5ee9-2a9a-5990-810f-502ea2b2012d",
  "paket_id": "b1f4c0de-5a2e-4f77-9a31-8c6d1e0b7a44",
  "uebergeben_am": "2026-09-10 14:32:11.123456+02"
}
```

Pflicht sind **`paket_id`, `company_id`, `uebergeben_am`** — mehr nicht.

**`teilprozesse` ist optional und wird nicht erwartet.** Der Zuschnitt des
Pakets steht in `public.v_uebergabe_offen`, eine Zeile je `sub_process_id`, und
BC2 liest ihn über die `paket_id` von dort. BC0s Begründung dafür ist die
richtige und steht in seinem Code (`app.py:4317`):

> *„Eine Nachricht ist nicht wiederholbar lesbar, ein Zustand schon. Die
> Nachricht ist der Zettel mit der Nummer, nicht der Inhalt — die Datenbank
> bleibt alleinige Quelle (ADR-003 Regel 4)."*

Kommt die Liste trotzdem mit, nimmt BC2 sie an und hebt sie roh auf; maßgeblich
bleibt die Datenbank. Dasselbe gilt für `anfrage_id` und `hinweis`.

**`uebergeben_am` darf in Postgres-Schreibweise kommen.** BC0 reicht
`uebergeben_am::text` durch, und das ist kein RFC 3339: Leerzeichen statt `T`,
zweistelliger Zonenversatz (`+02`). BC2 nimmt beide Schreibweisen an. Der Wert
wird **roh** aufgehoben.

**Der Endpunkt ist tolerant:** unbekannte Felder werden nicht abgewiesen,
sondern roh mitprotokolliert. BC0 kann also ergänzen, ohne sich mit BC2
abzustimmen.

**Alles Weitere zieht BC2 selbst aus der Datenbank** — auch die Stundensätze
(`rollen_kostensaetze`). Eine Quelle, nicht zwei.

## Die Antworten

| Code | Wann | Rumpf |
|---|---|---|
| `202 Accepted` | Paket angenommen | `{"paket_id": "…", "status": "angenommen"}` |
| `202 Accepted` | dieselbe Paket-ID erneut | `{"paket_id": "…", "status": "bereits_angenommen"}` |
| `400 Bad Request` | Pflichtfeld fehlt oder ist unbrauchbar | `{"fehler": "Klartext, was fehlt"}` |
| `401 Unauthorized` | Signatur und Bearer fehlen oder stimmen nicht | `{"fehler": "…"}` |
| `503 Service Unavailable` | Datenbank nicht erreichbar | `{"fehler": "…"}` — **hier lohnt ein Wiederholungsversuch**, bei 400 und 401 nicht |

**`202` und nicht `200`:** BC2 hat zum Antwortzeitpunkt nichts gerechnet, und
`202` sagt genau das — angenommen, Bearbeitung folgt. BC0 wertet jeden
2xx-Code als zugestellt, das passt.

**Doppelanstoß ist harmlos.** Zweiter Aufruf mit derselben `paket_id`: wieder
`202`, nur mit `"bereits_angenommen"`. Kein `409` — das zwänge BC0 zu einer
Sonderbehandlung für einen Fall, der keine ist. Durchgesetzt wird das von der
Datenbank (`paket_id` ist Primärschlüssel von `bc2.eingang`), nicht vom Code:
zwei gleichzeitige Aufrufe können sich damit nicht überholen.

## Kein Paket geht verloren — auf drei Wegen

1. **Der Ruf** ist der Auslöser.
2. **BC0s `POST …/uebergabe/nachliefern`** wiederholt, was nicht ankam
   (`bc_zustellungen`).
3. **BC2s Abgleich** gegen `v_uebergabe_offen`, beim Start und auf Knopfdruck.

Zwei und drei überschneiden sich, und das ist kein Fehler: Der Doppelanstoß ist
folgenlos, und die beiden Wege fallen zu **verschiedenen** Zeiten aus. Fällt BC2
aus, während BC0 überträgt, holt BC2 selbst nach — dafür muss auf BC0s Seite
niemand etwas anstoßen.

**Kein Dauer-Polling** — die Festlegung aus #165 bleibt. Der Abgleich läuft beim
Start und wenn er angestoßen wird, nicht im Sekundentakt.

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
