-- BC0-Gerüst für BC1-Tests. Abgeleitet aus schema_v1.1 / v1.2 / v1.3 (Teile A, B, C).
-- Wird als postgres (Superuser) eingespielt.
--
-- Anspruch, präzise (Codex R4-C3): Enthalten sind nur die Objekte, die BC1
-- berührt — für diese aber DEFINITIONSGLEICH: Spaltennamen, Typen, CHECK-Muster,
-- Schlüssel und Sichtdefinitionen wie in BC0. Nicht berührte Zusatzspalten
-- (z. B. ref_teilprozesse.medienbrueche/schnittstellen/api, mandant_rollen.hinweis,
-- weitere companies-Spalten) fehlen bewusst: Unser SQL nennt sie nie, sie können
-- also keinen falschen Grünstand erzeugen — anders als ein abweichender
-- Spaltenname, der genau das täte (deshalb sub_process_name statt step_name).
-- Wächst der Lesepfad in Etappe 2, wächst das Gerüst mit.

-- ---------- Rollen (idempotent; ROLLEN.md-Modell) ----------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser') THEN
        CREATE ROLE bc_leser NOLOGIN;
    END IF;
    FOR i IN 1..4 LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bc' || i || '_role') THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', 'bc' || i || '_role');
        END IF;
        EXECUTE format('GRANT bc_leser TO %I', 'bc' || i || '_role');
    END LOOP;
END $$;

-- ---------- Typen (wortgleich aus schema_v1.1) ----------
CREATE TYPE process_category AS ENUM
    ('Steuerungsprozess', 'Kerngeschäftsprozess', 'Unterstützungsprozess');
CREATE TYPE beleg_source AS ENUM
    ('chat', 'doc', 'xlsx', 'interview', 'manuell', 'baseline', 'yaml');

-- ---------- BC0-Stammdaten ----------
CREATE TABLE companies (
    company_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL
);

CREATE TABLE ref_prozesse (
    company_id   uuid             NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    process_id   varchar(8)       NOT NULL CHECK (process_id ~ '^KP-[0-9]{2}$'),
    process_name text             NOT NULL,
    kategorie    process_category NOT NULL,
    beschreibung text,                       -- ALTER aus schema_v1.2
    owner_name   text,
    owner_role   text,
    trigger_text text,
    input_text   text,
    output_text  text,
    created_at   timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, process_id)
);

CREATE TABLE ref_teilprozesse (
    company_id       uuid        NOT NULL,
    sub_process_id   varchar(16) NOT NULL CHECK (sub_process_id ~ '^KP-[0-9]{2}\.TP-[0-9]+$'),
    process_id       varchar(8)  NOT NULL,
    step_no          integer     NOT NULL CHECK (step_no BETWEEN 1 AND 5),
    sub_process_name text        NOT NULL,
    notation         text,
    tools            text,
    PRIMARY KEY (company_id, sub_process_id),
    FOREIGN KEY (company_id, process_id)
        REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE,
    UNIQUE (company_id, process_id, step_no)
);

CREATE TABLE mandant_rollen (
    company_id  uuid NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    rolle_id    text NOT NULL,
    bezeichnung text NOT NULL,
    klasse      text NOT NULL CHECK (klasse IN ('K1','K2','K3','K4','K5')),
    aktiv       boolean NOT NULL DEFAULT true,
    PRIMARY KEY (company_id, rolle_id)
);

CREATE TABLE mandant_systeme (
    company_id  uuid NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    system_id   text NOT NULL CHECK (system_id ~ '^S-[0-9]{2}$'),
    bezeichnung text NOT NULL,
    PRIMARY KEY (company_id, system_id)
);

CREATE TABLE ref_erhebungen (
    company_id  uuid NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    erhebung_id text NOT NULL CHECK (erhebung_id ~ '^E-[0-9]{4}-[0-9]{2}$'),
    bezeichnung text NOT NULL,
    stand       date NOT NULL,
    status      text NOT NULL CHECK (status IN ('offen','abgeschlossen','verworfen')),
    PRIMARY KEY (company_id, erhebung_id)
);

CREATE TABLE ref_items (
    item_nr   integer PRIMARY KEY CHECK (item_nr BETWEEN 1 AND 30),
    dimension text NOT NULL,
    kriterium text NOT NULL,
    frage     text NOT NULL
);

