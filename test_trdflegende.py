"""Prueft die Legende des TRDF-Moduls - ohne Datenbank.

Die Legende beantwortet die Frage, die vor jeder Tabelle des Moduls
steht: was heisst „_TSM“? Sie darf dabei nichts erfinden - eine falsche
Einheit in der Legende ist schlimmer als gar keine, weil ihr geglaubt
wird. Deshalb steht hier, was aus den Stammdaten kommt, was aus dem
Abruf und was offen bleibt.

Aufruf:  python test_trdflegende.py
"""

from __future__ import annotations

import tkinter as tk

import trdf
import trdflegende
import trdfpruefung


def mit_fenster(pruefung):
    fenster = tk.Tk()
    fenster.withdraw()
    try:
        pruefung(fenster)
    finally:
        fenster.destroy()


# ------------------------------------------------------- Die Stammdaten

def test_beide_kuerzelsysteme_decken_sich():
    """Die Laborliste in trdf und die Rohwertparameter hier sind
    dieselbe Auskunft - gehen sie auseinander, schreibt der Rueckweg in
    die falsche Zeile."""
    assert set(trdflegende.NACH_ROHKUERZEL) == set(trdf.ZUORDNUNG)
    for kurz, lang in trdf.ZUORDNUNG.items():
        assert lang in trdflegende.NACH_KUERZEL, (kurz, lang)


def test_die_zweite_trockenrohdichte_steht_daneben():
    """Seit dem 1.9.2026 fuehrt das Labor zwei: TRDF_Old rechnet weiter
    nach der bisherigen Formel. Beide schreiben auf denselben Parameter,
    und die Legende muss sie trotzdem auseinanderhalten."""
    assert "TRDF_Old" in trdflegende.NACH_KUERZEL
    name, zeichen, einheit, format_ = trdflegende.NACH_KUERZEL["TRDF_Old"]
    assert "alte Formel" in name
    assert (zeichen, einheit, format_) == ("TRDF", "g/cm3", "Dec03")
    hinweis = trdflegende.hinweis("TRDF_Old ber.")
    assert "alte Formel" in hinweis and "g/cm3" in hinweis


def test_jede_groesse_traegt_name_und_einheit():
    for kuerzel, name, zeichen, einheit, format_ in trdflegende.METHODEN:
        assert name and zeichen and einheit and format_, kuerzel


# ---------------------------------------------------------- Die Legende

def test_aus_dem_kuerzel_wird_ein_name():
    zeilen = trdflegende.rohlegende(["_TSM"])
    assert zeilen[0][:5] == ["_TSM", "Tiefenstufenmächtigkeit", "d", "cm",
                             "M"]


def test_die_rohwerte_zeigen_beide_kuerzel():
    """Am Teilprobenanhang steht das kurze - wer dort nachsieht,
    braucht es."""
    zeilen = trdflegende.rohlegende(["DichteGB"])
    assert zeilen[0][2] == "DGB" and zeilen[0][4] == "D"


def test_die_ergebnisspalten_sagen_woher_der_wert_kommt():
    zeilen = trdflegende.ergebnislegende(["TRD_TRDF LIMS", "TRD_TRDF ber."])
    assert "wie im LIMS gebucht" in zeilen[0][1]
    assert "gerechnet" in zeilen[1][1]
    assert zeilen[0][2] == "g/cm3" and zeilen[0][3] == "TRD_TRDF"


def test_die_pruefung_findet_ihre_ueberschriften_wieder():
    """Im Blatt heisst die Spalte "SKAgs63" - die Formel „_SKASgs“."""
    zeilen = trdflegende.pruefungslegende(list(trdfpruefung.SPALTEN),
                                          trdfpruefung.QUELLEN)
    nach_spalte = {zeile[0]: zeile for zeile in zeilen}
    assert nach_spalte["SKAgs63"][3] == "_SKASgs"
    assert nach_spalte["TRDF"][3] == "TRD_TRDF"
    assert nach_spalte["FBVorrat"][2] == "t/ha"


def test_die_fuehrenden_spalten_werden_auch_erklaert():
    zeilen = trdflegende.rohlegende(["Zeile", "Probe"])
    assert "LNR" in zeilen[0][1] and zeilen[1][1] == "Probennummer"


def test_was_die_stammdaten_nicht_kennen_kommt_aus_dem_abruf():
    methoden = [{"formelkuerzel": "NEU", "name": "Etwas Neues"}]
    zeilen = trdflegende.ergebnislegende(["NEU"], methoden)
    assert zeilen[0][1] == "Etwas Neues"
    assert zeilen[0][2] == trdflegende.UNBEKANNT      # keine Einheit erfunden


