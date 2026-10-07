"""
TRDF-Pruefmodul - die Trockenrohdichte ueber dem Kohlenstoff
============================================================

Die Pruefung sagt, *dass* eine Dichte ausserhalb ihres Sollbereichs
liegt. Sie sagt nicht, wie weit - und auch nicht, ob die ganze Serie an
einer Klassengrenze klebt oder ob eine einzelne Probe herausfaellt.
Genau das zeigt dieses Bild: jede Probe ein Punkt, der Sollbereich
ihrer Kohlenstoffklasse als Band dahinter.

Warum der organische Kohlenstoff
--------------------------------
Aufgetragen wird Corg, nicht Cges: in carbonathaltigen Boeden steckt
ein Teil des Kohlenstoffs im Kalk und sagt ueber die organische
Substanz nichts aus. Die Klassengrenzen des Pruefplans sind dieselben.

Warum zwei Baender
------------------
Der Sollbereich haengt nicht nur am Kohlenstoff, sondern auch daran, ob
Carbonat gefunden wurde - mit Kalk darf der Boden dichter sein. Deshalb
liegt das weitere Band (mit Carbonat) hinter dem engeren, und jede
Probe wird gegen das gemessen, das fuer sie gilt. Ein Punkt im hellen
Streifen dazwischen ist also nur dann auffaellig, wenn er kein Carbonat
traegt - und genau so ist er dann auch gefaerbt.

Die Achse
---------
Der Kohlenstoff geht ueber vier Groessenordnungen, von einem Gramm je
Kilogramm bis ueber hundert. Linear aufgetragen kleben neun von zehn
Punkten am linken Rand; deshalb steht er logarithmisch, und die
Klassengrenzen (2, 10, 40, 100 g/kg) liegen dann ungefaehr gleich weit
auseinander.
"""

from __future__ import annotations

import decimal

import trdf
import trdfpruefung
import trdfserie
from trdf import D

BREITE = 720
HOEHE = 420
RAND_LINKS = 62
RAND_UNTEN = 46
RAND_OBEN = 16
RAND_RECHTS = 16

# Die Achsen. Der Kohlenstoff logarithmisch von 0,5 bis 400 g/kg, die
# Dichte linear von 0 bis 2,5 g/cm^3 - beides deckt jeden Boden ab, der
# im Gelaende vorkommt.
CGES_VON, CGES_BIS = D("0.5"), D(400)
TRDF_VON, TRDF_BIS = D(0), D("2.5")
CGES_MARKEN = (D(1), D(2), D(5), D(10), D(20), D(40), D(100), D(200))
TRDF_MARKEN = (D(0), D("0.5"), D(1), D("1.5"), D(2), D("2.5"))

# Die Baender: das engere gilt ohne Carbonat, das weitere mit.
FARBE_OHNE = "#dbeafe"
FARBE_MIT = "#eff6ff"
FARBE_GRENZE = "#cbd5e1"
FARBE_ACHSE = "#94a3b8"

# Die Punkte. Rot, was ausserhalb seines Bereichs liegt; violett, was
# von Hand bewegt wurde - dieselben Farben wie in den Tabellen.
FARBE_PUNKT = "#334155"
FARBE_BEFUND = "#b91c1c"
FARBE_HAND = "#7c3aed"
FARBE_OHNE_AUFSCHLUSS = "#94a3b8"

PUNKT = 3.5


def _log(wert: D) -> float:
    """Der Zehnerlogarithmus als Fliesskomma - fuer die Achse reicht das."""
    return float(wert.ln() / D(10).ln())


def _zahl(wert) -> str:
    """Eine Achsenmarke - ohne Exponent und ohne ueberfluessige Nullen.

    `normalize()` schreibt zehn als 1E+1; auf einer Achse liest das
    niemand.
    """
    try:
        text = format(wert.normalize(), "f")
    except (decimal.InvalidOperation, ValueError):
        return str(wert)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


# --------------------------------------------------------------------------
# Das Bild als Daten - fuer die Weboberflaeche, die es als SVG zeichnet
# --------------------------------------------------------------------------
def _x(kohlenstoff, breite=BREITE) -> float:
    wert = min(max(kohlenstoff, CGES_VON), CGES_BIS)
    anteil = ((_log(wert) - _log(CGES_VON))
              / (_log(CGES_BIS) - _log(CGES_VON)))
    return RAND_LINKS + anteil * (breite - RAND_LINKS - RAND_RECHTS)


