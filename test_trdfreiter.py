"""Prueft die Seite "TRDF Pruefung" - mit Fenster, ohne Datenbank.

Die Seite selbst holt ihre Daten aus dem LIMS; hier bekommt sie sie
gereicht. Genommen werden die echten Formeln und die echten Zeilen der
Serie 2026B051 aus test_trdf.py - so prueft dieser Durchstich dieselbe
Rechnung, die im Betrieb laeuft, und nicht eine nachgebaute.

Aufruf:  xvfb-run -a python test_trdfreiter.py
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile
import tkinter as tk
from tkinter import ttk

import test_trdf
import lims_db

import trdf
import trdfblock
import trdfexport
import trdfpruefung
import trdfrohpruefung
import trdflegende

import trdfreiter
from trdf import D

BEWERTUNG = trdfreiter.BEWERTUNGSSPALTE
FORMELN = test_trdf.FORMELN
ZEILEN = test_trdf.ZEILEN

# Die Rohwerte kommen aus derselben Quelle wie die Formeln: was in
# keiner Formel als Ergebnis steht, ist einer.
ROHWERTE = tuple(ZEILEN[1]["roh"])

# Im LIMS traegt derselbe Rohwert zwei Namen: am Rohwertparameter - und
# damit im Teilprobenanhang - ein kurzes Kuerzel, an der Pruefmethode
# das lange, mit dem die Formeln rechnen. Der Bauplan haelt beide
# auseinander, sonst faellt eine falsche Zuordnung hier nie auf.
KURZ = {lang: kurz for kurz, lang in trdf.ZUORDNUNG.items()}


def geholt(zeilen=(1, 5, 11, 33), aufschluss=(), formeln=None,
           nachtrag=(), part_id=1) -> dict:
    """Ein Abruf, wie ihn lims_db liefern wuerde.

    `formeln` sagt, welchen Satz die Serie fuehrt: den bisherigen oder
    den mit der zweiten Trockenrohdichte. Beides kommt vor, und die
    Formeln kommen ohnehin aus dem LIMS - hier steht nur, was es
    liefert.
    """
    formeln = FORMELN if formeln is None else formeln
    methoden = []
    for nummer, kuerzel in enumerate(formeln, start=1000):
        methoden.append({"pm_id": nummer, "pm_ver": 1,
                         "formelkuerzel": kuerzel, "formel": formeln[kuerzel],
                         "parameter": f"{kuerzel}TRDF3.2", "name": kuerzel})
    for nummer, kuerzel in enumerate(ROHWERTE, start=1):
        methoden.append({"pm_id": nummer, "pm_ver": 1,
                         "formelkuerzel": kuerzel, "formel": "",
                         "parameter": kuerzel, "name": kuerzel})
    nach_kuerzel = {m["formelkuerzel"]: m["pm_id"] for m in methoden}
    ergebnisse, wgh = [], {}
    for lnr in zeilen:
        probe = f"26B{lnr:04d}"
        wgh[lnr] = ZEILEN[lnr]["wgh"]
        for quelle in ("roh", "lims"):
            for kuerzel, wert in ZEILEN[lnr][quelle].items():
                # So kommt die Zeile aus lims_db: mit dem ganzen
                # Schluessel und den Spalten, die der Rueckweg anfasst.
                # GEGR_ID und PSTA_ID sind im LIMS nullable, und beides
                # kommt in einer Serie nebeneinander vor - das gehoert
                # in den Bauplan, sonst prueft nichts den Fall.
                ergebnisse.append({"prob_id": lnr, "probe_nr": probe,
                                   "wdh_um": 1, "wdh_me": 1, "lnr": lnr,
                                   "pm_id": nach_kuerzel[kuerzel],
                                   "pm_ver": 1, "um_id": 42,
                                   "gegr_id": 7 if lnr % 2 else None,
                                   "psta_id": 1 if lnr % 2 else None,
                                   "korrektur_flag": None, "fc8": None,
                                   "mw_roh": wert, "mw": wert,
                                   "serie": "2026B051",
                                   "part_id": part_id})
    # Der Teilprobenanhang traegt dieselben Rohwerte ein zweites Mal -
    # aus ihm rechnet das LIMS.
    am_anhang = []
    for lnr in zeilen:
        for nummer, kuerzel in enumerate(ROHWERTE, start=1):
            # Was in der Zeile gar nicht steht, hat auch am Anhang keine
            # Zeile - so ist es in der 2026B051 bei LNR 269.
            if kuerzel not in ZEILEN[lnr]["roh"]:
                continue
            am_anhang.append({"prob_id": lnr, "um_id": 42, "rohw_id": nummer,
                              "lnr": nummer,
                              "formelkuerzel": KURZ.get(kuerzel, kuerzel),
                              "art": "", "mw": ZEILEN[lnr]["roh"][kuerzel],
                              "mw_old": None, "format": None})
    return {"um_id": 42, "kuerzel": "TRDF3.2", "methoden": methoden,
            "rohwerte": [{"name": f"{k} lang",
                          "formelkuerzel": KURZ.get(k, k)}
                         for k in ROHWERTE],
            "ergebnisse": ergebnisse, "wgh": wgh, "anhang": am_anhang,
            "aufschluss": list(aufschluss),
            "aufschlussnachtrag": list(nachtrag or ()),
            "nachtragsfehler": ""}


def nachtragszeile(probe_nr, para_id, mw, prob_id=9001, serie="2025B012",
                   kuerzel="ATNULL") -> dict:
    """Ein Aufschluss, der an einer anderen Anlage derselben Probe haengt."""
    return {"probe_nr": probe_nr, "prob_id": prob_id, "serie": serie,
            "para_id": para_id, "kuerzel": kuerzel, "mw": mw}


class Meldungen:
    """Statt eines Fensters, das auf einen Klick wartet: eine Liste.

    Die Meldung nach dem Schreiben ist Teil der Auskunft und soll
    geprueft werden - aber ein Hinweisfenster haelt den Testlauf an,
    bis jemand klickt, und im Bauplan klickt niemand.
    """

    def __init__(self):
        self.gezeigt = []

    def showinfo(self, titel, satz, **rest):
        self.gezeigt.append(("info", titel, satz))

    def showwarning(self, titel, satz, **rest):
        self.gezeigt.append(("warnung", titel, satz))

    def showerror(self, titel, satz, **rest):
        self.gezeigt.append(("fehler", titel, satz))


def ohne_fenster() -> Meldungen:
    """Haengt die Hinweisfenster ab und gibt zurueck, was sie zeigen."""
    meldungen = Meldungen()
    trdfreiter.messagebox = meldungen
    return meldungen


# Die Pruefungen lesen die Tabellen aller Reiter, ohne den Reiter zu
# wechseln - also wird alles sofort gezeichnet. Wie die Seite verdeckte
# Reiter aufschiebt, pruefen eigene Faelle weiter unten.
trdfreiter.TrdfSeite.sofort_zeichnen = True


# Ein Zugang, der nur da ist: die Seite fragt, ob jemand angemeldet ist,
# und geht mit ihm nie in die Datenbank - der Hintergrundlauf tut hier
# nichts.
ZUGANG = object()


# Wohin eine Pruefung schreibt, die keinen eigenen Ordner mitbringt.
#
# Ohne Angabe nimmt `TrdfSeite` `config.get_runtime_dir()`, und das ist
# in einer Arbeitskopie das Programmverzeichnis selbst. Damit legte
# jeder Lauf dieser Datei Zeilen im echten `trdf_backup/` ab - im
# Aenderungsprotokoll, das die Korrekturen am LIMS fuehrt, standen
# hinterher die erfundenen Proben dieser Pruefung. Das ist nicht nur
# unordentlich: in dieser Datei steht, was tatsaechlich geschrieben
# wurde, und eine Zeile darin, die niemand geschrieben hat, ist eine
# falsche Auskunft.
AUSWEICHORDNER = tempfile.mkdtemp(prefix="trdfreiter-pruefung-")


def test_keine_pruefung_schreibt_neben_das_programm():
    """Die Wache zum Ausweichordner oben.

    `trdfexport.protokollieren` schreibt dorthin, wo die Seite ihren
    Ordner hat. Faellt der Ausweichordner weg, ist das wieder das
    Programmverzeichnis - und das faellt erst auf, wenn jemand das
    Aenderungsprotokoll liest und dort Proben findet, die es nicht
    gibt.
    """
    import config
    assert AUSWEICHORDNER != config.get_runtime_dir()

    def pruefen(fenster):
        assert seite(fenster)._ordner == AUSWEICHORDNER
    mit_fenster(pruefen)


def seite(fenster, **angaben):
    """Eine Seite mit abgerufener Serie - ohne Datenbank."""
    zugang = angaben.pop("zugang", ZUGANG)
    blatt = trdfreiter.TrdfSeite(fenster, lambda: zugang,
                                 lambda *a, **k: None,
                                 ordner=angaben.pop("ordner",
                                                    AUSWEICHORDNER))
    blatt.v_serie.set("2026B051")
    blatt._uebernehmen(geholt(**angaben))
    return blatt


def mit_fenster(pruefung):
    fenster = tk.Tk()
    fenster.withdraw()
    try:
        pruefung(fenster)
    finally:
        fenster.destroy()


# ------------------------------------------------------------ Der Abruf

def test_der_abruf_trennt_rohwerte_von_berechnetem():
    def pruefen(fenster):
        blatt = seite(fenster)
        assert set(blatt.formeln) == set(FORMELN)
        assert set(blatt.rohliste) == set(ROHWERTE)
        assert len(blatt.proben) == 4
        assert blatt.um_kuerzel == "TRDF3.2"
    mit_fenster(pruefen)


def test_die_rechnung_trifft_was_das_lims_gebucht_hat():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        gerechnet = blatt.gerechnet("26B0005")
        for kuerzel, gebucht in ZEILEN[5]["lims"].items():
            assert trdf.gleich(gerechnet.get(kuerzel), gebucht), kuerzel
    mit_fenster(pruefen)


def test_ein_wert_von_hand_geht_in_die_rechnung_ein():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        vorher = blatt.pruefwerte("26B0011")[trdfpruefung.TRDF]
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        assert blatt.rohwert("26B0011", "TRDFgesch") == "1,2"
        assert blatt.pruefwerte("26B0011")[trdfpruefung.TRDF] == D("1.2")
        assert vorher == D("1.8")
    mit_fenster(pruefen)


# ---------------------------------------------------------- Die Pruefung

def test_die_pruefwerte_kommen_aus_der_eigenen_rechnung():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        werte = blatt.pruefwerte("26B0005")
        assert trdf.gleich(werte[trdfpruefung.TRDF], "1,63465373129843")
        assert trdf.gleich(werte[trdfpruefung.SKA], "16,2728584982361")
        assert werte[trdfpruefung.GBFANT] == D(10)   # Rohwert, nicht gerechnet
        assert werte[trdfpruefung.FAKTOR] == D(1)
        assert werte[trdfpruefung.CGES] is None
        assert werte[trdfpruefung.CO3] is None
    mit_fenster(pruefen)


def test_der_aufschluss_landet_bei_der_richtigen_probe():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11), aufschluss=(
            {"prob_id": 5, "para_id": trdf.WGH_PM_ID and 31, "mw": "45"},
            {"prob_id": 11, "para_id": 33, "mw": "3"}))
        assert blatt.pruefwerte("26B0005")[trdfpruefung.CGES] == D(45)
        assert blatt.pruefwerte("26B0011")[trdfpruefung.CO3] == D(3)
        assert blatt.pruefwerte("26B0011")[trdfpruefung.CGES] is None
    mit_fenster(pruefen)


def test_der_kohlenstoff_entscheidet_ueber_das_urteil():
    def pruefen(fenster):
        # Zeile 11: TRDF 1,8 g/cm^3. Ohne Kohlenstoff geht das durch,
        # bei 50 g/kg ohne Karbonat ist es zu schwer.
        ohne = seite(fenster, zeilen=(11,))
        assert trdfpruefung.TRDF_ZU_HOCH not in ohne.geprueft()[0]["bewertung"]
        mit = seite(fenster, zeilen=(11,), aufschluss=(
            {"prob_id": 11, "para_id": 31, "mw": "50"},))
        assert trdfpruefung.TRDF_ZU_HOCH in mit.geprueft()[0]["bewertung"]
    mit_fenster(pruefen)


def test_das_blatt_ist_nach_probennummer_sortiert():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(33, 5, 11, 1))
        nummern = [zeile["probe"] for zeile in blatt.geprueft()]
        assert nummern == sorted(nummern)
    mit_fenster(pruefen)


def test_jede_geprueft_zeile_traegt_werte_und_urteil():
    def pruefen(fenster):
        for zeile in seite(fenster).geprueft():
            assert set(zeile) == {"lnr", "probe", "werte", "bewertung"}
            assert isinstance(zeile["bewertung"], list)
    mit_fenster(pruefen)


# ----------------------------------------------------------- Die Tabellen

def test_die_drei_tabellen_zeigen_jede_probe():
    def pruefen(fenster):
        blatt = seite(fenster)
        for tabelle in (blatt.rohtabelle, blatt.ergebnistabelle,
                        blatt.pruefungstabelle):
            assert len(tabelle.zeilen()) == 4
    mit_fenster(pruefen)


def test_das_pruefblatt_traegt_die_spalten_des_pruefplans():
    def pruefen(fenster):
        blatt = seite(fenster)
        assert blatt.pruefungstabelle.spalten() == list(trdfpruefung.SPALTEN)
        zeile = blatt.pruefungstabelle.zeilen()[0]
        assert blatt.pruefungstabelle.wert(zeile, "Probe-Nr.") \
            .startswith("26B")
    mit_fenster(pruefen)


def test_die_legende_nennt_die_namen_aus_dem_lims():
    def pruefen(fenster):
        text = seite(fenster).legende.cget("text")
        assert "TRDF3.2" in text and "ATNULLCO3" in text
        assert "TRD_TRDFTRDF3.2" in text     # der Parametername des LIMS
    mit_fenster(pruefen)


# ------------------------------------------------------------- Der Block

def test_ein_klick_auf_die_probe_oeffnet_ihren_block():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        blatt._block_zeigen("26B0005", "Probe-Nr.")
        block = blatt.bloecke["26B0005"]
        assert block.winfo_exists()
        assert [marke for marke, _ in block.lagen] == \
            [trdfblock.FEINBODEN, trdfblock.GROB_KLEIN,
             trdfblock.GROB_GROSS]
        # Variante 4, Schaetzung 10 Prozent: die oberste Lage steht fest.
        assert block.lagen[-1][1] == D(10)
    mit_fenster(pruefen)


def test_ein_klick_auf_eine_andere_spalte_oeffnet_nichts():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        blatt._block_zeigen("26B0005", "TRDF")
        assert not blatt.bloecke
    mit_fenster(pruefen)


def test_ein_geaenderter_rohwert_zeichnet_den_offenen_block_mit():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        blatt._block_zeigen("26B0005", "Probe-Nr.")
        block = blatt.bloecke["26B0005"]
        blatt._von_hand_geaendert("26B0005", "GBFAnt", "20")
        # Dasselbe Fenster, andere Zahlen - es geht nicht zu und wieder auf.
        assert block.winfo_exists()
        assert blatt.bloecke["26B0005"] is block
        assert block.lagen[-1][1] == D(20)
    mit_fenster(pruefen)


def test_der_block_zeigt_den_feinbodenvorrat():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        blatt._block_zeigen("26B0005", "Probe-Nr.")
        block = blatt.bloecke["26B0005"]
        assert block.feld_vorrat.cget("text").startswith("4105,9")
    mit_fenster(pruefen)


# ---------------------------------------------------- Der Weg zurueck

def test_ohne_handeingabe_gibt_es_nichts_zu_schreiben():
    def pruefen(fenster):
        assert seite(fenster).aenderungen() == []
    mit_fenster(pruefen)


def test_ein_geaenderter_rohwert_und_seine_folgen_stehen_zum_schreiben():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        kuerzel = [eine["kuerzel"] for eine in geaendert]
        assert kuerzel[0] == "TRDFgesch"
        assert geaendert[0]["art"] == trdfexport.ROHWERT
        # Variante 7 bucht die geschaetzte Dichte als TRDF; alles, was
        # daran haengt, muss mitwandern.
        assert "TRD_TRDF" in kuerzel and "FBVb" in kuerzel
        assert all(eine["zeile"] for eine in geaendert)
    mit_fenster(pruefen)


def test_was_sich_nicht_bewegt_hat_bleibt_draussen():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        # Derselbe Wert noch einmal: das ist keine Korrektur.
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,8")
        assert blatt.aenderungen() == []
    mit_fenster(pruefen)


def test_ein_befund_ohne_handeingabe_wird_nicht_geschrieben():
    def pruefen(fenster):
        # Zeile 104: das LIMS bucht 0, LabControl rechnet 1,8. Ein
        # Befund - aber niemand hat etwas geaendert, also faehrt der
        # Rueckweg nicht.
        blatt = seite(fenster, zeilen=(104,))
        assert blatt.aenderungen() == []
    mit_fenster(pruefen)


def test_die_uebersicht_zeigt_alt_und_neu():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        zeilen = trdfexport.uebersicht(blatt.aenderungen())
        erste = dict(zip(trdfexport.SPALTEN, zeilen[0]))
        assert erste["Probe-Nr."] == "26B0011"
        assert erste["Wert aktuell LIMS"] == "1,8"
        assert erste["Wert neu"] == "1,7"
        assert erste["PM_ID"] and erste["PM_VER"] == 1
    mit_fenster(pruefen)


def test_der_geaenderte_wert_faellt_in_allen_tabellen_auf():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        bewegt = blatt.bewegt("26B0011")
        assert "TRDFgesch" in bewegt and "TRD_TRDF" in bewegt
        # Der Wert selbst, die daraus gerechnete Dichte und dieselbe
        # Dichte im Pruefblatt - jede Zelle einzeln, nicht die Zeile.
        assert blatt.rohtabelle.marke("26B0011", "TRDFgesch") == "geaendert"
        assert blatt.ergebnistabelle.marke("26B0011",
                                           "TRD_TRDF ber.") == "geaendert"
        assert blatt.pruefungstabelle.marke("26B0011", "TRDF") == "geaendert"
        # Und der Nachbar in derselben Zeile bleibt unbehelligt.
        assert blatt.rohtabelle.marke("26B0011", "DichteGB") is None
    mit_fenster(pruefen)


def test_die_sicherung_traegt_den_stand_von_vorher():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
            pfad = trdfexport.backup_schreiben(
                os.path.join(basis, trdfexport.ORDNER), "2026B051",
                blatt.aenderungen(), dt.datetime(2026, 9, 8, 10, 0, 0))
            text = open(pfad, "rb").read().decode("cp1252", "replace")
            assert "2026B051 2026-09-08 100000.csv" in pfad
            assert "1,8" in text and "26B0011" in text
    mit_fenster(pruefen)


def test_das_aenderungsblatt_geht_als_csv_in_den_ordner():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
            trdfpruefung.oeffnen = lambda pfad: ""
            blatt._aenderungen_speichern()
            dateien = os.listdir(os.path.join(basis, trdfexport.ORDNER))
            assert dateien and dateien[0].startswith("Aenderungen ")
            assert "Aenderungen" in blatt.rohstand.cget("text")
    mit_fenster(pruefen)


def test_ohne_aenderung_meldet_der_gruene_knopf_das_auch():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._lims_schreiben()
        assert "nichts" in blatt.stand.cget("text")
    mit_fenster(pruefen)


def test_nach_dem_schreiben_ist_der_neue_wert_der_lims_stand():
    def pruefen(fenster):
        ohne_fenster()
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
            geaendert = blatt.aenderungen()
            blatt._geschrieben(geaendert, {"geschrieben": len(geaendert),
                                           "ohne_zeile": [], "versucht": 3},
                               "irgendwo.csv")
            assert not blatt.vonhand
            assert blatt.limsroh["26B0011"]["TRDFgesch"] == "1,7"
            assert blatt.aenderungen() == []          # nichts mehr offen
            assert "geschrieben" in blatt.stand.cget("text")
    mit_fenster(pruefen)


def test_was_geschrieben_wurde_steht_im_korrekturlog():
    def pruefen(fenster):
        ohne_fenster()
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
            geaendert = blatt.aenderungen()
            blatt._geschrieben(geaendert, {"geschrieben": len(geaendert),
                                           "ohne_zeile": [], "versucht": 3},
                               "irgendwo.csv")
            ordner = os.path.join(basis, trdfexport.ORDNER)
            dateien = [name for name in os.listdir(ordner)
                       if name.endswith(".txt")]
            assert dateien
            text = open(os.path.join(ordner, dateien[0]),
                        encoding="utf-8").read()
            assert "UPDATE ergebnisse" in text
            assert "TRDF-Korrektur 2026B051" in text
            assert text.count("UPDATE ergebnisse") == len(geaendert)
    mit_fenster(pruefen)


def test_eine_fehlende_ergebniszeile_wird_gemeldet_und_nicht_uebernommen():
    def pruefen(fenster):
        meldungen = ohne_fenster()
        basis = tempfile.mkdtemp()
        blatt = seite(fenster, zeilen=(11,), ordner=basis)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        zeile = geaendert[0]["zeile"]
        bericht = {"geschrieben": len(geaendert) - 1,
                   "ohne_zeile": [{"prob_id": zeile["prob_id"],
                                   "pm_id": zeile["pm_id"],
                                   "pm_ver": zeile["pm_ver"]}],
                   "versucht": len(geaendert)}
        blatt._geschrieben(geaendert, bericht, "irgendwo.csv")
        assert blatt.limsroh["26B0011"]["TRDFgesch"] == "1,8"   # unveraendert
        assert "nicht gefunden" in blatt.stand.cget("text")
        art, _, satz = meldungen.gezeigt[-1]
        assert art == "warnung" and "nicht gefunden" in satz
    mit_fenster(pruefen)


def test_das_schreiben_meldet_sich_im_fenster():
    """Ein Schreibweg, der still bleibt, laesst offen, ob er etwas
    getan hat."""
    def pruefen(fenster):
        meldungen = ohne_fenster()
        basis = tempfile.mkdtemp()
        blatt = seite(fenster, zeilen=(11,), ordner=basis)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        blatt._geschrieben(geaendert, {"geschrieben": len(geaendert),
                                       "ohne_zeile": [], "versucht": 3,
                                       "anhang_geschrieben": 1,
                                       "anhang_ohne_zeile": []},
                           "irgendwo.csv")
        art, titel, satz = meldungen.gezeigt[-1]
        assert art == "info" and "geschrieben" in titel
        assert "COMMIT" in satz and "irgendwo.csv" in satz
    mit_fenster(pruefen)


def test_keine_getroffene_zeile_faellt_auf():
    """Die Anweisung lief fehlerfrei durch und hat trotzdem nichts
    getan - das ist der Fall, der sonst niemandem auffaellt."""
    def pruefen(fenster):
        meldungen = ohne_fenster()
        basis = tempfile.mkdtemp()
        blatt = seite(fenster, zeilen=(11,), ordner=basis)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        blatt._geschrieben(geaendert,
                           {"geschrieben": 0, "versucht": len(geaendert),
                            "ohne_zeile": [{"prob_id": 11, "pm_id": 1,
                                            "pm_ver": 1}],
                            "anhang_geschrieben": 0,
                            "anhang_ohne_zeile": []}, "irgendwo.csv")
        art, titel, satz = meldungen.gezeigt[-1]
        assert art == "warnung" and "nichts geschrieben" in titel
        assert "GEGR_ID" in satz          # der Schluessel, an dem es liegt
    mit_fenster(pruefen)


def test_ein_wert_der_nicht_ankam_heisst_update_fehlgeschlagen():
    """Getroffen und trotzdem unveraendert: der Stand im Fenster darf
    dann nicht so tun, als waere es geschehen."""
    def pruefen(fenster):
        meldungen = ohne_fenster()
        basis = tempfile.mkdtemp()
        blatt = seite(fenster, zeilen=(11,), ordner=basis)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        roh = [eine for eine in geaendert
               if eine["kuerzel"] == "TRDFgesch"][0]
        blatt._geschrieben(geaendert, {
            "geschrieben": len(geaendert), "versucht": len(geaendert),
            "ohne_zeile": [], "anhang_geschrieben": 1,
            "anhang_ohne_zeile": [],
            "nicht_uebernommen": [{"prob_id": roh["zeile"]["prob_id"],
                                   "pm_id": roh["zeile"]["pm_id"],
                                   "pm_ver": roh["zeile"]["pm_ver"]}],
            "anhang_nicht_uebernommen": []}, "irgendwo.csv")
        art, titel, satz = meldungen.gezeigt[-1]
        assert art == "fehler" and titel == "Update fehlgeschlagen"
        assert "26B0011 TRDFgesch" in satz
        # Der alte Stand bleibt stehen, und die Aenderung bleibt offen.
        assert blatt.limsroh["26B0011"]["TRDFgesch"] == "1,8"
        assert ("26B0011", "TRDFgesch") in blatt.vonhand
    mit_fenster(pruefen)


def test_was_ankam_gilt_auch_wenn_anderes_nicht_ankam():
    def pruefen(fenster):
        ohne_fenster()
        basis = tempfile.mkdtemp()
        blatt = seite(fenster, zeilen=(11,), ordner=basis)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        gerechnet = [eine for eine in geaendert
                     if eine["kuerzel"] == "TRD_TRDF"][0]
        blatt._geschrieben(geaendert, {
            "geschrieben": len(geaendert), "versucht": len(geaendert),
            "ohne_zeile": [], "anhang_geschrieben": 1,
            "anhang_ohne_zeile": [],
            "nicht_uebernommen": [{"prob_id": gerechnet["zeile"]["prob_id"],
                                   "pm_id": gerechnet["zeile"]["pm_id"],
                                   "pm_ver": gerechnet["zeile"]["pm_ver"]}],
            "anhang_nicht_uebernommen": []}, "irgendwo.csv")
        # Der Rohwert kam an, die daraus gerechnete Groesse nicht.
        assert blatt.limsroh["26B0011"]["TRDFgesch"] == "1,7"
        assert blatt.gebucht["26B0011"]["TRD_TRDF"] == "1,8"
    mit_fenster(pruefen)


def test_ein_fehler_beim_schreiben_bleibt_nicht_in_der_statuszeile():
    def pruefen(fenster):
        meldungen = ohne_fenster()
        blatt = seite(fenster, zeilen=(11,))
        blatt._schreiben_schiefgegangen(RuntimeError("ORA-00001"))
        art, _, satz = meldungen.gezeigt[-1]
        assert art == "fehler" and "ORA-00001" in satz
        assert "ORA-00001" in blatt.stand.cget("text")
    mit_fenster(pruefen)


def test_die_vorschau_zeigt_hoechstens_drei_nachkommastellen():
    """Sie soll aussehen wie die Tabellen daneben - geschrieben wird
    trotzdem mit allen Stellen."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "DichteGB", "2,9")
        geaendert = blatt.aenderungen()
        vorschau = trdfreiter.Exportvorschau(
            fenster, geaendert, "2026B051", lambda: None)
        for kennung in vorschau.baum.get_children():
            for wert in vorschau.baum.item(kennung)["values"][-2:]:
                stellen = str(wert).partition(",")[2]
                assert len(stellen) <= 3, wert
        # Geschickt wird weiter die ganze Zahl.
        assert any(len(str(satz["wert"]).partition(",")[2]) > 3
                   for satz in trdfexport.saetze(geaendert))
    mit_fenster(pruefen)


