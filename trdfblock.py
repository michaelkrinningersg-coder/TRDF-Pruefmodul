"""
TRDF-Pruefmodul - der Bodenblock einer TRDF-Probe
=================================================

Eine Zeile mit zwoelf Zahlen sagt einem geuebten Auge viel, aber nicht
alles: ob Schaetzung und Messung zusammenpassen, sieht man erst, wenn
beides uebereinander steht. Deshalb dieses Bild - ein Block Boden, wie
er im Gelaende ausgestochen wurde, von unten nach oben aufgeteilt:

    hellbraun    Feinboden - was uebrig bleibt
    dunkelbraun  Grobboden 2 bis 63 mm - im Labor gewogen
                 (VOLAntGB263, die Differenz zum Skelettanteil)
    dunkelgrau   Grobboden ueber 63 mm - im Gelaende geschaetzt
                 (VOLGB63gs, also GBFAnt mal Faktor Bergland/Flachland)

Unten das Feine, darueber die Steine, das Groebste zuoberst - dieselbe
Reihenfolge wie im Bild der Schaufelprobe daneben. Zwei Bilder
nebeneinander, die verschieden herum gelesen werden wollen, sind ein
Bild zu viel.

Die Aufteilung haengt an der Variante der Probenahme:

    1        kein Grobboden; der Block ist ganz Feinboden.
    2        kein Anteil ueber 63 mm; der ganze Skelettanteil kommt aus
             der Wagung und steht dunkelbraun.
    4, 5, 7  beides: unten die Schaetzung, darueber die Wagung.
    6        wie 4/5/7 - unten VOLGB63gs, darueber die Differenz zum
             Skelettanteil.

Dass 6 und 4/5/7 dasselbe Bild ergeben, ist kein Zufall: die Formel
VOLAntGB263 des LIMS rechnet fuer beide _SKA minus VOLGB63gs. Hier
stehen sie trotzdem einzeln, weil sie im Pruefplan einzeln stehen - und
weil eine geaenderte Formel dann hier auffaellt und nicht stillschweigend
mitwandert.

Der zweite Block: die Schaufelprobe
-----------------------------------
Rechts steht, was im Labor wirklich auf der Waage lag, als Volumen
gerechnet: der Feinboden aus seiner Masse und der Trockenrohdichte, der
Grobboden 2 bis 63 mm aus seiner Masse und der Gesteinsdichte. Diese
beiden zusammen sind der Bezug, die hundert Prozent - denn die
Schaufelprobe ist genau das, was ausgesiebt wurde.

Was ueber 63 mm dabei war, steht *obendrauf*: es gehoert zur Probe,
aber nicht in ihren Bezug, und ein Stein von zwei Kilo wuerde jede
Verhaeltniszahl darunter verzerren. Eine gestrichelte Linie zeigt, wo
die hundert Prozent liegen.

Bei Variante 5 steckt im Grobboden 2 bis 63 mm noch die Fraktion 2 bis
6,3 mm - die, die im Ministechzylinder mitgemessen wurde. Sie steht in
hellerem Grau *innerhalb* der Lage und nicht obendrauf: sie ist ein
Teil von ihr und wuerde sonst zweimal zaehlen.

Und daneben die Zahlen, aus denen das alles kommt - nach Stechzylinder,
Ministechzylinder und Schaufelprobe getrennt, weil je nach Variante ein
anderes Geraet die Probe genommen hat.
"""

from __future__ import annotations


import trdf
import trdfrohpruefung
from trdf import D

# Die drei Lagen und ihre Farben. Grau ist geschaetzt, braun gemessen,
# hell ist der Feinboden - so herum, weil das Auge die dunkle Lage als
# das Schwere liest, das sie auch ist.
GROB_GROSS = "gross"          # ueber 63 mm, aus der Schaetzung
GROB_KLEIN = "klein"          # 2 bis 63 mm, aus der Wagung
GROB_MITTEL = "mittel"        # 6,3 bis 63 mm - der Rest der Lage darueber
GROB_FEINST = "feinst"        # 2 bis 6,3 mm, ein Teil des vorigen
FEINBODEN = "fein"

