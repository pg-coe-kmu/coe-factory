"""Die Kette über Pakete hinweg, aus den Dateien geprüft (#291, ADR-009 · BC2).

Was sich an einer Lieferung allein und an den schon gelieferten im Repo prüfen lässt:
die Vorgänger und die Streichliste. Die Kandidatenmenge selbst (welche gelieferten
Potenziale einen Teilprozess des Pakets berühren) liest erst der Bau aus Schema `bc2`
(#295) — hier wird nur geprüft, dass nichts behauptet wird, was nicht stimmen kann.

Rein und ohne Abhängigkeiten, damit `validate.py` und die Tests dieselbe Regel benutzen.
"""
from __future__ import annotations


def gelieferte_potenziale(lieferungen):
    """Index aller Potenziale aus freigegebenen Lieferungen.

    ``lieferungen`` ist eine Folge von ``(konzepte, prio)``. Nur ``gate1.status == "approved"``
    zählt — ein Vorgänger muss bei BC3 angekommen sein (ADR-009 · BC2 §2.2). Ergebnis:
    ``potenzial_id -> {"paket_id", "kp_id", "klasse"}``.
    """
    index = {}
    for konzepte, prio in lieferungen:
        if prio.get("gate1", {}).get("status") != "approved":
            continue
        for k in konzepte:
            for p in k["potenziale"]:
                index[p["potenzial_id"]] = {
                    "paket_id": k["paket_id"],
                    "kp_id": k["kontext"]["kp_id"],
                    "klasse": p["automatisierungsgrad"]["klasse"],
                }
    return index


def kettenbefunde(konzepte, prio, geliefert):
    """Liste der Verstöße gegen ADR-009 · BC2; leer heißt: die Kette hält.

    Eine 3.0-Lieferung kennt keine Kette und wird nur auf einheitliche Fassung geprüft.
    """
    befunde = []
    versionen = {k["schema_version"] for k in konzepte} | {prio["schema_version"]}
    if len(versionen) > 1:
        befunde.append(f"uneinheitliche schema_version im Lauf: {sorted(versionen)}")
        return befunde
    if versionen != {"3.1"}:
        return befunde

    eigene = {p["potenzial_id"] for k in konzepte for p in k["potenziale"]}
    paket = prio["paket_id"]

    # Vorgänger: einer je Potenzial (das Schema), jede Kennung einmal je Lauf (1:1, §2.4).
    vorgaenger = {}
    for k in konzepte:
        for p in k["potenziale"]:
            for alt in p["ersetzt_potenzial_ids"]:
                if alt in vorgaenger:
                    befunde.append(
                        f"{alt} hat zwei Nachfolger ({vorgaenger[alt]}, {p['potenzial_id']}) "
                        "-- nur 1:1, eine Teilung macht neue Potenziale"
                    )
                vorgaenger[alt] = p["potenzial_id"]
                if alt in eigene:
                    befunde.append(f"{p['potenzial_id']} nennt {alt} aus demselben Lauf als Vorgaenger")
                    continue
                quelle = geliefert.get(alt)
                if quelle is None:
                    befunde.append(
                        f"Vorgaenger {alt} von {p['potenzial_id']} steht in keiner freigegebenen Lieferung"
                    )
                    continue
                if quelle["paket_id"] == paket:
                    befunde.append(
                        f"Vorgaenger {alt} stammt aus demselben Paket -- dort verkettet ersetzt_konzept_id"
                    )
                if quelle["kp_id"] != k["kontext"]["kp_id"]:
                    befunde.append(
                        f"Vorgaenger {alt} liegt in {quelle['kp_id']}, sein Nachfolger in {k['kontext']['kp_id']}"
                    )
                if quelle["klasse"] != p["automatisierungsgrad"]["klasse"]:
                    befunde.append(
                        f"{p['potenzial_id']}: Loesungsklasse {p['automatisierungsgrad']['klasse']!r} "
                        f"statt {quelle['klasse']!r} -- dann ist es ein neues Potenzial, kein Nachfolger"
                    )

    # Streichliste: einmal je Kennung, nichts aus diesem Lauf, nichts zugleich fortgeschrieben.
    gesehen = set()
    for g in prio["gestrichene_potenziale"]:
        pid = g["potenzial_id"]
        if pid in gesehen:
            befunde.append(f"{pid} steht zweimal auf der Streichliste")
        gesehen.add(pid)
        if pid in eigene:
            befunde.append(f"{pid} ist gestrichen und zugleich Potenzial dieses Laufs")
        if pid in vorgaenger:
            befunde.append(f"{pid} ist gestrichen und zugleich fortgeschrieben durch {vorgaenger[pid]}")
        quelle = geliefert.get(pid)
        if quelle is None:
            befunde.append(f"gestrichenes {pid} steht in keiner freigegebenen Lieferung")
        elif quelle["paket_id"] == paket:
            befunde.append(f"gestrichenes {pid} stammt aus demselben Paket")
        elif quelle["kp_id"] != g["kp_id"]:
            befunde.append(f"gestrichenes {pid} liegt in {quelle['kp_id']}, nicht in {g['kp_id']}")
    return befunde
