-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.7: Feste Texte des Reifegradberichts
-- Stand: 19.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- Grundlage: ADR-005 (Ergebnispflicht und Herkunftsnachweis), Vorgabe Dorka
--   Reproduzierbarkeit, Transparenz, Nachvollziehbarkeit
--
-- Anlass: Der Reifegradbericht besteht aus zwei Textsorten. Die eine haengt
--   vom Mandanten ab und wird zur Laufzeit aus den Zahlen erzeugt — regel-
--   basiert, deterministisch, ohne Sprachmodell. Die andere ist fuer jeden
--   Mandanten gleich: Methode, Skala, Matrizen, Grenzen. Genau diese steht
--   hier.
--
-- WARUM NICHT IM PROGRAMMCODE: Ein Bericht ist erst dann reproduzierbar, wenn
--   auch der erklaerende Satz reproduzierbar ist. Steht der Text im Quelltext,
--   aendert er sich mit jedem Deployment unbemerkt mit, und ein Bericht von
--   heute laesst sich in einem Jahr nicht mehr identisch erzeugen. Steht er in
--   der Datenbank mit Version und Gueltigkeitsdatum, fuehrt der Bericht seine
--   Textfassung mit — und man sieht, ob sich seither die Zahlen geaendert
--   haben oder die Formulierung.
--
-- NICHT MANDANTENBEZOGEN. Die Texte beschreiben das Modell, nicht das
--   Unternehmen. Eine mandantenbezogene Fassung waere spaeter additiv
--   nachruestbar (Spalte company_id, NULL = gilt fuer alle); heute waere sie
--   eine Einladung, den Methodenteil je Kunde schoenzuschreiben.
--
-- AENDERN HEISST NEUE VERSION. Ein bestehender Text wird nicht ueberschrieben,
--   sondern auf aktiv = FALSE gesetzt und durch eine hoehere Version ersetzt.
--   Damit bleibt ein alter Bericht erklaerbar. Das ist dieselbe Logik wie beim
--   Schreibmodell aus ADR-003: additiv, nichts wird ueberschrieben.
--
-- ADDITIV und wiederholbar (IF NOT EXISTS / ON CONFLICT DO NOTHING).
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.7_berichtstexte.sql
-- ============================================================


-- ============================================================
-- 23. TEXTBAUSTEINE DES REIFEGRADBERICHTS
-- ============================================================

CREATE TABLE IF NOT EXISTS ref_berichtstexte (
  baustein_id  TEXT    NOT NULL CHECK (baustein_id ~ '^B-[0-9]{2}$'),
  version      INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  gueltig_ab   DATE    NOT NULL,
  abschnitt    TEXT    NOT NULL,
  text         TEXT    NOT NULL CHECK (length(btrim(text)) > 0),
  aktiv        BOOLEAN NOT NULL DEFAULT TRUE,
  angelegt_am  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (baustein_id, version)
);

COMMENT ON TABLE ref_berichtstexte IS
  'Feste Texte des Reifegradberichts, mandantenunabhaengig. Aenderung erzeugt '
  'eine neue Version; die alte bleibt stehen, damit ein frueherer Bericht '
  'erklaerbar bleibt (ADR-005).';

COMMENT ON COLUMN ref_berichtstexte.abschnitt IS
  'Wohin der Baustein im Bericht gehoert. Reine Ordnungshilfe fuer die '
  'Redaktion; die Reihenfolge im Bericht bestimmt die Anwendung.';

COMMENT ON COLUMN ref_berichtstexte.aktiv IS
  'Genau eine Version je Baustein ist aktiv. Erzwungen durch ux_berichtstexte_aktiv.';

-- Genau eine aktive Fassung je Baustein. Ohne diesen Index koennte die
-- Anwendung zwei Fassungen desselben Bausteins finden und muesste raten.
CREATE UNIQUE INDEX IF NOT EXISTS ux_berichtstexte_aktiv
  ON ref_berichtstexte(baustein_id) WHERE aktiv;


-- ============================================================
-- 24. LESESICHT
-- ============================================================
-- Die Anwendung liest ausschliesslich hierueber. Sie sieht damit nie eine
-- abgeloeste Fassung, auch nicht versehentlich.

CREATE OR REPLACE VIEW v_berichtstexte_aktuell AS
SELECT baustein_id, version, gueltig_ab, abschnitt, text
  FROM ref_berichtstexte
 WHERE aktiv
 ORDER BY baustein_id;

