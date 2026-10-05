"""Prueft das Hauptfenster - Anmeldung und Arbeitsmaske, ohne Datenbank.

Aufruf:  xvfb-run -a python test_trdfpruefmodul.py
"""

from __future__ import annotations

import tempfile
import tkinter as tk

import config
import lims_db
import trdfpruefmodul
import trdfreiter


class ZugangAttrappe:
    """So viel von lims_db.Zugang, wie das Fenster davon braucht."""

    benutzer = "pruefer"
    alias = "LIMS"
    modus = "Thin Mode"
    protokoll = None

    def __init__(self):
        self.geschlossen = False

    def verbindungsart(self) -> str:
        return "ohne Vorrat"

    def schliessen(self):
        self.geschlossen = True


def anwendung():
    """Ein Hauptfenster, dessen Einstellungen in einem leeren Ordner liegen."""
    ordner = tempfile.mkdtemp(prefix="trdfpruefmodul-")
    echt = trdfpruefmodul.Config
    trdfpruefmodul.Config = lambda: config.Config(runtime_dir=ordner)
    try:
        fenster = trdfpruefmodul.PruefmodulAnwendung()
    finally:
        trdfpruefmodul.Config = echt
    fenster.withdraw()
    # Im Bauplan wird nichts im Hintergrund gefragt.
    fenster.im_hintergrund = lambda *a, **k: None
    return fenster


def mit_anwendung(pruefung):
    fenster = anwendung()
    try:
        pruefung(fenster)
    finally:
        fenster.destroy()


def test_zur_wahl_steht_nur_lims():
    def pruefen(fenster):
        assert list(fenster.feld_alias.cget("values")) == ["LIMS"]
        assert fenster.v_alias.get() == "LIMS"
        assert str(fenster.feld_alias.cget("state")) == "readonly"
    mit_anwendung(pruefen)


def test_eine_gemerkte_testdatenbank_wird_zu_lims():
    assert trdfpruefmodul.zulaessige_datenbank("LIMSTEST") == "LIMS"
    assert trdfpruefmodul.zulaessige_datenbank("eco") == "LIMS"
    assert trdfpruefmodul.zulaessige_datenbank("lims") == "LIMS"
    assert trdfpruefmodul.zulaessige_datenbank(None) == "LIMS"


def test_die_anmeldung_sagt_woher_die_verbindung_kommt():
    def pruefen(fenster):
        text = fenster.tns_hinweis.cget("text")
        assert "tnsnames.ora" in text
        assert lims_db.tnsnames_pfad() in text
    mit_anwendung(pruefen)


def test_die_felder_sind_dieselben_wie_in_labcontrol():
    """Oracle-Benutzer, Passwort, Datenbank - in dieser Reihenfolge."""
    def pruefen(fenster):
        texte = []

        def sammeln(widget):
            for kind in widget.winfo_children():
                if isinstance(kind, tk.Label):
                    texte.append(kind.cget("text"))
                sammeln(kind)
        sammeln(fenster.rahmen)
        felder = [t for t in texte
                  if t in ("Oracle-Benutzer", "Passwort", "Datenbank")]
        assert felder == ["Oracle-Benutzer", "Passwort", "Datenbank"]
    mit_anwendung(pruefen)


def test_nach_der_anmeldung_steht_die_trdf_seite_da():
    def pruefen(fenster):
        fenster.zugang = ZugangAttrappe()
        fenster.arbeitsmaske()
        seite = fenster.trdf_seite
        assert isinstance(seite, trdfreiter.TrdfSeite)
        assert seite._zugang_holen() is fenster.zugang
        # Der Weg zur Serie: Serie, Abfragen, Untersuchungsmethode.
        assert hasattr(seite, "feld_serie")
        assert hasattr(seite, "feld_methode")
        assert seite.knopf_abfragen is not None
    mit_anwendung(pruefen)


def test_abmelden_schliesst_den_zugang():
    def pruefen(fenster):
        zugang = ZugangAttrappe()
        fenster.zugang = zugang
        fenster.arbeitsmaske()
        fenster._abmelden()
        assert zugang.geschlossen
        assert fenster.zugang is None
        assert fenster.trdf_seite is None
        assert hasattr(fenster, "feld_alias")      # wieder die Anmeldung
    mit_anwendung(pruefen)


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
