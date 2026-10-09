"""Pruefungen fuer die Weboberflaeche - die Bruecke zwischen Svelte und Python.

Ohne Fenster und ohne Datenbank: `Api` wird so aufgerufen, wie die Seite
es ueber pywebview tut, im Demo-Betrieb mit der Beispielserie aus
test_trdfreiter. Was zurueckkommt, muss sich als JSON schicken lassen -
sonst kommt in JavaScript nichts an.
"""

from __future__ import annotations

import datetime as dt
import decimal
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request

os.environ.setdefault("TRDF_PRUEFMODUL_NICHT_OEFFNEN", "1")
os.environ["TRDF_DEMO_PROBEN"] = "12"

import config  # noqa: E402
import lims_db  # noqa: E402
import trdf  # noqa: E402
import test_trdfreiter  # noqa: E402
import trdfbild  # noqa: E402
import trdfblock  # noqa: E402
import trdfweb  # noqa: E402

D = decimal.Decimal


def api(demo=True) -> trdfweb.Api:
    ordner = tempfile.mkdtemp(prefix="trdfweb-pruefung-")
    sitzung = trdfweb.Websitzung(ordner=ordner,
                                 konfig=config.Config(runtime_dir=ordner))
    return trdfweb.Api(sitzung, demo=demo)


def geladen(demo=True) -> tuple:
    bruecke = api(demo)
    assert bruecke.anmelden("pruefer", "geheim")["ok"]
    methoden = bruecke.abfragen("2026B051")["methoden"]
    voll = bruecke.laden("2026B051", methoden[0]["um_id"])
    assert "fehler" not in voll, voll
    return bruecke, voll


def json_tauglich(antwort):
    text = json.dumps(antwort)
    assert text
    return json.loads(text)


def zeile(tafel, probe):
    return next(z for z in tafel["zeilen"] if z["id"] == probe)


# ---------------------------------------------------------------- Start

def test_start_sagt_was_die_anmeldung_braucht():
    antwort = json_tauglich(api().start())
    assert antwort["datenbanken"] == ["LIMS"]
    assert antwort["tnsnames"]["art"] == "text"
    assert antwort["angemeldet"] is False


def test_ohne_anmeldung_gibt_es_keine_serien():
    antwort = api(demo=False).serien()
    assert "anmelden" in antwort["fehler"]


def test_eine_falsche_anmeldung_kommt_als_text_zurueck():
    antwort = api(demo=False).anmelden("", "", "LIMS")
    assert antwort["ok"] is False
    assert antwort["fehler"]


def test_der_benutzer_wird_gemerkt_das_passwort_nie():
    bruecke = api()
    bruecke.anmelden("mustermann", "geheim")
    konfig = bruecke._s._einstellungen()
    assert konfig.get("benutzer") == "mustermann"
    assert "geheim" not in json.dumps(konfig.data if hasattr(konfig, "data")
                                      else vars(konfig), default=str)


# --------------------------------------------------------------- Laden

def test_abfragen_liefert_die_methoden_mit_eindeutigem_text():
    bruecke = api()
    bruecke.anmelden("pruefer", "x")
    antwort = json_tauglich(bruecke.abfragen("2026B051"))
    texte = [m["text"] for m in antwort["methoden"]]
    assert texte == ["TRDF3.2 (UM 42)", "TRDF3.2 (UM 207)"]
    assert antwort["stand"]["art"] == "warn"      # bitte eine waehlen


def test_laden_bringt_alle_drei_tabellen():
    _bruecke, voll = geladen()
    voll = json_tauglich(voll)
    tafeln = voll["tafeln"]
    assert len(tafeln["roh"]["zeilen"]) == 12
    assert len(tafeln["ergebnis"]["zeilen"]) == 12
    assert len(tafeln["pruefung"]["zeilen"]) == 12
    namen = [s["name"] for s in tafeln["roh"]["spalten"]]
    assert namen[:3] == ["Zeile", "Probe", "_TRDV"]
    aenderbar = {s["name"] for s in tafeln["roh"]["spalten"] if s["aenderbar"]}
    assert aenderbar == set(voll["rohliste"])
    assert "12 Proben" in voll["stand"]["text"]
    assert voll["auskunft"].startswith("TRDF3.2")
    assert voll["aenderungen"] == 0


