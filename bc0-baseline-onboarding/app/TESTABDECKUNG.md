# BC0 — Testabdeckung

**Projektgruppe KI-CoE-KMU · Bounded Context 0 (Baseline und Reifegrad)**
**Stand 20.08.2026 · Simeon Ehmer**

Gesamtlauf am 20.08.2026: **130 Tests, alle grün, 19,3 s.**

---

## 1. Verfahren

**Werkzeug:** pytest mit `fastapi.testclient.TestClient`. Die Tests sprechen die
Anwendung über HTTP an — dieselben Pfade, dieselbe Middleware, dieselbe
Serialisierung wie im Betrieb. Es werden keine Endpunktfunktionen direkt
aufgerufen. Damit prüfen die Tests auch die Anmeldeschicht mit, statt sie zu
umgehen.

**Was geprüft wird und was nicht:** Der Prüfgegenstand ist die
Anwendungsschicht — Endpunkte, Fachregeln, Rechte, Berichtsrechnung — und das
Anmeldepaket `bc0_auth`. Es sind Integrationstests im engeren Sinn, keine
Modultests: fast jeder Test schreibt in eine Datenbank und liest zurück.
Bewusst so, weil die interessanten Fehler dieses Systems an der Grenze zur
Datenbank liegen, nicht in einzelnen Funktionen.

**Isolierung gegen die Produktivdatenbank.** Der Kern von `conftest.py`, und
der Grund, warum diese Datei zuerst zu lesen ist:

> Die Gefahr ist real. `app.py` lädt beim Import eine `.env` aus dem
> Anwendungsverzeichnis, und auf dem Server steht dort die Verbindung zu
> Supabase. Würde ein Test unbedacht importieren, liefe er gegen die echten
> Daten. Das Einlesen geschieht über `os.environ.setdefault` — ein bereits
> gesetzter Wert wird also nicht überschrieben. Genau das nutzen wir:
> `DATABASE_URL` wird hier auf eine leere Zeichenkette gesetzt, bevor `app`
> importiert werden kann.

Jede Testdatei bekommt eine eigene SQLite-Datei in einem temporären
Verzeichnis. Fixtures sind überwiegend `scope="module"`: ein Mandant je Datei,
darauf mehrere Tests. Das ist schnell, erzeugt aber eine Reihenfolgeabhängigkeit
innerhalb einer Datei — an den Stellen, wo das relevant ist, ist es im Test
vermerkt.

**Grenze des SQLite-Modus.** Die Tests laufen gegen SQLite; der Betrieb läuft
gegen PostgreSQL 17.6. Das hat zweimal einen Fehler verdeckt, der erst im
PostgreSQL-Durchlauf am 11.08.2026 auffiel (gesperrte Rollen und gesperrte
Personen wurden beim nächsten Speichern wieder freigegeben). Beide Fälle stehen
seither als Test in der Sammlung — siehe `test_rollen_kosten.py` Nr. 11 und
`test_entitaeten.py` Nr. 7. Der Schluss daraus: **Ein grüner Testlauf ersetzt
den Durchlauf gegen das echte PostgreSQL nicht.** Er wird vor jedem Ausrollen
von Hand gefahren.

**Zusicherungen jenseits von pytest.** Die SQL-Skripte tragen am Dateiende
Gegenproben mit erwarteten Werten (`SELECT dimension, count(*) FROM ref_items
GROUP BY 1` → fünf Zeilen zu je sechs). Sie laufen beim Einspielen gegen den
echten Server mit, nicht in pytest.

---

## 2. Verteilung

| Datei | Prüfgegenstand | Tests | Zeilen |
|---|---|---:|---:|
| `test_auth.py` | Passwortverfahren, Sitzungen, Rollen | 27 | 290 |
| `test_entitaeten.py` | Personen- und Systemregister (ADR-004) | 25 | 405 |
| `test_gate0.py` | Freigabebogen Gate 0 | 25 | 528 |
| `test_app_zugriff.py` | Zugriffsschutz der laufenden Anwendung | 13 | 166 |
| `test_rollen_kosten.py` | Rollen und Kostensätze | 13 | 224 |
| `test_erhebungen.py` | Mehrfacherhebungen und maßgeblicher Stand | 11 | 243 |
| `test_mandantenfilter.py` | Mandantentrennung | 11 | 174 |
| **Summe** | | **130** | **2.030** |