FARBEN = {GROB_GROSS: "#4b5563", GROB_KLEIN: "#5b3a1e",
          GROB_MITTEL: "#5b3a1e", GROB_FEINST: "#9ca3af",
          FEINBODEN: "#d2b48c"}
BESCHRIFTUNG = {GROB_GROSS: "Grobboden > 63 mm (geschaetzt)",
                GROB_KLEIN: "Grobboden 2 - 63 mm (gemessen)",
                GROB_MITTEL: "davon 6,3 - 63 mm",
                GROB_FEINST: "davon 2 - 6,3 mm",
                FEINBODEN: "Feinboden"}
BESCHRIFTUNG_SCHAUFEL = {
    GROB_GROSS: "Grobboden > 63 mm (obendrauf)",
    GROB_KLEIN: "Grobboden 2 - 63 mm",
    GROB_MITTEL: "davon 6,3 - 63 mm",
    GROB_FEINST: "davon 2 - 6,3 mm",
    FEINBODEN: "Feinboden (Masse / TRDF)"}
SCHRIFTFARBE = {GROB_GROSS: "#ffffff", GROB_KLEIN: "#ffffff",
                GROB_MITTEL: "#ffffff", GROB_FEINST: "#1f2937",
                FEINBODEN: "#3f2d14"}

# In welcher Reihenfolge die Lagen der Schaufelprobe von unten nach
# oben stehen. Steckt eine feine Fraktion darin, wird die Lage 2 bis 63
# mm in ihre beiden Haelften geteilt gezeichnet - sonst liest man die
# obere Zahl als die ganze Lage.
SCHAUFELFOLGE = (FEINBODEN, GROB_FEINST, GROB_MITTEL, GROB_KLEIN)

# Die Formelkuerzel, aus denen das Bild entsteht.
VARIANTE = "_TRDV"
SKELETT = "_SKA"
GROSS = "VOLGB63gs"
KLEIN = "VOLAntGB263"
DICHTE = "TRD_TRDF"
VORRAT = "FBVb"
FEIN_SCHAUFEL = "FBMSchaufel"

# Die Rohwerte, die im Bild stehen - dieselben Namen wie in der
# Rohwertpruefung, damit es nur eine Wahrheit gibt.
VOL_SZ = trdfrohpruefung.VOL_SZ
MASSE_SZ = trdfrohpruefung.MASSE_SZ
GROBBODEN_SZ = trdfrohpruefung.GROBBODEN_SZ
VOL_MINI = trdfrohpruefung.VOL_MINI
MASSE_MINI = trdfrohpruefung.MASSE_MINI
MASSE_SCHAUFEL = trdfrohpruefung.MASSE_SCHAUFEL
GROBBODEN_63 = trdfrohpruefung.GROBBODEN_63
GROBBODEN_263 = trdfrohpruefung.GROBBODEN_263
GROBBODEN_SCHAUFEL = trdfrohpruefung.GROBBODEN_SCHAUFEL
DICHTE_GB = trdfrohpruefung.DICHTE_GB
TIEFENSTUFE = trdfrohpruefung.TIEFENSTUFE

# Welche Zahl in welcher Gruppe steht, und in welcher Einheit. Getrennt
# nach dem Geraet, mit dem die Probe genommen wurde: je nach Variante
# war es ein anderes, und eine Gruppe ohne einen einzigen Wert wird gar
# nicht erst gezeigt.
GRUPPEN = (
    ("Stechzylinder", ((MASSE_SZ, "Gesamtmasse", "g"),
                       (GROBBODEN_SZ, "Grobboden", "g"),
                       (VOL_SZ, "Volumen", "cm³"))),
    ("Ministechzylinder (Stechkappe)", ((MASSE_MINI, "Masse", "g"),
                                        (VOL_MINI, "Volumen", "cm³"))),
    ("Schaufelprobe", ((MASSE_SCHAUFEL, "Masse", "g"),
                       (GROBBODEN_63, "Grobboden > 63 mm", "g"),
                       (GROBBODEN_263, "Grobboden 2 - 63 mm", "g"),
                       (GROBBODEN_SCHAUFEL, "davon 2 - 6,3 mm", "g"))),
    ("Probe", ((DICHTE_GB, "Dichte Grobboden", "g/cm³"),
               (TIEFENSTUFE, "Tiefenstufenmaechtigkeit", "cm"))),
)

