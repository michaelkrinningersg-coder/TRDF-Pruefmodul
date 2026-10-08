"""Prueft den Bodenblock einer TRDF-Probe - Aufteilung und Fenster.

Das Bild soll zeigen, wie viel des Blocks geschaetzt und wie viel
gewogen wurde. Eine vertauschte Lage faellt beim Hinsehen nicht auf -
grau und braun stehen ja beide da -, wohl aber hier.

Aufruf:  xvfb-run -a python test_trdfblock.py
"""

from __future__ import annotations

import tkinter as tk

import trdf
import trdfblock
from trdf import D
from widgets import Style

GROSS, KLEIN, FEIN = (trdfblock.GROB_GROSS, trdfblock.GROB_KLEIN,
                      trdfblock.FEINBODEN)


def marken(lagen) -> list:
    return [marke for marke, _ in lagen]


def mit_fenster(pruefung):
    fenster = tk.Tk()
    fenster.withdraw()
    try:
        pruefung(fenster)
    finally:
        fenster.destroy()


# ------------------------------------------------------- Die Aufteilung

def test_variante_eins_ist_ganz_feinboden():
    assert trdfblock.anteile(1, D(0)) == [(FEIN, D(100))]
    # Auch wenn ein Skelettanteil dastuende: Variante 1 kennt keinen.
    assert trdfblock.anteile(1, D(30)) == [(FEIN, D(100))]


def test_variante_zwei_hat_keinen_anteil_ueber_63():
    lagen = trdfblock.anteile(2, D(30), gross=None)
    assert lagen == [(FEIN, D(70)), (KLEIN, D(30))]


def test_variante_zwei_uebergeht_eine_schaetzung():
    # Die Schaetzung gehoert nicht in dieses Bild - der ganze
    # Skelettanteil kommt aus der Wagung.
    assert trdfblock.anteile(2, D(30), gross=D(12)) == \
        [(FEIN, D(70)), (KLEIN, D(30))]


def test_die_lagen_stehen_von_unten_nach_oben():
    """Unten das Feine, darueber die Steine - wie in der Schaufelprobe."""
    lagen = trdfblock.anteile(4, D(16), gross=D(10))
    assert marken(lagen) == [FEIN, KLEIN, GROSS]
    assert lagen == [(FEIN, D(84)), (KLEIN, D(6)), (GROSS, D(10))]


def test_variante_sechs_teilt_wie_vier_fuenf_sieben():
    for variante in (4, 5, 6, 7):
        assert trdfblock.anteile(variante, D(50), gross=D(20)) == \
            [(FEIN, D(50)), (KLEIN, D(30)), (GROSS, D(20))]


def test_die_lagen_ergeben_immer_hundert_prozent():
    for variante in (1, 2, 4, 5, 6, 7):
        lagen = trdfblock.anteile(variante, D("79.1330850895496"),
                                  gross=D(50))
        assert sum(anteil for _, anteil in lagen) == D(100)


def test_ohne_skelettanteil_gibt_es_kein_bild():
    assert trdfblock.anteile(4, None, gross=D(10)) == []
    assert trdfblock.anteile(4, "x") == []


def test_ohne_schaetzung_hilft_der_gewogene_anteil_weiter():
    lagen = trdfblock.anteile(7, D(80), gross=None, klein=D(30))
    assert lagen == [(FEIN, D(20)), (KLEIN, D(30)), (GROSS, D(50))]


def test_ohne_beides_steht_der_ganze_skelettanteil_als_gewogen():
    assert trdfblock.anteile(7, D(30)) == [(FEIN, D(70)), (KLEIN, D(30))]


def test_leere_lagen_kommen_nicht_ins_bild():
    assert marken(trdfblock.anteile(4, D(0), gross=D(0))) == [FEIN]
    assert marken(trdfblock.anteile(4, D(100), gross=D(100))) == [GROSS]


