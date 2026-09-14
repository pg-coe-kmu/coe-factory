# -*- coding: utf-8 -*-
"""Patch v3.2 fuer app.py — 14.09.2026. Setzt patch_v3.1.py voraus.

**Was hier NICHT passiert.** Der Ruf bleibt, wie er ist: HMAC-Signatur ueber
Zeitstempel und rohen Rumpf, nur die Kennungen im Rumpf, kein Bearer-Token,
kein `teilprozesse[]`. BC2 hat sich am 10.09. an unsere Form angeglichen
(#190, Commit 183a160) und nimmt beide an; seine Empfehlung ist, unsere zu
behalten — eine Signatur ist kein Geheimnis, ein Bearer-Token im
Zugriffsprotokoll ist der Schluessel.

Zwei Befunde aus BC2s Betrieb am 10.09., beide an unserem Code:

  1. **`"None"` ueber die Leitung.** `_bc2_rufen` schickt `str(uebergeben_am)`.
     Liefert das `SELECT uebergeben_am::text` davor keine Zeile, geht die
     Zeichenkette `"None"` hinaus und BC2 antwortet 400 — auffallen wuerde es
     nur im Fehlerfall, und dann als Raetsel. Jetzt wird gar nicht gerufen und
     der Grund steht im Zustellprotokoll.
  2. **Der Zeitstempel ist kein RFC 3339.** PostgreSQL schreibt
     `2026-09-10 14:32:11.123456+02` — Leerzeichen statt `T`, zweistelliger
     Zonenversatz. BC2 faengt das seit dem 10.09. mit `iso_normalisieren()`
     ab; auf Python vor 3.11 waere es 400 gewesen. Die Nachsicht eines
     Empfaengers ist keine Zusicherung: wir senden ab jetzt selbst richtig.

Kein neues Paket, kein Schema, keine Datenbankaenderung.
"""
import io, sys

def lies(p):  return io.open(p, encoding="utf-8").read()
def schreib(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def ersetze(s, alt, neu, name):
    if s.count(alt) != 1:
        sys.exit("Anker nicht (eindeutig) gefunden: " + name)
    return s.replace(alt, neu, 1)

s = lies("app.py")

# ------------------------------------------------- 1. RFC-3339-Normalisierung
s = ersetze(s,
    '''def _bc2_rufen(cid, paket_id, uebergeben_am, versuch=1):''',
    '''_ZEIT_RE = re.compile(
    r"^(\\d{4}-\\d{2}-\\d{2})[ T](\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?)\\s*(Z|[+-]\\d{2}(?::?\\d{2})?)?$")


def _rfc3339(wert):
    """Macht aus PostgreSQLs Textform einen RFC-3339-Zeitstempel.

    PostgreSQL schreibt `2026-09-10 14:32:11.123456+02`: Leerzeichen statt
    `T`, Zonenversatz zweistellig. RFC 3339 verlangt `T` und `+02:00`.
    Python nimmt beides erst ab 3.11; ein Empfaenger auf 3.10 weist es ab.

    Gibt `None` zurueck, wenn nichts oder etwas Unlesbares ankommt — der
    Aufrufer entscheidet dann, dass nicht gerufen wird. Eine Zeichenkette,
    die wir nicht erkennen, reichen wir unveraendert durch: lieber der
    Originalwert als eine stille Verfaelschung.
    """
    if wert is None:
        return None
    text = str(wert).strip()
    if not text or text == "None":
        return None
    treffer = _ZEIT_RE.match(text)
    if not treffer:
        return text
    tag, zeit, zone = treffer.group(1), treffer.group(2), treffer.group(3)
    if not zone:
        return tag + "T" + zeit                      # ohne Zone: nichts erfinden
    if zone != "Z":
        if len(zone) == 3:                           # +02   -> +02:00
            zone += ":00"
        elif len(zone) == 5:                         # +0200 -> +02:00
            zone = zone[:3] + ":" + zone[3:]
    return tag + "T" + zeit + zone


def _bc2_rufen(cid, paket_id, uebergeben_am, versuch=1):''',
    "rfc3339")

# ------------------------------------------------- 2. None-Sperre und Rumpf
s = ersetze(s,
    '''    rumpf = json.dumps({"ereignis": "paket_uebergeben", "company_id": str(cid),
                        "paket_id": str(paket_id), "uebergeben_am": str(uebergeben_am)},
                       separators=(",", ":"), sort_keys=True).encode("utf-8")
    kopf = {"Content-Type": "application/json", "User-Agent": "BC0/3.1"}''',
    '''    # v3.2: Ohne Zeitpunkt wird nicht gerufen. Vorher ging in diesem Fall die
    # Zeichenkette "None" hinaus, BC2 antwortete 400, und im Protokoll stand
    # ein Raetsel statt einer Ursache. Das Paket ist deswegen nicht verloren —
    # BC2 holt es sich ueber v_uebergabe_offen (ADR-003 Regel 4).
    stand = _rfc3339(uebergeben_am)
    if not stand:
        _zustellung_merken(cid, paket_id, "fehler", None,
                           "uebergeben_am fehlt — es wurde nicht gerufen. "
                           "Das Paket steht in der Datenbank; BC2 holt es nach.",
                           versuch)
        return ("fehler", None, "uebergeben_am fehlt")

    rumpf = json.dumps({"ereignis": "paket_uebergeben", "company_id": str(cid),
                        "paket_id": str(paket_id), "uebergeben_am": stand},
                       separators=(",", ":"), sort_keys=True).encode("utf-8")
    kopf = {"Content-Type": "application/json", "User-Agent": "BC0/3.2"}''',
    "none sperre")

schreib("app.py", s)
print("app.py: gepatcht (v3.2)")

# ------------------------------------------------- 3. .env.example
try:
    e = lies(".env.example")
except IOError:
    e = None
if e is not None and "BC2_HOOK_URL" not in e:
    e = e.rstrip("\n") + '''

# ---- Ruf an BC2 (v3.1/v3.2) ----
# Ohne BC2_HOOK_URL wird nicht gerufen; das Paket steht trotzdem in der
# Datenbank und BC2 holt es ueber v_uebergabe_offen nach.
# BC2_HOOK_SECRET ist der HMAC-Schluessel, mit dem wir signieren und BC2
# prueft — derselbe Wert, den BC2 als BC2_TRIGGER_TOKEN fuehrt. Kommt per
# SMS, nie per Chat, Mail oder Repo.
# BC2_HOOK_URL=https://bc2.02da.de/api/bc0/uebergabe
# BC2_HOOK_SECRET=
# BC2_HOOK_TIMEOUT=5
'''
    schreib(".env.example", e)
    print(".env.example: BC2-Block ergaenzt")
else:
    print(".env.example: unveraendert")
