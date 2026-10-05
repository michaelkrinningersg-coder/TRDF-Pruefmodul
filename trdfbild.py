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
import tkinter as tk

import trdf
import trdfpruefung
import trdfserie
from trdf import D
from widgets import Style

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


class Streubild(tk.Canvas):
    """Ein Streudiagramm: Trockenrohdichte ueber organischem Kohlenstoff."""

    def __init__(self, eltern, bei_klick=None, breite=BREITE, hoehe=HOEHE):
        super().__init__(eltern, width=breite, height=hoehe, bg=Style.CARD,
                         highlightthickness=1,
                         highlightbackground=Style.BORDER)
        self.breite, self.hoehe = breite, hoehe
        self.bei_klick = bei_klick
        self.punkte = []          # (x, y, Probe)
        self.bind("<Button-1>", self._angeklickt)

    # ------------------------------------------------------------ Achsen
    def _x(self, kohlenstoff) -> float:
        wert = min(max(kohlenstoff, CGES_VON), CGES_BIS)
        anteil = ((_log(wert) - _log(CGES_VON))
                  / (_log(CGES_BIS) - _log(CGES_VON)))
        return RAND_LINKS + anteil * (self.breite - RAND_LINKS - RAND_RECHTS)

    def _y(self, dichte) -> float:
        wert = min(max(dichte, TRDF_VON), TRDF_BIS)
        anteil = float((wert - TRDF_VON) / (TRDF_BIS - TRDF_VON))
        unten = self.hoehe - RAND_UNTEN
        return unten - anteil * (unten - RAND_OBEN)

    def zeichnen(self, proben):
        """Zeichnet das Bild neu.

        `proben` sind Woerterbuecher mit "probe", "trdf", "cges", "co3"
        und "marke" - letzteres "geaendert", wenn der Wert von Hand
        bewegt wurde.
        """
        self.delete("all")
        self.punkte = []
        self._baender()
        self._achsen()
        for probe in proben:
            self._punkt(probe)

    def _baender(self):
        """Die Sollbereiche je Kohlenstoffklasse als liegende Balken."""
        von = CGES_VON
        for schranke, ohne, mit in trdfpruefung.KLASSEN:
            bis = CGES_BIS if schranke is None else min(schranke, CGES_BIS)
            if bis <= von:
                continue
            links, rechts = self._x(von), self._x(bis)
            for grenzen, farbe in ((mit, FARBE_MIT), (ohne, FARBE_OHNE)):
                self.create_rectangle(links, self._y(grenzen[1]), rechts,
                                      self._y(grenzen[0]), fill=farbe,
                                      width=0)
            if schranke is not None and schranke < CGES_BIS:
                self.create_line(rechts, RAND_OBEN, rechts,
                                 self.hoehe - RAND_UNTEN, fill=FARBE_GRENZE)
            von = bis

    def _achsen(self):
        unten = self.hoehe - RAND_UNTEN
        self.create_line(RAND_LINKS, unten, self.breite - RAND_RECHTS, unten,
                         fill=FARBE_ACHSE)
        self.create_line(RAND_LINKS, unten, RAND_LINKS, RAND_OBEN,
                         fill=FARBE_ACHSE)
        for marke in CGES_MARKEN:
            stelle = self._x(marke)
            self.create_line(stelle, unten, stelle, unten + 4,
                             fill=FARBE_ACHSE)
            self.create_text(stelle, unten + 14, text=_zahl(marke),
                             fill=Style.MUTED, font=Style.font(8))
        for marke in TRDF_MARKEN:
            stelle = self._y(marke)
            self.create_line(RAND_LINKS - 4, stelle, RAND_LINKS, stelle,
                             fill=FARBE_ACHSE)
            self.create_text(RAND_LINKS - 7, stelle, text=_zahl(marke),
                             anchor="e", fill=Style.MUTED,
                             font=Style.font(8))
        self.create_text(self.breite / 2, unten + 30,
                         text="organischer Kohlenstoff [g/kg]",
                         fill=Style.MUTED, font=Style.font(9))
        self.create_text(14, (unten + RAND_OBEN) / 2, angle=90,
                         text="Trockenrohdichte Feinboden [g/cm³]",
                         fill=Style.MUTED, font=Style.font(9))

    def _punkt(self, probe: dict):
        dichte = trdf.zahl(probe.get("trdf"))
        if dichte is None:
            return
        kohlenstoff = trdfserie.corg(probe.get("cges"), probe.get("co3"))
        if kohlenstoff is None or kohlenstoff <= 0:
            # Ohne Aufschluss gibt es keine Klasse - der Punkt gehoert
            # trotzdem ins Bild, aber an den Rand und in Grau.
            x, farbe = self._x(CGES_VON), FARBE_OHNE_AUFSCHLUSS
        else:
            x = self._x(kohlenstoff)
            farbe = FARBE_PUNKT
            if trdfpruefung.trdf_bewerten(dichte, kohlenstoff,
                                          trdf.zahl(probe.get("co3"))):
                farbe = FARBE_BEFUND
        if probe.get("marke") == "geaendert":
            farbe = FARBE_HAND
        y = self._y(dichte)
        self.create_oval(x - PUNKT, y - PUNKT, x + PUNKT, y + PUNKT,
                         fill=farbe, outline="")
        self.punkte.append((x, y, probe.get("probe")))

    # ------------------------------------------------------------- Klick
    def _angeklickt(self, ereignis):
        """Der naechstgelegene Punkt - wenn einer nahe genug liegt."""
        probe = self.getroffen(ereignis.x, ereignis.y)
        if probe is not None and self.bei_klick is not None:
            self.bei_klick(probe)

    def getroffen(self, x, y, umkreis=8):
        naechste, abstand = None, None
        for stelle_x, stelle_y, probe in self.punkte:
            weite = (stelle_x - x) ** 2 + (stelle_y - y) ** 2
            if abstand is None or weite < abstand:
                naechste, abstand = probe, weite
        if abstand is None or abstand > umkreis ** 2:
            return None
        return naechste


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