def test_eine_ganz_unbekannte_spalte_faellt_nicht_unter_den_tisch():
    zeilen = trdflegende.ergebnislegende(["XYZ"])
    assert zeilen[0][0] == "XYZ" and zeilen[0][1] == trdflegende.UNBEKANNT


# ------------------------------------------------------ Die Beschreibung

def test_die_beschreibung_haengt_am_formelkuerzel():
    """Einmal geschrieben, steht sie in allen drei Legenden."""
    texte = {"TRD_TRDF": "Bezugsgroesse fuer den Vorrat"}
    roh = trdflegende.rohlegende(["TRD_TRDF"], beschreibungen=texte)
    erg = trdflegende.ergebnislegende(["TRD_TRDF ber."], beschreibungen=texte)
    pru = trdflegende.pruefungslegende(["TRDF"], trdfpruefung.QUELLEN,
                                       beschreibungen=texte)
    assert roh[0][-1] == erg[0][-1] == pru[0][-1] == texte["TRD_TRDF"]


def test_ohne_beschreibung_bleibt_die_spalte_leer():
    for zeile in trdflegende.rohlegende(["_TSM", "Zeile"]):
        assert zeile[-1] == ""


def test_jede_zeile_ist_so_lang_wie_ihr_kopf():
    lang = trdflegende.rohlegende(["Zeile", "_TSM", "WGH"])
    assert all(len(zeile) == len(trdflegende.SPALTEN_ROH) for zeile in lang)
    kurz = trdflegende.pruefungslegende(list(trdfpruefung.SPALTEN),
                                        trdfpruefung.QUELLEN)
    assert all(len(zeile) == len(trdflegende.SPALTEN_ERGEBNIS)
               for zeile in kurz)


# ---------------------------------------------------------- Das Fenster

def test_das_fenster_zeigt_die_legende_und_gibt_sie_zurueck():
    def pruefen(fenster):
        zeilen = trdflegende.rohlegende(["_TSM", "DichteGB"])
        gemerkt = {}
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH), zeilen,
            speichern=lambda texte, ordnung: gemerkt.update(texte) or "",
            schluessel={"_TSM": "_TSM", "DichteGB": "DichteGB"})
        legende.tabelle._setzen("_TSM", trdflegende.BESCHREIBUNG,
                               "Maechtigkeit der Tiefenstufe")
        legende._sichern()
        assert gemerkt == {"_TSM": "Maechtigkeit der Tiefenstufe",
                           "DichteGB": ""}
        assert "1 Beschreibungen" in legende.stand.cget("text")
    mit_fenster(pruefen)


def test_dieselbe_groesse_zweimal_nimmt_die_bewegte_zeile():
    """"TRDF LIMS" und "TRDF ber." sind dieselbe Groesse. Wer eine der
    beiden Zeilen aendert, will nicht, dass die andere den alten Stand
    zurueckschreibt."""
    def pruefen(fenster):
        zeilen = trdflegende.ergebnislegende(
            ["TRD_TRDF LIMS", "TRD_TRDF ber."],
            beschreibungen={"TRD_TRDF": "alt"})
        legende = trdflegende.Legendenfenster(
            fenster, "Ergebnisse", list(trdflegende.SPALTEN_ERGEBNIS),
            zeilen, schluessel={"TRD_TRDF LIMS": "TRD_TRDF",
                                "TRD_TRDF ber.": "TRD_TRDF"})
        legende.tabelle._setzen("TRD_TRDF ber.", trdflegende.BESCHREIBUNG,
                               "neu")
        assert legende.texte() == {"TRD_TRDF": "neu"}
    mit_fenster(pruefen)


def test_ein_gescheitertes_speichern_wird_gesagt():
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["_TSM"]),
            speichern=lambda texte, ordnung: "kein Schreibrecht")
        legende._sichern()
        assert "kein Schreibrecht" in legende.stand.cget("text")
    mit_fenster(pruefen)


# ------------------------------------------------ Die Reihenfolge

def test_feste_spalten_stehen_vorn():
    """Nur links laesst sich etwas festhalten - also gehen sie nach vorn."""
    spalten = ["Zeile", "Probe", "_TSM", "_TRDV", "DichteGB"]
    sortiert, fest = trdflegende.geordnet(
        spalten, lambda name: name, fest=("Zeile", "Probe", "_TRDV"))
    assert sortiert[:3] == ["Zeile", "Probe", "_TRDV"]
    assert fest == ["Zeile", "Probe", "_TRDV"]
    assert sortiert[3:] == ["_TSM", "DichteGB"]


