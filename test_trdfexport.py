"""Prueft den Rueckweg der TRDF-Pruefung - ohne Datenbank, ohne GUI.

Dies ist der einzige Weg im Programm, der einen Messwert im LIMS
ueberschreibt. Was hier schiefgeht, faellt niemandem auf, bevor jemand
in der Datenbank nachsieht - deshalb steht jeder Schritt einzeln als
Pruefung da: das Zahlenformat, die Auswahl dessen, was ueberhaupt
geschrieben wird, und die Sicherung, ohne die nichts geschieht.

Aufruf:  python test_trdfexport.py
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile

import lims_db
import trdf
import trdfexport
import trdfpruefung
from trdf import D

ZEITPUNKT = dt.datetime(2026, 9, 8, 10, 30, 0)

ZEILE = {"prob_id": 11, "pm_id": 1084, "pm_ver": 1, "um_id": 42,
         "gegr_id": 7, "mw_roh": "1,8", "mw": "1,8", "psta_id": 1,
         "korrektur_flag": None, "fc8": None}


def eine(**rest) -> dict:
    angaben = {"probe": {"lnr": 11, "probe": "26B0011"},
               "kuerzel": "TRDFgesch", "art": trdfexport.ROHWERT,
               "alt": "1,8", "neu": D("1.7"), "zeile": dict(ZEILE),
               "name": "TRDFgeschTRDF3.2", "anhang": None}
    angaben.update(rest)
    return trdfexport.aenderung(angaben.pop("probe"), angaben.pop("kuerzel"),
                                angaben.pop("art"), angaben.pop("alt"),
                                angaben.pop("neu"), angaben.pop("zeile"),
                                angaben.pop("name"), angaben.pop("anhang"))


# ------------------------------------------------------- Das Zahlenformat

def test_die_zahl_geht_so_hinein_wie_das_lims_sie_schreibt():
    assert trdfexport.zahlfeld(D("1.63465373129843")) == "1,63465373129843"
    assert trdfexport.zahlfeld("1,8") == "1,8"
    assert trdfexport.zahlfeld(D("1.80000")) == "1,8"
    assert trdfexport.zahlfeld(D(0)) == "0"


def test_kein_exponent_und_kein_tausenderpunkt():
    """Fuer das LIMS waere "1E+3" kein Wert, sondern Text."""
    assert trdfexport.zahlfeld(D("1E+3")) == "1000"
    assert trdfexport.zahlfeld(D("0.00001")) == "0,00001"
    assert "." not in trdfexport.zahlfeld(D("4105.9465280043"))


def test_mehr_als_fuenfzehn_ziffern_werden_gerundet():
    lang = D(1) / D(3)
    assert trdfexport.zahlfeld(lang) == "0,333333333333333"


def test_wo_keine_zahl_ist_steht_nichts():
    for wert in (None, "x", "X", "##1093", ""):
        assert trdfexport.zahlfeld(wert) == ""


# ------------------------------------------------- Was geschrieben wird

def test_bewegt_hat_sich_was_vorher_anders_war():
    assert trdfexport.verschoben(D(1), D(2))
    assert not trdfexport.verschoben(D(1), D(1))


def test_aus_nichts_wird_etwas_und_umgekehrt():
    """Beides ist eine Bewegung: das LIMS hatte hier ein 'x'."""
    assert trdfexport.verschoben(None, D(2))
    assert trdfexport.verschoben(D(2), None)
    assert not trdfexport.verschoben(None, None)


def test_die_uebersicht_stellt_alt_und_neu_nebeneinander():
    zeile = dict(zip(trdfexport.SPALTEN,
                     trdfexport.uebersicht([eine()])[0]))
    assert zeile["Zeile"] == 11 and zeile["Probe-Nr."] == "26B0011"
    assert zeile["Groesse"] == "TRDFgesch"
    assert zeile["Art"] == trdfexport.ROHWERT
    assert zeile["Pruefmethode"] == "TRDFgeschTRDF3.2"
    assert zeile["PM_ID"] == 1084 and zeile["PM_VER"] == 1
    assert zeile["Wert aktuell LIMS"] == "1,8"
    assert zeile["Wert neu"] == "1,7"


def test_wo_im_lims_nichts_stand_steht_die_marke():
    zeile = dict(zip(trdfexport.SPALTEN,
                     trdfexport.uebersicht([eine(alt="x")])[0]))
    assert zeile["Wert aktuell LIMS"] == trdf.MARKE


def test_ohne_ergebniszeile_kein_satz():
    """Angelegt wird nichts - gemeldet schon."""
    aenderungen = [eine(), eine(zeile=None, kuerzel="TRD_TRDF")]
    assert len(trdfexport.saetze(aenderungen)) == 1
    assert len(trdfexport.ohne_zeile(aenderungen)) == 1
    assert trdfexport.ohne_zeile(aenderungen)[0]["kuerzel"] == "TRD_TRDF"


def test_das_ziel_sagt_welche_stellen_getroffen_werden():
    assert trdfexport.ziel(eine()) == trdfexport.ZIEL_ERGEBNIS
    mit_anhang = eine(anhang={"prob_id": 11, "um_id": 42, "rohw_id": 7,
                              "mw": "1,8", "mw_old": None})
    assert trdfexport.ziel(mit_anhang) == trdfexport.ZIEL_BEIDE
    assert trdfexport.ziel(eine(zeile=None)) == trdfexport.ZIEL_KEINS


def test_der_anhangsatz_traegt_nur_wert_und_schluessel():
    mit_anhang = eine(anhang={"prob_id": 11, "um_id": 42, "rohw_id": 7,
                              "mw": "1,8", "mw_old": None})
    satz, = trdfexport.anhangsaetze([mit_anhang])
    assert satz == {"wert": "1,7", "prob_id": 11, "um_id": 42, "rohw_id": 7}
    lims_db.trdf_anhang_satz_pruefen(satz)


def test_ohne_anhangzeile_kein_anhangsatz():
    assert trdfexport.anhangsaetze([eine()]) == []
    # Und ohne Ergebniszeile wird auch am Anhang nichts geschrieben:
    # was das LIMS nicht kennt, wird gemeldet und nicht angelegt.
    verwaist = eine(zeile=None, anhang={"prob_id": 11, "um_id": 42,
                                        "rohw_id": 7, "mw": "1,8"})
    assert trdfexport.anhangsaetze([verwaist]) == []


def test_der_anhang_nennt_sich_eigens_im_protokoll():
    mit_anhang = eine(anhang={"prob_id": 11, "um_id": 42, "rohw_id": 7,
                              "mw": "1,8", "mw_old": None})
    satz, = trdfexport.anhanghinweise([mit_anhang], "2026B051")
    assert "Anhang" in satz and "1,8" in satz and "1,7" in satz


def test_der_satz_traegt_den_ganzen_schluessel_und_die_kennzeichen():
    satz = trdfexport.satz(eine())
    assert satz["wert"] == "1,7"
    assert satz["fc8"] == lims_db.TRDF_FC8 == "TRDF-Korrektur"
    assert satz["psta_id"] == lims_db.PSTA_GESENDET
    assert satz["korrektur_flag"] == lims_db.KORREKTUR_FLAG
    assert (satz["prob_id"], satz["pm_id"], satz["pm_ver"], satz["um_id"],
            satz["gegr_id"]) == (11, 1084, 1, 42, 7)
    lims_db.trdf_satz_pruefen(satz)          # und er kommt durch


def test_jeder_satz_nennt_sich_im_protokoll():
    satz, = trdfexport.hinweise([eine()], "2026B051")
    assert "2026B051" in satz and "26B0011" in satz
    assert "1,8" in satz and "1,7" in satz


# ------------------------------------------------------- Die Sicherung

def test_die_sicherung_haelt_den_stand_von_jetzt_fest():
    mit_anhang = eine(anhang={"prob_id": 11, "um_id": 42, "rohw_id": 7,
                              "mw": "1,8", "mw_old": "1,9"})
    zeile = dict(zip(trdfexport.SPALTEN_BACKUP,
                     trdfexport.backup_zeilen("2026B051", [mit_anhang])[0]))
    assert zeile["ROHW_ID"] == 7
    assert zeile["Anhang MW"] == "1,8" and zeile["Anhang MW_OLD"] == "1,9"
    assert zeile["Serie"] == "2026B051"
    assert zeile["PROB_ID"] == 11 and zeile["GEGR_ID"] == 7
    assert zeile["MW_ROH"] == "1,8" and zeile["MW"] == "1,8"
    assert zeile["PSTA_ID"] == 1
    assert zeile["Wert neu"] == "1,7"


def test_der_dateiname_traegt_serie_und_zeitpunkt():
    assert trdfexport.dateiname("2026B051", ZEITPUNKT) == \
        "2026B051 2026-09-08 103000.csv"


def test_zweimal_korrigieren_ueberschreibt_nicht_die_erste_sicherung():
    frueher = trdfexport.dateiname("2026B051", ZEITPUNKT)
    spaeter = trdfexport.dateiname("2026B051",
                                   ZEITPUNKT + dt.timedelta(minutes=1))
    assert frueher != spaeter


def test_ein_seltsamer_serienname_wird_zum_dateinamen_entschaerft():
    name = trdfexport.dateiname("2026/B..\\051", ZEITPUNKT)
    assert "/" not in name and "\\" not in name
    assert name.endswith(".csv")


def test_die_sicherung_landet_im_ordner_trdf_backup():
    with tempfile.TemporaryDirectory() as basis:
        ordner = os.path.join(basis, trdfexport.ORDNER)
        pfad = trdfexport.backup_schreiben(ordner, "2026B051", [eine()],
                                           ZEITPUNKT)
        assert os.path.basename(os.path.dirname(pfad)) == "trdf_backup"
        text = open(pfad, "rb").read().decode("cp1252", "replace")
        for stueck in ("PROB_ID", "26B0011", "1,8", "1,7"):
            assert stueck in text


def test_ohne_ordner_kommt_kein_pfad_zurueck():
    """Der Aufrufer bricht dann ab - ohne Sicherung wird nichts
    geschrieben."""
    with tempfile.TemporaryDirectory() as basis:
        sperre = os.path.join(basis, "keinordner")
        open(sperre, "w").close()
        assert trdfexport.backup_schreiben(os.path.join(sperre, "tiefer"),
                                           "2026B051", [eine()],
                                           ZEITPUNKT) == ""


def test_das_aenderungsblatt_zeigt_dieselben_zeilen_zum_lesen():
    with tempfile.TemporaryDirectory() as basis:
        pfad = trdfexport.blatt_schreiben(basis, "2026B051", [eine()],
                                          ZEITPUNKT)
        assert os.path.basename(pfad).startswith("Aenderungen ")
        text = open(pfad, "rb").read().decode("cp1252", "replace")
        assert "Wert aktuell LIMS" in text and "26B0011" in text


# --------------------------------------------------- Der Weg aus der Sicherung

def test_eine_sicherung_laesst_sich_wieder_einlesen():
    with tempfile.TemporaryDirectory() as ordner:
        mit_anhang = eine(anhang={"prob_id": 11, "um_id": 42, "rohw_id": 7,
                                  "mw": "1,8", "mw_old": "1,9"})
        pfad = trdfexport.backup_schreiben(ordner, "2026B051", [mit_anhang],
                                           ZEITPUNKT)
        zeilen = trdfexport.gesichertes_lesen(pfad)
        assert len(zeilen) == 1
        assert zeilen[0]["Probe-Nr."] == "26B0011"
        assert zeilen[0]["MW_ROH"] == "1,8" and zeilen[0]["Wert neu"] == "1,7"


def test_eine_fremde_datei_wird_abgewiesen():
    with tempfile.TemporaryDirectory() as ordner:
        pfad = os.path.join(ordner, "irgendwas.csv")
        with open(pfad, "w", encoding="utf-8") as datei:
            datei.write("a;b;c\n1;2;3\n")
        try:
            trdfexport.gesichertes_lesen(pfad)
        except trdfexport.Einlesefehler as fehler:
            assert "Sicherung" in str(fehler)
        else:
            raise AssertionError("Die fremde Datei kam durch")


def test_beim_zurueckspielen_tauschen_alt_und_neu_die_rollen():
    with tempfile.TemporaryDirectory() as ordner:
        mit_anhang = eine(anhang={"prob_id": 11, "um_id": 42, "rohw_id": 7,
                                  "mw": "1,8", "mw_old": "1,9"})
        pfad = trdfexport.backup_schreiben(ordner, "2026B051", [mit_anhang],
                                           ZEITPUNKT)
        zurueck, = trdfexport.zurueck(trdfexport.gesichertes_lesen(pfad))
        # Was damals geschrieben wurde, steht jetzt im LIMS ...
        assert zurueck["alt"] == "1,7"
        # ... und was damals dastand, soll wieder hinein.
        assert zurueck["neu"] == "1,8"
        assert zurueck["probe"] == "26B0011"
        assert zurueck["zeile"]["pm_id"] == 1084
        assert zurueck["anhang"]["rohw_id"] == 7


def test_der_zurueckgespielte_satz_traegt_den_ganzen_alten_stand():
    zeilen = [{"Probe-Nr.": "26B0011", "Groesse": "TRDFgesch", "PROB_ID": "11",
               "PM_ID": "1084", "PM_VER": "1", "UM_ID": "42", "GEGR_ID": "7",
               "MW_ROH": "1,8", "MW": "1,8", "PSTA_ID": "1",
               "KORREKTUR_FLAG": "", "FC8": "", "ROHW_ID": "7",
               "Anhang MW": "1,8", "Anhang MW_OLD": "1,9", "Wert neu": "1,7"}]
    aenderungen = trdfexport.zurueck(zeilen)
    satz, = trdfexport.zuruecksaetze(aenderungen)
    assert satz["wert"] == "1,8"
    assert satz["psta_id"] == 1 and satz["korrektur_flag"] == ""
    assert satz["fc8"] == ""            # auch FC8 war vorher leer
    lims_db.trdf_satz_pruefen(satz)
    am_anhang, = trdfexport.zurueck_anhangsaetze(aenderungen)
    assert am_anhang == {"wert": "1,8", "alt": "1,9", "prob_id": 11,
                         "um_id": 42, "rohw_id": 7}
    lims_db.trdf_anhang_zurueck_pruefen(am_anhang)


def test_eine_berechnete_groesse_hat_beim_zurueckspielen_keinen_anhang():
    zeilen = [{"Probe-Nr.": "26B0011", "Groesse": "TRD_TRDF", "PROB_ID": "11",
               "PM_ID": "1009", "PM_VER": "1", "UM_ID": "42", "GEGR_ID": "7",
               "MW_ROH": "1,8", "MW": "1,8", "PSTA_ID": "1",
               "KORREKTUR_FLAG": "F", "FC8": "TRDF-Korrektur", "ROHW_ID": "",
               "Anhang MW": "", "Anhang MW_OLD": "", "Wert neu": "1,7"}]
    aenderung, = trdfexport.zurueck(zeilen)
    assert aenderung["anhang"] is None
    assert aenderung["art"] == trdfexport.BERECHNET
    assert trdfexport.zurueck_anhangsaetze([aenderung]) == []
    satz, = trdfexport.zuruecksaetze([aenderung])
    assert satz["korrektur_flag"] == "F"      # der Stand von damals


def test_das_zurueckspielen_nennt_sich_im_protokoll():
    zeilen = [{"Probe-Nr.": "26B0011", "Groesse": "TRDFgesch",
               "PROB_ID": "11", "PM_ID": "1084", "PM_VER": "1",
               "UM_ID": "42", "GEGR_ID": "7", "MW_ROH": "1,8", "MW": "1,8",
               "PSTA_ID": "1", "KORREKTUR_FLAG": "", "FC8": "",
               "ROHW_ID": "7", "Anhang MW": "1,8", "Anhang MW_OLD": "",
               "Wert neu": "1,7"}]
    satz, = trdfexport.zurueckhinweise(trdfexport.zurueck(zeilen),
                                       "2026B051 2026-09-08 103000.csv")
    assert "zurueckgespielt" in satz and "26B0011" in satz


# --------------------------------------------- Die drei Staende des LIMS

def test_drei_staende_und_jeder_wird_geschrieben():
    """Eine Zahl, ein „x“ (hier soll nichts stehen) und eine leere
    Zelle - alle drei sind eine Aussage und gehen so in das LIMS."""
    assert trdfexport.wertfeld(D("1.7")) == "1,7"
    assert trdfexport.wertfeld(trdf.MARKE) == trdf.MARKE
    assert trdfexport.wertfeld("") == ""
    assert trdfexport.wertfeld(None) == ""
    # Ein Verweis sagt dasselbe wie ein x und wird auch so geschrieben.
    assert trdfexport.wertfeld("##1093") == trdf.MARKE


def test_die_anzeige_gibt_dem_nichts_einen_namen():
    assert trdfexport.anzeige(D("1.7")) == "1,7"
    assert trdfexport.anzeige("x") == trdf.MARKE
    assert trdfexport.anzeige("") == trdfexport.LEER_TEXT


def test_ein_x_ueber_ein_x_wird_nicht_geschrieben():
    """Es aendert nichts - und jede Zeile, die geschrieben wird, traegt
    danach ein Korrekturkennzeichen."""
    assert not trdfexport.bewegt("x", trdf.MARKE)
    assert not trdfexport.bewegt("##1093", trdf.MARKE)
    assert trdfexport.bewegt("2,3", trdf.MARKE)
    assert trdfexport.bewegt("", trdf.MARKE)


def test_geleert_wird_nur_wo_etwas_steht():
    assert trdfexport.bewegt("2,3", "")
    assert trdfexport.bewegt("x", "")
    assert not trdfexport.bewegt("", "")
    assert not trdfexport.bewegt(None, "")


def test_eine_zahl_bleibt_der_massstab():
    assert trdfexport.bewegt("2,3", D("2.9"))
    assert not trdfexport.bewegt("2,3", D("2.3"))
    assert trdfexport.bewegt("x", D("2.3"))


def test_x_und_leer_lassen_sich_zaehlen():
    """Die Uebersicht sagt vorher, wie viele Werte kein Messwert sind."""
    saetze = [eine(neu=trdf.MARKE), eine(neu=""), eine(neu=D("1.7"))]
    assert trdfexport.markiert(saetze) == [saetze[0]]
    assert trdfexport.geleert(saetze) == [saetze[1]]


def test_die_null_ist_ein_messwert_und_kein_nichts():
    """Sie kommt als Variante vor und als Skelettanteil - wer nach der
    Wahrheit des Wertes fragt statt nach seinem Feld, zaehlt sie als
    geleert und meldet es auch so."""
    null = eine(neu=D(0))
    assert trdfexport.geleert([null]) == []
    assert trdfexport.markiert([null]) == []
    assert trdfexport.satz(null)["wert"] == "0"
    assert trdfexport.anzeige(D(0)) == "0"


def test_der_satz_traegt_den_stand_so_wie_er_ist():
    assert trdfexport.satz(eine(neu=trdf.MARKE))["wert"] == trdf.MARKE
    assert trdfexport.satz(eine(neu=""))["wert"] == ""
    anhang = {"prob_id": 11, "um_id": 42, "rohw_id": 13}
    assert trdfexport.anhangsatz(
        eine(neu=trdf.MARKE, anhang=anhang))["wert"] == trdf.MARKE


# ------------------------------------------------ Die Stellen der Uebersicht

def test_die_uebersicht_rundet_wie_die_tabellen():
    """Fuenfzehn Ziffern liest niemand - in der Tabelle daneben stand
    die Zahl auch nicht so."""
    lang = eine(alt="1,63465373129843", neu=D("1.70123456789"))
    zeilen = trdfexport.uebersicht([lang], trdfpruefung.stellen_fuer)
    assert zeilen[0][-2:] == ["1,635", "1,701"]
    # Massen, Anteile und Vorraete tragen eine Stelle - wie im Blatt.
    grob = eine(kuerzel="FBVb", alt="2135,23456", neu=D("2440.44444"))
    zeilen = trdfexport.uebersicht([grob], trdfpruefung.stellen_fuer)
    assert zeilen[0][-2:] == ["2135,2", "2440,4"]


def test_ohne_angabe_bleibt_die_zahl_wie_sie_geschrieben_wird():
    """Die Datei ist der Nachweis - dort steht jede Stelle."""
    lang = eine(alt="1,63465373129843", neu=D("1.70123456789"))
    assert trdfexport.uebersicht([lang])[0][-2:] == ["1,63465373129843",
                                                     "1,70123456789"]


def test_eine_aenderung_verschwindet_nicht_im_runden():
    """Zweimal dieselbe Zahl in der Uebersicht, mit der jemand ein
    Ueberschreiben freigibt, waere die falsche Auskunft."""
    fein = eine(alt="1,6346537", neu=D("1.6346539"))
    zeilen = trdfexport.uebersicht([fein], trdfpruefung.stellen_fuer)
    assert zeilen[0][-2] != zeilen[0][-1]
    assert zeilen[0][-2:] == ["1,6346537", "1,6346539"]


def test_wo_nichts_stand_bleibt_die_marke_auch_gerundet():
    zeilen = trdfexport.uebersicht([eine(alt="x")], trdfpruefung.stellen_fuer)
    assert zeilen[0][-2] == trdf.MARKE


# --------------------------------------------- Was der Rueckweg leer laesst

def gesicherte_zeile(**rest) -> dict:
    """Eine Zeile, wie sie in der Sicherung steht."""
    zeile = {"Serie": "2026B051", "Probe-Nr.": "26B0011",
             "Groesse": "TRDFgesch", "PROB_ID": "11", "PM_ID": "1084",
             "PM_VER": "1", "UM_ID": "42", "GEGR_ID": "", "MW_ROH": "",
             "MW": "", "PSTA_ID": "", "KORREKTUR_FLAG": "", "FC8": "",
             "ROHW_ID": "", "Anhang MW": "", "Anhang MW_OLD": "",
             "Wert neu": "1,7"}
    zeile.update(rest)
    return zeile


def test_ein_leerer_stand_wird_beim_zurueckspielen_wieder_leer():
    """Vor der Korrektur stand dort nichts - danach wieder nichts."""
    geaendert = trdfexport.zurueck([gesicherte_zeile()])
    assert trdfexport.geleert(geaendert) == geaendert
    satz = trdfexport.zuruecksaetze(geaendert)[0]
    assert satz["wert"] == "" and satz["psta_id"] is None
    lims_db.trdf_zurueck_pruefen(satz)                 # wirft nicht


def test_die_uebersicht_zeigt_auch_das_leerwerden():
    """Eine leere Zelle laese sich als "hier geschieht nichts" - und ein
    „x“ waere die falsche Auskunft: das ist ein eigener Stand."""
    zeilen = trdfexport.uebersicht(trdfexport.zurueck([gesicherte_zeile()]))
    assert zeilen[0][-1] == trdfexport.LEER_TEXT
    assert zeilen[0][-2] == "1,7"


def test_eine_gefuellte_zeile_zaehlt_nicht_als_geleert():
    geaendert = trdfexport.zurueck([gesicherte_zeile(MW_ROH="1,8",
                                                     PSTA_ID="1")])
    assert trdfexport.geleert(geaendert) == []
    assert trdfexport.zuruecksaetze(geaendert)[0]["psta_id"] == 1


# ------------------------------------------------------- Der Exportbericht

def bericht_beispiel() -> list:
    """Zwei Proben, ein Rohwert und eine daraus gerechnete Groesse."""
    return [
        eine(),
        eine(kuerzel="TRDF", art=trdfexport.BERECHNET, alt="1,8",
             neu=D("1.7")),
        eine(probe={"lnr": 12, "probe": "26B0012"}, alt=None, neu=D("2.1")),
    ]


def test_der_bericht_stellt_eine_probe_in_eine_zeile():
    spalten, zeilen = trdfexport.bericht(bericht_beispiel())
    assert spalten[:2] == list(trdfexport.BERICHT_KOPF)
    assert [kennung for kennung, _ in zeilen] == ["26B0011", "26B0012"]
    assert zeilen[0][1]["Zeile"] == 11


def test_die_rohwerte_stehen_vor_dem_gerechneten():
    """Der Rohwert ist die Ursache, die berechnete Groesse die Folge."""
    spalten, _ = trdfexport.bericht(bericht_beispiel())
    assert spalten[2:] == ["TRDFgesch", "TRDF"]


def test_in_der_zelle_stehen_beide_werte():
    _, zeilen = trdfexport.bericht(bericht_beispiel())
    assert zeilen[0][1]["TRDFgesch"] == "1,8 → 1,7"


def test_wo_vorher_nichts_stand_sagt_es_der_bericht():
    _, zeilen = trdfexport.bericht(bericht_beispiel())
    assert zeilen[1][1]["TRDFgesch"] == f"{trdfexport.LEER_TEXT} → 2,1"


def test_was_eine_probe_nicht_hat_bleibt_leer():
    _, zeilen = trdfexport.bericht(bericht_beispiel())
    assert "TRDF" not in zeilen[1][1]


def test_ohne_aenderung_bleibt_der_bericht_leer():
    spalten, zeilen = trdfexport.bericht([])
    assert spalten == list(trdfexport.BERICHT_KOPF) and zeilen == []


def test_der_bericht_liegt_neben_der_sicherung():
    with tempfile.TemporaryDirectory() as ordner:
        pfad = trdfexport.bericht_schreiben(ordner, "2026B051",
                                            bericht_beispiel(), ZEITPUNKT)
        assert os.path.basename(pfad).startswith("Bericht 2026B051")
        text = open(pfad, "rb").read().decode("utf-8-sig")
        assert "TRDFgesch" in text and "1,8 → 1,7" in text
        assert "26B0012" in text


def test_ohne_ordner_wird_kein_bericht_geschrieben():
    """Wie ueberall: eine Datei, die nicht entstehen kann, meldet sich."""
    with tempfile.TemporaryDirectory() as ordner:
        sperre = os.path.join(ordner, "sperre")
        open(sperre, "w").close()          # eine Datei, kein Ordner
        assert trdfexport.bericht_schreiben(sperre, "2026B051",
                                            bericht_beispiel(),
                                            ZEITPUNKT) == ""


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
