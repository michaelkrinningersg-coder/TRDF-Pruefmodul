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

import tkinter as tk

import trdf
import trdfrohpruefung
from trdf import D
from widgets import Style

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

# In welcher Reihenfolge die Lagen in der Legende stehen - fuer Probe und
# Schaufelprobe dieselbe, damit Feinboden neben Feinboden steht, 2 bis 63
# mm neben 2 bis 63 mm und ueber 63 mm neben ueber 63 mm. Die beiden
# Haelften der Lage 2 bis 63 mm gibt es nur in der Schaufelprobe.
LEGENDENFOLGE = (FEINBODEN, GROB_KLEIN, GROB_MITTEL, GROB_FEINST, GROB_GROSS)

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
# Das Fenster
# --------------------------------------------------------------------------
BREITE = 140          # der Block der Probe
BREITE_SCHAUFEL = 120
HOEHE = 300

# Die hundert Prozent stehen als gestrichelte Linie da, ohne Beschriftung:
# neben dem Block braeuchte sie einen leeren Streifen, im Block liegt sie
# im Weg. Was ueber der Linie steht, sagt die Legende darunter.
RAND = 20

# Ab dieser Hoehe traegt eine Lage ihre Zahl; darunter stuende sie ueber
# den Rand hinaus.
BESCHRIFTBAR = 15


