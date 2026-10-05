"""Erzeugt die Bilder der Anleitung (docs/bilder) - ohne Datenbank.

Die Seite bekommt die Beispielserie aus test_trdfreiter.py; jedes Bild
ist ein Ausschnitt des Bildschirms. Aufruf aus dem Repository-Ordner:

    xvfb-run -a -s "-screen 0 1400x860x24" python docs/anleitung_bilder.py

Danach das PDF: python docs/anleitung_pdf.py
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TRDF_PRUEFMODUL_NICHT_OEFFNEN"] = "1"
import config, trdfpruefmodul, trdfreiter, test_trdfreiter as T, test_trdfpruefmodul as A

ZIEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bilder")
ordner = tempfile.mkdtemp()
trdfpruefmodul.Config = lambda: config.Config(runtime_dir=ordner)
f = trdfpruefmodul.PruefmodulAnwendung()
f.state("normal"); f.geometry("1400x860+0+0")
f.im_hintergrund = lambda *a, **k: None
trdfreiter.messagebox = T.Meldungen()

def knipsen(widget, name):
    widget.update(); f.update()
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    w, h = widget.winfo_width(), widget.winfo_height()
    subprocess.run(["import", "-window", "root", "-crop", f"{w}x{h}+{x}+{y}",
                    "+repage", os.path.join(ZIEL, name)], check=True)

AUFSCHLUSS = [{"prob_id": p, "para_id": 31, "kuerzel": "ATNULL", "mw": c}
              for p, c in ((1, "48"), (5, "22"), (11, "9,5"), (33, "3,1"))] + \
             [{"prob_id": p, "para_id": 33, "kuerzel": "ATNULLCO3", "mw": "0"}
              for p in (1, 5, 11, 33)]

schritte = []
def schritt(fn):
    schritte.append(fn); return fn

@schritt
def anmeldung():
    f.v_benutzer.set("mustermann"); f.v_passwort.set("geheim")
    knipsen(f.rahmen.winfo_children()[0], "01_anmeldung.png")

@schritt
def methodenwahl():
    f.zugang = A.ZugangAttrappe(); f.arbeitsmaske()
    s = f.trdf_seite
    s.feld_serie["values"] = ["2026B051", "2026B048", "2026H012"]
    s.v_serie.set("2026B051")
    s._methoden_zeigen("2026B051", [(42, "TRDF3.2"), (207, "TRDF3.2")])
    knipsen(f, "02_serie_methode.png")

@schritt
def geladen():
    s = f.trdf_seite
    s.v_methode.set("TRDF3.2 (UM 42)")
    s._methodenfeld_freigeben()
    s._uebernehmen(T.geholt(aufschluss=AUFSCHLUSS))
    s._melden("Serie 2026B051 - TRDF3.2, 4 Proben, 13 berechnete Groessen, "
              "16 Rohwerte", trdfreiter.Style.TEXT)
    knipsen(f, "03_serie_geladen.png")

@schritt
def einfuegen():
    s = f.trdf_seite
    w = s.einfuegen_oeffnen(); w.geometry("1000x520+200+170")
    w.textfeld.insert("1.0", "Serie: 2026B051\tUntersuchungsmethode: TRDF3.2\n"
                      "LNR\tProbe-Nr.\tVariante\tTiefenstufenmaechtigkeit\t"
                      "FaktorBerglandFlachland\tVolumenStechzylinder\t...\n"
                      "1\t26B0001\t2\t30\tx\t400\t...\n"
                      "5\t26B0005\t4\t30\t1\t500\t...\n")
    f.after(300, lambda: (knipsen(w, "04_einfuegen.png"), w._schliessen()))

@schritt
def aendern():
    s = f.trdf_seite
    s._berechnete_umschalten(merken=False)
    s._von_hand_geaendert("26B0011", "TRDFgesch", "1,2")
    s._von_hand_geaendert("26B0005", "GMSZ", "850")
    s._arbeitszeile_setzen("26B0011")
    knipsen(f, "05_aendern_live.png")

@schritt
def tasten():
    s = f.trdf_seite
    s.info_tasten._sofort()
    f.after(300, lambda: (knipsen(f, "06_tastenkuerzel.png"),
                          s.info_tasten._hinweis.hidetip()))

@schritt
def block():
    s = f.trdf_seite
    s._block_zeigen("26B0011", "Probe")
    b = s.bloecke["26B0011"]; b.geometry("+250+120")
    f.after(400, lambda: knipsen(b, "07_block.png"))

@schritt
def pruefung():
    s = f.trdf_seite
    for b in list(s.bloecke.values()):
        b.destroy()
    s.reiter.select(2)
    knipsen(f, "08_pruefung.png")

@schritt
def bild():
    s = f.trdf_seite
    s._bild_zeigen(); s.bildfenster.geometry("+300+80")
    f.after(400, lambda: knipsen(s.bildfenster, "09_bild.png"))

@schritt
def ergebnisse():
    s = f.trdf_seite
    s.bildfenster.destroy()
    s.reiter.select(1)
    knipsen(f, "10_ergebnisse.png")

@schritt
def vorschau():
    s = f.trdf_seite
    s.reiter.select(0)
    s._lims_schreiben()
    v = [k for k in s.winfo_children() if isinstance(k, trdfreiter.Exportvorschau)][0]
    v.geometry("1180x520+110+150")
    f.after(400, lambda: knipsen(v, "11_uebersicht_schreiben.png"))

@schritt
def bericht():
    s = f.trdf_seite
    for k in s.winfo_children():
        if isinstance(k, trdfreiter.Exportvorschau):
            k.destroy()
    geaendert = s.aenderungen()
    import datetime, trdfexport
    global SICHERUNG
    SICHERUNG = trdfexport.backup_schreiben(
        os.path.join(ordner, trdfexport.ORDNER), "2026B051", geaendert,
        datetime.datetime(2026, 10, 5, 16, 12))
    s._geschrieben(geaendert, {"geschrieben": len(geaendert), "ohne_zeile": [],
                               "anhang_geschrieben": 2, "anhang_ohne_zeile": [],
                               "nicht_uebernommen": [],
                               "anhang_nicht_uebernommen": []},
                   r"G:\TRDF-Pruefmodul\trdf_backup\2026B051 2026-10-05 161200.csv")
    s.reiter.select(3)
    knipsen(f, "12_exportbericht.png")

@schritt
def zurueck():
    import trdfexport
    s = f.trdf_seite
    geaendert = trdfexport.zurueck(trdfexport.gesichertes_lesen(SICHERUNG))
    v = trdfreiter.Exportvorschau(s, geaendert, os.path.basename(SICHERUNG),
                                  lambda: None, zurueck=True)
    v.geometry("1180x520+110+150")
    f.after(400, lambda: knipsen(v, "13_zurueckspielen.png"))

def weiter(i=0):
    if i >= len(schritte):
        f.after(500, f.destroy); return
    schritte[i]()
    f.after(1200, lambda: weiter(i + 1))

f.after(800, weiter)
f.mainloop()
print("fertig")
