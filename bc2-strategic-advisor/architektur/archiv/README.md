# Archiv — das alte Präsentations-Template

> **Zeigt Vertrag v2 und wird nicht gepflegt.** Nicht befüllen, nicht ausliefern.

| Datei | Was |
|---|---|
| `build_template.py` | Erzeugte `BC2_Praesentations_Template.pptx`: 13 Folien im KIsult-Schnitt mit `{{…}}`-Platzhaltern |
| `BC2_Praesentations_Template.pptx` | Das einzige greifbare Abbild des KIsult-Schnitts im Repo — als Augenmaß, nicht als Vorlage |

Abgelöst durch den Generator `app/praesentation/` ([#257](https://github.com/pg-coe-kmu/coe-factory/issues/257),
entschieden in [#244](https://github.com/pg-coe-kmu/coe-factory/issues/244)), der Palette, Formen und Schnitt
von hier übernommen hat und den Foliensatz aus Konzepten und Priorisierung **zeichnet**.

Warum das Template nicht mehr taugt: es kennt die vier Stufen `gering … sehr hoch` statt 1–10,
führt den manuellen Aufwand als Urteil statt als gemessene Jahresstunden, nennt „BC1-Prozessprofil"
als Quelle, kennt keine Bandbreiten, zeigt eine Kausalketten-Folie, die aus den Daten nicht folgt —
und speichert auf einen absoluten Pfad außerhalb des Repos. Wer es von Hand befüllt, liefert einen
v2-Foliensatz aus.

`build_pptx.py` und `BC2_Systemarchitektur.*` im Ordner darüber bleiben: sie betreffen die
Architektur-Präsentation fürs Team, kein Mandantenergebnis.