class Blockfenster(tk.Toplevel):
    """Ein kleines Fenster mit dem Block einer Probe.

    Links die Probe, wie sie im Boden stand; in der Mitte die Zahlen,
    aus denen sie gerechnet ist; rechts die Schaufelprobe, wie sie im
    Labor auf der Waage lag. Je Probe eines - ein zweiter Klick auf
    dieselbe Probe frischt es auf, statt ein zweites zu oeffnen.
    """

    def __init__(self, eltern, probe: str, lagen, dichte=None, variante=None,
                 skelett=None, vorrat=None, roh=None, gerechnet=None,
                 bei_wechsel=None):
        super().__init__(eltern)
        self.title(f"Bodenblock {probe}")
        self.configure(bg=Style.BG)
        self.resizable(False, False)
        # Ueber dem Hauptfenster bleiben: wer in der Tabelle einen
        # Rohwert aendert, will den Block dabei sehen und nicht erst
        # wieder hervorholen. `transient` haelt ihn oben, ohne ihn
        # ueber andere Programme zu legen.
        try:
            self.transient(eltern.winfo_toplevel())
        except tk.TclError:
            pass
        self.probe = probe
        self.lagen = list(lagen)
        # Pfeil rauf und runter blaettert durch die Probenliste: der
        # Block ist zum Vergleichen da, und dafuer muss man die Nachbarn
        # sehen koennen, ohne jedes Mal in die Tabelle zurueckzugehen.
        self._bei_wechsel = bei_wechsel
        for taste, richtung in (("<Up>", -1), ("<Down>", 1),
                                ("<Prior>", -1), ("<Next>", 1)):
            self.bind(taste, lambda ereignis, wohin=richtung:
                      self._wechseln(wohin))
        self.focus_set()

        kopfzeile = tk.Frame(self, bg=Style.BG)
        kopfzeile.pack(fill="x", padx=RAND, pady=(14, 2))
        self.kopf = tk.Label(kopfzeile, text="", bg=Style.BG, fg=Style.TEXT,
                             font=Style.font(11, "bold"), anchor="w")
        self.kopf.pack(side="left")
        tk.Label(self, text="Beide Bilder von unten nach oben: Feinboden, "
                            "gewogener Grobboden, geschaetzter Grobboden. "
                            "Links die Probe im Boden, rechts die "
                            "Schaufelprobe nach Volumen; ueber der "
                            "gestrichelten Linie steht, was groesser als 63 "
                            "mm war, und der hellere Streifen in der Lage 2 "
                            "bis 63 mm ist die Fraktion 2 bis 6,3 mm.",
                 bg=Style.BG, fg=Style.MUTED, font=Style.font(9), anchor="w",
                 justify="left", wraplength=640).pack(
            fill="x", padx=RAND, pady=(0, 10))

        mitte = tk.Frame(self, bg=Style.BG)
        mitte.pack(fill="both", expand=True, padx=RAND)

        links = tk.Frame(mitte, bg=Style.BG)
        links.pack(side="left", anchor="n")
        tk.Label(links, text="Probe", bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").pack(fill="x")
        self.bild = tk.Canvas(links, width=BREITE, height=HOEHE,
                              bg=Style.CARD, highlightthickness=1,
                              highlightbackground=Style.BORDER)
        self.bild.pack(anchor="w")

        daneben = tk.Frame(mitte, bg=Style.BG)
        daneben.pack(side="left", fill="y", padx=(18, 0), anchor="n")
        tk.Label(daneben, text="Trockenrohdichte Feinboden", bg=Style.BG,
                 fg=Style.MUTED, font=Style.font(9), anchor="w").pack(
            fill="x")
        self.feld_dichte = tk.Label(daneben, text="", bg=Style.BG,
                                    fg=Style.TEXT, font=Style.font(16, "bold"),
                                    anchor="w")
        self.feld_dichte.pack(fill="x")
        paar = tk.Frame(daneben, bg=Style.BG)
        paar.pack(fill="x", pady=(8, 0))
        self.feld_vorrat = self._kennzahl(paar, "Feinbodenvorrat")
        self.feld_skelett = self._kennzahl(paar, "Skelettanteil")
        self.zahlen = tk.Frame(daneben, bg=Style.BG)
        self.zahlen.pack(fill="x", pady=(10, 0))

        # Die Schaufelprobe steht nur da, wenn sie gewogen wurde - ohne
        # Masse (0 oder x) faellt die ganze Spalte weg.
        self.rechts = rechts = tk.Frame(mitte, bg=Style.BG)
        rechts.pack(side="left", anchor="n", padx=(18, 0))
        tk.Label(rechts, text="Schaufelprobe", bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").pack(fill="x")
        self.schaufelbild = tk.Canvas(rechts, width=BREITE_SCHAUFEL,
                                      height=HOEHE, bg=Style.CARD,
                                      highlightthickness=1,
                                      highlightbackground=Style.BORDER)
        self.schaufelbild.pack(anchor="w")

        # Die Legenden unter beiden Bildern, nebeneinander: je Lage eine
        # Zeile, die Prozente rechtsbuendig untereinander.
        legenden = tk.Frame(self, bg=Style.BG)
        legenden.pack(fill="x", padx=RAND, pady=(10, 0))
        self.legende = tk.Frame(legenden, bg=Style.BG)
        self.legende.pack(side="left", anchor="n")
        self.schaufellegende = tk.Frame(legenden, bg=Style.BG)
        self.schaufellegende.pack(side="left", anchor="n", padx=(28, 0))

        tk.Frame(self, bg=Style.BG, height=RAND).pack(fill="x")
        self._stellen(lagen, dichte, variante, skelett, vorrat, roh or {},
                      gerechnet or {})
        self.bind("<Escape>", lambda e: self.destroy())

    @staticmethod
    def _kennzahl(eltern, beschriftung: str) -> tk.Label:
        spalte = tk.Frame(eltern, bg=Style.BG)
        spalte.pack(side="left", padx=(0, 18))
        tk.Label(spalte, text=beschriftung, bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").pack(fill="x")
        feld = tk.Label(spalte, text="", bg=Style.BG, fg=Style.TEXT,
                        font=Style.font(12, "bold"), anchor="w")
        feld.pack(fill="x")
        return feld

    # ------------------------------------------------------------ Stellen
    def _stellen(self, lagen, dichte, variante, skelett, vorrat, roh,
                 gerechnet):
        """Setzt alle Zahlen und zeichnet beide Bloecke neu."""
        self.lagen = list(lagen)
        self.roh, self.gerechnet = dict(roh), dict(gerechnet)
        self.schaufelteile = schaufel(self.roh, self.gerechnet)
        self.kopf.config(text=f"Probe {self.probe}" + (
            f"  ·  Variante {variante}" if variante is not None else ""))
        self.feld_dichte.config(text=dichtetext(dichte))
        self.feld_vorrat.config(text=vorratstext(vorrat))
        self.feld_skelett.config(text=prozent(skelett))
        self._zeichnen()
        self._schaufel_zeichnen()
        self._zahlen_zeigen()
        self._legende_zeichnen()

    def _wechseln(self, richtung: int):
        """Eine Probe weiter - die Liste fuehrt der Aufrufer."""
        if self._bei_wechsel is not None:
            self._bei_wechsel(self, richtung)
        return "break"

    def uebernehmen(self, probe: str, roh: dict, gerechnet: dict):
        """Dasselbe Fenster, eine andere Probe."""
        self.probe = probe
        self.title(f"Bodenblock {probe}")
        self.neu_zeichnen(roh, gerechnet)

    def neu_zeichnen(self, roh: dict, gerechnet: dict):
        """Nimmt einen neuen Stand an - dasselbe Fenster, andere Zahlen."""
        art = _zahl(roh.get(VARIANTE))
        self._stellen(aus_werten(roh, gerechnet), gerechnet.get(DICHTE),
                      int(art) if art is not None else None,
                      gerechnet.get(SKELETT), gerechnet.get(VORRAT),
                      roh, gerechnet)

    # ----------------------------------------------------------- Zeichnen
    def _lage(self, flaeche, marke, unten, hoehe, breite, text=None):
        """Eine Lage auf die Flaeche legen - mit ihrer Zahl, wenn Platz ist."""
        oben = unten - hoehe
        flaeche.create_rectangle(0, oben, breite, unten,
                                 fill=FARBEN[marke], width=0)
        if hoehe >= BESCHRIFTBAR and text:
            flaeche.create_text(breite / 2, (oben + unten) / 2, text=text,
                                fill=SCHRIFTFARBE[marke],
                                font=Style.font(9, "bold"))
        return oben

    def _zeichnen(self):
        """Die Lagen der Probe von unten nach oben."""
        self.bild.delete("all")
        if not self.lagen:
            self.bild.create_text(BREITE / 2, HOEHE / 2,
                                  text="kein Skelettanteil\nberechnet",
                                  fill=Style.MUTED, font=Style.font(9),
                                  justify="center")
            return
        unten = float(HOEHE)
        for marke, anteil in self.lagen:
            unten = self._lage(self.bild, marke, unten,
                               float(anteil) / 100.0 * HOEHE, BREITE,
                               prozent(anteil))

    def _schaufel_zeichnen(self):
        """Die Schaufelprobe - Bezug unten, was ueber 63 mm war obendrauf."""
        self.schaufelbild.delete("all")
        teile = self.schaufelteile
        if not teile:
            self.rechts.pack_forget()
            return
        if not self.rechts.winfo_manager():
            self.rechts.pack(side="left", anchor="n", padx=(18, 0))
        bezug = teile["bezug"]
        gesamt = bezug + teile.get(GROB_GROSS, D(0))
        skala = float(HOEHE) / float(gesamt) if gesamt > 0 else 0.0
        unten = float(HOEHE)
        if teile.get(FEINBODEN):
            unten = self._lage(self.schaufelbild, FEINBODEN, unten,
                               float(teile[FEINBODEN]) * skala,
                               BREITE_SCHAUFEL,
                               anteil_von(teile[FEINBODEN], bezug))
        if teile.get(GROB_KLEIN):
            unten = self._grobboden(teile, bezug, skala, unten)
        if teile.get(GROB_GROSS):
            self._lage(self.schaufelbild, GROB_GROSS, unten,
                       float(teile[GROB_GROSS]) * skala, BREITE_SCHAUFEL,
                       anteil_von(teile[GROB_GROSS], bezug))
            self._hundert(unten)

    def _hundert(self, hoehe: float):
        """Die Linie der hundert Prozent - zuletzt, also ueber den Lagen.

        Nur die Linie: eine Beschriftung braucht entweder Platz neben
        dem Block oder liegt in ihm im Weg. Dass darueber der Grobboden
        ueber 63 mm steht, sagt die Legende darunter.
        """
        self.schaufelbild.create_line(0, hoehe, BREITE_SCHAUFEL, hoehe,
                                      fill="#111827", dash=(4, 3))

    def _grobboden(self, teile: dict, bezug, skala: float, unten: float):
        """Die Lage 2 bis 63 mm - innen geteilt, aussen eine Zahl.

        Steckt eine Fraktion 2 bis 6,3 mm darin, wird sie als eigener
        heller Streifen gezeichnet, bekommt aber keine eigene Zahl: im
        Block steht der Anteil der ganzen Lage, und was davon die feine
        Fraktion ist, sagt die Legende darunter. Zwei Zahlen
        uebereinander liest man sonst als zwei Lagen.
        """
        hoehe = float(teile[GROB_KLEIN]) * skala
        oben = unten - hoehe
        feinst = teile.get(GROB_FEINST)
        if feinst:
            self._lage(self.schaufelbild, GROB_FEINST, unten,
                       float(feinst) * skala, BREITE_SCHAUFEL)
            self._lage(self.schaufelbild, GROB_MITTEL,
                       unten - float(feinst) * skala,
                       float(teile[GROB_MITTEL]) * skala, BREITE_SCHAUFEL)
        else:
            self._lage(self.schaufelbild, GROB_KLEIN, unten, hoehe,
                       BREITE_SCHAUFEL)
        if hoehe >= BESCHRIFTBAR:
            self.schaufelbild.create_text(
                BREITE_SCHAUFEL / 2, (oben + unten) / 2,
                text=anteil_von(teile[GROB_KLEIN], bezug),
                fill=SCHRIFTFARBE[GROB_KLEIN], font=Style.font(9, "bold"))
        return oben

    # ------------------------------------------------------------ Zahlen
    def _zahlen_zeigen(self):
        """Die Rohwerte, nach Geraet geordnet."""
        for kind in self.zahlen.winfo_children():
            kind.destroy()
        for name, zeilen in gruppen(self.roh):
            tk.Label(self.zahlen, text=name, bg=Style.BG, fg=Style.MUTED,
                     font=Style.font(9, "bold"), anchor="w").pack(
                fill="x", pady=(6, 0))
            for beschriftung, wert in zeilen:
                zeile = tk.Frame(self.zahlen, bg=Style.BG)
                zeile.pack(fill="x")
                tk.Label(zeile, text=beschriftung, bg=Style.BG,
                         fg=Style.MUTED, font=Style.font(9), anchor="w",
                         width=22).pack(side="left")
                tk.Label(zeile, text=wert, bg=Style.BG, fg=Style.TEXT,
                         font=Style.font(9), anchor="w").pack(side="left")

    def _legende_zeichnen(self):
        """Was welche Farbe bedeutet - nur die Lagen, die vorkommen.

        Probe und Schaufelprobe stehen nebeneinander, und dieselbe Lage
        steht in derselben Zeile: Feinboden neben Feinboden, 2 bis 63 mm
        neben 2 bis 63 mm, ueber 63 mm neben ueber 63 mm. Fehlt eine Lage
        auf einer Seite, bleibt dort die Zeile leer. Die beiden Haelften
        der Lage 2 bis 63 mm gibt es nur in der Schaufelprobe.
        """
        for rahmen in (self.legende, self.schaufellegende):
            for kind in rahmen.winfo_children():
                kind.destroy()
        probe = {marke: (BESCHRIFTUNG[marke], prozent(anteil))
                 for marke, anteil in self.lagen}
        teile = self.schaufelteile
        schaufel = {marke: (BESCHRIFTUNG_SCHAUFEL[marke],
                            anteil_von(teile[marke], teile["bezug"]))
                    for marke in LEGENDENFOLGE if teile and teile.get(marke)}
        seiten = [(self.legende, "Probe", probe)]
        if schaufel:
            seiten.append((self.schaufellegende, "Schaufelprobe", schaufel))
        folge = [marke for marke in LEGENDENFOLGE
                 if any(marke in eintraege for _r, _t, eintraege in seiten)]
        for rahmen, titel, eintraege in seiten:
            if not eintraege:
                continue
            self._legendenkopf(rahmen, titel)
            for zeile, marke in enumerate(folge, start=1):
                if marke in eintraege:
                    self._legendenzeile(rahmen, marke, *eintraege[marke],
                                        zeile=zeile)
                else:
                    # Platzhalter: haelt die Zeile so hoch wie nebenan.
                    tk.Label(rahmen, text="", bg=Style.BG,
                             font=Style.font(9)).grid(row=zeile, column=1)

    @staticmethod
    def _legendenkopf(rahmen, titel):
        tk.Label(rahmen, text=titel, bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))

    @staticmethod
    def _legendenzeile(rahmen, marke, text, wert, zeile=None):
        """Eine Zeile: Farbe, Name, Prozent - der Prozent rechtsbuendig."""
        if zeile is None:
            zeile = rahmen.grid_size()[1]
        tk.Frame(rahmen, bg=FARBEN[marke], width=12, height=12).grid(
            row=zeile, column=0, sticky="w", pady=1)
        tk.Label(rahmen, text=text, bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(9), anchor="w").grid(
            row=zeile, column=1, sticky="w", padx=(6, 12))
        tk.Label(rahmen, text=wert, bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(9, "bold"), anchor="e").grid(
            row=zeile, column=2, sticky="e")


def zeigen(eltern, probe: str, roh: dict, gerechnet: dict,
           bei_wechsel=None) -> Blockfenster:
    """Oeffnet den Block zu einer Probe."""
    art = _zahl(roh.get(VARIANTE))
    return Blockfenster(eltern, probe, aus_werten(roh, gerechnet),
                        dichte=gerechnet.get(DICHTE),
                        variante=int(art) if art is not None else None,
                        skelett=gerechnet.get(SKELETT),
                        vorrat=gerechnet.get(VORRAT),
                        roh=roh, gerechnet=gerechnet,
                        bei_wechsel=bei_wechsel)
