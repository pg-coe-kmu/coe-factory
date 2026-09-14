# -*- coding: utf-8 -*-
"""Erzeugt daten_v1_use_cases_testdaten.sql.

Die 90 Stufen stehen hier und nicht im SQL, damit die Summen nachrechenbar
bleiben: Wer die Reifegrade aendern will, aendert die Listen und laesst neu
erzeugen, statt 90 Zeilen von Hand zu korrigieren.
"""
import io

W = {"Technologie": [4, 4, 3, 4, 3, 3], "Prozessdaten": [3, 4, 3, 3, 4, 3],
     "Prozessqualitaet": [3, 3, 3, 3, 3, 3], "Kunden": [3, 3, 3, 4, 3, 3],
     "Skills": [3, 4, 3, 3, 3, 2]}                       # Summe 96 -> 3,20
O = {"Technologie": [3, 3, 3, 3, 3, 2], "Prozessdaten": [2, 3, 2, 3, 2, 2],
     "Prozessqualitaet": [3, 2, 3, 2, 3, 2], "Kunden": [3, 3, 2, 3, 3, 2],
     "Skills": [2, 2, 3, 2, 2, 2]}                       # Summe 75 -> 2,50
R = {"Technologie": [3, 2, 2, 3, 2, 2], "Prozessdaten": [2, 2, 2, 2, 2, 1],
     "Prozessqualitaet": [2, 2, 2, 2, 2, 2], "Kunden": [2, 2, 2, 2, 2, 2],
     "Skills": [2, 2, 2, 2, 2, 1]}                       # Summe 60 -> 2,00

ORD = ["Technologie", "Prozessdaten", "Prozessqualitaet", "Kunden", "Skills"]


def zeilen(tp, d, soll):
    out, nr, s = [], 1, 0
    for dim in ORD:
        assert len(d[dim]) == 6, (tp, dim)
        for stufe in d[dim]:
            out.append("      ('%s', %d, %d)" % (tp, nr, stufe))
            nr += 1
            s += stufe
    assert nr == 31 and abs(s / 30.0 - soll) < 1e-9, (tp, s, s / 30.0, soll)
    return out


werte = ",\n".join(zeilen("KP-05.TP-1", W, 3.20)
                   + zeilen("KP-06.TP-1", O, 2.50)
                   + zeilen("KP-06.TP-2", R, 2.00))

sql = io.open("gen_testdaten_vorlage.sql", encoding="utf-8").read().replace("@@WERTE@@", werte)
io.open("daten_v1_use_cases_testdaten.sql", "w", encoding="utf-8").write(sql)
print("geschrieben: %d Bytes, %d Wertzeilen" % (len(sql.encode()), werte.count("('KP-")))