def test_die_vorschau_laesst_sich_zur_seite_rollen():
    """Zehn Spalten passen nicht in jedes Fenster, und gerade die
    letzte - der neue Wert - ist die, um die es geht."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        vorschau = trdfreiter.Exportvorschau(
            fenster, blatt.aenderungen(), "2026B051", lambda: None)
        fenster.update()
        leisten = [kind for kind in vorschau.baum.master.winfo_children()
                   if isinstance(kind, ttk.Scrollbar)]
        richtungen = {str(leiste.cget("orient")) for leiste in leisten}
        assert richtungen == {"horizontal", "vertical"}
        assert vorschau.baum.cget("xscrollcommand")
    mit_fenster(pruefen)


def test_die_vorschau_zeigt_jede_zeile_und_schreibt_erst_auf_zuruf():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        gerufen = []
        fenster_vorschau = trdfreiter.Exportvorschau(
            fenster, geaendert, "2026B051", lambda: gerufen.append(1))
        assert len(fenster_vorschau.baum.get_children()) == len(geaendert)
        assert not gerufen                      # noch nichts geschehen
        fenster_vorschau._schreiben()
        assert gerufen == [1]
    mit_fenster(pruefen)


def test_die_vorschau_sagt_was_beim_zurueckspielen_leer_wird():
    """Eine leere Zelle laese sich als "hier geschieht nichts"."""
    def pruefen(fenster):
        zeilen = [{"Serie": "2026B051", "Probe-Nr.": "26B0011",
                   "Groesse": "TRDF", "PROB_ID": "11", "PM_ID": "1084",
                   "PM_VER": "1", "UM_ID": "42", "GEGR_ID": "",
                   "MW_ROH": "", "MW": "", "PSTA_ID": "",
                   "KORREKTUR_FLAG": "", "FC8": "", "ROHW_ID": "",
                   "Anhang MW": "", "Anhang MW_OLD": "", "Wert neu": "1,7"}]
        geaendert = trdfexport.zurueck(zeilen)
        vorschau = trdfreiter.Exportvorschau(fenster, geaendert, "Alt.csv",
                                             lambda: None, zurueck=True)
        saetze = [kind.cget("text") for kind in vorschau.winfo_children()
                  if isinstance(kind, tk.Label)]
        assert any("stand vor der Korrektur nichts" in satz
                   for satz in saetze), saetze
        werte = vorschau.baum.item(vorschau.baum.get_children()[0])["values"]
        assert str(werte[-1]) == trdfexport.LEER_TEXT
    mit_fenster(pruefen)


# --------------------------------------------------- Der Teilprobenanhang

def test_der_anhang_wird_mitgelesen():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        zeile = blatt.anhang[("26B0011", "TRDFgesch")]
        assert zeile["rohw_id"] and zeile["mw"] == "1,8"
    mit_fenster(pruefen)


def test_ein_geaenderter_rohwert_geht_an_beide_stellen():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        roh = [eine for eine in geaendert
               if eine["art"] == trdfexport.ROHWERT][0]
        assert roh["anhang"] is not None
        assert trdfexport.ziel(roh) == trdfexport.ZIEL_BEIDE
        saetze = trdfexport.anhangsaetze(geaendert)
        assert len(saetze) == 1
        assert saetze[0]["wert"] == "1,7"
        assert saetze[0]["rohw_id"] == roh["anhang"]["rohw_id"]
    mit_fenster(pruefen)


def test_der_anhang_findet_auch_die_andere_anlage_derselben_probe():
    """Dieselbe Probe steht im LIMS unter mehreren PROB_ID - einmal je
    Untersuchungsmethode. Die Ergebniszeile kommt dann unter der
    einen, der Teilprobenanhang unter der anderen.

    Vorher fiel er dabei still heraus: `_anhang_zuordnen` schlug die
    PROB_ID in den Ergebniszeilen nach, fand sie nicht, und liess die
    Zeile fallen. Die Rohwerte standen im LIMS, im Reiter stand
    nichts, und keine Meldung sagte warum.
    """
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        # Die Ergebnisse der Probe stehen an einer Anlage, der Anhang
        # an einer anderen - dieselbe Probennummer.
        probe = blatt.proben[0][1]
        eigene = next(zeile for zeile in blatt.zeilen.values())
        blatt.anhang = {}
        blatt._anhang_zuordnen({
            "ergebnisse": [{"prob_id": 447370, "probe_nr": probe}],
            "anhang": [{"prob_id": 478965, "probe_nr": probe,
                        "formelkuerzel": "T", "mw": "0,1357"}]})
        assert blatt.anhang, "der Anhang der anderen Anlage fehlt"
        assert list(blatt.anhang)[0][0] == probe
        assert eigene is not None
        # Eine fremde Probennummer bleibt draussen: was der Abruf
        # nicht gebracht hat, gehoert nicht in diese Serie.
        blatt.anhang = {}
        blatt._anhang_zuordnen({
            "ergebnisse": [{"prob_id": 447370, "probe_nr": probe}],
            "anhang": [{"prob_id": 999999, "probe_nr": "2099B09999",
                        "formelkuerzel": "T", "mw": "1,0"}]})
        assert blatt.anhang == {}
    mit_fenster(pruefen)


def test_nachgefragt_wird_nur_wo_kein_anhang_kam():
    """Steht der Anhang an jeder Probe der Serie - der Regelfall -,
    entfaellt die zweite Abfrage ganz."""
    ergebnisse = [{"prob_id": 1, "probe_nr": "26B0011"},
                  {"prob_id": 2, "probe_nr": "26B0012"}]
    # Beide haben einen Anhang: nichts offen.
    assert trdfreiter._ohne_anhang(ergebnisse, [
        {"prob_id": 1, "probe_nr": "26B0011"},
        {"prob_id": 2, "probe_nr": "26B0012"}]) == []
    # Einer fehlt: genau der wird nachgefragt.
    assert trdfreiter._ohne_anhang(ergebnisse, [
        {"prob_id": 1, "probe_nr": "26B0011"}]) == [2]
    # Und wo der Anhang unter einer anderen Anlage derselben Probe
    # kam, ist er da - ein zweites Mal zu fragen braechte dieselben
    # Zeilen.
    assert trdfreiter._ohne_anhang(ergebnisse, [
        {"prob_id": 1, "probe_nr": "26B0011"},
        {"prob_id": 478965, "probe_nr": "26B0012"}]) == []
    # Ohne Anhang sind alle offen.
    assert trdfreiter._ohne_anhang(ergebnisse, []) == [1, 2]


def test_die_nachfrage_nimmt_nur_die_gewaehlte_methode():
    """Wer TRDF3.2 abruft, bekommt die Rohwerte der TRDF3.2 - nicht
    die der verworfenen TRDF3.1, die daneben an derselben Probe
    haengt."""
    gefragt = {}

    def nachtrag(_zugang, prob_ids, um_id, **_rest):
        gefragt["ids"], gefragt["um_id"] = list(prob_ids), um_id
        return [{"prob_id": 478965, "probe_nr": "26B0012", "um_id": um_id,
                 "rohw_id": 1, "lnr": 1, "formelkuerzel": "T", "art": "",
                 "mw": "0,1357", "mw_old": None, "format": None}]

    echt = lims_db.trdf_rohwerte_nachtrag
    lims_db.trdf_rohwerte_nachtrag = nachtrag
    try:
        gebaut = trdfreiter._mit_nachtrag(
            None, 261,
            [{"prob_id": 1, "probe_nr": "26B0011"},
             {"prob_id": 2, "probe_nr": "26B0012"}],
            [{"prob_id": 1, "probe_nr": "26B0011", "formelkuerzel": "T"}])
    finally:
        lims_db.trdf_rohwerte_nachtrag = echt
    assert gefragt == {"ids": [2], "um_id": 261}
    assert len(gebaut) == 2
    # Und ohne offene Probe wird gar nicht gefragt.
    gefragt.clear()
    lims_db.trdf_rohwerte_nachtrag = nachtrag
    try:
        trdfreiter._mit_nachtrag(
            None, 261, [{"prob_id": 1, "probe_nr": "26B0011"}],
            [{"prob_id": 1, "probe_nr": "26B0011", "formelkuerzel": "T"}])
    finally:
        lims_db.trdf_rohwerte_nachtrag = echt
    assert gefragt == {}


def test_berechnete_groessen_haengen_nicht_am_anhang():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        for eine in blatt.aenderungen():
            if eine["art"] == trdfexport.BERECHNET:
                assert eine["anhang"] is None
                assert trdfexport.ziel(eine) == trdfexport.ZIEL_ERGEBNIS
    mit_fenster(pruefen)


def test_gehen_die_beiden_stellen_auseinander_faellt_es_auf():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        assert blatt.rohbefund("26B0011") == []
        # Im LIMS steht am Anhang etwas anderes als in der Ergebniszeile.
        blatt.anhang[("26B0011", "DichteGB")]["mw"] = "2,9"
        befund = blatt.rohbefund("26B0011")
        assert befund == [trdfrohpruefung.ANHANG_ANDERS.format("DichteGB")]
    mit_fenster(pruefen)


def test_was_von_hand_geaendert_ist_zaehlt_nicht_als_abweichung():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "DichteGB", "2,9")
        assert blatt.rohbefund("26B0011") == []
    mit_fenster(pruefen)


def test_nach_dem_schreiben_gilt_der_wert_auch_am_anhang():
    def pruefen(fenster):
        ohne_fenster()
        basis = tempfile.mkdtemp()
        blatt = seite(fenster, zeilen=(11,), ordner=basis)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        blatt._geschrieben(geaendert, {"geschrieben": len(geaendert),
                                       "ohne_zeile": [], "versucht": 3,
                                       "anhang_geschrieben": 1,
                                       "anhang_ohne_zeile": []},
                           "irgendwo.csv")
        assert blatt.anhang[("26B0011", "TRDFgesch")]["mw"] == "1,7"
        assert blatt.rohbefund("26B0011") == []      # beide Stellen einig
    mit_fenster(pruefen)


def test_die_sicherung_haelt_auch_den_anhang_fest():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
            pfad = trdfexport.backup_schreiben(
                os.path.join(basis, trdfexport.ORDNER), "2026B051",
                blatt.aenderungen(), dt.datetime(2026, 9, 8, 10, 0, 0))
            text = open(pfad, "rb").read().decode("cp1252", "replace")
            assert "ROHW_ID" in text and "Anhang MW" in text
    mit_fenster(pruefen)


def test_massen_anteile_und_vorraete_tragen_eine_stelle():
    """Drei Nachkommastellen an einem Vorrat behaupten ein Milligramm
    je Hektar - eine genuegt."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        ergebnisse, pruefblatt = blatt.ergebnistabelle, blatt.pruefungstabelle
        assert ergebnisse.wert("26B0005", "FBVb ber.") == "4105,9"
        assert ergebnisse.wert("26B0005", "FBMSZ ber.") == "798,8"
        assert ergebnisse.wert("26B0005", "_SKA ber.") == "16,3"
        assert pruefblatt.wert("26B0005", "FBVorrat") == "4105,9"
        assert pruefblatt.wert("26B0005", "Skelettanteil") == "16,3"
        assert pruefblatt.wert("26B0005", "SKA63") == "12,9"
        # Die Volumenanteile ebenso - sie sind Prozente.
        assert ergebnisse.wert("26B0005", "VOLAntGB263 ber.") == "6,3"
        assert ergebnisse.wert("26B0005", "VOLGB63gs ber.") == "10,0"
        assert pruefblatt.wert("26B0005", "GBFAnt63gs") == "10,0"
        # Die Dichte bleibt bei drei Stellen - sie wird auf zwei gemessen.
        assert ergebnisse.wert("26B0005", "TRD_TRDF ber.") == "1,635"
        assert pruefblatt.wert("26B0005", "TRDF") == "1,635"
    mit_fenster(pruefen)


