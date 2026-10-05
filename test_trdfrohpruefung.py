"""Prueft die Pruefung der TRDF-Rohwerte - ohne Datenbank, ohne GUI.

Die Vollstaendigkeitsliste ist aus den Formeln des LIMS abgelesen. Sie
kann nur veralten, nicht auffallen: fehlt hier ein Rohwert, meldet das
Programm nichts, und das faellt erst auf, wenn eine Serie mit "##1093"
im LIMS steht. Deshalb steht jede Variante unten einzeln da - und die
echten Zeilen der 2026B051 daneben als Probe aufs Exempel.

Aufruf:  python test_trdfrohpruefung.py
"""

from __future__ import annotations

import os
import tempfile

import test_trdf
import trdf
import trdfrohpruefung as roh
from trdf import D

ZEILEN = test_trdf.ZEILEN
FORMELN = test_trdf.FORMELN


def werte(variante, **rest) -> dict:
    """Eine vollstaendige Probe dieser Variante - dann gezielt veraendert."""
    gefuellt = {roh.VARIANTE: str(variante)}
    vorgaben = {roh.TIEFENSTUFE: "30", roh.FAKTOR: "1", roh.VOL_SZ: "500",
                roh.MASSE_SZ: "834,3", roh.GROBBODEN_SZ: "24,99",
                roh.MASSE_SCHAUFEL: "7938,1", roh.GROBBODEN_63: "641,42",
                roh.GROBBODEN_263: "660,42", roh.GROBBODEN_SCHAUFEL: "392,17",
                roh.MASSE_MINI: "797,3", roh.VOL_MINI: "500",
                roh.DICHTE_GB: "2,2", roh.GBF_ANTEIL: "10",
                roh.TRDF_GESCHAETZT: "1,8"}
    for name in roh.GEBRAUCHT.get(variante, ()):
        gefuellt[name] = vorgaben[name]
    gefuellt.update(rest)
    return gefuellt


# ----------------------------------------------- Was welche Variante braucht

def test_die_liste_deckt_jede_variante_ab_die_es_gibt():
    """Variante 3 gibt es nicht - der Rest muss vollstaendig sein."""
    assert roh.VARIANTEN == (1, 2, 4, 5, 6, 7)
    assert 3 not in roh.GEBRAUCHT


def test_jede_vollstaendige_probe_bleibt_ohne_befund():
    for art in roh.VARIANTEN:
        assert roh.bewerten(werte(art)) == [], art


def test_jeder_gebrauchte_rohwert_wird_einzeln_vermisst():
    for art in roh.VARIANTEN:
        for name in roh.GEBRAUCHT[art]:
            gefunden = roh.fehlende(werte(art, **{name: "x"}))
            assert gefunden == [name], (art, name, gefunden)


def test_die_gebrauchten_rohwerte_stehen_auch_in_den_formeln():
    """Ein Name, den keine Formel kennt, waere ein Tippfehler."""
    text = " ".join(FORMELN.values())
    for art, namen in roh.GEBRAUCHT.items():
        for name in namen:
            assert name in text, (art, name)


def test_eine_unbekannte_variante_faellt_auf():
    """Aber nur, wenn ueberhaupt etwas dasteht."""
    assert roh.bewerten({roh.VARIANTE: "3", roh.VOL_SZ: "500"}) == \
        [roh.VARIANTE_UNBEKANNT]
    assert roh.bewerten({roh.VARIANTE: "", roh.MASSE_SZ: "834,3"}) == \
        [roh.VARIANTE_UNBEKANNT]


def test_ein_x_in_der_variante_ist_eine_angabe_und_keine_luecke():
    """Ein leeres Feld heisst "hier fehlt noch die Angabe", ein x
    heisst "hier soll keine stehen" - dann fehlt auch keiner der
    Rohwerte, die eine Variante braeuchte."""
    assert roh.ohne_variante({roh.VARIANTE: "x"})
    assert not roh.ohne_variante({roh.VARIANTE: ""})
    assert not roh.ohne_variante({roh.VARIANTE: "4"})
    assert roh.bewerten({roh.VARIANTE: "x", roh.MASSE_SZ: "834,3"}) == []
    assert roh.vollstaendig({roh.VARIANTE: "x"}) == []