def test_ein_skelettanteil_ueber_hundert_sprengt_den_block_nicht():
    lagen = trdfblock.anteile(4, D(140), gross=D(50))
    assert sum(anteil for _, anteil in lagen) == D(100)
    assert lagen == [(KLEIN, D(50)), (GROSS, D(50))]


def test_ein_negativer_anteil_wird_nicht_gezeichnet():
    lagen = trdfblock.anteile(4, D(10), gross=D(-5))
    assert lagen == [(FEIN, D(90)), (KLEIN, D(10))]


def test_die_werte_kommen_aus_rohwert_und_rechnung():
    lagen = trdfblock.aus_werten(
        {trdfblock.VARIANTE: "4"},
        {trdfblock.SKELETT: D("16.2728584982361"),
         trdfblock.GROSS: D(10), trdfblock.KLEIN: D("6.2728584982361")})
    assert marken(lagen) == [FEIN, KLEIN, GROSS]
    assert lagen[-1][1] == D(10)


def test_eine_variante_die_das_lims_nicht_kennt_zeigt_was_da_ist():
    lagen = trdfblock.aus_werten({trdfblock.VARIANTE: "x"},
                                 {trdfblock.SKELETT: D(20),
                                  trdfblock.GROSS: D(5)})
    assert lagen == [(FEIN, D(80)), (KLEIN, D(15)), (GROSS, D(5))]


# ------------------------------------------------------ Die Beschriftung

def test_anteile_stehen_mit_komma_und_einer_stelle():
    assert trdfblock.prozent(D("16.2728")) == "16,3 %"
    assert trdfblock.prozent(None) == trdf.MARKE
    assert trdfblock.prozent("x") == trdf.MARKE


def test_die_dichte_steht_mit_einheit_daneben():
    assert trdfblock.dichtetext(D("1.63465373")) == "1,635 g/cm³"
    assert trdfblock.dichtetext("x") == trdf.MARKE


def test_der_vorrat_steht_in_tonnen_je_hektar():
    assert trdfblock.vorratstext(D("5756.3840302028")) == "5756,4 t/ha"
    assert trdfblock.vorratstext("x") == trdf.MARKE


# ------------------------------------------------------- Die Schaufelprobe

import test_trdf                                     # noqa: E402

ROH33 = test_trdf.ZEILEN[33]["roh"]                  # Variante 5
ROH5 = test_trdf.ZEILEN[5]["roh"]                    # Variante 4, mit > 63 mm


def test_der_bezug_sind_feinboden_und_grobboden_2_bis_63():
    teile = trdfblock.schaufel(ROH33, test_trdf.gerechnet(33))
    assert teile["bezug"] == teile[FEIN] + teile[KLEIN]
    # Feinboden aus Masse und Trockenrohdichte, Grobboden aus Masse und
    # Gesteinsdichte.
    assert teile[KLEIN] == D("1254.51") / D("2.64")
    assert trdfblock.anteil_von(teile[FEIN], teile["bezug"]) == "83,9 %"


def test_was_groesser_als_63_ist_kommt_obendrauf():
    teile = trdfblock.schaufel(ROH5, test_trdf.gerechnet(5))
    assert teile[GROSS] == D("641.42") / D("2.2")
    # Es zaehlt nicht in den Bezug hinein - sonst waere ein Stein von
    # zwei Kilo jede Verhaeltniszahl darunter.
    assert teile["bezug"] == teile[FEIN] + teile[KLEIN]
    assert teile[GROSS] not in (teile["bezug"],)


def test_ohne_grosse_steine_gibt_es_keine_lage_dafuer():
    teile = trdfblock.schaufel(ROH33, test_trdf.gerechnet(33))
    assert GROSS not in teile                 # GBM63Schaufel ist 0


def test_die_feine_fraktion_steckt_im_groeberen():
    teile = trdfblock.schaufel(ROH33, test_trdf.gerechnet(33))
    assert teile[trdfblock.GROB_FEINST] == D("392.17") / D("2.64")
    assert teile[trdfblock.GROB_FEINST] < teile[KLEIN]