def test_die_beiden_spalten_einer_groesse_gehoeren_zusammen():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        tabelle = blatt.ergebnistabelle
        # Beide Spalten einer Groesse tragen denselben Hintergrund, die
        # naechste Groesse den anderen.
        erste = blatt.folge[0]
        zweite = blatt.folge[1]
        assert tabelle.marke("26B0005", f"{erste} LIMS") == \
            tabelle.marke("26B0005", f"{erste} ber.")
        assert tabelle.marke("26B0005", f"{zweite} LIMS") == \
            tabelle.marke("26B0005", f"{zweite} ber.")
        assert tabelle.marke("26B0005", f"{erste} LIMS") != \
            tabelle.marke("26B0005", f"{zweite} LIMS")
        assert "gruppe" in (tabelle.marke("26B0005", f"{erste} LIMS"),
                            tabelle.marke("26B0005", f"{zweite} LIMS"))
    mit_fenster(pruefen)


def test_die_ergebnisse_haben_eine_bewertung():
    def pruefen(fenster):
        # Zeile 104: das LIMS bucht 0, LabControl rechnet 1,8.
        blatt = seite(fenster, zeilen=(104,))
        tabelle = blatt.ergebnistabelle
        satz = tabelle.wert("26B0104", trdfreiter.BEWERTUNGSSPALTE)
        assert satz.startswith("LIMS ungleich gerechnet")
        assert "TRD_TRDF" in satz
        assert tabelle.marke("26B0104",
                             trdfreiter.BEWERTUNGSSPALTE) == "abweichung"
        assert tabelle.marke("26B0104", "TRD_TRDF LIMS") == "abweichung"
    mit_fenster(pruefen)


def test_wo_alles_stimmt_bleibt_die_bewertung_leer():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        tabelle = blatt.ergebnistabelle
        assert tabelle.wert("26B0005", trdfreiter.BEWERTUNGSSPALTE) == ""
        assert tabelle.marke("26B0005",
                             trdfreiter.BEWERTUNGSSPALTE) is None
    mit_fenster(pruefen)


def test_von_hand_bewegt_sticht_auch_in_den_ergebnissen():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        tabelle = blatt.ergebnistabelle
        assert tabelle.marke("26B0011", "TRD_TRDF ber.") == "geaendert"
        # Die Bewertung nennt die Groesse trotzdem: sie geht jetzt
        # auseinander, weil von Hand etwas anderes dasteht.
        assert "TRD_TRDF" in tabelle.wert("26B0011",
                                          trdfreiter.BEWERTUNGSSPALTE)
    mit_fenster(pruefen)


def test_der_wassergehalt_steht_mit_einer_stelle():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        # Im LIMS steht 1,20955548835796.
        assert blatt.rohtabelle.wert("26B0011", "WGH") == "1,2"
        assert blatt.ergebnistabelle.wert("26B0011", "WGH") == "1,2"
        # Gerechnet wird weiter mit dem vollen Wert.
        assert blatt.wgh["26B0011"] == "1,20955548835796"
    mit_fenster(pruefen)


def test_eine_zeile_ohne_rohwerte_ist_kein_fehler():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt.limsroh["26B0011"] = {}
        blatt.anhang = {}
        assert blatt.rohbefund("26B0011") == [trdfrohpruefung.KEINE_DATEN]
    mit_fenster(pruefen)


def test_der_befund_faerbt_die_zelle_um_die_es_geht():
    def pruefen(fenster):
        # 50 g/kg Kohlenstoff ohne Carbonat: bis 1,3 g/cm^3, die Probe
        # hat 1,8.
        blatt = seite(fenster, zeilen=(11,), aufschluss=(
            {"prob_id": 11, "para_id": 31, "mw": "50"},))
        tabelle = blatt.pruefungstabelle
        assert tabelle.marke("26B0011", "TRDF") == "abweichung"
        assert tabelle.marke("26B0011", "Bewertung") == "abweichung"
        # Der Kohlenstoff ist der Massstab, nicht der Befund.
        assert tabelle.marke("26B0011", "Cges") is None
        assert tabelle.marke("26B0011", "Skelettanteil") is None
    mit_fenster(pruefen)


def test_von_hand_bewegt_sticht_den_befund():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,), aufschluss=(
            {"prob_id": 11, "para_id": 31, "mw": "50"},))
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,25")
        # Jetzt liegt die Dichte im Bereich und ist von Hand bewegt.
        assert blatt.pruefungstabelle.marke("26B0011", "TRDF") == "geaendert"
    mit_fenster(pruefen)


def test_die_bewertung_bekommt_platz_wenn_etwas_darin_steht():
    def pruefen(fenster):
        ohne = seite(fenster, zeilen=(5,))
        schmal = ohne.pruefungstabelle._breiten[trdfreiter.BEWERTUNGSSPALTE]
        mit = seite(fenster, zeilen=(11,), aufschluss=(
            {"prob_id": 11, "para_id": 31, "mw": "50"},))
        breit = mit.pruefungstabelle._breiten[trdfreiter.BEWERTUNGSSPALTE]
        assert breit >= schmal * 3
        assert breit >= len(trdfpruefung.TRDF_ZU_HOCH)
    mit_fenster(pruefen)


def test_der_schalter_zeigt_nur_die_proben_mit_befund():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11), aufschluss=(
            {"prob_id": 11, "para_id": 31, "mw": "50"},))
        assert not blatt.v_nur_befunde.get()          # aus, wie vorgesehen
        assert len(blatt.pruefungstabelle.zeilen()) == 2
        blatt.v_nur_befunde.set(True)
        blatt._pruefung_zeigen()
        assert blatt.pruefungstabelle.zeilen() == ["26B0011"]
        assert "1 ausgeblendet" in blatt.pruefstand.cget("text")
        blatt.v_nur_befunde.set(False)
        blatt._pruefung_zeigen()
        assert len(blatt.pruefungstabelle.zeilen()) == 2
    mit_fenster(pruefen)


def test_variante_x_laesst_sich_ausblenden_und_wird_trotzdem_geschrieben():
    """Ein Schalter fuer alle drei Reiter, von Haus aus aus. Nur die
    Anzeige: was an einer ausgeblendeten Probe geaendert ist, geht mit
    in den Export."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        assert not blatt.v_ohne_x.get()
        assert len(blatt.schalter_ohne_x) == 3
        blatt._von_hand_geaendert("26B0011", "_TRDV", "x")
        assert blatt.variante_x("26B0011")
        blatt.v_ohne_x.set(True)
        blatt._zeigen()
        assert blatt.rohtabelle.zeilen() == ["26B0005"]
        assert blatt.ergebnistabelle.zeilen() == ["26B0005"]
        assert blatt.pruefungstabelle.zeilen() == ["26B0005"]
        assert "1 ausgeblendet" in blatt.rohstand.cget("text")
        assert "1 Proben ausgeblendet" in blatt.stand.cget("text")
        assert any(eine["probe"] == "26B0011" for eine in blatt.aenderungen())
        blatt.v_ohne_x.set(False)
        blatt._zeigen()
        assert len(blatt.rohtabelle.zeilen()) == 2
    mit_fenster(pruefen)


def test_das_blatt_als_csv_bleibt_vollstaendig():
    """Es ist der Nachweis ueber die Serie, nicht ueber ihre
    Auffaelligkeiten."""
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(5, 11), ordner=basis,
                          aufschluss=({"prob_id": 11, "para_id": 31,
                                       "mw": "50"},))
            blatt.v_nur_befunde.set(True)
            blatt._pruefung_zeigen()
            trdfpruefung.oeffnen = lambda pfad: ""
            blatt._blatt_speichern()
            ordner = os.path.join(basis, trdfpruefung.ORDNER)
            pfad = os.path.join(ordner, os.listdir(ordner)[0])
            text = open(pfad, "rb").read().decode("cp1252", "replace")
            assert "26B0005" in text and "26B0011" in text
    mit_fenster(pruefen)


# ------------------------------------------- Die Quelle - von selbst

# Eine eingefuegte UM aus der Probenvorbereitung, so wie sie aus
# "aktueller Block -> kopieren" kommt - mit einem Wert fuer 26B0011.
UM_TEXT = "\n".join([
    "Serie\t2026B051",
    "Untersuchungsmethode\tTRDF3.2",
    "\t\t\t\t\tSortier # -->\t1",
    "LNR\tText\tProbenummer\tUM\tMe\tFaktor\tTRDFgesch lang",
    "\t\t\t\t\t\tg/cm3",
    "11\t\t26B0011\t1\t1\t1,0000\t1,5",
])


def test_ohne_eingefuegte_um_gilt_das_lims():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        assert blatt.quelle == trdfreiter.QUELLE_LIMS
        assert blatt.aus_der_quelle("26B0011", "TRDFgesch") is None
        assert blatt.rohwert("26B0011", "TRDFgesch") == "1,8"
        assert blatt.quellanzeige.cget("text") == "Rohwerte aus: LIMS"
        # Kein Knopf mehr zum Umschalten - es ergibt sich von selbst.
        assert not hasattr(blatt, "knopf_quelle")
    mit_fenster(pruefen)


def test_eine_uebernommene_um_wird_zur_quelle():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._einfuegetext = UM_TEXT
        assert blatt._text_uebernehmen() is True
        assert blatt.quelle == trdfreiter.QUELLE_TEXT
        assert blatt.rohwert("26B0011", "TRDFgesch") == "1,5"
        assert blatt.gerechnet("26B0011")["TRD_TRDF"] == D("1.5")
        assert "eingefuegter UM" in blatt.quellanzeige.cget("text")
        assert "gerechnet wird mit dieser Liste" in blatt.stand.cget("text")
        # Im LIMS steht 1,8 - die Liste ist ein Vergleich, amber.
        assert blatt.rohtabelle.marke("26B0011", "TRDFgesch") == "abweichung"
        # Wo die Liste nichts sagt, gilt weiter das LIMS.
        assert blatt.rohwert("26B0011", "DichteGB") == "2,3"
        assert "1 von 16" in blatt._quellstand()
    mit_fenster(pruefen)


def test_leeren_schaltet_zurueck_auf_das_lims():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._einfuegetext = UM_TEXT
        blatt._text_uebernehmen()
        blatt._text_leeren()
        assert blatt.quelle == trdfreiter.QUELLE_LIMS
        assert blatt.rohwert("26B0011", "TRDFgesch") == "1,8"
        assert blatt.quellanzeige.cget("text") == "Rohwerte aus: LIMS"
        assert "LIMS" in blatt.stand.cget("text")
    mit_fenster(pruefen)


def test_eine_leere_einfuegung_aendert_die_quelle_nicht():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._einfuegetext = "   "
        assert blatt._text_uebernehmen() is False
        assert blatt.quelle == trdfreiter.QUELLE_LIMS
    mit_fenster(pruefen)


def test_von_hand_sticht_auch_die_eingefuegte_um():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._einfuegetext = UM_TEXT
        blatt._text_uebernehmen()
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        assert blatt.rohwert("26B0011", "TRDFgesch") == "1,2"
        assert blatt.gerechnet("26B0011")["TRD_TRDF"] == D("1.2")
    mit_fenster(pruefen)


# ------------------------------------------------------------ Das Blatt

def test_das_blatt_wird_geschrieben_und_traegt_die_bewertung():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, ordner=basis, aufschluss=(
                {"prob_id": 11, "para_id": 31, "mw": "50"},))
            trdfpruefung.oeffnen = lambda pfad: ""     # nicht wirklich oeffnen
            blatt._blatt_speichern()
            ordner = os.path.join(basis, trdfpruefung.ORDNER)
            dateien = os.listdir(ordner)
            assert dateien == ["Pruefung 2026B051 TRDF3.2.csv"]
            inhalt = open(os.path.join(ordner, dateien[0]), "rb").read()
            text = inhalt.decode("cp1252", "replace")
            assert "26B0011" in text
            assert trdfpruefung.TRDF_ZU_HOCH in text
    mit_fenster(pruefen)


def test_ohne_serie_wird_nichts_geschrieben():
    def pruefen(fenster):
        blatt = trdfreiter.TrdfSeite(fenster, lambda: ZUGANG,
                                     lambda *a, **k: None, ordner="/nirgends")
        blatt._blatt_speichern()
        assert "keine Serie" in blatt.pruefstand.cget("text")
    mit_fenster(pruefen)


# ----------------------------------------------------- Die Variante

def test_die_variante_raeumt_die_zeile_auf():
    """Wie die Eingabemaske des LIMS: was diese Variante nicht braucht,
    bekommt ein x - und zwar sichtbar in der Tabelle."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        vorher = dict(blatt.rohsatz("26B0011"))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "1")
        bewegt = 0
        for kuerzel in trdfrohpruefung.MASKIERT[1]:
            if kuerzel not in blatt.rohliste:
                continue
            assert blatt.rohwert("26B0011", kuerzel) == trdf.MARKE, kuerzel
            assert blatt.rohtabelle.wert("26B0011", kuerzel) == trdf.MARKE
            if vorher[kuerzel] != trdf.MARKE:
                bewegt += 1
                # Rot heisst hier wie ueberall: von Hand bewegt.
                assert blatt.rohtabelle.marke("26B0011",
                                              kuerzel) == "geaendert"
        assert bewegt                       # es hat sich wirklich etwas getan
        # Was Variante 1 braucht, ruehrt niemand an.
        for kuerzel in trdfrohpruefung.GEBRAUCHT[1]:
            assert blatt.rohwert("26B0011", kuerzel) == vorher[kuerzel]
    mit_fenster(pruefen)


def test_null_raeumt_die_rohwerte_der_probe_leer():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "0")
        for kuerzel in blatt.rohliste:
            if kuerzel == trdfrohpruefung.VARIANTE:
                continue
            assert blatt.rohwert("26B0011", kuerzel) == "", kuerzel
    mit_fenster(pruefen)


def test_ein_x_belegt_die_ganze_zeile():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "x")
        for kuerzel in blatt.rohliste:
            if kuerzel == trdfrohpruefung.VARIANTE:
                continue
            assert blatt.rohwert("26B0011", kuerzel) == trdf.MARKE, kuerzel
    mit_fenster(pruefen)


def test_nur_die_eine_probe_ist_betroffen():
    """Die Variante gilt je Teilprobe - die Nachbarzeile geht das nichts an."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        vorher = blatt.rohsatz("26B0005")
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "1")
        assert blatt.rohsatz("26B0005") == vorher
    mit_fenster(pruefen)


def test_ein_anderer_rohwert_raeumt_nichts_auf():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        vorher = dict(blatt.rohsatz("26B0011"))
        blatt._von_hand_geaendert("26B0011", "DichteGB", "2,9")
        nachher = blatt.rohsatz("26B0011")
        assert nachher["DichteGB"] == "2,9"
        for kuerzel, wert in vorher.items():
            if kuerzel != "DichteGB":
                assert nachher[kuerzel] == wert, kuerzel
    mit_fenster(pruefen)


def test_ein_eingefuegter_block_bringt_seine_werte_mit():
    """Er traegt die Rohwerte der neuen Variante selbst bei - sie
    duerfen nicht gleich wieder mit x ueberschrieben werden."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._block_eingefuegt([("26B0011", trdfrohpruefung.VARIANTE, "1"),
                                 ("26B0011", "DichteGB", "2,7")])
        assert blatt.rohwert("26B0011", "DichteGB") == "2,7"
    mit_fenster(pruefen)


def test_die_gerechneten_groessen_folgen_der_variante():
    """Der eigentliche Zweck: nach dem Wechsel rechnet LabControl die
    Serie so, wie das LIMS sie rechnen wuerde."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        vorher = blatt.gerechnet("26B0011")
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "1")
        assert blatt.gerechnet("26B0011") != vorher
    mit_fenster(pruefen)


def test_die_bewertung_folgt_der_handeingabe_sofort():
    """Sie ist die Antwort auf das, was eben getippt wurde - bis zum
    naechsten Neuaufbau der Tabelle zu warten hilft niemandem."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        assert blatt.rohtabelle.wert("26B0005", BEWERTUNG) == ""
        blatt._von_hand_geaendert("26B0005", "GBM63Schaufel", "9000")
        gezeigt = blatt.rohtabelle.wert("26B0005", BEWERTUNG)
        assert gezeigt and gezeigt == trdfrohpruefung.bewertungstext(
            blatt.rohbefund("26B0005"))
        assert blatt.rohtabelle.marke("26B0005", BEWERTUNG) == "abweichung"
        # Und sie geht wieder, wenn der Wert stimmt.
        blatt._von_hand_geaendert("26B0005", "GBM63Schaufel", "641,42")
        assert blatt.rohtabelle.wert("26B0005", BEWERTUNG) == ""
        assert blatt.rohtabelle.marke("26B0005", BEWERTUNG) is None
    mit_fenster(pruefen)