def test_ein_spaltenpaar_wandert_zusammen():
    """"TRDF LIMS" und "TRDF ber." zeigen dieselbe Groesse."""
    spalten = ["Zeile", "A LIMS", "A ber.", "TRDF LIMS", "TRDF ber."]
    sortiert, _fest = trdflegende.geordnet(
        spalten, lambda name: trdflegende.zerlegen(name)[0],
        reihenfolge=["TRDF", "Zeile", "A"])
    assert sortiert == ["TRDF LIMS", "TRDF ber.", "Zeile", "A LIMS",
                        "A ber."]


def test_was_die_reihenfolge_nicht_kennt_bleibt_am_ende():
    """Eine neue Pruefmethode darf nicht verschwinden."""
    sortiert, _fest = trdflegende.geordnet(
        ["A", "B", "NEU"], lambda name: name, reihenfolge=["B", "A"])
    assert sortiert == ["B", "A", "NEU"]


# --------------------------------------------- Die Wahl der Ueberschrift

def test_von_haus_aus_steht_das_formelkuerzel_oben():
    assert trdflegende.ueberschrift("_TSM", "Spalte") == "_TSM"
    assert trdflegende.ueberschrift("_TSM", "") == "_TSM"


def test_die_ueberschrift_kann_den_namen_zeigen():
    assert trdflegende.ueberschrift("_TSM", "Name") == \
        "Tiefenstufenmächtigkeit"
    assert trdflegende.ueberschrift("_TSM", "Kuerzel") == "TSM"
    assert trdflegende.ueberschrift("_TSM", "Einheit") == "cm"


def test_die_rohwerte_nehmen_den_namen_des_rohwertparameters():
    """Dort heisst die Groesse anders - und so nennt sie das Labor."""
    assert trdflegende.ueberschrift("DichteGB", "Name", roh=True) == \
        "DichteGrobboden"
    assert trdflegende.ueberschrift("DichteGB", "Name") == "Grobbodendichte"


def test_das_paar_behaelt_seinen_zusatz():
    assert trdflegende.ueberschrift("_TSM ber.", "Kuerzel") == "TSM ber."


def test_die_eigene_beschreibung_darf_oben_stehen():
    assert trdflegende.ueberschrift(
        "_TSM", "Beschreibung",
        beschreibungen={"_TSM": "Maechtigkeit"}) == "Maechtigkeit"
    # Wo keine steht, bleibt es beim Kuerzel - eine leere Ueberschrift
    # waere schlimmer als eine kryptische.
    assert trdflegende.ueberschrift("_TSM", "Beschreibung") == "_TSM"


def test_die_fuehrenden_spalten_heissen_immer_gleich():
    assert trdflegende.ueberschrift("Probe", "Name") == "Probe"
    assert trdflegende.ueberschriften(["Zeile", "_TSM"], "Kuerzel") == \
        {"Zeile": "Zeile", "_TSM": "TSM"}


def test_das_pruefblatt_findet_sein_kuerzel_ueber_die_quelle():
    assert trdflegende.ueberschrift("TRDF", "Name",
                                    quellen={"TRDF": "TRD_TRDF"}) == \
        "TrockenrohdichteFeinboden"


# ------------------------------------------------ Das Fenster kann beides