Auffällig ist die Gewichtung: **51 der 130 Tests (39 %) prüfen Rechte und
Trennung** — Anmeldung, Rollen, Mandantenfilter, Adminvorbehalt. Das entspricht
der Risikolage: Bis zum 10.08.2026 war schreibender Zugriff ohne jede Anmeldung
möglich.

---

## 3. Die 130 Tests im Einzelnen

Die Formulierungen sind die Docstrings aus dem Quelltext; sie sind dort
zusammen mit dem Test entstanden und nennen jeweils den Grund, nicht die
Mechanik.

### 3.1 Zugriffsschutz der laufenden Anwendung — `test_app_zugriff.py` (13)

*Zugriffstests gegen die laufende Anwendung.*

| # | Test | Zusicherung |
|---:|---|---|
| 1 | api ist ohne anmeldung gesperrt | Der Kern der Etappe 4a: kein Datenzugriff ohne Sitzung. |
| 2 | schreibender zugriff ist ohne anmeldung gesperrt | Bis zum 10.08.2026 war genau das möglich — von jedem, ohne Anmeldung. |
| 3 | unbekannter api pfad ist ebenfalls gesperrt | Die Sperre gilt für das gesamte Präfix, nicht für eine Liste von Endpunkten. |
| 4 | oberflaeche bleibt erreichbar | Die PWA-Hülle muss ausgeliefert werden — sonst gäbe es keine Anmeldemaske. |
| 5 | status gibt ohne anmeldung auskunft | |
| 6 | falsche zugangsdaten | |
| 7 | anmeldung oeffnet die api | |
| 8 | sitzungsschluessel steht nicht in der antwort | Der Schlüssel gehört ins HttpOnly-Cookie, nicht in den Antwortkörper. |
| 9 | eigenes konto wird ohne hash ausgeliefert | |
| 10 | benutzerverwaltung ist admins vorbehalten | |
| 11 | admin darf benutzer verwalten | |
| 12 | admin kann sich nicht selbst herabstufen | Sonst könnte der letzte Admin die Anwendung führungslos machen. |
| 13 | abmelden beendet den zugang | |

Tests 1–3 prüfen die Middleware als Boden: Nr. 3 fragt einen Pfad ab, den es
nicht gibt, und erwartet 401 statt 404. Das ist die Probe auf das
Entwurfsmuster — ein vergessener Endpunkt ist geschützt, nicht offen.

### 3.2 Benutzerverwaltung, Passwörter, Sitzungen — `test_auth.py` (27)

*Tests der Benutzerverwaltung.*

**Passwortverfahren (1–7)**

| # | Test | Zusicherung |
|---:|---|---|
| 1 | hash laesst sich pruefen | |
| 2 | falsches passwort wird abgelehnt | |
| 3 | gleiches passwort ergibt verschiedene hashes | Das Salz muss je Passwort neu gezogen werden. |
| 4 | beschaedigter hash fuehrt nicht zur ausnahme | |
| 5 | zu kurzes passwort wird abgelehnt | |
| 6 | veralteter kostenparameter wird erkannt | |
| 7 | unbekannte rolle wird nicht stillschweigend ersetzt | |

Nr. 3 ist die Probe gegen ein festes Salz, Nr. 4 gegen einen Absturz bei
zerschossenem Datenbankinhalt (ein `IndexError` beim Zerlegen des
Hash-Strings wäre ein Denial of Service über die Anmeldemaske), Nr. 6 hält den
Weg für eine spätere Erhöhung der Durchläufe offen.

**Rechte und Sichtbarkeit (8–11)**

| # | Test | Zusicherung |
|---:|---|---|
| 8 | admin sieht alle mandanten | |
| 9 | benutzer sieht nur seinen mandanten | |
| 10 | benutzer darf nicht loeschen und nicht freigeben | |
| 11 | neue datenbank ist nicht eingerichtet | |

**Konten (12–15)**