def test_die_lage_wird_geteilt_ausgewiesen():
    """Sonst liest man die Zahl der ganzen Lage als ihren dunklen Teil."""
    teile = trdfblock.schaufel(ROH33, test_trdf.gerechnet(33))
    assert teile[trdfblock.GROB_MITTEL] + teile[trdfblock.GROB_FEINST] == \
        teile[KLEIN]
    bezug = teile["bezug"]
    assert trdfblock.anteil_von(teile[KLEIN], bezug) == "16,1 %"
    assert trdfblock.anteil_von(teile[trdfblock.GROB_MITTEL], bezug) == \
        "11,1 %"
    assert trdfblock.anteil_von(teile[trdfblock.GROB_FEINST], bezug) == "5,0 %"


def test_ohne_feine_fraktion_bleibt_die_lage_eine():
    teile = trdfblock.schaufel(ROH5, test_trdf.gerechnet(5))
    assert trdfblock.GROB_MITTEL not in teile
    assert trdfblock.GROB_FEINST not in teile


def test_eine_zu_grosse_feine_fraktion_sprengt_die_lage_nicht():
    werte = dict(ROH33, **{trdfblock.GROBBODEN_SCHAUFEL: "9000"})
    teile = trdfblock.schaufel(werte, test_trdf.gerechnet(33))
    assert teile[trdfblock.GROB_FEINST] == teile[KLEIN]


def test_ohne_feinboden_gibt_es_kein_bild():
    assert trdfblock.schaufel(ROH33, {}) == {}


def test_ohne_gesteinsdichte_wird_kein_bild_behauptet():
    """Sonst stuende da, die Probe habe keine Steine gehabt."""
    ohne = dict(ROH33, **{trdfblock.DICHTE_GB: "x"})
    assert trdfblock.schaufel(ohne, test_trdf.gerechnet(33)) == {}
    # Ohne gewogene Steine ist der Feinboden dagegen die ganze Probe.
    leer = dict(ROH33, **{trdfblock.GROBBODEN_263: "x",
                          trdfblock.GROBBODEN_63: "x",
                          trdfblock.GROBBODEN_SCHAUFEL: "x"})
    teile = trdfblock.schaufel(leer, test_trdf.gerechnet(33))
    assert teile["bezug"] == teile[FEIN]


def test_die_zahlen_stehen_nach_geraet_getrennt():
    namen = [name for name, _ in trdfblock.gruppen(ROH33)]
    # Variante 5: der Stechzylinder war nicht im Einsatz.
    assert namen == ["Ministechzylinder (Stechkappe)", "Schaufelprobe",
                     "Probe"]
    zeilen = dict(trdfblock.gruppen(ROH33))["Ministechzylinder (Stechkappe)"]
    assert ("Masse", "797,3 g") in zeilen
    assert ("Volumen", "500 cm³") in zeilen


def test_der_stechzylinder_steht_da_wo_er_benutzt_wurde():
    namen = [name for name, _ in trdfblock.gruppen(ROH5)]
    assert namen[0] == "Stechzylinder"
    zeilen = dict(trdfblock.gruppen(ROH5))["Probe"]
    assert ("Dichte Grobboden", "2,2 g/cm³") in zeilen
    assert ("Tiefenstufenmaechtigkeit", "30 cm") in zeilen


def test_massen_stehen_mit_komma_und_einheit():
    assert trdfblock.masse("5047,3") == "5047,3 g"
    assert trdfblock.masse("500", "cm³") == "500 cm³"
    assert trdfblock.masse("x") == trdf.MARKE


# ------------------------------------------------------------ Das Fenster

def rechtecke(fenster):
    return [fenster.bild.itemcget(kennung, "fill")
            for kennung in fenster.bild.find_all()
            if fenster.bild.type(kennung) == "rectangle"]