def test_bei_einem_x_bleibt_die_variante_am_anhang_stumm():
    """Dass dort noch eine Zahl steht, ist gerade der Zustand, den das
    x beschreibt. Die uebrigen Rohwerte werden weiter verglichen."""
    werte = {roh.VARIANTE: "x", roh.MASSE_SZ: "834,3"}
    vergleich = {roh.VARIANTE: ("x", "7"), roh.MASSE_SZ: ("834,3", "834,3")}
    assert roh.anhang_ohne_variante(vergleich, werte) == []
    assert roh.bewerten(werte, vergleich=vergleich) == []
    # Ein anderer Rohwert, der auseinandergeht, faellt weiter auf.
    vergleich[roh.MASSE_SZ] = ("834,3", "900")
    assert roh.anhang_ohne_variante(vergleich, werte) == [
        roh.ANHANG_ANDERS.format(roh.MASSE_SZ)]
    # Und mit einer richtigen Variante wird auch sie verglichen.
    mit = {roh.VARIANTE: "4", roh.MASSE_SZ: "834,3"}
    assert roh.anhang_ohne_variante({roh.VARIANTE: ("4", "7")}, mit) == [
        roh.ANHANG_ANDERS.format(roh.VARIANTE)]


def test_eine_leere_zeile_ist_kein_fehler():
    """Sie wartet auf ihre Messung und soll nicht wie ein Fehler
    aussehen - eine gefuellte ohne Variante schon: an ihr rechnet das
    LIMS nichts, obwohl alles da waere."""
    assert roh.bewerten({}) == [roh.KEINE_DATEN]
    assert roh.bewerten({roh.VARIANTE: ""}) == [roh.KEINE_DATEN]
    # Mit einem x in der Variante steht dort ueberhaupt nichts mehr:
    # die Teilprobe bekommt keine, und damit fehlt auch nichts.
    assert roh.bewerten({roh.VARIANTE: "x"}) == []
    assert roh.bewerten({roh.VARIANTE: "x", roh.VOL_SZ: "x",
                         roh.MASSE_SZ: ""}) == []
    assert roh.leer({roh.VARIANTE: "4"})
    assert not roh.leer({roh.VARIANTE: "x", roh.VOL_SZ: "500"})


def test_ein_wert_den_die_variante_nie_benutzt_deutet_auf_die_falsche():
    saetze = roh.bewerten(werte(1, **{roh.GROBBODEN_SZ: "24,99"}))
    assert saetze == [roh.UEBERZAEHLIG.format(1, roh.GROBBODEN_SZ)]


def test_die_fotoauswertung_darf_ueberall_stehen():
    assert roh.ueberzaehlige(werte(1, **{roh.SKA_FOTO: "30"})) == []


def test_wo_die_variante_fehlt_wird_nichts_weiter_behauptet():
    assert roh.fehlende({roh.VARIANTE: "x"}) == []
    assert roh.ueberzaehlige({roh.VARIANTE: "x"}) == []


# ------------------------------------------------------- Die einzelnen Werte

def test_die_gesteinsdichte_liegt_zwischen_zwei_und_drei():
    assert roh.bereiche({roh.DICHTE_GB: "2,64"}) == []
    assert roh.bereiche({roh.DICHTE_GB: "26,4"})
    assert roh.bereiche({roh.DICHTE_GB: "1"})


def test_anteile_liegen_zwischen_null_und_hundert():
    assert roh.bereiche({roh.GBF_ANTEIL: "0"}) == []
    assert roh.bereiche({roh.GBF_ANTEIL: "100"}) == []
    assert roh.bereiche({roh.GBF_ANTEIL: "101"})
    assert roh.bereiche({roh.SKA_FOTO: "-1"})


def test_massen_und_volumen_sind_positiv():
    assert roh.bereiche({roh.VOL_SZ: "0"})
    assert roh.bereiche({roh.MASSE_SZ: "-1"})
    # Ein Grobboden von null Gramm ist dagegen ein Wert: da war keiner.
    assert roh.bereiche({roh.GROBBODEN_63: "0"}) == []


def test_die_geschaetzte_dichte_haelt_sich_an_ihren_bereich():
    assert roh.bereiche({roh.TRDF_GESCHAETZT: "1,8"}) == []
    assert roh.bereiche({roh.TRDF_GESCHAETZT: "18"})


def test_der_faktor_bergland_flachland_ist_hoechstens_eins():
    assert roh.bereiche({roh.FAKTOR: "0,66"}) == []
    assert roh.bereiche({roh.FAKTOR: "1"}) == []
    assert roh.bereiche({roh.FAKTOR: "1,5"})


def test_was_nicht_dasteht_wird_nicht_bemaengelt():
    assert roh.bereiche({roh.DICHTE_GB: "x", roh.VOL_SZ: ""}) == []


def test_die_meldung_nennt_den_rohwert():
    satz, = roh.bereiche({roh.DICHTE_GB: "9"})
    assert roh.DICHTE_GB in satz


# --------------------------------------------------- Was zueinander passt