| # | Test | Zusicherung |
|---:|---|---|
| 12 | benutzer anlegen und wiederfinden | |
| 13 | email wird unabhaengig von grossschreibung gefunden | |
| 14 | doppelte adresse wird abgelehnt | |
| 15 | mandantenzuordnung wird gespeichert | |

**Anmeldung (16–19)**

| # | Test | Zusicherung |
|---:|---|---|
| 16 | anmeldung mit richtigen daten | |
| 17 | anmeldung mit falschem passwort | |
| 18 | anmeldung mit unbekannter adresse | |
| 19 | gesperrtes konto kann sich nicht anmelden | |

**Sitzungen (20–27)**

| # | Test | Zusicherung |
|---:|---|---|
| 20 | sitzung loest den benutzer auf | |
| 21 | unbekannter schluessel loest nichts auf | |
| 22 | schluessel steht nicht im klartext in der datenbank | **Der wichtigste Test dieser Datei.** |
| 23 | abmelden macht die sitzung ungueltig | |
| 24 | abgelaufene sitzung wird abgewiesen | |
| 25 | passwortwechsel beendet alle sitzungen | |
| 26 | sperren beendet laufende sitzung | Eine Sperre wirkt sofort, nicht erst bei der nächsten Anmeldung. |
| 27 | rollenwechsel wirkt ohne neuanmeldung | Der Benutzer wird je Anfrage neu geladen — eine Höherstufung wirkt sofort. |

Nr. 22 prüft die Eigenschaft, die ein Datenbankleck entschärft: In `sessions`
steht nur der SHA-256-Abdruck des Sitzungsschlüssels. Wer die Tabelle liest,
kann keine Sitzung übernehmen. Nr. 25 und 26 prüfen den Widerruf — die
Eigenschaft, die serverseitige Sitzungen gegenüber JSON Web Tokens haben und
die der Grund für diese Entwurfsentscheidung war.

### 3.3 Personen- und Systemregister — `test_entitaeten.py` (25)

*Tests für das Entitäten-Register (ADR-004): Personen, Systeme, Zuordnungen.*

**Identität und Lebenszyklus (1–9)**

| # | Test | Zusicherung |
|---:|---|---|
| 1 | leerer mandant liefert die auswahllisten | Die Oberfläche darf keine zweite Werteliste führen müssen. |
| 2 | personen bekommen fortlaufende ids | |
| 3 | person ohne namen ist erlaubt | „externer Steuerberater" hat keinen erhobenen Namen, aber eine Rolle im Prozess. |
| 4 | person ohne namen und ohne funktion wird uebergangen | |
| 5 | bestehende person behaelt ihre id | Die ID ist der Anker für BC1 — Umbenennen darf sie nicht ändern. |
| 6 | entfernte person wird gesperrt statt geloescht | |
| 7 | gesperrte person bleibt gesperrt beim naechsten speichern | Derselbe Fehler war am 11.08. bei den Rollen erst im PostgreSQL-Lauf aufgefallen. |
| 8 | gesperrte person gibt ihre id nicht frei | ADR-004 R3. Der wichtigste Test dieser Datei. |
| 9 | unbekannte rolle wird abgelehnt | |

Nr. 5 und Nr. 8 zusammen sind ADR-004: Eine ID ist ein Anker, kein Anzeigename.
Sie darf beim Umbenennen nicht wandern und nach dem Sperren nicht neu vergeben
werden — sonst zeigte ein Verweis aus BC1 auf eine andere Person als bei seiner
Entstehung.

**Systeme (10–13)**

| # | Test | Zusicherung |
|---:|---|---|
| 10 | system ohne katalogbezug ist erlaubt | „Strategie-Cockpit" benennt eine Gattung, kein Produkt. |
| 11 | katalog ist vorbelegt und verwendbar | Der Katalog ist global wie die 30 Bitkom-Items und steht ohne Pflege bereit. |
| 12 | unbekanntes katalogprodukt wird abgelehnt | |
| 13 | entferntes system wird gesperrt statt geloescht | |

**Teilformulare und Zuordnungen (14–18)**