def test_auch_ein_eingefuegter_block_zieht_die_bewertung_nach():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        gesetzt, uebrig = blatt.rohtabelle.einfuegen(
            "26B0005", "GBM63Schaufel", [["9000"]])
        blatt._block_eingefuegt(gesetzt, uebrig)
        assert blatt.rohtabelle.wert("26B0005", BEWERTUNG)
    mit_fenster(pruefen)


# ------------------------------- Der Hinweis an der Spaltenueberschrift

def test_die_ueberschriften_sagen_was_sie_bedeuten():
    """Dieselbe Auskunft wie unter „Info“ - nur ohne dass man sie
    oeffnen muss."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        hinweis = blatt.rohtabelle._kopfhinweise["_TSM"]
        assert "Tiefenstufenm" in hinweis and "_TSM" in hinweis
        assert "cm" in hinweis                 # die Einheit
        assert "am Anhang: M" in hinweis       # das kurze Kuerzel
        # Auch die Fuehrungsspalten sagen etwas.
        assert "Probennummer" in blatt.rohtabelle._kopfhinweise["Probe"]
    mit_fenster(pruefen)


def test_jede_tabelle_hat_ihre_eigenen_hinweise():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", "DichteGB", "2,9")
        geschrieben(blatt, blatt.aenderungen())
        ergebnis = blatt.ergebnistabelle._kopfhinweise
        assert "gebucht" in ergebnis["TRD_TRDF LIMS"]
        assert "gerechnet" in ergebnis["TRD_TRDF ber."]
        # Im Pruefblatt heisst die Spalte anders als die Formel.
        pruefung = blatt.pruefungstabelle._kopfhinweise
        assert "_SKASgs" in pruefung["SKAgs63"]
        # Und im Exportbericht steht sie unter ihrem Formelkuerzel -
        # mit dem Namen der Pruefmethode und dem Kuerzel des
        # Rohwertparameters, unter dem sie am Anhang haengt.
        bericht = blatt.berichtstabelle._kopfhinweise["DichteGB"]
        assert "Grobbodendichte" in bericht and "am Anhang: D" in bericht
    mit_fenster(pruefen)


def test_die_eigene_beschreibung_steht_im_hinweis():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._spalten_speichern(trdfreiter.BLATT_ROH,
                                     {"_TSM": "Maechtigkeit in cm"})
            blatt._rohwerte_zeigen()
            assert "Maechtigkeit in cm" in \
                blatt.rohtabelle._kopfhinweise["_TSM"]
    mit_fenster(pruefen)


def test_der_hinweis_kommt_erst_beim_warten_und_geht_wieder():
    """Wo die Maus steht, laesst sich im Bauplan nicht stellen - das
    Fenster ist verborgen und hat keine Masse. Geprueft wird deshalb,
    was danach geschieht: der Hinweis erscheint zur gemerkten Spalte,
    traegt ihren Text und geht wieder."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        tabelle = blatt.rohtabelle
        tabelle._kopfspalte = "_TSM"            # so merkt es sich <Motion>
        tabelle._kopf_zeigen("_TSM", 10)
        assert tabelle._kopffenster is not None
        beschriftung = tabelle._kopffenster.winfo_children()[0]
        assert "Tiefenstufenm" in beschriftung.cget("text")
        tabelle._kopf_verlassen()
        assert tabelle._kopffenster is None and tabelle._kopfspalte is None
        # Zu einer Spalte, ueber der die Maus nicht mehr steht, kommt
        # keiner - und zu einer ohne Hinweis auch nicht.
        tabelle._kopf_zeigen("_TSM", 10)
        assert tabelle._kopffenster is None
        tabelle._kopfspalte = "gibtsnicht"
        tabelle._kopf_zeigen("gibtsnicht", 10)
        assert tabelle._kopffenster is None
    mit_fenster(pruefen)


# --------------------------------------- Die zweite Trockenrohdichte

def test_eine_serie_mit_trdf_old_zeigt_beide():
    """Die Formeln kommen aus dem LIMS - was dort steht, wird gerechnet
    und danebengestellt, ohne dass hier etwas eingetragen werden muss."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 11),
                      formeln=test_trdf.FORMELN_NEU)
        assert "TRDF_Old" in blatt.folge
        for probe, erwartet in (("26B0001", "1,423"), ("26B0011", "1,800")):
            gerechnet = blatt.gerechnet(probe)
            assert trdf.gleich(gerechnet["TRDF_Old"],
                               str(gerechnet["TRD_TRDF"])), probe
            # Und die Ergebnistabelle zeigt das Paar wie jedes andere.
            assert blatt.ergebnistabelle.wert(probe, "TRDF_Old ber.").startswith(
                erwartet), probe
            assert blatt.ergebnistabelle.hat(probe)
    mit_fenster(pruefen)


def test_ohne_trdf_old_bleibt_alles_wie_bisher():
    """Es gibt beide Serien - die neue Methode fehlt dann einfach."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        assert "TRDF_Old" not in blatt.folge
        assert "TRDF_Old ber." not in blatt.ergebnistabelle.spalten()
        assert blatt.gerechnet("26B0011")["TRD_TRDF"]
    mit_fenster(pruefen)


def test_die_geschaetzte_dichte_wirkt_sofort_auf_beide():
    """Wer TRDFgesch von Hand setzt, sieht den Unterschied der beiden
    Formeln: die neue nimmt die Schaetzung, die alte rechnet weiter."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1,), formeln=test_trdf.FORMELN_NEU)
        vorher = blatt.gerechnet("26B0001")["TRDF_Old"]
        blatt._von_hand_geaendert("26B0001", "TRDFgesch", "1,5")
        gerechnet = blatt.gerechnet("26B0001")
        assert gerechnet["TRD_TRDF"] == D("1.5")
        assert gerechnet["TRDF_Old"] == vorher      # die alte Formel bleibt
        # Und in den Export geht nur, was sich wirklich bewegt hat.
        bewegt = {eine["kuerzel"] for eine in blatt.aenderungen()}
        assert "TRD_TRDF" in bewegt and "TRDF_Old" not in bewegt, bewegt
    mit_fenster(pruefen)


def test_das_pruefblatt_sagt_wenn_geschaetzt_wurde():
    """Der Fall, um den es geht: eine Variante, die rechnen wuerde, und
    trotzdem steht eine Schaetzung da."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 11), formeln=test_trdf.FORMELN_NEU)
        assert blatt.geprueft()[0]["bewertung"] == []
        # Die Schaetzung steht im LIMS, nicht von Hand: sonst ist die
        # Zelle rot ("das habe ich bewegt") und nicht amber.
        blatt.limsroh["26B0001"]["TRDFgesch"] = "1,5"
        blatt.anhang[("26B0001", "TRDFgesch")]["mw"] = "1,5"
        blatt._rechnung_vergessen()
        blatt._zeigen()
        eintrag = blatt.geprueft()[0]
        assert eintrag["bewertung"] == [trdfpruefung.SCHAETZUNG]
        # Die Zelle, um die es geht, wird mitgefaerbt.
        assert blatt.pruefungstabelle.marke("26B0001", "TRDF") == "abweichung"
        assert blatt.pruefungstabelle.wert("26B0001", "Bewertung") == \
            trdfpruefung.SCHAETZUNG
    mit_fenster(pruefen)


def test_bei_variante_sieben_steht_nichts_im_blatt():
    """Dort ist die geschaetzte Dichte der vorgesehene Weg."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,), formeln=test_trdf.FORMELN_NEU)
        eintrag = blatt.geprueft()[0]
        assert eintrag["werte"][trdfpruefung.VARIANTE] == D(7)
        assert trdfpruefung.SCHAETZUNG not in eintrag["bewertung"]
    mit_fenster(pruefen)


def test_ohne_die_zweite_methode_meldet_das_blatt_keine_schaetzung():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 11))
        blatt._von_hand_geaendert("26B0001", "TRDFgesch", "1,5")
        for eintrag in blatt.geprueft():
            assert trdfpruefung.SCHAETZUNG not in eintrag["bewertung"]
    mit_fenster(pruefen)


def test_die_legende_kennt_die_zweite_dichte():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,), formeln=test_trdf.FORMELN_NEU)
        hinweis = blatt.ergebnistabelle._kopfhinweise["TRDF_Old ber."]
        assert "alte Formel" in hinweis and "g/cm3" in hinweis
    mit_fenster(pruefen)


# ------------------------------------------ Cges und CO3 nachtragen

def test_cges_kommt_auch_von_einer_anderen_anlage_der_probe() -> None:
    """Dieselbe PROBE_NR steht im LIMS mehrfach, und der Aufschluss
    haengt nur an einer von ihnen. Die Spalte blieb leer, obwohl das
    Labor die Zahl hat."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,), nachtrag=[
            nachtragszeile("26B0005", 31, "2,40"),
            nachtragszeile("26B0005", 33, "0,30", kuerzel="ATNULLCO3")])
        assert blatt.aufschluss["26B0005"]["Cges"] == "2,40"
        assert blatt.aufschluss["26B0005"]["CO3"] == "0,30"
        # In der Tabelle steht sie - und markiert, denn sie kommt nicht
        # von dieser Probe der Serie.
        assert blatt.ergebnistabelle.wert("26B0005", "Cges") == "2,400"
        assert blatt.ergebnistabelle.marke("26B0005", "Cges") == "ersatz"
        # Und der Hinweis nennt die PROB_ID: ohne sie ist die Zahl
        # nicht nachzusehen.
        hinweis = blatt.aufschlusshinweis("26B0005", "Cges")
        assert "9001" in hinweis
        assert "2025B012" in hinweis
    mit_fenster(pruefen)


def test_ein_gebuchter_wert_wird_nie_ersetzt() -> None:
    """Die Zahl zweier verschiedener Anlagen derselben Nummer ist nicht
    dieselbe Zahl - welche gilt, entscheidet nicht die Reihenfolge
    einer Abfrage."""
    def pruefen(fenster):
        blatt = seite(
            fenster, zeilen=(5,),
            aufschluss=[{"prob_id": 5, "para_id": 31, "kuerzel": "ATNULL",
                         "mw": "1,00"}],
            nachtrag=[nachtragszeile("26B0005", 31, "9,99")])
        assert blatt.aufschluss["26B0005"]["Cges"] == "1,00"
        assert blatt.aufschlusshinweis("26B0005", "Cges") is None
        # Nicht markiert - die zarte Toenung der Spaltengruppe bleibt.
        assert blatt.ergebnistabelle.marke("26B0005", "Cges") != "ersatz"
    mit_fenster(pruefen)


def test_von_mehreren_anlagen_gilt_die_hoechste_prob_id() -> None:
    """Eine Festlegung und keine Wahrheit - deshalb steht die PROB_ID
    im Hinweis, und wer sie nachsieht, findet auch die anderen."""
    def pruefen(fenster):
        # So kommt es aus der Abfrage: nach PROB_ID absteigend.
        blatt = seite(fenster, zeilen=(5,), nachtrag=[
            nachtragszeile("26B0005", 31, "7,00", prob_id=9100),
            nachtragszeile("26B0005", 31, "3,00", prob_id=9001)])
        assert blatt.aufschluss["26B0005"]["Cges"] == "7,00"
        assert "9100" in blatt.aufschlusshinweis("26B0005", "Cges")
    mit_fenster(pruefen)


def test_ein_nachtrag_zu_einer_fremden_probe_wird_nicht_genommen() -> None:
    """Sonst stuende der Aufschluss einer Probe, die in dieser Serie
    gar nicht vorkommt, in einer Zeile, die es gibt."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,), nachtrag=[
            nachtragszeile("26B0999", 31, "5,00")])
        assert blatt.aufschluss == {}
        assert blatt.aufschlussherkunft == {}
    mit_fenster(pruefen)


def test_der_nachgetragene_wert_geht_in_die_pruefung_ein() -> None:
    """Die Pruefungen auf dem Kohlenstoff kamen ohne ihn zu keinem
    Urteil - und "keine Bewertung" sieht aus wie "in Ordnung"."""
    def pruefen(fenster):
        ohne = seite(fenster, zeilen=(5,))
        mit = seite(fenster, zeilen=(5,), nachtrag=[
            nachtragszeile("26B0005", 31, "2,40")])
        gefragt = [satz for satz in mit.geprueft()
                   if satz["probe"] == "26B0005"][0]
        leer = [satz for satz in ohne.geprueft()
                if satz["probe"] == "26B0005"][0]
        assert trdf.gleich(gefragt["werte"].get("Cges"), "2,40")
        assert leer["werte"].get("Cges") in (None, "")
        # Und im Pruefblatt steht er markiert.
        assert mit.pruefungstabelle.wert("26B0005", "Cges")
        assert mit.pruefungstabelle.marke("26B0005", "Cges") == "ersatz"
    mit_fenster(pruefen)


def test_gefragt_wird_nur_nach_den_proben_ohne_aufschluss() -> None:
    """Steht Cges und CO3 an jeder Probe der Serie - der Regelfall -,
    entfaellt die Abfrage ganz. Sie ging vorher ueber
    UPPER(probe_nr) und damit ueber die ganze Tabelle PROBEN; das
    kostete bei jedem Serienabruf Sekunden."""
    zeilen = geholt(zeilen=(5, 11))["ergebnisse"]
    voll = []
    for prob_id in (5, 11):
        for para_id in (31, 33):
            voll.append({"prob_id": prob_id, "para_id": para_id,
                         "kuerzel": "ATNULL", "mw": "1,00"})
    assert trdfreiter._ohne_aufschluss(zeilen, voll) == []
    # Fehlt einer Probe das CO3, wird nach ihr gefragt - und nur nach
    # ihr.
    halb = [eintrag for eintrag in voll
            if not (eintrag["prob_id"] == 11 and eintrag["para_id"] == 33)]
    assert trdfreiter._ohne_aufschluss(zeilen, halb) == [11]
    # Und ohne jeden Aufschluss nach allen.
    assert trdfreiter._ohne_aufschluss(zeilen, []) == [5, 11]
    # Eine leere Zahl zaehlt nicht als gebucht.
    leer = [dict(eintrag, mw=" ") for eintrag in voll]
    assert trdfreiter._ohne_aufschluss(zeilen, leer) == [5, 11]


def test_die_probenkennungen_kommen_aus_den_zeilen() -> None:
    """Sie stehen dort schon da - eine Abfrage darueber greift ueber
    den Primaerschluessel."""
    zeilen = geholt(zeilen=(5, 11))["ergebnisse"]
    assert trdfreiter._probenkennungen(zeilen) == [5, 11]
    assert trdfreiter._probenkennungen([]) == []
    assert trdfreiter._probenkennungen([{"prob_id": None}]) == []


def test_ein_fehler_beim_nachfragen_haelt_den_abruf_nicht_auf() -> None:
    """Der Aufschluss ist eine Beigabe, die Serie ist die Arbeit."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5,))
        kaputt = object()

        def werfen(*a, **k):
            raise RuntimeError("keine Verbindung")

        echt = trdfreiter.lims_db.trdf_aufschluss_nachtrag
        trdfreiter.lims_db.trdf_aufschluss_nachtrag = werfen
        try:
            liste, grund = blatt._nachtrag_holen(kaputt, ["26B0005"])
        finally:
            trdfreiter.lims_db.trdf_aufschluss_nachtrag = echt
        assert liste == []
        assert "keine Verbindung" in grund
        # Ohne Probennummern wird gar nicht gefragt.
        assert blatt._nachtrag_holen(kaputt, []) == ([], "")
    mit_fenster(pruefen)


# ------------------------------------------------ Serie und Methode
#
# Das Pruefmodul kennt einen Weg: erst die Serie, dann "Abfragen", dann
# die Untersuchungsmethode. Angeboten wird jede Methode der Serie, deren
# Kuerzel TRDF traegt - ohne die ausgeschlossenen.

def knopftexte(widget) -> list:
    """Die Beschriftungen aller RoundedButtons unter einem Widget."""
    gebaut = []
    for kind in widget.winfo_children():
        if isinstance(kind, trdfreiter.RoundedButton):
            gebaut.append(str(getattr(kind, "_text", "")))
        gebaut.extend(knopftexte(kind))
    return gebaut


class Hintergrund:
    """Merkt sich, was im Hintergrund laufen soll - und laesst es auf
    Wunsch gleich laufen."""

    def __init__(self, sofort=False):
        self.sofort = sofort
        self.auftraege = []

    def __call__(self, arbeit, fertig, schief=None):
        self.auftraege.append((arbeit, fertig, schief))
        if self.sofort:
            fertig(arbeit())


def leere_seite(fenster, hintergrund=None, zugang=ZUGANG):
    """Eine Seite, an der noch nichts abgerufen ist."""
    return trdfreiter.TrdfSeite(fenster, lambda: zugang,
                                hintergrund or Hintergrund(),
                                ordner=tempfile.mkdtemp(
                                    prefix="trdfreiter-wahl-"))


class Datenbank:
    """Setzt die Abfragen von lims_db fuer eine Pruefung ein."""

    NAMEN = ("trdf_methoden", "trdf_serien",
             "methoden_fuer_serie", "trdf_ergebnisse", "trdf_pruefmethoden",
             "trdf_rohwertparameter", "trdf_rohwerte_anhang",
             "trdf_rohwerte_nachtrag", "trdf_wiederfindung",
             "trdf_aufschluss", "trdf_aufschluss_nachtrag")

    def __init__(self, methoden, zeilen=(5, 11)):
        vorrat = geholt(zeilen=zeilen)
        self.gefragt = []

        def methoden_fuer_serie(_zugang, serie, **_rest):
            self.gefragt.append(("methoden", serie))
            return list(methoden)

        def ergebnisse(_zugang, serie, um_id, **_rest):
            self.gefragt.append(("ergebnisse", serie, um_id))
            return vorrat["ergebnisse"]

        self.ersatz = {
            # Die Serienliste beim Aufbau der Seite.
            "trdf_methoden": lambda *a, **k: [(42, "TRDF3.2")],
            "trdf_serien": lambda *a, **k: ["2026B051", "2026B052"],
            "methoden_fuer_serie": methoden_fuer_serie,
            "trdf_ergebnisse": ergebnisse,
            "trdf_pruefmethoden": lambda *a, **k: vorrat["methoden"],
            "trdf_rohwertparameter": lambda *a, **k: vorrat["rohwerte"],
            "trdf_rohwerte_anhang": lambda *a, **k: vorrat["anhang"],
            "trdf_rohwerte_nachtrag": lambda *a, **k: [],
            "trdf_wiederfindung": lambda *a, **k: vorrat["wgh"],
            "trdf_aufschluss": lambda *a, **k: [],
            "trdf_aufschluss_nachtrag": lambda *a, **k: [],
        }

    def __enter__(self):
        self.echt = {name: getattr(trdfreiter.lims_db, name)
                     for name in self.NAMEN}
        for name, ersatz in self.ersatz.items():
            setattr(trdfreiter.lims_db, name, ersatz)
        return self

    def __exit__(self, *_rest):
        for name, echt in self.echt.items():
            setattr(trdfreiter.lims_db, name, echt)


