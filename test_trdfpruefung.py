"""Prueft die Sollbereiche der TRDF-Pruefung - ohne Datenbank, ohne GUI.

Die Grenzen stehen im Pruefplan des Labors; hier steht jede von ihnen
noch einmal als Rechenaufgabe. Das ist der Sinn dieser Datei: eine
verrutschte Klassengrenze faellt beim Ausprobieren nicht auf - der Wert
liegt ja meistens in der Mitte -, sondern erst, wenn eine Serie durch
die Pruefung geht und nichts meldet.

Aufruf:  python test_trdfpruefung.py
"""

from __future__ import annotations

import os
import tempfile

import trdf
import trdfpruefung as pruefung
from trdf import D


def werte(**angaben) -> dict:
    """Eine Probe, deren Werte alle Zahlen sind."""
    return {schluessel: (wert if wert is None else D(str(wert)))
            for schluessel, wert in angaben.items()}


# ------------------------------------------------------- Klassen nach Cges

def test_ohne_kohlenstoff_bleibt_der_weite_bereich():
    assert pruefung.grenzen(None, None) == pruefung.OHNE_AUFSCHLUSS
    assert pruefung.grenzen(None, D(1)) == pruefung.OHNE_AUFSCHLUSS


def test_die_fuenf_klassen_ohne_karbonat():
    assert pruefung.grenzen(D(1), None) == (D(1), D(2))
    assert pruefung.grenzen(D(5), None) == (D("0.9"), D("1.8"))
    assert pruefung.grenzen(D(20), None) == (D("0.6"), D("1.7"))
    assert pruefung.grenzen(D(50), None) == (D("0.4"), D("1.3"))
    assert pruefung.grenzen(D(200), None) == (D("0.3"), D("0.8"))


def test_mit_karbonat_darf_der_boden_dichter_sein():
    assert pruefung.grenzen(D(5), D(3)) == (D("0.9"), D(2))
    assert pruefung.grenzen(D(20), D(3)) == (D("0.6"), D("1.9"))
    assert pruefung.grenzen(D(50), D(3)) == (D("0.6"), D("1.9"))
    assert pruefung.grenzen(D(200), D(3)) == (D("0.5"), D("1.8"))


def test_unter_zwei_gramm_ist_karbonat_ohne_belang():
    assert pruefung.grenzen(D(1), D(5)) == pruefung.grenzen(D(1), None)


def test_die_klassengrenze_gehoert_zur_naechsten_klasse():
    assert pruefung.grenzen(D(2), None) == (D("0.9"), D("1.8"))
    assert pruefung.grenzen(D(10), None) == (D("0.6"), D("1.7"))
    assert pruefung.grenzen(D(40), None) == (D("0.4"), D("1.3"))
    assert pruefung.grenzen(D(100), None) == (D("0.3"), D("0.8"))


def test_eine_gemessene_null_heisst_ohne_karbonat():
    """Sie ist eine Aussage ueber die Probe: es ist keines da. Der
    weitere Bereich der karbonathaltigen Boeden steht ihr nicht zu -
    und ein Wert unter null heisst dasselbe, so streut eine Messung."""
    assert not pruefung.karbonathaltig(D(0))
    assert not pruefung.karbonathaltig(D("-0.2"))
    assert not pruefung.karbonathaltig(None)
    assert pruefung.karbonathaltig(D("0.1"))
    for cges in (D(5), D(20), D(50), D(200)):
        ohne = pruefung.grenzen(cges, None)
        assert pruefung.grenzen(cges, D(0)) == ohne, cges
        assert pruefung.grenzen(cges, D("-0.3")) == ohne, cges
        assert pruefung.grenzen(cges, D(2)) != ohne, cges


def test_erst_ueber_null_wird_der_bereich_weiter():
    """Der Fall, der es zeigt: 1,8 g/cm3 bei 20 g/kg Kohlenstoff."""
    assert pruefung.trdf_bewerten(D("1.8"), D(20), D(0)) == \
        [pruefung.TRDF_ZU_HOCH]
    assert pruefung.trdf_bewerten(D("1.8"), D(20), D(5)) == []


# ------------------------------------------------ Geschaetzt statt gerechnet

def test_gehen_die_beiden_dichten_auseinander_wurde_geschaetzt():
    """Seit dem 1.9.2026 nimmt TRD_TRDF eine gemessene Schaetzung vorweg;
    TRDF_Old rechnet weiter. Wo beide auseinandergehen, ist geschaetzt
    worden - und das soll im Blatt stehen."""
    assert pruefung.schaetzung_bewerten(D("1.5"), D("1.42"), D(2)) == \
        [pruefung.SCHAETZUNG]
    assert pruefung.schaetzung_bewerten(D("1.5"), D("1.5"), D(2)) == []