| # | Test | Zusicherung |
|---:|---|---|
| 14 | teilformular loescht nicht was es nicht anzeigt | Ein PUT nur mit `personen` darf Systeme nicht sperren. |
| 15 | mehrere eigner und doppelrolle sind moeglich | Genau das ließ sich in `owner_name` nicht abbilden. |
| 16 | unbekannte beteiligung wird abgelehnt | |
| 17 | abgewiesene zuordnung leert die tabelle nicht | Erst prüfen, dann löschen. |
| 18 | unbekannte person in der zuordnung wird abgelehnt | |

Nr. 14 und Nr. 17 sind die beiden Fehlerklassen, die bei einem
Ersetzen-statt-Ändern-Endpunkt entstehen: Ein PUT, der die vollständige Liste
erwartet, aber nur einen Teil bekommt, würde den Rest löschen; und ein PUT, der
erst löscht und dann prüft, hinterlässt bei einem Fehler eine leere Tabelle.

**Kontaktdaten und Datenschutz (19–23)**

| # | Test | Zusicherung |
|---:|---|---|
| 19 | kontaktdaten werden gespeichert und gelesen | |
| 20 | kontaktdaten duerfen leer bleiben | Wie beim Namen: Nicht erhoben ist ein zulässiger Zustand. |
| 21 | telefonnummer hat keinen formatzwang | Durchwahl, Landesvorwahl und Mobilnummer stehen im Haus in mehreren Schreibweisen. |
| 22 | email ohne klammeraffen wird abgewiesen | Die einzige Prüfung, und sie greift nur bei gefülltem Feld. |
| 23 | keine sicht gibt kontaktdaten aus | Die pseudonymisierten Sichten dürfen sich nicht durch neue Spalten erweitern. |

Nr. 23 ist der Datenschutztest: Er hält die Zusicherung aus ADR-004, dass an
BC1 bis BC4 und an Sprachmodelle nur IDs gehen. Er läuft über alle
`v_*`-Sichten und schlägt fehl, sobald eine davon eine Klarnamens- oder
Kontaktspalte aufnimmt — auch wenn das jemand später versehentlich tut.

**Trennung (24–25)**

| # | Test | Zusicherung |
|---:|---|---|
| 24 | fremder mandant bleibt gesperrt | |
| 25 | anmeldung ist pflicht | Ohne Sitzung kein Zugriff — Klarnamen stehen in diesem Endpunkt. |

### 3.4 Mehrfacherhebungen — `test_erhebungen.py` (11)

*Tests für Erhebungen (Schema v1.3 Teil C).*

| # | Test | Zusicherung |
|---:|---|---|
| 1 | erste bewertung erzeugt eine erhebung | Niemand soll vor der ersten Bewertung an einen Messzeitpunkt denken müssen. |
| 2 | mandant meldet die geltende erhebung | Die Oberfläche muss anzeigen können, in welchen Messzeitpunkt geschrieben wird. |
| 3 | zweite bewertung landet in derselben erhebung | |
| 4 | erhebung abschliessen | |
| 5 | zweite erhebung im selben monat wird abgelehnt | Die Kennung ist `E-JJJJ-MM`. Zwei Erhebungen im selben Monat kann sie nicht abbilden. |
| 6 | unbekannte aktion wird abgelehnt | |
| 7 | nacherhebung ueberschreibt nur die nacherhobenen | **Der wichtigste Test dieser Datei.** |
| 8 | alte bewertung bleibt erhalten | Der alte Wert ist nicht überschrieben, sondern liegt unter seiner Erhebung. |
| 9 | verworfene erhebung wird uebergangen | Ein Fehlversuch darf den Stand nicht verfälschen — und nicht gelöscht werden. |
| 10 | bericht rechnet auf dem massgeblichen stand | Der Reifegradbericht darf nicht über zwei Erhebungen hinweg mitteln. |
| 11 | fremder mandant bleibt gesperrt | |

Diese elf Tests sichern die anspruchsvollste Regel des Datenmodells ab. Der
maßgebliche Stand ist **keine** Erhebung, sondern eine Zusammensetzung: je
Teilprozess und Item die Zeile aus der neuesten nicht verworfenen Erhebung, die
sie überhaupt enthält (Fensterfunktion in `v_bewertung_aktuell`). Nr. 7 prüft
genau das an einer Teilnacherhebung, Nr. 9 die Ausklammerung eines
Fehlversuchs, Nr. 10 die Wirkung auf die Berichtsrechnung. Ohne Nr. 10 ließe
sich ein Bericht bauen, der über zwei Messzeitpunkte hinweg mittelt und damit
eine Zahl ausweist, die es nie gegeben hat.