def test_es_gibt_keinen_profil_und_keinen_probenweg() -> None:
    """Eine Einzelauswertung: keine Profilliste, kein Profilfenster,
    kein Abruf einzelner Probennummern."""
    def pruefen(fenster):
        blatt = seite(fenster)
        texte = knopftexte(blatt)
        assert "Abfragen" in texte
        assert "Profil-CSV laden" not in texte
        assert "Proben abrufen" not in texte
        assert not hasattr(blatt, "profilinfos")
        blatt._block_zeigen("26B0005", "Probe")
        assert "Profil" not in knopftexte(blatt.bloecke["26B0005"])
    mit_fenster(pruefen)


def test_nur_die_trdf_methoden_der_serie_stehen_zur_wahl() -> None:
    gefunden = trdfreiter.TrdfSeite.trdf_methoden_der_serie(
        [(1, "ATNULL"), (42, "TRDF3.2"), (41, "TRDF3.1"),
         (43, "trdfBA1.1"), (5, None)])
    # TRDF3.1 ist ausgeschlossen, ATNULL traegt kein TRDF, und gross
    # oder klein spielt keine Rolle.
    assert gefunden == [(42, "TRDF3.2"), (43, "trdfBA1.1")]


def test_ohne_abfrage_ist_keine_methode_zu_waehlen() -> None:
    def pruefen(fenster):
        blatt = leere_seite(fenster)
        assert str(blatt.feld_methode.cget("state")) == "disabled"
        assert blatt.v_methode.get() == trdfreiter.METHODE_OFFEN
        assert blatt.gewaehlte_methode() == (None, "")
    mit_fenster(pruefen)


def test_ohne_serie_wird_nicht_abgefragt() -> None:
    def pruefen(fenster):
        hinten = Hintergrund()
        blatt = leere_seite(fenster, hinten)
        vorher = len(hinten.auftraege)       # die Serienliste beim Aufbau
        blatt.v_serie.set("")
        blatt._abfragen()
        assert len(hinten.auftraege) == vorher
        assert "Serie" in blatt.stand.cget("text")
    mit_fenster(pruefen)


def test_eine_einzige_methode_wird_gleich_geholt() -> None:
    def pruefen(fenster):
        with Datenbank([(1, "ATNULL"), (42, "TRDF3.2")]) as db:
            blatt = leere_seite(fenster, Hintergrund(sofort=True))
            blatt.v_serie.set("2026B051")
            blatt._abfragen()
        assert db.gefragt[0] == ("methoden", "2026B051")
        assert ("ergebnisse", "2026B051", 42) in db.gefragt
        # Die Serienliste aus dem Fahrplan steht im Feld.
        assert list(blatt.feld_serie.cget("values")) == ["2026B051",
                                                         "2026B052"]
        assert blatt.v_methode.get() == "TRDF3.2"
        assert blatt.um_kuerzel == "TRDF3.2"
        assert len(blatt.proben) == 2
        # Die Serie steht beim naechsten Start wieder im Feld.
        assert blatt._einstellungen().get("serie") == "2026B051"
    mit_fenster(pruefen)


def test_mehrere_methoden_warten_auf_die_wahl() -> None:
    def pruefen(fenster):
        with Datenbank([(42, "TRDF3.2"), (207, "TRDF3.2"),
                        (43, "TRDFBA1.1")]) as db:
            blatt = leere_seite(fenster, Hintergrund(sofort=True))
            blatt.v_serie.set("2026B051")
            blatt._abfragen()
            # Gefragt ist nach den Methoden - geholt noch nichts.
            assert [eintrag[0] for eintrag in db.gefragt] == ["methoden"]
            assert list(blatt.feld_methode.cget("values")) == [
                "TRDF3.2 (UM 42)", "TRDF3.2 (UM 207)", "TRDFBA1.1"]
            assert str(blatt.feld_methode.cget("state")) == "readonly"
            assert "bitte eine waehlen" in blatt.stand.cget("text")
            assert blatt.proben == []
            # Die Wahl holt die Serie unter genau dieser Methode.
            blatt.v_methode.set("TRDF3.2 (UM 207)")
            blatt._methode_gewaehlt()
        assert ("ergebnisse", "2026B051", 207) in db.gefragt
        assert blatt.gewaehlte_methode() == (207, "TRDF3.2")
        assert blatt.um_id == 207
        assert len(blatt.proben) == 2
    mit_fenster(pruefen)


def test_ohne_trdf_methode_wird_nichts_geholt() -> None:
    def pruefen(fenster):
        with Datenbank([(1, "ATNULL"), (41, "TRDF3.1")]) as db:
            blatt = leere_seite(fenster, Hintergrund(sofort=True))
            blatt.v_serie.set("2026B051")
            blatt._abfragen()
        assert [eintrag[0] for eintrag in db.gefragt] == ["methoden"]
        assert "keine" in blatt.stand.cget("text")
        assert str(blatt.feld_methode.cget("state")) == "disabled"
    mit_fenster(pruefen)


def test_eine_andere_serie_raeumt_die_methodenliste() -> None:
    def pruefen(fenster):
        blatt = leere_seite(fenster)
        blatt.v_serie.set("2026B051")
        blatt._methoden_zeigen("2026B051", [(42, "TRDF3.2"),
                                            (43, "TRDFBA1.1")])
        assert blatt.abgefragte_serie == "2026B051"
        blatt.v_serie.set("2026B052")
        assert blatt.methodenwahl == []
        assert blatt.abgefragte_serie == ""
        assert str(blatt.feld_methode.cget("state")) == "disabled"
    mit_fenster(pruefen)


def test_eine_spaete_antwort_fuer_eine_alte_serie_zaehlt_nicht() -> None:
    def pruefen(fenster):
        blatt = leere_seite(fenster)
        blatt.v_serie.set("2026B052")
        blatt._methoden_zeigen("2026B051", [(42, "TRDF3.2")])
        assert blatt.methodenwahl == []
        assert blatt.v_methode.get() == trdfreiter.METHODE_OFFEN
    mit_fenster(pruefen)


def test_abrufen_fragt_bei_neuer_serie_erst_die_methoden() -> None:
    def pruefen(fenster):
        with Datenbank([(42, "TRDF3.2")]) as db:
            blatt = leere_seite(fenster, Hintergrund(sofort=True))
            blatt.v_serie.set("2026B051")
            blatt._abrufen()
        assert db.gefragt[0] == ("methoden", "2026B051")
        assert blatt.um_id == 42
    mit_fenster(pruefen)


def test_ohne_gewaehlte_methode_wird_nicht_abgerufen() -> None:
    def pruefen(fenster):
        hinten = Hintergrund()
        blatt = leere_seite(fenster, hinten)
        blatt.v_serie.set("2026B051")
        blatt._methoden_zeigen("2026B051", [(42, "TRDF3.2"),
                                            (43, "TRDFBA1.1")])
        vorher = len(hinten.auftraege)
        blatt._abrufen()
        assert len(hinten.auftraege) == vorher
        assert "Untersuchungsmethode" in blatt.stand.cget("text")
    mit_fenster(pruefen)


# ------------------------------------------- Aufgeraeumte Oberflaeche

def test_die_liste_der_probenvorbereitung_hat_ein_eigenes_fenster() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        assert not hasattr(blatt, "textfeld")       # nicht auf der Seite
        assert blatt.knopf_einfuegen._text == trdfreiter.EINFUEGEN_TEXT
        eigenes = blatt.einfuegen_oeffnen()
        assert isinstance(eigenes, tk.Toplevel)
        assert blatt.einfuegen_oeffnen() is eigenes  # nur eines
        assert "Strg+V" in eigenes.hinweis.cget("text")
        # Zu und wieder auf: die Liste bleibt liegen.
        eigenes.textfeld.insert("1.0", "etwas")
        eigenes._schliessen()
        wieder = blatt.einfuegen_oeffnen()
        assert wieder.textfeld.get("1.0", "end").strip() == "etwas"
        wieder._schliessen()
        assert blatt.stand.winfo_manager() == "pack"
    mit_fenster(pruefen)


