"""
TRDF-Pruefmodul - eine Tabelle, in der sich Zellen aendern lassen
=================================================================

Die Anzeigetabelle (tabelle.py) zeigt, was da ist. Hier soll etwas
anderes gehen: einen Rohwert von Hand ueberschreiben und sofort sehen,
was daraus folgt. Wer die TRDF-Rechnung prueft, will genau das - "und
wenn die Trockenrohdichte 1,8 waere, kaeme dann das heraus, was das LIMS
gebucht hat?".

Wie es sich bedienen laesst
---------------------------
Ein Klick oeffnet die Zelle, der Inhalt ist markiert: wer tippt,
ersetzt ihn, ohne vorher loeschen zu muessen. Von dort:

    Tab / Shift+Tab   die naechste Zelle in derselben Zeile
    Pfeile            in alle vier Richtungen
    Eingabe           uebernehmen und eine Zeile tiefer
    Esc               verwerfen

Am Zeilenende springt Tab in die naechste Zeile - so laesst sich eine
Probe in einem Zug durchgehen. Dazu wie in Excel:

    Strg+C / Strg+V   Zelle kopieren / einen Block aus Excel einfuegen
    Strg+D            den Wert der Zelle darueber uebernehmen
    Strg+Shift+D      den Wert bis ans Ende der Spalte nach unten kopieren
    Strg+L            dasselbe, aber nur in die leeren Zellen
    Strg+I            nach unten hochzaehlen: Wert, Wert+1, Wert+2 ...
    Strg+E            die leeren Zellen der Zeile fuellen
    Strg+Shift+E      die leeren Zellen der Spalte fuellen
                      (beides nur, wenn der Aufrufer sagt, womit - siehe
                      `bei_fuellen`)

Was "leer" heisst, kann der Aufrufer sagen (`ist_leer`): eine Tabelle,
die eine leere Zelle als "x" anzeigt, weiss es selbst nicht.

Warum ein Textfeld und keine Treeview
-------------------------------------
Weil eine Treeview nur ganze Zeilen faerben kann. Beim Pruefen ist aber
die einzelne Zahl die Aussage: *dieser* Wert wurde von Hand bewegt,
*jene* Groesse hat sich dadurch verschoben, und die daneben nicht. Eine
getoente Zeile sagt "hier ist irgendetwas", und danach sucht man wieder
mit dem Finger.

Ein tk.Text kann jede Zelle einzeln einfaerben - dieselbe Technik, mit
der das Zellenraster im Ergebnis-Reiter arbeitet. Die Spalten stehen
dafuer in fester Zeichenbreite, und die Kopfzeile laeuft in einem
eigenen Feld darueber mit.

Warum ein wanderndes Feld
-------------------------
Eine Serie hat dreihundertsechzig Proben und sechzehn Rohwerte, also
fast sechstausend Zellen. Ebenso viele Eingabefelder anzulegen dauert
Sekunden und frisst Speicher. Deshalb gibt es *ein* Feld, das an die
Zelle wandert, in der gerade gearbeitet wird - der Text darunter zeigt
den Rest.
"""

from __future__ import annotations

import decimal
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from widgets import Style

# Zellen, die auffallen sollen, und woran man sie erkennt.
#
# Rot ist das, was gerade von Hand bewegt wurde - der Wert und alles,
# was sich durch ihn verschoben hat. Amber ist der Befund: gebucht und
# gerechnet gehen auseinander. Beides rot zu zeigen hiesse, zwei
# verschiedene Aussagen gleich aussehen zu lassen.
FARBEN = {"geaendert": "#b91c1c", "abweichung": "#b45309",
          "berechnet": "#334155", "fehlt": "#94a3b8",
          # Die Abstufungen der Qualitaetspruefung. Sie sagen nicht
          # "hier stimmt etwas nicht", sondern wie sehr: ein Wert ueber
          # der Schwelle (rot), einer darunter, der nur zusammen mit
          # einem zweiten Befund zaehlt (gelb), und einer, der kein
          # Befund ist, aber jede Rechnung darueber unsicher macht
          # (dezent). Drei Aussagen in derselben Farbe waeren keine.
          "hoch": "#b91c1c", "erhoeht": "#92400e", "gering": "#9a3412",
          # Ein Wert, der nicht von der Spalte kommt, in der er steht -
          # das aeltere Geraet, wenn am neueren nichts stand.
          "ersatz": "#be123c",
          # Und was aufgeht: gruen kommt in dieser Tabelle nur hier
          # vor, deshalb faellt es auf, ohne laut zu sein.
          "stimmt": "#15803d",
          # Zwei Staende der Kenndaten auf derselben Messung: rot auf
          # gelb. Es ist kein Messfehler - die Zahlen sind richtig
          # gebucht -, aber sie sind nicht vergleichbar, und das ist
          # der Befund, den man beim Ueberfliegen nicht uebersehen
          # darf.
          "kenndaten": "#b91c1c",
          # Ein Wert, der auf der Liste an das LIMS steht: noch nicht
          # geschrieben, aber schon entschieden.
          "bereit": "#1d4ed8",
          # Und eine Zahl, an der jemand von Hand gedreht hat - im
          # Profilvergleich eine Summe, deren Horizonte einer selbst
          # zusammengestellt hat. Blau und nicht amber: amber sagt
          # "hier fehlt etwas", und hier fehlt nichts, hier hat
          # jemand entschieden.
          "handwahl": "#4338ca",
          # Und beides zugleich: jemand hat gedreht, *und* der Summe
          # fehlen Horizonte. Violett zwischen dem Amber der Luecke
          # und dem Blau der Handwahl - es ist keine dritte Aussage,
          # sondern die beiden zusammen, und eine der beiden Farben
          # allein verschwiege die andere.
          "handluecke": "#7e22ce",
          # Und eine Aussage, die kein Urteil ist: hier liess sich
          # nicht pruefen, und das ist kein Befund. Weiss - denn jede
          # Farbe hiesse etwas, und hier ist nichts zu sagen.
          "unbeurteilt": "#334155",
          # Die drei Zeilen eines Paerchens in der Nachmessung: was im
          # LIMS steht, was nachgemessen wurde, und wie weit die
          # beiden auseinanderliegen. Jede bekommt ihren Grund, sonst
          # liest man drei Zeilen als drei Proben.
          "zeile_lims": "#334155", "zeile_neu": "#9a3412",
          "zeile_abw": "#1e40af"}
HINTERGRUND = {"geaendert": "#fee2e2", "abweichung": "#fef3c7",
               "hoch": "#fee2e2", "erhoeht": "#fef9c3",
               "gering": "#fff7ed", "stimmt": "#dcfce7",
               # Kein Befund, sondern eine Zusammengehoerigkeit: so
               # zart, dass sie nur beim Ueberfliegen wirkt.
               "gruppe": "#eef2f7",
               "kenndaten": "#fef08a", "bereit": "#dbeafe",
               "handwahl": "#e0e7ff",
               "handluecke": "#f3e8ff",
               "unbeurteilt": "#ffffff",
               "zeile_lims": "#f1f5f9", "zeile_neu": "#fff7ed",
               "zeile_abw": "#eff6ff"}

# Die Zeile, auf die eine gezogene Zeile fallen wuerde. Kraeftiger als
# die Maus-Zeile: hier soll man sehen, wohin man gerade zielt.
FARBE_ZIEL = "#dbeafe"
TAG_ZIEL = "ziehziel"

# Wie weit die Maus wandern muss, bis aus dem Klick ein Zug wird. Ohne
# diese Schwelle waere jeder Klick mit zittriger Hand ein Verschieben.
ZIEHSCHWELLE = 4

# Was beim Ziehen am Zeiger haengt: ein Schild mit der Zeile, die
# gerade wandert. Bei dreissig Zeilen weiss man sonst nach dem dritten
# Zug nicht mehr, welche man gegriffen hat - und waehrend die anderen
# Zeilen darunter zusammenruecken, ist das Schild das einzige, was
# stillsteht.
FARBE_ZUG = "#1d4ed8"
HINTERGRUND_ZUG = "#dbeafe"
# Ein Stueck neben dem Zeiger, sonst verdeckt das Schild die Stelle,
# auf die man zielt.
ZUG_ABSTAND = 14

# Die Zeile, die gerade gewaehlt ist: die Probe, deren Bodenblock
# offen steht. Wer im Blockbild mit den Pfeilen durch die Serie
# blaettert, sieht so in der Tabelle mit, wo er ist - kraeftiger als
# die Maus-Zeile, denn sie bleibt stehen, und zarter als ein Befund.
FARBE_AUSWAHL = "#dbe8fa"
TAG_AUSWAHL = "auswahl"

# Die Zeile unter dem Mauszeiger. Bei siebenundzwanzig Spalten verliert
# das Auge auf dem Weg nach rechts die Zeile; eine Spur Hintergrund
# haelt sie zusammen. So zart, dass sie neben einem Befund nicht
# auffaellt - und sie liegt auch unter ihm: eine rote Zelle bleibt rot.
FARBE_MAUSZEILE = "#eef4fb"
TAG_MAUSZEILE = "mauszeile"

# Was zwischen zwei Spalten steht. Ein Strich statt eines Leerzeichens:
# bei zwanzig Zahlenspalten sagt ein Abstand allein nicht mehr, wo die
# eine aufhoert und die naechste anfaengt - das Auge rutscht in die
# Nachbarspalte. Er ist ein Zeichen breit wie das Leerzeichen vorher,
# also bleibt die Rechnerei mit den Spaltenstellen dieselbe.
TRENNER = "│"
LUECKE = len(TRENNER)

# Und er faellt nicht auf: er soll die Spalten trennen, nicht mit den
# Zahlen um Aufmerksamkeit streiten.
FARBE_TRENNER = "#cbd5e1"

# Zwei kraeftigere Striche fuer Tabellen, in denen Spalten zu Bloecken
# gehoeren: bei fuenf Spalten je Pruefmethode und einem Dutzend
# Pruefmethoden sagt ein gleichmaessiger Strich nicht mehr, wo ein
# Block aufhoert. Der erste trennt die Bloecke, der zweite die groesseren
# Einheiten darueber - bei der Wiederholungspruefung die Pruefmethoden
# und die Geraetemethoden.
FARBE_TRENNER_STARK = "#64748b"
FARBE_TRENNER_GRUPPE = "#1e293b"
TAG_TRENNER_STARK = "trenner_stark"
TAG_TRENNER_GRUPPE = "trenner_gruppe"

# Und die Trennung in der anderen Richtung: wo eine Probe mehrere
# Zeilen hat - zwei Wiederholungen, drei Standardmessungen -, sagt ein
# Strich zwischen den Spalten nichts darueber, wo die eine Probe
# aufhoert. Jede zweite Gruppe bekommt deshalb einen Hauch
# Hintergrund. Er liegt unter allem: eine rote Zelle bleibt rot.
FARBE_STREIFEN = "#eef2f7"
TAG_STREIFEN = "gruppenstreifen"

def _kopfzeilen(text) -> list:
    """Eine Ueberschrift in ihre Zeilen - "" gibt keine.

    Angenommen wird beides: eine Liste von Zeilen und ein Text mit
    Umbruechen. Leere Zeilen fallen weg - eine Luecke in der Kopfzeile
    waere eine Spalte, die nichts sagt und trotzdem Hoehe braucht.
    """
    if text is None:
        return []
    teile = (text if isinstance(text, (list, tuple))
             else str(text).split("\n"))
    return [str(teil).strip() for teil in teile if str(teil).strip()]


