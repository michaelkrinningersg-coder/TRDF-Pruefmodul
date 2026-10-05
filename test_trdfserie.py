"""Prueft den Kohlenstoff der Serie - Corg und die eine Unmoeglichkeit.

Mehr Carbonatkohlenstoff als Gesamtkohlenstoff kann es nicht geben. Das
ist die einzige Pruefung, die hier noch steht, und sie ist absolut: sie
braucht keinen Vergleich mit anderen Proben und kann deshalb auch nicht
davon abhaengen, aus wie vielen Plots eine Serie kommt.

Der Vergleich des Wiederfindungsgrades mit den Proben derselben
Kohlenstoffklasse stand bis September 2026 hier. Warum er heraus ist,
sagt der Kopf von trdfserie.py; dass er ganz heraus ist, prueft
`test_die_serienpruefung_ist_wirklich_heraus` - eine Rechnung ohne
Aufrufer ist beim naechsten Griff danach wieder da.

Aufruf:  python test_trdfserie.py
"""

from __future__ import annotations

import pathlib

import trdfserie as serie
from trdf import D


def proben(anzahl=12, cges="50", co3=None, wgh=None) -> list:
    """Eine Serie, in der alles beieinanderliegt."""
    gefunden = []
    for nummer in range(anzahl):
        gestreut = wgh if wgh is not None else str(
            D("1.2") + D(nummer % 5 - 2) / D(100)).replace(".", ",")
        gefunden.append({"probe": f"26B{nummer:04d}", "wgh": gestreut,
                         "cges": cges, "co3": co3})
    return gefunden


# ---------------------------------------------------- Der Kohlenstoff

def test_ohne_carbonat_ist_corg_der_ganze_kohlenstoff():
    assert serie.corg(D(50), None) == D(50)
    assert serie.corg("50", "x") == D(50)


def test_das_carbonat_wird_abgezogen():
    assert serie.corg(D(50), D(8)) == D(50) - D(8) * serie.CO3_ZU_C


def test_co3_ist_im_haus_schon_kohlenstoff():
    """Steht dort das Carbonat selbst, ist CO3_ZU_C der eine Ort, an
    dem das umzustellen waere."""
    assert serie.CO3_ZU_C == D(1)
    assert serie.corg(D(50), D(8)) == D(42)


def test_ohne_gesamtkohlenstoff_gibt_es_kein_corg():
    assert serie.corg(None, D(8)) is None
    assert serie.corg("x", "8") is None


def test_mehr_carbonat_als_kohlenstoff_kann_es_nicht_geben():
    """Das eine steckt im anderen: trifft es zu, ist eine der beiden
    Messungen falsch oder die Einheiten passen nicht zueinander."""
    assert serie.kohlenstoff_bewerten(D(5), D(8)) == \
        [serie.KOHLENSTOFF_NEGATIV]
    assert serie.kohlenstoff_bewerten(D(50), D(8)) == []
    assert serie.kohlenstoff_bewerten(None, D(8)) == []


def test_der_befund_faerbt_beide_zellen():
    """Welche der beiden Messungen falsch ist, sagt er nicht - also
    sind beide gemeint."""
    betroffen = serie.BETROFFEN[serie.KOHLENSTOFF_NEGATIV]
    assert len(betroffen) == 2


# ------------------------------------------------------ Der Serienblick

def test_eine_ruhige_serie_meldet_nichts():
    assert serie.bewerten(proben()) == {}


def test_nur_die_probe_mit_dem_unmoeglichen_kohlenstoff():
    alle = proben(6)
    alle[3]["cges"] = "5"
    alle[3]["co3"] = "8"
    assert list(serie.bewerten(alle)) == ["26B0003"]
    assert serie.bewerten(alle)["26B0003"] == [serie.KOHLENSTOFF_NEGATIV]


def test_ein_ausreissender_wiederfindungsgrad_ist_kein_befund_mehr():
    """Eine Serie traegt die Proben vieler Plots - verschiedene
    Standorte mit verschiedenen Boeden. Die Streuung kam zu einem
    grossen Teil aus dem Standort, und die Pruefung sprang zu oft an."""
    alle = proben(12)
    alle[7]["wgh"] = "9"             # weit daneben
    alle[2]["wgh"] = "400"           # noch weiter
    assert serie.bewerten(alle) == {}


def test_der_wiederfindungsgrad_wird_gar_nicht_mehr_gelesen():
    """Auch nicht als Nebenwirkung: `bewerten` kommt ohne ihn aus."""
    ohne = [{"probe": "26B0001", "cges": "5", "co3": "8"}]
    assert list(serie.bewerten(ohne)) == ["26B0001"]


def test_die_serienpruefung_ist_wirklich_heraus():
    """Eine Rechnung ohne Aufrufer stehen zu lassen waere das Gegenteil
    von "herausgenommen": sie faellt niemandem mehr auf und ist beim
    naechsten Griff danach wieder da."""
    for name in ("wgh_bewerten", "mitten", "klasse", "MINDESTENS",
                 "SPANNE", "MINDESTMASS", "WGH_PASST_NICHT"):
        assert not hasattr(serie, name), name
    quelle = pathlib.Path(__file__).with_name("trdfserie.py").read_text(
        encoding="utf-8")
    # Die Klasseneinteilung steht dort, wo sie hingehoert: als
    # Sollbereich der Trockenrohdichte.
    assert "KLASSEN" not in quelle.split('"""')[2]
    # Und der Kopf sagt, was heraus ist und wie es wiederkaeme.
    kopf = quelle.split('"""')[1]
    assert "Wiederfindungsgrad" in kopf
    assert "Plot" in kopf


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
    import sys
    sys.exit(main())