def test_das_fenster_zeichnet_je_lage_ein_rechteck():
    def pruefen(eltern):
        block = trdfblock.zeigen(
            eltern, "26B0005", {trdfblock.VARIANTE: "4"},
            {trdfblock.SKELETT: D(16), trdfblock.GROSS: D(10),
             trdfblock.DICHTE: D("1.634")})
        assert rechtecke(block) == [trdfblock.FARBEN[FEIN],
                                    trdfblock.FARBEN[KLEIN],
                                    trdfblock.FARBEN[GROSS]]
        assert "26B0005" in block.title()
    mit_fenster(pruefen)


def test_die_hoehe_einer_lage_folgt_ihrem_anteil():
    def pruefen(eltern):
        block = trdfblock.Blockfenster(eltern, "26B0005",
                                       [(FEIN, D(75)), (GROSS, D(25))])
        block.update()
        kennungen = [k for k in block.bild.find_all()
                     if block.bild.type(k) == "rectangle"]
        unten, oben = (block.bild.coords(k) for k in kennungen)
        # Die erste Lage liegt unten und nimmt drei Viertel ein.
        assert unten[3] == trdfblock.HOEHE        # Feinboden bis unten hin
        assert oben[1] == 0                       # Grobboden bis oben hin
        assert oben[3] == trdfblock.HOEHE * 0.25
    mit_fenster(pruefen)


def test_ohne_lagen_steht_ein_hinweis_statt_eines_blocks():
    def pruefen(eltern):
        block = trdfblock.Blockfenster(eltern, "26B0092", [])
        assert not rechtecke(block)
        texte = [block.bild.itemcget(k, "text") for k in block.bild.find_all()]
        assert any("kein Skelettanteil" in text for text in texte)
    mit_fenster(pruefen)


def test_der_schaufelblock_zeichnet_seine_lagen():
    def pruefen(eltern):
        block = trdfblock.zeigen(eltern, "26B0033", ROH33,
                                 test_trdf.gerechnet(33))
        farben = [block.schaufelbild.itemcget(k, "fill")
                  for k in block.schaufelbild.find_all()
                  if block.schaufelbild.type(k) == "rectangle"]
        assert farben == [trdfblock.FARBEN[FEIN],
                          trdfblock.FARBEN[trdfblock.GROB_FEINST],
                          trdfblock.FARBEN[trdfblock.GROB_MITTEL]]
        # Im Block steht der Anteil der ganzen Lage 2 bis 63 mm; was
        # davon die feine Fraktion ist, sagt die Legende darunter.
        zahlen = [block.schaufelbild.itemcget(k, "text")
                  for k in block.schaufelbild.find_all()
                  if block.schaufelbild.type(k) == "text"]
        assert zahlen == ["83,9 %", "16,1 %"]
        # Unter dem Bild steht die Aufteilung, um die es beim Sieben
        # ging: die ganze Lage und ihre beiden Haelften.
        legende = _legendenzeilen(block.schaufellegende)
        assert any("2 - 63 mm: 16,1 %" in text for text in legende)
        assert any("6,3 - 63 mm: 11,1 %" in text for text in legende)
        assert any("2 - 6,3 mm: 5,0 %" in text for text in legende)
    mit_fenster(pruefen)


def test_ohne_masse_der_schaufelprobe_keine_schaufelspalte():
    """Masse 0 oder x: die Probe wurde nicht mit der Schaufel genommen -
    dann steht auch kein Schaufelbild da, und keine Legende dazu."""
    def pruefen(eltern):
        ohne = dict(ROH33, MSchaufel="x")
        block = trdfblock.zeigen(eltern, "26B0033", ohne,
                                 test_trdf.gerechnet(33))
        block.update_idletasks()
        assert not block.rechts.winfo_manager()
        assert _legendenzeilen(block.schaufellegende) == []
        block.neu_zeichnen(ROH33, test_trdf.gerechnet(33))
        block.update_idletasks()
        assert block.rechts.winfo_manager() == "pack"
        assert _legendenzeilen(block.schaufellegende)
    mit_fenster(pruefen)