def test_die_feuchtdichte_faengt_das_verrutschte_komma():
    assert roh.beziehungen(werte(2)) == []
    assert roh.DICHTE_SZ in roh.beziehungen(werte(2, **{roh.MASSE_SZ: "8343"}))
    assert roh.DICHTE_SZ in roh.beziehungen(werte(2, **{roh.MASSE_SZ: "83"}))


def test_der_ministechzylinder_wird_ebenso_geprueft():
    assert roh.DICHTE_MINI in roh.beziehungen(werte(5, **{roh.MASSE_MINI:
                                                          "7973"}))


def test_der_grobboden_ist_teil_der_probe():
    saetze = roh.beziehungen(werte(2, **{roh.GROBBODEN_SZ: "900"}))
    assert roh.GROBBODEN_SCHWERER in saetze


def test_der_grobboden_passt_in_den_zylinder():
    """Sonst wird der Feinbodenraum negativ - und die Dichte Unsinn."""
    saetze = roh.beziehungen(werte(2, **{roh.GROBBODEN_SZ: "1200",
                                         roh.MASSE_SZ: "2000",
                                         roh.DICHTE_GB: "2,2",
                                         roh.VOL_SZ: "500"}))
    assert roh.GROBBODEN_ZU_GROSS in saetze


def test_die_schaufelprobe_geht_auf():
    saetze = roh.beziehungen(werte(4, **{roh.GROBBODEN_263: "8000"}))
    assert roh.SCHAUFEL_GEHT_NICHT_AUF in saetze


def test_das_feinste_steckt_im_groeberen():
    """2 bis 6,3 mm ist ein Teil von 2 bis 63 mm, nicht mehr."""
    assert roh.beziehungen(werte(5)) == []
    saetze = roh.beziehungen(werte(5, **{roh.GROBBODEN_SCHAUFEL: "2000"}))
    assert roh.FEINSTES_ZU_GROSS in saetze


def test_der_wiederfindungsgrad_hat_ein_fenster():
    assert roh.beziehungen(werte(2), wgh="1,3") == []
    assert roh.WGH_UNPLAUSIBEL in roh.beziehungen(werte(2), wgh="80")
    assert roh.beziehungen(werte(2), wgh="x") == []


# ------------------------------------------- Die echten Zeilen der 2026B051

def test_die_beiden_bekannten_luecken_werden_gefunden():
    """LNR 92 fehlt die geschaetzte Dichte, LNR 269 der Grobboden 2-63.

    Beides erklaert, warum im LIMS "##1093" steht - und beides ist der
    Grund, aus dem es diese Pruefung gibt.
    """
    assert roh.bewerten(ZEILEN[92]["roh"]) == \
        [roh.FEHLT.format(roh.TRDF_GESCHAETZT)]
    assert roh.bewerten(ZEILEN[269]["roh"]) == \
        [roh.FEHLT.format(roh.GROBBODEN_263)]


def test_die_uebrigen_echten_zeilen_bleiben_ohne_befund():
    for lnr in (1, 5, 11, 33, 104):
        assert roh.bewerten(ZEILEN[lnr]["roh"],
                            ZEILEN[lnr]["wgh"]) == [], lnr


def test_der_echte_fehler_des_lims_ist_keiner_der_rohwerte():
    """LNR 104: die Rohwerte sind vollstaendig und plausibel - gebucht
    hat das LIMS trotzdem eine Null. Das ist ein Befund der
    Ergebnispruefung und keiner von hier."""
    assert roh.bewerten(ZEILEN[104]["roh"]) == []
    assert not roh.unvollstaendig(ZEILEN[104]["roh"])


def test_unvollstaendig_sagt_ob_ein_urteil_ueberhaupt_traegt():
    assert roh.unvollstaendig(ZEILEN[92]["roh"])
    assert roh.unvollstaendig({roh.VARIANTE: ""})
    # Ein x ist keine Luecke: es soll dort nichts stehen.
    assert not roh.unvollstaendig({roh.VARIANTE: "x"})
    assert not roh.unvollstaendig(ZEILEN[5]["roh"])


# ------------------------------------------------------------- Das Blatt

def test_das_blatt_zeigt_variante_rohwerte_und_bewertung():
    rohliste = (roh.VOL_SZ, roh.MASSE_SZ)
    gefunden = roh.zeile({"lnr": 92, "probe": "26B0092",
                          "werte": ZEILEN[92]["roh"], "wgh": "0,9",
                          "bewertung": roh.bewerten(ZEILEN[92]["roh"])},
                         rohliste)
    zeile = dict(zip(roh.spalten(rohliste), gefunden))
    assert zeile["Zeile"] == 92 and zeile["Probe-Nr."] == "26B0092"
    assert zeile["Variante"] == "7"
    assert zeile[roh.VOL_SZ] == trdf.MARKE
    assert roh.TRDF_GESCHAETZT in zeile[roh.BEWERTUNGSSPALTE]