# Welche Variante welches Bild ergibt.
OHNE_GROBBODEN = (1,)
OHNE_GROSSEN = (2,)
MIT_BEIDEM = (4, 5, 6, 7)

GANZ = D(100)


def _zahl(wert):
    """Eine Zahl oder None - auch aus einem 'x' des LIMS."""
    return trdf.zahl(wert)


def anteile(variante, skelett, gross=None, klein=None) -> list:
    """Die Lagen des Blocks von unten nach oben - (Marke, Prozent).

    `variante` ist _TRDV, `skelett` der Skelettanteil in Prozent,
    `gross` der geschaetzte Anteil ueber 63 mm und `klein` - wenn die
    Schaetzung fehlt - der gewogene Anteil 2 bis 63 mm.

    Zurueck kommen sie von unten nach oben: Feinboden, der gewogene
    Grobboden, der geschaetzte - wie in der Schaufelprobe daneben.

    Ohne Skelettanteil gibt es kein Bild: dann ist nicht bekannt, wie
    viel Boden ueberhaupt Feinboden ist, und ein Block, der zu 100
    Prozent hellbraun steht, waere eine Behauptung und keine Auskunft.
    """
    skelett = _zahl(skelett)
    gross, klein = _zahl(gross), _zahl(klein)
    if variante is not None and int(variante) in OHNE_GROBBODEN:
        return [(FEINBODEN, GANZ)]
    if skelett is None:
        return []
    if variante is not None and int(variante) in OHNE_GROSSEN:
        gross = D(0)
    elif gross is None and klein is not None:
        gross = skelett - klein
    elif gross is None:
        gross = D(0)
    gross = min(max(gross, D(0)), GANZ)
    gewogen = min(max(skelett - gross, D(0)), GANZ - gross)
    lagen = [(FEINBODEN, GANZ - gross - gewogen), (GROB_KLEIN, gewogen),
             (GROB_GROSS, gross)]
    return [(marke, anteil) for marke, anteil in lagen if anteil > 0]


def aus_werten(roh: dict, gerechnet: dict) -> list:
    """Die Lagen aus dem, was zu einer Probe im Programm steht."""
    variante = _zahl(roh.get(VARIANTE))
    return anteile(int(variante) if variante is not None else None,
                   gerechnet.get(SKELETT), gerechnet.get(GROSS),
                   gerechnet.get(KLEIN))


def _teilen(masse, dichte):
    """Masse durch Dichte - das Volumen, das dieser Teil einnimmt."""
    masse, dichte = _zahl(masse), _zahl(dichte)
    if masse is None or dichte is None or dichte <= 0:
        return None
    return masse / dichte


