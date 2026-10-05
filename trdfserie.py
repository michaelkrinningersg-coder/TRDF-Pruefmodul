"""
TRDF-Pruefmodul - was erst im Vergleich mit der Serie auffaellt
===============================================================

Geblieben ist eine Pruefung: kann dieser Kohlenstoff so gemessen
worden sein? Mehr Carbonatkohlenstoff als Gesamtkohlenstoff kann es
nicht geben - das eine steckt im anderen. Trifft es zu, ist eine der
beiden Messungen falsch oder die Einheiten passen nicht zueinander.

Der organische Kohlenstoff
--------------------------
Gemessen wird der Gesamtkohlenstoff. In carbonathaltigen Boeden steckt
ein Teil davon im Kalk und sagt ueber die organische Substanz nichts
aus - abgezogen wird er ueber CO3. Im NW-FVA-Labor steht unter "CO3"
bereits der Kohlenstoff des Carbonats (C-CO3), also wird glatt
abgezogen. Sollte eine andere Stelle dort das Carbonat selbst fuehren,
ist CO3_ZU_C der eine Ort, an dem das umzustellen waere.

Was hier gestanden hat und warum es heraus ist
----------------------------------------------
Bis September 2026 verglich dieses Modul zusaetzlich den
Wiederfindungsgrad jeder Probe mit den Proben *derselben
Kohlenstoffklasse in derselben Serie*: Median als Mitte, mittlere
absolute Abweichung als Mass, auffaellig ab dem Dreifachen.

Die Annahme dahinter war, dass die Proben einer Serie miteinander
vergleichbar sind. Das sind sie nicht. Eine Serie traegt die Proben
vieler Plots, und Plots sind verschiedene Standorte mit verschiedenen
Boeden; die Streuung innerhalb einer Kohlenstoffklasse kommt damit zu
einem grossen Teil aus dem Standort und nicht aus der Messung. Die
Pruefung sprang zu oft an - und eine Pruefung, die zu oft anspringt,
wird ueberlesen. Dann sieht man auch den Befund nicht mehr, den sie
eigentlich finden sollte.

Wieder aufnehmen liesse sie sich mit dem *Plot* als Bezug: die Proben
eines Profils sind vergleichbar. Das Pruefmodul ist bewusst eine
Einzelauswertung je Serie und fuehrt keine Profilliste; die Profile
stehen in LabControl. Bis dahin lieber keine Pruefung als eine, die man
wegklickt.

Mit ihr gingen `klasse`, `mitten`, der Median und die Streuung: eine
Rechnung ohne Aufrufer stehen zu lassen waere das Gegenteil von
"herausgenommen" - sie faellt niemandem mehr auf und ist beim naechsten
Griff danach wieder da. Die Klasseneinteilung selbst ist nicht
verloren, sie steht in `trdfpruefung.KLASSEN`, wo sie hingehoert: dort
ist sie der Sollbereich der Trockenrohdichte.
"""

from __future__ import annotations

import trdf
import trdfpruefung
from trdf import D

# Womit CO3 in Kohlenstoff umgerechnet wird, bevor es abgezogen wird.
# Im Labor der NW-FVA ist der Parameter CO3 der Kohlenstoff des
# Carbonats (C-CO3) - also eins. Fuehrte eine Stelle dort das Carbonat
# selbst, waere es sein Kohlenstoffanteil: 12/60 fuer CO3, 12/100 fuer
# CaCO3.
CO3_ZU_C = D(1)

KOHLENSTOFF_NEGATIV = "CO3 groesser als Cges"


# Was der Serienblick beurteilt - fuer die Faerbung im Pruefblatt:
# welche Zellen der Befund meint.
BETROFFEN = {KOHLENSTOFF_NEGATIV: (trdfpruefung.CGES, trdfpruefung.CO3)}


def corg(cges, co3):
    """Der organische Kohlenstoff - Gesamtkohlenstoff ohne den im Kalk.

    Ohne Carbonat ist er der Gesamtkohlenstoff selbst: wo kein Kalk ist,
    steckt aller Kohlenstoff in der organischen Substanz. Ohne
    Gesamtkohlenstoff gibt es ihn nicht.
    """
    gesamt, karbonat = trdf.zahl(cges), trdf.zahl(co3)
    if gesamt is None:
        return None
    if karbonat is None:
        return gesamt
    return gesamt - karbonat * CO3_ZU_C


def kohlenstoff_bewerten(cges, co3) -> list:
    """Kann dieser Kohlenstoff so gemessen worden sein?

    Mehr Carbonatkohlenstoff als Gesamtkohlenstoff kann es nicht geben -
    das eine steckt im anderen. Trifft es zu, ist eine der beiden
    Messungen falsch oder die Einheiten passen nicht zueinander.
    """
    gefunden = corg(cges, co3)
    if gefunden is not None and gefunden < 0:
        return [KOHLENSTOFF_NEGATIV]
    return []


def bewerten(proben) -> dict:
    """Alle Befunde der Serie - Probennummer auf Saetze.

    Die Schleife ueber alle Proben ist geblieben, obwohl jede jetzt
    fuer sich beurteilt wird: eine Pruefung, die die ganze Serie
    ansieht, kommt hier wieder hinein, sobald der Plot der Bezug ist -
    siehe der Kopf dieser Datei.
    """
    befunde = {}
    for probe in proben:
        saetze = kohlenstoff_bewerten(probe.get("cges"), probe.get("co3"))
        if saetze:
            befunde[probe.get("probe")] = saetze
    return befunde