def test_bei_variante_sieben_ist_die_schaetzung_der_weg():
    """Dort ist die Trockenrohdichte die geschaetzte - das ist kein
    Befund, sondern die Variante."""
    assert pruefung.schaetzung_bewerten(D("1.8"), D("1.8"),
                                        pruefung.SCHAETZVARIANTE) == []
    assert pruefung.schaetzung_bewerten(D("1.8"), D("1.4"),
                                        pruefung.SCHAETZVARIANTE) == []


def test_auch_eine_fehlende_alte_dichte_ist_eine_abweichung():
    """Die alte Formel kann nicht rechnen, die neue nimmt die
    Schaetzung - dann steht dort eine Zahl, wo sonst ein x steht."""
    assert pruefung.schaetzung_bewerten(D("1.5"), None, D(3)) == \
        [pruefung.SCHAETZUNG]
    assert pruefung.schaetzung_bewerten(None, D("1.5"), D(3)) == \
        [pruefung.SCHAETZUNG]
    assert pruefung.schaetzung_bewerten(None, None, D(3)) == []


def test_ohne_die_zweite_methode_bleibt_das_blatt_still():
    """Es gibt Serien mit der neuen Pruefmethode und Serien ohne. Fehlt
    sie, gibt es nichts zu vergleichen - und ein fehlender Wert darf
    nicht wie eine Abweichung aussehen."""
    werte = {pruefung.TRDF: D("1.5"), pruefung.VARIANTE: D(2)}
    assert pruefung.SCHAETZUNG not in pruefung.bewerten(werte)
    werte[pruefung.TRDF_ALT] = D("1.42")
    assert pruefung.SCHAETZUNG in pruefung.bewerten(werte)


def test_die_schaetzung_meint_die_trockenrohdichte():
    """Gefaerbt wird die Zelle, um die es geht."""
    assert pruefung.betroffen([pruefung.SCHAETZUNG]) == {pruefung.TRDF}


# --------------------------------------------------- Trockenrohdichte

def test_die_dichte_in_der_mitte_wird_nicht_bemaengelt():
    assert pruefung.trdf_bewerten(D("1.4"), D(5), None) == []


def test_zu_leicht_und_zu_schwer_stehen_in_der_bewertung():
    assert pruefung.trdf_bewerten(D("0.8"), D(5), None) == \
        [pruefung.TRDF_ZU_GERING]
    assert pruefung.trdf_bewerten(D("1.9"), D(5), None) == \
        [pruefung.TRDF_ZU_HOCH]


def test_karbonat_haelt_die_gleiche_dichte_gerade_noch_aus():
    # 1,9 g/cm^3 bei 5 g/kg Kohlenstoff: ohne Karbonat zu hoch, mit
    # Karbonat noch im Bereich. Genau dafuer wird CO3 mitgeholt.
    assert pruefung.trdf_bewerten(D("1.9"), D(5), None) == \
        [pruefung.TRDF_ZU_HOCH]
    assert pruefung.trdf_bewerten(D("1.9"), D(5), D("0.4")) == []


def test_bei_viel_kohlenstoff_ist_auch_karbonat_streng():
    assert pruefung.trdf_bewerten(D("0.4"), D(200), D(1)) == \
        [pruefung.TRDF_ZU_GERING]
    assert pruefung.trdf_bewerten(D("0.4"), D(200), None) == []
    assert pruefung.trdf_bewerten(D("1.9"), D(200), D(1)) == \
        [pruefung.TRDF_ZU_HOCH]


def test_ohne_aufschluss_faellt_nur_das_unmoegliche_auf():
    assert pruefung.trdf_bewerten(D("1.4"), None, None) == []
    assert pruefung.trdf_bewerten(D("0.4"), None, None) == \
        [pruefung.TRDF_ZU_GERING]
    assert pruefung.trdf_bewerten(D("2.4"), None, None) == \
        [pruefung.TRDF_ZU_HOCH]


def test_ohne_dichte_gibt_es_keine_bewertung():
    assert pruefung.trdf_bewerten(None, D(5), None) == []


def test_die_grenze_selbst_gilt_noch_als_gut():
    assert pruefung.trdf_bewerten(D(1), D(1), None) == []
    assert pruefung.trdf_bewerten(D(2), D(1), None) == []


# ------------------------------------------------------ Skelettanteil

def test_der_skelettanteil_liegt_zwischen_null_und_hundert():
    assert pruefung.ska_bewerten(D(50)) == []
    assert pruefung.ska_bewerten(D(101)) == [pruefung.SKA_ZU_HOCH]
    assert pruefung.ska_bewerten(D("-0.5")) == [pruefung.SKA_NEGATIV]