def test_laden_ohne_abfragen_wird_abgewiesen():
    bruecke = api()
    bruecke.anmelden("pruefer", "x")
    assert "abfragen" in bruecke.laden("2026B051", 42)["fehler"]


def test_die_serie_wird_gemerkt():
    bruecke, _voll = geladen()
    assert bruecke._s._einstellungen().get("serie") == "2026B051"


def test_leere_rohwerte_werden_als_leer_gemeldet():
    """Die Seite zeigt x, braucht aber den Unterschied fuer Strg+L."""
    bruecke, voll = geladen()
    for z in voll["tafeln"]["roh"]["zeilen"]:
        for kuerzel in z["l"]:
            assert bruecke._s.ist_leer(z["id"], kuerzel)


# -------------------------------------------------------------- Aendern

def test_eine_eingabe_rechnet_nur_ihre_probe_neu():
    bruecke, voll = geladen()
    vorher = zeile(voll["tafeln"]["ergebnis"], "26B0005")
    antwort = json_tauglich(bruecke.setzen([["26B0005", "GMSZ", "850"]],
                                           "tippen", ["26B0005"]))
    assert [z["id"] for z in antwort["roh"]] == ["26B0005"]
    nachher = antwort["ergebnis"][0]
    assert nachher["w"] != vorher["w"]
    assert antwort["roh"][0]["m"]["GMSZ"] == "geaendert"
    assert antwort["roh"][0]["m"]["Probe"] == "geaendert"
    assert "geaendert" in nachher["m"].values()
    assert antwort["aenderungen"] > 0
    assert set(antwort["staende"]) == {"roh", "ergebnis", "pruefung"}
    # Der offene Block kommt mit seinem neuen Bild.
    assert antwort["bloecke"]["26B0005"]["probe"] == "26B0005"


def test_die_variante_raeumt_beim_tippen_auf():
    bruecke, _voll = geladen()
    antwort = bruecke.setzen([["26B0001", "_TRDV", "1"]], "tippen")
    assert "Variante 1" in antwort["meldung"]["text"]
    assert bruecke._s.vonhand[("26B0001", "_TRDV")] == "1"
    assert len([k for (p, k) in bruecke._s.vonhand if p == "26B0001"]) > 1


def test_ein_block_bringt_seine_werte_selbst_mit():
    bruecke, _voll = geladen()
    antwort = bruecke.setzen([["26B0001", "_TRDV", "1"],
                              ["26B0002", "_TRDV", "1"]], "block")
    assert antwort["meldung"]["text"] == "2 Werte eingefuegt"
    assert [k for (p, k) in bruecke._s.vonhand if p == "26B0001"] == ["_TRDV"]


def test_nach_unten_laesst_die_variante_wirken():
    bruecke, _voll = geladen()
    antwort = bruecke.setzen([["26B0002", "_TRDV", "1"],
                              ["26B0003", "_TRDV", "1"]], "nach_unten")
    assert "nach unten" in antwort["meldung"]["text"]
    assert len([k for (p, k) in bruecke._s.vonhand if p == "26B0003"]) > 1


def test_unbekannte_spalten_werden_nicht_gesetzt():
    bruecke, _voll = geladen()
    bruecke.setzen([["26B0001", "TRD_TRDF", "9"]], "tippen")
    assert not bruecke._s.vonhand


def test_leere_fuellen_ohne_leere_zelle_sagt_es():
    bruecke, _voll = geladen()
    spalte = bruecke._s.rohliste[-1]
    for _lnr, probe in bruecke._s.proben:
        bruecke._s.vonhand[(probe, spalte)] = "1"
    antwort = bruecke.leere_fuellen(None, spalte)
    assert "keine leere Zelle" in antwort["meldung"]["text"]