def test_was_im_lims_fehlt_wird_aus_der_liste_vorgemerkt() -> None:
    """Rohwerte, die im LIMS noch nicht stehen, kommen aus der Liste -
    und gehen ueber \u201eExport\u201c dorthin. Ein
    gebuchter Wert wird nicht still ersetzt."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        blatt.limsroh["26B0005"]["GMSZ"] = ""            # fehlt im LIMS
        gebucht = blatt.limsroh["26B0005"]["VOLSZ"]
        blatt.eingefuegt = {"26B0005": {"GMSZ": "834,3", "VOLSZ": "999"},
                            "26B9999": {"GMSZ": "1"}}  # nicht in der Serie
        assert blatt._fehlende_vormerken() == 1
        assert blatt.vonhand == {("26B0005", "GMSZ"): "834,3"}
        assert blatt.limsroh["26B0005"]["VOLSZ"] == gebucht
        geschrieben = {(eine["probe"], eine["kuerzel"])
                       for eine in blatt.aenderungen()}
        assert ("26B0005", "GMSZ") in geschrieben
        assert ("26B0005", "VOLSZ") not in geschrieben
    mit_fenster(pruefen)


def sichtbare_texte(widget) -> list:
    """Die Texte aller gepackten oder gesetzten Labels unter einem Widget."""
    gefunden = []
    for kind in widget.winfo_children():
        if not kind.winfo_manager():
            continue
        if isinstance(kind, tk.Label):
            gefunden.append(str(kind.cget("text")))
        gefunden.extend(sichtbare_texte(kind))
    return gefunden


def test_die_erklaertexte_stehen_hinter_dem_i() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        texte = " ".join(sichtbare_texte(blatt))
        assert "Die Rechnung des LIMS nachrechnen und pruefen" in texte
        for satz in ("Das LIMS bildet aus den Rohwerten",
                     "Was aus der gewaehlten Quelle kommt",
                     "Je Groesse zwei Spalten",
                     "Die bodenphysikalischen Werte",
                     "Der letzte Schreibweg"):
            assert satz not in texte, satz
        for info, satz in ((blatt.info_kopf, "Das LIMS bildet"),
                           (blatt.info_roh, "gewaehlten Quelle"),
                           (blatt.info_ergebnis, "zwei Spalten"),
                           (blatt.info_pruefung, "bodenphysikalischen"),
                           (blatt.info_bericht, "letzte Schreibweg")):
            assert satz in info.text.replace("\n", " "), satz
            assert info.cget("text") == "i"
        # Und das i im Pruefblatt sagt, welche Spalte welcher Parameter ist.
        assert "U-Methode TRDF3.2" in blatt.info_pruefung.text
    mit_fenster(pruefen)


# ------------------------------- Berechnete Groessen ueber den Rohwerten

def test_die_berechneten_groessen_sind_zu_beginn_zugeklappt() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        assert not blatt.berechnete_offen()
        assert blatt.ergebnistabellen == [blatt.ergebnistabelle]
        assert len(blatt.rohteilung.panes()) == 1
        assert blatt.knopf_berechnete._text == trdfreiter.BERECHNETE_EIN_TEXT
    mit_fenster(pruefen)


def test_aufgeklappt_stehen_sie_ueber_den_rohwerten() -> None:
    def pruefen(fenster):
        blatt = trdfreiter.TrdfSeite(fenster, lambda: ZUGANG,
                                     lambda *a, **k: None,
                                     ordner=tempfile.mkdtemp(prefix="oben-"))
        blatt.v_serie.set("2026B051")
        blatt._uebernehmen(geholt())
        blatt._berechnete_umschalten()
        assert blatt.berechnete_offen()
        # Oben die berechneten, unten die Rohwerte - zwei Tabellen.
        assert len(blatt.rohteilung.panes()) == 2
        assert str(blatt.rohteilung.panes()[0]) == str(blatt.berechnet_rahmen)
        assert blatt.berechnet_oben is not blatt.rohtabelle
        assert blatt.berechnet_oben.zeilen() == \
            blatt.ergebnistabelle.zeilen()
        assert blatt.berechnet_oben.spalten() == \
            blatt.ergebnistabelle.spalten()
        # Der Zustand bleibt fuer den naechsten Start.
        assert blatt._einstellungen().get("trdf_berechnete") == \
            trdfreiter.BERECHNETE_AN
        blatt._berechnete_umschalten()
        assert not blatt.berechnete_offen()
        assert len(blatt.rohteilung.panes()) == 1
        assert blatt._einstellungen().get("trdf_berechnete") == \
            trdfreiter.BERECHNETE_AUS
    mit_fenster(pruefen)


def test_eine_aenderung_markiert_dieselbe_probe_oben() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        blatt._berechnete_umschalten(merken=False)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        # Unten die Zelle und die Probe, oben dieselbe Probe.
        assert blatt.rohtabelle.marke("26B0011", "TRDFgesch") == "geaendert"
        assert blatt.rohtabelle.marke("26B0011", "Probe") == "geaendert"
        for tabelle in (blatt.berechnet_oben, blatt.ergebnistabelle):
            assert tabelle.marke("26B0011", "Probe") == "geaendert"
            assert tabelle.marke("26B0005", "Probe") != "geaendert"
            # Und was sich bewegt hat, steht rot.
            assert tabelle.marke("26B0011", "TRD_TRDF ber.") == "geaendert"
            assert "26B0011" in tabelle.gewaehlt()
        assert blatt.pruefungstabelle.marke("26B0011", "Probe-Nr.") == \
            "geaendert"
        assert blatt.arbeitszeile == "26B0011"
    mit_fenster(pruefen)


def test_die_arbeitszeile_wird_ueberall_unterlegt() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        blatt._berechnete_umschalten(merken=False)
        blatt._arbeitszeile_setzen("26B0033")
        for tabelle in (blatt.rohtabelle, blatt.berechnet_oben,
                        blatt.ergebnistabelle, blatt.pruefungstabelle):
            assert tabelle.gewaehlt() == ["26B0033"]
        # Ein offener Block bleibt daneben unterlegt.
        blatt._block_zeigen("26B0005", "Probe")
        assert set(blatt.berechnet_oben.gewaehlt()) == {"26B0005", "26B0033"}
    mit_fenster(pruefen)


def test_eine_neue_serie_vergisst_die_arbeitszeile() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        blatt._arbeitszeile_setzen("26B0033")
        blatt._uebernehmen(geholt())
        assert blatt.arbeitszeile is None
    mit_fenster(pruefen)


def test_sehen_rollt_ohne_die_auswahl_zu_aendern() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        tabelle = blatt.ergebnistabelle
        tabelle.auswahl(["26B0001"])
        assert tabelle.sehen("26B0033") is True
        assert tabelle.gewaehlt() == ["26B0001"]
        assert tabelle.sehen("gibt es nicht") is False
    mit_fenster(pruefen)


def test_die_tabellen_haben_die_groessere_schrift() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        for tabelle in (blatt.rohtabelle, blatt.ergebnistabelle,
                        blatt.berechnet_oben, blatt.pruefungstabelle,
                        blatt.berichtstabelle):
            assert tabelle.schrift[1] == trdfreiter.SCHRIFT
            assert tabelle.zeilenluft == trdfreiter.ZEILENLUFT
    mit_fenster(pruefen)


# ------------------------------------------------ Wie in Excel: Strg+D/E

def offen_tun(tabelle, zeile, spalte):
    """Eine Zelle so offen stellen, als haette man sie angeklickt.

    Ohne sichtbares Fenster findet das Feld seine Zelle nicht (siehe
    `eingetippt`); geprueft wird hier, was die Tasten tun.
    """
    tabelle._offen = (str(zeile), str(spalte))
    tabelle._vorher = tabelle.wert(zeile, spalte)
    tabelle._aktiv = tabelle.feld
    tabelle.feld.delete(0, "end")
    tabelle.feld.insert(0, tabelle._vorher)


def test_strg_d_uebernimmt_den_wert_darueber() -> None:
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        tabelle = blatt.rohtabelle
        oben = tabelle.wert("26B0005", "GMSZ").strip()
        offen_tun(tabelle, "26B0011", "GMSZ")
        assert tabelle.von_oben() == "break"
        assert tabelle.wert("26B0011", "GMSZ").strip() == oben
        # Die Seite hat es mitbekommen - als Handaenderung, rot.
        assert blatt.rohwert("26B0011", "GMSZ") == oben
        assert tabelle.marke("26B0011", "GMSZ") == "geaendert"
        assert tabelle.feld.get() == oben          # die Zelle bleibt offen
    mit_fenster(pruefen)


def test_strg_d_in_der_ersten_zeile_tut_nichts() -> None:
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        offen_tun(blatt.rohtabelle, "26B0005", "GMSZ")
        blatt.rohtabelle.von_oben()
        assert blatt.vonhand == {}
    mit_fenster(pruefen)


def leer_machen(blatt, probe, anzahl=2) -> list:
    """Ein paar Rohwerte der Probe, die im LIMS gar nicht stehen."""
    gemacht = []
    for kuerzel in blatt.rohliste:
        if kuerzel == "_TRDV" or len(gemacht) == anzahl:
            continue
        blatt.limsroh.setdefault(probe, {})[kuerzel] = ""
        gemacht.append(kuerzel)
    blatt._rechnung_vergessen()
    blatt._zeigen()
    return gemacht


def test_strg_e_fuellt_nur_die_leeren_zellen_der_probe() -> None:
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        leer = leer_machen(blatt, "26B0011")
        leer_machen(blatt, "26B0005")
        voll = [k for k in blatt.rohliste if k not in leer]
        offen_tun(blatt.rohtabelle, "26B0011", voll[0])
        blatt.rohtabelle._fuellen()
        for kuerzel in leer:
            assert blatt.rohwert("26B0011", kuerzel) == trdf.MARKE, kuerzel
            assert blatt.rohtabelle.marke("26B0011", kuerzel) == "geaendert"
        for kuerzel in voll:
            assert ("26B0011", kuerzel) not in blatt.vonhand
        # Die andere Probe bleibt, wie sie war.
        assert not any(probe == "26B0005" for probe, _k in blatt.vonhand)
        assert blatt.leere_fuellen("26B0011") == []
    mit_fenster(pruefen)


def test_strg_shift_e_fuellt_die_leeren_zellen_der_spalte() -> None:
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        kuerzel = leer_machen(blatt, "26B0005", 1)[0]
        leer_machen(blatt, "26B0011", 1)
        offen_tun(blatt.rohtabelle, "26B0005", kuerzel)
        blatt.rohtabelle._fuellen(spaltenweise=True)
        assert blatt.vonhand == {("26B0005", kuerzel): trdf.MARKE,
                                 ("26B0011", kuerzel): trdf.MARKE}
    mit_fenster(pruefen)


def test_strg_shift_d_kopiert_bis_ans_ende() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)                     # 1, 5, 11, 33
        tabelle = blatt.rohtabelle
        offen_tun(tabelle, "26B0005", "_TSM")
        tabelle.feld.delete(0, "end")
        tabelle.feld.insert(0, "40")
        gesetzt = tabelle.nach_unten("alle")
        assert [z for z, _s, _w in gesetzt] == ["26B0011", "26B0033"]
        for probe in ("26B0005", "26B0011", "26B0033"):
            assert blatt.rohwert(probe, "_TSM") == "40"
        assert ("26B0001", "_TSM") not in blatt.vonhand   # darueber nicht
    mit_fenster(pruefen)


def test_strg_l_kopiert_nur_in_leere_zellen() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        blatt.limsroh["26B0033"]["_TSM"] = ""
        vorher = blatt.rohwert("26B0011", "_TSM")
        offen_tun(blatt.rohtabelle, "26B0005", "_TSM")
        gesetzt = blatt.rohtabelle.nach_unten("leere")
        assert gesetzt == [("26B0033", "_TSM", blatt.rohwert("26B0005",
                                                             "_TSM"))]
        assert blatt.rohwert("26B0011", "_TSM") == vorher
    mit_fenster(pruefen)


def test_strg_i_zaehlt_nach_unten_hoch() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        tabelle = blatt.rohtabelle
        offen_tun(tabelle, "26B0001", "GMSZ")
        tabelle.feld.delete(0, "end")
        tabelle.feld.insert(0, "10,5")
        tabelle.nach_unten("plus")
        assert [blatt.rohwert(p, "GMSZ") for p in
                ("26B0001", "26B0005", "26B0011", "26B0033")] == \
            ["10,5", "11,5", "12,5", "13,5"]
    mit_fenster(pruefen)


def test_hochzaehlen_braucht_eine_zahl() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        offen_tun(blatt.rohtabelle, "26B0001", "GMSZ")
        blatt.rohtabelle.feld.delete(0, "end")
        blatt.rohtabelle.feld.insert(0, "x")
        blatt.rohtabelle._uebernehmen()
        vorher = dict(blatt.vonhand)
        assert blatt.rohtabelle.nach_unten("plus") == []
        assert blatt.vonhand == vorher
    mit_fenster(pruefen)


def test_eine_variante_nach_unten_setzt_ihre_x() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        offen_tun(blatt.rohtabelle, "26B0005", "_TRDV")
        blatt.rohtabelle.feld.delete(0, "end")
        blatt.rohtabelle.feld.insert(0, "0")
        blatt.rohtabelle.nach_unten("alle")
        # 0 raeumt die Zeile - auch in den Zeilen darunter.
        for probe in ("26B0011", "26B0033"):
            andere = [k for k in blatt.rohliste if k != "_TRDV"]
            assert all(blatt.vonhand.get((probe, k)) == "" for k in andere)
    mit_fenster(pruefen)


def test_die_tasten_stehen_im_dezenten_i() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        for taste in ("Strg+D", "Strg+Shift+D", "Strg+L", "Strg+I",
                      "Strg+E", "Strg+Shift+E", "Strg+V"):
            assert taste in blatt.info_tasten.text
        # Nicht im Erklaertext - der sagt, was die Tabelle ist.
        assert "Strg+D" not in blatt.info_roh.text
        assert blatt.info_tasten.cget("bg") != blatt.info_roh.cget("bg")
    mit_fenster(pruefen)


def test_die_berechneten_groessen_gehen_als_csv() -> None:
    def pruefen(fenster):
        ordner = tempfile.mkdtemp(prefix="ergebnisblatt-")
        blatt = seite(fenster, ordner=ordner)
        kopf, zeilen = blatt.ergebnisblatt()
        assert kopf[:2] == ["Zeile", "Probe"]
        assert len(zeilen) == 4
        pfad = blatt._ergebnisblatt_speichern()
        assert pfad.startswith(ordner) and os.path.isfile(pfad)
        with open(pfad, encoding="utf-8-sig") as datei:
            inhalt = datei.read()
        assert "Berechnete Groessen - Serie 2026B051" in inhalt
        assert "26B0011" in inhalt
        assert "TRD_TRDF ber." in inhalt
    mit_fenster(pruefen)


def test_spaltenkoepfe_und_beschreibungen_ueberstehen_den_neustart() -> None:
    """Was unter \u201eInfo\u201c gespeichert wird, steht beim naechsten
    Start wieder da - aus der Datei neben dem Programm."""
    import config

    def pruefen(fenster):
        ordner = tempfile.mkdtemp(prefix="neustart-")
        blatt = trdfreiter.TrdfSeite(fenster, lambda: ZUGANG,
                                     lambda *a, **k: None, ordner=ordner)
        fehler = blatt._spalten_speichern(
            trdfreiter.BLATT_ROH, {"GMSZ": "Gesamtmasse feucht"},
            {"reihenfolge": ["Zeile", "Probe", "_TRDV", "GMSZ"],
             "fest": ["Zeile", "Probe"], "versteckt": ["FBLFL"],
             "kopfspalte": "Name", "kopfspalten": {"GMSZ": "Einheit"}})
        assert fehler == ""
        blatt._berechnete_umschalten()
        neu = config.Config(runtime_dir=ordner)          # der Neustart
        assert neu.get("trdf_beschreibung") == {"GMSZ": "Gesamtmasse feucht"}
        assert neu.get("trdf_reihenfolge")[trdfreiter.BLATT_ROH][:3] == \
            ["Zeile", "Probe", "_TRDV"]
        assert neu.get("trdf_fest")[trdfreiter.BLATT_ROH] == ["Zeile",
                                                              "Probe"]
        assert neu.get("trdf_versteckt")[trdfreiter.BLATT_ROH] == ["FBLFL"]
        assert neu.get("trdf_kopfspalte") == "Name"
        assert neu.get("trdf_kopfspalten") == {"GMSZ": "Einheit"}
        assert neu.get("trdf_berechnete") == trdfreiter.BERECHNETE_AN
        # Und die neue Seite nimmt es.
        wieder = trdfreiter.TrdfSeite(fenster, lambda: ZUGANG,
                                      lambda *a, **k: None, ordner=ordner,
                                      konfig=neu)
        assert wieder.berechnete_offen()
        assert wieder.beschreibungen() == {"GMSZ": "Gesamtmasse feucht"}
        assert wieder.kopfspalte() == "Name"
    mit_fenster(pruefen)


def test_ein_geaenderter_wert_steht_rot_und_nicht_grau() -> None:
    """Der neue Text erbte frueher die Tags der Trennstriche daneben -
    und stand blassgrau statt rot da."""
    def pruefen(fenster):
        blatt = seite(fenster)
        blatt._von_hand_geaendert("26B0005", "GMSZ", "850")
        tabelle = blatt.rohtabelle
        nummer = tabelle._reihen.index("26B0005") + 1
        feld = tabelle._wo("GMSZ")
        von = tabelle._anfang["GMSZ"]
        for stelle in range(von, von + tabelle._breiten["GMSZ"]):
            tags = feld.tag_names(f"{nummer}.{stelle}")
            assert "trenner" not in tags, (stelle, tags)
        assert "geaendert" in feld.tag_names(
            f"{nummer}.{von + tabelle._breiten['GMSZ'] - 1}")
    mit_fenster(pruefen)


# ------------------------------------- Verdeckte Reiter: erst beim Oeffnen

def aufschiebende_seite(fenster):
    """Eine Seite wie im Betrieb: verdeckte Reiter warten."""
    blatt = seite(fenster)
    blatt.sofort_zeichnen = False
    blatt.reiter.select(0)
    return blatt


def test_eine_eingabe_zeichnet_verdeckte_reiter_nicht_sofort() -> None:
    def pruefen(fenster):
        blatt = aufschiebende_seite(fenster)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        # Ergebnisse und Pruefblatt liegen verdeckt - sie warten.
        assert blatt.ergebnistabelle in blatt._veraltet
        assert blatt.pruefungstabelle in blatt._veraltet
        assert blatt.ergebnistabelle.marke("26B0011", "TRD_TRDF ber.") \
            != "geaendert"
        # Die Statuszeile ist trotzdem auf dem neuen Stand.
        assert "Werten stimmen" in blatt.stand.cget("text")
    mit_fenster(pruefen)


def test_der_reiter_zieht_beim_oeffnen_nach() -> None:
    def pruefen(fenster):
        blatt = aufschiebende_seite(fenster)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        blatt.reiter.select(1)
        blatt._nachziehen()            # was <<NotebookTabChanged>> ausloest
        assert blatt.ergebnistabelle not in blatt._veraltet
        assert blatt.ergebnistabelle.marke("26B0011", "TRD_TRDF ber.") \
            == "geaendert"
        assert blatt.pruefungstabelle in blatt._veraltet    # noch verdeckt
        blatt.reiter.select(2)
        blatt._nachziehen()
        assert blatt.pruefungstabelle.marke("26B0011", "Probe-Nr.") \
            == "geaendert"
    mit_fenster(pruefen)


def test_aufgeklappte_berechnete_groessen_gehen_sofort_mit() -> None:
    def pruefen(fenster):
        blatt = aufschiebende_seite(fenster)
        blatt._berechnete_umschalten(merken=False)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        assert blatt.berechnet_oben not in blatt._veraltet
        assert blatt.berechnet_oben.marke("26B0011", "TRD_TRDF ber.") \
            == "geaendert"
    mit_fenster(pruefen)


def test_das_ergebnisblatt_liest_den_neuen_stand() -> None:
    """Auch wenn der Reiter verdeckt war: das Blatt zeigt, was gilt."""
    def pruefen(fenster):
        blatt = aufschiebende_seite(fenster)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        kopf, zeilen = blatt.ergebnisblatt()
        zeile = next(z for z in zeilen if "26B0011" in z)
        assert "1,200" in zeile[kopf.index("TRD_TRDF ber.")]
    mit_fenster(pruefen)


def test_eine_eingabe_rechnet_nur_ihre_probe_neu() -> None:
    def pruefen(fenster):
        blatt = seite(fenster)
        for _lnr, probe in blatt.proben:
            blatt.gerechnet(probe)
        gemerkt = dict(blatt._mit_hand)
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
        for probe in ("26B0001", "26B0005", "26B0033"):
            assert blatt._mit_hand[probe] is gemerkt[probe], probe
        assert blatt._mit_hand["26B0011"] is not gemerkt["26B0011"]
        # Ohne Handeingabe ist "ohne Hand" dieselbe Rechnung.
        assert blatt.gerechnet_ohne_hand("26B0005") is \
            blatt.gerechnet("26B0005")
    mit_fenster(pruefen)


# ------------------------------------- Eine Anmeldung je Aktion

class ZaehlZugang:
    """Ein Zugang, der Verbindungen und Abfragen zaehlt - ohne Datenbank.

    Geantwortet wird mit leeren Zeilen, nur die Methodenliste einer
    Serie bringt eine TRDF-Methode mit. Gerechnet wird gegen die echten
    Abfragen aus lims_db.
    """

    benutzer, alias, protokoll, modus = "pruefer", "LIMS", None, "Thin Mode"

    def __init__(self):
        self.verbindungen = 0
        self.abfragen = 0

    def verbinden(self):
        self.verbindungen += 1
        zugang = self

        class Cursor:
            rowcount = 1

            def __enter__(self):
                return self

            def __exit__(self, *rest):
                return None

            def execute(self, sql, bindungen=None, **rest):
                zugang.abfragen += 1
                self.sql = " ".join(sql.lower().split())

            def fetchall(self):
                if "from teilproben t" in self.sql and "distinct" in self.sql:
                    return [(42, "TRDF3.2")]
                return []

        class Verbindung:
            def cursor(self):
                return Cursor()

            def __enter__(self):
                return self

            def __exit__(self, *rest):
                return None

            def close(self):
                return None

        return Verbindung()


def test_eine_serie_laden_heisst_eine_anmeldung() -> None:
    """Jede Abfrage mit eigener Verbindung hiess: jede mit eigener
    Anmeldung. Eine Serie zu laden waren sechs davon."""
    def pruefen(fenster):
        zugang = ZaehlZugang()
        blatt = trdfreiter.TrdfSeite(
            fenster, lambda: zugang,
            lambda arbeit, fertig, schief=None: fertig(arbeit()),
            ordner=tempfile.mkdtemp(prefix="anmeldung-"))
        zugang.verbindungen = zugang.abfragen = 0
        blatt.v_serie.set("2026B051")
        blatt.abgefragte_serie = "2026B051"
        blatt.methodenwahl = trdfreiter.methodentexte([(42, "TRDF3.2")])
        blatt.v_methode.set("TRDF3.2")
        blatt._abrufen()
        assert zugang.abfragen >= 6
        assert zugang.verbindungen == 1
        # Und die Methoden einer Serie: eine Anmeldung fuer alle Wege.
        zugang.verbindungen = 0
        blatt._abfragen()
        assert zugang.verbindungen <= 2          # Methoden + Laden
    mit_fenster(pruefen)


def test_ohne_echten_zugang_verbindet_jede_abfrage_selbst() -> None:
    """In den Pruefungen ist der Zugang ein Platzhalter - dann bleibt
    alles beim Alten."""
    with trdfreiter.lims_db.sitzung(object()) as verbindung:
        assert verbindung is None


# --------------------------------------------------- Die Grossansicht

def eingetippt(tabelle, zeile, spalte, wert):
    """Einen Wert eintragen, ohne das Eingabefeld zu brauchen.

    Das wandernde Feld will wissen, wo seine Zelle auf dem Schirm liegt
    - in einem verborgenen oder gerade erst geoeffneten Fenster weiss
    das niemand, und unter Windows faellt es damit anders aus als unter
    X11. Geprueft wird hier, was danach geschieht, und das ist beide
    Male dasselbe: die Zelle bekommt ihren Wert, und die Seite erfaehrt
    davon. Das Feld selbst hat seine eigenen Pruefungen.
    """
    tabelle._setzen(str(zeile), str(spalte), wert)
    tabelle.bei_aenderung(str(zeile), str(spalte), wert)


def test_die_grossansicht_zeigt_dieselbe_tabelle():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        gross = blatt._gross_zeigen()
        try:
            assert gross.tabelle.zeilen() == blatt.rohtabelle.zeilen()
            assert gross.tabelle.spalten() == blatt.rohtabelle.spalten()
            assert gross.tabelle.wert("26B0011", "DichteGB") == \
                blatt.rohtabelle.wert("26B0011", "DichteGB")
            # Grosse Schrift, hohe Zeile - darum geht es.
            assert gross.tabelle.schrift[1] > blatt.rohtabelle.schrift[1]
            assert gross.tabelle.zeilenluft > 0
        finally:
            gross._schliessen()
    mit_fenster(pruefen)


def test_was_gross_getippt_wird_steht_sofort_im_reiter():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        gross = blatt._gross_zeigen()
        try:
            eingetippt(gross.tabelle, "26B0011", "DichteGB", "2,7")
            assert blatt.rohwert("26B0011", "DichteGB") == "2,7"
            assert blatt.rohtabelle.wert("26B0011", "DichteGB") == "2,7"
            assert blatt.rohtabelle.marke("26B0011",
                                          "DichteGB") == "geaendert"
            # Und die Rechnung ist mitgegangen.
            assert "DichteGB" in {eine["kuerzel"]
                                  for eine in blatt.aenderungen()}
        finally:
            gross._schliessen()
    mit_fenster(pruefen)


def test_was_im_reiter_geschieht_steht_auch_gross_da():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        gross = blatt._gross_zeigen()
        try:
            blatt._von_hand_geaendert("26B0011", "DichteGB", "2,8")
            assert gross.tabelle.wert("26B0011", "DichteGB") == "2,8"
            assert gross.tabelle.marke("26B0011", "DichteGB") == "geaendert"
            # Auch das Aufraeumen der Variante.
            blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE,
                                      "1")
            assert gross.tabelle.wert("26B0011", "MMini") == trdf.MARKE
        finally:
            gross._schliessen()
    mit_fenster(pruefen)


def test_ein_eingefuegter_block_kommt_in_beiden_an():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        gross = blatt._gross_zeigen()
        try:
            # Denselben Weg wie die Zwischenablage: eintragen und
            # der Seite Bescheid geben.
            gesetzt, uebrig = gross.tabelle.einfuegen(
                "26B0005", "DichteGB", [["2,71"], ["2,72"]])
            gross.tabelle.bei_block(gesetzt, uebrig)
            for tabelle in (blatt.rohtabelle, gross.tabelle):
                assert tabelle.wert("26B0005", "DichteGB") == "2,71"
                assert tabelle.wert("26B0011", "DichteGB") == "2,72"
                assert tabelle.marke("26B0011", "DichteGB") == "geaendert"
        finally:
            gross._schliessen()
    mit_fenster(pruefen)


def test_der_block_liegt_ueber_der_grossansicht():
    """Sonst verschwindet er hinter ihr, und das Bild ist genau dann da,
    wenn man die Zahlen dazu eintippt."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        gross = blatt._gross_zeigen()
        try:
            gross._angeklickt("26B0011", "Probe")
            block = blatt.bloecke["26B0011"]
            assert block.master is gross
            # Und die Pfeiltasten blaettern auch von dort.
            assert "<Key-Down>" in set(block.bind())
        finally:
            gross._schliessen()
    mit_fenster(pruefen)