def test_im_fenster_laesst_sich_eine_spalte_festnageln():
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM"]),
            ordnung={"fest": ["Zeile", "Probe"]})
        try:
            assert legende.tabelle.wert("Zeile", trdflegende.FEST) == \
                trdflegende.JA
            assert legende.tabelle.wert("_TSM", trdflegende.FEST) == \
                trdflegende.NEIN
            legende._geklickt("_TSM", trdflegende.FEST)
            assert legende.tabelle.wert("_TSM", trdflegende.FEST) == \
                trdflegende.JA
            assert legende.ordnung()["fest"] == ["Zeile", "Probe", "_TSM"]
            # Und wieder los.
            legende._geklickt("_TSM", trdflegende.FEST)
            assert legende.ordnung()["fest"] == ["Zeile", "Probe"]
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_eine_spalte_laesst_sich_ausblenden():
    """Von Haus aus stehen alle da; ein Klick nimmt eine heraus."""
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM", "DichteGB"]),
            ordnung={"fest": ["Zeile", "Probe"]})
        try:
            for spalte in ("Zeile", "_TSM", "DichteGB"):
                assert legende.tabelle.wert(
                    spalte, trdflegende.ZEIGEN) == trdflegende.JA, spalte
            assert legende.ordnung()["versteckt"] == []
            legende._geklickt("DichteGB", trdflegende.ZEIGEN)
            assert legende.tabelle.wert(
                "DichteGB", trdflegende.ZEIGEN) == trdflegende.NEIN
            assert legende.ordnung()["versteckt"] == ["DichteGB"]
            # Und wieder her.
            legende._geklickt("DichteGB", trdflegende.ZEIGEN)
            assert legende.ordnung()["versteckt"] == []
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_was_fest_steht_bleibt_sichtbar():
    """Eine ausgeblendete Probennummer nimmt der Zeile ihren Namen."""
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM"]),
            ordnung={"fest": ["Zeile", "Probe"]})
        try:
            legende._geklickt("Probe", trdflegende.ZEIGEN)
            assert legende.tabelle.wert(
                "Probe", trdflegende.ZEIGEN) == trdflegende.JA
            assert legende.ordnung()["versteckt"] == []
            assert trdflegende.BLEIBT in legende.stand.cget("text")
            # Erst ohne „Fest“ geht es.
            legende._geklickt("Probe", trdflegende.FEST)
            legende._geklickt("Probe", trdflegende.ZEIGEN)
            assert legende.ordnung()["versteckt"] == ["Probe"]
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_wer_fest_stellt_holt_die_spalte_zurueck():
    """Fest und ausgeblendet widerspricht sich - fest gewinnt."""
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM"]),
            ordnung={"fest": ["Zeile"], "versteckt": ["_TSM"]})
        try:
            assert legende.tabelle.wert(
                "_TSM", trdflegende.ZEIGEN) == trdflegende.NEIN
            legende._geklickt("_TSM", trdflegende.FEST)
            assert legende.tabelle.wert(
                "_TSM", trdflegende.ZEIGEN) == trdflegende.JA
            assert legende.ordnung()["versteckt"] == []
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_die_kopfzeile_laesst_sich_je_spalte_waehlen():
    """Das Kuerzel bei den kryptischen, der Name bei den seltenen."""
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM", "DichteGB"]),
            ordnung={"fest": ["Zeile", "Probe"], "kopfspalte": "Spalte"})
        try:
            assert legende.tabelle.wert(
                "_TSM", trdflegende.KOPFSPALTE) == "Spalte"
            legende._geklickt("_TSM", trdflegende.KOPFSPALTE)
            assert legende.tabelle.wert(
                "_TSM", trdflegende.KOPFSPALTE) == "Name"
            # Nur diese eine - die andere folgt weiter der Wahl fuer alle.
            assert legende.ordnung()["kopfspalten"] == {"_TSM": "Name"}
            assert legende.tabelle.wert(
                "DichteGB", trdflegende.KOPFSPALTE) == "Spalte"
            # Einmal ganz durch die Reihe und wieder am Anfang.
            for _ in range(len(trdflegende.KOPFWAHL) - 1):
                legende._geklickt("_TSM", trdflegende.KOPFSPALTE)
            assert legende.tabelle.wert(
                "_TSM", trdflegende.KOPFSPALTE) == "Spalte"
            assert legende.ordnung()["kopfspalten"] == {}
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_die_wahl_in_der_leiste_stellt_alle_zugleich():
    """Bei dreissig Spalten waere jede einzeln Arbeit fuer nichts."""
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM", "DichteGB"]),
            ordnung={"fest": ["Zeile", "Probe"], "kopfspalte": "Spalte",
                     "kopfspalten": {"_TSM": "Name"}})
        try:
            assert legende.tabelle.wert(
                "_TSM", trdflegende.KOPFSPALTE) == "Name"
            legende.v_kopf.set("Einheit")
            legende._alle_koepfe()
            for spalte in ("_TSM", "DichteGB"):
                assert legende.tabelle.wert(
                    spalte, trdflegende.KOPFSPALTE) == "Einheit", spalte
            ordnung = legende.ordnung()
            assert ordnung["kopfspalte"] == "Einheit"
            assert ordnung["kopfspalten"] == {}
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_ein_spaltenpaar_traegt_dieselben_schalter():
    """"TRDF LIMS" und "TRDF ber." zeigen dieselbe Groesse."""
    def pruefen(fenster):
        spalten = ["Probe", "TRD_TRDF LIMS", "TRD_TRDF ber."]
        legende = trdflegende.Legendenfenster(
            fenster, "Ergebnisse", list(trdflegende.SPALTEN_ERGEBNIS),
            trdflegende.ergebnislegende(spalten),
            schluessel={spalte: trdflegende.schluessel(spalte)
                        for spalte in spalten},
            ordnung={"fest": ["Probe"]})
        try:
            legende._geklickt("TRD_TRDF LIMS", trdflegende.ZEIGEN)
            for spalte in ("TRD_TRDF LIMS", "TRD_TRDF ber."):
                assert legende.tabelle.wert(
                    spalte, trdflegende.ZEIGEN) == trdflegende.NEIN, spalte
            assert legende.ordnung()["versteckt"] == ["TRD_TRDF"]
            legende._geklickt("TRD_TRDF ber.", trdflegende.KOPFSPALTE)
            for spalte in ("TRD_TRDF LIMS", "TRD_TRDF ber."):
                assert legende.tabelle.wert(
                    spalte, trdflegende.KOPFSPALTE) == "Name", spalte
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_ausgeblendet_wird_je_groesse():
    """Beide Spalten eines Paares gehen zusammen - oder keine."""
    spalten = ["Probe", "TRD_TRDF LIMS", "TRD_TRDF ber.", "_SKA LIMS",
               "_SKA ber."]
    gezeigt = trdflegende.sichtbar(
        spalten, lambda name: trdflegende.schluessel(name),
        versteckt=["_SKA"], fest=["Probe"])
    assert gezeigt == ["Probe", "TRD_TRDF LIMS", "TRD_TRDF ber."]