def schaufel(roh: dict, gerechnet: dict) -> dict:
    """Die Volumenverteilung in der Schaufelprobe - in cm^3.

    Der Bezug sind Feinboden und Grobboden 2 bis 63 mm zusammen: das
    ist die Probe, die ausgesiebt wurde. Was groesser als 63 mm war,
    steht daneben und kommt im Bild obendrauf; die Fraktion 2 bis 6,3
    mm steckt im Grobboden 2 bis 63 mm und wird nur ausgewiesen.

    Ohne Feinboden gibt es kein Bild: dann fehlt entweder die Masse der
    Schaufelprobe oder die Trockenrohdichte, und ein Verhaeltnis ohne
    seinen groessten Teil waere eine Falschauskunft.
    """
    # Ohne gewogene Schaufelprobe gibt es keine - auch wenn aus anderen
    # Werten ein Feinboden zu rechnen waere. Eine Masse 0 oder x heisst:
    # diese Probe wurde nicht mit der Schaufel genommen.
    masse_schaufel = _zahl(roh.get(MASSE_SCHAUFEL))
    if masse_schaufel is None or masse_schaufel <= 0:
        return {}
    fein = _teilen(gerechnet.get(FEIN_SCHAUFEL), gerechnet.get(DICHTE))
    dichte = roh.get(DICHTE_GB)
    klein = _teilen(roh.get(GROBBODEN_263), dichte)
    gross = _teilen(roh.get(GROBBODEN_63), dichte)
    feinst = _teilen(roh.get(GROBBODEN_SCHAUFEL), dichte)
    if fein is None or fein <= 0:
        return {}
    # Eine gewogene Steinmasse ohne Gesteinsdichte laesst sich nicht in
    # Volumen umrechnen. Das Bild wuerde dann behaupten, es haette keine
    # Steine gegeben - lieber gar keines.
    for name, volumen in ((GROBBODEN_263, klein), (GROBBODEN_63, gross)):
        if volumen is None and not trdf.leer(roh.get(name)):
            return {}
    klein = klein if klein is not None and klein > 0 else D(0)
    bezug = fein + klein
    gefunden = {FEINBODEN: fein, GROB_KLEIN: klein, "bezug": bezug}
    if gross is not None and gross > 0:
        gefunden[GROB_GROSS] = gross
    if feinst is not None and feinst > 0:
        # Die feine Fraktion und der Rest der Lage werden einzeln
        # ausgewiesen: sonst steht ueber dem hellen Streifen die Zahl
        # der ganzen Lage, und man liest den dunklen Teil als sie.
        gefunden[GROB_FEINST] = min(feinst, klein)
        gefunden[GROB_MITTEL] = klein - gefunden[GROB_FEINST]
    return gefunden


def anteil_von(wert, bezug) -> str:
    """Ein Volumen als Anteil des Bezugs."""
    if wert is None or not bezug:
        return trdf.MARKE
    return prozent(wert / bezug * GANZ)


def masse(wert, einheit="g") -> str:
    """Eine Masse oder ein Volumen, wie es auf der Waage stand."""
    zahl = _zahl(wert)
    if zahl is None:
        return trdf.MARKE
    gerundet = zahl.quantize(D("0.01")).normalize()
    text = format(gerundet, "f").replace(".", ",")
    return f"{text} {einheit}" if einheit else text


def gruppen(roh: dict) -> list:
    """Die Zahlen der Probe, nach Geraet geordnet - nur was dasteht."""
    gefunden = []
    for name, felder in GRUPPEN:
        zeilen = [(beschriftung, masse(roh.get(kuerzel), einheit))
                  for kuerzel, beschriftung, einheit in felder
                  if not trdf.leer(roh.get(kuerzel))]
        if zeilen:
            gefunden.append((name, zeilen))
    return gefunden


def prozent(wert) -> str:
    """Ein Anteil, wie er im Bild steht."""
    zahl = _zahl(wert)
    if zahl is None:
        return trdf.MARKE
    return str(zahl.quantize(D("0.1"))).replace(".", ",") + " %"


def dichtetext(wert) -> str:
    """Die Trockenrohdichte fuer die Beschriftung neben dem Block."""
    zahl = _zahl(wert)
    if zahl is None:
        return trdf.MARKE
    return str(zahl.quantize(D("0.001"))).replace(".", ",") + " g/cm³"


def vorratstext(wert) -> str:
    """Der Feinbodenvorrat - die Zahl, um die es am Ende geht.

    Der Block zeigt, wie viel Feinboden im Boden steckt; diese Zahl sagt,
    wie viel davon auf der Flaeche steht. Sie gehoert daneben.
    """
    zahl = _zahl(wert)
    if zahl is None:
        return trdf.MARKE
    return str(zahl.quantize(D("0.1"))).replace(".", ",") + " t/ha"


# --------------------------------------------------------------------------
# Der Block als Daten - fuer die Weboberflaeche, die ihn als SVG zeichnet
# --------------------------------------------------------------------------
def _lage(marke, unten, hoehe, text=None) -> dict:
    """Eine Lage von `unten` bis `unten + hoehe` - Anteile der Bildhoehe."""
    return {"marke": marke, "unten": float(unten), "hoehe": float(hoehe),
            "farbe": FARBEN[marke], "schrift": SCHRIFTFARBE[marke],
            "text": text}