def test_leere_fuellen_setzt_x_nur_in_leere():
    bruecke, _voll = geladen()
    spalte = bruecke._s.rohliste[-1]
    probe = bruecke._s.proben[0][1]
    bruecke._s.vonhand[(probe, spalte)] = ""
    bruecke._s._rechnung_vergessen()
    antwort = bruecke.leere_fuellen(None, spalte)
    assert "gefuellt" in antwort["meldung"]["text"]
    assert bruecke._s.vonhand[(probe, spalte)] == "x"


# ---------------------------------------------------------- Eingefuegte UM

def test_eine_eingefuegte_um_wird_zur_quelle():
    bruecke, _voll = geladen()
    antwort = json_tauglich(bruecke.um_einfuegen(test_trdfreiter.UM_TEXT))
    assert antwort["ok"] is True
    assert antwort["quelle_um"] is True
    assert "eingefuegter UM" in antwort["quelle"]
    assert bruecke.um_text()["text"] == test_trdfreiter.UM_TEXT
    zurueck = bruecke.um_leeren()
    assert zurueck["quelle_um"] is False
    assert bruecke.um_text()["text"] == ""


def test_eine_kaputte_um_wird_abgewiesen():
    bruecke, _voll = geladen()
    antwort = bruecke.um_einfuegen("unsinn")
    assert antwort["ok"] is False
    assert antwort["stand"]["art"] == "fehler"


# ------------------------------------------------------- Block und Bild

def test_der_block_kommt_als_daten():
    bruecke, _voll = geladen()
    block = json_tauglich(bruecke.block("26B0003"))
    assert block["probe"] == "26B0003"
    assert block["stelle"] == 2 and block["anzahl"] == 12
    hoehen = sum(lage["hoehe"] for lage in block["lagen"])
    assert abs(hoehen - 1) < 1e-9 or not block["lagen"]
    assert bruecke.nachbar("26B0003", 1)["probe"] == "26B0004"
    assert bruecke.nachbar("26B0001", -1)["probe"] is None


def test_ein_fremder_block_wird_abgewiesen():
    bruecke, _voll = geladen()
    assert "gehoert nicht" in bruecke.block("99X0001")["fehler"]


def test_das_bild_traegt_baender_und_punkte():
    bruecke, _voll = geladen()
    daten = json_tauglich(bruecke.bild())
    assert daten["anzahl"] == 12
    assert daten["baender"] and daten["xmarken"] and daten["ymarken"]
    for punkt in daten["punkte"]:
        assert daten["links"] <= punkt["x"] <= daten["rechts"]
        assert daten["oben"] <= punkt["y"] <= daten["unten"]


def test_blockdaten_wie_im_fenster():
    roh = {"_TRDV": "4", "MSchaufel": "950", "DichteGB": "2,65",
           "GBM263Schaufel": "120", "GBMSchaufel": "30"}
    gerechnet = {"_SKA": D(25), "VOLGB63gs": D(10), "TRD_TRDF": D("1.2"),
                 "FBVb": D(1500), "FBMSchaufel": D(800)}
    daten = trdfblock.blockdaten("26B1", roh, gerechnet)
    assert [lage["marke"] for lage in daten["lagen"]] == [
        trdfblock.FEINBODEN, trdfblock.GROB_KLEIN, trdfblock.GROB_GROSS]
    assert daten["lagen"][0]["text"] == "75,0 %"
    assert daten["dichte"] == "1,200 g/cm³"
    marken = [lage["marke"] for lage in daten["schaufel"]]
    assert trdfblock.GROB_FEINST in marken and trdfblock.GROB_MITTEL in marken
    # Die Lage 2 bis 63 mm traegt eine Zahl, gezeichnet wird sie geteilt.
    nur_text = [lage for lage in daten["schaufel"] if lage.get("nur_text")]
    assert len(nur_text) == 1 and nur_text[0]["text"]


