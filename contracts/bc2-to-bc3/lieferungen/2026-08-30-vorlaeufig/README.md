# ⚠️ VORLÄUFIGE Übergangslieferung an BC3 — 30.08.2026

> **Diese Lieferung ist keine Bewertung.** Sie existiert aus einem einzigen Grund: BC3 kann
> Tickets schneiden und BC4 kann bauen, ohne auf BC2s fertiges Value-Modell zu warten.
> Die Wirtschaftlichkeitszahlen darin sind **gesetzt, nicht erhoben.**
>
> Erzeugt für [#168](https://github.com/pg-coe-kmu/coe-factory/issues/168).

## Was echt ist und was nicht

Das ist die wichtigste Tabelle in diesem Ordner.

| Echt — aus dem BC0-Snapshot v3 (27.08.2026) gelesen | Vorläufig — hier gesetzt, nirgends erhoben |
| --- | --- |
| Kernprozesse KP-02, KP-03, KP-04 mit ihren Teilprozessen | Fallzahlen pro Jahr |
| Namen, Notation, Trigger, Prozesseigner | Bearbeitungszeit pro Fall |
| Eingesetzte Tools, dokumentierte Medienbrüche, Schnittstellen | Angenommener Einsparungsgrad |
| Reifegrad je Teilprozess und Kriterium (6 Dimensionen) | Umsetzungsaufwand in Personentagen |
| Stundensatz 68 EUR/h (Kostensatz K3) — aber in der DB als `geschaetzt` geführt | Alles, was daraus folgt: `ist_kosten_eur_jahr`, `einsparung_eur_jahr`, `investition_eur_richtwert`, `amortisation_monate` |

**Warum die Zahlen gesetzt sind.** Die Value-Rechnung braucht Frequenz × Aufwand × Kostensatz.
Die gemeinsame Datenbank führt den **Kostensatz**, aber weder **Fallzahlen** noch
**Bearbeitungszeiten** ([#159](https://github.com/pg-coe-kmu/coe-factory/issues/159)). Die beiden
fehlenden Faktoren müssen also angenommen werden — unabhängig davon, woher die Prozessdaten
stammen. Genau deshalb ist die Lieferung als vorläufig markiert und nicht als „berechnet".

**Was daraus trotzdem trägt:** die Prozesse, Teilprozesse, Medienbrüche und Systeme sind real.
Tickets, die BC3 daraus schneidet, beschreiben **existierende NoroAI-Arbeit** und überleben den
Austausch der Zahlen. Nur die Priorisierung untereinander kann sich noch drehen.

## Warum nicht der v2-Mock

`contracts/examples/mock_automatisierungskonzept.json` wäre schneller lieferbar gewesen, beschreibt
aber „Antragsbearbeitung Krankentagegeld, KP-07, Aurelia Krankenkasse" — **frei erfunden**. Real ist
KP-07 die Buchhaltung und nicht erhoben; NoroAI ist eine KI-Beratung mit 10 Mitarbeitenden.

BC3 hätte daraus Tickets für einen Prozess geschnitten, den es nicht gibt. Da die Value-Zahlen
ohnehin in beiden Fällen gesetzt sind, kostet der reale Weg fast nichts extra — er liefert nur
statt erfundener Prozesse die echten. BC3 hat ausdrücklich um einen *fiktiven ROI* gebeten, nicht
um einen fiktiven Prozess.

## Woher die Prozessdaten kommen

Aus dem eingefrorenen BC0-Snapshot im Repo, **nicht** aus BC1:

```
bc0-baseline-onboarding/app/snapshots/NoroAI_Consulting_GmbH_baseline_v3.json
```

`prozessprofil_ref` weist das aus (`bc0-snapshot:…#KP-02`). Grund: die Schemata `bc1`, `bc3`, `bc4`
existieren in der Datenbank, enthalten aber **null Tabellen** — BC1 liefert derzeit nichts
([#163](https://github.com/pg-coe-kmu/coe-factory/issues/163)). Diese Lieferung überspringt BC1
bewusst und einmalig.

## Warum genau diese drei Prozesse

KP-02, KP-03 und KP-04 sind die drei Kerngeschäftsprozesse, die aus BC0-Sicht **sauber** sind
(#159). KP-01 und KP-06 haben zu niedrigen Reifegrad, KP-05 und KP-06 sind unvollständig erhoben,
KP-07 bis KP-10 gar nicht.

Die Potenziale sind an den **gemessen schwächsten Teilprozessen** und den dort **dokumentierten
Medienbrüchen** verankert — nicht frei gewählt:

| Rang | KP | Potenzial | Anker im Snapshot |
| --- | --- | --- | --- |
| 1 | KP-02 | Lead-Erfassung/-Qualifizierung aus E-Mail ins CRM | Medienbruch „Manuelle CRM-Pflege bei Email-Anfragen" (TP-1, TP-2) |
| 2 | KP-04 | Retrospektive + Lessons Learned verdichten | TP-3/TP-5, Tools-Wert 3.0 — die niedrigsten in KP-04 |
| 3 | KP-03 | AVV-/DSGVO-Abwicklung medienbruchfrei | Medienbruch „AVV-Unterzeichnung kann Papier sein", Systemintegration 3.0 (TP-4) |

## Ein Befund, der nicht am Zahlenwert hängt

Bei NoroAIs Größe (10 Mitarbeitende) sind die Volumina klein. Selbst großzügig angenommen ergibt
KP-03 eine Amortisation von rund **53 Monaten** — die klassische ROI-Arithmetik trägt diesen
Anwendungsfall nicht. Sein Nutzen liegt in Compliance-Sicherheit und Nachweisbarkeit, nicht in
Zeitersparnis.

Das ist kein Artefakt der gesetzten Zahlen, sondern eine Größenordnung, die sich mit echten Werten
nicht umdrehen wird. Es ist zugleich das erste konkrete Argument für die **Nutzwertanalyse** neben
der Monetärrechnung ([#166](https://github.com/pg-coe-kmu/coe-factory/issues/166)).

Deshalb ranked die Priorisierung nach **Impact × Komplexität** und benutzt die Geldbeträge nur als
Tie-Break — ein Ranking direkt nach Euro wäre scheingenau.

## Wie die Vorläufigkeit markiert ist

Fünf Träger, damit die Markierung das Kopieren in BC3-Tickets und BC4-Code überlebt. Der Vertrag
bleibt dabei auf **v2.0** — kein Schema-Bump, keine weitere Abstimmungsrunde:

| Träger | Wo | Überlebt Kopieren? |
| --- | --- | --- |
| `[VORLAEUFIG]`-Präfix im **Titel** | jedes Potenzial, jeder Priorisierungs-Eintrag | **ja** — Titel wandern wörtlich in Tickets |
| Warnblock am Anfang der **`beschreibung`** | jedes Potenzial | **ja** — Beschreibung wird von BC3 gelesen und übernommen |
| `value.value_quelle = "default"` | jedes `value{}` | maschinenlesbar, stirbt beim Umformen |
| `value.annahmen[0]` = Warntext | jedes `value{}` | maschinenlesbar |
| `gate1.kommentar` = Freigabesperre | jedes Konzept | maschinenlesbar |

`value_quelle: "default"` ist kein Notbehelf: das Schema definiert `default` als „Eingabedaten waren
unvollständig, Fallback-Werte genutzt (Resilienz R-04)" — genau der vorliegende Fall. `berechnet`
wäre schlicht falsch gewesen.

**ID-Konvention:** Jede UUID dieser Lieferung beginnt mit **acht Nullen**
(`00000000-0000-4000-8000-…`). Wer eine solche ID in BC3- oder BC4-Artefakten findet, hat einen
vorläufigen Datensatz vor sich.

## Was hier drin liegt

| Datei | Inhalt |
| --- | --- |
| `konzept_KP-02.json` | Automatisierungskonzept Vertrieb & Lead-Management (L2-01) |
| `konzept_KP-03.json` | Automatisierungskonzept Kunden-Onboarding (L2-01) |
| `konzept_KP-04.json` | Automatisierungskonzept Engagement-Steuerung (L2-01) |
| `prozesspriorisierung.json` | Priorisierung über alle drei Konzepte (L2-02) |

Ein Konzept **je Kernprozess** — `kontext.kp_id` ist einwertig, und jede Ausgabe führt die
Kernprozess-ID mit (Auflage BC0). Die Priorisierung geht über alle drei.

## Was fehlt und wann es kommt

| Fehlt | Wirkung auf BC3 | Klärung |
| --- | --- | --- |
| `akzeptanzkriterien_geschaeftlich`, `fachliche_anforderungen`, ausführliches `to_be_vision` | BC3 muss Akzeptanzkriterien vorerst selbst formulieren | [#160](https://github.com/pg-coe-kmu/coe-factory/issues/160) |
| Belastbares Value-Modell (Bandbreiten, Nutzwertanalyse) | Priorisierung kann sich noch drehen | [#166](https://github.com/pg-coe-kmu/coe-factory/issues/166) |
| Gate-0-Freigabe | **kein** Kernprozess ist freigegeben; diese Lieferung nimmt das vorweg | [#159](https://github.com/pg-coe-kmu/coe-factory/issues/159), Umgang: [#165](https://github.com/pg-coe-kmu/coe-factory/issues/165) |
| BC1-Prozessprofile | Herkunft ist ersatzweise der BC0-Snapshot | [#163](https://github.com/pg-coe-kmu/coe-factory/issues/163) |
| Geklärte PII-Grenze beim LLM-Aufruf | betrifft KP-02 unmittelbar (Kontaktdaten) | [#150](https://github.com/pg-coe-kmu/coe-factory/issues/150) |

## Reproduzieren und prüfen

```bash
# aus dem Repo-Wurzelverzeichnis
python3 bc2-strategic-advisor/tools/gen_uebergangslieferung.py   # erzeugt neu (deterministisch)
python3 bc2-strategic-advisor/tools/validate.py                  # prüft gegen die v2-Schemas
```

`validate.py` prüft neben Schema-Konformität auch, dass die Vorläufigkeits-Kennzeichnung
vollständig ist — Titel-Marker, `value_quelle`, Warn-Annahme, Gate-1-Sperre. Exit 0 = grün.

Die Rechnung im Generator ist **deterministisch**, ohne LLM (Invariante aus
`bc2-strategic-advisor/CLAUDE.md`). Alle Annahmen stehen als Konstanten am Kopf der Datei und
zusätzlich in jedem `value.annahmen[]`.