def test_nach_dem_schliessen_bleibt_nur_der_reiter():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        gross = blatt._gross_zeigen()
        eingetippt(gross.tabelle, "26B0011", "DichteGB", "2,9")
        gross._schliessen()
        assert blatt.rohtabellen == [blatt.rohtabelle]
        assert not gross.winfo_exists()
        # Die Aenderung ist geblieben - sie stand ja die ganze Zeit hier.
        assert blatt.rohwert("26B0011", "DichteGB") == "2,9"
        blatt._von_hand_geaendert("26B0011", "GMSZ", "600")   # kein Fehler
    mit_fenster(pruefen)


def test_zweimal_gross_bleibt_ein_fenster():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        erste = blatt._gross_zeigen()
        try:
            assert blatt._gross_zeigen() is erste
            assert len(blatt.rohtabellen) == 2
        finally:
            erste._schliessen()
    mit_fenster(pruefen)


def test_ohne_serie_gibt_es_nichts_gross_zu_zeigen():
    def pruefen(fenster):
        blatt = trdfreiter.TrdfSeite(fenster, lambda: ZUGANG,
                                     lambda *a, **k: None)
        assert blatt._gross_zeigen() is None
        assert "keine Serie" in blatt.rohstand.cget("text")
    mit_fenster(pruefen)


# ------------------------- Wo nichts steht, ist auch kein Befund

def test_bei_variante_x_fehlt_kein_rohwert():
    """Ein x heisst "diese Teilprobe bekommt keine Variante" - dann
    fehlt auch keiner der Rohwerte, die eine braeuchte."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "x")
        assert blatt.rohbefund("26B0011") == []
        # Und im Pruefblatt steht es auch nicht.
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "x")
        eintrag = blatt.geprueft()[0]
        assert trdfreiter.ROHWERTE_UNVOLLSTAENDIG not in eintrag["bewertung"]
    mit_fenster(pruefen)


def test_bei_variante_x_schweigt_auch_der_anhang():
    """Dass am Anhang noch eine Zahl steht, ist gerade der Zustand, den
    das x beschreibt."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        # Das x steht im LIMS selbst, nicht von Hand - sonst bliebe der
        # Vergleich ohnehin aussen vor.
        blatt.limsroh["26B0011"][trdfrohpruefung.VARIANTE] = trdf.MARKE
        blatt.anhang[("26B0011", trdfrohpruefung.VARIANTE)]["mw"] = "7"
        befund = blatt.rohbefund("26B0011")
        assert not any(trdfrohpruefung.VARIANTE in satz for satz in befund)
        # Ein anderer Rohwert, der auseinandergeht, faellt weiter auf.
        blatt.anhang[("26B0011", "DichteGB")]["mw"] = "2,9"
        assert blatt.rohbefund("26B0011") == [
            trdfrohpruefung.ANHANG_ANDERS.format("DichteGB")]
    mit_fenster(pruefen)


def test_eine_leere_ergebniszelle_ist_kein_widerspruch():
    """Hat das LIMS die Groesse noch nicht gerechnet, steht dort nichts -
    das ist keine Abweichung, sondern eine Serie, die ihre Groessen noch
    vor sich hat."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        for kuerzel in list(blatt.gebucht["26B0011"]):
            blatt.gebucht["26B0011"][kuerzel] = ""
        blatt._ergebnisse_zeigen()
        assert blatt.ergebnistabelle.wert("26B0011", BEWERTUNG) == ""
    mit_fenster(pruefen)


def test_ein_x_oder_eine_null_im_lims_wird_geprueft():
    """Beides steht wirklich da und ist eine Aussage."""
    def pruefen(fenster):
        for gebucht in (trdf.MARKE, "0"):
            blatt = seite(fenster, zeilen=(11,))
            for kuerzel in list(blatt.gebucht["26B0011"]):
                blatt.gebucht["26B0011"][kuerzel] = ""
            blatt.gebucht["26B0011"]["TRD_TRDF"] = gebucht
            blatt._ergebnisse_zeigen()
            bewertung = blatt.ergebnistabelle.wert("26B0011", BEWERTUNG)
            assert "TRD_TRDF" in bewertung, (gebucht, bewertung)
    mit_fenster(pruefen)


# ------------------------------ Was die Variante in das LIMS schreibt

def test_die_variante_schreibt_ihre_x_auch_in_das_lims():
    """Was die Maske des LIMS mit x belegt, soll dort auch stehen -
    an beiden Stellen und bei den daraus gerechneten Groessen."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "1")
        geaendert = blatt.aenderungen()
        nach_kuerzel = {eine["kuerzel"]: eine for eine in geaendert}
        # Ein Rohwert, den Variante 1 nicht braucht.
        assert nach_kuerzel["DichteGB"]["neu"] == trdf.MARKE
        assert nach_kuerzel["DichteGB"]["anhang"] is not None
        # Und eine Groesse, die daraus gerechnet wird.
        assert nach_kuerzel["FBVb"]["neu"] == trdf.MARKE
        assert nach_kuerzel["FBVb"]["art"] == trdfexport.BERECHNET
        # So gehen sie in die Anweisung.
        saetze = {satz["prob_id"]: satz for satz in
                  trdfexport.saetze([nach_kuerzel["DichteGB"]])}
        assert list(saetze.values())[0]["wert"] == trdf.MARKE
        assert trdfexport.anhangsaetze(
            [nach_kuerzel["DichteGB"]])[0]["wert"] == trdf.MARKE
    mit_fenster(pruefen)


def test_null_schreibt_leere_werte_in_das_lims():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "0")
        geaendert = blatt.aenderungen()
        geleert = trdfexport.geleert(geaendert)
        assert geleert                       # es wird wirklich geleert
        for eine in geleert:
            assert eine["art"] == trdfexport.ROHWERT
            assert trdfexport.satz(eine)["wert"] == ""
        # Die gerechneten Groessen folgen mit einem x - so rechnet das
        # LIMS aus leeren Rohwerten auch.
        berechnet = [eine for eine in geaendert
                     if eine["art"] == trdfexport.BERECHNET]
        assert berechnet and all(eine["neu"] == trdf.MARKE
                                 for eine in berechnet)
    mit_fenster(pruefen)


def test_ein_x_ueber_ein_x_kommt_nicht_in_die_liste():
    """Es aendert nichts, und jede geschriebene Zeile bekaeme ein
    Korrekturkennzeichen."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        vorher = dict(blatt.rohsatz("26B0011"))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "1")
        bewegt = {eine["kuerzel"] for eine in blatt.aenderungen()}
        for kuerzel, wert in vorher.items():
            if wert == trdf.MARKE and kuerzel in trdfrohpruefung.MASKIERT[1]:
                assert kuerzel not in bewegt, kuerzel
    mit_fenster(pruefen)


def test_die_vorschau_sagt_was_kein_messwert_ist():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "0")
        vorschau = trdfreiter.Exportvorschau(
            fenster, blatt.aenderungen(), "2026B051", lambda: None)
        saetze = [kind.cget("text") for kind in vorschau.winfo_children()
                  if isinstance(kind, tk.Label)]
        assert any("geleert" in satz for satz in saetze), saetze
        assert any("Eingabemaske" in satz for satz in saetze)
    mit_fenster(pruefen)


def test_nach_dem_schreiben_steht_das_x_auch_im_fenster():
    def pruefen(fenster):
        ohne_fenster()
        blatt = seite(fenster, zeilen=(11,), ordner=tempfile.mkdtemp())
        blatt._von_hand_geaendert("26B0011", trdfrohpruefung.VARIANTE, "1")
        geaendert = blatt.aenderungen()
        geschrieben(blatt, geaendert)
        assert blatt.limsroh["26B0011"]["DichteGB"] == trdf.MARKE
        assert blatt.anhang[("26B0011", "DichteGB")]["mw"] == trdf.MARKE
        assert blatt.gebucht["26B0011"]["FBVb"] == trdf.MARKE
    mit_fenster(pruefen)


# ------------------------------------------- Den Anhang angleichen

def test_auseinandergelaufene_rohwerte_werden_gefunden():
    """Die Ergebniszeile zeigt der Mensch sich an, aus dem Anhang
    rechnet das LIMS - gehen sie auseinander, sieht es niemand."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        assert blatt.auseinander() == []
        blatt.anhang[("26B0011", "DichteGB")]["mw"] = "2,9"
        gefunden = blatt.auseinander()
        assert len(gefunden) == 1
        eine = gefunden[0]
        assert eine["kuerzel"] == "DichteGB"
        assert eine["art"] == trdfexport.ROHWERT
        assert eine["alt"] == "2,9"                  # der Stand am Anhang
        assert eine["neu"] == D("2.3")               # die Ergebniszeile
        assert eine["anhang"] is not None
    mit_fenster(pruefen)


def test_angeglichen_wird_nur_der_anhang():
    """Die Ergebniszeile ist hier die Vorlage und wird nicht angefasst."""
    def pruefen(fenster):
        ohne_fenster()
        gemerkt = {}

        def exportieren(zugang, saetze, hinweise=None, anhang=None,
                        anhang_hinweise=None, zurueck=False):
            gemerkt["saetze"] = list(saetze)
            gemerkt["anhang"] = list(anhang or [])
            return {"geschrieben": 0, "ohne_zeile": [], "versucht": 0,
                    "anhang_geschrieben": len(anhang or []),
                    "anhang_ohne_zeile": [], "nicht_uebernommen": [],
                    "anhang_nicht_uebernommen": []}

        echt = trdfreiter.lims_db.trdf_exportieren
        trdfreiter.lims_db.trdf_exportieren = exportieren
        try:
            with tempfile.TemporaryDirectory() as basis:
                blatt = seite(fenster, zeilen=(11,), ordner=basis)
                blatt._im_hintergrund = (
                    lambda arbeit, fertig, schief: fertig(arbeit()))
                blatt._abrufen = lambda: None
                blatt.anhang[("26B0011", "DichteGB")]["mw"] = "2,9"
                blatt._anhang_schreiben(blatt.auseinander())
                # Und eine Sicherung liegt daneben.
                ordner = os.path.join(basis, trdfexport.ORDNER)
                assert os.listdir(ordner)
        finally:
            trdfreiter.lims_db.trdf_exportieren = echt
        assert gemerkt["saetze"] == []
        assert len(gemerkt["anhang"]) == 1
        assert gemerkt["anhang"][0]["wert"] == "2,3"
        assert gemerkt["anhang"][0]["rohw_id"]
    mit_fenster(pruefen)


def test_ohne_abweichung_wird_nichts_geschrieben():
    def pruefen(fenster):
        ohne_fenster()
        blatt = seite(fenster, zeilen=(11,))
        blatt._anhang_angleichen()
        assert "stimmen ueberein" in blatt.rohstand.cget("text")
    mit_fenster(pruefen)


def test_die_vorschau_sagt_dass_nur_der_anhang_geschrieben_wird():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        blatt.anhang[("26B0011", "DichteGB")]["mw"] = "2,9"
        vorschau = trdfreiter.Exportvorschau(
            fenster, blatt.auseinander(), "2026B051", lambda: None,
            nur_anhang=True)
        saetze = [kind.cget("text") for kind in vorschau.winfo_children()
                  if isinstance(kind, tk.Label)]
        assert any("nur der Teilprobenanhang" in satz for satz in saetze)
        assert "angleichen" in vorschau.title()
    mit_fenster(pruefen)


def test_eine_alte_sicherung_ohne_rohw_id_wird_angesagt():
    """Sie stellt nur die Ergebniszeile zurueck - der Anhang bliebe auf
    dem korrigierten Wert stehen, und niemand saehe es."""
    def pruefen(fenster):
        zeilen = [{"Serie": "2026B051", "Probe-Nr.": "26B0011",
                   "Groesse": "DichteGB", "PROB_ID": "11", "PM_ID": "13",
                   "PM_VER": "1", "UM_ID": "42", "GEGR_ID": "7",
                   "MW_ROH": "2,3", "MW": "2,3", "PSTA_ID": "1",
                   "KORREKTUR_FLAG": "", "FC8": "", "ROHW_ID": "",
                   "Anhang MW": "", "Anhang MW_OLD": "", "Wert neu": "2,9"}]
        geaendert = trdfexport.zurueck(zeilen)
        # Ohne ROHW_ID gilt die Zeile als berechnete Groesse - gemeint
        # war ein Rohwert, und genau das ist die Luecke.
        geaendert[0]["art"] = trdfexport.ROHWERT
        assert trdfexport.ohne_anhang(geaendert) == geaendert
        vorschau = trdfreiter.Exportvorschau(fenster, geaendert, "Alt.csv",
                                             lambda: None, zurueck=True)
        saetze = [kind.cget("text") for kind in vorschau.winfo_children()
                  if isinstance(kind, tk.Label)]
        assert any("keine ROHW_ID" in satz for satz in saetze), saetze
    mit_fenster(pruefen)


# ------------------------------------------------ Das Zurueckspielen

def test_zurueckspielen_sagt_der_datenbank_die_richtung():
    """Zurueck gelten andere Regeln: der gesicherte Stand darf leer sein.

    Eine berechnete Groesse haengt an keinem Anhang - dann sagt kein
    Satz mehr, in welche Richtung geschrieben wird, und der Weg
    scheiterte an einer leeren PSTA_ID.
    """
    def pruefen(fenster):
        ohne_fenster()
        gemerkt = {}

        def exportieren(zugang, saetze, hinweise=None, anhang=None,
                        anhang_hinweise=None, zurueck=False):
            gemerkt["zurueck"] = zurueck
            gemerkt["saetze"] = saetze
            for satz in saetze:                 # dieselbe Pruefung wie echt
                (trdfreiter.lims_db.trdf_zurueck_pruefen if zurueck
                 else trdfreiter.lims_db.trdf_satz_pruefen)(satz)
            return {"geschrieben": len(saetze), "ohne_zeile": [],
                    "versucht": len(saetze), "anhang_geschrieben": 0,
                    "anhang_ohne_zeile": [], "nicht_uebernommen": [],
                    "anhang_nicht_uebernommen": []}

        echt = trdfreiter.lims_db.trdf_exportieren
        trdfreiter.lims_db.trdf_exportieren = exportieren
        try:
            blatt = seite(fenster, zeilen=(11,), ordner=tempfile.mkdtemp())
            # Erst jetzt: der Abruf beim Aufbau soll nicht wirklich laufen.
            blatt._im_hintergrund = (
                lambda arbeit, fertig, schief: fertig(arbeit()))
            blatt._abrufen = lambda: None      # danach wird neu geholt
            zeilen = [{"Serie": "2026B051", "Probe-Nr.": "26B0011",
                       "Groesse": "TRDF", "PROB_ID": "11", "PM_ID": "1084",
                       "PM_VER": "1", "UM_ID": "42", "GEGR_ID": "",
                       "MW_ROH": "", "MW": "", "PSTA_ID": "",
                       "KORREKTUR_FLAG": "", "FC8": "", "ROHW_ID": "",
                       "Anhang MW": "", "Anhang MW_OLD": "",
                       "Wert neu": "1,7"}]
            blatt._zurueck_schreiben(trdfexport.zurueck(zeilen), "Alt.csv")
        finally:
            trdfreiter.lims_db.trdf_exportieren = echt
        assert gemerkt["zurueck"] is True
        assert gemerkt["saetze"][0]["psta_id"] is None
    mit_fenster(pruefen)


# ------------------------------------------------------------ Die Legende

def test_jeder_reiter_hat_seinen_infoknopf():
    """Drei Tabellen, drei Legenden - jede zu ihren eigenen Spalten."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        for oeffnen, spalte, erwartet in (
                (blatt._rohlegende_zeigen, "DichteGB", "DichteGrobboden"),
                (blatt._ergebnislegende_zeigen, "TRD_TRDF ber.",
                 "TrockenrohdichteFeinboden"),
                (blatt._prueflegende_zeigen, "TRDF",
                 "TrockenrohdichteFeinboden")):
            legende = oeffnen()
            try:
                assert legende.tabelle.hat(spalte), spalte
                namensspalte = [name for name in legende.spalten
                                if name in ("Name", "Parametername")][0]
                assert erwartet in legende.tabelle.wert(
                    spalte, namensspalte), spalte
            finally:
                legende.destroy()
    mit_fenster(pruefen)


def test_die_legende_zeigt_die_spalten_der_tabelle():
    """Nicht alle Groessen des Labors - die dieser Serie."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        legende = blatt._rohlegende_zeigen()
        try:
            assert legende.tabelle.zeilen() == blatt.rohtabelle.spalten()
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_eine_beschreibung_ueberdauert_das_fenster():
    """Sie liegt bei den Einstellungen - und nirgendwo sonst."""
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            legende = blatt._rohlegende_zeigen()
            legende.tabelle._setzen("_TSM", trdflegende.BESCHREIBUNG,
                                    "Maechtigkeit der Tiefenstufe")
            legende._sichern()
            legende.destroy()
            assert blatt.beschreibungen()["_TSM"] == \
                "Maechtigkeit der Tiefenstufe"
            # Und beim naechsten Mal steht sie wieder da - auch in einem
            # anderen Reiter, denn sie haengt am Formelkuerzel.
            neu = trdfreiter.TrdfSeite(fenster, lambda: ZUGANG,
                                       lambda *a, **k: None, ordner=basis)
            assert neu.beschreibungen()["_TSM"] == \
                "Maechtigkeit der Tiefenstufe"
    mit_fenster(pruefen)


def test_eine_geleerte_beschreibung_ist_wieder_weg():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            assert blatt._spalten_speichern(
                trdfreiter.BLATT_ROH, {"_TSM": "etwas"}) == ""
            assert blatt._spalten_speichern(
                trdfreiter.BLATT_ROH, {"_TSM": "  "}) == ""
            assert "_TSM" not in blatt.beschreibungen()
    mit_fenster(pruefen)


def test_von_der_beschreibung_geht_nichts_in_die_datenbank():
    """Sie ist eine Notiz des Labors und kein Messwert."""
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._spalten_speichern(trdfreiter.BLATT_ROH,
                                     {"TRDFgesch": "nur eine Notiz"})
            blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
            geaendert = blatt.aenderungen()
            saetze = (trdfexport.saetze(geaendert)
                      + trdfexport.anhangsaetze(geaendert))
            assert saetze
            for satz in saetze:
                assert "nur eine Notiz" not in str(satz)
    mit_fenster(pruefen)


# ------------------------------------------------------- Der Bodenblock

def test_pfeil_runter_blaettert_zur_naechsten_probe():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 5, 11))
        blatt._block_zeigen("26B0001", "Probe")
        block = blatt.bloecke["26B0001"]
        try:
            blatt._block_wechseln(block, 1)
            assert block.probe == "26B0005"
            assert blatt.bloecke.get("26B0005") is block
            assert "26B0001" not in blatt.bloecke
            assert "26B0005" in block.title()
            blatt._block_wechseln(block, -1)
            assert block.probe == "26B0001"
        finally:
            block.destroy()
    mit_fenster(pruefen)