def test_ohne_masse_der_schaufelprobe_kein_schaufelbild():
    roh = {"_TRDV": "4", "DichteGB": "2,65", "GBM263Schaufel": "120"}
    gerechnet = {"_SKA": D(25), "TRD_TRDF": D("1.2"), "FBMSchaufel": D(800)}
    for masse in (None, "", "x", "0", "0,0"):
        if masse is not None:
            roh["MSchaufel"] = masse
        daten = trdfblock.blockdaten("26B1", roh, gerechnet)
        assert daten["schaufel"] == [] and daten["schaufellegende"] == [], masse
    roh["MSchaufel"] = "950"
    assert trdfblock.blockdaten("26B1", roh, gerechnet)["schaufel"]


def test_die_legende_traegt_text_und_prozent_getrennt():
    roh = {"_TRDV": "4", "MSchaufel": "950", "DichteGB": "2,65",
           "GBM263Schaufel": "120"}
    gerechnet = {"_SKA": D(25), "VOLGB63gs": D(10), "TRD_TRDF": D("1.2"),
                 "FBMSchaufel": D(800)}
    daten = trdfblock.blockdaten("26B1", roh, gerechnet)
    for eintrag in daten["legende"] + daten["schaufellegende"]:
        assert eintrag["wert"].endswith("%")
        assert "%" not in eintrag["text"]
    assert daten["legende"][0] == {"marke": "fein",
                                   "farbe": trdfblock.FARBEN["fein"],
                                   "text": "Feinboden", "wert": "75,0 %"}


def test_proben_mit_variante_x_sind_gekennzeichnet():
    """Die Seite blendet sie auf Wunsch aus - geschrieben wird trotzdem."""
    bruecke, voll = geladen()
    assert not any(z["x"] for z in voll["tafeln"]["roh"]["zeilen"])
    antwort = bruecke.setzen([["26B0003", "_TRDV", "x"]], "tippen")
    assert antwort["roh"][0]["x"] is True
    assert antwort["ergebnis"][0]["x"] is True
    assert antwort["pruefung"][0]["x"] is True
    # Was sich dabei bewegt hat, steht in der Uebersicht vor dem Export.
    vorschau = bruecke.export_vorschau()["vorschau"]
    assert any(zeile[1] == "26B0003" for zeile in vorschau["zeilen"])


def test_bild_ohne_aufschluss_steht_am_rand():
    daten = trdfbild.bild([{"probe": "1", "trdf": D("1.2"), "cges": None,
                            "co3": None}])
    punkt = daten["punkte"][0]
    assert punkt["farbe"] == trdfbild.FARBE_OHNE_AUFSCHLUSS
    assert abs(punkt["x"] - daten["links"]) < 1e-9


# --------------------------------------------------------------- Export

def test_export_erst_nach_vorschau_und_mit_sicherung():
    bruecke, _voll = geladen()
    assert "nichts von Hand" in bruecke.export_vorschau()["stand"]["text"]
    bruecke.setzen([["26B0005", "GMSZ", "850"]], "tippen")
    vorschau = json_tauglich(bruecke.export_vorschau())["vorschau"]
    assert vorschau["anzahl"] == len(vorschau["zeilen"]) > 0
    assert vorschau["knopf"] == "Sichern und schreiben"
    assert "trdf_backup" in vorschau["hinweis"]
    voll = json_tauglich(bruecke.vorschau_ausfuehren())
    assert voll["meldung"]["titel"] == "In das LIMS geschrieben"
    assert voll["aenderungen"] == 0              # ist jetzt LIMS-Stand
    assert voll["reiter"] == "bericht"
    assert voll["bericht"]["zeilen"]
    sicherung = bruecke._s.letzter_export["sicherung"]
    assert os.path.isfile(sicherung)


def test_ohne_vorschau_wird_nichts_geschrieben():
    bruecke, _voll = geladen()
    assert "Uebersicht" in bruecke.vorschau_ausfuehren()["fehler"]