### 3.5 Freigabebogen Gate 0 — `test_gate0.py` (25)

*Tests für den Gate-0-Freigabebogen (Schema v1.4).*

**Adminvorbehalt (1–3)**

| # | Test | Zusicherung |
|---:|---|---|
| 1 | benutzer scheitert auf allen gate endpunkten | Ein normaler Benutzer darf den Bogen nicht einmal lesen. |
| 2 | benutzer sieht die freigabe nicht in der liste | Auch nach einer Freigabe bleibt der Bogen für ihn verschlossen. |
| 3 | admin bekommt die liste | |

**Vollständigkeit der Entscheidung (4–10)**

| # | Test | Zusicherung |
|---:|---|---|
| 4 | bogen zeigt pruefpunkte und kette | |
| 5 | teilprozess ohne vorbedingungen ist gesperrt | TP-2 ist nicht bewertet — der Bogen ist nicht auszufüllen. |
| 6 | freigabe ohne guete bei dauer scheitert | Die Dauer geht in die Rechnung ein. Ohne Güte weiß BC2 nicht, worauf sie beruht. |
| 7 | zurueckweisung ohne massnahme scheitert | |
| 8 | zurueckweisung ohne grund scheitert | |
| 9 | unbekannter pruefpunkt scheitert | |
| 10 | zurueckweisung darf abbrechen | Eine Zurückweisung braucht **keine** vollständige Güte — wer abbricht, muss nicht erst alles erheben. |

Nr. 6 und Nr. 10 zusammen sind die eigentliche Fachregel: Der Prüfmaßstab ist
für Ja und Nein verschieden. Eine Freigabe ohne Güteangabe ließe BC2 einen
Punktwert rechnen, ohne je zu erfahren, worauf er beruht — genau die
Scheingenauigkeit, die das Gate abfangen soll. Eine Zurückweisung dagegen darf
abbrechen.

**Schreiben, Reproduzierbarkeit, Widerruf (11–15)**

| # | Test | Zusicherung |
|---:|---|---|
| 11 | freigabe wird geschrieben und erscheint im naechsten get | |
| 12 | erhebung ist im ereignis gesetzt | Ohne den festgehaltenen Datenstand wäre die Freigabe nicht reproduzierbar. |
| 13 | widerruf ueber zweite entscheidung | Nichts wird überschrieben — der aktuelle Stand ist die jüngste Zeile. |
| 14 | anfragen werden fortlaufend nummeriert | |
| 15 | anfrage ohne originaltext scheitert | |

Nr. 12 und Nr. 13 machen den Bogen zu einem Ereignisspeicher: Eine
Entscheidung wird nie geändert, sondern durch eine spätere überlagert, und sie
trägt die Erhebung als kopierten Wert mit sich. Damit ist auch ein Jahr später
belegbar, auf welchem Datenstand sie beruhte.

**Mandantengrenze (16–17)**

| # | Test | Zusicherung |
|---:|---|---|
| 16 | fremder mandant liefert 404 | Ein Admin darf alle Mandanten sehen — aber keine, die es nicht gibt. |
| 17 | teilprozess eines fremden mandanten liefert 404 | Die Teilprozess-ID allein öffnet nichts — sie muss zum Mandanten gehören. |

Nr. 17 ist der Test gegen die klassische unsichere direkte Objektreferenz: Der
Endpunkt darf nicht auf die Teilprozess-ID allein hören, sondern muss die
Zugehörigkeit zum Mandanten mitprüfen.

**Vorbedingungen und Zustandslogik (18–25)**