def test_wer_festgehalten_ist_bleibt_auch_dann_sichtbar():
    spalten = ["Zeile", "Probe", "_TSM"]
    gezeigt = trdflegende.sichtbar(
        spalten, lambda name: trdflegende.schluessel(name),
        versteckt=["Probe", "_TSM"], fest=["Zeile", "Probe"])
    assert gezeigt == ["Zeile", "Probe"]


def test_eine_eigene_kopfwahl_sticht_die_fuer_alle():
    koepfe = trdflegende.ueberschriften(
        ["Probe", "_TSM", "DichteGB"], "Spalte",
        wahl={"_TSM": "Name", "DichteGB": "Einheit"})
    assert koepfe["Probe"] == "Probe"
    assert koepfe["_TSM"] == "Tiefenstufenmächtigkeit"
    assert koepfe["DichteGB"] == "g/cm3"


def test_eine_gezogene_zeile_aendert_die_reihenfolge():
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM", "DichteGB"]),
            ordnung={"fest": ["Zeile", "Probe"]})
        try:
            legende._verschieben("DichteGB", "_TSM")
            assert legende.ordnung()["reihenfolge"] == [
                "Zeile", "Probe", "DichteGB", "_TSM"]
            legende._verschieben("DichteGB", "_TSM")
            assert legende.ordnung()["reihenfolge"] == [
                "Zeile", "Probe", "_TSM", "DichteGB"]
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_was_fest_steht_laesst_sich_nicht_aus_versehen_verschieben():
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "Probe", "_TSM"]),
            ordnung={"fest": ["Zeile", "Probe"]})
        try:
            legende._verschieben("Probe", "_TSM")
            legende._verschieben("_TSM", "Zeile")
            assert legende.ordnung()["reihenfolge"] == [
                "Zeile", "Probe", "_TSM"]
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_eine_getippte_beschreibung_ueberlebt_das_verschieben():
    def pruefen(fenster):
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["_TSM", "DichteGB"]))
        try:
            legende.tabelle.setzen("_TSM", trdflegende.BESCHREIBUNG,
                                   "meine Notiz")
            legende._verschieben("DichteGB", "_TSM")
            assert legende.tabelle.wert("_TSM",
                                        trdflegende.BESCHREIBUNG).strip() == \
                "meine Notiz"
        finally:
            legende.destroy()
    mit_fenster(pruefen)


def test_die_wahl_der_ueberschrift_wird_mitgespeichert():
    def pruefen(fenster):
        gemerkt = {}
        legende = trdflegende.Legendenfenster(
            fenster, "Rohwerte", list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(["Zeile", "_TSM"]),
            speichern=lambda texte, ordnung: gemerkt.update(ordnung) or "",
            ordnung={"kopfspalte": "Spalte"})
        try:
            legende.v_kopf.set("Name")
            legende._sichern()
            assert gemerkt["kopfspalte"] == "Name"
            assert gemerkt["reihenfolge"] == ["Zeile", "_TSM"]
        finally:
            legende.destroy()
    mit_fenster(pruefen)


# --------------------------------------------------------------------------

def main() -> int:
    pruefungen = [(name, wert) for name, wert in sorted(globals().items())
                  if name.startswith("test_") and callable(wert)]
    fehler = 0
    for name, pruefung in pruefungen:
        try:
            pruefung()
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