def _y(dichte, hoehe=HOEHE) -> float:
    wert = min(max(dichte, TRDF_VON), TRDF_BIS)
    anteil = float((wert - TRDF_VON) / (TRDF_BIS - TRDF_VON))
    unten = hoehe - RAND_UNTEN
    return unten - anteil * (unten - RAND_OBEN)


def punktfarbe(probe: dict):
    """(x-Wert, Farbe) eines Punktes - None ohne Dichte.

    Ohne Aufschluss gibt es keine Klasse: der Punkt gehoert trotzdem ins
    Bild, aber an den linken Rand und in Grau.
    """
    dichte = trdf.zahl(probe.get("trdf"))
    if dichte is None:
        return None
    kohlenstoff = trdfserie.corg(probe.get("cges"), probe.get("co3"))
    if kohlenstoff is None or kohlenstoff <= 0:
        x, farbe = CGES_VON, FARBE_OHNE_AUFSCHLUSS
    else:
        x, farbe = kohlenstoff, FARBE_PUNKT
        if trdfpruefung.trdf_bewerten(dichte, kohlenstoff,
                                      trdf.zahl(probe.get("co3"))):
            farbe = FARBE_BEFUND
    if probe.get("marke") == "geaendert":
        farbe = FARBE_HAND
    return x, dichte, farbe


def bild(proben, breite=BREITE, hoehe=HOEHE) -> dict:
    """Alles, was im Bild steht, in Bildpunkten - Baender, Achsen, Punkte.

    Dieselbe Rechnung wie auf der Tk-Leinwand; gezeichnet wird anderswo.
    """
    unten = hoehe - RAND_UNTEN
    baender, grenzen = [], []
    von = CGES_VON
    for schranke, ohne, mit in trdfpruefung.KLASSEN:
        bis = CGES_BIS if schranke is None else min(schranke, CGES_BIS)
        if bis <= von:
            continue
        links, rechts = _x(von, breite), _x(bis, breite)
        for werte, farbe, art in ((mit, FARBE_MIT, "mit"),
                                  (ohne, FARBE_OHNE, "ohne")):
            baender.append({"x": links, "y": _y(werte[1], hoehe),
                            "b": rechts - links,
                            "h": _y(werte[0], hoehe) - _y(werte[1], hoehe),
                            "farbe": farbe, "art": art})
        if schranke is not None and schranke < CGES_BIS:
            grenzen.append(rechts)
        von = bis
    punkte = []
    for probe in proben:
        gefunden = punktfarbe(probe)
        if gefunden is None:
            continue
        x, dichte, farbe = gefunden
        punkte.append({"probe": probe.get("probe"), "x": _x(x, breite),
                       "y": _y(dichte, hoehe), "farbe": farbe,
                       "trdf": _zahl(dichte.quantize(D("0.001"))),
                       "corg": _zahl(x.quantize(D("0.1")))
                       if farbe != FARBE_OHNE_AUFSCHLUSS else ""})
    return {
        "breite": breite, "hoehe": hoehe,
        "links": RAND_LINKS, "rechts": breite - RAND_RECHTS,
        "oben": RAND_OBEN, "unten": unten,
        "baender": baender, "grenzen": grenzen,
        "xmarken": [{"x": _x(m, breite), "text": _zahl(m)}
                    for m in CGES_MARKEN],
        "ymarken": [{"y": _y(m, hoehe), "text": _zahl(m)}
                    for m in TRDF_MARKEN],
        "punkte": punkte}


# Die Fenster stehen in trdfbildfenster.py - die Weboberflaeche kommt ohne Tk
# aus. Wer sie hier sucht, findet sie trotzdem.
_FENSTER = ('Streubild',)


def __getattr__(name):
    if name in _FENSTER:
        # importlib, damit PyInstaller die Tk-Fenster nicht in die
        # Web-exe packt.
        import importlib
        return getattr(importlib.import_module("trdfbildfenster"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