| # | Test | Zusicherung |
|---:|---|---|
| 18 | allein der eigner genuegt als vorbedingung | Eigner zugeordnet, 30 Items bewertet, sonst niemand benannt — offen ist nichts. |
| 19 | prozess ohne jede zuordnung bleibt bc0 pflege | Die Gegenprobe — der Fall, den die Sperre wirklich verhindern soll. |
| 20 | ein weiterer beteiligter aendert den zustand nicht | Ein nachgetragener Mitwirkender ist eine Auskunft, keine Vorbedingung. |
| 21 | nach der entscheidung ist der teilprozess entschieden | Eine Freigabe ist trotz `wartet_bc1` möglich — der Zustand steuert nur die Anzeige. |
| 22 | hindernisse sind je kernprozess gruppiert | Zehn Kernprozesse, nichts gepflegt: **zehn** Einträge je Art, nicht fünfzig. |
| 23 | hindernisse zaehlen entschiedenes nicht mehr mit | Der freigegebene Teilprozess aus KP-01 taucht in den Hindernissen nicht auf. |
| 24 | die liste ist nach am zug sortiert | Was zu tun ist, steht oben: entscheiden, bc0_pflege, wartet_bc1. |
| 25 | entscheiden ist ohne bc1 nicht erreichbar | Solange `_bc1_angaben` nichts liefert, gibt es keinen entscheidungsreifen Teilprozess. |

Nr. 18 bis 20 halten die am 18.08.2026 geänderte Fachregel fest: Vorbedingung
ist „mindestens eine Person zugeordnet, darunter ein Eigner". Die frühere
zweite Vorbedingung „Ansprechpartner benannt" ist entfallen, weil sie den
Eigner ausschloss und damit einen Prozess sperrte, der einen Verantwortlichen
hatte.

### 3.6 Mandantentrennung — `test_mandantenfilter.py` (11)

*Tests der Mandantentrennung (Etappe 4b).*

| # | Test | Zusicherung |
|---:|---|---|
| 1 | benutzer sieht nur seinen mandanten | |
| 2 | admin sieht alle mandanten | |
| 3 | benutzer ohne zuordnung sieht nichts | Kein Fehler, sondern eine leere Liste — und damit eine ehrliche Antwort. |
| 4 | fremder mandant wird mit 404 abgewiesen | |
| 5 | eigener mandant bleibt erreichbar | |
| 6 | schreiben auf fremden mandanten wird abgewiesen | Der eigentliche Punkt der Etappe: kein Schreibzugriff über die Grenze. |
| 7 | schreiben auf eigenen mandanten geht | |
| 8 | benutzer darf keinen mandanten anlegen | Sonst wäre die Trennung umgehbar: Wer sich selbst Mandanten anlegen kann, hebt sie auf. |
| 9 | benutzer darf kein yaml importieren | |
| 10 | admin darf mandanten anlegen | |
| 11 | entzogene zuordnung wirkt sofort | Ohne Neuanmeldung — der Benutzer wird bei jeder Anfrage frisch geladen. |

Nr. 4 prüft die Antwort **404 statt 403**: Ein fremder Mandant soll nicht als
existierend erkennbar sein. Nr. 8 ist die Probe auf die Rechteausweitung über
den Umweg — die Trennung wäre wertlos, wenn ein Benutzer sich selbst einen
zweiten Mandanten anlegen könnte.

### 3.7 Rollen und Kostensätze — `test_rollen_kosten.py` (13)

*Tests für Rollen und Kostensätze (Stammdaten der ROI-Kostenachse).*

| # | Test | Zusicherung |
|---:|---|---|
| 1 | leerer mandant liefert die fuenf klassen | Auch ohne gepflegte Daten muss die Oberfläche wissen, welche Klassen es gibt. |
| 2 | rollen bekommen fortlaufende ids | |
| 3 | bestehende rolle behaelt ihre id | Die ID ist der Anker für BC1 — sie darf sich beim Umbenennen nicht ändern. |
| 4 | entfernte rolle wird gesperrt statt geloescht | Der wichtigste Test dieser Datei. |
| 5 | unbekannte klasse wird abgelehnt | |
| 6 | kostensatz wird gespeichert und gelesen | |
| 7 | negativer satz wird abgelehnt | |
| 8 | unbekannte quelle wird abgelehnt | |
| 9 | aenderung am selben tag ueberschreibt die tageszeile | Sonst entstünden bei mehreren Korrekturen am selben Tag Dubletten. |
| 10 | fremder mandant bleibt gesperrt | Die Mandantentrennung gilt auch für die neuen Endpunkte. |
| 11 | gesperrte rolle bleibt gesperrt beim naechsten speichern | Gefunden im PostgreSQL-Durchlauf am 11.08.2026. |
| 12 | gesperrte rolle laesst sich wieder freigeben | Die Sperre ist keine Sackgasse — ein Häkchen genügt. |
| 13 | beschreibung wird gespeichert und gelesen | Richards Wunsch aus der ADR-003-Rückmeldung. |