def blockdaten(probe: str, roh: dict, gerechnet: dict) -> dict:
    """Alles, was im Blockfenster steht - Lagen, Schaufel, Zahlen.

    Die Hoehen kommen als Anteil der Bildhoehe (0 bis 1, von unten);
    wie gross gezeichnet wird, entscheidet die Oberflaeche. Gerechnet
    wird wie im Tk-Fenster: dieselben Lagen, dieselben Texte.
    """
    art = _zahl(roh.get(VARIANTE))
    variante = int(art) if art is not None else None
    lagen = aus_werten(roh, gerechnet)
    bild, unten = [], D(0)
    for marke, anteil in lagen:
        bild.append(_lage(marke, unten / GANZ, anteil / GANZ,
                          prozent(anteil)))
        unten += anteil
    legende = [{"farbe": FARBEN[marke], "text": BESCHRIFTUNG[marke],
                "wert": prozent(anteil)}
               for marke, anteil in lagen]

    teile = schaufel(roh, gerechnet)
    schaufelbild, schaufellegende, hundert = [], [], None
    if teile:
        bezug = teile["bezug"]
        gesamt = bezug + teile.get(GROB_GROSS, D(0))
        unten = D(0)
        if teile.get(FEINBODEN):
            schaufelbild.append(_lage(FEINBODEN, unten / gesamt,
                                      teile[FEINBODEN] / gesamt,
                                      anteil_von(teile[FEINBODEN], bezug)))
            unten += teile[FEINBODEN]
        if teile.get(GROB_KLEIN):
            # Innen geteilt, aussen eine Zahl: die feine Fraktion als
            # eigener Streifen, die Zahl gilt der ganzen Lage.
            feinst = teile.get(GROB_FEINST)
            text = anteil_von(teile[GROB_KLEIN], bezug)
            if feinst:
                schaufelbild.append(_lage(GROB_FEINST, unten / gesamt,
                                          feinst / gesamt))
                schaufelbild.append(_lage(GROB_MITTEL,
                                          (unten + feinst) / gesamt,
                                          teile[GROB_MITTEL] / gesamt))
                schaufelbild.append({**_lage(GROB_KLEIN, unten / gesamt,
                                             teile[GROB_KLEIN] / gesamt,
                                             text), "nur_text": True})
            else:
                schaufelbild.append(_lage(GROB_KLEIN, unten / gesamt,
                                          teile[GROB_KLEIN] / gesamt, text))
            unten += teile[GROB_KLEIN]
        if teile.get(GROB_GROSS):
            schaufelbild.append(_lage(GROB_GROSS, unten / gesamt,
                                      teile[GROB_GROSS] / gesamt,
                                      anteil_von(teile[GROB_GROSS], bezug)))
            hundert = float(unten / gesamt)
        for marke in (FEINBODEN, GROB_KLEIN, GROB_MITTEL, GROB_FEINST,
                      GROB_GROSS):
            if teile.get(marke):
                schaufellegende.append({
                    "farbe": FARBEN[marke],
                    "text": BESCHRIFTUNG_SCHAUFEL[marke],
                    "wert": anteil_von(teile[marke], bezug)})
    return {
        "probe": probe, "variante": variante,
        "dichte": dichtetext(gerechnet.get(DICHTE)),
        "vorrat": vorratstext(gerechnet.get(VORRAT)),
        "skelett": prozent(gerechnet.get(SKELETT)),
        "lagen": bild, "legende": legende,
        "schaufel": schaufelbild, "schaufellegende": schaufellegende,
        "hundert": hundert,
        "gruppen": [{"name": name,
                     "zeilen": [{"text": text, "wert": wert}
                                for text, wert in zeilen]}
                    for name, zeilen in gruppen(roh)]}


# Die Fenster stehen in trdfblockfenster.py - die Weboberflaeche kommt ohne Tk
# aus. Wer sie hier sucht, findet sie trotzdem.
_FENSTER = ('Blockfenster', 'zeigen', 'BREITE', 'BREITE_SCHAUFEL', 'HOEHE', 'RAND', 'BESCHRIFTBAR')


def __getattr__(name):
    if name in _FENSTER:
        # importlib, damit PyInstaller die Tk-Fenster nicht in die
        # Web-exe packt.
        import importlib
        return getattr(importlib.import_module("trdfblockfenster"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