CREATE TABLE bitkom_bewertungen (
    company_id     uuid         NOT NULL,
    erhebung_id    text         NOT NULL,
    id             varchar(28)  NOT NULL
                   CHECK (id ~ '^KP-[0-9]{2}\.TP-[0-9]+\.I-[0-9]{2}$'),
    sub_process_id varchar(16)  NOT NULL,
    item_nr        integer      NOT NULL REFERENCES ref_items(item_nr),
    stufe          integer      NOT NULL CHECK (stufe BETWEEN 1 AND 5),
    beleg          text         NOT NULL CHECK (length(btrim(beleg)) > 0),
    quelle         beleg_source NOT NULL DEFAULT 'manuell',
    bewerter       text,
    bewertet_am    timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, erhebung_id, id),
    FOREIGN KEY (company_id, sub_process_id)
        REFERENCES ref_teilprozesse(company_id, sub_process_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id, erhebung_id)
        REFERENCES ref_erhebungen(company_id, erhebung_id) ON DELETE CASCADE,
    UNIQUE (company_id, erhebung_id, sub_process_id, item_nr)
);

CREATE TABLE prozess_personen (
    company_id uuid NOT NULL,
    process_id varchar(8) NOT NULL,
    person_id  text NOT NULL,
    funktion   text NOT NULL
        CHECK (funktion IN ('eigner','sponsor','mitwirkend','vertretung')),
    PRIMARY KEY (company_id, process_id, person_id, funktion),
    FOREIGN KEY (company_id, process_id)
        REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE
);

-- ---------- Sichten (wortgleich aus schema_v1.3 übernommen) ----------
CREATE OR REPLACE VIEW v_bewertung_aktuell AS
SELECT company_id, erhebung_id, id, sub_process_id, item_nr, stufe, beleg,
       quelle, bewerter, bewertet_am
  FROM (SELECT b.company_id, b.erhebung_id, b.id, b.sub_process_id, b.item_nr,
               b.stufe, b.beleg, b.quelle, b.bewerter, b.bewertet_am,
               row_number() OVER (PARTITION BY b.company_id, b.sub_process_id, b.item_nr
                                  ORDER BY e.stand DESC, e.erhebung_id DESC) AS rang
          FROM bitkom_bewertungen b
          JOIN ref_erhebungen e
            ON e.company_id = b.company_id AND e.erhebung_id = b.erhebung_id
         WHERE e.status <> 'verworfen') t
 WHERE rang = 1;

CREATE OR REPLACE VIEW v_prozesse_lesen AS
SELECT p.company_id, p.process_id, p.process_name, p.beschreibung,
       p.trigger_text, p.input_text, p.output_text, p.created_at,
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id AND pp.process_id = p.process_id
           AND pp.funktion = 'eigner')  AS eigner_ids,
       (SELECT array_agg(pp.person_id ORDER BY pp.person_id)
          FROM prozess_personen pp
         WHERE pp.company_id = p.company_id AND pp.process_id = p.process_id
           AND pp.funktion = 'sponsor') AS sponsor_ids
  FROM ref_prozesse p;

-- ---------- Schema bc1 + Rechte wie in BC0s ROLLEN.md ----------
CREATE SCHEMA IF NOT EXISTS bc1 AUTHORIZATION bc1_role;
GRANT USAGE, CREATE ON SCHEMA bc1 TO bc1_role;
GRANT USAGE ON SCHEMA bc1 TO bc_leser;
GRANT USAGE ON SCHEMA public TO bc1_role, bc_leser;

-- Der Stolperstein aus R14-I1: BC0 vergibt SELECT auf JEDE neue Tabelle von bc1_role
-- automatisch an bc_leser. Ohne diese Zeile testet die ACL-Prüfung ins Leere.
ALTER DEFAULT PRIVILEGES FOR ROLE bc1_role IN SCHEMA bc1 GRANT SELECT ON TABLES TO bc_leser;

-- Rechte, die BC1 laut Spec K1 (Einspiel-Voraussetzungen I9) bekommt:
GRANT REFERENCES ON companies, ref_prozesse, ref_teilprozesse, mandant_rollen,
                    ref_erhebungen TO bc1_role;
GRANT SELECT ON v_bewertung_aktuell, mandant_systeme, ref_teilprozesse, companies,
                v_prozesse_lesen TO bc1_role;

-- BEWUSST NICHT: SELECT auf ref_prozesse (BC0 hat das Recht entzogen, R14-I2).
-- Ein Test beweist, dass der direkte Lesezugriff scheitert und v_prozesse_lesen trägt.
--
-- ABWEICHUNG, bewusst und geprueft (25.08., Abgleich gegen origin/main): BC0s
-- prozess_personen traegt zusaetzlich einen FK auf ref_personen(company_id, person_id).
-- Den hat das Geruest nicht, weil ref_personen fehlt — das Geruest ist an dieser
-- Stelle also LAXER als BC0. Folgenlos, solange BC1 prozess_personen nur mittelbar
-- ueber v_prozesse_lesen liest und nie beschreibt. Schreibt BC1 dort je hinein,
-- muss ref_personen ins Geruest.