COMMENT ON VIEW v_berichtstexte_aktuell IS
  'Die jeweils gueltige Fassung jedes Bausteins. Einzige Lesequelle der Anwendung.';


-- ============================================================
-- 25. DIE TEXTE, FASSUNG 1 VOM 19.08.2026
-- ============================================================
-- Redigiert von Simeon Ehmer. Grundsatz: Der Bericht stellt fest und
-- empfiehlt nicht. Ein Satz, der eine Empfehlung nahelegt, gehoert nicht
-- hierher, sondern in den Strategic Advisor.

INSERT INTO ref_berichtstexte (baustein_id, version, gueltig_ab, abschnitt, text) VALUES

('B-01', 1, DATE '2026-08-19', 'Titelblatt',
 'Reifegradfeststellung nach dem Bitkom-Leitfaden „Reifegradmodell Digitale Geschäftsprozesse 3.0". Erhoben, gerechnet und dokumentiert im Bounded Context 0 der Projektgruppe KI-CoE-KMU.'),

('B-02', 1, DATE '2026-08-19', '1 Kurzfassung',
 'Die Kurzfassung nennt die Zahlen, auf denen alles Weitere beruht: den Digitalisierungsgrad über alle erhobenen Prozesse, den Wert je Kernprozess, die Zahl der Bewertungen und den Anteil, der mit einem Beleg hinterlegt ist. Was diese Zahlen bedeuten und was sie nicht bedeuten, steht im Kapitel Grundlage und im Kapitel Grenzen.'),