def test_ein_update_ohne_wirkung_wird_gemeldet():
    bruecke, _voll = geladen()
    bruecke.setzen([["26B0005", "GMSZ", "850"]], "tippen")
    bruecke.export_vorschau()
    echt = trdfweb.demo_schreiben

    def bleibt(saetze, *rest, **kwargs):
        bericht = echt(saetze, *rest, **kwargs)
        bericht["nicht_uebernommen"] = list(saetze)
        return bericht

    trdfweb.demo_schreiben = bleibt
    try:
        voll = bruecke.vorschau_ausfuehren()
    finally:
        trdfweb.demo_schreiben = echt
    assert voll["meldung"]["titel"] == "Update fehlgeschlagen"
    assert voll["stand"]["art"] == "fehler"
    assert voll["aenderungen"] > 0               # der Stand bleibt


def test_ohne_datenbank_echter_zugang_geht_ueber_lims_db():
    """Ohne Demo schreibt die Bruecke ueber lims_db.trdf_exportieren."""
    bruecke, _voll = geladen()
    bruecke._demo = False
    bruecke.setzen([["26B0005", "GMSZ", "850"]], "tippen")
    bruecke.export_vorschau()
    gerufen = []
    echt = lims_db.trdf_exportieren

    def ersatz(zugang, *args, **kwargs):
        gerufen.append(kwargs)
        return trdfweb.demo_schreiben(*args, **kwargs)

    lims_db.trdf_exportieren = ersatz
    try:
        voll = bruecke.vorschau_ausfuehren()
    finally:
        lims_db.trdf_exportieren = echt
    assert gerufen and gerufen[0].get("leeren") is True
    assert voll["meldung"]["titel"] == "In das LIMS geschrieben"


def test_load_backup_spielt_den_alten_stand_zurueck():
    bruecke, _voll = geladen()
    bruecke.setzen([["26B0005", "GMSZ", "850"]], "tippen")
    bruecke.export_vorschau()
    bruecke.vorschau_ausfuehren()
    pfad = bruecke._s.letzter_export["sicherung"]
    liste = bruecke.sicherungen()
    assert pfad in liste["dateien"]
    vorschau = bruecke.backup_lesen(pfad)["vorschau"]
    assert vorschau["art"] == "zurueck"
    assert vorschau["knopf"] == "Zurueckspielen"
    voll = bruecke.vorschau_ausfuehren()
    assert voll["meldung"]["titel"] == "Sicherung zurueckgespielt"
    assert "zurueckgespielt" in voll["bericht"]["stand"]["text"]


def test_eine_kaputte_sicherung_wird_gemeldet():
    bruecke, _voll = geladen()
    pfad = os.path.join(tempfile.mkdtemp(), "kaputt.csv")
    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write("das ist keine Sicherung\n")
    antwort = bruecke.backup_lesen(pfad)
    assert antwort["stand"]["art"] == "fehler"


def test_anhang_angleichen_ohne_unterschied():
    bruecke, _voll = geladen()
    antwort = bruecke.anhang_vorschau()
    assert "stimmen" in antwort["stand"]["text"] or "vorschau" in antwort


# ------------------------------------------------------------ Blaetter

def test_alle_blaetter_als_csv():
    bruecke, _voll = geladen()
    assert bruecke.csv("aenderungen")["stand"]["art"] == "warn"
    for blatt in ("roh", "ergebnis", "pruefung"):
        antwort = bruecke.csv(blatt)
        assert os.path.isfile(antwort["pfad"]), blatt
    bruecke.setzen([["26B0005", "GMSZ", "850"]], "tippen")
    assert os.path.isfile(bruecke.csv("aenderungen")["pfad"])
    bruecke.export_vorschau()
    bruecke.vorschau_ausfuehren()
    assert os.path.isfile(bruecke.csv("bericht")["pfad"])