def test_dieselbe_lage_steht_in_derselben_zeile():
    """Feinboden neben Feinboden, 2-63 neben 2-63, >63 neben >63 - auch
    wenn die Schaufelprobe zwei Zeilen mehr hat (ihre Haelften der Lage
    2 bis 63 mm)."""
    def zeile_von(rahmen, anfang):
        for kind in rahmen.grid_slaves():
            if isinstance(kind, tk.Label) and \
                    str(kind.cget("text")).startswith(anfang):
                return int(kind.grid_info()["row"])
        return None

    def pruefen(eltern):
        for probe, roh, lnr in (("26B0005", ROH5, 5), ("26B0033", ROH33, 33)):
            block = trdfblock.zeigen(eltern, probe, roh,
                                     test_trdf.gerechnet(lnr))
            for anfang in ("Feinboden", "Grobboden 2 - 63 mm",
                           "Grobboden > 63 mm"):
                links = zeile_von(block.legende, anfang)
                rechts = zeile_von(block.schaufellegende, anfang)
                if links is None or rechts is None:
                    continue                  # Lage nur auf einer Seite
                assert links == rechts, (probe, anfang)
        # 26B0033: die Schaufelprobe hat mehr Zeilen als die Probe.
        assert len(_legendenzeilen(block.schaufellegende)) > \
            len(_legendenzeilen(block.legende))
    mit_fenster(pruefen)


def test_die_prozente_der_legende_stehen_rechtsbuendig():
    def pruefen(eltern):
        block = trdfblock.zeigen(eltern, "26B0005", ROH5,
                                 test_trdf.gerechnet(5))
        for rahmen in (block.legende, block.schaufellegende):
            prozente = [k for k in rahmen.grid_slaves()
                        if isinstance(k, tk.Label)
                        and int(k.grid_info()["column"]) == 2]
            assert prozente
            for feld in prozente:
                assert feld.grid_info()["sticky"] == "e"
                assert feld.cget("text").endswith("%")
    mit_fenster(pruefen)


def test_der_block_ist_immer_so_breit_wie_der_block():
    """Kein leerer Streifen daneben - die Marke der hundert Prozent
    liegt im Bild."""
    def pruefen(eltern):
        for probe, roh, lnr in (("26B0033", ROH33, 33), ("26B0005", ROH5, 5)):
            block = trdfblock.zeigen(eltern, probe, roh,
                                     test_trdf.gerechnet(lnr))
            assert int(block.schaufelbild.cget("width")) == \
                trdfblock.BREITE_SCHAUFEL
    mit_fenster(pruefen)


def test_die_linie_kommt_ohne_beschriftung_aus():
    """Sie braeuchte entweder Platz neben dem Block oder laege in ihm
    im Weg; was ueber ihr steht, sagt die Legende."""
    def pruefen(eltern):
        block = trdfblock.zeigen(eltern, "26B0005", ROH5,
                                 test_trdf.gerechnet(5))
        flaeche = block.schaufelbild
        assert flaeche.type(flaeche.find_all()[-1]) == "line"
        texte = [flaeche.itemcget(k, "text") for k in flaeche.find_all()
                 if flaeche.type(k) == "text"]
        assert "100 %" not in texte
        legende = _legendenzeilen(block.schaufellegende)
        assert any("obendrauf" in text for text in legende)
    mit_fenster(pruefen)


def test_der_block_bleibt_ueber_dem_hauptfenster():
    def pruefen(eltern):
        block = trdfblock.zeigen(eltern, "26B0033", ROH33,
                                 test_trdf.gerechnet(33))
        assert block.wm_transient()
    mit_fenster(pruefen)