('B-03', 1, DATE '2026-08-19', '2 Grundlage',
 'Grundlage der Feststellung ist der Bitkom-Leitfaden „Reifegradmodell Digitale Geschäftsprozesse 3.0". Wir folgen ihm ohne eigene Erweiterungen: Die Dimensionen, die Kriterien und die dreißig Fragen sind unverändert übernommen, ebenso die Rechenweise.

Das Modell ist von unten nach oben aufgebaut. Zwei Fragen ergeben ein Kriterium, drei Kriterien eine Dimension, fünf Dimensionen den Digitalisierungsgrad. Bewertet wird auf der Ebene des Teilprozesses — dort, wo Arbeit tatsächlich stattfindet. Der Wert eines Kernprozesses ist der Mittelwert seiner Teilprozesse und keine eigene Erhebung.

Die fünf Dimensionen sind Technologie, Prozessdaten, Prozessqualität, Kundinnen und Kunden sowie Skills und Kultur. Sie decken nacheinander ab, ob Informationen digital vorliegen und Systeme verbunden sind, ob im Ablauf verwertbare Daten entstehen, ob der Ablauf beschrieben und stabil ist, ob die Außensicht abgebildet wird und ob die Beteiligten digital arbeiten können.'),

('B-04', 1, DATE '2026-08-19', '2 Grundlage',
 'Eine Stufe ist ein Erfüllungsgrad, kein Etikett. Stufe 1 steht für null Prozent, Stufe 2 für über null bis vierzig Prozent, Stufe 3 für über vierzig bis fünfzig Prozent, Stufe 4 für über fünfzig bis fünfundneunzig Prozent und Stufe 5 für über fünfundneunzig Prozent.

Die Abstände sind damit ungleich, und der Sprung von 3 auf 4 ist der größte im ganzen Modell: Er überspannt fünfundvierzig Prozentpunkte, während zwischen 2 und 3 nur zehn liegen. Für die Lektüre dieses Berichts heißt das zweierlei. Erstens ist der Unterschied zwischen 2,9 und 3,4 ein anderer als der zwischen 3,4 und 3,9, obwohl beide Male fünf Zehntel dazwischenliegen. Zweitens ist jede lineare Umrechnung des Reifegrads in eine Nutzen- oder Einspargröße an dieser Stelle falsch.

Die einzelne Antwort ist immer eine ganze Zahl. Mittelwerte haben Nachkommastellen, und das ist beabsichtigt — sie auf ganze Zahlen zu runden verwischt genau die Unterschiede, um derentwillen erhoben wurde.'),

('B-05', 1, DATE '2026-08-19', '2 Grundlage',
 'Jede Bewertung trägt einen Beleg: einen Verweis auf eine Dokumentation, ein Bildschirmfoto, eine Kennzahl oder einen Satz aus der Praxis. Das ist keine Empfehlung, sondern eine Regel in der Datenbank — eine Bewertung ohne Begründung wird nicht angenommen. Die Belegquote in der Kurzfassung ist deshalb kein Qualitätssiegel, sondern eine Selbstverständlichkeit; auffällig wäre erst ein Wert unter hundert Prozent.

Die Belege selbst stehen im Anhang, zusammen mit der Herkunft jedes Wertes.'),

('B-06', 1, DATE '2026-08-19', '3 Dimensionen',
 'Die folgenden Werte sind über alle erhobenen Teilprozesse gemittelt. Sie zeigen, wo die Organisation als Ganzes steht, nicht wie ein einzelner Prozess abschneidet. Unter jeder Dimension stehen ihre drei Kriterien; erst auf dieser Ebene wird erkennbar, worauf ein Dimensionswert beruht — ein mittlerer Wert kann aus drei mittleren Kriterien entstehen oder aus einem hohen und zwei niedrigen.'),

('B-07', 1, DATE '2026-08-19', '4 Prozesse',
 'Bewertet wurde je Teilprozess. Die Tabelle zeigt zuerst den Kernprozess als Mittel seiner Teilprozesse und darunter die Teilprozesse einzeln. Der Kernprozesswert allein kann täuschen: Er verdeckt, wie weit die Teilprozesse auseinanderliegen. Wo die Spanne groß ist, ist der Mittelwert die schwächere Auskunft.'),

('B-08', 1, DATE '2026-08-19', '5 Auffälligkeiten',
 'Dieses Kapitel benennt, was in den Zahlen heraussticht: die höchsten und niedrigsten Werte, die größten Abstände innerhalb eines Prozesses und Bewertungen, die von ihrer Umgebung abweichen. Es sind Beobachtungen, keine Bewertungen. Ob eine Auffälligkeit ein Problem ist, eine bewusste Entscheidung oder ein Erhebungsfehler, ist aus den Zahlen nicht zu entscheiden — das klärt das Interview im nachfolgenden Schritt.'),

('B-09', 1, DATE '2026-08-19', '7 Matrizen',
 'Die Matrix stellt je Teilprozess sechs Kriterien nebeneinander, die für eine Automatisierung des Ablaufs selbst maßgeblich sind: Technologiebasis, Tools im Prozess, Systemintegration, Prozessbeschreibung, Ausführung und Compliance. Sie greift dazu auf zwölf der dreißig Fragen zurück — die sechs aus der Dimension Technologie und die sechs aus der Dimension Prozessqualität.

Die Einfärbung folgt allein dem Wert und ist eine Lesehilfe, keine Aussage über Dringlichkeit.'),

('B-10', 1, DATE '2026-08-19', '7 Matrizen',
 'Die cross-sectionale Betrachtung reiht dieselben sechs Kriterien entlang der Prozesskette auf — nicht nach Prozessnummer, sondern in der Reihenfolge, in der die Prozesse einander beliefern. Sie beantwortet damit eine andere Frage als die Matrix zuvor: nicht „wie weit ist dieser Prozess", sondern „bricht die Kette irgendwo".

Unter jedem Kriterium stehen neben dem Durchschnitt die beiden Einzelfragen, aus denen er entsteht. Darauf zielt das Verfahren: Ein Kriterium, dessen zwei Fragen weit auseinanderliegen, ist im Durchschnitt unauffällig und in der Sache nicht durchgängig. Solche Stellen sind rot umrandet.

Der Leitfaden markiert dafür Einzelbewertungen. Hier ist jeder Wert bereits ein Mittel über die Teilprozesse eines Kernprozesses; die Schwelle wird auf diese Mittelwerte angewandt. Ein Prozess kann in sich gut automatisierbar sein und trotzdem an seinen Rändern brechen — die beiden Darstellungen nebeneinander machen das sichtbar.'),

('B-15', 1, DATE '2026-08-19', '3 Portfolio',
 'Das Management-Cockpit ordnet die Prozesse nicht nach ihrer Nummer, sondern nach Prozesskategorie: Steuerungs-, Kerngeschäfts- und Unterstützungsprozesse nebeneinander, jeder auf der Höhe seines Reifegrads. Es rechnet nichts Neues; es zeigt dieselben Werte in der Anordnung, die den Blick vom einzelnen Prozess auf das Portfolio hebt.

Zwei Dinge werden hier sichtbar, die in den Tabellen untergehen. Erstens, wie weit die Prozesse einer Kategorie auseinanderliegen — eine Kategorie mit einem hohen und zwei niedrigen Prozessen ist etwas anderes als eine mit drei mittleren. Zweitens, welche Kategorien überhaupt erhoben sind; eine leere Spalte ist selbst ein Befund.

Die Höhe eines Eintrags folgt dem Reifegrad, nicht der Stufenklasse. Die Klassen selbst sind unterschiedlich breit — das ist eine Eigenschaft der Skala und im Kapitel Grundlage erklärt.'),

('B-11', 1, DATE '2026-08-19', '7 Grenzen',
 'Dieser Bericht stellt einen Reifegrad fest. Er empfiehlt nichts.

Das ist keine Zurückhaltung, sondern eine Eigenschaft des Modells: Der Bitkom-Leitfaden hält im Kapitel über die Grenzen ausdrücklich fest, dass aus dem Reifegrad keine Handlungsempfehlung folgt. Er sagt, wie digital ein Prozess ist — nicht, was zu tun ist, und nicht, ob sich etwas lohnt.

Dazu kommen drei Grenzen aus der Erhebung selbst. Erstens erhebt das Modell keine Zeiten, Mengen und Häufigkeiten; ohne die ist keine Wirtschaftlichkeitsrechnung möglich. Diese Angaben entstehen im nachfolgenden Interview. Zweitens beruhen die Werte auf Selbsteinschätzung, abgesichert durch die Belegpflicht, aber nicht durch Messung. Drittens gibt es keinen Vergleichsmaßstab: weder einen früheren Stand desselben Unternehmens noch Werte anderer Unternehmen. Alle Vergleiche in diesem Bericht sind Vergleiche innerhalb dieser einen Erhebung.

Priorisierung, Wirtschaftlichkeitsrechnung und Empfehlung sind Gegenstand der nachfolgenden Schritte und stehen bewusst nicht hier.'),

('B-12', 1, DATE '2026-08-19', '7 Grenzen',
 'An mehreren Stellen wird ein Wert gegen die Schwelle 3,5 gehalten. Diese Schwelle stammt nicht von Bitkom, sondern ist eine Festlegung dieses Projekts: Ein Prozess gilt erst ab einem Reifegrad von 3,5 als tragfähiger Kandidat für den nachfolgenden Schritt. Sie ist begründet und dokumentiert, aber sie ist gesetzt und nicht abgeleitet. Wer sie ändert, ändert die Auswahl — nicht die Zahlen.'),

('B-13', 1, DATE '2026-08-19', '8 Anhang',
 'Der Anhang weist die Herkunft der Zahlen aus: die Erhebungen, aus denen der maßgebliche Stand zusammengesetzt ist, und je Teilprozess die Zahl der Bewertungen samt Belegstand. Auf Anforderung führt er zusätzlich jede einzelne Bewertung mit Frage, Stufe und Beleg auf.

Er ist der Grund, warum dieser Bericht nachvollziehbar ist und nicht nur plausibel: Jede Zahl in den vorangegangenen Kapiteln lässt sich von hier aus bis zu der Antwort zurückverfolgen, aus der sie gerechnet wurde.'),

('B-14', 1, DATE '2026-08-19', 'Fußzeile',
 'Quelle: Bitkom, Leitfaden „Reifegradmodell Digitale Geschäftsprozesse 3.0". Erhebung, Rechnung und Darstellung: Bounded Context 0, Projektgruppe KI-CoE-KMU, FH Südwestfalen.')

ON CONFLICT (baustein_id, version) DO NOTHING;


-- ============================================================
-- GEGENPROBE
-- ============================================================
-- Erwartet: 15 Zeilen, alle aktiv, alle Version 1.
--
--   SELECT count(*) FROM v_berichtstexte_aktuell;
--
-- Erwartet: kein Baustein doppelt aktiv (der Index verhindert es ohnehin).
--
--   SELECT baustein_id, count(*) FROM ref_berichtstexte WHERE aktiv
--    GROUP BY baustein_id HAVING count(*) > 1;
--
-- So wird ein Text spaeter geaendert — nicht per UPDATE des Textes:
--
--   UPDATE ref_berichtstexte SET aktiv = FALSE WHERE baustein_id = 'B-11' AND version = 1;
--   INSERT INTO ref_berichtstexte (baustein_id, version, gueltig_ab, abschnitt, text)
--   VALUES ('B-11', 2, CURRENT_DATE, '7 Grenzen', '...neuer Text...');
-- ============================================================