# Wie lange die Maus ueber einer Spaltenueberschrift stehen muss, bis
# der Hinweis kommt - dieselbe Verzoegerung wie bei den Knoepfen. Wer
# nur hinueberfaehrt, soll nichts aufblitzen sehen.
KOPF_VERZOEGERUNG = 600

# Wenn nichts anderes gesagt ist, so breit wie die Anzeigetabelle es
# hielt: knapp hundert Punkte.
VORGABEBREITE = 96

# Eine mitwachsende Spalte richtet sich nach ihrem laengsten Eintrag.
# Steht ueberhaupt etwas darin, wird sie ausserdem ein Vielfaches ihrer
# Vorgabe breit: eine Spalte fuer Saetze, die so breit ist wie eine fuer
# Zahlen, schneidet jeden Satz ab. Nach oben ist Schluss, sonst schoebe
# ein einziger langer Eintrag alles andere aus dem Blick.
MITWACHSEND_VIELFACHES = 3
MITWACHSEND_HOECHSTENS = 150


def _als_zahl(text):
    """Eine Zahl aus der Zelle - auch mit Dezimalkomma; sonst None."""
    try:
        return decimal.Decimal(str(text).strip().replace(",", "."))
    except (decimal.InvalidOperation, ValueError):
        return None


def _zahltext(zahl, vorlage: str) -> str:
    """Eine Zahl so geschrieben wie die Vorlage - Komma bleibt Komma."""
    text = format(zahl, "f")
    return text.replace(".", ",") if "," in str(vorlage) else text


def zerlegen(inhalt: str) -> list:
    """Was aus der Zwischenablage kommt, als Zeilen und Spalten.

    Excel legt einen kopierten Bereich mit Tabulatoren zwischen den
    Spalten und Zeilenumbruechen zwischen den Zeilen ab - genau so kommt
    er hier an. Der letzte Umbruch gehoert zur letzten Zeile und nicht zu
    einer weiteren.
    """
    text = str(inhalt or "").replace("\r\n", "\n").replace("\r", "\n")
    while text.endswith("\n"):
        text = text[:-1]
    return [zeile.split("\t") for zeile in text.split("\n")]