def test_das_ergebnisblatt_traegt_die_koepfe_der_tabelle():
    bruecke, _voll = geladen()
    pfad = bruecke.csv("ergebnis")["pfad"]
    with open(pfad, encoding="utf-8-sig") as datei:
        text = datei.read()
    assert "Berechnete Groessen - Serie 2026B051" in text
    assert "TRD_TRDF ber." in text


# ------------------------------------------------------------- Legende

def test_legende_lesen_und_speichern():
    bruecke, _voll = geladen()
    legende = json_tauglich(bruecke.legende("roh"))
    assert legende["zeilen"][0][0] == "Zeile"
    ordnung = legende["ordnung"]
    reihenfolge = [legende["schluessel"][z[0]] for z in legende["zeilen"]]
    reihenfolge.reverse()
    voll = bruecke.legende_speichern(
        "roh", {"GMSZ": "Masse Zylinder"},
        {**ordnung, "reihenfolge": reihenfolge, "versteckt": ["MMini"]})
    assert "fehler" not in voll
    namen = [s["name"] for s in voll["tafeln"]["roh"]["spalten"]]
    assert "MMini" not in namen
    assert bruecke._s.beschreibungen()["GMSZ"] == "Masse Zylinder"


def test_eine_spalte_am_kopf_verschieben():
    bruecke, voll = geladen()
    namen = [s["name"] for s in voll["tafeln"]["roh"]["spalten"]]
    assert namen.index("VOLSZ") < namen.index("GMSZ")
    antwort = bruecke.spalte_verschieben("roh", "VOLSZ", "GMSZ")
    namen = [s["name"] for s in antwort["tafeln"]["roh"]["spalten"]]
    assert namen.index("VOLSZ") == namen.index("GMSZ") + 1
    # und es bleibt so - auch nach dem naechsten Abruf
    assert bruecke._s.spaltenordnung("Rohwerte")[0].index("VOLSZ") > \
        bruecke._s.spaltenordnung("Rohwerte")[0].index("GMSZ")


def test_ein_paar_wandert_zusammen_und_feste_bleiben():
    bruecke, voll = geladen()
    antwort = bruecke.spalte_verschieben("ergebnis", "TRD_TRDF ber.",
                                         "FBMSZ LIMS")
    namen = [s["name"] for s in antwort["tafeln"]["ergebnis"]["spalten"]]
    assert namen.index("TRD_TRDF LIMS") + 1 == namen.index("TRD_TRDF ber.")
    assert namen.index("TRD_TRDF ber.") < namen.index("FBMSZ LIMS")
    antwort = bruecke.spalte_verschieben("roh", "Probe", "GMSZ")
    assert antwort["stand"]["art"] == "warn"


def test_ergebnisse_angleichen_ueber_die_bruecke():
    bruecke, _voll = geladen()
    s = bruecke._s
    probe = s.proben[0][1]
    for kuerzel in s.folge:
        s.gebucht.setdefault(probe, {})[kuerzel] = None
    s._rechnung_vergessen()
    vorschau = json_tauglich(bruecke.ergebnisse_vorschau())["vorschau"]
    assert vorschau["art"] == "ergebnisse"
    assert vorschau["knopf"] == "Angleichen"
    assert "berechneten Groessen" in vorschau["hinweis"]
    voll = bruecke.vorschau_ausfuehren()
    assert voll["meldung"]["titel"] == "In das LIMS geschrieben"
    assert os.path.isfile(bruecke._s.letzter_export["sicherung"])
    assert bruecke.ergebnisse_vorschau()["stand"]["text"].startswith(
        "Die Ergebnisse im LIMS stimmen")


def test_ergebnisse_angleichen_erst_nach_dem_export_der_handwerte():
    bruecke, _voll = geladen()
    bruecke.setzen([["26B0005", "GMSZ", "850"]], "tippen")
    antwort = bruecke.ergebnisse_vorschau()
    assert "zuerst" in antwort["stand"]["text"]


