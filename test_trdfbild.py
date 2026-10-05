"""Prueft das Streubild - Achsen, Baender, Punkte.

Ein Bild kann nicht "falsch rechnen", aber es kann falsch zeigen: ein
Punkt auf der falschen Seite einer Klassengrenze, ein Band, das den
falschen Bereich abdeckt. Beides sieht man nicht, sondern glaubt es -
deshalb steht es hier als Rechenaufgabe.

Aufruf:  xvfb-run -a python test_trdfbild.py
"""

from __future__ import annotations

import tkinter as tk

import trdfbild
import trdfpruefung
from trdf import D


def mit_fenster(pruefung):
    fenster = tk.Tk()
    fenster.geometry("900x600")
    fenster.update()
    try:
        pruefung(fenster)
    finally:
        fenster.destroy()


def bild(fenster, **rest):
    flaeche = trdfbild.Streubild(fenster, **rest)
    flaeche.pack()
    fenster.update()
    return flaeche


def probe(trdfw, cges=None, co3=None, marke=None, name="26B0001") -> dict:
    return {"probe": name, "trdf": trdfw, "cges": cges, "co3": co3,
            "marke": marke}


def kreise(flaeche):
    return [k for k in flaeche.find_all() if flaeche.type(k) == "oval"]


# --------------------------------------------------------------- Achsen

def test_die_kohlenstoffachse_ist_logarithmisch():
    def pruefen(fenster):
        flaeche = bild(fenster)
        # Gleiche Verhaeltnisse, gleiche Abstaende: von 1 auf 10 ist so
        # weit wie von 10 auf 100.
        erste = flaeche._x(D(10)) - flaeche._x(D(1))
        zweite = flaeche._x(D(100)) - flaeche._x(D(10))
        assert abs(erste - zweite) < 0.5
    mit_fenster(pruefen)


def test_die_dichteachse_ist_linear_und_steht_auf_dem_kopf():
    def pruefen(fenster):
        flaeche = bild(fenster)
        # Mehr Dichte heisst weiter oben, also kleineres y.
        assert flaeche._y(D(2)) < flaeche._y(D(1))
        mitte = (flaeche._y(D(0)) + flaeche._y(D("2.5"))) / 2
        assert abs(flaeche._y(D("1.25")) - mitte) < 0.5
    mit_fenster(pruefen)


def test_werte_ausserhalb_der_achse_bleiben_am_rand():
    def pruefen(fenster):
        flaeche = bild(fenster)
        assert flaeche._x(D(10000)) == flaeche._x(trdfbild.CGES_BIS)
        assert flaeche._y(D(9)) == flaeche._y(trdfbild.TRDF_BIS)
    mit_fenster(pruefen)


def test_die_marken_stehen_ohne_exponent_da():
    assert trdfbild._zahl(D(100)) == "100"
    assert trdfbild._zahl(D("0.5")) == "0,5"
    assert trdfbild._zahl(D("2.50")) == "2,5"


# --------------------------------------------------------------- Baender

def test_je_klasse_zwei_baender():
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([])
        rechtecke = [k for k in flaeche.find_all()
                     if flaeche.type(k) == "rectangle"]
        assert len(rechtecke) == 2 * len(trdfpruefung.KLASSEN)
    mit_fenster(pruefen)


def test_das_band_deckt_den_sollbereich_seiner_klasse():
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([])
        rechtecke = [k for k in flaeche.find_all()
                     if flaeche.type(k) == "rectangle"]
        # Das zweite Rechteck ist das engere Band der ersten Klasse
        # (ohne Carbonat): 1 bis 2 g/cm^3.
        _, oben, _, unten = flaeche.coords(rechtecke[1])
        assert abs(oben - flaeche._y(D(2))) < 0.5
        assert abs(unten - flaeche._y(D(1))) < 0.5
    mit_fenster(pruefen)


# ---------------------------------------------------------------- Punkte

def test_jede_probe_ein_punkt():
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([probe(D("1.4"), D(50), name=f"p{n}")
                          for n in range(7)])
        assert len(kreise(flaeche)) == 7
        assert len(flaeche.punkte) == 7
    mit_fenster(pruefen)


def test_ohne_dichte_kein_punkt():
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([probe(None, D(50)), probe("x", D(50))])
        assert kreise(flaeche) == []
    mit_fenster(pruefen)