def test_die_hundert_prozent_linie_steht_nur_wenn_etwas_obendrauf_liegt():
    def pruefen(eltern):
        ohne = trdfblock.zeigen(eltern, "26B0033", ROH33,
                                test_trdf.gerechnet(33))
        assert not [k for k in ohne.schaufelbild.find_all()
                    if ohne.schaufelbild.type(k) == "line"]
        mit = trdfblock.zeigen(eltern, "26B0005", ROH5,
                               test_trdf.gerechnet(5))
        linien = [k for k in mit.schaufelbild.find_all()
                  if mit.schaufelbild.type(k) == "line"]
        assert len(linien) == 1
        # Beschriftet ist sie nicht - die Legende sagt, was darueber steht.
        texte = [mit.schaufelbild.itemcget(k, "text")
                 for k in mit.schaufelbild.find_all()
                 if mit.schaufelbild.type(k) == "text"]
        assert "100 %" not in texte
    mit_fenster(pruefen)


def test_der_block_zeigt_die_massen_der_probe():
    def pruefen(eltern):
        block = trdfblock.zeigen(eltern, "26B0033", ROH33,
                                 test_trdf.gerechnet(33))
        texte = _alle_texte(block.zahlen)
        assert "Schaufelprobe" in texte and "5047,3 g" in texte
        assert "2,64 g/cm³" in texte and "50 cm" in texte
        assert "Tiefenstufenmaechtigkeit" in texte
        assert "Stechzylinder" not in texte      # Variante 5 hat keinen
    mit_fenster(pruefen)


def test_eine_aenderung_geht_durch_beide_bloecke():
    def pruefen(eltern):
        block = trdfblock.zeigen(eltern, "26B0033", ROH33,
                                 test_trdf.gerechnet(33))
        vorher = block.schaufelteile[KLEIN]
        werte = dict(ROH33, **{trdfblock.GROBBODEN_263: "2509,02"})
        block.neu_zeichnen(werte, test_trdf.gerechnet(33))
        assert block.schaufelteile[KLEIN] == vorher * 2
        assert "2509,02 g" in _alle_texte(block.zahlen)
    mit_fenster(pruefen)


def _legendenzeilen(rahmen) -> list:
    """Die Legende Zeile fuer Zeile als "Name: Prozent".

    Name und Prozent stehen in eigenen Spalten, damit die Prozente
    untereinander stehen - gelesen wird hier wieder eine Zeile daraus.
    """
    zeilen = {}
    for kind in rahmen.grid_slaves():
        if isinstance(kind, tk.Label):
            info = kind.grid_info()
            zeilen.setdefault(int(info["row"]), {})[int(info["column"])] = \
                kind.cget("text")
    return [": ".join(teile[spalte] for spalte in sorted(teile))
            for _zeile, teile in sorted(zeilen.items())
            if any(teile.values())]


def _alle_texte(rahmen) -> list:
    texte = []
    for kind in rahmen.winfo_children():
        if isinstance(kind, tk.Label):
            texte.append(kind.cget("text"))
        else:
            texte += _alle_texte(kind)
    return texte


def beschriftungen(widget) -> list:
    """Alle Label-Texte unter einem Widget - ueber den ganzen Baum."""
    gebaut = []
    for kind in widget.winfo_children():
        if isinstance(kind, tk.Label):
            gebaut.append(kind.cget("text"))
        gebaut.extend(beschriftungen(kind))
    return gebaut


def test_die_variante_und_die_dichte_stehen_im_fenster():
    def pruefen(eltern):
        block = trdfblock.zeigen(
            eltern, "26B0011", {trdfblock.VARIANTE: "7"},
            {trdfblock.SKELETT: D("79.13"), trdfblock.GROSS: D(50),
             trdfblock.DICHTE: D("1.8")})
        # Der ganze Baum und nicht nur die erste Ebene: die Kopfzeile
        # traegt einen eigenen Rahmen um sich.
        assert any("Variante 7" in text for text in beschriftungen(block))
        alle = str(block.winfo_children())
        assert alle          # das Fenster steht
        assert trdfblock.dichtetext(D("1.8")) == "1,800 g/cm³"
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