def test_ein_grosses_x_wird_beim_setzen_klein():
    bruecke, _voll = geladen()
    antwort = bruecke.setzen([["26B0005", "GMSZ", "X"]], "tippen")
    assert bruecke._s.vonhand[("26B0005", "GMSZ")] == "x"
    assert antwort["roh"][0]["w"]["GMSZ"] == "x"



def test_anhang_angleichen_macht_ein_grosses_x_ueberall_klein():
    """Ueber die Bruecke: X am Anhang und in der Ergebniszeile werden in
    einem Zug ein x - mit Sicherung."""
    bruecke, _voll = geladen()
    s = bruecke._s
    probe = s.proben[0][1]
    kuerzel = next(k for k in s.rohliste
                   if trdf.zahl(s.limsroh[probe].get(k)) is None
                   and (probe, k) in s.anhang)
    s.limsroh[probe][kuerzel] = "X"
    s.anhang[(probe, kuerzel)]["mw"] = "X"
    gesehen = {}
    echt = trdfweb.demo_schreiben

    def merken(saetze, hinweise=None, anhang=None, anhang_hinweise=None,
               **rest):
        gesehen["saetze"], gesehen["anhang"] = list(saetze), list(anhang or [])
        return echt(saetze, hinweise, anhang, anhang_hinweise, **rest)

    vorschau = bruecke.anhang_vorschau()["vorschau"]
    assert "Ergebniszeile" in vorschau["hinweis"]
    trdfweb.demo_schreiben = merken
    try:
        voll = bruecke.vorschau_ausfuehren()
    finally:
        trdfweb.demo_schreiben = echt
    assert voll["meldung"]["titel"] == "Teilprobenanhang angeglichen"
    assert any(satz["wert"] == "x" for satz in gesehen["saetze"])
    assert any(satz["wert"] == "x" for satz in gesehen["anhang"])

def test_nur_bekannte_einstellungen():
    bruecke = api()
    assert bruecke.einstellung("trdf_berechnete", "an")["ok"]
    assert bruecke.start()["auto_angleichen"] is True     # von Haus aus an
    assert bruecke.einstellung("trdf_auto_angleichen", "aus")["ok"]
    assert bruecke.start()["auto_angleichen"] is False
    assert "Unbekannte" in bruecke.einstellung("passwort", "x")["fehler"]


# ------------------------------------------------------------ Allgemein

def test_klar_macht_alles_json_tauglich():
    wert = trdfweb.klar({"a": D("1.50"), "b": (1, 2), "c": dt.date(2026, 1, 2),
                         "d": {D(1)}, "e": None})
    assert wert == {"a": "1,5", "b": [1, 2], "c": "02.01.2026", "d": ["1"],
                    "e": None}


def test_fehler_kommen_als_text_und_nicht_als_ausnahme():
    bruecke = api()
    antwort = bruecke.csv("unbekannt")
    assert "fehler" in antwort or antwort["stand"]["art"] == "warn"


def test_die_weboberflaeche_braucht_kein_tkinter():
    """Die Web-exe packt tkinter nicht mit - also darf nichts es laden."""
    fertig = subprocess.run(
        [sys.executable, "-c",
         "import sys, trdfweb, trdfmodell, trdfblock, trdflegende, trdfbild;"
         "print('tkinter' in sys.modules)"],
        capture_output=True, text=True, timeout=60,
        cwd=os.path.dirname(os.path.abspath(__file__)))
    assert fertig.stdout.strip() == "False", fertig.stdout + fertig.stderr


def test_die_tk_fenster_sind_unter_altem_namen_da():
    import trdfblockfenster
    assert trdfblock.Blockfenster is trdfblockfenster.Blockfenster
    assert trdfbild.Streubild.__name__ == "Streubild"