def test_das_rohwertblatt_geht_als_csv_in_den_ordner():
    with tempfile.TemporaryDirectory() as basis:
        ordner = os.path.join(basis, roh.ORDNER)
        pfad = roh.schreiben(ordner, "2026B051",
                             [{"lnr": 92, "probe": "26B0092",
                               "werte": ZEILEN[92]["roh"],
                               "bewertung": ["Rohwert fehlt: TRDFgesch"]}],
                             (roh.VOL_SZ,))
        assert os.path.basename(pfad) == "Rohwerte 2026B051.csv"
        text = open(pfad, "rb").read().decode("cp1252", "replace")
        assert "26B0092" in text and "TRDFgesch" in text


def test_ein_unbeschreibbarer_ordner_meldet_sich_und_wirft_nicht():
    with tempfile.TemporaryDirectory() as basis:
        sperre = os.path.join(basis, "keinordner")
        open(sperre, "w").close()
        assert roh.schreiben(os.path.join(sperre, "tiefer"), "2026B051",
                             [], ()) == ""


# ------------------------------------------- Was die Variante aufraeumt

def alle_rohwerte(wert="1") -> dict:
    """Eine Zeile, in der jeder Rohwert etwas stehen hat."""
    werte = {kuerzel: wert for kuerzel in
             sorted({k for kuerzel in roh.GEBRAUCHT.values()
                     for k in kuerzel} | {roh.SKA_FOTO})}
    werte[roh.VARIANTE] = "1"
    return werte


def test_die_variante_setzt_die_ueberzaehligen_auf_x():
    """So haelt es die Eingabemaske des LIMS auch."""
    neu = roh.nach_variante(alle_rohwerte(), "1")
    assert set(neu) == set(roh.MASKIERT[1])
    assert set(neu.values()) == {trdf.MARKE}
    # Was Variante 1 braucht, bleibt unberuehrt.
    for kuerzel in roh.GEBRAUCHT[1]:
        assert kuerzel not in neu, kuerzel


def test_jede_variante_raeumt_nur_ihr_eigenes_auf():
    """Kein Rohwert wird zugleich gebraucht und maskiert - sonst
    stuende nach dem Wechsel ein x, wo gerechnet werden soll."""
    for nummer, maskiert in roh.MASKIERT.items():
        gebraucht = set(roh.GEBRAUCHT[nummer])
        assert not gebraucht & set(maskiert), nummer


def test_die_variante_selbst_bleibt_stehen():
    for eingabe in ("1", "5", "0", "x"):
        neu = roh.nach_variante(alle_rohwerte(), eingabe)
        assert roh.VARIANTE not in neu, eingabe


def test_null_raeumt_die_ganze_zeile_leer():
    neu = roh.nach_variante(alle_rohwerte(), "0")
    assert set(neu.values()) == {""}
    assert roh.SKA_FOTO in neu


def test_ein_x_belegt_die_ganze_zeile_mit_x():
    neu = roh.nach_variante(alle_rohwerte(), "x")
    assert set(neu.values()) == {trdf.MARKE}
    assert roh.SKA_FOTO in neu


def test_ohne_zahl_bekommt_die_fotoauswertung_ein_x():
    """Sie haengt an keiner Variante: steht dort keine Zahl, steht dort x."""
    werte = alle_rohwerte()
    werte[roh.SKA_FOTO] = ""
    neu = roh.nach_variante(werte, "4")
    assert neu[roh.SKA_FOTO] == trdf.MARKE
    # Mit einer Zahl bleibt sie stehen.
    werte[roh.SKA_FOTO] = "12,5"
    assert roh.SKA_FOTO not in roh.nach_variante(
        werte, "4")


def test_eine_unbekannte_variante_raeumt_nichts_auf():
    """Lieber nichts anfassen als raten - die Pruefung meldet sie ohnehin."""
    for eingabe in ("3", "", "  ", "abc"):
        assert roh.nach_variante(alle_rohwerte(), eingabe) == {}


def test_was_schon_dasteht_wird_nicht_noch_einmal_gesetzt():
    werte = alle_rohwerte()
    for kuerzel in roh.MASKIERT[2]:
        werte[kuerzel] = trdf.MARKE
    assert roh.nach_variante(werte, "2") == {}


def test_nur_rohwerte_die_es_gibt_werden_angefasst():
    """Eine Serie muss nicht jeden Rohwert fuehren."""
    werte = {roh.VARIANTE: "1",
             roh.DICHTE_GB: "2,65"}
    assert set(roh.nach_variante(werte, "1")) == {
        roh.DICHTE_GB}


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