class Eingaberaster(tk.Frame):
    """Eine Tabelle, deren Zellen sich einzeln faerben und aendern lassen."""

    def __init__(self, eltern, hoehe=14, bei_aenderung=None, bei_klick=None,
                 bei_block=None, schriftgroesse=9, zeilenluft=0,
                 bei_verschieben=None, bei_rechtsklick=None,
                 bei_doppelklick=None, bei_kopfklick=None, bei_zeile=None,
                 bei_fuellen=None, ist_leer=None, bei_nach_unten=None):
        super().__init__(eltern, bg=Style.CARD,
                         highlightbackground=Style.BORDER,
                         highlightthickness=1)
        self.bei_aenderung = bei_aenderung
        # Was in einer Spalte geschieht, in der nicht getippt wird. Der
        # Klick auf die Probennummer oeffnet so ihr Bild - ohne dass
        # diese Tabelle wissen muesste, was ein Bodenblock ist.
        self.bei_klick = bei_klick
        # Ein ganzer Block auf einmal - aus der Zwischenablage. Wird er
        # nicht gebraucht, meldet sich jede Zelle einzeln.
        self.bei_block = bei_block
        # Eine Zeile mit der Maus an eine andere Stelle ziehen. Wird das
        # nicht gebraucht, bleibt ein Zug ein Klick - und niemand
        # verschiebt aus Versehen etwas.
        self.bei_verschieben = bei_verschieben
        # Die rechte Maustaste auf einer Zelle. Was dann geschieht,
        # weiss die Tabelle nicht - sie sagt nur, wo geklickt wurde.
        # Ohne Angabe tut die rechte Taste nichts, wie bisher.
        self.bei_rechtsklick = bei_rechtsklick
        # Der Doppelklick. Er ist nicht derselbe Griff wie der einfache
        # Klick: der setzt etwas ein, der Doppelklick oeffnet es. Wer
        # nur einsetzen will, soll nicht aus Versehen eine Abfrage
        # anstossen.
        self.bei_doppelklick = bei_doppelklick
        # Ein Klick auf die Spaltenueberschrift. Uebergeben wird der
        # Spaltenname; was damit geschieht - sortieren -, weiss die
        # Tabelle nicht. Ohne Angabe tut der Klick, was er bisher tat:
        # den Hinweis wegnehmen.
        self.bei_kopfklick = bei_kopfklick
        # Die Zeile, in der gerade eine Zelle geoeffnet wurde. Damit
        # kann eine zweite Tabelle mitgehen - etwa die berechneten
        # Groessen ueber den Rohwerten, die dieselbe Probe zeigen.
        self.bei_zeile = bei_zeile
        # Strg+E: die leeren Zellen der offenen Zeile fuellen. Womit und
        # welche, weiss der Aufrufer - hier steht nur die Taste.
        self.bei_fuellen = bei_fuellen
        # Ob eine Zelle leer ist - ohne Angabe: es steht nichts darin.
        self.ist_leer = ist_leer
        # Wohin die Werte gehen, die nach unten kopiert werden. Ohne
        # Angabe wie ein eingefuegter Block (`bei_block`), sonst einzeln.
        self.bei_nach_unten = bei_nach_unten
        self.schrift = ("Consolas", schriftgroesse)
        # Luft ueber und unter der Zeile. Eine hohe Zeile liest sich in
        # einer breiten Tabelle leichter, ohne dass die Schrift so gross
        # werden muss, dass nur noch drei Spalten hineinpassen.
        self.zeilenluft = max(0, int(zeilenluft))
        self._spalten = []
        self._fest = []              # die Spalten, die stehen bleiben
        self._aenderbar = set()      # welche Spalten sich aendern lassen
        # Und welche Zeilen. None heisst "alle" - der Regelfall.
        # Gebraucht, wo eine Tabelle je Probe mehrere Zeilen zeigt und
        # nur eine davon eine Eingabe ist: die Nachmessung stellt den
        # Wert aus dem LIMS, den nachgemessenen und ihre Abweichung
        # untereinander, und getippt wird nur in der Mitte. Ohne das
        # liefe ein Block aus Excel ueber alle drei.
        self._tippzeilen = None
        self._linksbuendig = set()   # davon die, in denen Text steht
        self._titel = {}             # Spalte -> was in der Kopfzeile steht
        self._reihen = []            # die Kennungen in ihrer Reihenfolge
        self._zellen = {}            # (zeile, spalte) -> Text
        self._marken = {}            # (zeile, spalte) -> Marke
        # Womit zuletzt gefuellt wurde - damit dieselbe Tabelle noch
        # einmal aufgebaut werden kann, etwa in einem eigenen, groesseren
        # Fenster. Ohne Fuellung: None, nicht ein leerer Satz - "noch
        # nichts gezeigt" und "nichts zu zeigen" sind zwei Dinge.
        self._fuellung = None
        self._breiten = {}           # Spalte -> Zeichen
        self._anfang = {}            # Spalte -> erste Spalte in ihrem Feld
        # Verbundene Zellen: eine Spalte, mehrere Zeilen, ein Wert.
        # (Zeile, Spalte) -> Kennung der ersten Zeile des Blocks, und
        # umgekehrt die Kennungen je Block.
        self._blockvon = {}
        self._blockzeilen = {}
        self._stark = set()          # Spalten mit kraeftigem Strich davor
        self._gruppen = set()        # und mit dem kraeftigsten

        # Zwei Paare: links das, was stehen bleibt, rechts das, was
        # waagerecht laeuft. Beide haben dieselbe Schrift, dieselbe
        # Zeilenhoehe und dieselbe Zeilenzahl - deshalb stehen ihre
        # Zeilen auf derselben Hoehe, solange sie senkrecht gemeinsam
        # scrollen.
        self.festkopf = self._feld(1)
        self.festtext = self._feld(max(1, hoehe))
        self.kopf = self._feld(1)
        self.text = self._feld(max(1, hoehe))
        senkrecht = tk.Scrollbar(self, orient="vertical",
                                 command=self._senkrecht)
        waagerecht = tk.Scrollbar(self, orient="horizontal",
                                  command=self._waagerecht)
        self.text.configure(yscrollcommand=self._senkrecht_gefolgt,
                            xscrollcommand=self._waagerecht_gefolgt)
        self.kopf.grid(row=0, column=1, sticky="we", padx=(6, 0), pady=(4, 0))
        self.text.grid(row=1, column=1, sticky="nsew", padx=(6, 0),
                       pady=(0, 4))
        senkrecht.grid(row=1, column=2, sticky="ns")
        waagerecht.grid(row=2, column=1, sticky="we")
        self.waagerecht = waagerecht
        self.senkrecht = senkrecht
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        for feld in self._koepfe():
            feld.tag_configure("kopf", foreground=Style.TEXT)
        for feld in self._koepfe() + self._felder():
            feld.tag_configure("trenner", foreground=FARBE_TRENNER)
            feld.tag_configure(TAG_TRENNER_STARK,
                               foreground=FARBE_TRENNER_STARK)
            feld.tag_configure(TAG_TRENNER_GRUPPE,
                               foreground=FARBE_TRENNER_GRUPPE)
        for feld in self._felder():
            for name, farbe in FARBEN.items():
                feld.tag_configure(name, foreground=farbe)
            for name, farbe in HINTERGRUND.items():
                feld.tag_configure(f"{name}_hg", background=farbe)
            feld.tag_configure(TAG_ZIEL, background=FARBE_ZIEL)
            # Unten in der Reihenfolge: jede gefaerbte Zelle sticht sie.
            # Die gewaehlte Zeile liegt ueber der Maus-Zeile - sie sagt
            # mehr, denn sie steht, wo gearbeitet wird.
            feld.tag_configure(TAG_AUSWAHL, background=FARBE_AUSWAHL)
            feld.tag_configure(TAG_MAUSZEILE, background=FARBE_MAUSZEILE)
            feld.tag_configure(TAG_STREIFEN, background=FARBE_STREIFEN)
            feld.tag_lower(TAG_AUSWAHL)
            feld.tag_lower(TAG_MAUSZEILE)
            feld.tag_lower(TAG_STREIFEN)
        self._streifen = []          # die Zeilengruppen, die unterlegt werden
        self._unter_maus = None      # welche Zeile gerade hervorgehoben ist
        self._zug = None             # was gerade gezogen wird
        self._zugschild = None       # das Schild am Zeiger
        self._zugspalten = []        # was darauf steht
        self._gewaehlt = []          # die Zeilen, die unterlegt sind

        # Das eine Feld, das an die Zelle wandert, in der gearbeitet wird -
        # eines je Haelfte, denn ein Feld kann nur in einem Text liegen.
        self.feld = self._eingabefeld(self.text)
        self.festfeld = self._eingabefeld(self.festtext)
        self._aktiv = self.feld
        self._offen = None           # (Zeilenkennung, Spaltenname)
        self._vorher = ""
        # Was ueber einer Spaltenueberschrift steht, wenn die Maus dort
        # wartet. Die Ueberschriften tragen die Kuerzel des LIMS; wer
        # sie nicht auswendig kennt, faehrt hinueber statt die Legende
        # zu oeffnen.
        self._kopfhinweise = {}
        self._kopfspalte = None
        self._kopfwarten = None
        self._kopffenster = None
        # Und was ueber einer *Zelle* steht. Anders als bei den
        # Ueberschriften wird der Text nicht vorgehalten, sondern
        # gefragt: bei dreihundert Zeilen und fuenfzig Spalten waeren
        # es fuenfzehntausend Saetze, von denen einer gelesen wird.
        self._zellquelle = None
        self._zellstelle = None
        self._zellwarten = None
        self._zellfenster = None
        for feld in self._felder():
            feld.bind("<Button-1>", self._angeklickt)
            feld.bind("<B1-Motion>", self._gezogen)
            feld.bind("<ButtonRelease-1>", self._losgelassen)
            feld.bind("<Configure>", lambda e: self.schliessen())
            feld.bind("<Motion>", self._maus_bewegt)
            feld.bind("<Leave>", self._maus_verlassen)
            feld.bind("<Button-3>", self._rechts_geklickt)
            feld.bind("<Double-Button-1>", self._doppelt_geklickt)
        for feld in self._koepfe():
            feld.bind("<Motion>", self._kopf_bewegt)
            feld.bind("<Leave>", lambda e: self._kopf_verlassen())
            feld.bind("<Button-1>", self._kopf_geklickt)
        # Das Mausrad ueber der festen Haelfte rollt die ganze Tabelle:
        # sonst liefe sie unter den festen Spalten weg.
        for ereignis in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.festtext.bind(ereignis, self._gerollt)

    def _kopf_geklickt(self, ereignis):
        """Ein Klick auf eine Spaltenueberschrift.

        Der Hinweis verschwindet - wie bisher -, und der Aufrufer
        erfaehrt, welche Spalte gemeint war. Wer nichts damit vorhat,
        merkt keinen Unterschied.
        """
        self._kopf_verlassen()
        if self.bei_kopfklick is None:
            return None
        feld = ereignis.widget
        spalte = self._spalte_bei(feld, ereignis.x, ereignis.y,
                                  feld is self.festkopf)
        if spalte is None:
            return None
        self.bei_kopfklick(spalte)
        return "break"

    def _felder(self) -> tuple:
        """Die beiden Textfelder mit den Werten - fest und laufend."""
        return (self.text, self.festtext)

    def _koepfe(self) -> tuple:
        return (self.kopf, self.festkopf)

    def _eingabefeld(self, eltern) -> ttk.Entry:
        """Das wandernde Feld - eines je Haelfte, sonst gleich."""
        feld = ttk.Entry(eltern, justify="right", font=self.schrift)
        feld.bind("<Return>", lambda e: self._weiter(1, 0))
        feld.bind("<Escape>", lambda e: self.schliessen())
        feld.bind("<Tab>", lambda e: self._weiter(0, 1))
        feld.bind("<Shift-Tab>", lambda e: self._weiter(0, -1))
        # Unter X11 heisst Shift+Tab am Ende ISO_Left_Tab; Windows kennt
        # den Namen nicht und weist ihn zurueck. Also binden, wo es geht,
        # und sonst weitermachen - <Shift-Tab> traegt dort allein.
        try:
            feld.bind("<ISO_Left_Tab>", lambda e: self._weiter(0, -1))
        except tk.TclError:
            pass
        feld.bind("<Up>", lambda e: self._weiter(-1, 0))
        feld.bind("<Down>", lambda e: self._weiter(1, 0))
        # Auch die Seitwaertspfeile wechseln die Zelle - wie in einer
        # Tabellenkalkulation. Im Feld selbst zu wandern braucht hier
        # niemand: der Inhalt ist beim Oeffnen markiert, und wer tippt,
        # ersetzt ihn ohnehin.
        feld.bind("<Right>", lambda e: self._weiter(0, 1))
        feld.bind("<Left>", lambda e: self._weiter(0, -1))
        for ereignis in ("<Control-v>", "<Control-V>", "<<Paste>>",
                         "<Shift-Insert>"):
            feld.bind(ereignis, self._eingefuegt)
        # Gross geschrieben heisst in Tk: mit Shift. Eine eigene Taste
        # also und nicht dieselbe in zwei Schreibweisen.
        feld.bind("<Control-d>", lambda e: self.von_oben())
        feld.bind("<Control-D>", lambda e: self.nach_unten("alle"))
        feld.bind("<Control-l>", lambda e: self.nach_unten("leere"))
        feld.bind("<Control-L>", lambda e: self.nach_unten("leere"))
        feld.bind("<Control-i>", lambda e: self.nach_unten("plus"))
        feld.bind("<Control-I>", lambda e: self.nach_unten("plus"))
        feld.bind("<Control-e>", lambda e: self._fuellen())
        feld.bind("<Control-E>", lambda e: self._fuellen(spaltenweise=True))
        feld.bind("<FocusOut>", lambda e: self._uebernehmen())
        return feld

    def _feld(self, hoehe: int) -> tk.Text:
        feld = tk.Text(self, height=hoehe, wrap="none", font=self.schrift,
                       bg=Style.CARD, fg=Style.TEXT, bd=0,
                       highlightthickness=0, padx=0, pady=0, cursor="arrow",
                       spacing1=self.zeilenluft, spacing3=self.zeilenluft)
        feld.configure(state="disabled")
        return feld

    # ----------------------------------------------------- Kopf und Koerper
    def _waagerecht(self, *args):
        """Kopf und Koerper laufen gemeinsam - sonst stehen sie versetzt."""
        self.text.xview(*args)
        self.kopf.xview(*args)
        self.schliessen()

    def _waagerecht_gefolgt(self, anfang, ende):
        self.waagerecht.set(anfang, ende)
        self.kopf.xview("moveto", anfang)

    def _senkrecht(self, *args):
        """Beide Haelften zusammen - sonst stuenden die Zeilen versetzt.

        Die feste Haelfte haengt am laufenden Teil und nicht umgekehrt:
        es gibt genau eine Stelle, an der die Zeile entschieden wird,
        und deshalb kann keine der beiden zurueckbleiben.
        """
        self.text.yview(*args)
        self.festtext.yview(*args)
        self.schliessen()

    def _senkrecht_gefolgt(self, anfang, ende):
        self.senkrecht.set(anfang, ende)
        self.festtext.yview("moveto", anfang)

    def _gerollt(self, ereignis):
        """Das Mausrad ueber der festen Haelfte rollt die ganze Tabelle."""
        hinunter = getattr(ereignis, "num", 0) == 5 or \
            getattr(ereignis, "delta", 0) < 0
        self.text.yview_scroll(3 if hinunter else -3, "units")
        return "break"

    def _lose(self) -> list:
        """Die Spalten, die waagerecht mitlaufen."""
        return [name for name in self._spalten if name not in self._fest]

    def _wo(self, spalte: str) -> tk.Text:
        """In welchem der beiden Textfelder eine Spalte steht."""
        return self.festtext if spalte in self._fest else self.text

    def _wo_kopf(self, spalte: str) -> tk.Text:
        return self.festkopf if spalte in self._fest else self.kopf

    def zeichenbreite(self) -> int:
        """Wie breit ein Zeichen dieser Schrift ist - mindestens eins."""
        return max(1, tkfont.Font(font=self.schrift).measure("0"))

    def _spaltenbreiten(self, breiten, zeilen=(), mitwachsend=(),
                        passend=()):
        """Rechnet die Punktbreiten der Aufrufer in Zeichen um.

        Die Aufrufer denken in Punkten, weil sie es von der Treeview so
        gewohnt sind; hier zaehlen Zeichen. Die Ueberschrift passt
        immer hinein - eine abgeschnittene Spaltenueberschrift ist keine.

        Eine mitwachsende Spalte richtet sich zusaetzlich nach ihrem
        laengsten Eintrag: dort stehen Saetze und keine Zahlen, und
        deren Laenge weiss erst, wer sie gesehen hat. Eine passende
        Spalte richtet sich nur danach - sie wird so breit, wie ihr
        Inhalt und ihre Ueberschrift es verlangen, und keinen Anschlag
        breiter.
        """
        breite = self.zeichenbreite()
        laengste = self._laengsten(zeilen, set(mitwachsend) | set(passend))
        self._breiten, self._anfang = {}, {}
        # Jede Haelfte zaehlt bei Null wieder an: sie ist ein eigenes
        # Textfeld und weiss nichts von den Spalten der anderen.
        for gruppe in (self._fest, self._lose()):
            stelle = 0
            for name in gruppe:
                stelle = self._eine_breite(name, breiten, laengste, breite,
                                           mitwachsend, passend, stelle)

    def _eine_breite(self, name, breiten, laengste, breite, mitwachsend,
                     passend, stelle: int) -> int:
        """Eine Spalte vermessen und einordnen.

        Zurueck kommt, wo die naechste Spalte anfaengt.
        """
        punkte = (breiten or {}).get(name, VORGABEBREITE)
        zeichen = max([int(round(punkte / breite))]
                      + [len(zeile) for zeile
                         in self._titel.get(name, [name])])
        if name in passend:
            # So breit, wie Inhalt und Ueberschrift es verlangen -
            # und nie schmaler als die Vorgabe: eine beschreibbare
            # Spalte, die auf ihre Ueberschrift zusammenschrumpft,
            # laedt niemanden zum Schreiben ein.
            zeichen = min(MITWACHSEND_HOECHSTENS,
                          max(zeichen, laengste.get(name, 0)))
        elif name in mitwachsend and laengste.get(name):
            zeichen = min(MITWACHSEND_HOECHSTENS,
                          max(zeichen * MITWACHSEND_VIELFACHES,
                              laengste[name]))
        self._breiten[name] = zeichen
        self._anfang[name] = stelle
        return stelle + zeichen + LUECKE

    @staticmethod
    def _laengsten(zeilen, mitwachsend) -> dict:
        """Der laengste Eintrag je Spalte, die sich nach ihm richtet."""
        gefunden = {}
        for _, werte in zeilen:
            for name in mitwachsend:
                laenge = len(str(werte.get(name, "") or ""))
                if laenge > gefunden.get(name, 0):
                    gefunden[name] = laenge
        return gefunden

    def _gesetzt(self, wert, spalte: str) -> str:
        """Ein Feld auf seine Breite gebracht - Zahlen rechtsbuendig.

        Beschreibbar heisst hier meist "eine Zahl", und Zahlen liest
        man am rechten Rand. Wo in einer beschreibbaren Spalte Saetze
        stehen, sagt das der Aufrufer: `linksbuendig`.
        """
        breite = self._breiten[spalte]
        text = str("" if wert is None else wert)
        if len(text) > breite:
            text = text[:breite]
        if spalte in self._aenderbar and spalte not in self._linksbuendig:
            return text.rjust(breite)
        return text.ljust(breite)

    # ---------------------------------------------------- Verbundene Zellen
    def _bloecke_setzen(self, verbunden):
        """Merkt sich, welche Zellen zu einem Block gehoeren."""
        self._blockvon = {}
        self._blockzeilen = {}
        for spalte, kennungen in verbunden or ():
            name = str(spalte)
            reihe = [str(kennung) for kennung in kennungen]
            if len(reihe) < 2:
                # Eine Zelle allein ist kein Block - dann bleibt alles,
                # wie es ohne Verbinden waere.
                continue
            self._blockzeilen[(reihe[0], name)] = reihe
            for kennung in reihe:
                self._blockvon[(kennung, name)] = reihe[0]

    def block_von(self, zeile, spalte):
        """Die erste Zeile des Blocks, in dem diese Zelle liegt.

        Ohne Block die Zeile selbst - so laesst sich jede Zelle gleich
        behandeln, ob sie zu einem Block gehoert oder nicht.
        """
        zeile, spalte = str(zeile), str(spalte)
        return self._blockvon.get((zeile, spalte), zeile)

    def blockzeilen(self, zeile, spalte) -> list:
        """Alle Zeilen des Blocks - die Zeile selbst, wo keiner ist."""
        zeile, spalte = str(zeile), str(spalte)
        erste = self._blockvon.get((zeile, spalte))
        if erste is None:
            return [zeile]
        return list(self._blockzeilen.get((erste, spalte), [zeile]))

    @staticmethod
    def _blockmitte(kennungen) -> str:
        """In welcher Zeile der Wert eines Blocks steht.

        In der Mitte, und bei gerader Anzahl in der oberen der beiden:
        so steht er bei zwei Zeilen oben und nicht unten, und das
        liest sich zur ersten Messung hin.
        """
        return kennungen[(len(kennungen) - 1) // 2]

    def _zellentext(self, kennung: str, spalte: str, werte: dict) -> str:
        """Was in einer Zelle steht - mit Ruecksicht auf Bloecke.

        In einem Block traegt nur die Mitte den Wert, und sie traegt
        ihn zentriert: er gehoert zu allen Zeilen des Blocks, nicht zu
        einer. Die uebrigen Zellen bleiben leer - so sieht der Block
        aus wie eine Zelle.
        """
        erste = self._blockvon.get((kennung, spalte))
        if erste is None:
            return self._gesetzt(werte.get(spalte, ""), spalte)
        reihe = self._blockzeilen.get((erste, spalte), [])
        breite = self._breiten[spalte]
        if kennung != self._blockmitte(reihe):
            return " " * breite
        text = str(self._zellen.get((erste, spalte), ""))[:breite]
        return text.center(breite)

    def _ueberschrift(self, spalte: str, zeile: int = 0) -> str:
        """Eine Zeile der Ueberschrift, mittig ueber ihrer Spalte.

        Linksbuendig ueber einer rechtsbuendigen Zahlenspalte steht sie
        am falschen Ende; mittig gehoert sie sichtbar zu beidem.

        Mehrzeilig wird sie von unten gefuellt: bei "UM / Pruefmethode
        / Einheit" und einer Spalte, die nur zwei Zeilen braucht, soll
        die Einheit trotzdem in der untersten stehen - sonst steht in
        einer Reihe die Einheit neben einem Namen.
        """
        breite = self._breiten[spalte]
        zeilen = self._titel.get(spalte, [str(spalte)])
        fehlend = self.kopfhoehe - len(zeilen)
        stelle = zeile - fehlend
        if stelle < 0:
            return " " * breite
        return zeilen[stelle][:breite].center(breite)

    def fuellen(self, spalten, zeilen, aenderbar=(), marken=None,
                breiten=None, mitwachsend=(), passend=(), linksbuendig=(),
                fest=(), ueberschriften=None, zugspalten=(), verbunden=(),
                starke_trenner=(), gruppentrenner=(), gruppenstreifen=(),
                tippzeilen=None):
        """Zeigt die Tabelle.

        `spalten` sind die Spaltennamen, `zeilen` eine Liste von
        (Kennung, Werte) - die Kennung ist die Probennummer und bleibt
        beim Neuzeichnen dieselbe, damit die offene Zelle nicht wandert.
        `aenderbar` nennt die Spalten, in denen getippt werden darf.
        `marken` ist auf (Kennung, Spalte) geschluesselt und faerbt
        einzelne Zellen. `mitwachsend` nennt die Spalten, die sich nach
        ihrem Inhalt richten duerfen statt nach ihrer Vorgabe,
        `passend` die, die sich genau nach ihm richten sollen,
        `linksbuendig` die beschreibbaren, in denen Text steht.
        `fest` nennt die Spalten, die links stehen bleiben, waehrend der
        Rest waagerecht laeuft; `ueberschriften` erlaubt, in der
        Kopfzeile etwas anderes zu zeigen als den Spaltennamen - die
        Spalte heisst innen weiter, wie sie heisst. Eine Ueberschrift
        darf mehrzeilig sein: dann ist sie eine Liste von Zeilen (oder
        ein Text mit Umbruechen), und die Kopfzeile wird so hoch wie
        die laengste. Damit wird eine Spalte so schmal wie ihr
        laengstes *Stueck* und nicht wie alle zusammen - "TRDF3.2 /
        Cges / g/kg" untereinander braucht acht Anschlaege statt
        zwanzig. Gefuellt wird von unten, damit die Einheit in allen
        Spalten in derselben Reihe steht. `zugspalten` sagt,
        was auf dem Schild steht, das beim Verschieben am Zeiger
        haengt - ohne Angabe die erste Spalte.

        `verbunden` nennt Bloecke von Zellen, die als *eine* gelten:
        eine Liste von (Spalte, [Zeilenkennungen]). Der Wert der ersten
        Zeile steht mittig in der Mitte des Blocks, die uebrigen Zellen
        bleiben leer, eine Marke gilt fuer den ganzen Block, und ein
        Klick darin trifft ihn als Ganzes. Damit laesst sich eine
        Aussage ueber eine Gruppe von Zeilen auch so hinschreiben - etwa
        der Variationskoeffizient ueber die Messungen einer Probe.

        `starke_trenner` und `gruppentrenner` nennen Spalten, vor denen
        ein kraeftigerer Strich steht: bei fuenf Spalten je Pruefmethode
        sagt ein gleichmaessiger Strich nicht mehr, wo ein Block
        aufhoert.

        `gruppenstreifen` nennt die Zeilengruppen - eine Liste von
        Listen von Zeilenkennungen - und unterlegt jede zweite davon
        ganz zart. Das ist dieselbe Frage in der anderen Richtung: wo
        eine Probe mehrere Zeilen hat, sagt ein Spaltenstrich nicht,
        wo sie aufhoert.
        """
        self.schliessen()
        self._kopf_verlassen()
        self._zelle_verlassen()
        self._fuellung = (list(spalten), list(zeilen), {
            "aenderbar": aenderbar, "marken": marken, "breiten": breiten,
            "mitwachsend": mitwachsend, "passend": passend,
            "linksbuendig": linksbuendig, "fest": fest,
            "ueberschriften": ueberschriften, "zugspalten": zugspalten,
            "verbunden": verbunden, "starke_trenner": starke_trenner,
            "gruppentrenner": gruppentrenner,
            "gruppenstreifen": gruppenstreifen,
            "tippzeilen": tippzeilen})
        self._spalten = [str(name) for name in spalten]
        self._aenderbar = {str(name) for name in aenderbar}
        self._tippzeilen = (None if tippzeilen is None
                            else {str(name) for name in tippzeilen})
        self._linksbuendig = {str(name) for name in linksbuendig}
        self._titel = {name: zeilen for name, zeilen in
                       ((str(name), _kopfzeilen(text)) for name, text
                        in (ueberschriften or {}).items()) if zeilen}
        # So hoch ist die Kopfzeile: die laengste Ueberschrift
        # bestimmt sie fuer alle, sonst stuenden die Spalten auf
        # verschiedenen Hoehen.
        self.kopfhoehe = max([1] + [len(zeilen)
                                    for zeilen in self._titel.values()])
        gewuenscht = {str(name) for name in fest}
        # Stehen bleiben koennen nur Spalten, die es gibt - und sie
        # stehen in der Reihenfolge, in der sie uebergeben wurden.
        self._fest = [name for name in self._spalten if name in gewuenscht]
        self._marken = {(kennung, str(spalte)): marke
                        for (kennung, spalte), marke in (marken or {}).items()}
        self._stark = {str(name) for name in (starke_trenner or ())}
        self._gruppen = {str(name) for name in (gruppentrenner or ())}
        self._streifen = [[str(kennung) for kennung in reihe]
                          for reihe in (gruppenstreifen or ())]
        self._bloecke_setzen(verbunden)
        self._spaltenbreiten(breiten, zeilen, set(mitwachsend),
                             set(passend))
        # Wo die Tabelle stand, bevor sie neu geschrieben wird. Ein
        # gesetzter Kommentar aendert eine Zelle, und die Tabelle wird
        # dafuer ganz neu geschrieben - sie sprang dabei an den
        # Anfang. Bei dreihundert Proben heisst das: nach jedem
        # Kommentar zurueckrollen zu der Zeile, an der man war.
        #
        # Zurueckgesetzt wird nur, wenn dieselben Zeilen dastehen:
        # eine andere Serie, ein anderer Filter, eine andere Sortierung
        # sind ein neuer Anfang, und dort waere die alte Stelle
        # willkuerlich.
        vorher = self._stand_merken()
        self._reihen = [str(kennung) for kennung, _ in zeilen]
        self._unter_maus = None      # das Raster wird neu geschrieben
        # Ein Klick, der noch kein Zug geworden ist, gilt nach dem
        # Neuschreiben nicht mehr. Ein laufender Zug schon: beim
        # Einordnen wird die Tabelle unter dem Finger neu geschrieben,
        # und der Finger haelt seine Zeile weiter.
        if self._zug is not None and not self._zug.get("aktiv"):
            self._zug = None
        self._zugspalten = [str(name) for name in (zugspalten or ())]
        self._zellen = {}
        lose = self._lose()
        zeilentexte, festtexte = [], []
        for kennung, werte in zeilen:
            kennung = str(kennung)
            for name in self._spalten:
                wert = werte.get(name, "")
                self._zellen[(kennung, name)] = str(
                    "" if wert is None else wert)
            zeilentexte.append(TRENNER.join(
                self._zellentext(kennung, name, werte) for name in lose)
                + "\n")
            if self._fest:
                # Ein Strich auch ganz rechts: er trennt die feste
                # Haelfte von der, die unter ihr weglaeuft.
                festtexte.append(TRENNER.join(
                    self._zellentext(kennung, name, werte)
                    for name in self._fest) + TRENNER + "\n")
        self.kopf.configure(height=self.kopfhoehe)
        self.festkopf.configure(height=self.kopfhoehe)
        self._schreiben(self.kopf, "\n".join(
            TRENNER.join(self._ueberschrift(name, zeile) for name in lose)
            for zeile in range(self.kopfhoehe)))
        self._schreiben(self.text, "".join(zeilentexte))
        if self._fest:
            self._schreiben(self.festkopf, "\n".join(
                TRENNER.join(self._ueberschrift(name, zeile)
                             for name in self._fest) + TRENNER
                for zeile in range(self.kopfhoehe)))
            self._schreiben(self.festtext, "".join(festtexte))
        self._feste_haelfte_zeigen()
        self._striche()
        self._faerben()
        # Die gewaehlte Zeile bleibt gewaehlt: das Raster wird bei jeder
        # Aenderung neu geschrieben, und wer im Blockbild blaettert,
        # will die Unterlegung dabei nicht verlieren.
        self._auswahl_zeigen()
        self._stand_einsetzen(vorher)

    def _stand_merken(self) -> dict:
        """Wo die Tabelle steht - Zeilen und Rollstellen.

        Vor dem Neuschreiben aufgenommen; ``_stand_einsetzen`` setzt
        die Stellen zurueck, wenn dieselben Zeilen dastehen.
        """
        try:
            return {"reihen": list(self._reihen),
                    "senkrecht": self.text.yview()[0],
                    "waagerecht": self.text.xview()[0]}
        except tk.TclError:                      # pragma: no cover
            return {}

    def _stand_einsetzen(self, vorher: dict) -> bool:
        """Die Rollstellen zurueck - nur bei unveraenderten Zeilen.

        Zurueck kommt, ob gerollt wurde. Zwei Tabellen mit denselben
        Zeilen sind dieselbe Ansicht; eine mit anderen ist eine neue,
        und dort waere die alte Stelle willkuerlich.
        """
        if not vorher or vorher.get("reihen") != self._reihen:
            return False
        try:
            self.text.yview("moveto", vorher["senkrecht"])
            self.text.xview("moveto", vorher["waagerecht"])
            self.kopf.xview("moveto", vorher["waagerecht"])
            if self._fest:
                self.festtext.yview("moveto", vorher["senkrecht"])
        except tk.TclError:                      # pragma: no cover
            return False
        return True

    def _feste_haelfte_zeigen(self):
        """Die feste Haelfte einblenden - so breit wie ihre Spalten.

        Ohne feste Spalten verschwindet sie ganz, und die laufende
        Haelfte steht wieder da, wo sie immer stand.
        """
        if not self._fest:
            self.festkopf.grid_remove()
            self.festtext.grid_remove()
            self.kopf.grid_configure(padx=(6, 0))
            self.text.grid_configure(padx=(6, 0))
            return
        zeichen = sum(self._breiten[name] + LUECKE for name in self._fest)
        for feld in (self.festkopf, self.festtext):
            feld.configure(width=zeichen)
        self.festkopf.grid(row=0, column=0, sticky="we", padx=(6, 0),
                           pady=(4, 0))
        self.festtext.grid(row=1, column=0, sticky="nsew", padx=(6, 0),
                           pady=(0, 4))
        self.kopf.grid_configure(padx=(0, 0))
        self.text.grid_configure(padx=(0, 0))
        # Beim Neuaufbau steht die feste Haelfte oben, die laufende
        # vielleicht nicht - also einmal angleichen.
        self.festtext.yview("moveto", self.text.yview()[0])

    def _striche(self):
        """Die Trennstriche zuruecknehmen - in einem Zug.

        Je Strich einzeln zu faerben waeren bei dreihundert Zeilen und
        zwanzig Spalten sechstausend Anweisungen; Tk nimmt alle Stellen
        in einer entgegen.
        """
        for kopf, feld, spalten, letzter in (
                (self.kopf, self.text, self._lose(), False),
                (self.festkopf, self.festtext, self._fest, True)):
            # In der festen Haelfte steht auch hinter der letzten Spalte
            # ein Strich - er trennt sie von der laufenden.
            trennende = spalten if letzter else spalten[:-1]
            stellen = [(f"{zeile}.{self._anfang[name] + self._breiten[name]}",
                        f"{zeile}."
                        f"{self._anfang[name] + self._breiten[name] + LUECKE}")
                       for zeile in range(1, self.kopfhoehe + 1)
                       for name in trennende]
            if stellen:
                kopf.tag_add("trenner",
                             *[teil for paar in stellen for teil in paar])
            stellen = []
            for zeile in range(1, len(self._reihen) + 1):
                for name in trennende:
                    spalte = self._anfang[name] + self._breiten[name]
                    stellen.append((f"{zeile}.{spalte}",
                                    f"{zeile}.{spalte + LUECKE}"))
            if stellen:
                feld.tag_add("trenner",
                             *[teil for paar in stellen for teil in paar])
        self._starke_striche()

    def _starke_striche(self):
        """Die kraeftigeren Striche - vor den genannten Spalten.

        Sie liegen ueber dem gewoehnlichen Strich und ueber den Farben:
        sie gehoeren zu keiner Zelle und sollen von keiner eingefaerbt
        werden.
        """
        if not (self._stark or self._gruppen):
            return
        for kopf, feld, spalten in ((self.kopf, self.text, self._lose()),
                                    (self.festkopf, self.festtext,
                                     self._fest)):
            for tag, namen in ((TAG_TRENNER_STARK, self._stark),
                               (TAG_TRENNER_GRUPPE, self._gruppen)):
                stellen = []
                for nummer, name in enumerate(spalten):
                    # Der Strich *vor* einer Spalte ist der hinter
                    # ihrer Vorgaengerin - die erste Spalte hat keinen.
                    if nummer == 0 or name not in namen:
                        continue
                    vorher = spalten[nummer - 1]
                    stelle = self._anfang[vorher] + self._breiten[vorher]
                    for zeile in range(0, len(self._reihen) + 1):
                        stellen.append((zeile, stelle))
                if not stellen:
                    continue
                kopfstellen = [(f"{kopfzeile}.{stelle}",
                                f"{kopfzeile}.{stelle + LUECKE}")
                               for zeile, stelle in stellen if zeile == 0
                               for kopfzeile in range(1,
                                                      self.kopfhoehe + 1)]
                if kopfstellen:
                    kopf.tag_add(tag, *[teil for paar in kopfstellen
                                        for teil in paar])
                feldstellen = [(f"{zeile}.{stelle}",
                                f"{zeile}.{stelle + LUECKE}")
                               for zeile, stelle in stellen if zeile >= 1]
                if feldstellen:
                    feld.tag_add(tag, *[teil for paar in feldstellen
                                        for teil in paar])
            for ziel in (kopf, feld):
                ziel.tag_raise(TAG_TRENNER_STARK)
                ziel.tag_raise(TAG_TRENNER_GRUPPE)

    @staticmethod
    def _schreiben(feld: tk.Text, inhalt: str):
        feld.configure(state="normal")
        feld.delete("1.0", "end")
        feld.insert("1.0", inhalt)
        feld.configure(state="disabled")

    def _faerben(self):
        """Alle Marken auf einmal - je Farbe eine Anweisung.

        Je Zelle einzeln zu faerben waeren bei dreihundert Proben und
        siebenundzwanzig Spalten zehntausend Anweisungen, und die
        merkt man. Tk nimmt beliebig viele Stellen in einer entgegen,
        also werden sie nach Farbe gesammelt.
        """
        for feld in self._felder():
            for name in list(FARBEN) + [f"{name}_hg" for name in HINTERGRUND]:
                feld.tag_remove(name, "1.0", "end")
        self._streifen_zeigen()
        stellen = {}
        for (kennung, spalte), marke in self._marken.items():
            # Eine Marke auf einer verbundenen Zelle gilt fuer den
            # ganzen Block: die Zelle *ist* der Block, und halb rot
            # waere keine Aussage.
            for zeile in self.blockzeilen(kennung, spalte):
                bereich = self._bereich(zeile, spalte)
                if bereich is None:
                    continue
                feld, von, bis = bereich
                for name in self._tags(marke):
                    stellen.setdefault((id(feld), name),
                                       (feld, []))[1].extend((von, bis))
        for (_, name), (feld, bereiche) in stellen.items():
            feld.tag_add(name, *bereiche)
        self._striche_nach_oben()

    def _striche_nach_oben(self):
        """Alle Striche ueber die Farben heben - auch die kraeftigen.

        Sie gehoeren zu keiner Zelle und sollen von keiner eingefaerbt
        werden. Der gewoehnliche Strich stand hier schon; die
        kraeftigen fehlten, und genau das sah man: in den
        Ueberschriften standen sie da (dort faerbt nichts), in der
        Tabelle waren sie unter der Zellfarbe verschwunden.
        """
        for feld in self._felder():
            feld.tag_raise("trenner")
            feld.tag_raise(TAG_TRENNER_STARK)
            feld.tag_raise(TAG_TRENNER_GRUPPE)

    def _streifen_zeigen(self):
        """Jede zweite Zeilengruppe ganz zart unterlegen.

        Unterlegt wird die ganze Zeile, in beiden Haelften: der
        Streifen soll die Gruppe zusammenhalten, und eine Haelfte
        allein tut das nicht.
        """
        for feld in self._felder():
            feld.tag_remove(TAG_STREIFEN, "1.0", "end")
        if not self._streifen:
            return
        stellen = []
        for nummer, reihe in enumerate(self._streifen):
            if nummer % 2 == 0:
                continue
            for kennung in reihe:
                if kennung not in self._reihen:
                    continue
                zeile = self._reihen.index(kennung) + 1
                stellen.append((f"{zeile}.0", f"{zeile}.end"))
        if not stellen:
            return
        for feld in self._felder():
            feld.tag_add(TAG_STREIFEN,
                         *[teil for paar in stellen for teil in paar])
            feld.tag_lower(TAG_STREIFEN)

    def _bereich(self, kennung: str, spalte: str):
        """Wo eine Zelle steht: (Feld, von, bis) - None, wo es sie nicht gibt."""
        if spalte not in self._anfang or kennung not in self._reihen:
            return None
        zeile = self._reihen.index(kennung) + 1
        von = self._anfang[spalte]
        return (self._wo(spalte), f"{zeile}.{von}",
                f"{zeile}.{von + self._breiten[spalte]}")

    @staticmethod
    def _tags(marke) -> list:
        """Welche Tags zu einer Marke gehoeren - Schrift und Hintergrund."""
        if marke is None:
            return []
        return [name for name in (marke, f"{marke}_hg")
                if name in FARBEN or name[:-3] in HINTERGRUND]

    def _zelle_faerben(self, kennung: str, spalte: str, marke):
        """Eine einzelne Zelle - beim Nachtragen und beim Tippen."""
        bereich = self._bereich(kennung, spalte)
        if bereich is None:
            return
        feld, von, bis = bereich
        for name in list(FARBEN) + [f"{name}_hg" for name in HINTERGRUND]:
            feld.tag_remove(name, von, bis)
        for name in self._tags(marke):
            feld.tag_add(name, von, bis)
        self._striche_nach_oben()

    def setzen(self, zeile, spalte, wert) -> bool:
        """Schreibt einen Wert von aussen in eine Zelle.

        Fuer das, was nicht der Mensch tippt, sondern das Programm aus
        seiner Eingabe folgert - und was er trotzdem sofort dastehen
        sehen soll, ohne dass die Tabelle neu gebaut wird und ihm dabei
        das offene Feld unter den Fingern wegfaellt.
        """
        zeile, spalte = str(zeile), str(spalte)
        if (zeile, spalte) not in self._zellen:
            return False
        self._setzen(zeile, spalte, str("" if wert is None else wert))
        return True

    def marke_setzen(self, zeile, spalte, marke):
        """Faerbt eine Zelle nach, ohne die Tabelle neu zu bauen.

        Beim Tippen ist das der Unterschied zwischen fluessig und zaeh:
        eine Serie hat dreihundert Zeilen, und die alle neu zu setzen,
        nur weil eine Zahl sich geaendert hat, wuerde man merken.
        Ausserdem bliebe das offene Eingabefeld dabei auf der Strecke.
        """
        zeile, spalte = str(zeile), str(spalte)
        if zeile not in self._reihen or spalte not in self._anfang:
            return
        erste = self.block_von(zeile, spalte)
        self._marken[(erste, spalte)] = marke
        for reihe in self.blockzeilen(zeile, spalte):
            self._zelle_faerben(reihe, spalte, marke)

    # ------------------------------------------------------------- Auskunft
    def fuellung(self):
        """Womit die Tabelle gefuellt wurde - (Spalten, Zeilen, Angaben).

        Zurueck kommt, was beim letzten ``fuellen`` uebergeben wurde,
        oder None, wenn noch nie gefuellt wurde. Damit laesst sich
        dieselbe Tabelle ein zweites Mal aufbauen - in einem eigenen,
        groesseren Fenster etwa, wo mehr Zeilen auf einmal dastehen.
        """
        if self._fuellung is None:
            return None
        spalten, zeilen, angaben = self._fuellung
        return list(spalten), list(zeilen), dict(angaben)

    def zeilen(self) -> list:
        """Die Kennungen in der Reihenfolge, in der sie stehen."""
        return list(self._reihen)

    def spalten(self) -> list:
        return list(self._spalten)

    def feste(self) -> list:
        """Die Spalten, die links stehen bleiben - in ihrer Folge."""
        return list(self._fest)

    def ueberschrift(self, spalte) -> str:
        """Was ueber einer Spalte steht - ihr Name, wo kein Titel gilt.

        Die Kennung einer Spalte und ihre Ueberschrift sind zwei
        Dinge: die Kennung haelt die Zelle, die Ueberschrift sagt, was
        darin steht - etwa mit der Einheit, in der es dasteht.

        Mehrzeilig kommt sie mit Zeilenumbruechen zurueck; die Zeilen
        einzeln gibt `ueberschriftzeilen`.
        """
        return "\n".join(self.ueberschriftzeilen(spalte))

    def ueberschriftzeilen(self, spalte) -> list:
        """Die Zeilen der Ueberschrift - immer mindestens eine."""
        spalte = str(spalte)
        return list(self._titel.get(spalte, [spalte]))

    def wert(self, zeile, spalte) -> str:
        """Was in einer Zelle steht.

        In einem Block der Wert des Blocks - gefragt nach einer seiner
        Zeilen kommt dieselbe Antwort, denn es ist eine Zelle.
        """
        zeile, spalte = str(zeile), str(spalte)
        return self._zellen.get((self.block_von(zeile, spalte), spalte), "")

    def marke(self, zeile, spalte):
        """Wie eine Zelle gefaerbt ist - None, wo sie es nicht ist.

        In einem Block gilt die Marke des Blocks, von welcher seiner
        Zeilen auch gefragt wird.
        """
        zeile, spalte = str(zeile), str(spalte)
        eigene = self._marken.get((zeile, spalte))
        if eigene is not None:
            return eigene
        return self._marken.get((self.block_von(zeile, spalte), spalte))

    def hat(self, zeile) -> bool:
        return str(zeile) in self._reihen

    # ------------------------------------------------------------ Tippen
    def _stelle(self, feld, x: int, y: int):
        """Welche Zelle liegt unter diesem Punkt in diesem Feld?"""
        stelle = feld.index(f"@{x},{y}")
        zeile, zeichen = (int(teil) for teil in stelle.split("."))
        if not 1 <= zeile <= len(self._reihen):
            return None
        spalten = self._fest if feld is self.festtext else self._lose()
        for name in reversed(spalten):
            if zeichen >= self._anfang[name]:
                if zeichen < self._anfang[name] + self._breiten[name]:
                    return (self._reihen[zeile - 1], name)
                return None          # der Strich gehoert zu keiner Spalte
        return None

    # ---------------------------------------------- Hinweis an der Spalte
    def kopfhinweise(self, zuordnung):
        """Was zu welcher Spaltenueberschrift zu sagen ist."""
        self._kopfhinweise = {str(name): str(text)
                              for name, text in (zuordnung or {}).items()
                              if str(text).strip()}

    def kopfhinweis(self, spalte) -> str:
        """Was ueber dieser Ueberschrift steht - "" wenn nichts dazu."""
        return self._kopfhinweise.get(str(spalte), "")

    def _kopf_spalte(self, feld, x: int, y: int):
        """Ueber welcher Spaltenueberschrift der Zeiger steht."""
        return self._spalte_bei(feld, x, y, feld is self.festkopf)

    def _spalte_bei(self, feld, x: int, y: int, fest: bool):
        """In welcher Spalte der Zeiger steht - None auf dem Strich.

        Gerechnet wird in Zeichen: die Tabelle ist ein Text mit fester
        Schriftbreite, und jede Spalte hat darin ihren Anfang und ihre
        Breite. Der Strich dazwischen gehoert zu keiner.
        """
        if not self._spalten:
            return None
        zeichen = int(feld.index(f"@{x},{y}").split(".")[1])
        spalten = self._fest if fest else self._lose()
        for name in reversed(spalten):
            if zeichen >= self._anfang[name]:
                if zeichen < self._anfang[name] + self._breiten[name]:
                    return name
                return None          # der Strich gehoert zu keiner Spalte
        return None

    def _kopf_bewegt(self, ereignis):
        spalte = self._kopf_spalte(ereignis.widget, ereignis.x, ereignis.y)
        if spalte == self._kopfspalte:
            return
        self._kopf_verlassen()
        self._kopfspalte = spalte
        if spalte in self._kopfhinweise:
            self._kopfwarten = self.kopf.after(
                KOPF_VERZOEGERUNG,
                lambda: self._kopf_zeigen(spalte, ereignis.x_root))

    def _kopf_zeigen(self, spalte: str, x: int):
        self._kopfwarten = None
        if spalte != self._kopfspalte or spalte not in self._kopfhinweise:
            return
        fenster = tk.Toplevel(self.kopf)
        fenster.wm_overrideredirect(True)
        fenster.wm_geometry(f"+{x}"
                            f"+{self.kopf.winfo_rooty() + 22}")
        tk.Label(fenster, text=self._kopfhinweise[spalte], justify="left",
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("Arial", 9)).pack(ipadx=3, ipady=3)
        self._kopffenster = fenster

    def _kopf_verlassen(self):
        """Der Hinweis geht wieder - und der Wecker dazu."""
        if self._kopfwarten is not None:
            self.kopf.after_cancel(self._kopfwarten)
            self._kopfwarten = None
        if self._kopffenster is not None:
            self._kopffenster.destroy()
            self._kopffenster = None
        self._kopfspalte = None

    # ------------------------------------------------------- Unter der Maus
    def _maus_bewegt(self, ereignis):
        """Die Zeile unter dem Zeiger hervorheben - und nur die."""
        stelle = ereignis.widget.index(f"@{ereignis.x},{ereignis.y}")
        try:
            zeile = int(stelle.split(".")[0])
        except ValueError:
            return
        self._maus_zeile(zeile if 1 <= zeile <= len(self._reihen) else None)
        self._zelle_bewegt(ereignis)

    def _maus_verlassen(self, ereignis=None):
        """Der Zeiger ist heraus - Hervorhebung und Hinweis gehen."""
        self._maus_zeile(None)
        self._zelle_verlassen()

    def _maus_zeile(self, zeile):
        """Faerbt die Zeile um - nur, wenn es eine andere geworden ist.

        Bei jedem Mausschubser neu zu faerben waere dieselbe Arbeit
        hundertmal in der Sekunde, und man saehe es.
        """
        if zeile == self._unter_maus:
            return
        self._unter_maus = zeile
        for feld in self._felder():
            feld.tag_remove(TAG_MAUSZEILE, "1.0", "end")
            if zeile is not None:
                feld.tag_add(TAG_MAUSZEILE, f"{zeile}.0", f"{zeile}.end")
                feld.tag_lower(TAG_MAUSZEILE)

    # -------------------------------------------------- Die rechte Maustaste
    def _rechts_geklickt(self, ereignis):
        """Meldet, auf welcher Zelle die rechte Taste gedrueckt wurde.

        Der Hinweis geht vorher weg: sonst stuende er ueber dem Menue,
        das gerade aufgeht.
        """
        if self.bei_rechtsklick is None:
            return None
        self._zelle_verlassen()
        feld = ereignis.widget
        spalte = self._spalte_bei(feld, ereignis.x, ereignis.y,
                                  feld is self.festtext)
        zeile = self._zeile_bei(feld, ereignis.y)
        if zeile is None or spalte is None:
            return None
        # In einer verbundenen Zelle trifft der Klick den Block: sie
        # *ist* eine Zelle, und ihre Kennung ist die ihrer ersten Zeile.
        self.bei_rechtsklick(self.block_von(zeile, spalte), spalte, ereignis)
        return "break"

    # ----------------------------------------------- Der Hinweis an der Zelle
    def _doppelt_geklickt(self, ereignis):
        """Der Doppelklick auf eine Zelle - wo, sagt die Tabelle.

        Der einfache Klick ist vorher schon gelaufen; das ist kein
        Fehler, sondern die Reihenfolge: erst einsetzen, dann oeffnen.
        """
        if self.bei_doppelklick is None:
            return None
        stelle = self._stelle(ereignis.widget, ereignis.x, ereignis.y)
        if stelle is None:
            return None
        zeile, spalte = stelle
        self.bei_doppelklick(self.block_von(zeile, spalte), spalte)
        return "break"

    def darf_tippen(self, zeile, spalte) -> bool:
        """Ob in dieser Zelle getippt werden darf - Zeile und Spalte.

        Die Spalte entscheidet wie bisher; dazu die Zeile, wo eine
        Tabelle je Probe mehrere Zeilen zeigt und nur eine davon eine
        Eingabe ist.
        """
        if str(spalte) not in self._aenderbar:
            return False
        return self._tippzeilen is None or str(zeile) in self._tippzeilen

    def _tippbare_reihen(self) -> list:
        """Die Zeilen, in denen getippt werden darf - in ihrer Folge.

        Darueber laeuft ein eingefuegter Block und das Weiterspringen
        mit Tab: eine Zeile, in der nichts zu tippen ist, wuerde den
        Block sonst verschlucken.
        """
        if self._tippzeilen is None:
            return list(self._reihen)
        return [name for name in self._reihen if name in self._tippzeilen]

    def ist_aenderbar(self, spalte) -> bool:
        """Ob in diese Spalte getippt werden darf.

        Eine Auskunft fuer den Aufrufer und fuer die Pruefungen: in
        manche Spalten wird ausdruecklich *nicht* getippt, und das
        soll festzuhalten sein.
        """
        return str(spalte) in self._aenderbar

    def zellhinweise(self, quelle):
        """Woher der Hinweis kommt, der ueber einer Zelle stehen soll.

        Uebergeben wird eine Funktion (Zeilenkennung, Spaltenname), die
        einen Satz liefert oder None. Gefragt wird erst, wenn die Maus
        stehen bleibt - so muss niemand fuer fuenfzehntausend Zellen
        Saetze vorhalten, von denen einer gelesen wird.
        """
        self._zellquelle = quelle

    def _zelle_bewegt(self, ereignis):
        """Ueber welcher Zelle der Zeiger steht - und seit wann."""
        if self._zellquelle is None:
            return
        feld = ereignis.widget
        spalte = self._spalte_bei(feld, ereignis.x, ereignis.y,
                                  feld is self.festtext)
        zeile = self._zeile_bei(feld, ereignis.y)
        stelle = None if spalte is None or zeile is None else (zeile, spalte)
        if stelle == self._zellstelle:
            return
        self._zelle_verlassen()
        self._zellstelle = stelle
        if stelle is None:
            return
        self._zellwarten = self.after(
            KOPF_VERZOEGERUNG,
            lambda: self._zelle_zeigen(stelle, ereignis.x_root,
                                       ereignis.y_root))

    def _zelle_zeigen(self, stelle, x: int, y: int):
        self._zellwarten = None
        if stelle != self._zellstelle or self._zellquelle is None:
            return
        try:
            text = self._zellquelle(*stelle)
        except Exception:                                # noqa: BLE001
            # Ein Hinweis ist eine Bequemlichkeit. Geht er schief, soll
            # die Tabelle weiter dastehen und nicht der Fehler.
            return
        if not text:
            return
        fenster = tk.Toplevel(self)
        fenster.wm_overrideredirect(True)
        fenster.wm_geometry(f"+{x + 14}+{y + 18}")
        tk.Label(fenster, text=str(text), justify="left",
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("Arial", 9)).pack(ipadx=3, ipady=3)
        self._zellfenster = fenster

    def _zelle_verlassen(self):
        """Der Hinweis geht wieder - und der Wecker dazu."""
        if self._zellwarten is not None:
            self.after_cancel(self._zellwarten)
            self._zellwarten = None
        if self._zellfenster is not None:
            self._zellfenster.destroy()
            self._zellfenster = None
        self._zellstelle = None

    # ------------------------------------------------------ Gewaehlte Zeile
    def auswahl(self, zeilen=None):
        """Unterlegt die gewaehlten Zeilen - und nur sie.

        Uebergeben wird eine Kennung, mehrere oder nichts. Die
        Unterlegung sagt: hier bin ich gerade - die Probe, deren
        Bodenblock offen steht. Sie bleibt stehen, bis eine andere
        gewaehlt wird, und uebersteht das Neuschreiben der Tabelle.
        """
        if zeilen is None:
            gewaehlt = []
        elif isinstance(zeilen, (str, bytes)):
            gewaehlt = [str(zeilen)]
        else:
            gewaehlt = [str(zeile) for zeile in zeilen]
        self._gewaehlt = gewaehlt
        self._auswahl_zeigen()

    def gewaehlt(self) -> list:
        """Welche Zeilen unterlegt sind."""
        return list(self._gewaehlt)

    def hat(self, zeile) -> bool:
        """Ob diese Zeile in der Tabelle steht."""
        return str(zeile) in self._reihen

    def zeigen(self, zeile) -> bool:
        """Eine Zeile in den Blick holen und unterlegen.

        Fuer das Suchen ueber die Blaetter: gefunden zu haben ist die
        halbe Auskunft, die andere Haelfte ist, sie auch zu sehen. Die
        Unterlegung bleibt stehen - nach dem Sprung soll man die Zeile
        noch finden, wenn der Blick vom Suchfeld zurueckkommt.

        Zurueck kommt, ob es die Zeile gibt.
        """
        kennung = str(zeile)
        if kennung not in self._reihen:
            return False
        self.auswahl(kennung)
        nummer = self._reihen.index(kennung) + 1
        # Nur senkrecht. `see` auf Spalte 0 rollt auch waagerecht, und
        # zwar ganz nach links - wer eine Zeile in den Blick holt, will
        # nicht die Spalte verlieren, in der er gerade liest.
        waagerecht = self.text.xview()[0]
        for feld in self._felder():
            feld.see(f"{nummer}.0")
        self.text.xview("moveto", waagerecht)
        return True

    def sehen(self, zeile) -> bool:
        """Eine Zeile in den Blick holen - ohne an der Auswahl zu ruehren.

        Anders als `zeigen` bleibt die Unterlegung, wie sie ist: wer in
        einer anderen Tabelle arbeitet, gibt hier nur den Blick vor.
        Waagerecht bleibt alles stehen.
        """
        kennung = str(zeile)
        if kennung not in self._reihen:
            return False
        nummer = self._reihen.index(kennung) + 1
        waagerecht = self.text.xview()[0]
        for feld in self._felder():
            feld.see(f"{nummer}.0")
        self.text.xview("moveto", waagerecht)
        return True

    def _auswahl_zeigen(self):
        """Die Unterlegung setzen - in beiden Haelften zugleich."""
        for feld in self._felder():
            feld.tag_remove(TAG_AUSWAHL, "1.0", "end")
        for kennung in self._gewaehlt:
            if kennung not in self._reihen:
                continue
            zeile = self._reihen.index(kennung) + 1
            for feld in self._felder():
                feld.tag_add(TAG_AUSWAHL, f"{zeile}.0", f"{zeile}.end")
                feld.tag_lower(TAG_AUSWAHL)
                feld.tag_lower(TAG_MAUSZEILE)

    def _angeklickt(self, ereignis):
        self._zelle_verlassen()
        self._zug = None
        zelle = self._stelle(ereignis.widget, ereignis.x, ereignis.y)
        if zelle is None:
            return "break"
        zeile, spalte = zelle
        if not self.darf_tippen(zeile, spalte):
            self.schliessen()
            if self.bei_verschieben is not None:
                # Erst beim Ziehen wird daraus ein Verschieben; bleibt
                # die Maus stehen, ist es ein gewoehnlicher Klick.
                self._zug = {"zeile": zeile, "spalte": spalte,
                             "y": ereignis.y_root, "aktiv": False,
                             "ziel": None}
                return "break"
            if self.bei_klick is not None:
                # Auch hier trifft der Klick den Block als Ganzes.
                self.bei_klick(self.block_von(zeile, spalte), spalte)
            return "break"
        self.oeffnen(zeile, spalte)
        return "break"

    # ------------------------------------------------------ Zeilen ziehen
    def _gezogen(self, ereignis):
        """Die Zeile folgt der Maus - und die anderen ruecken zusammen.

        Gezogen wird nicht auf Vorrat: sobald der Zeiger ueber einer
        anderen Zeile steht, wird umgeordnet. Wer loslaesst, sieht
        also nichts Neues mehr - er sieht das, was die ganze Zeit
        dastand. Am Zeiger haengt dabei ein Schild mit der Zeile, die
        wandert; ohne es verliert man im Umordnen, welche man greift.
        """
        if self._zug is None:
            return None
        if not self._zug["aktiv"]:
            if abs(ereignis.y_root - self._zug["y"]) < ZIEHSCHWELLE:
                return "break"
            self._zug["aktiv"] = True
            self._zugschild_zeigen(self._zug["zeile"])
        self._zugschild_stellen(ereignis)
        ziel = self._zeile_bei(ereignis.widget, ereignis.y)
        if self.bei_verschieben is None:
            self._zug["ziel"] = ziel
            self._ziel_zeigen(ziel)
            return "break"
        if ziel is not None and ziel != self._zug["zeile"] and \
                ziel != self._zug["ziel"]:
            self._zug["ziel"] = ziel
            self._zug["gelegt"] = True
            self.bei_verschieben(self._zug["zeile"], ziel)
        # Hervorgehoben wird die Zeile selbst: sie steht ja schon dort,
        # wo sie hinsoll.
        self._ziel_zeigen(self._zug["zeile"])
        return "break"

    def _losgelassen(self, ereignis=None):
        """Fallen lassen - oder, wenn nicht gezogen wurde, ein Klick."""
        zug, self._zug = self._zug, None
        if zug is None:
            return None
        self._zugschild_verbergen()
        self._ziel_zeigen(None)
        if not zug["aktiv"]:
            if self.bei_klick is not None:
                self.bei_klick(self.block_von(zug["zeile"], zug["spalte"]),
                               zug["spalte"])
            return "break"
        # Beim Ziehen wurde schon eingeordnet; nur wenn das aus
        # irgendeinem Grund nicht geschah, kommt es hier nach.
        if zug["ziel"] is not None and zug["ziel"] != zug["zeile"] and \
                not zug.get("gelegt") and self.bei_verschieben is not None:
            self.bei_verschieben(zug["zeile"], zug["ziel"])
        return "break"

    def _zeile_bei(self, feld, y: int):
        """Auf welche Zeile der Zeiger zeigt - die letzte, wenn darunter."""
        if not self._reihen:
            return None
        zeile = int(feld.index(f"@{0},{y}").split(".")[0])
        zeile = min(max(zeile, 1), len(self._reihen))
        return self._reihen[zeile - 1]

    def _ziel_zeigen(self, kennung):
        """Zeigt, wo die gezogene Zeile hinfiele - in beiden Haelften."""
        for feld in self._felder():
            feld.tag_remove(TAG_ZIEL, "1.0", "end")
        if kennung is None or kennung not in self._reihen:
            return
        zeile = self._reihen.index(kennung) + 1
        for feld in self._felder():
            feld.tag_add(TAG_ZIEL, f"{zeile}.0", f"{zeile}.end")
            feld.tag_lower(TAG_ZIEL)

    # -------------------------------------------------- Das Schild am Zeiger
    def zugtext(self, kennung: str) -> str:
        """Was auf dem Schild steht: die Zeile, kurz genug zum Lesen."""
        kennung = str(kennung)
        spalten = [name for name in self._zugspalten
                   if name in self._spalten] or self._spalten[:1]
        teile = [self._zellen.get((kennung, name), "").strip()
                 for name in spalten]
        return "  ".join(teil for teil in teile if teil) or kennung

    def _zugschild_zeigen(self, kennung: str):
        if self._zugschild is None:
            self._zugschild = tk.Label(
                self, bg=HINTERGRUND_ZUG, fg=FARBE_ZUG, font=self.schrift,
                bd=1, relief="solid", padx=6, pady=1)
        self._zugschild.configure(text=self.zugtext(kennung))

    def _zugschild_stellen(self, ereignis):
        """Das Schild an den Zeiger - im Raster gerechnet, nicht im Feld."""
        if self._zugschild is None:
            return
        x = (ereignis.widget.winfo_rootx() - self.winfo_rootx()
             + ereignis.x + ZUG_ABSTAND)
        y = (ereignis.widget.winfo_rooty() - self.winfo_rooty()
             + ereignis.y + ZUG_ABSTAND)
        self._zugschild.place(x=x, y=y)
        self._zugschild.lift()

    def _zugschild_verbergen(self):
        if self._zugschild is not None:
            self._zugschild.place_forget()

    def _kasten(self, zeile: str, spalte: str):
        """Wo die Zelle auf dem Schirm liegt - None, wenn sie nicht steht."""
        nummer = self._reihen.index(zeile) + 1
        von = self._anfang[spalte]
        bis = von + self._breiten[spalte] - 1
        feld = self._wo(spalte)
        links = feld.bbox(f"{nummer}.{von}")
        rechts = feld.bbox(f"{nummer}.{bis}")
        if not links or not rechts:
            return None
        return (links[0], links[1], rechts[0] + rechts[2] - links[0],
                max(links[3], rechts[3]))

    def oeffnen(self, zeile, spalte):
        """Legt das Eingabefeld auf eine Zelle - Inhalt markiert.

        Markiert, weil geaendert und nicht ergaenzt wird: wer eine Zahl
        tippt, will die alte ersetzen und nicht erst loeschen.
        """
        zeile, spalte = str(zeile), str(spalte)
        if zeile not in self._reihen or not self.darf_tippen(zeile, spalte):
            return
        self._uebernehmen()
        # Erst hinscrollen, dann messen - und dazwischen aufraeumen
        # lassen. Ohne das steht die Zelle zwar im Blick, hat aber noch
        # keine Koordinaten, und das Feld erschiene nicht: beim
        # Durchtippen mit Tab ginge genau da der Faden verloren, wo die
        # Tabelle breiter ist als das Fenster.
        nummer = self._reihen.index(zeile) + 1
        # Senkrecht entscheidet immer die laufende Haelfte: die feste
        # haengt an ihr, und so bleiben beide auf derselben Zeile.
        #
        # `see` auf Spalte 0 rollt aber auch waagerecht - ganz nach
        # links. Wer eine Zelle am rechten Rand anklickt, sah die
        # Tabelle danach woanders stehen: angeklickt, um sie zu
        # bearbeiten, und sie springt weg. Die waagerechte Stellung
        # wird deshalb gemerkt und wiederhergestellt; gerollt wird
        # danach nur, wenn die Zelle wirklich nicht zu sehen ist.
        waagerecht = self.text.xview()[0]
        self.text.see(f"{nummer}.0")
        self.text.xview("moveto", waagerecht)
        self.text.update_idletasks()
        kasten = self._kasten(zeile, spalte)
        if kasten is None and spalte not in self._fest:
            # Jetzt hin - und zwar auf das *Ende* der Zelle: steht nur
            # ihr Anfang im Blick, liegt der Rest hinter dem Rand und
            # das Eingabefeld haette keinen Platz.
            self.text.see(f"{nummer}.{self._anfang[spalte]}")
            self.text.see(f"{nummer}."
                          f"{self._anfang[spalte] + self._breiten[spalte]}")
            self.text.update_idletasks()
            kasten = self._kasten(zeile, spalte)
        if kasten is None:
            return
        self._offen = (zeile, spalte)
        self._vorher = self.wert(zeile, spalte)
        neues = self.festfeld if spalte in self._fest else self.feld
        if neues is not self._aktiv:
            # Die andere Haelfte raeumt ihr Feld weg - sonst stuenden
            # zwei offene Zellen nebeneinander.
            self._aktiv.place_forget()
        self._aktiv = neues
        self._aktiv.delete(0, "end")
        self._aktiv.insert(0, self._vorher)
        self._aktiv.place(x=kasten[0], y=kasten[1], width=kasten[2],
                          height=kasten[3])
        self._aktiv.focus_set()
        self._aktiv.select_range(0, "end")
        self._aktiv.icursor("end")
        if self.bei_zeile is not None:
            self.bei_zeile(zeile)

    def von_oben(self):
        """Strg+D: der Wert der Zelle darueber, wie in Excel.

        Die Zelle bleibt offen und zeigt den neuen Wert - wer weiter
        nach unten kopieren will, geht mit Eingabe eine Zeile tiefer und
        drueckt noch einmal Strg+D.
        """
        if self._offen is None:
            return "break"
        zeile, spalte = self._offen
        stelle = self._reihen.index(zeile)
        if stelle == 0:
            return "break"
        wert = self.wert(self._reihen[stelle - 1], spalte).strip()
        self._aktiv.delete(0, "end")
        self._aktiv.insert(0, wert)
        self._uebernehmen()
        if self._offen == (zeile, spalte):
            self._vorher = wert
            self._aktiv.delete(0, "end")
            self._aktiv.insert(0, self.wert(zeile, spalte).strip())
            self._aktiv.select_range(0, "end")
        return "break"

    def leer(self, zeile, spalte) -> bool:
        """Ob eine Zelle leer ist - so, wie der Aufrufer es sieht."""
        if self.ist_leer is not None:
            return bool(self.ist_leer(str(zeile), str(spalte)))
        return not self.wert(zeile, spalte).strip()

    def nach_unten(self, art: str = "alle") -> list:
        """Den Wert der offenen Zelle in die Spalte darunter tragen.

        `art` sagt wie: "alle" kopiert bis ans Ende und ueberschreibt,
        "leere" kopiert nur in die leeren Zellen, "plus" zaehlt hoch -
        Wert, Wert+1, Wert+2 - und braucht dafuer eine Zahl. Zurueck
        kommen die gesetzten Zellen als (Zeile, Spalte, Wert).
        """
        if self._offen is None:
            return []
        self._uebernehmen()
        if self._offen is None:
            return []
        zeile, spalte = self._offen
        wert = self.wert(zeile, spalte).strip()
        darunter = [kennung for kennung
                    in self._reihen[self._reihen.index(zeile) + 1:]
                    if self.darf_tippen(kennung, spalte)]
        gesetzt = []
        if art == "plus":
            zahl = _als_zahl(wert)
            if zahl is None:
                self.bell()
                return []
            for schritt, kennung in enumerate(darunter, start=1):
                gesetzt.append((kennung, spalte,
                                _zahltext(zahl + schritt, wert)))
        else:
            for kennung in darunter:
                if art == "leere" and not self.leer(kennung, spalte):
                    continue
                if self.wert(kennung, spalte).strip() == wert and \
                        not self.leer(kennung, spalte):
                    continue
                gesetzt.append((kennung, spalte, wert))
        self._verteilen(gesetzt)
        return gesetzt

    def _verteilen(self, gesetzt):
        """Mehrere Zellen auf einmal - der Aufrufer rechnet einmal."""
        if not gesetzt:
            return
        if self.bei_nach_unten is not None:
            self.bei_nach_unten(gesetzt)
        elif self.bei_block is not None:
            self.bei_block(gesetzt)
        else:
            for kennung, spalte, wert in gesetzt:
                self._setzen(kennung, spalte, wert)
                if self.bei_aenderung is not None:
                    self.bei_aenderung(kennung, spalte, wert)

    def _fuellen(self, spaltenweise=False):
        """Strg+E / Strg+Shift+E: leere Zellen der Zeile oder Spalte.

        Welche leer sind und womit gefuellt wird, weiss der Aufrufer.
        """
        if self._offen is None or self.bei_fuellen is None:
            return "break"
        zeile, spalte = self._offen
        self._uebernehmen()
        if spaltenweise:
            self.bei_fuellen(None, spalte)
        else:
            self.bei_fuellen(zeile)
        if self._offen == (zeile, spalte):
            self._vorher = self.wert(zeile, spalte)
            self._aktiv.delete(0, "end")
            self._aktiv.insert(0, self._vorher)
            self._aktiv.select_range(0, "end")
        return "break"

    def schliessen(self):
        self._offen = None
        self.feld.place_forget()
        self.festfeld.place_forget()

    def _uebernehmen(self) -> bool:
        """Traegt ein, was im Feld steht - und meldet, ob sich etwas aendert."""
        if self._offen is None:
            return False
        zeile, spalte = self._offen
        neu = self._aktiv.get().strip()
        if zeile not in self._reihen or neu == self._vorher:
            return False
        self._setzen(zeile, spalte, neu)
        if self.bei_aenderung is not None:
            self.bei_aenderung(zeile, spalte, neu)
        return True

    def _setzen(self, zeile: str, spalte: str, wert: str):
        """Schreibt einen Wert in die Zelle - Text und Merkzettel."""
        self._zellen[(zeile, spalte)] = wert
        nummer = self._reihen.index(zeile) + 1
        von = self._anfang[spalte]
        bis = von + self._breiten[spalte]
        feld = self._wo(spalte)
        # Die Zeile kann kuerzer sein als das Raster, wenn die letzte
        # Spalte leer blieb. Dann wird aufgefuellt, bevor ersetzt wird.
        laenge = int(feld.index(f"{nummer}.end").split(".")[1])
        feld.configure(state="normal")
        if laenge < bis:
            feld.insert(f"{nummer}.end", " " * (bis - laenge))
        feld.delete(f"{nummer}.{von}", f"{nummer}.{bis}")
        feld.insert(f"{nummer}.{von}", self._gesetzt(wert, spalte))
        feld.configure(state="disabled")
        self._zelle_faerben(zeile, spalte, self._marken.get((zeile, spalte)))

    # ----------------------------------------------------------- Einfuegen
    def _eingefuegt(self, ereignis=None):
        """Ein Block aus der Zwischenablage - ab der offenen Zelle.

        Wer eine Spalte aus Excel kopiert, will sie hier nicht Zelle fuer
        Zelle abtippen. Also: einmal die obere Zelle anklicken,
        einfuegen, und der Block laeuft von dort nach unten und nach
        rechts weiter. Vorhandene Werte werden dabei ueberschrieben - das
        ist der Zweck.

        Ein einzelner Wert geht den gewoehnlichen Weg und landet im
        Eingabefeld; erst ab zwei Werten wird es ein Block.
        """
        if self._offen is None:
            return None
        try:
            inhalt = self.clipboard_get()
        except tk.TclError:
            return None
        block = zerlegen(inhalt)
        if len(block) <= 1 and len(block[0]) <= 1:
            return None
        zeile, spalte = self._offen
        self.schliessen()
        gesetzt, uebrig = self.einfuegen(zeile, spalte, block)
        if self.bei_block is not None:
            self.bei_block(gesetzt, uebrig)
        elif self.bei_aenderung is not None:
            for angaben in gesetzt:
                self.bei_aenderung(*angaben)
        return "break"

    def einfuegen(self, zeile, spalte, block) -> tuple:
        """Traegt einen Block ab dieser Zelle ein.

        Zurueck kommt, was gesetzt wurde - (Zeile, Spalte, Wert) - und
        wie viele Werte keinen Platz mehr fanden. Leere Felder im Block
        werden uebersprungen: eine leere Zelle in Excel heisst "hier
        steht nichts", nicht "loesche, was da steht".
        """
        zeile, spalte = str(zeile), str(spalte)
        aenderbar = [name for name in self._spalten
                     if name in self._aenderbar]
        reihen = self._tippbare_reihen()
        if zeile not in reihen or spalte not in aenderbar:
            return ([], 0)
        erste, links = reihen.index(zeile), aenderbar.index(spalte)
        gesetzt, uebrig = [], 0
        for hinunter, werte in enumerate(block):
            for hinueber, wert in enumerate(werte):
                unten, rechts = erste + hinunter, links + hinueber
                text = str(wert).strip()
                if unten >= len(reihen) or rechts >= len(aenderbar):
                    uebrig += 1 if text else 0
                    continue
                if not text:
                    continue
                ziel = (reihen[unten], aenderbar[rechts])
                if self.wert(*ziel) == text:
                    continue
                self._setzen(ziel[0], ziel[1], text)
                gesetzt.append((ziel[0], ziel[1], text))
        return (gesetzt, uebrig)

    def _weiter(self, zeilen: int, spalten: int):
        """Uebernimmt und geht eine Zelle weiter."""
        if self._offen is None:
            return "break"
        zeile, spalte = self._offen
        self._uebernehmen()
        ziel = self.nachbar(zeile, spalte, zeilen, spalten)
        self.schliessen()
        if ziel is not None:
            self.oeffnen(*ziel)
        return "break"

    def nachbar(self, zeile, spalte, zeilen: int, spalten: int):
        """Die naechste aenderbare Zelle in dieser Richtung - oder None.

        Am Zeilenende geht es in der naechsten Zeile weiter: eine Probe
        laesst sich so in einem Zug durchtippen. Nicht aenderbare Spalten
        werden uebersprungen, sonst bliebe das Feld an einer Zelle
        haengen, in der nichts zu tippen ist.
        """
        zeile, spalte = str(zeile), str(spalte)
        aenderbar = [name for name in self._spalten if name in self._aenderbar]
        reihen = self._tippbare_reihen()
        if not reihen or not aenderbar or zeile not in reihen \
                or spalte not in aenderbar:
            return None
        zeilenstelle = reihen.index(zeile)
        spaltenstelle = aenderbar.index(spalte)
        if spalten:
            spaltenstelle += spalten
            if spaltenstelle >= len(aenderbar):
                spaltenstelle, zeilenstelle = 0, zeilenstelle + 1
            elif spaltenstelle < 0:
                spaltenstelle, zeilenstelle = (len(aenderbar) - 1,
                                               zeilenstelle - 1)
        else:
            zeilenstelle += zeilen
        if not 0 <= zeilenstelle < len(reihen):
            return None
        return (reihen[zeilenstelle], aenderbar[spaltenstelle])