def test_die_untergrenze_kommt_aus_der_schaetzung():
    # 50 % geschaetzt, Faktor 1: unter 40 % wird es unglaubwuerdig.
    assert pruefung.ska_untergrenze(D(50), D(1)) == D(40)
    assert pruefung.ska_bewerten(D(45), D(50), D(1)) == []
    assert pruefung.ska_bewerten(D(39), D(50), D(1)) == \
        [pruefung.SKA_ZU_GERING]


def test_ohne_schaetzung_keine_untergrenze():
    assert pruefung.ska_untergrenze(None, D(1)) is None
    assert pruefung.ska_untergrenze(D(50), None) is None
    assert pruefung.ska_bewerten(D(0), None, None) == []


def test_der_faktor_geht_in_die_untergrenze_ein():
    # Flachland: die Haelfte des geschaetzten Grobbodens zaehlt.
    assert pruefung.ska_untergrenze(D(60), D("0.66")) == D("29.6")


def test_zu_hoch_und_zu_gering_koennen_zusammen_auftreten():
    saetze = pruefung.ska_bewerten(D(-5), D(50), D(1))
    assert saetze == [pruefung.SKA_NEGATIV, pruefung.SKA_ZU_GERING]


# ---------------------------------------------------------- Differenz

def test_gemessen_und_geschaetzt_duerfen_zwanzig_punkte_auseinander():
    assert pruefung.differenz_bewerten(D(60), D(45)) == []
    assert pruefung.differenz_bewerten(D(60), D(39)) == \
        [pruefung.DIFFERENZ_ZU_GROSS]
    assert pruefung.differenz_bewerten(D(39), D(60)) == \
        [pruefung.DIFFERENZ_ZU_GROSS]


def test_genau_zwanzig_punkte_gehen_noch_durch():
    assert pruefung.differenz_bewerten(D(60), D(40)) == []


def test_ohne_zweiten_wert_keine_differenz():
    assert pruefung.differenz_bewerten(D(60), None) == []
    assert pruefung.differenz_bewerten(None, D(60)) == []


# ------------------------------------------------------- Feinbodenvorrat

def test_der_vorrat_darf_nicht_negativ_sein():
    assert pruefung.vorrat_bewerten(D(1000)) == []
    assert pruefung.vorrat_bewerten(D(0)) == []
    assert pruefung.vorrat_bewerten(D("-0.1")) == [pruefung.VORRAT_NEGATIV]
    assert pruefung.vorrat_bewerten(None) == []


# ------------------------------------------------------- alles zusammen

def test_eine_saubere_probe_bleibt_ohne_bewertung():
    probe = werte(**{pruefung.SKA: 20, pruefung.SKA_GEMESSEN: 18,
                     pruefung.SKA_GESCHAETZT: 20, pruefung.VORRAT: 4000,
                     pruefung.TRDF: "1.4", pruefung.GBFANT: 10,
                     pruefung.FAKTOR: 1, pruefung.CGES: 5,
                     pruefung.CO3: None})
    assert pruefung.bewerten(probe) == []
    assert pruefung.bewertungstext(pruefung.bewerten(probe)) == ""


def test_mehrere_fehlgeschlagene_pruefungen_stehen_mit_komma_nebeneinander():
    probe = werte(**{pruefung.SKA: 120, pruefung.SKA_GEMESSEN: 10,
                     pruefung.SKA_GESCHAETZT: 90, pruefung.VORRAT: -3,
                     pruefung.TRDF: "2.6", pruefung.CGES: 1})
    text = pruefung.bewertungstext(pruefung.bewerten(probe))
    assert text == (f"{pruefung.SKA_ZU_HOCH}, {pruefung.DIFFERENZ_ZU_GROSS}, "
                    f"{pruefung.VORRAT_NEGATIV}, {pruefung.TRDF_ZU_HOCH}")


def test_eine_leere_probe_wird_nicht_bemaengelt():
    assert pruefung.bewerten({}) == []


# --------------------------------------------------- Worum es im Satz geht

def test_jeder_satz_nennt_seinen_wert():
    """Sonst faerbt das Blatt eine Zelle, die niemand gemeint hat."""
    for satz, kuerzel in pruefung.BETROFFEN.items():
        assert kuerzel, satz
        for name in kuerzel:
            assert name in pruefung.QUELLEN.values(), (satz, name)