Nr. 8 prüft die Herkunftsangabe des Kostensatzes (`quelle`) — die Zusicherung
aus ADR-005: Keine Zahl ohne Herkunft. Nr. 9 hält die Zeitreihe der Kostensätze
frei von Dubletten; sie ist tagesscharf, nicht sekundenscharf.

---

## 4. Was die Tests nicht abdecken

Ehrliche Aufstellung der Lücken, nach Gewicht:

| # | Lücke | Wirkung | Aufwand |
|---:|---|---|---|
| 1 | **Keine Abdeckungsmessung** | Es ist nicht belegt, welcher Anteil von `app.py` überhaupt durchlaufen wird. 130 Tests sind eine Zahl, keine Abdeckung. | `pytest-cov` einbinden, ~1 h; die Auswertung mehr |
| 2 | **Keine Tests der Berichtsrechnung** | Die Befundgeneratoren (`berichtstexte()`, `_satz_*`, `_prozesskanten()`) sind nur über den Reproduzierbarkeitsnachweis geprüft, nicht mit erwarteten Werten. Ein Rechenfehler wäre reproduzierbar falsch. | ~4 h; ein Mandant mit von Hand gerechneten Sollwerten |
| 3 | **Keine Tests für die neuen Endpunkte** | KI-Readiness (`ki_readiness_*`) und Prozessdokumentation (`prozessdok_*`) sind ungetestet. Sie sind bewusst noch nicht ausgerollt und auf Oktober terminiert. | ~3 h, mit dem Ausrollen |
| 4 | **Keine Oberflächentests** | 1.913 Zeilen JavaScript ohne einen einzigen automatisierten Test. Der Wettlauf beim Reiterwechsel fiel erst im Betrieb auf. | Playwright-Grundgerüst ~1 Tag |
| 5 | **Keine Lasttests** | Unbekannt, wie sich der Berichtsabruf bei 30 Mandanten verhält. Bei der geplanten Nutzung (Projektgruppe, Übungsmandant) nachrangig. | gering |
| 6 | **Kein Test der Zeichensatzgrenzen** | Umlaute und Sonderzeichen in Freitexten sind nur von Hand geprüft. | ~1 h |
| 7 | **SQLite statt PostgreSQL** | Siehe Abschnitt 1 — zwei Fehler sind so durchgerutscht. Ein zweiter Testlauf gegen ein PostgreSQL im Container wäre die saubere Lösung. | ~4 h (Testcontainers) |

Die Punkte 1 und 2 sind die, die ich einem Prüfer zuerst nennen würde: Die
Sammlung ist dort stark, wo im August ein Fehler weh getan hat (Rechte,
Trennung, Identität), und dünn dort, wo noch keiner aufgetreten ist
(Berichtsrechnung). Das ist die typische Verzerrung einer historisch
gewachsenen Testsammlung, und sie ist hier nachweisbar: Sechs der 130 Tests
tragen im Docstring das Datum eines Fehlers, den sie seither verhindern.

---

## 5. Reproduktion des Laufs

```bash
cd bc0-baseline-onboarding
python -m pytest tests/ -q          # 130 passed in ~19 s
python -m pytest tests/ -v          # mit Einzelnamen
python -m pytest tests/test_gate0.py -v
```

Kein Aufsatz nötig: `conftest.py` legt SQLite-Dateien in temporären
Verzeichnissen an und räumt nichts weg — die Testdatenbanken bleiben zur
Nachschau liegen. Ein PostgreSQL wird für den Lauf **nicht** benötigt und
ausdrücklich **nicht** angesprochen.

---

*Grundlage: `tests/` in der Arbeitskopie, Stand 20.08.2026. Alle Docstrings
wörtlich übernommen. Der Lauf wurde für dieses Papier neu gefahren.*