def test_der_dienst_beantwortet_aufrufe():
    bruecke = api()
    port_holen = threading.Event()
    gefunden = {}

    def starten():
        import socket
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            gefunden["port"] = probe.getsockname()[1]
        port_holen.set()
        trdfweb.dienst(bruecke, gefunden["port"])

    threading.Thread(target=starten, daemon=True).start()
    port_holen.wait(5)
    adresse = f"http://127.0.0.1:{gefunden['port']}/api/start"
    for _ in range(50):
        try:
            anfrage = urllib.request.Request(adresse, data=b"[]",
                                             method="POST")
            with urllib.request.urlopen(anfrage, timeout=2) as antwort:
                daten = json.loads(antwort.read())
            break
        except OSError:
            import time
            time.sleep(0.1)
    else:
        raise AssertionError("Der Dienst antwortet nicht")
    assert daten["datenbanken"] == ["LIMS"]
    # Woran die Seite den Dienst erkennt - im Programm gibt es das nicht.
    with urllib.request.urlopen(
            f"http://127.0.0.1:{gefunden['port']}/api/bereit",
            timeout=2) as antwort:
        assert json.loads(antwort.read()) == {"dienst": True}
    anfrage = urllib.request.Request(
        f"http://127.0.0.1:{gefunden['port']}/api/_s", data=b"[]",
        method="POST")
    try:
        urllib.request.urlopen(anfrage, timeout=2)
        raise AssertionError("Private Namen duerfen nicht erreichbar sein")
    except urllib.error.HTTPError as fehler:
        assert fehler.code == 404


def test_selbsttest_prueft_webview_und_die_seite():
    code, zeilen = lims_db.selbsttest(oberflaeche=("json",))
    assert "  json vorhanden" in zeilen
    code, zeilen = lims_db.selbsttest(oberflaeche=("gibt_es_nicht_xyz",))
    assert code == 1


def _gefundene_module(datei: str) -> set:
    """Was ein Startpunkt statisch nach sich zieht - wie PyInstaller."""
    import modulefinder
    ordner = os.path.dirname(os.path.abspath(__file__))
    finder = modulefinder.ModuleFinder(path=[ordner] + sys.path,
                                       excludes=["oracledb", "webview"])
    finder.run_script(os.path.join(ordner, datei))
    return set(finder.modules)


def test_die_tk_exe_packt_ihre_fenster_mit():
    """Die Tk-Fenster werden in trdfblock & Co. nur verzoegert geladen -
    die Tk-Seite muss sie deshalb selbst importieren, sonst fehlen sie in
    der exe (\"No module named 'trdflegendefenster'\")."""
    module = _gefundene_module("trdfpruefmodul.py")
    for name in ("trdfblockfenster", "trdflegendefenster", "trdfbildfenster"):
        assert name in module, name


def test_die_web_exe_packt_keine_tk_seite():
    module = _gefundene_module("trdfweb.py")
    for name in ("trdfreiter", "eingaberaster", "trdflegendefenster",
                 "test_trdfreiter"):
        assert name not in module, name


def test_die_seite_unterscheidet_bruecke_und_dienst():
    """pywebview liefert die Seite ueber http aus - "http" allein darf
    nicht heissen, dass ueber den Entwicklungsdienst gerufen wird."""
    ordner = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(ordner, "web", "src", "lib", "api.js"),
              encoding="utf-8") as datei:
        text = datei.read()
    assert "pywebviewready" in text
    assert "/api/bereit" in text


def test_start_meldet_die_verbindung_im_protokoll():
    import logging
    gesehen = []

    class Sammler(logging.Handler):
        def emit(self, record):
            gesehen.append(record.getMessage())

    logger = logging.getLogger("trdfweb")
    sammler = Sammler()
    logger.addHandler(sammler)
    logger.setLevel(logging.INFO)
    try:
        api().start()
    finally:
        logger.removeHandler(sammler)
    assert trdfweb.SEITE_VERBUNDEN in gesehen


def test_das_fenstersymbol_ist_unter_windows_eine_ico():
    """WinForms nimmt kein PNG - die exe beendete sich sonst sofort."""
    assert trdfweb.SYMBOL_WINDOWS.endswith(".ico")
    assert os.path.isfile(trdfweb.ressource(trdfweb.SYMBOL_WINDOWS))


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
    sys.exit(main())