def test_die_dichte_meint_die_dichte_und_nicht_den_kohlenstoff():
    """Dass die Trockenrohdichte zu hoch ist, sagt etwas ueber sie -
    nicht ueber den Kohlenstoff, an dem ihre Grenze haengt."""
    assert pruefung.betroffen([pruefung.TRDF_ZU_HOCH]) == {pruefung.TRDF}
    assert pruefung.betroffen([pruefung.TRDF_ZU_GERING]) == {pruefung.TRDF}


def test_die_differenz_meint_beide_skelettanteile():
    assert pruefung.betroffen([pruefung.DIFFERENZ_ZU_GROSS]) == \
        {pruefung.SKA_GEMESSEN, pruefung.SKA_GESCHAETZT}


def test_mehrere_saetze_ergeben_mehrere_zellen():
    gemeint = pruefung.betroffen([pruefung.SKA_ZU_HOCH,
                                  pruefung.VORRAT_NEGATIV,
                                  pruefung.TRDF_ZU_HOCH])
    assert gemeint == {pruefung.SKA, pruefung.VORRAT, pruefung.TRDF}


def test_ein_satz_ohne_eigene_zelle_faerbt_nichts():
    assert pruefung.betroffen(["Rohwerte unvollstaendig"]) == set()
    assert pruefung.betroffen([]) == set()


def test_fremde_pruefungen_lassen_sich_dazustellen():
    gemeint = pruefung.betroffen(["Kohlenstoff seltsam"],
                                 {"Kohlenstoff seltsam": (pruefung.CGES,)})
    assert gemeint == {pruefung.CGES}


# ------------------------------------------------------------ Das Blatt

def test_die_spalten_stehen_in_der_reihenfolge_des_pruefplans():
    assert pruefung.SPALTEN[:4] == ("Zeile", "Probe-Nr.", "UM", "ME")
    assert pruefung.SPALTEN[-1] == "Bewertung"
    for name in pruefung.SPALTEN[4:-1]:
        assert name in pruefung.QUELLEN


def test_eine_zeile_traegt_zahlen_mit_komma_und_die_bewertung():
    probe = {"lnr": 5, "probe": "26B0001",
             "werte": werte(**{pruefung.SKA: "16.2728584982361",
                               pruefung.TRDF: "1.63465373129843"}),
             "bewertung": [pruefung.TRDF_ZU_HOCH]}
    gefunden = pruefung.zeile(probe)
    assert gefunden[0] == 5 and gefunden[1] == "26B0001"
    # Der Anteil traegt eine Stelle, die Dichte drei.
    assert gefunden[pruefung.SPALTEN.index("Skelettanteil")] == "16,3"
    assert gefunden[pruefung.SPALTEN.index("TRDF")] == "1,635"
    assert gefunden[-1] == pruefung.TRDF_ZU_HOCH


def test_wo_kein_wert_steht_steht_die_marke():
    gefunden = pruefung.zeile({"lnr": 1, "probe": "26B0002"})
    assert gefunden[pruefung.SPALTEN.index("Cges")] == trdf.MARKE


def test_das_blatt_traegt_die_serie_im_titel():
    (titel, spalten, zeilen), = pruefung.blatt([{"probe": "26B0001"}],
                                               "2026B051")
    assert "2026B051" in titel
    assert spalten == list(pruefung.SPALTEN)
    assert len(zeilen) == 1


def test_der_dateiname_haelt_serie_und_methode_fest():
    name = pruefung.dateiname("2026B051", "TRDF3.2")
    assert name == "Pruefung 2026B051 TRDF3.2.csv"
    assert "/" not in pruefung.dateiname("2026/B051", "a\\b")


def test_die_csv_landet_im_ordner_und_traegt_die_spalten():
    with tempfile.TemporaryDirectory() as ordner:
        ziel = os.path.join(ordner, pruefung.ORDNER)
        pfad = pruefung.schreiben(ziel, "2026B051",
                                  [{"lnr": 1, "probe": "26B0001",
                                    "werte": {pruefung.TRDF: D("1.4")},
                                    "bewertung": []}], "TRDF3.2")
        assert pfad and os.path.exists(pfad)
        inhalt = open(pfad, "rb").read().decode("cp1252", "replace")
        assert "Probe-Nr." in inhalt and "26B0001" in inhalt
        assert "1,4" in inhalt


def test_ein_unbeschreibbarer_ordner_meldet_sich_und_wirft_nicht():
    # Eine Datei als Ordner: das geht auf keinem Betriebssystem.
    with tempfile.TemporaryDirectory() as basis:
        sperre = os.path.join(basis, "keinordner")
        open(sperre, "w").close()
        assert pruefung.schreiben(os.path.join(sperre, "tiefer"),
                                  "2026B051", []) == ""


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