def test_was_ausserhalb_liegt_ist_rot():
    def pruefen(fenster):
        flaeche = bild(fenster)
        # 50 g/kg ohne Carbonat: 0,4 bis 1,3 g/cm^3.
        flaeche.zeichnen([probe(D("1.0"), D(50)), probe(D("2.2"), D(50),
                                                        name="26B0002")])
        farben = [flaeche.itemcget(k, "fill") for k in kreise(flaeche)]
        assert farben == [trdfbild.FARBE_PUNKT, trdfbild.FARBE_BEFUND]
    mit_fenster(pruefen)


def test_carbonat_verschiebt_das_urteil_im_bild():
    def pruefen(fenster):
        flaeche = bild(fenster)
        # 1,9 g/cm^3 bei 5 g/kg: ohne Carbonat zu hoch, mit Carbonat nicht.
        flaeche.zeichnen([probe(D("1.9"), D(5)),
                          probe(D("1.9"), D(5), co3=D(1), name="26B0002")])
        farben = [flaeche.itemcget(k, "fill") for k in kreise(flaeche)]
        assert farben == [trdfbild.FARBE_BEFUND, trdfbild.FARBE_PUNKT]
    mit_fenster(pruefen)


def test_von_hand_bewegt_sticht_jede_farbe():
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([probe(D("2.2"), D(50), marke="geaendert")])
        assert flaeche.itemcget(kreise(flaeche)[0], "fill") == \
            trdfbild.FARBE_HAND
    mit_fenster(pruefen)


def test_ohne_aufschluss_steht_der_punkt_grau_am_rand():
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([probe(D("1.4"))])
        kreis = kreise(flaeche)[0]
        assert flaeche.itemcget(kreis, "fill") == \
            trdfbild.FARBE_OHNE_AUFSCHLUSS
        links, _, rechts, _ = flaeche.coords(kreis)
        assert abs((links + rechts) / 2 - flaeche._x(trdfbild.CGES_VON)) < 0.5
    mit_fenster(pruefen)


def test_das_carbonat_wird_vom_kohlenstoff_abgezogen():
    """Aufgetragen wird Corg: Cges 45 mit 40 im Kalk sind organisch 5."""
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([probe(D("1.4"), D(45), co3=D(40))])
        links, _, rechts, _ = flaeche.coords(kreise(flaeche)[0])
        assert abs((links + rechts) / 2 - flaeche._x(D(5))) < 0.5
    mit_fenster(pruefen)


# ----------------------------------------------------------------- Klick

def test_ein_klick_trifft_den_naechsten_punkt():
    def pruefen(fenster):
        getroffen = []
        flaeche = bild(fenster, bei_klick=getroffen.append)
        flaeche.zeichnen([probe(D("1.4"), D(50), name="26B0001"),
                          probe(D("0.6"), D(5), name="26B0002")])
        x, y, name = flaeche.punkte[1]
        flaeche.event_generate("<Button-1>", x=int(x), y=int(y))
        fenster.update()
        assert getroffen == [name]
    mit_fenster(pruefen)


def test_ein_klick_ins_leere_trifft_nichts():
    def pruefen(fenster):
        getroffen = []
        flaeche = bild(fenster, bei_klick=getroffen.append)
        flaeche.zeichnen([probe(D("1.4"), D(50))])
        x, y, _ = flaeche.punkte[0]
        assert flaeche.getroffen(x + 40, y + 40) is None
        assert flaeche.getroffen(x + 2, y + 2) == "26B0001"
    mit_fenster(pruefen)


def test_ohne_punkte_trifft_ein_klick_ins_leere():
    def pruefen(fenster):
        flaeche = bild(fenster)
        flaeche.zeichnen([])
        assert flaeche.getroffen(100, 100) is None
    mit_fenster(pruefen)


# --------------------------------------------------------------------------

def main() -> int:
    pruefungen = [(name, wert) for name, wert in sorted(globals().items())
                  if name.startswith("test_") and callable(wert)]
    fehler = 0
    for name, pruefstueck in pruefungen:
        try:
            pruefstueck()
        except AssertionError as ausnahme:
            fehler += 1
            print(f"FEHLGESCHLAGEN {name}: {ausnahme}")
        except Exception as ausnahme:            # noqa: BLE001
            fehler += 1
            print(f"FEHLER {name}: {type(ausnahme).__name__}: {ausnahme}")
        else:
            print(f"  ok  {name}")
    print(f"{len(pruefungen) - fehler} von {len(pruefungen)} "
          f"Pruefungen bestanden")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