def test_am_ende_der_liste_ist_schluss():
    """Wer unten ankommt, soll es merken und nicht oben landen."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 5))
        blatt._block_zeigen("26B0001", "Probe")
        block = blatt.bloecke["26B0001"]
        try:
            blatt._block_wechseln(block, -1)
            assert block.probe == "26B0001"
            blatt._block_wechseln(block, 1)
            blatt._block_wechseln(block, 1)
            assert block.probe == "26B0005"
        finally:
            block.destroy()
    mit_fenster(pruefen)


def test_eine_schon_offene_probe_bekommt_kein_zweites_fenster():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 5))
        blatt._block_zeigen("26B0001", "Probe")
        blatt._block_zeigen("26B0005", "Probe")
        erster, zweiter = blatt.bloecke["26B0001"], blatt.bloecke["26B0005"]
        try:
            blatt._block_wechseln(erster, 1)
            assert erster.probe == "26B0001"      # unveraendert
            assert blatt.bloecke["26B0005"] is zweiter
        finally:
            erster.destroy()
            zweiter.destroy()
    mit_fenster(pruefen)


def test_der_block_hoert_auf_die_pfeiltasten():
    """Die Tasten selbst lassen sich hier nicht druecken - das Fenster
    haengt an einem verborgenen Hauptfenster und bekommt keine Eingabe.
    Geprueft wird deshalb beides einzeln: dass die Tasten gebunden sind
    und dass die Bindung eine Probe weiterschaltet."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 5))
        blatt._block_zeigen("26B0001", "Probe")
        block = blatt.bloecke["26B0001"]
        try:
            gebunden = set(block.bind())
            assert {"<Key-Down>", "<Key-Up>"} <= gebunden, gebunden
            block._wechseln(1)
            assert block.probe == "26B0005"
        finally:
            block.destroy()
    mit_fenster(pruefen)


# ------------------------------------------------------- Der Exportbericht

def geschrieben(blatt, geaendert, gescheitert=()):
    """Ein Schreibweg, wie ihn lims_db beantworten wuerde."""
    nicht = [{"prob_id": (eine["zeile"] or {}).get("prob_id"),
              "pm_id": (eine["zeile"] or {}).get("pm_id"),
              "pm_ver": (eine["zeile"] or {}).get("pm_ver")}
             for eine in gescheitert]
    blatt._geschrieben(geaendert,
                       {"geschrieben": len(geaendert) - len(nicht),
                        "ohne_zeile": [], "versucht": len(geaendert),
                        "anhang_geschrieben": 1, "anhang_ohne_zeile": [],
                        "nicht_uebernommen": nicht,
                        "anhang_nicht_uebernommen": []}, "irgendwo.csv")


def test_vor_dem_ersten_export_ist_der_bericht_leer():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(11,))
        assert blatt.letzter_export is None
        assert blatt.berichtstand.cget("text") == trdfreiter.BERICHT_LEER
    mit_fenster(pruefen)


def test_nach_dem_export_steht_die_probe_im_bericht():
    def pruefen(fenster):
        ohne_fenster()
        blatt = seite(fenster, zeilen=(11,), ordner=tempfile.mkdtemp())
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geschrieben(blatt, blatt.aenderungen())
        # Eine Zeile je Probe, eine Spalte je bewegter Groesse.
        assert blatt.berichtstabelle.wert("26B0011", "TRDFgesch") == \
            "1,800 → 1,700"
        assert "2026B051" in blatt.berichtstand.cget("text")
        assert "1 Proben" in blatt.berichtstand.cget("text")
    mit_fenster(pruefen)


def test_der_bericht_zeigt_auch_die_folgen_des_rohwerts():
    """Geaendert wird ein Rohwert - im LIMS bewegt sich mehr."""
    def pruefen(fenster):
        ohne_fenster()
        blatt = seite(fenster, zeilen=(11,), ordner=tempfile.mkdtemp())
        blatt._von_hand_geaendert("26B0011", "DichteGB", "2,9")
        geaendert = blatt.aenderungen()
        geschrieben(blatt, geaendert)
        spalten = blatt.berichtstabelle._spalten
        assert spalten[:3] == ["Zeile", "Probe-Nr.", "DichteGB"]
        assert len(spalten) > 3          # die berechneten Groessen dahinter
        assert blatt.berichtstabelle.wert("26B0011", spalten[3])
    mit_fenster(pruefen)


def test_was_nicht_ankam_steht_nicht_im_bericht():
    """Der Bericht sagt, was im LIMS steht - nicht, was geschickt wurde."""
    def pruefen(fenster):
        meldungen = ohne_fenster()
        blatt = seite(fenster, zeilen=(11,), ordner=tempfile.mkdtemp())
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geaendert = blatt.aenderungen()
        geschrieben(blatt, geaendert, gescheitert=geaendert)
        assert blatt.letzter_export["aenderungen"] == []
        assert "wie vorher" in blatt.berichtstand.cget("text")
        assert meldungen.gezeigt              # und gemeldet wurde es auch
    mit_fenster(pruefen)


def test_der_bericht_laesst_sich_ablegen():
    def pruefen(fenster):
        ohne_fenster()
        with tempfile.TemporaryDirectory() as basis:
            trdfreiter.trdfpruefung.oeffnen = lambda pfad: None
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
            geschrieben(blatt, blatt.aenderungen())
            blatt._bericht_speichern()
            pfad = blatt.berichtstand.cget("text")
            assert os.path.isfile(pfad)
            text = open(pfad, "rb").read().decode("utf-8-sig")
            assert "1,8 → 1,7" in text
    mit_fenster(pruefen)


def test_auf_dem_schirm_gerundet_in_der_datei_vollstaendig():
    """Zwei fuenfzehnstellige Zahlen je Zelle waeren nicht zu lesen -
    die Datei behaelt sie trotzdem, sie ist der Nachweis."""
    def pruefen(fenster):
        ohne_fenster()
        with tempfile.TemporaryDirectory() as basis:
            trdfreiter.trdfpruefung.oeffnen = lambda pfad: None
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._von_hand_geaendert("26B0011", "DichteGB", "2,9")
            geschrieben(blatt, blatt.aenderungen())
            spalte = blatt.berichtstabelle._spalten[3]     # eine gerechnete
            gezeigt = blatt.berichtstabelle.wert("26B0011", spalte)
            assert len(gezeigt.split(" → ")[1].split(",")[1]) <= 3
            blatt._bericht_speichern()
            text = open(blatt.berichtstand.cget("text"),
                        "rb").read().decode("utf-8-sig")
            assert gezeigt not in text        # dort steht die lange Zahl
    mit_fenster(pruefen)


def test_der_bericht_ueberdauert_den_naechsten_abruf():
    """"Immer der letzte Export" - auch wenn danach neu abgerufen wird."""
    def pruefen(fenster):
        ohne_fenster()
        blatt = seite(fenster, zeilen=(11,), ordner=tempfile.mkdtemp())
        blatt._von_hand_geaendert("26B0011", "TRDFgesch", "1,7")
        geschrieben(blatt, blatt.aenderungen())
        blatt._uebernehmen(geholt(zeilen=(11,)))
        assert blatt.berichtstabelle.wert("26B0011", "TRDFgesch") == \
            "1,800 → 1,700"
    mit_fenster(pruefen)


# ------------------------------------------- Was beim Scrollen stehen bleibt

def test_die_rohwerte_halten_zeile_probe_und_variante_fest():
    """Ohne die Variante sagt keine Zahl der Zeile etwas - also bleibt
    sie mit im Blick, gleich hinter der Probennummer."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        spalten, fest, _koepfe, _alle = blatt._rohspalten()
        assert fest == ["Zeile", "Probe", trdfrohpruefung.VARIANTE]
        assert spalten[:3] == ["Zeile", "Probe", trdfrohpruefung.VARIANTE]
        assert blatt.rohtabelle._fest == fest
        # Die feste Haelfte traegt die Probennummer, die laufende nicht.
        assert "26B0011" in blatt.rohtabelle.festtext.get("1.0", "end")
        assert "26B0011" not in blatt.rohtabelle.text.get("1.0", "end")
    mit_fenster(pruefen)


def test_die_ergebnisse_halten_zeile_und_probe_fest():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        assert blatt.ergebnistabelle._fest == ["Zeile", "Probe"]
        assert blatt.ergebnistabelle.spalten()[:2] == ["Zeile", "Probe"]
    mit_fenster(pruefen)


def test_das_pruefblatt_haelt_zeile_und_probennummer_fest():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        assert blatt.pruefungstabelle._fest == ["Zeile", "Probe-Nr."]
    mit_fenster(pruefen)


def test_auch_das_grosse_fenster_haelt_sie_fest():
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        gross = blatt._gross_zeigen()
        try:
            assert gross.tabelle._fest == blatt.rohtabelle._fest
            assert gross.tabelle._fest[:3] == ["Zeile", "Probe",
                                               trdfrohpruefung.VARIANTE]
        finally:
            gross._schliessen()
    mit_fenster(pruefen)


def test_die_getoenten_paare_folgen_der_neuen_reihenfolge():
    """Der Wechsel zaehlt die Groessen so, wie sie dann stehen."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        spalten, gruppen, fest, _koepfe, _alle = blatt._ergebnisspalten()
        for name in fest:
            assert name not in gruppen
        beteiligt = [name for name in spalten if name in gruppen]
        # Ein Paar traegt dieselbe Toenung - sonst zerfaellt es im Auge.
        for name in beteiligt:
            kuerzel, anhang = trdflegende.zerlegen(name)
            if anhang:
                assert gruppen[f"{kuerzel} LIMS"] == gruppen[f"{kuerzel} ber."]
    mit_fenster(pruefen)


def test_eine_gespeicherte_reihenfolge_gilt_beim_naechsten_mal():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(5, 11), ordner=basis)
            spalten, _fest, _koepfe, _alle = blatt._rohspalten()
            hinten = spalten[-3]
            blatt._spalten_speichern(
                trdfreiter.BLATT_ROH, {},
                {"reihenfolge": [hinten], "fest": ["Zeile", "Probe"],
                 "kopfspalte": "Spalte"})
            neu, fest, _koepfe, _alle = blatt._rohspalten()
            assert fest == ["Zeile", "Probe"]
            assert neu[2] == hinten, neu[:4]
            # Und die Tabelle steht schon so da.
            assert blatt.rohtabelle.spalten() == neu
    mit_fenster(pruefen)


def test_wer_den_namen_oben_haben_will_bekommt_ihn():
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._spalten_speichern(
                trdfreiter.BLATT_ROH, {},
                {"reihenfolge": [], "fest": ["Zeile", "Probe"],
                 "kopfspalte": "Name"})
            kopf = blatt.rohtabelle.kopf.get("1.0", "1.end")
            assert "Tiefenstufenmächtigkeit" in kopf, kopf
            # Innen heisst die Spalte weiter, wie das LIMS sie nennt.
            assert "_TSM" in blatt.rohtabelle.spalten()
    mit_fenster(pruefen)


def test_wer_eine_spalte_ausblendet_sieht_sie_nur_noch_in_der_legende():
    """Sonst liesse sie sich nicht wieder einblenden."""
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(5, 11), ordner=basis)
            vorher = blatt.rohtabelle.spalten()
            assert "DichteGB" in vorher
            blatt._spalten_speichern(
                trdfreiter.BLATT_ROH, {},
                {"reihenfolge": [], "fest": ["Zeile", "Probe"],
                 "versteckt": ["DichteGB"], "kopfspalte": "Spalte"})
            gezeigt = blatt.rohtabelle.spalten()
            assert "DichteGB" not in gezeigt
            assert len(gezeigt) == len(vorher) - 1
            # Die Werte der anderen Spalten stehen weiter da.
            assert "_TSM" in gezeigt
            legende = blatt._rohlegende_zeigen()
            try:
                assert legende.tabelle.hat("DichteGB")
                assert legende.tabelle.wert(
                    "DichteGB", trdflegende.ZEIGEN) == trdflegende.NEIN
            finally:
                legende.destroy()
    mit_fenster(pruefen)


def test_eine_einzelne_groesse_bekommt_ihre_eigene_ueberschrift():
    """Das Kuerzel bei den kryptischen, der Name bei den seltenen."""
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._spalten_speichern(
                trdfreiter.BLATT_ROH, {},
                {"reihenfolge": [], "fest": ["Zeile", "Probe"],
                 "kopfspalte": "Spalte",
                 "kopfspalten": {"_TSM": "Name"}})
            kopf = (blatt.rohtabelle.kopf.get("1.0", "1.end")
                    + blatt.rohtabelle.festkopf.get("1.0", "1.end"))
            assert "Tiefenstufenmächtigkeit" in kopf, kopf
            # Und nur diese eine - die anderen tragen weiter ihr Kuerzel.
            assert "DichteGB" in kopf, kopf
            assert "_TSM" in blatt.rohtabelle.spalten()
    mit_fenster(pruefen)


def test_die_kopfwahl_einer_groesse_gilt_in_allen_tabellen():
    """Dieselbe Groesse soll nicht hier ihren Namen und dort ihr
    Kuerzel tragen."""
    def pruefen(fenster):
        with tempfile.TemporaryDirectory() as basis:
            blatt = seite(fenster, zeilen=(11,), ordner=basis)
            blatt._spalten_speichern(
                trdfreiter.BLATT_ROH, {},
                {"reihenfolge": [], "fest": ["Zeile", "Probe"],
                 "kopfspalte": "Spalte",
                 "kopfspalten": {"TRD_TRDF": "Einheit"}})
            assert blatt.kopfspalten() == {"TRD_TRDF": "Einheit"}
            kopf = blatt.ergebnistabelle.kopf.get("1.0", "1.end")
            assert "g/cm3 LIMS" in kopf, kopf
    mit_fenster(pruefen)


def test_die_rohwerte_lassen_sich_auf_die_befunde_eingrenzen():
    """Wie im Pruefblatt: der Arbeitsvorrat dessen, der sie abarbeitet."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(5, 11))
        alle = blatt.rohtabelle.zeilen()
        mit_befund = [probe for _lnr, probe in blatt.proben
                      if blatt.rohbefund(probe)]
        blatt.v_nur_rohbefunde.set(True)
        blatt._rohwerte_zeigen()
        assert blatt.rohtabelle.zeilen() == mit_befund, mit_befund
        # Gerechnet und geschrieben wird weiter ueber die ganze Serie.
        assert len(blatt.rohblatt()) == len(alle)
        if len(mit_befund) < len(alle):
            assert "ausgeblendet" in blatt.rohstand.cget("text")
        blatt.v_nur_rohbefunde.set(False)
        blatt._rohwerte_zeigen()
        assert blatt.rohtabelle.zeilen() == alle
    mit_fenster(pruefen)


def test_wer_im_blockbild_blaettert_sieht_die_zeile_unterlegt():
    """Das Bild sagt, welche Probe - die Tabelle sagt, wo sie steht."""
    def pruefen(fenster):
        blatt = seite(fenster, zeilen=(1, 5))
        blatt._block_zeigen("26B0001", "Probe")
        block = blatt.bloecke["26B0001"]
        try:
            assert blatt.rohtabelle.gewaehlt() == ["26B0001"]
            assert blatt.pruefungstabelle.gewaehlt() == ["26B0001"]
            gross = blatt._gross_zeigen()
            try:
                assert gross.tabelle.gewaehlt() == ["26B0001"]
                # Ein Pfeil weiter - und die naechste Zeile ist es.
                blatt._block_wechseln(block, 1)
                assert block.probe == "26B0005"
                assert blatt.rohtabelle.gewaehlt() == ["26B0005"]
                assert gross.tabelle.gewaehlt() == ["26B0005"]
            finally:
                gross._schliessen()
        finally:
            block.destroy()
        fenster.update()
        # Fenster zu, Unterlegung weg.
        assert blatt.rohtabelle.gewaehlt() == []
    mit_fenster(pruefen)


# ------------------------------------------- Probenart und Methodentext
#
# Das Haus fuehrt dieselbe Untersuchungsmethode je Probenart einmal:
# TRDF3.2 fuer den Boden und TRDF3.2 fuer den Humus sind zwei UM_ID.

def test_ein_h_in_der_serie_ist_humus() -> None:
    """Die Tabelle PROBENART des LIMS fuehrt 1 Boden, 2 Pflanze,
    3 Wasser, 4 Humus - Holz gibt es dort nicht. Eine Humusserie unter
    dem Namen "Holz" zu fuehren heisst, sie nicht zu finden."""
    assert trdfreiter.probenart("2024H00870") == "Humus"
    assert trdfreiter.probenart("2026B051") == "Boden"
    assert "Holz" not in trdfreiter.PROBENARTEN.values()
    assert set(trdfreiter.PROBENART_ZU_ID.values()) == \
        set(trdfreiter.PROBENARTEN.values())


def test_die_probenart_kommt_aus_den_gebuchten_zeilen() -> None:
    """PART_ID der Ergebniszeile ist die Auskunft des LIMS; der
    Buchstabe im Seriennamen ist die Hausschreibweise davon - und bei
    einzelnen Proben gibt es keinen Namen, aus dem sie zu raten
    waere."""
    def pruefen(fenster):
        blatt = seite(fenster, part_id=4)
        assert "Humus" in blatt.auskunft.cget("text")
    mit_fenster(pruefen)


def test_ohne_part_id_bleibt_der_serienname_als_notnagel() -> None:
    """Eine Auskunft aus dem Namen ist besser als keine."""
    def pruefen(fenster):
        blatt = seite(fenster, part_id=None)
        assert "Boden" in blatt.auskunft.cget("text")
    mit_fenster(pruefen)


def test_zwei_methoden_mit_gleichem_kuerzel_sind_beide_waehlbar() -> None:
    """In einer Liste, die zweimal "TRDF3.2" zeigt, ist die zweite
    nicht zu waehlen - und welche die erste war, stand nirgends."""
    texte = trdfreiter.methodentexte([(42, "TRDF3.2"), (207, "TRDF3.2"),
                                      (43, "TRDFBA1.1")])
    assert [text for _um, _k, text in texte] == [
        "TRDF3.2 (UM 42)", "TRDF3.2 (UM 207)", "TRDFBA1.1"]
    # Das Kuerzel bleibt daneben stehen: gefragt wird mit ihm, und im
    # Kopf des Reiters steht es ohne die Nummer.
    assert [k for _um, k, _text in texte][0] == "TRDF3.2"


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
