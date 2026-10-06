"""
TRDF-Pruefmodul - die Seite "TRDF Pruefung"
===========================================

Hier laeuft zusammen, was trdf.py rechnet und was trdfpruefung.py davon
haelt: eine Serie waehlen, ihre TRDF-Untersuchungsmethoden abfragen,
eine davon waehlen - und daneben steht, was das LIMS daraus gemacht hat
und ob das Ergebnis in einem Boden vorkommen kann.

Ausgeloest aus dem Reiter "TRDF Pruefung" von LabControl (TestLims) als
Einzelauswertung: eine Serie, eine Untersuchungsmethode. Nicht
mitgekommen sind die Profilansichten (Profil-CSV, Plot und Tiefenstufe,
Profilfenster mit dem Plotvergleich) und der Weg ueber einzelne
Probennummern. Geblieben sind die drei Tabellen, das Aendern der
Rohwerte, der Bodenblock beim Klick auf die Probe und der Rueckweg in
das LIMS.

Der Weg zur Serie
-----------------
Erst die Serie, dann "Abfragen": gefragt wird, welche
Untersuchungsmethoden die Serie fuehrt, und davon bleiben alle, deren
Kuerzel "TRDF" traegt (ohne die ausgeschlossenen, siehe
lims_db.AUSGESCHLOSSENE_METHODEN). Fuehrt die Serie genau eine, wird sie
gleich geholt; fuehrt sie mehrere, wird im Feld daneben gewaehlt - und
mit der Wahl geholt.

Zwei Wege zu den Rohwerten
--------------------------
Die Untersuchungsmethode aus der Probenvorbereitung laesst sich
einfuegen ("UM einfuegen") - damit prueft man, ob die Uebernahme ins
LIMS stimmt. Sonst kommen die Rohwerte aus dem Teilprobenanhang, also
aus der Stelle, aus der das LIMS selbst rechnet. Welcher Weg gilt,
ergibt sich von selbst: ist eine UM eingefuegt, gilt sie. Von Hand
geaenderte Werte stechen in beiden Faellen.

Drei Unterreiter, und warum es drei sind
-----------------------------------------
Ein Rohwert kann an drei Stellen anders aussehen: im eingefuegten Text,
in der Ergebnistabelle des LIMS, und in dem, was das LIMS daraus
gerechnet hat. "Rohwerte" und "Ergebnisse" stellen das nebeneinander -
sonst sieht man zwar, *dass* etwas nicht stimmt, aber nicht, wo es
angefangen hat. "Pruefung" fragt etwas anderes: die Rechnung kann
stimmen und der Wert trotzdem nicht in den Boden passen.

Von Hand aendern
----------------
Die Rohwerte lassen sich ueberschreiben. Damit laesst sich die Frage
beantworten, die beim Pruefen als naechstes kommt: "und wenn hier 1,8
staende - kaeme dann das heraus, was gebucht ist?" Gerechnet und
geprueft wird sofort neu. In das LIMS geht eine Aenderung erst ueber den
Knopf "Export" - nach einer bestaetigten Uebersicht und
einer Sicherung (trdfexport.py).
"""

from __future__ import annotations

import datetime as dt
import decimal
import os
import textwrap
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import eingaberaster
import lims_db
import trdf
import trdfbild
import trdfblock
import trdfexport
import trdflegende
import trdfpruefung
import trdfrohpruefung
import trdfserie
from widgets import RoundedButton, Style, ToolTip

# Wie viele Nachkommastellen die Anzeige zeigt.
STELLEN = 3

# Der Wiederfindungsgrad steht in Prozent und wird gelesen, nicht
# nachgerechnet - eine Stelle genuegt. Gerechnet wird weiter mit dem
# vollen Wert, wie ihn das LIMS liefert.
STELLEN_WGH = 1

# Woher die Rohwerte kommen, mit denen gerechnet wird - es ergibt sich
# von selbst:
#
#   eingefuegte UM  die Liste aus der Probenvorbereitung, sobald eine
#                   eingefuegt und uebernommen ist. Damit prueft man,
#                   ob die Uebernahme ins LIMS stimmt.
#   LIMS            sonst die Rohwerte der Ergebniszeilen im LIMS.
#
# Wo die eingefuegte UM eine Luecke hat, tritt das LIMS ein; von Hand
# geaenderte Werte stechen immer. "Leeren" im Einfuegefenster schaltet
# zurueck auf das LIMS. Ob der Teilprobenanhang - aus ihm rechnet das
# LIMS - dasselbe sagt wie die Ergebniszeile, prueft die Rohwertpruefung
# ohnehin ("Rohwert am Anhang weicht ab"), und "Anhang angleichen"
# bringt beides zusammen.
QUELLE_TEXT = "eingefuegte UM"
QUELLE_LIMS = "LIMS"
QUELLEN = (QUELLE_TEXT, QUELLE_LIMS)

# Die Probenart steckt im Seriennamen: 2026B051 - das Zeichen hinter
# der Jahreszahl. Dieselben Namen wie in der Tabelle PROBENART des
# LIMS: 1 Boden, 2 Pflanze, 3 Wasser, 4 Humus. Ein "H" ist damit
# Humus und nicht Holz - Holz gibt es dort nicht, und eine Humusserie
# unter falschem Namen zu fuehren heisst, sie nicht zu finden.
PROBENARTEN = {"B": "Boden", "P": "Pflanze", "H": "Humus", "W": "Wasser"}

# Und dieselben Namen zur PART_ID der Ergebniszeile. Das ist die
# Auskunft des LIMS; der Buchstabe im Seriennamen ist die
# Hausschreibweise davon.
PROBENART_ZU_ID = {1: "Boden", 2: "Pflanze", 3: "Wasser", 4: "Humus"}

# Wie die Spalte heisst, in der das Urteil steht - in beiden Tabellen
# dieselbe, damit sie an derselben Stelle gesucht wird.
BEWERTUNGSSPALTE = trdfrohpruefung.BEWERTUNGSSPALTE

# Wie die drei Tabellen in den Einstellungen heissen. Unter diesen
# Namen liegen ihre Spaltenreihenfolge und die Spalten, die links
# stehen bleiben - und unter denselben stehen sie im Fenster „Info“.
BLATT_ROH = "Rohwerte"
BLATT_ERGEBNIS = "Ergebnisse"
BLATT_PRUEFUNG = "Pruefung"

# Was in der Ergebnistabelle steht, wenn gebucht und gerechnet
# auseinandergehen. Genannt werden die Groessen selbst: bei zwoelf
# Paaren ist "hier stimmt etwas nicht" keine Auskunft.
AUSEINANDER = "LIMS ungleich gerechnet: {}"

# Was im Pruefblatt vor jedem anderen Urteil steht: ohne vollstaendige
# Rohwerte hat das LIMS nichts gerechnet, und LabControl auch nicht.
ROHWERTE_UNVOLLSTAENDIG = "Rohwerte unvollstaendig"

# Wie breit die Spalten des Pruefblattes stehen. Die Kopfzeile traegt
# den Parameternamen; wird sie abgeschnitten, ist die Spalte nicht mehr
# zu erkennen - deshalb steht die Breite hier und nicht auf Vorgabe.
BREITEN = {"Zeile": 56, "Probe-Nr.": 104, "UM": 40, "ME": 40,
           "Skelettanteil": 104,
           "SKA63": 88, "SKAgs63": 88, "Faktor B/F": 80,
           "GBFAnt63gs": 104, "FBVorrat": 100, "TRDF": 88, "Cges": 84,
           "CO3": 84, "Bewertung": 320}

# Was ueber einer Zelle steht, deren Wert von einer anderen Anlage
# derselben Probe kommt. Die PROB_ID gehoert dazu: ohne sie ist die
# Zahl nicht nachzusehen.
NACHGETRAGEN = ("nachgetragen aus PROB_ID {prob_id}{woher} - an dieser "
                "Probe der Serie ist kein Aufschluss gebucht")

# Was im Exportbericht steht, solange nichts geschrieben wurde. Der
# Reiter ist dann kein Fehler, sondern nur noch leer.
BERICHT_LEER = "Es wurde in dieser Sitzung noch nichts geschrieben."

# Was im Methodenfeld steht, solange keine Serie abgefragt ist.
METHODE_OFFEN = "erst abfragen"

# Schrift und Zeilenluft der Tabellen auf der Seite. Groesser als in
# LabControl: hier wird getippt, und eine Zelle, die man trifft, ohne
# hinzusehen, ist die halbe Arbeit.
SCHRIFT = 11
ZEILENLUFT = 3

# Wie die berechneten Groessen ueber den Rohwerten stehen: eingeklappt
# oder offen. Von Haus aus eingeklappt - dann gehoert das ganze Fenster
# den Rohwerten.
BERECHNETE_AN = "an"
BERECHNETE_AUS = "aus"
BERECHNETE_EIN_TEXT = "\u25b8 Berechnete Groessen"
EINFUEGEN_TEXT = "UM einfuegen ..."
BERECHNETE_AUS_TEXT = "\u25be Berechnete Groessen"

# Die Grossansicht der Rohwerte: eine Zeile doppelt so hoch wie im
# Reiter. Die Haelfte davon kommt aus der groesseren Schrift, die
# andere aus Luft ueber und unter der Zeile - waere die Schrift allein
# doppelt so gross, passten nur noch halb so viele Spalten
# nebeneinander, und darum geht es hier gerade.
GROSS_SCHRIFT = 13
GROSS_LUFT = 5
GROSS_ZEILEN = 18


def _nachtragsteil(geholt) -> dict:
    """Das Ergebnis von `_nachtrag_holen` als Eintraege des Abrufs."""
    liste, fehler = geholt
    return {"aufschlussnachtrag": liste, "nachtragsfehler": fehler}


def _kennung(zeile) -> str:
    """Die Zeilenkennung einer Ergebniszeile - mit UM/ME bei Wiederholungen."""
    return trdf.probenkennung(zeile.get("probe_nr"), zeile.get("wdh_um"),
                              zeile.get("wdh_me"))


def _kennungen(ergebnisse) -> dict:
    """PROB_ID -> Zeilenkennung, ueber alle Ergebniszeilen eines Abrufs."""
    return {zeile["prob_id"]: _kennung(zeile) for zeile in ergebnisse or ()}


def _probenkennungen(ergebnisse) -> list:
    """Die PROB_ID eines Abrufs - einmal je Probe.

    Sie stehen in den Ergebniszeilen schon da. Eine Abfrage, die sie
    benutzt, greift ueber den Primaerschluessel; eine, die die
    Probennummer gross schreibt, geht die ganze Tabelle durch.
    """
    return sorted({zeile["prob_id"] for zeile in ergebnisse or []
                   if zeile.get("prob_id") is not None})


def _ohne_anhang(ergebnisse, anhang) -> list:
    """Die PROB_ID der Proben, zu denen kein Teilprobenanhang kam.

    Nur nach diesen wird nachgefragt. Steht der Anhang an jeder Probe
    der Serie - der Regelfall -, bleibt die Liste leer und die
    Abfrage entfaellt ganz.

    Gefragt wird nach der Probe und nicht nach der Anlage: kam der
    Anhang unter einer anderen PROB_ID derselben Probennummer, ist er
    da, und ein zweites Mal zu fragen brachte dieselben Zeilen.
    """
    haben = {zeile.get("prob_id") for zeile in anhang or ()}
    nummern = {trdf.probenschluessel(zeile.get("probe_nr"))
               for zeile in anhang or ()}
    nummern.discard("")
    offen = []
    for zeile in ergebnisse or ():
        if zeile.get("prob_id") in haben:
            continue
        if trdf.probenschluessel(zeile.get("probe_nr")) in nummern:
            continue
        offen.append(zeile.get("prob_id"))
    return sorted({kennung for kennung in offen if kennung is not None})


def _mit_nachtrag(zugang, um_id, ergebnisse, anhang) -> list:
    """Den Anhang um die Zeilen anderer Anlagen derselben Probe ergaenzen.

    Der Teilprobenanhang haengt an der PROB_ID, und dieselbe Probe
    steht im LIMS mehrfach - einmal je Untersuchungsmethode. Die
    Serie sieht dann nur die eine Anlage, und die Rohwerte bleiben
    leer, obwohl sie gebucht sind.

    Nachgefragt wird unter derselben Methode: wer TRDF3.2 abruft,
    bekommt die Rohwerte der TRDF3.2 und nicht die der verworfenen
    TRDF3.1, die daneben an derselben Probe haengt.
    """
    offen = _ohne_anhang(ergebnisse, anhang)
    if not offen:
        return list(anhang or [])
    return list(anhang or []) + lims_db.trdf_rohwerte_nachtrag(
        zugang, offen, um_id)


def _ohne_aufschluss(ergebnisse, aufschluss) -> list:
    """Die PROB_ID der Proben, denen Cges oder CO3 fehlt.

    Nur nach diesen wird nachgefragt. Steht der Aufschluss an jeder
    Probe der Serie - der Regelfall -, bleibt die Liste leer und die
    Abfrage entfaellt ganz.
    """
    gebucht = {}
    for eintrag in aufschluss or []:
        name = trdf.ATNULL_PARAMETER.get(eintrag.get("para_id"))
        if name and str(eintrag.get("mw") or "").strip():
            gebucht.setdefault(eintrag["prob_id"], set()).add(name)
    vollstaendig = set(trdf.ATNULL_PARAMETER.values())
    return [kennung for kennung in _probenkennungen(ergebnisse)
            if gebucht.get(kennung, set()) != vollstaendig]


def methodentexte(methoden) -> list:
    """Je Untersuchungsmethode ein Text, der nur sie meint.

    Das Haus fuehrt dieselbe Methode je Probenart einmal: TRDF3.2
    fuer den Boden und TRDF3.2 fuer den Humus sind zwei UM_ID mit
    demselben Kuerzel. In einer Liste, die zweimal "TRDF3.2" zeigt,
    ist die zweite nicht zu waehlen - und welche die erste war, stand
    nirgends. Deshalb traegt der Text die UM_ID, sobald ein Kuerzel
    mehrfach vorkommt; kommt es einmal vor, bleibt es, wie es ist.

    Zurueck kommen (um_id, Kuerzel, Text) in der Folge der Liste.
    """
    haeufig = {}
    for _um, kuerzel in methoden or ():
        name = str(kuerzel or "").strip()
        haeufig[name] = haeufig.get(name, 0) + 1
    gebaut = []
    for um_id, kuerzel in methoden or ():
        name = str(kuerzel or "").strip()
        gebaut.append((um_id, name,
                       name if haeufig.get(name, 0) < 2
                       else f"{name} (UM {um_id})"))
    return gebaut



def probenart(serie: str) -> str:
    """Boden, Pflanze, Holz oder Wasser - aus dem Namen der Serie."""
    text = str(serie or "").strip().upper()
    if len(text) < 5 or not text[:4].isdigit():
        return ""
    return PROBENARTEN.get(text[4], "")


def zahltext(wert, stellen=STELLEN) -> str:
    """Eine Zahl fuer die Anzeige - mit Komma und fester Stellenzahl."""
    if not isinstance(wert, trdf.D):
        return trdf.MARKE if wert == trdf.MARKE else str(wert or "")
    gerundet = wert.quantize(trdf.D(1).scaleb(-stellen))
    return str(gerundet).replace(".", ",")


# Wie ein Rohwert in der Tabelle dasteht - nur die Anzeige: gerechnet,
# verglichen und geschrieben wird mit dem vollen Wert. Ohne eigene Regel
# hoechstens vier signifikante Stellen; die Stellen vor dem Komma werden
# nie abgeschnitten (12345,6 zeigt 12346). Geschluesselt ist auf das
# Formelkuerzel ohne fuehrenden Unterstrich, gross geschrieben.
SIGNIFIKANT = 4
ROH_STELLEN = {
    "TRDV": 0,          # Variante - immer eine ganze Zahl
    "TSM": 0,           # Tiefenstufenmaechtigkeit
    "DICHTEGB": 2,      # Dichte Grobboden
    "GBFANT": 0,        # Grobbodenflaechenanteil
    "FBLFL": 2,         # Faktor Bergland/Flachland
    "SKAFOTO": 0,       # Skelettanteil aus dem Foto
    "TRDFGESCH": 3,     # Trockenrohdichte geschaetzt
    "VOLSZ": 0,         # Volumen Stechzylinder
}
# Die Massen: hoechstens eine Nachkommastelle.
MASSEN = ("GMSZ", "GBM", "MSCHAUFEL", "MMINI")
MASSE_STELLEN = 1


def _ohne_nullen(text: str) -> str:
    """Nullen am Ende der Nachkommastellen weg - und das Komma, wenn nichts bleibt."""
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def rohtext(kuerzel, wert) -> str:
    """Ein Rohwert fuer die Tabelle - gerundet nach seiner Regel.

    Was keine Zahl ist - ein x, ein Verweis wie "##1093" -, bleibt wie
    es ist; leer wird zum x. Ob der Wert aus dem LIMS, aus der
    eingefuegten UM oder von Hand kommt, ist gleich.
    """
    zahl = trdf.zahl(wert)
    if zahl is None:
        text = str(wert if wert is not None else "").strip()
        return text or trdf.MARKE
    name = str(kuerzel or "").lstrip("_").upper()
    if name in ROH_STELLEN:
        stellen, fest = ROH_STELLEN[name], True
    else:
        stellen = 0 if zahl.is_zero() else \
            max(0, SIGNIFIKANT - 1 - zahl.adjusted())
        if name.startswith(MASSEN):
            stellen = min(stellen, MASSE_STELLEN)
        fest = False
    try:
        gerundet = zahl.quantize(trdf.D(1).scaleb(-stellen),
                                 rounding=decimal.ROUND_HALF_UP)
    except decimal.InvalidOperation:
        return str(wert).strip()
    text = format(gerundet, "f")
    if not fest:
        text = _ohne_nullen(text)
    if text in ("-0", "-0.0", "-0.00", "-0.000"):
        text = text[1:]
    return text.replace(".", ",")


def _differenz(alt, neu, stellen=None) -> str:
    """Wie weit sich ein Wert bewegt hat - mit Vorzeichen, "" ohne zwei Zahlen."""
    if not isinstance(alt, trdf.D) or not isinstance(neu, trdf.D):
        return ""
    unterschied = neu - alt
    text = zahltext(unterschied, stellen) if stellen is not None else \
        rohtext("", unterschied)
    return text if text.startswith("-") else f"+{text}"


def aenderungstext(alt: str, neu: str, differenz="", im_lims=None) -> str:
    """Der Hinweis ueber einer roten Zelle: alter Wert und von -> auf."""
    zeilen = [f"Alter Wert: {alt}",
              f"Geaendert von {alt} auf {neu}"
              + (f"  ({differenz})" if differenz else "")]
    if im_lims is not None:
        zeilen.append(f"Im LIMS gebucht: {im_lims}")
    return "\n".join(zeilen)


def erklaerung(*saetze) -> str:
    """Ein Erklaertext fuer das i - in Zeilen, die ein Hinweisfenster traegt."""
    return "\n".join(textwrap.fill(" ".join(saetze), 72).splitlines())


# Was im Rohwertraster wie in Excel geht - steht im i der Rohwerte.
TASTEN = ("Tab / Pfeile / Eingabe   Zelle wechseln\n"
          "Strg+C / Strg+V          kopieren / Block aus Excel einfuegen\n"
          "Strg+D                   Wert der Zelle darueber uebernehmen\n"
          "Strg+Shift+D             Wert nach unten kopieren (bis zum Ende)\n"
          "Strg+L                   Wert nach unten, nur in leere Zellen\n"
          "Strg+I                   nach unten hochzaehlen (+1 je Zeile)\n"
          "Strg+E                   leere Zellen der Probe mit x fuellen\n"
          "Strg+Shift+E             leere Zellen der Spalte mit x fuellen\n"
          "Variante (_TRDV):  x = alles x,  0 = Zeile leeren,\n"
          "                   1-7 = nicht benoetigte Felder bekommen x")

PRUEF_ERKLAERUNG = erklaerung(
    "Die bodenphysikalischen Werte, nach Probe-Nr. "
    "sortiert. Geprueft wird, was das Pruefmodul gerechnet "
    "hat: der Skelettanteil gegen 0 und 100 Prozent und "
    "gegen den geschaetzten Grobboden, der Abstand "
    "zwischen gemessenem und geschaetztem Skelettanteil, "
    "der Feinbodenvorrat gegen null und die "
    "Trockenrohdichte gegen den Sollbereich ihrer "
    "Kohlenstoffklasse. Dazu, was erst im Vergleich mit "
    "der Serie auffaellt: ein Wiederfindungsgrad, der "
    "nicht zum organischen Kohlenstoff passt, und "
    "Rohwerte, die im LIMS an zwei Stellen verschieden "
    "stehen. Was auffaellt, steht in der Bewertung.")


class Infozeichen(tk.Label):
    """Ein kleines "i": der Erklaertext steht dahinter und nicht im Weg.

    Die Seite traegt sonst ueber jeder Tabelle einen Absatz, den man
    einmal liest und danach nur noch ueberspringt. Hier kommt er, wenn
    die Maus auf dem i steht - oder sofort bei einem Klick darauf.
    """

    def __init__(self, eltern, text: str, dezent=False):
        # Dezent: grau statt blau - fuer das, was man einmal nachschlaegt
        # und dann kann, wie die Tastenkuerzel.
        super().__init__(eltern, text="i",
                         fg="#64748b" if dezent else "#ffffff",
                         bg="#e2e8f0" if dezent else Style.ACCENT,
                         font=(Style.FONT, 8, "bold italic"), width=2,
                         cursor="question_arrow", padx=0, pady=0)
        self._hinweis = ToolTip(self, text)
        if dezent:
            self._hinweis.font = ("Consolas", 9)
        self.bind("<Button-1>", lambda e: self._sofort())

    @property
    def text(self) -> str:
        return self._hinweis.text

    def setzen(self, text: str):
        self._hinweis.text = text

    def _sofort(self):
        self._hinweis.hidetip()
        self._hinweis.showtip()


class TrdfSeite(tk.Frame):
    """Die ganze Seite - Auswahl, Einfuegefeld und die drei Tabellen."""

    def __init__(self, eltern, zugang_holen, im_hintergrund, ordner=None,
                 konfig=None):
        super().__init__(eltern, bg=Style.BG, padx=8, pady=6)
        self._zugang_holen = zugang_holen
        self._im_hintergrund = im_hintergrund
        self._ordner = ordner or config.get_runtime_dir()
        # Die Einstellungen: dort stehen die Beschreibungen der Legende
        # und die zuletzt gewaehlte Serie. Ohne uebergebene wird eine
        # eigene geoeffnet - im Betrieb gibt das Hauptfenster seine mit.
        self._konfig = konfig
        # Diese gehoeren *nicht* in `_leeren` - sie gehoeren der Auswahl
        # und nicht dem Abruf. Stuenden sie dort, waere die Methodenliste
        # nach jedem Abruf weg, und ein Wechsel der Methode ginge nicht.
        #
        # Die TRDF-Serien aus dem Fahrplan - fuer die Liste im Serienfeld.
        self.serienliste = []
        # Die Serie, zu der die Methodenliste gehoert. Steht im Feld
        # inzwischen eine andere, ist die Liste nicht mehr ihre.
        self.abgefragte_serie = ""
        # (um_id, Kuerzel, Text) der TRDF-Methoden dieser Serie - der Text
        # steht im Feld und meint genau eine Methode, auch wo zwei
        # dasselbe Kuerzel tragen.
        self.methodenwahl = []
        self._leeren()
        self._aufbauen()

    def _leeren(self):
        self.um_id = None
        self.um_kuerzel = ""
        self.methoden = []           # Pruefmethoden mit Formeln
        self.formeln = {}            # Formelkuerzel -> Formel
        self.folge = []              # Rechenreihenfolge
        self.rohnamen = {}           # Spaltenname -> Formelkuerzel
        self.rohkuerzel = {}         # Kuerzel am Rohwert -> das der Formel
        self.parameternamen = {}     # Formelkuerzel -> Name im LIMS
        self.rohliste = []           # Formelkuerzel in der Reihenfolge des LIMS
        self.gebucht = {}            # probe -> Formelkuerzel -> Text
        self.limsroh = {}            # probe -> Formelkuerzel -> Text
        self.wgh = {}                # probe -> Text
        self.aufschluss = {}         # probe -> {"Cges", "CO3"}
        self.aufschlussherkunft = {}  # (probe, Name) -> woher der Wert kam
        self.eingefuegt = {}         # probe -> Formelkuerzel -> Text
        self.quelle = QUELLE_LIMS    # woher die Rohwerte kommen - von selbst
        self.vonhand = {}            # (probe, Formelkuerzel) -> Text
        self.zeilen = {}             # (probe, Kuerzel) -> Ergebniszeile
        self.anhang = {}             # (probe, Kuerzel) -> Zeile am Anhang
        self.bloecke = {}            # probe -> offenes Blockfenster
        self._mit_hand = {}          # gemerkte Rechnungen, mit Handwerten
        self._ohne_hand = {}         # dieselben ohne sie
        self.proben = []             # (lnr, probe)
        self.wiederholungen = {}     # probe -> (Probennummer, UM, ME)
        self.arbeitszeile = None     # die Probe, in der gerade getippt wird
        self.letzter_export = None   # der Bericht des letzten Schreibwegs
        self._ausstehend = {}        # verdeckte Tabelle -> wie sie zu fuellen ist

    # ------------------------------------------------------------- Aufbau
    def _aufbauen(self):
        # Der Kopf ist so knapp wie moeglich: drei Zeilen, damit den
        # Tabellen darunter der Platz bleibt.
        kopf = tk.Frame(self, bg=Style.CARD, highlightbackground=Style.BORDER,
                        highlightthickness=1, padx=12, pady=6)
        kopf.pack(fill="x")
        titel = tk.Frame(kopf, bg=Style.CARD)
        titel.pack(fill="x", pady=(0, 4))
        tk.Label(titel, text="Die Rechnung des LIMS nachrechnen und pruefen",
                 bg=Style.CARD, fg=Style.TEXT, font=Style.font(11, "bold"),
                 anchor="w").pack(side="left")
        self.info_kopf = Infozeichen(titel, erklaerung(
            "Das LIMS bildet aus den Rohwerten einer TRDF-Serie ein Dutzend "
            "Groessen. Das Pruefmodul rechnet sie mit denselben Formeln noch "
            "einmal, stellt beides nebeneinander und prueft, ob die "
            "bodenphysikalischen Werte zueinander passen.",
            "Erst die Serie waehlen, dann \u201eAbfragen\u201c: angeboten "
            "werden alle Untersuchungsmethoden der Serie, deren Kuerzel TRDF "
            "traegt.",
            "Rohwerte lassen sich von Hand aendern - dann wird sofort neu "
            "gerechnet; in das LIMS geht eine Aenderung erst ueber "
            "\u201eExport\u201c."))
        self.info_kopf.pack(side="left", padx=(8, 0))
        wahl = tk.Frame(kopf, bg=Style.CARD)
        wahl.pack(fill="x")
        tk.Label(wahl, text="Serie", bg=Style.CARD, fg=Style.MUTED,
                 font=Style.font(9)).grid(row=0, column=0, sticky="w",
                                          padx=(0, 6))
        self.v_serie = tk.StringVar(value=self._gemerkt("serie"))
        self.feld_serie = ttk.Combobox(wahl, textvariable=self.v_serie,
                                       width=14)
        self.feld_serie.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.feld_serie.bind("<Return>", lambda e: self._abfragen())
        self.feld_serie.bind("<<ComboboxSelected>>",
                             lambda e: self._serie_gewechselt())
        self.v_serie.trace_add("write", lambda *_: self._serie_getippt())
        ToolTip(self.feld_serie,
                "Die Serien aus dem Fahrplan, die eine TRDF-Methode "
                "fuehren.\nEine andere laesst sich eintippen - sie muss "
                "nicht im Fahrplan stehen.")
        self.knopf_abfragen = RoundedButton(
            wahl, text="Abfragen", width=120, height=30, bg="#15803d",
            command=self._abfragen)
        self.knopf_abfragen.grid(row=0, column=2, sticky="w", padx=(0, 16))
        ToolTip(self.knopf_abfragen,
                "Fragt, welche Untersuchungsmethoden diese Serie fuehrt,\n"
                "und bietet alle an, deren Kuerzel TRDF traegt. Ist es\n"
                "genau eine, wird die Serie gleich geholt.")
        tk.Label(wahl, text="Untersuchungsmethode", bg=Style.CARD,
                 fg=Style.MUTED, font=Style.font(9)).grid(
            row=0, column=3, sticky="w", padx=(0, 6))
        self.v_methode = tk.StringVar()
        self.feld_methode = ttk.Combobox(
            wahl, textvariable=self.v_methode, width=18, state="disabled",
            values=[])
        self.feld_methode.grid(row=0, column=4, sticky="w", padx=(0, 12))
        self.v_methode.set(METHODE_OFFEN)
        self.feld_methode.bind("<<ComboboxSelected>>",
                               lambda e: self._methode_gewaehlt())
        ToolTip(self.feld_methode,
                "Die TRDF-Methoden der abgefragten Serie. Die Wahl holt\n"
                "die Serie unter dieser Methode.\n\n"
                "Das Haus fuehrt dieselbe Methode je Probenart einmal:\n"
                "TRDF3.2 fuer den Boden und TRDF3.2 fuer den Humus sind\n"
                "zwei UM_ID. Wo zwei dasselbe Kuerzel tragen, steht die\n"
                "UM_ID dabei.")
        # Was gerade geladen ist - Methode und Probenart - steht in der
        # Titelzeile; in der Auswahlzeile ist dafuer kein Platz.
        self.auskunft = tk.Label(titel, text="", bg=Style.CARD,
                                 fg=Style.MUTED, font=Style.font(9),
                                 anchor="w")
        self.auskunft.pack(side="left", padx=(16, 0))
        wahl.grid_columnconfigure(5, weight=1)
        # Wiederholungen (UM oder ME ueber 1) stehen von Haus aus nicht
        # da: gearbeitet wird an der Erstmessung. Ein Haken holt sie
        # unter die Erstmessungen - in allen Reitern.
        self.v_wiederholungen = tk.BooleanVar(value=False)
        self.schalter_wiederholungen = tk.Checkbutton(
            wahl, text="UM/ME ≠ 1", variable=self.v_wiederholungen,
            command=self._wiederholungen_umschalten, bg=Style.CARD,
            fg=Style.MUTED, activebackground=Style.CARD,
            font=Style.font(8), padx=0, pady=0, bd=0,
            highlightthickness=0)
        self.schalter_wiederholungen.grid(row=0, column=5, sticky="w")
        ToolTip(self.schalter_wiederholungen,
                "Zeigt auch die Wiederholungen - Proben, deren UM oder ME\n"
                "nicht 1 ist. Sie stehen unter den Erstmessungen: zuerst\n"
                "die Wiederholungen der Untersuchungsmethode (UM 2, ...),\n"
                "dann die der Messung (ME 2, ...), jeweils nach\n"
                "Probennummer. Gilt fuer alle Reiter und die Blaetter.")
        self.knopf_export = RoundedButton(
            titel, text="Export", width=120, height=28,
            bg="#15803d", command=self._lims_schreiben)
        self.knopf_export.pack(side="right")
        self.knopf_zurueck = RoundedButton(
            titel, text="Load backup", width=140, height=28,
            bg="#6b7268", command=self._zurueckspielen)
        self.knopf_zurueck.pack(side="right", padx=(0, 10))
        ToolTip(self.knopf_zurueck,
                "Liest eine Datei aus dem Ordner „trdf_backup“ und stellt\n"
                "den Stand wieder her, der vor der Korrektur im LIMS\n"
                "stand - Ergebniszeile und Teilprobenanhang.")
        ToolTip(self.knopf_export,
                "Export in das LIMS: schreibt die von Hand geaenderten\n"
                "und die vorgemerkten Werte und die Groessen,\n"
                "die sich dadurch verschoben haben, in das LIMS zurueck.\n"
                "Vorher zeigt eine Uebersicht Zeile fuer Zeile, was alt und\n"
                "was neu waere; der alte Stand geht in eine Sicherung.")

        # Die Liste aus der Probenvorbereitung ist eine Option und hat ihr
        # eigenes Fenster - so bekommt sie den ganzen Platz und nimmt der
        # Seite keinen weg.
        # Woher die Rohwerte kommen, ergibt sich von selbst: ist eine UM
        # eingefuegt, gilt sie, sonst das LIMS. Hier steht nur, was gilt.
        self.quellanzeige = tk.Label(wahl, text="", bg=Style.CARD,
                                     fg=Style.MUTED, font=Style.font(9),
                                     anchor="e")
        self.quellanzeige.grid(row=0, column=7, sticky="e")
        ToolTip(self.quellanzeige,
                "Woher die Rohwerte kommen, mit denen gerechnet wird.\n"
                "Ist eine Untersuchungsmethode eingefuegt (\u201eUM einfuegen\u201c),\n"
                "gilt sie; sonst die Rohwerte des LIMS.\n"
                "\u201eLeeren\u201c im Einfuegefenster schaltet zurueck\n"
                "auf das LIMS.\n"
                "Von Hand geaenderte Werte stechen immer.")
        self.knopf_einfuegen = RoundedButton(
            wahl, text=EINFUEGEN_TEXT, width=170, height=28,
            bg="#334155", command=self.einfuegen_oeffnen)
        self.knopf_einfuegen.grid(row=0, column=6, sticky="e", padx=(0, 8))
        ToolTip(self.knopf_einfuegen,
                "Optional: die Untersuchungsmethode aus der\n"
                "Probenvorbereitung einfuegen\n"
                "(dort \u201eaktueller Block\u201c -> kopieren). Oeffnet ein\n"
                "eigenes Fenster. Nach \u201eUebernehmen\u201c wird mit dieser\n"
                "Liste gerechnet; Werte, die im LIMS noch fehlen, werden\n"
                "fuer den Export vorgemerkt.")

        # Die Statuszeile steht immer da - sie sagt, was gerade geschieht.
        self.stand = tk.Label(kopf, text="", bg=Style.CARD, fg=Style.MUTED,
                              font=Style.font(9), anchor="w", justify="left",
                              wraplength=1300)
        self.stand.pack(fill="x", pady=(4, 0))

        self.reiter = ttk.Notebook(self)
        self.reiter.pack(fill="both", expand=True, pady=(6, 0))
        self.reiter.bind("<<NotebookTabChanged>>",
                         lambda _e: self._nachziehen(), add="+")
        self._rohwerte_reiter()
        self._ergebnis_reiter()
        self._pruef_reiter()
        self._bericht_reiter()
        self._quelle_zeigen()
        if self._gemerkt("trdf_berechnete") == BERECHNETE_AN:
            self._berechnete_umschalten(merken=False)
        self.serienliste_laden()

    def _rohwerte_reiter(self):
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Rohwerte ")
        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Rohwertblatt CSV", width=150,
                      height=28, bg="#334155",
                      command=self._rohblatt_speichern).pack(side="left")
        RoundedButton(leiste, text="Aenderungen CSV", width=150,
                      height=28, bg="#334155",
                      command=self._aenderungen_speichern).pack(
            side="left", padx=(8, 0))
        # Wie im Pruefblatt: aus ist das Blatt ueber die ganze Serie, an
        # der Arbeitsvorrat dessen, der die Befunde abarbeitet.
        self.v_nur_rohbefunde = tk.BooleanVar(value=False)
        self.schalter_rohbefunde = ttk.Checkbutton(
            leiste, variable=self.v_nur_rohbefunde,
            text="nur Eintraege mit Bewertung",
            command=self._rohwerte_zeigen)
        self.schalter_rohbefunde.pack(side="left", padx=(14, 0))
        ToolTip(self.schalter_rohbefunde,
                "Zeigt nur die Proben, zu deren Rohwerten etwas zu\n"
                "sagen ist. Gerechnet und geschrieben wird weiter\n"
                "ueber die ganze Serie, und das Rohwertblatt als CSV\n"
                "bleibt vollstaendig. Auch das grosse Fenster zeigt\n"
                "dann nur diese Proben.")
        self._infoknopf(leiste, self._rohlegende_zeigen)
        gross = RoundedButton(leiste, text="Maximieren", width=120,
                              height=28, bg="#1d4ed8",
                              command=self._gross_zeigen)
        gross.pack(side="left", padx=(8, 0))
        ToolTip(gross,
                "Dieselbe Tabelle in einem eigenen, grossen Fenster:\n"
                "doppelte Zeilenhoehe, wenig drumherum. Alles geht\n"
                "dort wie hier - Tabulator, Pfeile, Einfuegen aus\n"
                "Excel, Klick auf die Probennummer. Was dort steht,\n"
                "steht sofort auch hier.")
        knopf = RoundedButton(leiste, text="Anhang angleichen", width=170,
                              height=28, bg="#7c5e10",
                              command=self._anhang_angleichen)
        knopf.pack(side="left", padx=(8, 0))
        ToolTip(knopf,
                "Schreibt den Wert der Ergebniszeile in den\n"
                "Teilprobenanhang - fuer die Rohwerte, die im LIMS\n"
                "an den beiden Stellen verschieden stehen.\n"
                "Auch dieser Weg geht ueber eine bestaetigte\n"
                "Uebersicht und nach einer Sicherung.")
        self.info_roh = Infozeichen(leiste, erklaerung(
            "Was aus der gewaehlten Quelle kommt, daneben was in "
            "der Ergebnistabelle des LIMS steht. "
            "Eine Zelle laesst sich anklicken und ueberschreiben; "
            "Tab geht in der Zeile weiter, die Pfeile in alle "
            "Richtungen, Eingabe eine Zeile tiefer. Aus Excel "
            "kopierte Werte lassen sich in die obere Zelle "
            "einfuegen - sie laufen von dort nach unten und "
            "nach rechts weiter und ueberschreiben, was dort "
            "steht. Rechts steht, "
            "was an den Rohwerten auffaellt: was der Variante "
            "fehlt, was ausserhalb seines Bereichs liegt und was "
            "nicht zueinander passt."))
        self.info_roh.pack(side="left", padx=(10, 0))
        self.info_tasten = Infozeichen(leiste, "Tastenkuerzel\n\n" + TASTEN,
                                       dezent=True)
        self.info_tasten.pack(side="left", padx=(4, 0))
        self.rohstand = tk.Label(leiste, text="", bg=Style.BG, fg=Style.MUTED,
                                 font=Style.font(9), anchor="w")
        self.rohstand.pack(side="left", padx=(14, 0))

        # Oben die berechneten Groessen, unten die Rohwerte - zwei
        # getrennte Tabellen, die Grenze dazwischen laesst sich ziehen.
        # Oben ist von Haus aus zugeklappt: dann gehoert das Fenster
        # den Rohwerten.
        self.knopf_berechnete = RoundedButton(
            leiste, text=BERECHNETE_EIN_TEXT, width=200, height=28,
            bg="#334155", command=self._berechnete_umschalten)
        self.knopf_berechnete.pack(side="left", padx=(8, 0),
                                   before=self.info_roh)
        ToolTip(self.knopf_berechnete,
                "Zeigt ueber den Rohwerten die berechneten Groessen -\n"
                "dieselbe Tabelle wie im Reiter \u201eErgebnisse\u201c. Wer\n"
                "unten einen Rohwert aendert, sieht oben dieselbe Probe:\n"
                "die Zeile ist unterlegt, was sich bewegt hat, steht rot.\n"
                "Die Grenze zwischen beiden laesst sich ziehen.")
        self.rohteilung = ttk.PanedWindow(seite, orient="vertical")
        self.rohteilung.pack(fill="both", expand=True)
        self.berechnet_rahmen = tk.Frame(self.rohteilung, bg=Style.BG)
        obenkopf = tk.Frame(self.berechnet_rahmen, bg=Style.BG)
        obenkopf.pack(fill="x", pady=(0, 2))
        tk.Label(obenkopf, text="Berechnete Groessen", bg=Style.BG,
                 fg=Style.TEXT, font=Style.font(9, "bold"),
                 anchor="w").pack(side="left")
        Infozeichen(obenkopf, erklaerung(
            "Je Groesse zwei Spalten: gebucht im LIMS und gerechnet "
            "(ber.). Rot: durch die Handeingabe bewegt - und die Probe, in "
            "der von Hand geaendert wurde. Unterlegt ist die Zeile, in der "
            "unten gerade getippt wird.")).pack(side="left", padx=(8, 0))
        RoundedButton(obenkopf, text="Blatt als CSV", width=140, height=24,
                      bg="#334155",
                      command=self._ergebnisblatt_speichern).pack(
            side="left", padx=(12, 0))
        self.berechnet_oben = eingaberaster.Eingaberaster(
            self.berechnet_rahmen, hoehe=8, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.berechnet_oben.pack(fill="both", expand=True, pady=(0, 6))
        rohrahmen = tk.Frame(self.rohteilung, bg=Style.BG)
        self.rohtabelle = eingaberaster.Eingaberaster(
            rohrahmen, hoehe=16, bei_aenderung=self._von_hand_geaendert,
            bei_klick=self._block_zeigen,
            bei_block=self._block_eingefuegt,
            bei_zeile=self._arbeitszeile_setzen,
            bei_fuellen=self.leere_fuellen,
            ist_leer=self.ist_leer,
            bei_nach_unten=self._nach_unten_eingefuegt,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.rohtabelle.pack(fill="both", expand=True)
        self.rohteilung.add(rohrahmen, weight=3)
        # Dieselbe Tabelle kann zweimal dastehen - klein im Reiter und
        # gross im eigenen Fenster. Beide zeigen denselben Stand und
        # nehmen dieselben Eingaben an; was hier steht, wird ueberall
        # nachgezogen.
        self.rohtabellen = [self.rohtabelle]

    def _ergebnis_reiter(self):
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Ergebnisse ")
        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Ergebnisblatt als CSV", width=200,
                      height=28, bg="#334155",
                      command=self._ergebnisblatt_speichern).pack(side="left")
        self._infoknopf(leiste, self._ergebnislegende_zeigen)
        self.info_ergebnis = Infozeichen(leiste, erklaerung(
            "Je Groesse zwei Spalten: was das LIMS gebucht hat "
            "und was das Pruefmodul aus denselben Formeln rechnet - "
            "zusammengehalten durch den Hintergrund, der von "
            "Groesse zu Groesse wechselt. Amber heisst, dass "
            "beides auseinandergeht; rechts steht, welche "
            "Groessen es sind. Rot heisst, dass der Wert von "
            "Hand bewegt wurde."))
        self.info_ergebnis.pack(side="left", padx=(10, 0))
        self.ergebnistabelle = eingaberaster.Eingaberaster(
            seite, hoehe=16, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.ergebnistabelle.pack(fill="both", expand=True)
        # Die berechneten Groessen koennen ein zweites Mal dastehen - ueber
        # den Rohwerten. Beide werden mit demselben Stand gefuellt.
        self.ergebnistabellen = [self.ergebnistabelle]

    def _pruef_reiter(self):
        """Das Arbeitsblatt: ein Wert je Zeile und ein Urteil dazu."""
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Pruefung ")
        # Welche Spalte welchen Parameter zeigt: steht im i, nicht ueber
        # der Tabelle. Das Label bleibt als Traeger des Textes.
        self.legende = tk.Label(seite, text="", bg=Style.BG, fg=Style.MUTED,
                                font=Style.font(8), anchor="w",
                                justify="left", wraplength=980)

        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Blatt als CSV", width=150, height=28,
                      bg="#334155", command=self._blatt_speichern).pack(
            side="left")
        # Aus: das Blatt ist der Nachweis ueber die ganze Serie. An:
        # der Arbeitsvorrat dessen, der die Befunde abarbeitet.
        self.v_nur_befunde = tk.BooleanVar(value=False)
        self.schalter_befunde = ttk.Checkbutton(
            leiste, variable=self.v_nur_befunde,
            text="nur Eintraege mit Bewertung",
            command=self._pruefung_zeigen)
        self.schalter_befunde.pack(side="left", padx=(14, 0))
        ToolTip(self.schalter_befunde,
                "Zeigt nur die Proben, zu denen etwas zu sagen ist.\n"
                "Gerechnet und geschrieben wird weiter ueber die ganze\n"
                "Serie, und das Blatt als CSV bleibt vollstaendig - es\n"
                "ist der Nachweis ueber sie und nicht ueber ihre\n"
                "Auffaelligkeiten.")
        RoundedButton(leiste, text="Bild", width=110, height=28,
                      bg="#334155", command=self._bild_zeigen).pack(
            side="left", padx=(8, 0))
        self._infoknopf(leiste, self._prueflegende_zeigen)
        self.info_pruefung = Infozeichen(leiste, PRUEF_ERKLAERUNG)
        self.info_pruefung.pack(side="left", padx=(10, 0))
        self.pruefstand = tk.Label(leiste, text="", bg=Style.BG,
                                   fg=Style.MUTED, font=Style.font(9),
                                   anchor="w")
        self.pruefstand.pack(side="left", padx=(14, 0))

        self.pruefungstabelle = eingaberaster.Eingaberaster(
            seite, hoehe=16, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.pruefungstabelle.pack(fill="both", expand=True)

    def _bericht_reiter(self):
        """Was zuletzt in das LIMS gegangen ist - eine Probe je Zeile."""
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Exportbericht ")
        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Bericht als CSV", width=170, height=28,
                      bg="#334155", command=self._bericht_speichern).pack(
            side="left")
        self.info_bericht = Infozeichen(leiste, erklaerung(
            "Der letzte Schreibweg in das LIMS, von der anderen "
            "Seite gesehen: eine Probe je Zeile und eine Spalte "
            "je Groesse, die sich bewegt hat - erst die "
            "Rohwerte, dann die daraus berechneten Groessen. In "
            "der Zelle steht, was vorher im LIMS stand und was "
            "jetzt dort steht. Der Bericht bleibt stehen, bis "
            "wieder geschrieben wird; als Datei - mit allen "
            "geschriebenen Stellen - liegt er neben "
            "der Sicherung im Ordner "
            f"„{trdfexport.ORDNER}“."))
        self.info_bericht.pack(side="left", padx=(10, 0))
        self.berichtstand = tk.Label(leiste, text=BERICHT_LEER, bg=Style.BG,
                                     fg=Style.MUTED, font=Style.font(9),
                                     anchor="w")
        self.berichtstand.pack(side="left", padx=(14, 0))
        self.berichtstabelle = eingaberaster.Eingaberaster(
            seite, hoehe=16, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.berichtstabelle.pack(fill="both", expand=True)

    # ------------------------------------------------------ Einfuegeliste
    def einfuegen_oeffnen(self):
        """Das Fenster fuer die Liste der Probenvorbereitung - eines."""
        vorhandenes = getattr(self, "einfuegefenster", None)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            vorhandenes.lift()
            vorhandenes.textfeld.focus_set()
            return vorhandenes
        self.einfuegefenster = Einfuegefenster(self)
        return self.einfuegefenster

    def einfuegetext(self) -> str:
        """Was in der Liste steht - aus dem Fenster, wenn es offen ist."""
        fenster = getattr(self, "einfuegefenster", None)
        if fenster is not None and fenster.winfo_exists():
            self._einfuegetext = fenster.textfeld.get("1.0", "end")
        return getattr(self, "_einfuegetext", "")

    # ------------------------------------- Berechnete Groessen ueber Rohwerten
    def berechnete_offen(self) -> bool:
        """Ob die berechneten Groessen ueber den Rohwerten stehen."""
        return self.berechnet_oben in self.ergebnistabellen

    def _berechnete_umschalten(self, merken=True):
        """Die berechneten Groessen ueber den Rohwerten auf- oder zuklappen."""
        if self.berechnete_offen():
            self.ergebnistabellen.remove(self.berechnet_oben)
            self.rohteilung.forget(self.berechnet_rahmen)
            self.knopf_berechnete.config(text=BERECHNETE_EIN_TEXT)
        else:
            self.rohteilung.insert(0, self.berechnet_rahmen, weight=2)
            self.ergebnistabellen.append(self.berechnet_oben)
            self.knopf_berechnete.config(text=BERECHNETE_AUS_TEXT)
            self._ergebnisse_zeigen()
            self._auswahl_stellen()
            self._teilung_setzen()
        if merken:
            konfig = self._einstellungen()
            konfig.set("trdf_berechnete", BERECHNETE_AN
                       if self.berechnete_offen() else BERECHNETE_AUS)
            konfig.speichern()

    def _teilung_setzen(self):
        """Oben gut ein Drittel, unten der Rest - ziehen laesst es sich."""
        try:
            self.rohteilung.update_idletasks()
            hoehe = self.rohteilung.winfo_height()
            if hoehe > 50:
                self.rohteilung.sashpos(0, int(hoehe * 0.38))
        except tk.TclError:
            pass

    def _arbeitszeile_setzen(self, probe: str):
        """In einer Rohwertzeile wird getippt - die anderen Tabellen gehen mit.

        Die Zeile wird ueberall unterlegt, und die berechneten Groessen
        und das Pruefblatt rollen zu ihr: wer unten einen Rohwert
        aendert, sieht oben dieselbe Probe.
        """
        self.arbeitszeile = str(probe)
        self._auswahl_stellen()
        self._mitgehen()

    # ------------------------------------------- Verdeckte Tabellen spaeter
    # Wer in den Rohwerten tippt, sieht die Reiter Ergebnisse und
    # Pruefung nicht. Sie bei jeder Eingabe neu zu fuellen kostete bei
    # dreihundert Proben den groessten Teil der Wartezeit; gefuellt wird
    # deshalb, was zu sehen ist, und der Rest, sobald sein Reiter
    # aufgeht. Gerechnet und gezaehlt wird trotzdem sofort - die
    # Statuszeile stimmt immer.

    def _im_blick(self, tabelle) -> bool:
        """Ob diese Tabelle gerade zu sehen ist.

        Steht die Seite selbst nicht auf dem Schirm (im Bauplan, beim
        Aufbau), gilt jede als sichtbar: dann wird wie bisher sofort
        gefuellt.
        """
        try:
            if not self.winfo_viewable():
                return True
            gewaehlt = str(self.reiter.select() or "")
        except tk.TclError:
            return True
        return not gewaehlt or str(tabelle).startswith(gewaehlt + ".")

    def _fuellen(self, tabelle, auftrag):
        """Fuellt eine Tabelle jetzt - oder, wenn sie verdeckt ist, spaeter."""
        if self._im_blick(tabelle):
            self._ausstehend.pop(tabelle, None)
            auftrag()
        else:
            self._ausstehend[tabelle] = auftrag

    def _nachziehen(self, alle=False):
        """Fuellt, was liegen geblieben ist und jetzt zu sehen ist."""
        nachgezogen = False
        for tabelle, auftrag in list(self._ausstehend.items()):
            if alle or self._im_blick(tabelle):
                del self._ausstehend[tabelle]
                auftrag()
                nachgezogen = True
        if nachgezogen:
            self._auswahl_stellen()
            self._mitgehen()

    def _mitgehen(self):
        """Die berechneten Tabellen zur Arbeitszeile rollen."""
        if not self.arbeitszeile:
            return
        for tabelle in list(self.ergebnistabellen) + [self.pruefungstabelle]:
            try:
                tabelle.sehen(self.arbeitszeile)
            except tk.TclError:
                pass

    def _bericht_merken(self, geaendert, serie: str, sicherung: str,
                        offen=()):
        """Haelt fest, was gerade geschrieben wurde, und zeigt es."""
        self.letzter_export = {
            "serie": serie, "zeitpunkt": dt.datetime.now(),
            "sicherung": sicherung,
            "aenderungen": list(geaendert), "offen": list(offen)}
        self._bericht_zeigen()

    def _bericht_zeigen(self):
        """Fuellt den Reiter aus dem gemerkten Export."""
        stand = self.letzter_export
        if not stand:
            self.berichtstabelle.fuellen(list(trdfexport.BERICHT_KOPF), [])
            self.berichtstand.config(text=BERICHT_LEER, fg=Style.MUTED)
            return
        # Auch ein Export, bei dem nichts angekommen ist, ist der letzte:
        # die leere Tabelle mit der Zeile darueber ist dann die Auskunft.
        spalten, zeilen = trdfexport.bericht(stand["aenderungen"],
                                             trdfpruefung.stellen_fuer)
        # Rot heisst hier dasselbe wie ueberall im Reiter: dieser Wert
        # ist von Hand bewegt worden. Der Rest ist seine Folge.
        marken = {(kennung, eine["kuerzel"]): "geaendert"
                  for eine in stand["aenderungen"]
                  for kennung in [str(eine.get("probe") or "")]
                  if eine.get("art") == trdfexport.ROHWERT}
        self.berichtstabelle.fuellen(spalten, zeilen, marken=marken,
                                     breiten=BREITEN, passend=spalten[2:])
        self._kopfhinweise(self.berichtstabelle, spalten)
        werte = len(stand["aenderungen"])
        satz = (f"{stand['serie']}  |  {stand['zeitpunkt']:%d.%m.%Y %H:%M}  "
                f"|  {len(zeilen)} Proben, {werte} Werte  |  Sicherung: "
                f"{stand['sicherung']}")
        if stand["offen"]:
            satz += (f"  |  {len(stand['offen'])} Werte stehen danach noch "
                     f"wie vorher da")
        self.berichtstand.config(
            text=satz, fg=Style.ERROR if stand["offen"] else Style.TEXT)

    def _bericht_verworfen(self, name: str):
        """Nach dem Zurueckspielen gilt der letzte Export nicht mehr."""
        self.letzter_export = None
        self._bericht_zeigen()
        self.berichtstand.config(
            text=f"Der letzte Export wurde aus {name} zurueckgespielt.",
            fg=Style.WARN)

    def _bericht_speichern(self):
        """Legt den Bericht als CSV ab und oeffnet ihn."""
        stand = self.letzter_export
        if not stand or not stand["aenderungen"]:
            self.berichtstand.config(text=BERICHT_LEER, fg=Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        pfad = trdfexport.bericht_schreiben(ordner, stand["serie"],
                                            stand["aenderungen"],
                                            stand["zeitpunkt"])
        if not pfad:
            self.berichtstand.config(
                text=f"Die Datei liess sich nicht schreiben. Steht der "
                     f"Ordner „{ordner}“ zur Verfuegung?", fg=Style.ERROR)
            return
        self.berichtstand.config(text=pfad, fg=Style.TEXT)
        trdfpruefung.oeffnen(pfad)

    # ------------------------------------------------------------- Legende
    #
    # Die Tabellen tragen die Kuerzel, mit denen das LIMS rechnet - unter
    # ihnen stehen die Groessen in den Formeln, und wer eine Formel
    # liest, sucht genau sie. Nur weiss niemand auswendig, dass „_TSM“
    # die Tiefenstufenmaechtigkeit ist. Der Knopf „Info“ sagt es, je
    # Reiter fuer dessen eigene Spalten - und laesst Platz fuer das, was
    # das Labor selbst dazu zu sagen hat.

    def _infoknopf(self, leiste, befehl):
        knopf = RoundedButton(leiste, text="Info", width=90, height=28,
                              bg="#3f4a5a", command=befehl)
        knopf.pack(side="left", padx=(8, 0))
        ToolTip(knopf, "Was die Spaltenueberschriften dieser Tabelle\n"
                       "bedeuten - Name, Einheit und Formelkuerzel.\n"
                       "Eine eigene Beschreibung laesst sich dort\n"
                       "eintragen und speichern. Dort steht auch, in\n"
                       "welcher Reihenfolge die Spalten kommen (Zeile\n"
                       "greifen und ziehen), welche links stehen\n"
                       "bleiben („Fest“), welche ueberhaupt dastehen\n"
                       "(„Zeigen“) und was oben in der Kopfzeile steht -\n"
                       "je Spalte einzeln oder fuer alle zugleich.")
        return knopf

    def _einstellungen(self):
        """Die Einstellungen - erst wenn sie gebraucht werden.

        Das Hauptfenster gibt seine mit; ohne sie (im Bauplan, und wenn
        die Seite einmal allein steht) wird eine eigene geoeffnet.
        """
        if self._konfig is None:
            self._konfig = config.Config(runtime_dir=self._ordner)
        return self._konfig

    def beschreibungen(self) -> dict:
        """Was das Labor selbst zu den Groessen notiert hat."""
        gespeichert = self._einstellungen().get("trdf_beschreibung")
        return dict(gespeichert or {})

    def spaltenordnung(self, blatt: str) -> tuple:
        """Reihenfolge und feste Spalten einer Tabelle - aus den Einstellungen.

        Ohne Eintrag gilt, womit eine Tabelle von Haus aus anfaengt:
        die Zeile, die Probe und - bei den Rohwerten - die Variante.
        Ohne sie sagt keine Zahl der Zeile etwas.
        """
        konfig = self._einstellungen()
        reihenfolge = (konfig.get("trdf_reihenfolge") or {}).get(blatt) or []
        fest = (konfig.get("trdf_fest") or {}).get(blatt)
        if fest is None:
            fest = trdflegende.STANDARD_FEST
        return trdflegende.mit_wiederholung(reihenfolge, fest)

    def kopfspalte(self) -> str:
        """Was in der Kopfzeile steht - das Kuerzel, der Name, die Einheit."""
        return str(self._einstellungen().get("trdf_kopfspalte")
                   or trdflegende.KOPFWAHL[0])

    def kopfspalten(self) -> dict:
        """Und was davon abweichend fuer einzelne Groessen gilt.

        Geschluesselt auf das Formelkuerzel wie die Beschreibung: eine
        Groesse heisst in den drei Tabellen verschieden, und wer sie
        einmal eingestellt hat, will das nicht dreimal tun.
        """
        return dict(self._einstellungen().get("trdf_kopfspalten") or {})

    def versteckt(self, blatt: str) -> list:
        """Welche Spalten dieser Tabelle ausgeblendet sind.

        Von Haus aus keine: wer eine Tabelle oeffnet, will erst einmal
        sehen, was es gibt.
        """
        gespeichert = (self._einstellungen().get("trdf_versteckt")
                       or {}).get(blatt)
        return list(gespeichert or [])

    def _geordnet(self, blatt: str, spalten, quellen=None,
                  roh=False) -> tuple:
        """Die Spalten einer Tabelle, wie der Pruefer sie sehen will.

        Zurueck kommen die Spalten, die die Tabelle zeigt, die, die
        links stehen bleiben, die Kopfzeile dazu - und alle Spalten,
        auch die ausgeblendeten. Die Legende braucht sie: aus einer
        Liste, in der eine ausgeblendete Spalte fehlt, liesse sie sich
        nicht wieder einblenden.
        """
        reihenfolge, fest = self.spaltenordnung(blatt)

        def schluessel(name):
            return trdflegende.schluessel(name, quellen)

        alle, gehalten = trdflegende.geordnet(spalten, schluessel,
                                              reihenfolge, fest)
        sortiert = trdflegende.sichtbar(alle, schluessel,
                                        self.versteckt(blatt), fest)
        koepfe = trdflegende.ueberschriften(
            alle, self.kopfspalte(), self.methoden, quellen,
            self.beschreibungen(), roh, self.kopfspalten())
        return sortiert, gehalten, koepfe, alle

    def _spalten_speichern(self, blatt: str, texte: dict,
                           ordnung=None) -> str:
        """Legt Beschreibungen und Spaltenordnung ab - "" wenn es klappte.

        Gespeichert wird nur, was auch dasteht: ein geleerter Text
        nimmt seinen Eintrag mit. Nichts davon geht in die Datenbank.
        """
        konfig = self._einstellungen()
        gespeichert = dict(konfig.get("trdf_beschreibung") or {})
        for schluessel, text in texte.items():
            if str(text or "").strip():
                gespeichert[schluessel] = str(text).strip()
            else:
                gespeichert.pop(schluessel, None)
        konfig.set("trdf_beschreibung", gespeichert)
        if ordnung:
            reihen = dict(konfig.get("trdf_reihenfolge") or {})
            reihen[blatt] = list(ordnung.get("reihenfolge") or [])
            konfig.set("trdf_reihenfolge", reihen)
            feste = dict(konfig.get("trdf_fest") or {})
            feste[blatt] = list(ordnung.get("fest") or [])
            konfig.set("trdf_fest", feste)
            verborgen = dict(konfig.get("trdf_versteckt") or {})
            verborgen[blatt] = list(ordnung.get("versteckt") or [])
            konfig.set("trdf_versteckt", verborgen)
            konfig.set("trdf_kopfspalte", str(ordnung.get("kopfspalte")
                                              or trdflegende.KOPFWAHL[0]))
            # Die Wahl je Groesse gilt ueber alle drei Tabellen: dieselbe
            # Groesse soll nicht in der einen ihren Namen und in der
            # anderen ihr Kuerzel tragen. Gespeichert wird, was in dieser
            # Legende zu sehen war - was sie nicht kannte, bleibt stehen.
            eigene = dict(konfig.get("trdf_kopfspalten") or {})
            for kuerzel in (ordnung.get("reihenfolge") or []):
                eigene.pop(str(kuerzel), None)
            for kuerzel, wert in (ordnung.get("kopfspalten") or {}).items():
                eigene[str(kuerzel)] = str(wert)
            konfig.set("trdf_kopfspalten", eigene)
        if not konfig.speichern():
            return konfig.meldung or "unbekannter Grund"
        # Sofort sichtbar: wer die Reihenfolge zurechtzieht, will sie
        # nicht erst beim naechsten Abruf sehen.
        self._ansichten_erneuern()
        return ""

    def _ansichten_erneuern(self):
        """Die Tabellen neu schreiben - nach einer neuen Spaltenordnung."""
        try:
            self._zeigen()
        except tk.TclError:
            pass

    def _legende_zeigen(self, titel: str, spalten, zeilen, quellen=None):
        reihenfolge, fest = self.spaltenordnung(titel)
        schluessel = {spalte: trdflegende.schluessel(spalte, quellen)
                      for spalte in (zeile[0] for zeile in zeilen)}
        fenster = trdflegende.Legendenfenster(
            self, titel, spalten, zeilen,
            speichern=lambda texte, ordnung, blatt=titel:
                self._spalten_speichern(blatt, texte, ordnung),
            schluessel=schluessel,
            ordnung={"reihenfolge": reihenfolge,
                     # Nur die, die es in dieser Tabelle auch gibt -
                     # sonst stuende in der Legende ein „ja“ neben
                     # einer Spalte, die hier gar nicht festgehalten
                     # werden kann.
                     "fest": [kuerzel for kuerzel in fest
                              if kuerzel in set(schluessel.values())],
                     "versteckt": [kuerzel
                                   for kuerzel in self.versteckt(titel)
                                   if kuerzel in set(schluessel.values())],
                     "kopfspalte": self.kopfspalte(),
                     "kopfspalten": {kuerzel: wert for kuerzel, wert
                                     in self.kopfspalten().items()
                                     if kuerzel in set(schluessel.values())}})
        return fenster

    def _rohlegende_zeigen(self):
        # Alle Spalten, auch die ausgeblendeten: aus einer Liste, in der
        # sie fehlen, liessen sie sich nicht wieder einblenden.
        spalten = self._rohspalten()[3]
        return self._legende_zeigen(
            BLATT_ROH, list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(spalten, self.methoden,
                                   self.beschreibungen()))

    def _ergebnislegende_zeigen(self):
        spalten = self._ergebnisspalten()[4]
        return self._legende_zeigen(
            BLATT_ERGEBNIS, list(trdflegende.SPALTEN_ERGEBNIS),
            trdflegende.ergebnislegende(spalten, self.methoden,
                                        self.beschreibungen()))

    def _prueflegende_zeigen(self):
        spalten = self._pruefspalten()[3]
        return self._legende_zeigen(
            BLATT_PRUEFUNG, list(trdflegende.SPALTEN_ERGEBNIS),
            trdflegende.pruefungslegende(spalten, trdfpruefung.QUELLEN,
                                         self.methoden,
                                         self.beschreibungen()),
            quellen=trdfpruefung.QUELLEN)

    # ------------------------------------------------------------- Abrufen
    def _melden(self, text, farbe=Style.MUTED):
        self.stand.config(text=text, fg=farbe)

    def serienliste_laden(self, danach=None):
        """Die TRDF-Serien aus dem Fahrplan - im Hintergrund.

        Nur fuer die Liste im Serienfeld: welche Methoden eine Serie
        fuehrt, fragt erst "Abfragen". Ohne Zugang (beim Bauen der Seite
        ist noch niemand angemeldet) bleibt die Liste leer und das Feld
        nimmt eine eingetippte Serie.
        """
        zugang = self._zugang_holen()
        if zugang is None:
            return

        def arbeit():
            methoden = lims_db.trdf_methoden(zugang)
            return lims_db.trdf_serien(zugang, [um for um, _ in methoden])

        def fertig(serien):
            self.serienliste = list(serien)
            self.feld_serie["values"] = self.serienliste
            self._melden(f"{len(self.serienliste)} TRDF-Serien im Fahrplan "
                         f"- Serie waehlen und \u201eAbfragen\u201c.")
            if danach is not None:
                danach()

        self._im_hintergrund(arbeit, fertig, self._schiefgegangen)

    def _schiefgegangen(self, fehler):
        self._melden(lims_db.fehlertext(fehler), Style.ERROR)

    def _schreiben_schiefgegangen(self, fehler):
        """Beim Schreiben reicht die Statuszeile nicht.

        Wer auf "Schreiben" gedrueckt hat, wartet auf eine Antwort und
        darf nicht raten muessen, ob etwas angekommen ist - eine
        gescheiterte Abfrage ist eine Unbequemlichkeit, ein gescheiterter
        Schreibweg eine offene Frage.
        """
        satz = lims_db.fehlertext(fehler)
        self._melden(satz, Style.ERROR)
        messagebox.showerror("Es wurde nichts geschrieben", satz, parent=self)

    # ------------------------------------------------------ Serie und Methode
    def _gemerkt(self, schluessel: str) -> str:
        """Was zuletzt in einem Feld stand - aus den Einstellungen."""
        try:
            return str(self._einstellungen().get(schluessel) or "")
        except Exception:                          # noqa: BLE001
            return ""

    def _merken(self):
        """Die Serie fuer den naechsten Start ablegen.

        Die Methode nicht: welche gilt, sagt beim naechsten Mal wieder
        die Abfrage - eine gemerkte koennte zu einer anderen Serie
        gehoeren.
        """
        konfig = self._einstellungen()
        konfig.set("serie", self.v_serie.get().strip())
        konfig.speichern()

    def _methoden_leeren(self, text=METHODE_OFFEN):
        """Die Methodenliste gilt nicht mehr - etwa nach einer neuen Serie."""
        self.methodenwahl = []
        self.abgefragte_serie = ""
        self.feld_methode.config(values=[], state="disabled")
        self.v_methode.set(text)

    def _serie_gewechselt(self):
        """Eine Serie aus der Liste - die Methoden werden gleich gefragt."""
        self._abfragen()

    def _serie_getippt(self):
        """Steht eine andere Serie im Feld, ist die Methodenliste veraltet."""
        if not hasattr(self, "feld_methode"):
            return
        if self.abgefragte_serie and \
                self.v_serie.get().strip() != self.abgefragte_serie:
            self._methoden_leeren()

    @staticmethod
    def trdf_methoden_der_serie(methoden) -> list:
        """Aus den Methoden einer Serie die, deren Kuerzel TRDF traegt.

        Die ausgeschlossenen bleiben draussen: TRDF3.1 traegt dieselben
        Groessen unter derselben Bezeichnung wie TRDF3.2, und welche der
        beiden Zahlen dann gilt, entschiede die Reihenfolge und nicht
        das Labor.
        """
        return [(um, str(k or "").strip()) for um, k in methoden or ()
                if lims_db.TRDF_MARKE in str(k or "").upper()
                and not lims_db.ist_ausgeschlossen(k)]

    def _abfragen(self):
        """Welche TRDF-Methoden fuehrt die Serie? - im Hintergrund."""
        serie = self.v_serie.get().strip()
        zugang = self._zugang_holen()
        if not serie or zugang is None:
            self._melden("Erst anmelden und eine Serie waehlen.", Style.WARN)
            return
        self._methoden_leeren("wird abgefragt ...")
        self._melden(f"Die Untersuchungsmethoden der Serie {serie} werden "
                     f"abgefragt ...")
        self.update_idletasks()

        def arbeit():
            return self.trdf_methoden_der_serie(
                lims_db.methoden_fuer_serie(zugang, serie))

        def fertig(passend):
            self._methoden_zeigen(serie, passend)

        self._im_hintergrund(arbeit, fertig, self._abfrage_schiefgegangen)

    def _abfrage_schiefgegangen(self, fehler):
        self._methoden_leeren()
        self._schiefgegangen(fehler)

    def _methoden_zeigen(self, serie: str, passend):
        """Die Methodenliste der Serie ins Feld - und bei einer gleich holen."""
        if self.v_serie.get().strip() != serie:
            # Inzwischen steht eine andere Serie im Feld - die Antwort
            # gehoert nicht mehr zu ihr.
            self._methoden_leeren()
            return
        if not passend:
            self._methoden_leeren("keine TRDF-Methode")
            self._melden(f"Die Serie {serie} fuehrt keine Untersuchungs"
                         f"methode mit TRDF im Kuerzel.", Style.WARN)
            return
        self.abgefragte_serie = serie
        self.methodenwahl = methodentexte(passend)
        texte = [text for _um, _k, text in self.methodenwahl]
        self.feld_methode.config(values=texte, state="readonly")
        if len(texte) == 1:
            self.v_methode.set(texte[0])
            self._methodenfeld_freigeben()
            self._abrufen()
            return
        self.v_methode.set("")
        namen = ", ".join(texte)
        self._melden(f"Die Serie {serie} fuehrt {len(texte)} TRDF-Methoden "
                     f"({namen}) - bitte eine waehlen.", Style.WARN)

    def _methode_gewaehlt(self):
        self._methodenfeld_freigeben()
        self._abrufen()

    def _methodenfeld_freigeben(self):
        """Fokus und Markierung weg vom Methodenfeld.

        Im clam-Thema zeichnet ein schreibgeschuetztes Auswahlfeld mit
        Fokus seinen Text nicht sichtbar - die gewaehlte Methode saehe
        aus wie keine. Ohne Fokus steht sie da.
        """
        try:
            self.feld_methode.selection_clear()
            self.focus_set()
        except tk.TclError:
            pass

    def gewaehlte_methode(self) -> tuple:
        """(UM_ID, Kuerzel) der gewaehlten Methode - (None, "") ohne.

        Kein stiller Ersatz: eine Methode, die nicht in der Liste der
        abgefragten Serie steht, ist keine Wahl.
        """
        gewaehlt = self.v_methode.get().strip()
        for um_id, name, text in self.methodenwahl:
            if text == gewaehlt:
                return um_id, name
        return None, ""

    def _abrufen(self):
        """Holt alles, was zu Serie und gewaehlter Methode gehoert."""
        serie = self.v_serie.get().strip()
        zugang = self._zugang_holen()
        if not serie or zugang is None:
            self._melden("Erst anmelden und eine Serie waehlen.", Style.WARN)
            return
        if serie != self.abgefragte_serie:
            # Die Methodenliste gehoert zu einer anderen Serie - erst
            # fragen, sonst kaeme die Serie unter einer Methode, die sie
            # vielleicht gar nicht fuehrt.
            self._abfragen()
            return
        um_id, kuerzel = self.gewaehlte_methode()
        if um_id is None:
            self._melden("Erst eine Untersuchungsmethode waehlen.", Style.WARN)
            return
        self._melden(f"Serie {serie} - {kuerzel} wird geholt ...")
        self.update_idletasks()

        def arbeit():
            ergebnisse = lims_db.trdf_ergebnisse(zugang, serie, um_id)
            # Der Aufschluss zuerst: danach steht fest, welchen Proben
            # er fehlt, und nur nach denen wird nachgefragt. Steht er
            # an jeder - der Regelfall -, entfaellt die Abfrage ganz.
            aufschluss = lims_db.trdf_aufschluss(zugang, serie)
            return {
                "um_id": um_id, "kuerzel": kuerzel,
                "methoden": lims_db.trdf_pruefmethoden(zugang, serie, um_id),
                "rohwerte": lims_db.trdf_rohwertparameter(zugang, um_id),
                "ergebnisse": ergebnisse,
                "anhang": _mit_nachtrag(
                    zugang, um_id, ergebnisse,
                    lims_db.trdf_rohwerte_anhang(zugang, serie, um_id)),
                "wgh": lims_db.trdf_wiederfindung(zugang, serie),
                "aufschluss": aufschluss,
                **_nachtragsteil(self._nachtrag_holen(
                    zugang, _ohne_aufschluss(ergebnisse, aufschluss)))}

        def fertig(geholt):
            self._uebernehmen(geholt)
            self._merken()

        self._im_hintergrund(arbeit, fertig, self._schiefgegangen)

    def _nachtrag_holen(self, zugang, prob_ids) -> tuple:
        """Cges und CO3 ueber alle Anlagen dieser Proben.

        `prob_ids` sind die Proben, denen der Aufschluss *fehlt* - nicht
        alle. Steht er an jeder Probe der Serie, ist die Liste leer, und
        der Abruf kostet keine Abfrage.

        Zurueck kommen (Liste, Grund). Gescheitert wird hier und nicht
        am Abruf: der Aufschluss ist eine Beigabe, die Serie ist die
        Arbeit. Gesagt wird es aber - eine Spalte, die leer bleibt,
        sieht sonst aus wie eine ohne gebuchten Wert.
        """
        if not prob_ids:
            return [], ""
        try:
            return lims_db.trdf_aufschluss_nachtrag(zugang, prob_ids), ""
        except Exception as fehler:               # noqa: BLE001
            return [], (f"Cges/CO3 nicht nachgefragt: "
                        f"{lims_db.fehlertext(fehler)}")

    def _uebernehmen(self, geholt):
        self._leeren()
        self.um_id, self.um_kuerzel = geholt["um_id"], geholt["kuerzel"]
        self.methoden = geholt["methoden"]
        self.formeln = {m["formelkuerzel"]: m["formel"] for m in self.methoden
                        if m["formelkuerzel"]
                        and str(m["formel"] or "").strip()}
        self.folge = trdf.reihenfolge(self.formeln)
        self.rohliste = [m["formelkuerzel"] for m in self.methoden
                         if m["formelkuerzel"] and m["formelkuerzel"]
                         not in self.formeln]
        # Ein Rohwert traegt zwei Kuerzel: ein kurzes am Parameter (und
        # damit am Teilprobenanhang und in der Vorbereitungsliste) und
        # das, mit dem die Formeln rechnen. Ohne die Bruecke gehoert
        # keiner der beiden Werte zu einer Groesse.
        self.rohkuerzel = trdf.zuordnen(geholt["rohwerte"], self.methoden,
                                        self.rohliste)
        self.rohnamen = {eintrag["name"]: self._formelkuerzel(
                             eintrag["formelkuerzel"])
                         for eintrag in geholt["rohwerte"]
                         if eintrag["name"] and eintrag["formelkuerzel"]}
        self._namen_merken(geholt["rohwerte"])
        nach_pm = {(m["pm_id"], m["pm_ver"]): m["formelkuerzel"]
                   for m in self.methoden}
        gesehen = {}
        for zeile in geholt["ergebnisse"]:
            probe = _kennung(zeile)
            kuerzel = nach_pm.get((zeile["pm_id"], zeile["pm_ver"]))
            if kuerzel is None:
                continue
            gesehen.setdefault(probe, zeile["lnr"])
            self.wiederholungen.setdefault(probe, (
                trdf.probenschluessel(zeile["probe_nr"]),
                trdf.wiederholung(zeile.get("wdh_um")),
                trdf.wiederholung(zeile.get("wdh_me"))))
            eimer = self.gebucht if self.formeln.get(kuerzel) else self.limsroh
            eimer.setdefault(probe, {})[kuerzel] = zeile["mw_roh"]
            # Die Zeile selbst wird aufgehoben: ohne ihren vollen
            # Schluessel liesse sich eine Korrektur weder sichern noch
            # zurueckschreiben.
            self.zeilen[(probe, kuerzel)] = zeile
        self._wgh_zuordnen(geholt)
        self._anhang_zuordnen(geholt)
        self.proben = sorted(((lnr, probe) for probe, lnr in gesehen.items()),
                             key=lambda p: (p[0] is None, p[0], p[1]))
        satz = (f"Serie {self.v_serie.get()} - {self.um_kuerzel}, "
                f"{len(self.proben)} Proben, {len(self.formeln)} berechnete "
                f"Groessen, {len(self.rohliste)} Rohwerte")
        ohne = [eintrag["formelkuerzel"] for eintrag in geholt["rohwerte"]
                if eintrag["formelkuerzel"]
                and eintrag["formelkuerzel"] not in self.rohkuerzel]
        if ohne:
            satz += ("  |  ohne Zuordnung zur Formel: " + ", ".join(ohne))
        if geholt.get("nachtragsfehler"):
            satz += f"  |  {geholt['nachtragsfehler']}"
        if self.aufschlussherkunft:
            satz += (f"  |  {len(self.aufschlussherkunft)} x Cges/CO3 aus "
                     f"einer anderen Anlage derselben Probennummer "
                     f"nachgetragen")
        self._melden(satz, Style.WARN if ohne else Style.TEXT)
        self.auskunft.config(
            text=f"{self.um_kuerzel}  |  Probenart "
                 f"{self._probenart_der_zeilen(geholt) or 'unbekannt'}")
        self._legende_stellen()
        self._quelle_zeigen()
        self._zeigen()

    def _probenart_der_zeilen(self, geholt) -> str:
        """Die Probenart aus den gebuchten Zeilen - PART_ID des LIMS.

        Nicht aus dem Seriennamen: der ist die Hausschreibweise, und
        bei einzelnen Proben gibt es keinen. Stehen mehrere darin,
        werden sie genannt - eine davon zu waehlen waere geraten.

        Ohne PART_ID bleibt der Name der Serie als Notnagel: eine
        Auskunft aus dem Namen ist besser als keine.
        """
        arten = []
        for zeile in geholt.get("ergebnisse") or ():
            name = PROBENART_ZU_ID.get(zeile.get("part_id"))
            if name and name not in arten:
                arten.append(name)
        if arten:
            return " und ".join(arten)
        return probenart(self.v_serie.get())

    def _formelkuerzel(self, kurz):
        """Das Kuerzel, mit dem die Formeln rechnen - zu einem kurzen."""
        return self.rohkuerzel.get(str(kurz or "").strip(), kurz)

    def _namen_merken(self, rohwerte):
        """Wie die Groessen im LIMS heissen - fuer die Legende.

        Gerechnet wird mit den Formelkuerzeln, im Pruefplan des Labors
        stehen die Parameternamen. Wer beides nebeneinander sieht, muss
        nicht raten, welche Spalte gemeint ist.
        """
        for eintrag in rohwerte:
            if eintrag["formelkuerzel"]:
                self.parameternamen.setdefault(
                    self._formelkuerzel(eintrag["formelkuerzel"]),
                    eintrag["name"])
        for methode in self.methoden:
            name = methode.get("parameter") or methode.get("name")
            if methode["formelkuerzel"] and name:
                self.parameternamen[methode["formelkuerzel"]] = name

    def _anhang_zuordnen(self, geholt):
        """Die Rohwerte am Teilprobenanhang - die zweite Stelle im LIMS.

        Aus ihr rechnen die Formeln des LIMS. Wer nur die Ergebniszeile
        korrigiert, aendert am Rechenweg nichts - deshalb wird sie hier
        mitgelesen und beim Zurueckschreiben mit angefasst.

        Zugeordnet wird ueber die **Probennummer** und nicht ueber die
        PROB_ID. Dieselbe Probe steht im LIMS unter mehreren Anlagen -
        einmal je Untersuchungsmethode -, und der Anhang haengt dann an
        einer anderen als die Ergebniszeile. Vorher fiel er dabei still
        heraus: die Rohwerte standen im LIMS, im Reiter stand nichts,
        und keine Meldung sagte warum.

        Ist es aber die PROB_ID einer Zeile dieser Serie, gilt sie: eine
        Wiederholung (UM/ME) traegt dieselbe Probennummer wie die
        Erstmessung, und ihr Anhang gehoert zu ihr und nicht zu jener.
        Was nur ueber die Nummer kommt, gehoert zur Erstmessung.
        """
        nummern = _kennungen(geholt["ergebnisse"])
        bekannt = set(nummern.values())
        for zeile in geholt.get("anhang", ()):
            probe = (nummern.get(zeile.get("prob_id"))
                     or trdf.probenschluessel(zeile.get("probe_nr")))
            kuerzel = self._formelkuerzel(zeile["formelkuerzel"])
            # Nur zu Proben, die auch in der Tabelle stehen: eine
            # Nummer, die der Abruf nicht gebracht hat, gehoert nicht
            # in diese Serie.
            if probe and kuerzel and probe in bekannt:
                self.anhang[(probe, kuerzel)] = zeile

    def _wgh_zuordnen(self, geholt):
        """Wiederfindungsgrad und Aufschluss haengen an der PROB_ID."""
        nummern = _kennungen(geholt["ergebnisse"])
        for prob_id, wert in geholt["wgh"].items():
            probe = nummern.get(prob_id)
            if probe:
                self.wgh[probe] = wert
        for eintrag in geholt["aufschluss"]:
            probe = nummern.get(eintrag["prob_id"])
            name = trdf.ATNULL_PARAMETER.get(eintrag["para_id"])
            if probe and name:
                self.aufschluss.setdefault(probe, {})[name] = eintrag["mw"]
        self._aufschluss_nachtragen(geholt, set(nummern.values()))

    def _aufschluss_nachtragen(self, geholt, eigene):
        """Cges und CO3, die an einer anderen PROB_ID derselben Probe stehen.

        Dieselbe Probe steht im LIMS mehrfach - dieselbe PROBE_NR unter
        einer anderen PROB_ID, oft in einer anderen Serie -, und der
        Aufschluss ist nur an einer von ihnen gebucht. Die Spalte blieb
        dann leer, obwohl das Labor die Zahl hat, und die Pruefungen,
        die auf dem Kohlenstoff stehen, kamen zu keinem Urteil.

        Nachgetragen wird nur, wo an der eigenen PROB_ID nichts steht.
        Ein vorhandener Wert wird nie ersetzt: die Zahl zweier
        verschiedener Anlagen derselben Nummer ist nicht dieselbe Zahl,
        und welche gilt, entscheidet nicht die Reihenfolge einer
        Abfrage.

        Ein Nachtrag gilt fuer jede Zeile dieser Nummer - auch fuer die
        Wiederholungen (UM/ME): der Aufschluss gehoert zur Probe und
        nicht zur Messung.
        """
        je_nummer = {}
        for probe in eigene:
            nummer = self.wiederholungen.get(probe, (probe,))[0]
            je_nummer.setdefault(nummer, []).append(probe)
        for eintrag in geholt.get("aufschlussnachtrag") or []:
            nummer = trdf.probenschluessel(eintrag.get("probe_nr"))
            name = trdf.ATNULL_PARAMETER.get(eintrag.get("para_id"))
            if not name:
                continue
            for probe in sorted(je_nummer.get(nummer, ())):
                if str(self.aufschluss.get(probe, {}).get(name)
                       or "").strip():
                    continue
                if (probe, name) in self.aufschlussherkunft:
                    continue    # die erste Zeile gilt - die hoechste PROB_ID
                self.aufschluss.setdefault(probe, {})[name] = eintrag["mw"]
                serie = str(eintrag.get("serie") or "").strip()
                self.aufschlussherkunft[(probe, name)] = NACHGETRAGEN.format(
                    prob_id=eintrag.get("prob_id"),
                    woher=f", Serie {serie}" if serie else "")

    def aufschlusshinweis(self, probe: str, spalte: str):
        """Woher ein nachgetragener Aufschlusswert kommt - sonst None."""
        return self.aufschlussherkunft.get((probe, spalte))

    def ergebnishinweis(self, probe: str, spalte: str):
        """Was ueber einer Zelle der berechneten Groessen steht - sonst None.

        Steht eine Groesse rot, weil eine Handeingabe sie bewegt hat,
        sagt der Hinweis, was vorher dastand und wohin es ging - ohne
        dass jemand die Eingabe zuruecknehmen muss, um es zu sehen.
        Sonst, wo es einen gibt, der Hinweis zum Aufschluss.
        """
        spalte = str(spalte)
        for anhaengsel in trdflegende.ANHAENGSEL:
            if not spalte.endswith(anhaengsel):
                continue
            kuerzel = spalte[:-len(anhaengsel)]
            if kuerzel not in self.formeln or \
                    kuerzel not in self.bewegt(probe):
                return None
            stellen = trdfpruefung.stellen_fuer(kuerzel, STELLEN)
            alt = self.gerechnet_ohne_hand(probe).get(kuerzel)
            neu = self.gerechnet(probe).get(kuerzel)
            gebucht = self.gebucht.get(probe, {}).get(kuerzel)
            return aenderungstext(
                zahltext(alt, stellen) or trdf.MARKE,
                zahltext(neu, stellen) or trdf.MARKE,
                _differenz(alt, neu, stellen),
                trdf.MARKE if trdf.leer(gebucht)
                else zahltext(trdf.zahl(gebucht), stellen))
        return self.aufschlusshinweis(probe, spalte)

    def rohhinweis(self, probe: str, spalte: str):
        """Ueber einem von Hand geaenderten Rohwert: der alte Wert - sonst None."""
        spalte = str(spalte)
        if (probe, spalte) not in self.vonhand:
            return None
        alt = self.rohwert_ohne_hand(probe, spalte)
        neu = self.vonhand[(probe, spalte)]
        return aenderungstext(rohtext(spalte, alt), rohtext(spalte, neu),
                              _differenz(trdf.zahl(alt), trdf.zahl(neu)),
                              rohtext(spalte, self.limsroh.get(probe, {})
                                      .get(spalte)))

    # -------------------------------------------------------- Einfuegetext
    def _text_leeren(self):
        self._einfuegetext = ""
        fenster = getattr(self, "einfuegefenster", None)
        if fenster is not None and fenster.winfo_exists():
            fenster.textfeld.delete("1.0", "end")
        self.eingefuegt = {}
        self._quelle_bestimmen()
        self._rechnung_vergessen()
        self._zeigen()
        for probe in list(self.bloecke):
            self._block_auffrischen(probe)
        # Nach dem Neuzeichnen: das schreibt sonst seine eigene Zeile
        # darueber.
        self._melden("Die eingefuegte UM ist geleert - gerechnet wird mit "
                     "den Rohwerten aus dem LIMS.", Style.TEXT)

    def _text_uebernehmen(self) -> bool:
        """Die eingefuegte Liste lesen - zurueck kommt, ob es geklappt hat."""
        inhalt = self.einfuegetext()
        if not inhalt.strip():
            self._melden("Das Einfuegefeld ist leer.", Style.WARN)
            return False
        try:
            gelesen = trdf.text_lesen(inhalt)
        except trdf.Einfuegefehler as fehler:
            self._melden(str(fehler), Style.ERROR)
            return False
        unbekannt = [name for name in gelesen["spalten"]
                     if name not in self.rohnamen]
        self.eingefuegt = {}
        for zeile in gelesen["zeilen"]:
            # Wiederholungen (UM/ME) treffen ihre eigene Zeile - unter
            # derselben Kennung wie im LIMS.
            self.eingefuegt[trdf.probenkennung(
                    zeile["probe"], zeile["wdh_um"], zeile["wdh_me"])] = {
                self.rohnamen[name]: wert
                for name, wert in zeile["werte"].items()
                if name in self.rohnamen}
        self._quelle_bestimmen()
        vorgemerkt = self._fehlende_vormerken()
        satz = (f"{len(self.eingefuegt)} Proben eingefuegt "
                f"(Serie {gelesen['serie']}, {gelesen['methode']}) - "
                f"gerechnet wird mit dieser Liste")
        if vorgemerkt:
            satz += (f"  |  {vorgemerkt} Werte, die im LIMS noch fehlen, "
                     f"zum Schreiben vorgemerkt")
        farbe = Style.TEXT
        if gelesen["serie"] and gelesen["serie"] != self.v_serie.get().strip():
            satz += f"  |  Achtung: abgerufen ist {self.v_serie.get()}"
            farbe = Style.WARN
        if unbekannt:
            satz += ("  |  ohne Zuordnung: " + ", ".join(unbekannt))
            farbe = Style.WARN
        self._rechnung_vergessen()
        self._zeigen()
        for probe in list(self.bloecke):
            self._block_auffrischen(probe)
        # Erst jetzt: das Neuzeichnen schreibt sonst "x von y Werten
        # stimmen" darueber, und die Auskunft ueber die Liste waere weg.
        self._melden(satz, farbe)
        return True

    def _fehlende_vormerken(self) -> int:
        """Was die Liste bringt und im LIMS noch fehlt, wird geschrieben.

        Steht ein Rohwert im LIMS noch gar nicht, ist die Liste die
        einzige Quelle - er wird vorgemerkt wie eine Handeingabe: rot,
        aenderbar und ueber \u201eExport\u201c schickbar.
        Steht dort schon etwas, bleibt die Liste ein Vergleich (amber):
        ein gebuchter Wert wird nicht still durch einen eingefuegten
        ersetzt. Was schon von Hand dasteht, sticht.
        """
        eigene = {probe for _lnr, probe in self.proben}
        vorgemerkt = 0
        for probe, werte in self.eingefuegt.items():
            if probe not in eigene:
                continue
            for kuerzel, wert in werte.items():
                if kuerzel not in self.rohliste or \
                        not str(wert or "").strip() or \
                        (probe, kuerzel) in self.vonhand or \
                        str(self.limsroh.get(probe, {}).get(kuerzel)
                            or "").strip():
                    continue
                self.vonhand[(probe, kuerzel)] = str(wert).strip()
                vorgemerkt += 1
        return vorgemerkt

    # ----------------------------------------------------------- Die Quelle
    def _quelle_bestimmen(self):
        """Welche Quelle gilt - von selbst, nach dem, was eingefuegt ist.

        Ist eine UM eingefuegt und uebernommen, wird mit ihr gerechnet;
        sonst mit den Rohwerten des LIMS.
        """
        self.quelle = QUELLE_TEXT if self.eingefuegt else QUELLE_LIMS
        self._quelle_zeigen()

    def _quelle_zeigen(self):
        """Sagt, woher die Rohwerte kommen - oben und im Einfuegefenster."""
        if self.quelle == QUELLE_TEXT:
            text = (f"Rohwerte aus: eingefuegter UM "
                    f"({len(self.eingefuegt)} Proben)")
        else:
            text = "Rohwerte aus: LIMS"
        self.quellanzeige.config(
            text=text, fg=Style.ACCENT if self.quelle == QUELLE_TEXT
            else Style.MUTED)
        self.quellhinweis = (
            "In der Probenvorbereitung \u201eaktueller Block\u201c -> "
            "kopieren, hier mit Strg+V einfuegen, dann \u201eUebernehmen\u201c "
            "- danach wird mit dieser Liste gerechnet. \u201eLeeren\u201c "
            "schaltet zurueck auf die Rohwerte aus dem LIMS.")
        fenster = getattr(self, "einfuegefenster", None)
        if fenster is not None and fenster.winfo_exists():
            fenster.hinweis.config(text=self.quellhinweis)

    def _quellstand(self) -> str:
        """Wie viele Werte die Quelle je Probe liefert."""
        if not self.proben:
            return f"Rohdaten aus: {self.quelle}"
        gefunden = sum(
            1 for _, probe in self.proben for kuerzel in self.rohliste
            if not trdf.leer(self.aus_der_quelle(probe, kuerzel)))
        moeglich = len(self.proben) * len(self.rohliste)
        return (f"Rohdaten aus: {self.quelle}  |  {gefunden} von {moeglich} "
                f"Zellen belegt")

    # ------------------------------------------------------------ Rechnen
    def von_hand_bewegt(self, probe: str) -> bool:
        """Ob in dieser Probe ein Rohwert von Hand steht."""
        return any(welche == probe for (welche, _k) in self.vonhand)

    def _von_hand_geaendert(self, zeile, spalte, wert):
        self.vonhand[(zeile, spalte)] = wert
        if spalte == trdfrohpruefung.VARIANTE:
            self._variante_wirkt(zeile, wert)
        self._rechnung_vergessen([zeile])
        # Die Rohwerttabelle wird nicht neu gebaut - sonst faellt das
        # offene Eingabefeld heraus, und der naechste Tabulator ginge
        # ins Leere. Gefaerbt wird nur die eine Zelle.
        for tabelle in self.rohtabellen:
            tabelle.setzen(zeile, spalte, rohtext(spalte, wert))
            tabelle.marke_setzen(zeile, spalte, "geaendert")
            tabelle.marke_setzen(zeile, "Probe", "geaendert")
        self._befund_nachtragen(zeile)
        self._zeigen(nur_ergebnisse=True)
        self._block_auffrischen(zeile)
        self.arbeitszeile = str(zeile)
        self._auswahl_stellen()
        self._mitgehen()

    def _befund_nachtragen(self, probe: str):
        """Die Bewertung einer Zeile neu setzen, ohne die Tabelle zu bauen.

        Die Rohwerttabelle wird nach einer Handeingabe nicht neu
        geschrieben - sonst faellt das offene Eingabefeld heraus. Die
        Bewertung stand darum bis zum naechsten Neuaufbau noch auf dem
        alten Stand, und gerade sie ist die Antwort auf das, was eben
        getippt wurde.
        """
        saetze = self.rohbefund(probe)
        text = trdfrohpruefung.bewertungstext(saetze)
        for tabelle in self.rohtabellen:
            if tabelle.setzen(probe, BEWERTUNGSSPALTE, text):
                tabelle.marke_setzen(probe, BEWERTUNGSSPALTE,
                                     "abweichung" if saetze else None)

    def _variante_wirkt(self, probe: str, eingabe):
        """Die neue Variante raeumt die Rohwerte auf, die sie nicht braucht.

        So haelt es die Eingabemaske des LIMS auch: was eine Variante
        nicht braucht, bekommt ein x - dann steht in der Zeile, dass
        dort nichts stehen soll, und nicht bloss nichts. Vorhandene
        Werte werden dabei ueberschrieben; „0“ raeumt die Zeile ganz
        leer, ein eingegebenes x belegt sie ganz mit x.

        Nur beim Tippen in die Zelle - ein eingefuegter Block bringt
        seine Werte selbst mit, und die sollen stehen bleiben.
        """
        neu = trdfrohpruefung.nach_variante(self.rohsatz(probe), eingabe)
        for kuerzel, wert in neu.items():
            self.vonhand[(probe, kuerzel)] = wert
            for tabelle in self.rohtabellen:
                if tabelle.setzen(probe, kuerzel, rohtext(kuerzel, wert)):
                    tabelle.marke_setzen(probe, kuerzel, "geaendert")
                    tabelle.marke_setzen(probe, "Probe", "geaendert")
        if neu:
            self._rohmelden(
                f"Variante {str(eingabe).strip()}: {len(neu)} Rohwerte "
                f"angepasst", Style.TEXT)
        return neu

    def ist_leer(self, probe: str, kuerzel: str) -> bool:
        """Steht hier wirklich nichts - weder Zahl noch x?

        Die Tabelle zeigt eine leere Zelle als x; fuer das Fuellen und
        das Kopieren nach unten zaehlt aber der Unterschied: ein x heisst
        "hier soll nichts stehen" (so setzt es die Variante), leer heisst
        "hier steht noch nichts".
        """
        return not str(self.rohwert(probe, kuerzel) or "").strip()

    def leere_fuellen(self, probe=None, spalte=None) -> list:
        """Strg+E / Strg+Shift+E: leere Rohwertzellen bekommen ein x.

        Mit `probe` die Zeile dieser Probe, mit `spalte` die ganze
        Spalte. Leer heisst: es steht wirklich nichts da (`ist_leer`).
        Ein x heisst im LIMS "hier soll nichts stehen", leer heisst
        "hier steht noch nichts"; die Taste macht aus dem einen das
        andere, so wie es die Eingabemaske des LIMS beim Setzen der
        Variante tut. Zahlen bleiben unberuehrt.
        """
        if spalte is not None:
            if spalte not in self.rohliste:
                return []
            zellen = [(name, spalte)
                      for _lnr, name in self.sichtbare_proben()]
            wo = f"Spalte {spalte}"
        else:
            zellen = [(probe, kuerzel) for kuerzel in self.rohliste]
            wo = str(probe)
        gesetzt = [(name, kuerzel, trdf.MARKE) for name, kuerzel in zellen
                   if self.ist_leer(name, kuerzel)]
        if not gesetzt:
            self._rohmelden(f"{wo}: keine leere Zelle", Style.TEXT)
            return []
        self._block_eingefuegt(gesetzt)
        self._rohmelden(f"{wo}: {len(gesetzt)} leere Zellen mit "
                        f"\u201e{trdf.MARKE}\u201c gefuellt", Style.TEXT)
        return gesetzt

    def _nach_unten_eingefuegt(self, gesetzt):
        """Nach unten kopiert - wie ein Block, die Variante wirkt dabei.

        Wer eine Variante nach unten zieht, will in jeder Zeile, was
        die Variante dort verlangt: die x in den Feldern, die sie nicht
        braucht. Ein Block aus Excel bringt seine Werte dagegen selbst
        mit; deshalb gilt das nur hier.
        """
        self._block_eingefuegt(gesetzt)
        varianten = [(zeile, wert) for zeile, spalte, wert in gesetzt
                     if spalte == trdfrohpruefung.VARIANTE]
        for zeile, wert in varianten:
            self._variante_wirkt(zeile, wert)
        if varianten:
            self._rechnung_vergessen([zeile for zeile, _wert in varianten])
            self._zeigen(nur_ergebnisse=True)
            for zeile, _wert in varianten:
                self._befund_nachtragen(zeile)
                self._block_auffrischen(zeile)
        self._rohmelden(f"{len(gesetzt)} Zellen nach unten gefuellt",
                        Style.TEXT)

    def _block_eingefuegt(self, gesetzt, uebrig=0):
        """Ein Block aus der Zwischenablage - einmal rechnen, einmal zeigen.

        Je Zelle neu zu rechnen waere bei dreihundert eingefuegten Werten
        dreihundertmal dieselbe Arbeit; hier wird alles uebernommen und
        danach ein einziges Mal gerechnet und gezeichnet.
        """
        for zeile, spalte, wert in gesetzt:
            self.vonhand[(zeile, spalte)] = wert
            for tabelle in self.rohtabellen:
                tabelle.setzen(zeile, spalte, rohtext(spalte, wert))
                tabelle.marke_setzen(zeile, spalte, "geaendert")
                tabelle.marke_setzen(zeile, "Probe", "geaendert")
        self._rechnung_vergessen({zeile for zeile, _spalte, _wert in gesetzt})
        self._zeigen(nur_ergebnisse=True)
        for probe in {zeile for zeile, _, _ in gesetzt}:
            self._befund_nachtragen(probe)
            self._block_auffrischen(probe)
        satz = f"{len(gesetzt)} Werte eingefuegt"
        if uebrig:
            satz += (f"  |  {uebrig} passten nicht mehr in die Tabelle und "
                     f"wurden nicht uebernommen")
        self._rohmelden(satz, Style.WARN if uebrig else Style.TEXT)

    def rohwert(self, probe: str, kuerzel: str) -> str:
        """Der Wert, mit dem gerechnet wird - und woher er kommt.

        Von Hand geaendert sticht alles; danach der eingefuegte Text,
        zuletzt das LIMS. So rechnet die Pruefung mit dem, was der Mensch
        gerade vor sich hat.
        """
        if (probe, kuerzel) in self.vonhand:
            return self.vonhand[(probe, kuerzel)]
        return self.rohwert_ohne_hand(probe, kuerzel)

    def aus_der_quelle(self, probe: str, kuerzel: str):
        """Der Rohwert aus der eingefuegten UM - None, wo keiner steht.

        Ohne eingefuegte UM gibt es keinen, und es gilt das LIMS; mit
        ihr kann sie Luecken haben, und dort tritt das LIMS ein.
        """
        return self.eingefuegt.get(probe, {}).get(kuerzel)

    def rohwert_ohne_hand(self, probe: str, kuerzel: str) -> str:
        """Derselbe Wert, aber so, wie er ohne die Handeingabe waere.

        Er ist der Vergleichsmassstab: nur was sich zwischen dieser
        Rechnung und der mit den Handwerten bewegt, ist eine Korrektur.
        """
        aus_der_quelle = self.aus_der_quelle(probe, kuerzel)
        if aus_der_quelle is not None and not trdf.leer(aus_der_quelle):
            return aus_der_quelle
        return self.limsroh.get(probe, {}).get(kuerzel, "")

    def _rechnen(self, probe: str, mit_hand=True) -> dict:
        hole = self.rohwert if mit_hand else self.rohwert_ohne_hand
        roh = {kuerzel: trdf.zahl(hole(probe, kuerzel))
               for kuerzel in self.rohliste}
        return trdf.rechnen(roh, self.formeln,
                            trdf.zahl(self.wgh.get(probe)), self.folge)

    def gerechnet(self, probe: str) -> dict:
        """Die berechneten Groessen - mit allem, was gerade gilt.

        Gemerkt, weil dieselbe Probe in einem Durchgang mehrfach gefragt
        wird: einmal fuer die Ergebnisse, einmal fuer die Pruefung, und
        beim Bodenblock noch einmal. Zwoelf Formeln je Probe mal
        dreihundert Proben sind sonst dreimal so viel Arbeit wie noetig.
        """
        if probe not in self._mit_hand:
            self._mit_hand[probe] = self._rechnen(probe, mit_hand=True)
        return self._mit_hand[probe]

    def gerechnet_ohne_hand(self, probe: str) -> dict:
        """Wie es ohne die Handeingaben aussaehe."""
        if not self.vonhand:
            return self.gerechnet(probe)
        if probe not in self._ohne_hand:
            self._ohne_hand[probe] = self._rechnen(probe, mit_hand=False)
        return self._ohne_hand[probe]

    def _rechnung_vergessen(self, proben=None):
        """Nach einer Aenderung: die gemerkten Rechnungen gelten nicht mehr.

        Mit `proben` nur die dieser Proben, und nur die mit Handwerten:
        eine Handeingabe aendert nichts an der Rechnung ohne sie, und
        nichts an den anderen Proben. Bei dreihundert Proben ist das der
        Unterschied zwischen einer Rechnung je Eingabe und sechshundert.
        Ohne Angabe - neue Quelle, Export - gilt nichts mehr.
        """
        if proben is None:
            self._mit_hand, self._ohne_hand = {}, {}
            return
        for probe in proben:
            self._mit_hand.pop(probe, None)

    def bewegt(self, probe: str) -> set:
        """Welche Groessen dieser Probe die Handeingabe verschoben hat."""
        bewegte = {kuerzel for (welche, kuerzel) in self.vonhand
                   if welche == probe}
        # Ohne Handwert in dieser Probe rechnet sie mit und ohne dasselbe
        # - die Rechnung ohne muss dann gar nicht erst laufen.
        if not bewegte:
            return bewegte
        ohne, mit = self.gerechnet_ohne_hand(probe), self.gerechnet(probe)
        for kuerzel in self.folge:
            if trdfexport.verschoben(ohne.get(kuerzel), mit.get(kuerzel)):
                bewegte.add(kuerzel)
        return bewegte

    @staticmethod
    def eingetragen(wert):
        """Der Stand, den ein Feld meint - eine Zahl, ein x oder nichts.

        Das LIMS kennt diese drei, und alle drei sind eine Aussage: eine
        Zahl ist gemessen, ein „x“ heisst "hier soll nichts stehen"
        (so setzt es die Eingabemaske, wenn die Variante den Rohwert
        nicht braucht), und leer heisst "hier steht noch nichts".
        """
        zahl = trdf.zahl(wert)
        if zahl is not None:
            return zahl
        return trdf.MARKE if str(wert if wert is not None else "").strip() \
            else ""

    def aenderungen(self) -> list:
        """Was geschrieben wuerde: von Hand bewegt und im LIMS anders.

        Zwei Bedingungen, und beide muessen zutreffen. Eine Zahl, die
        LabControl schon immer anders sah als das LIMS, ist ein Befund
        der Pruefung - ueber sie entscheidet das Labor und nicht dieser
        Knopf. Erst die Handeingabe macht aus dem Befund eine Korrektur.

        Geschrieben wird jeder der drei Staende: eine Zahl, ein x und
        das Leeren. Wer die Variante wechselt, aendert damit nicht bloss
        Zahlen, sondern raeumt die Zeile auf - und das gehoert genauso
        in das LIMS wie eine berichtigte Zahl.
        """
        gefunden = []
        for lnr, probe in sorted(self.proben, key=lambda p: (p[1], p[0])):
            eckdaten = {"lnr": lnr, "probe": probe}
            for kuerzel in self.rohliste:
                if (probe, kuerzel) not in self.vonhand:
                    continue
                alt = self.limsroh.get(probe, {}).get(kuerzel)
                neu = self.eingetragen(self.vonhand[(probe, kuerzel)])
                if not trdfexport.bewegt(alt, neu):
                    continue
                gefunden.append(self._aenderung(eckdaten, kuerzel,
                                                trdfexport.ROHWERT, alt, neu))
            if not self.von_hand_bewegt(probe):
                continue
            ohne, mit = self.gerechnet_ohne_hand(probe), self.gerechnet(probe)
            for kuerzel in self.folge:
                neu = self.eingetragen(mit.get(kuerzel))
                if not trdfexport.verschoben(ohne.get(kuerzel), neu):
                    continue
                alt = self.gebucht.get(probe, {}).get(kuerzel)
                if not trdfexport.bewegt(alt, neu):
                    continue
                gefunden.append(self._aenderung(eckdaten, kuerzel,
                                                trdfexport.BERECHNET, alt,
                                                neu))
        return gefunden

    def _aenderung(self, eckdaten, kuerzel, art, alt, neu) -> dict:
        probe = eckdaten["probe"]
        return trdfexport.aenderung(
            eckdaten, kuerzel, art, alt, neu, self.zeilen.get((probe, kuerzel)),
            self.parameternamen.get(kuerzel, kuerzel),
            anhang=self.anhang.get((probe, kuerzel)))

    def pruefwerte(self, probe: str) -> dict:
        """Die Zahlen, mit denen die Pruefung arbeitet.

        Genommen wird, was LabControl gerechnet hat - danach wird ja
        gefragt. Wo keine Formel greift, tritt der gebuchte Wert des LIMS
        an seine Stelle: eine Probe ganz ohne Urteil hilft niemandem.
        """
        gerechnet = self.gerechnet(probe)
        werte = {}
        for kuerzel in (trdfpruefung.SKA, trdfpruefung.SKA_GEMESSEN,
                        trdfpruefung.SKA_GESCHAETZT, trdfpruefung.VORRAT,
                        trdfpruefung.TRDF):
            wert = trdf.zahl(gerechnet.get(kuerzel))
            if wert is None:
                wert = trdf.zahl(self.gebucht.get(probe, {}).get(kuerzel))
            werte[kuerzel] = wert
        for kuerzel in (trdfpruefung.GBFANT, trdfpruefung.FAKTOR):
            werte[kuerzel] = trdf.zahl(self.rohwert(probe, kuerzel))
        # Die zweite Trockenrohdichte nur, wo die Serie sie fuehrt: ohne
        # sie gibt es nichts zu vergleichen, und ein fehlender Wert
        # duerfte nicht wie eine Abweichung aussehen.
        if trdfpruefung.TRDF_ALT in self.formeln:
            werte[trdfpruefung.TRDF_ALT] = trdf.zahl(
                gerechnet.get(trdfpruefung.TRDF_ALT))
        werte[trdfpruefung.VARIANTE] = trdf.zahl(
            self.rohwert(probe, trdfpruefung.VARIANTE))
        aufschluss = self.aufschluss.get(probe, {})
        werte[trdfpruefung.CGES] = trdf.zahl(aufschluss.get("Cges"))
        werte[trdfpruefung.CO3] = trdf.zahl(aufschluss.get("CO3"))
        return werte

    def _serienblick(self) -> dict:
        """Was der Blick auf die ganze Serie sagt.

        Einmal je Durchgang. Heute ist es nur der Kohlenstoff - mehr
        Carbonat als Gesamt kann es nicht geben -, und das liesse sich
        auch je Probe fragen. Der Weg bleibt, weil hier eine Pruefung
        wieder hereinkommt, sobald der Plot der Bezug ist; siehe den
        Kopf von `trdfserie`.
        """
        return trdfserie.bewerten(
            [{"probe": probe,
              "cges": self.aufschluss.get(probe, {}).get("Cges"),
              "co3": self.aufschluss.get(probe, {}).get("CO3")}
             for _, probe in self.proben])

    def geprueft(self) -> list:
        """Alle Proben mit ihren Werten und ihrem Urteil - nach Probe-Nr."""
        blatt = []
        aus_der_serie = self._serienblick()
        for lnr, probe in self.sichtbare_proben(nach_nummer=True):
            werte = self.pruefwerte(probe)
            bewertung = (trdfpruefung.bewerten(werte)
                         + aus_der_serie.get(probe, []))
            # Was am Rohwert haengt, steht vorneweg: ein Urteil ueber
            # eine Groesse aus einem fehlenden Rohwert ist keines, und
            # wo die beiden Stellen im LIMS auseinandergehen, rechnet es
            # mit einer Zahl, die in der Ergebnistabelle nicht steht.
            rohwerte = self.rohsatz(probe)
            vorneweg = trdfrohpruefung.anhang_ohne_variante(
                self._anhangvergleich(probe), rohwerte)
            if trdfrohpruefung.unvollstaendig(rohwerte):
                vorneweg = [ROHWERTE_UNVOLLSTAENDIG] + vorneweg
            blatt.append({"lnr": lnr, "probe": probe, "werte": werte,
                          "bewertung": vorneweg + bewertung,
                          **self._wiederholungsteil(probe)})
        return blatt

    # ------------------------------------------------------------- Anzeige
    def _zeigen(self, nur_ergebnisse=False):
        if not nur_ergebnisse:
            self._rohwerte_zeigen()
        self._ergebnisse_zeigen()
        self._pruefung_zeigen()

    def ist_wiederholung(self, probe: str) -> bool:
        """Ob diese Zeile eine Wiederholung ist - UM oder ME ueber 1."""
        _nummer, um, me = self.probenangabe(probe)
        return um != 1 or me != 1

    def _wiederholungsfolge(self, eintrag) -> tuple:
        """Wo eine Wiederholung steht: erst UM 2, 3 ..., dann ME 2, 3 ...

        Innerhalb jeder Stufe nach Probennummer.
        """
        lnr, probe = eintrag
        nummer, um, me = self.probenangabe(probe)
        if um != 1:
            return (0, um, nummer, me, lnr is None, lnr or 0)
        return (1, me, nummer, 0, lnr is None, lnr or 0)

    def sichtbare_proben(self, nach_nummer=False) -> list:
        """Die Proben, die die Tabellen zeigen - (lnr, probe), in ihrer Folge.

        Zuerst die Erstmessungen: nach Zeile oder, mit `nach_nummer`,
        nach Probennummer wie im Pruefblatt. Die Wiederholungen nur mit
        dem Haken „UM/ME ≠ 1“, und dann darunter.
        """
        erste = [eintrag for eintrag in self.proben
                 if not self.ist_wiederholung(eintrag[1])]
        if nach_nummer:
            erste.sort(key=lambda p: (p[1], p[0] is None, p[0] or 0))
        if not self.zeigt_wiederholungen():
            return erste
        weitere = [eintrag for eintrag in self.proben
                   if self.ist_wiederholung(eintrag[1])]
        return erste + sorted(weitere, key=self._wiederholungsfolge)

    def zeigt_wiederholungen(self) -> bool:
        schalter = getattr(self, "v_wiederholungen", None)
        return bool(schalter is not None and schalter.get())

    def ausgeblendete_wiederholungen(self) -> int:
        """Wie viele Wiederholungen gerade nicht dastehen."""
        if self.zeigt_wiederholungen():
            return 0
        return sum(1 for _lnr, probe in self.proben
                   if self.ist_wiederholung(probe))

    def _wiederholungen_umschalten(self):
        self._zeigen()
        self._auswahl_stellen()

    def probenangabe(self, probe: str) -> tuple:
        """Probennummer, UM und ME zu einer Zeile - (Nummer, 1, 1) ohne Angabe."""
        return self.wiederholungen.get(probe, (probe, 1, 1))

    def probenfelder(self, probe: str, spalte="Probe") -> dict:
        """Die Spalten, die eine Zeile benennen: Probe, UM und ME.

        Die Probenspalte zeigt die blosse Nummer; welche Messung es ist,
        sagen UM und ME daneben - bei einer Wiederholung steht dieselbe
        Nummer in mehreren Zeilen.
        """
        nummer, um, me = self.probenangabe(probe)
        return {spalte: nummer, "UM": um, "ME": me}

    def _wiederholungsteil(self, probe: str) -> dict:
        """Nummer, UM und ME fuer die Blaetter (CSV)."""
        nummer, um, me = self.probenangabe(probe)
        return {"nummer": nummer, "um": um, "me": me}

    def rohsatz(self, probe: str) -> dict:
        """Die Rohwerte einer Probe, so wie gerade gerechnet wird."""
        return {kuerzel: self.rohwert(probe, kuerzel)
                for kuerzel in self.rohliste}

    def rohbefund(self, probe: str) -> list:
        """Was an den Rohwerten dieser Probe auffaellt.

        Steht in der Variante ein x, faellt hier nichts mehr auf: die
        Teilprobe bekommt keine Variante, und damit fehlt auch keiner
        der Rohwerte, die eine braeuchte.
        """
        return trdfrohpruefung.bewerten(self.rohsatz(probe),
                                        self.wgh.get(probe),
                                        self._anhangvergleich(probe))

    def _anhangvergleich(self, probe: str) -> dict:
        """Rohwert je Stelle im LIMS - Ergebniszeile gegen Anhang.

        Nur was von Hand nicht angefasst wurde: ein Wert, den der
        Pruefer gerade aendert, steht ohnehin an beiden Stellen anders,
        und darueber gibt es schon eine rote Zelle.
        """
        vergleich = {}
        for kuerzel in self.rohliste:
            if (probe, kuerzel) in self.vonhand:
                continue
            am_anhang = self.anhang.get((probe, kuerzel))
            if am_anhang is None:
                continue
            vergleich[kuerzel] = (
                self.limsroh.get(probe, {}).get(kuerzel), am_anhang["mw"])
        return vergleich

    def auseinander(self) -> list:
        """Rohwerte, die im LIMS an den beiden Stellen verschieden stehen.

        Die Ergebniszeile zeigt der Mensch sich an, aus dem
        Teilprobenanhang rechnet das LIMS. Gehen die beiden auseinander,
        rechnet es mit einer Zahl, die in der Tabelle nicht steht - und
        niemand sieht es. Zurueck kommen Aenderungen im ueblichen
        Zuschnitt: der Anhang bekommt, was in der Ergebniszeile steht.
        """
        gefunden = []
        for lnr, probe in sorted(self.proben, key=lambda p: (p[1], p[0])):
            for kuerzel, (zeile, am_anhang) in sorted(
                    self._anhangvergleich(probe).items()):
                if trdf.zahl(zeile) is None or trdf.zahl(zeile) == trdf.zahl(
                        am_anhang):
                    continue
                gefunden.append(self._aenderung(
                    {"lnr": lnr, "probe": probe}, kuerzel,
                    trdfexport.ROHWERT, am_anhang, trdf.zahl(zeile)))
        return gefunden

    def rohblatt(self) -> list:
        """Alle Proben mit Rohwerten und Befund - fuer Tabelle und CSV."""
        return [{"lnr": lnr, "probe": probe, "werte": self.rohsatz(probe),
                 "wgh": zahltext(trdf.zahl(self.wgh.get(probe)),
                                 STELLEN_WGH),
                 "bewertung": self.rohbefund(probe),
                 **self._wiederholungsteil(probe)}
                for lnr, probe in self.sichtbare_proben()]

    def _kopfhinweise(self, tabelle, spalten, quellen=None):
        """Was ueber den Spaltenueberschriften steht, wenn die Maus wartet.

        Dieselbe Auskunft wie unter „Info“, nur auf zwei bis vier
        Zeilen: die Ueberschriften tragen die Kuerzel des LIMS, und wer
        sie nicht auswendig kennt, faehrt hinueber statt die Legende zu
        oeffnen.
        """
        tabelle.kopfhinweise(trdflegende.hinweise(
            spalten, self.methoden, quellen, self.beschreibungen()))

    def _rohspalten(self) -> tuple:
        """Die Spalten der Rohwerttabelle - auch die Legende fragt danach.

        Zurueck kommen die Spalten, die festen darunter und die
        Kopfzeile: beides steht in den Einstellungen und laesst sich
        unter „Info“ zurechtziehen.
        """
        return self._geordnet(
            BLATT_ROH,
            ["Zeile", "Probe", "UM", "ME"] + list(self.rohliste)
            + ["WGH", BEWERTUNGSSPALTE],
            roh=True)

    def _rohwerte_zeigen(self):
        spalten, fest, koepfe, _alle = self._rohspalten()
        zeilen, marken = [], {}
        auffaellig = 0
        for eintrag in self.rohblatt():
            probe = eintrag["probe"]
            werte = {"Zeile": eintrag["lnr"], **self.probenfelder(probe),
                     "WGH": eintrag["wgh"],
                     BEWERTUNGSSPALTE:
                         trdfrohpruefung.bewertungstext(eintrag["bewertung"])}
            for kuerzel in self.rohliste:
                werte[kuerzel] = rohtext(kuerzel, self.rohwert(probe, kuerzel))
                aus_der_quelle = self.aus_der_quelle(probe, kuerzel)
                im_lims = self.limsroh.get(probe, {}).get(kuerzel)
                if (probe, kuerzel) in self.vonhand:
                    marken[(probe, kuerzel)] = "geaendert"
                elif aus_der_quelle is not None and not (
                        trdf.leer(aus_der_quelle) and trdf.leer(im_lims)) and \
                        trdf.zahl(aus_der_quelle) != trdf.zahl(im_lims):
                    marken[(probe, kuerzel)] = "abweichung"
            if eintrag["bewertung"]:
                auffaellig += 1
                marken[(probe, BEWERTUNGSSPALTE)] = "abweichung"
            if self.von_hand_bewegt(probe):
                marken[(probe, "Probe")] = "geaendert"
            zeilen.append((probe, werte))
        gesamt = len(zeilen)
        if self.v_nur_rohbefunde.get():
            # Nur zeigen, wozu etwas zu sagen ist - gerechnet und
            # geschrieben wird weiter ueber die ganze Serie.
            zeilen = [(kennung, werte) for kennung, werte in zeilen
                      if werte.get(BEWERTUNGSSPALTE)]
        for tabelle in self.rohtabellen:
            tabelle.zellhinweise(self.rohhinweis)
            tabelle.fuellen(
                spalten, zeilen, aenderbar=self.rohliste, marken=marken,
                breiten={"Zeile": 56, "Probe": 110, "UM": 40, "ME": 40,
                         "WGH": 110,
                         BEWERTUNGSSPALTE: 420},
                fest=fest, ueberschriften=koepfe,
                zugspalten=("Probe",))
            self._kopfhinweise(tabelle, spalten)
        if gesamt:
            satz = (f"{gesamt - auffaellig} von {gesamt} Proben mit "
                    f"sauberen Rohwerten"
                    + (f"  |  {auffaellig} zu pruefen" if auffaellig else ""))
            if self.v_nur_rohbefunde.get():
                satz += f"  |  {gesamt - len(zeilen)} ausgeblendet"
            self._rohmelden(satz,
                            Style.WARN if auffaellig else Style.TEXT)

    def _ergebnisspalten(self) -> tuple:
        """Die Spalten der Ergebnistabelle und ihre Gruppierung.

        Je Groesse zwei Spalten - und sie gehoeren zusammen. Damit das
        Auge sie als Paar liest und nicht als zwei Nachbarn, bekommt
        jede zweite Groesse einen zarten Hintergrund; die Zuordnung
        steht in `gruppen`.
        """
        gerechnet = list(self.folge)
        spalten = ["Zeile", "Probe", "UM", "ME"]
        for kuerzel in gerechnet:
            spalten += [f"{kuerzel} LIMS", f"{kuerzel} ber."]
        spalten += ["WGH", "Cges", "CO3", BEWERTUNGSSPALTE]
        spalten, fest, koepfe, alle = self._geordnet(BLATT_ERGEBNIS, spalten)
        # Getoent wird erst, wenn die Reihenfolge steht: der Wechsel
        # zaehlt Groesse fuer Groesse in der Reihenfolge, in der sie
        # dann tatsaechlich stehen.
        gruppen, nummer, vorheriges = {}, 0, None
        for name in spalten:
            if name in fest or name == BEWERTUNGSSPALTE:
                continue
            kuerzel = trdflegende.schluessel(name)
            if vorheriges is not None and kuerzel != vorheriges:
                nummer += 1
            vorheriges = kuerzel
            gruppen[name] = nummer % 2 == 1
        return spalten, gruppen, fest, koepfe, alle

    def _ergebnisse_zeigen(self):
        gerechnet = list(self.folge)
        spalten, gruppen, fest, koepfe, _alle = self._ergebnisspalten()
        zeilen, marken = [], {}
        abweichungen = 0
        sichtbar = self.sichtbare_proben()
        for lnr, probe in sichtbar:
            ergebnis = self.gerechnet(probe)
            werte = {}
            werte.update({
                     "Zeile": lnr, **self.probenfelder(probe),
                     "WGH": zahltext(trdf.zahl(self.wgh.get(probe)),
                                     STELLEN_WGH),
                     "Cges": zahltext(trdf.zahl(
                         self.aufschluss.get(probe, {}).get("Cges"))),
                     "CO3": zahltext(trdf.zahl(
                         self.aufschluss.get(probe, {}).get("CO3")))})
            for name, getoent in gruppen.items():
                if getoent:
                    marken[(probe, name)] = "gruppe"
            # Erst nach der Toenung: sie ist Schmuck, dies ist eine
            # Auskunft - der Wert kommt nicht von dieser Probe der
            # Serie, sondern von einer anderen Anlage derselben Nummer.
            for name in trdf.ATNULL_PARAMETER.values():
                if self.aufschlusshinweis(probe, name):
                    marken[(probe, name)] = "ersatz"
            bewegte = self.bewegt(probe)
            auseinander = []
            for kuerzel in gerechnet:
                gebucht = self.gebucht.get(probe, {}).get(kuerzel)
                meins = ergebnis.get(kuerzel)
                stellen = trdfpruefung.stellen_fuer(kuerzel, STELLEN)
                werte[f"{kuerzel} LIMS"] = (
                    trdf.MARKE if trdf.leer(gebucht)
                    else zahltext(trdf.zahl(gebucht), stellen))
                werte[f"{kuerzel} ber."] = zahltext(meins, stellen)
                # Rot heisst hier: das habe *ich* gerade bewegt. Was nur
                # anders gebucht ist als gerechnet, bleibt ein Befund und
                # steht in Amber - sonst saehen beide gleich aus.
                #
                # Verglichen wird nur, wo im LIMS ueberhaupt etwas steht:
                # eine Zahl, ein x oder eine Null. Eine leere Zelle heisst,
                # dass dort noch nicht gerechnet wurde - das ist kein
                # Widerspruch zu dem, was LabControl rechnet, sondern eine
                # Serie, die ihre Groessen noch vor sich hat.
                if str(gebucht or "").strip() and not trdf.gleich(meins,
                                                                   gebucht):
                    auseinander.append(kuerzel)
                    abweichungen += 1
                    marken[(probe, f"{kuerzel} LIMS")] = "abweichung"
                    marken[(probe, f"{kuerzel} ber.")] = "abweichung"
                if kuerzel in bewegte:
                    marken[(probe, f"{kuerzel} LIMS")] = "geaendert"
                    marken[(probe, f"{kuerzel} ber.")] = "geaendert"
            # Die Zeile selbst sagt, dass in ihr gearbeitet wurde - auch
            # wenn sich keine Groesse bewegt hat.
            if bewegte or self.von_hand_bewegt(probe):
                marken[(probe, "Probe")] = "geaendert"
                marken[(probe, "Zeile")] = "geaendert"
            werte[BEWERTUNGSSPALTE] = (
                AUSEINANDER.format(", ".join(auseinander))
                if auseinander else "")
            if auseinander:
                marken[(probe, BEWERTUNGSSPALTE)] = "abweichung"
            zeilen.append((probe, werte))
        def fuellen(tabelle):
            tabelle.zellhinweise(self.ergebnishinweis)
            tabelle.fuellen(
                spalten, zeilen, marken=marken,
                breiten={"Zeile": 56, "Probe": 110, "UM": 40, "ME": 40,
                         BEWERTUNGSSPALTE: 420},
                fest=fest, ueberschriften=koepfe)
            self._kopfhinweise(tabelle, spalten)
        for tabelle in self.ergebnistabellen:
            self._fuellen(tabelle, lambda t=tabelle: fuellen(t))
        if sichtbar:
            gesamt = len(sichtbar) * len(gerechnet)
            verborgen = self.ausgeblendete_wiederholungen()
            self._melden(
                f"{gesamt - abweichungen} von {gesamt} Werten stimmen"
                + (f"  |  {abweichungen} Abweichungen" if abweichungen
                   else "")
                + (f"  |  {verborgen} Wiederholungen (UM/ME \u2260 1) "
                   f"ausgeblendet" if verborgen else ""),
                Style.WARN if abweichungen else Style.TEXT)

    def _pruefspalten(self) -> tuple:
        """Die Spalten des Pruefblatts - in der Reihenfolge des Pruefers."""
        return self._geordnet(
            BLATT_PRUEFUNG,
            list(trdfpruefung.SPALTEN),
            trdfpruefung.QUELLEN)

    def _pruefung_zeigen(self):
        """Das Arbeitsblatt fuellen - eine Zeile je Probe."""
        spalten, fest, koepfe, _alle = self._pruefspalten()
        zeilen, marken = [], {}
        auffaellig = 0
        blatt = self.geprueft()
        for probe in blatt:
            werte = {"Zeile": probe["lnr"],
                     **self.probenfelder(probe["probe"], "Probe-Nr."),
                     "Bewertung": trdfpruefung.bewertungstext(
                         probe["bewertung"])}
            bewegte = self.bewegt(probe["probe"])
            # Welche Zellen die Bewertung meint: sie werden wie die
            # Bewertung selbst gefaerbt, damit bei zwoelf Spalten nicht
            # gesucht werden muss, welcher Wert gemeint ist.
            gemeint = trdfpruefung.betroffen(probe["bewertung"],
                                             trdfserie.BETROFFEN)
            for name in [eine for eine in spalten
                         if eine in trdfpruefung.QUELLEN]:
                kuerzel = trdfpruefung.QUELLEN[name]
                werte[name] = trdfpruefung.gerundet(
                    probe["werte"].get(kuerzel),
                    trdfpruefung.stellen_fuer(kuerzel))
                if kuerzel in bewegte:
                    marken[(probe["probe"], name)] = "geaendert"
                elif kuerzel in gemeint:
                    marken[(probe["probe"], name)] = "abweichung"
            for name in trdf.ATNULL_PARAMETER.values():
                if self.aufschlusshinweis(probe["probe"], name):
                    marken[(probe["probe"], name)] = "ersatz"
            if probe["bewertung"]:
                auffaellig += 1
                marken[(probe["probe"], "Bewertung")] = "abweichung"
            if bewegte or self.von_hand_bewegt(probe["probe"]):
                marken[(probe["probe"], "Probe-Nr.")] = "geaendert"
            zeilen.append((probe["probe"], werte))
        gesamt = len(zeilen)
        if self.v_nur_befunde.get():
            # Nur zeigen, wozu etwas zu sagen ist - gerechnet und
            # geschrieben wird weiter ueber die ganze Serie.
            mit_befund = {probe["probe"] for probe in blatt
                          if probe["bewertung"]}
            zeilen = [(kennung, werte) for kennung, werte in zeilen
                      if kennung in mit_befund]
        def fuellen():
            self.pruefungstabelle.zellhinweise(self.aufschlusshinweis)
            self.pruefungstabelle.fuellen(
                spalten, zeilen, marken=marken,
                breiten=dict(BREITEN),
                mitwachsend=(BEWERTUNGSSPALTE,), fest=fest,
                ueberschriften=koepfe)
            self._kopfhinweise(self.pruefungstabelle, spalten,
                               trdfpruefung.QUELLEN)
        self._fuellen(self.pruefungstabelle, fuellen)
        if gesamt:
            satz = (f"{gesamt - auffaellig} von {gesamt} Proben ohne Befund"
                    + (f"  |  {auffaellig} zu pruefen" if auffaellig else ""))
            if self.v_nur_befunde.get():
                satz += f"  |  {gesamt - len(zeilen)} ausgeblendet"
            self._pruefmelden(satz, Style.WARN if auffaellig else Style.TEXT)

    def _bild_zeigen(self):
        """Die Trockenrohdichte ueber dem Kohlenstoff - alle Proben auf einmal.

        Die Tabelle sagt, dass ein Wert ausserhalb liegt; das Bild sagt,
        wie weit - und ob die ganze Serie an einer Klassengrenze klebt
        oder eine einzelne Probe herausfaellt.
        """
        blatt = self.geprueft()
        if not blatt:
            self._pruefmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return
        vorhandenes = getattr(self, "bildfenster", None)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            vorhandenes.destroy()
        self.bildfenster = Bildfenster(self, self.v_serie.get().strip(),
                                       self._bildpunkte(blatt),
                                       self._block_zeigen)

    def _bildpunkte(self, blatt) -> list:
        punkte = []
        for probe in blatt:
            werte = probe["werte"]
            punkte.append({
                "probe": probe["probe"], "trdf": werte.get(trdfpruefung.TRDF),
                "cges": werte.get(trdfpruefung.CGES),
                "co3": werte.get(trdfpruefung.CO3),
                "marke": "geaendert" if trdfblock.DICHTE in self.bewegt(
                    probe["probe"]) else None})
        return punkte

    def _pruefmelden(self, text, farbe=Style.MUTED):
        self.pruefstand.config(text=text, fg=farbe)

    def _legende_stellen(self):
        """Welche Spalte welchen Parameter des LIMS zeigt."""
        teile = []
        for name in trdfpruefung.SPALTEN[4:-2]:
            kuerzel = trdfpruefung.QUELLEN[name]
            im_lims = self.parameternamen.get(kuerzel)
            teile.append(f"{name} = {im_lims or kuerzel}")
        methoden = (f"U-Methode {self.um_kuerzel}  |  Cges aus "
                    f"{lims_db.ATNULL_MARKE}, CO3 aus "
                    f"{lims_db.ATNULL_CO3_MARKE}")
        self.legende.config(text=methoden + "\n" + "  ·  ".join(teile))
        self.info_pruefung.setzen(
            PRUEF_ERKLAERUNG + "\n\n" + methoden + "\n"
            + "\n".join(teile))

    # ------------------------------------------------------------- Der Block
    # Ein Klick auf die Probennummer - in welcher der drei Tabellen auch
    # immer - oeffnet den Bodenblock: die Zahlen einer Zeile sagen, was
    # herauskam, das Bild sagt, ob Schaetzung und Wagung zusammenpassen.

    def _block_zeigen(self, zeile, spalte, ueber=None):
        """Der Bodenblock zu einer Probe - je Probe ein Fenster.

        `ueber` ist das Fenster, ueber dem er liegen soll. Wer in der
        Grossansicht auf die Probennummer klickt, will den Block nicht
        dahinter verschwinden sehen.
        """
        if spalte not in ("Probe", "Probe-Nr.") or not zeile:
            return
        vorhandenes = self.bloecke.get(zeile)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            self._block_auffrischen(zeile)
            vorhandenes.lift()
            return
        fenster = trdfblock.zeigen(
            ueber or self, zeile, self.rohsatz(zeile), self.gerechnet(zeile),
            bei_wechsel=self._block_wechseln)
        self.bloecke[zeile] = fenster
        # Geht das Fenster wieder zu, geht die Unterlegung mit ihm.
        fenster.bind("<Destroy>",
                     lambda ereignis, f=fenster:
                         self._block_geschlossen(ereignis, f), add="+")
        self._auswahl_stellen()

    def _gross_zeigen(self):
        """Die Rohwerte gross - zum Eintragen ohne Lupe."""
        vorhandenes = getattr(self, "_grossansicht", None)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            vorhandenes.lift()
            vorhandenes.focus_set()
            return vorhandenes
        if not self.proben:
            self._rohmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return None
        self._grossansicht = Grossansicht(self)
        return self._grossansicht

    def rohansicht_anmelden(self, tabelle):
        """Eine zweite Ansicht der Rohwerte - sie wird mitgefuehrt."""
        if tabelle not in self.rohtabellen:
            self.rohtabellen.append(tabelle)
        self._rohwerte_zeigen()
        # Auch die neue Ansicht zeigt, wo gerade gearbeitet wird.
        self._auswahl_stellen()

    def rohansicht_abmelden(self, tabelle):
        if tabelle in self.rohtabellen:
            self.rohtabellen.remove(tabelle)

    def _block_wechseln(self, block, richtung: int):
        """Pfeil rauf und runter im Blockfenster: eine Probe weiter.

        Geblaettert wird in der Reihenfolge, in der die Proben in den
        Tabellen stehen. Am Ende der Liste ist Schluss - wer unten
        ankommt, will nicht oben wieder anfangen, sondern merken, dass
        er unten ist.
        """
        namen = [probe for _lnr, probe in self.sichtbare_proben()]
        if block.probe not in namen:
            return
        stelle = namen.index(block.probe) + richtung
        if not 0 <= stelle < len(namen):
            return
        neue = namen[stelle]
        vorhandenes = self.bloecke.get(neue)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            # Diese Probe steht schon in einem eigenen Fenster - zwei
            # gleiche waeren nur verwirrend.
            vorhandenes.lift()
            vorhandenes.focus_set()
            return
        self.bloecke.pop(block.probe, None)
        self.bloecke[neue] = block
        block.uebernehmen(neue, self.rohsatz(neue), self.gerechnet(neue))
        self._auswahl_stellen()

    def _block_geschlossen(self, ereignis, fenster):
        """Ein Blockfenster ist zu - wessen Zeile also nicht mehr gewaehlt.

        `<Destroy>` kommt auch von jedem Kind des Fensters; gemeint ist
        nur das Fenster selbst.
        """
        if ereignis.widget is not fenster:
            return
        for probe, offenes in list(self.bloecke.items()):
            if offenes is fenster:
                self.bloecke.pop(probe, None)
        self._auswahl_stellen()

    def _auswahl_stellen(self):
        """Unterlegt in allen Tabellen die Proben mit offenem Blockbild.

        Wer im Blockbild mit den Pfeilen durch die Serie blaettert,
        sieht so in der Tabelle mit, wo er gerade ist - in der kleinen
        wie in der grossen.
        """
        offen = [probe for probe, fenster in self.bloecke.items()
                 if fenster is not None and fenster.winfo_exists()]
        # Dazu die Zeile, in der gerade getippt wird - sie ist der Ort,
        # an dem gearbeitet wird, auch ohne offenen Block.
        if self.arbeitszeile and self.arbeitszeile not in offen:
            offen.append(self.arbeitszeile)
        for tabelle in list(self.rohtabellen) + list(
                getattr(self, "ergebnistabellen", [])) + [
                getattr(self, "pruefungstabelle", None)]:
            if tabelle is None:
                continue
            try:
                tabelle.auswahl(offen)
            except tk.TclError:
                pass

    def _block_auffrischen(self, probe: str):
        """Ein offener Block folgt der Aenderung, ohne zu blinken.

        Genau dafuer ist er da: einen Rohwert aendern und zusehen, wie
        der Skelettanteil wandert. Ein Fenster, das sich dabei schliesst
        und neu aufgeht, waere das Gegenteil davon.
        """
        block = self.bloecke.get(probe)
        if block is None or not block.winfo_exists():
            self.bloecke.pop(probe, None)
            return
        block.neu_zeichnen(self.rohsatz(probe), self.gerechnet(probe))

    # ------------------------------------------------------ Zurueckschreiben
    # Der einzige Weg im Programm, der einen Messwert ueberschreibt. Er
    # geht nur ueber eine bestaetigte Uebersicht und nur nach einer
    # Sicherung - beides steht unten in dieser Reihenfolge und laesst
    # sich nicht umgehen.

    def _rohblatt_speichern(self):
        """Die Rohwerte mit ihrem Befund als Blatt."""
        blatt = self.rohblatt()
        if not blatt:
            self._rohmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfrohpruefung.ORDNER)
        pfad = trdfrohpruefung.schreiben(ordner, self.v_serie.get().strip(),
                                         blatt, self.rohliste)
        if not pfad:
            self._rohmelden(f"Die Datei liess sich nicht schreiben. Steht "
                            f"der Ordner „{ordner}“ zur Verfuegung?",
                            Style.ERROR)
            return
        self._rohmelden(f"{len(blatt)} Zeilen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)

    def _aenderungen_speichern(self):
        """Die von Hand geaenderten Werte als Blatt - zum Ansehen und Drucken."""
        geaendert = self.aenderungen()
        if not geaendert:
            self._rohmelden("Es ist nichts von Hand geaendert.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        pfad = trdfexport.blatt_schreiben(ordner, self.v_serie.get().strip(),
                                          geaendert, dt.datetime.now())
        if not pfad:
            self._rohmelden(f"Die Datei liess sich nicht schreiben. Steht "
                            f"der Ordner „{ordner}“ zur Verfuegung?",
                            Style.ERROR)
            return
        self._rohmelden(f"{len(geaendert)} Aenderungen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)

    def _rohmelden(self, text, farbe=Style.MUTED):
        self.rohstand.config(text=text, fg=farbe)

    def _lims_schreiben(self):
        """Zeigt, was geschrieben wuerde - geschrieben wird erst danach."""
        zugang = self._zugang_holen()
        if zugang is None:
            self._melden("Erst anmelden.", Style.WARN)
            return
        geaendert = self.aenderungen()
        if not geaendert:
            self._melden("Es ist nichts von Hand geaendert - es gibt nichts "
                         "zu schreiben.", Style.WARN)
            return
        Exportvorschau(self, geaendert, self.v_serie.get().strip(),
                       lambda: self._wirklich_schreiben(geaendert))

    def _anhang_angleichen(self):
        """Den Teilprobenanhang auf den Stand der Ergebniszeile bringen.

        Der Fall, fuer den es diesen Weg gibt: eine Korrektur ist nur an
        einer der beiden Stellen angekommen - aus einer aelteren
        Sicherung zurueckgespielt etwa, die keine ROHW_ID trug. Dann
        steht in der Ergebnistabelle die eine Zahl und in der Rechnung
        des LIMS die andere. Geschrieben wird nur der Anhang; die
        Ergebniszeile gilt und bleibt, wie sie ist.
        """
        zugang = self._zugang_holen()
        if zugang is None:
            self._rohmelden("Erst anmelden.", Style.WARN)
            return
        geaendert = self.auseinander()
        if not geaendert:
            self._rohmelden("Ergebniszeile und Teilprobenanhang stimmen "
                            "ueberein.", Style.TEXT)
            return
        Exportvorschau(self, geaendert, self.v_serie.get().strip(),
                       lambda: self._anhang_schreiben(geaendert),
                       nur_anhang=True)

    def _anhang_schreiben(self, geaendert):
        """Erst die Sicherung, dann der Anhang - wie ueberall hier."""
        zugang = self._zugang_holen()
        if zugang is None:
            return
        serie = self.v_serie.get().strip()
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        sicherung = trdfexport.backup_schreiben(ordner, serie, geaendert,
                                                dt.datetime.now())
        if not sicherung:
            self._melden(f"Ohne Sicherung wird nichts geschrieben. Der "
                         f"Ordner „{ordner}“ liess sich nicht anlegen.",
                         Style.ERROR)
            return
        anhang = trdfexport.anhangsaetze(geaendert)
        hinweise = trdfexport.anhanghinweise(geaendert, serie)
        self._melden(f"Sicherung: {sicherung}  |  {len(anhang)} Rohwerte am "
                     f"Anhang werden angeglichen ...")
        self.update_idletasks()

        def arbeit():
            # Ohne Ergebnissaetze: die Ergebniszeile ist die Vorlage und
            # wird nicht angefasst.
            return lims_db.trdf_exportieren(zugang, [], None, anhang,
                                            hinweise)

        def fertig(bericht):
            trdfexport.protokollieren(ordner,
                                      getattr(zugang, "benutzer", ""),
                                      anhang, hinweise,
                                      sql=lims_db.trdf_anhang_sql())
            getroffen = bericht.get("anhang_geschrieben", 0)
            fehlt = len(bericht.get("anhang_ohne_zeile", ()))
            offen = len(bericht.get("anhang_nicht_uebernommen", ()))
            satz = (f"{getroffen} Rohwerte am Teilprobenanhang angeglichen"
                    f"  |  Sicherung: {sicherung}")
            if fehlt:
                satz += f"  |  {fehlt} Zeilen nicht gefunden"
            if offen:
                satz += f"  |  {offen} stehen danach noch wie vorher da"
            self._melden(satz, Style.ERROR if offen
                         else Style.WARN if fehlt else Style.TEXT)
            (messagebox.showerror if offen else
             messagebox.showwarning if fehlt else messagebox.showinfo)(
                "Teilprobenanhang angeglichen", satz, parent=self)
            self._abrufen()      # der Stand im Fenster gilt nicht mehr

        self._im_hintergrund(arbeit, fertig, self._schreiben_schiefgegangen)

    def _zurueckspielen(self):
        """Den Stand vor einer Korrektur wiederherstellen.

        Es gibt einen Weg, der ueberschreibt - also muss es einen zurueck
        geben. Gelesen wird die Sicherung, die damals angelegt wurde;
        geschrieben wird erst nach derselben bestaetigten Uebersicht.
        """
        zugang = self._zugang_holen()
        if zugang is None:
            self._melden("Erst anmelden.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        pfad = filedialog.askopenfilename(
            parent=self, title="Sicherung waehlen",
            initialdir=ordner if os.path.isdir(ordner) else self._ordner,
            filetypes=[("Sicherung", "*.csv"), ("Alle Dateien", "*.*")])
        if not pfad:
            return
        try:
            zeilen = trdfexport.gesichertes_lesen(pfad)
        except (trdfexport.Einlesefehler, OSError) as fehler:
            self._melden(str(fehler), Style.ERROR)
            return
        geaendert = trdfexport.zurueck(zeilen)
        if not geaendert:
            self._melden("In dieser Sicherung steht keine Zeile.", Style.WARN)
            return
        Exportvorschau(self, geaendert, os.path.basename(pfad),
                       lambda: self._zurueck_schreiben(geaendert, pfad),
                       zurueck=True)

    def _zurueck_schreiben(self, geaendert, pfad: str):
        """Schreibt den gesicherten Stand - beide Stellen, eine Transaktion."""
        zugang = self._zugang_holen()
        if zugang is None:
            return
        name = os.path.basename(pfad)
        saetze = trdfexport.zuruecksaetze(geaendert)
        anhang = trdfexport.zurueck_anhangsaetze(geaendert)
        hinweise = trdfexport.zurueckhinweise(geaendert, name)
        self._melden(f"{len(saetze)} Zeilen werden aus {name} "
                     f"zurueckgespielt ...")
        self.update_idletasks()

        def arbeit():
            return lims_db.trdf_exportieren(zugang, saetze, hinweise, anhang,
                                            hinweise, zurueck=True)

        def fertig(bericht):
            ordner = os.path.join(self._ordner, trdfexport.ORDNER)
            benutzer = getattr(zugang, "benutzer", "")
            # Beide Anweisungen in den Log - der Anhang gehoert genauso
            # dazu wie die Ergebniszeile, sonst steht dort die halbe
            # Wahrheit ueber das, was geschehen ist.
            trdfexport.protokollieren(ordner, benutzer, saetze, hinweise,
                                      sql=lims_db.trdf_zurueck_sql())
            trdfexport.protokollieren(ordner, benutzer, anhang, hinweise,
                                      sql=lims_db.trdf_anhang_zurueck_sql())
            satz = (f"{bericht['geschrieben']} Ergebniszeilen und "
                    f"{bericht.get('anhang_geschrieben', 0)} Rohwerte am "
                    f"Anhang zurueckgespielt aus {name}")
            fehlt = (len(bericht["ohne_zeile"])
                     + len(bericht.get("anhang_ohne_zeile", ())))
            if fehlt:
                satz += f"  |  {fehlt} Zeilen nicht gefunden"
            # Der Exportbericht stimmt jetzt nicht mehr: was er zeigt,
            # ist gerade zurueckgenommen worden.
            self._bericht_verworfen(name)
            self._melden(satz, Style.WARN if fehlt else Style.TEXT)
            (messagebox.showwarning if fehlt else messagebox.showinfo)(
                "Sicherung zurueckgespielt", satz, parent=self)
            self._abrufen()          # der Stand im Fenster gilt nicht mehr

        self._im_hintergrund(arbeit, fertig, self._schreiben_schiefgegangen)

    def _wirklich_schreiben(self, geaendert):
        """Erst die Sicherung, dann die Datenbank - in dieser Reihenfolge."""
        zugang = self._zugang_holen()
        if zugang is None:
            return
        serie = self.v_serie.get().strip()
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        sicherung = trdfexport.backup_schreiben(ordner, serie, geaendert,
                                                dt.datetime.now())
        if not sicherung:
            self._melden(f"Ohne Sicherung wird nichts geschrieben. Der "
                         f"Ordner „{ordner}“ liess sich nicht anlegen.",
                         Style.ERROR)
            return
        saetze = trdfexport.saetze(geaendert)
        hinweise = trdfexport.hinweise(geaendert, serie)
        anhang = trdfexport.anhangsaetze(geaendert)
        anhanghinweise = trdfexport.anhanghinweise(geaendert, serie)
        self._melden(f"Sicherung: {sicherung}  |  {len(saetze)} Zeilen "
                     f"und {len(anhang)} Rohwerte am Anhang werden "
                     f"geschrieben ...")
        self.update_idletasks()

        def arbeit():
            # Geleert werden darf: die Uebersicht davor hat gesagt, wie
            # viele Werte es trifft, und die Sicherung liegt schon.
            return lims_db.trdf_exportieren(zugang, saetze, hinweise,
                                            anhang, anhanghinweise,
                                            leeren=True)

        def fertig(bericht):
            self._geschrieben(geaendert, bericht, sicherung)

        self._im_hintergrund(arbeit, fertig, self._schreiben_schiefgegangen)

    def _gescheitert(self, geaendert, bericht: dict) -> list:
        """Die Aenderungen, bei denen nach dem Schreiben der alte Wert steht.

        Getroffen und trotzdem unveraendert - das ist der Fall, den man
        von aussen nicht sieht: die Anweisung lief durch, die Zeile gab
        es, und geschehen ist nichts.
        """
        zeilen = {(satz["prob_id"], satz["pm_id"], satz["pm_ver"])
                  for satz in bericht.get("nicht_uebernommen", ())}
        anhaenge = {(satz["prob_id"], satz["rohw_id"])
                    for satz in bericht.get("anhang_nicht_uebernommen", ())}
        gefunden = []
        for eine in geaendert:
            zeile, anhang = eine.get("zeile") or {}, eine.get("anhang") or {}
            if (zeile.get("prob_id"), zeile.get("pm_id"),
                    zeile.get("pm_ver")) in zeilen or (
                        anhang and (anhang.get("prob_id"),
                                    anhang.get("rohw_id")) in anhaenge):
                gefunden.append(eine)
        return gefunden

    def _geschrieben(self, geaendert, bericht: dict, sicherung: str):
        """Uebernimmt den neuen Stand in die Anzeige und meldet ihn."""
        fehlend = {(satz["prob_id"], satz["pm_id"], satz["pm_ver"])
                   for satz in bericht["ohne_zeile"]}
        gescheitert = self._gescheitert(geaendert, bericht)
        angekommen = [eine for eine in geaendert
                      if eine.get("zeile") and eine not in gescheitert and
                      (eine["zeile"]["prob_id"], eine["zeile"]["pm_id"],
                       eine["zeile"]["pm_ver"]) not in fehlend]
        self._mitschreiben(angekommen)
        for eine in angekommen:
            self._uebernommen(eine)
        self._rechnung_vergessen()
        self._zeigen()
        # Der Bericht haelt fest, was angekommen ist - nicht, was
        # geschickt wurde. Was steckengeblieben ist, steht daneben.
        self._bericht_merken(angekommen, self.v_serie.get().strip(),
                             sicherung, gescheitert)
        getroffen = bericht["geschrieben"]
        am_anhang = bericht.get("anhang_geschrieben", 0)
        fehlend = (len(bericht["ohne_zeile"])
                   + len(bericht.get("anhang_ohne_zeile", ())))
        satz = (f"{getroffen} Ergebniszeilen und {am_anhang} Rohwerte am "
                f"Anhang geschrieben  |  Sicherung: {sicherung}")
        if fehlend:
            satz += f"  |  {fehlend} Zeilen im LIMS nicht gefunden"
        if gescheitert:
            satz += (f"  |  {len(gescheitert)} Werte stehen danach noch "
                     f"wie vorher da")
        self._melden(satz, Style.ERROR if gescheitert
                     else Style.WARN if fehlend else Style.TEXT)
        if gescheitert:
            self._nicht_uebernommen(gescheitert, sicherung)
            return
        self._gemeldet(getroffen, am_anhang, fehlend, sicherung)

    def _nicht_uebernommen(self, gescheitert, sicherung: str):
        """Die Meldung, die nach dem Nachlesen wirklich zaehlt."""
        namen = ", ".join(f"{eine.get('probe')} {eine['kuerzel']}"
                          for eine in gescheitert[:12])
        if len(gescheitert) > 12:
            namen += f" und {len(gescheitert) - 12} weitere"
        messagebox.showerror(
            "Update fehlgeschlagen",
            f"{len(gescheitert)} Werte stehen in der Datenbank nach dem "
            "Schreiben immer noch so da wie vorher.\n\nDie Anweisung lief "
            "durch, die Zeilen gibt es, und geschrieben wurde trotzdem "
            "nichts - das deutet auf einen Ausloeser, ein fehlendes Recht "
            "oder eine Sicht statt einer Tabelle hin. Der Stand im Fenster "
            "bleibt deshalb unveraendert.\n\n"
            f"Betroffen: {namen}\n\nWas geschickt wurde, steht im "
            f"Korrekturlog neben der Sicherung:\n{sicherung}", parent=self)

    def _gemeldet(self, getroffen: int, am_anhang: int, fehlend: int,
                  sicherung: str):
        """Sagt es auch im Fenster - nicht nur in der Statuszeile.

        Ein Schreibweg, der still bleibt, laesst offen, ob er etwas
        getan hat. Vor allem der Fall "keine Zeile getroffen" faellt
        sonst niemandem auf: die Anweisung war fehlerfrei, sie hat nur
        nichts gefunden.
        """
        satz = (f"{getroffen} Ergebniszeilen und {am_anhang} Rohwerte am "
                f"Teilprobenanhang wurden geschrieben und festgeschrieben "
                f"(COMMIT).\n\nDie Sicherung liegt unter:\n{sicherung}")
        if fehlend:
            satz += (f"\n\n{fehlend} Zeilen wurden im LIMS nicht gefunden "
                     "und deshalb nicht geschrieben.")
        if not getroffen and not am_anhang:
            messagebox.showwarning(
                "Es wurde nichts geschrieben",
                "Keine einzige Zeile wurde getroffen. Die Anweisung lief "
                "fehlerfrei durch, hat aber im LIMS nichts gefunden - der "
                "Schluessel aus PROB_ID, PM_ID, PM_VER, UM_ID und GEGR_ID "
                "passt dort auf keine Zeile.\n\nWas geschickt wurde, "
                "steht im Aenderungsprotokoll und im Korrekturlog neben "
                f"der Sicherung:\n{sicherung}", parent=self)
            return
        (messagebox.showwarning if fehlend else messagebox.showinfo)(
            "In das LIMS geschrieben", satz, parent=self)

    def _mitschreiben(self, angekommen):
        """Der Korrekturlog neben den Sicherungen - die letzten 5000.

        Das Aenderungsprotokoll neben dem Programm fuehrt ohnehin jede
        Anweisung. Dieser Log steht dort, wo auch der alte Stand liegt,
        und beantwortet die engere Frage: was hat die TRDF-Pruefung in
        diese Datenbank geschrieben?
        """
        if not angekommen:
            return
        zugang = self._zugang_holen()
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        benutzer = getattr(zugang, "benutzer", "")
        serie = self.v_serie.get().strip()
        trdfexport.protokollieren(ordner, benutzer,
                                  trdfexport.saetze(angekommen),
                                  trdfexport.hinweise(angekommen, serie))
        trdfexport.protokollieren(ordner, benutzer,
                                  trdfexport.anhangsaetze(angekommen),
                                  trdfexport.anhanghinweise(angekommen, serie),
                                  sql=lims_db.trdf_anhang_sql())

    def _uebernommen(self, eine: dict):
        """Was geschrieben wurde, steht ab jetzt auch hier als LIMS-Stand."""
        probe, kuerzel = eine["probe"], eine["kuerzel"]
        text = trdfexport.wertfeld(eine["neu"])
        eimer = self.gebucht if eine["art"] == trdfexport.BERECHNET \
            else self.limsroh
        eimer.setdefault(probe, {})[kuerzel] = text
        zeile = self.zeilen.get((probe, kuerzel))
        if zeile is not None:
            zeile["mw_roh"] = zeile["mw"] = text
        am_anhang = self.anhang.get((probe, kuerzel))
        if am_anhang is not None:
            am_anhang["mw"] = text
        self.vonhand.pop((probe, kuerzel), None)

    def ergebnisblatt(self) -> tuple:
        """Die berechneten Groessen, wie sie dastehen: (Kopf, Zeilen).

        Gelesen wird aus der Tabelle selbst - mit ihrer Spaltenordnung
        und den Ueberschriften, die unter \u201eInfo\u201c gewaehlt sind -,
        damit im Blatt steht, was auf dem Schirm stand.
        """
        self._nachziehen(alle=True)
        tabelle = self.ergebnistabelle
        spalten = tabelle.spalten()
        kopf = [" ".join(tabelle.ueberschriftzeilen(name)) or name
                for name in spalten]
        zeilen = [[tabelle.wert(kennung, name).strip() for name in spalten]
                  for kennung in tabelle.zeilen()]
        return kopf, zeilen

    def _ergebnisblatt_speichern(self):
        """Die berechneten Groessen als CSV ablegen und oeffnen."""
        kopf, zeilen = self.ergebnisblatt()
        if not zeilen:
            self._melden("Es ist keine Serie abgerufen.", Style.WARN)
            return ""
        serie = self.v_serie.get().strip() or "Serie"
        ordner = os.path.join(self._ordner, trdfpruefung.ORDNER)
        name = "".join(zeichen for zeichen in serie
                       if zeichen.isalnum() or zeichen in " _-.") or "Serie"
        pfad = os.path.join(ordner, f"Ergebnisse {name}.csv")
        inhalt = lims_db.csv_bloecke([(
            f"Berechnete Groessen - Serie {serie} - {self.um_kuerzel}",
            kopf, zeilen)])
        try:
            os.makedirs(ordner, exist_ok=True)
            with open(pfad, "wb") as datei:
                datei.write(inhalt)
        except OSError:
            self._melden(f"Die Datei liess sich nicht schreiben. Steht der "
                         f"Ordner \u201e{ordner}\u201c zur Verfuegung?",
                         Style.ERROR)
            return ""
        self._melden(f"{len(zeilen)} Zeilen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)
        return pfad

    def _blatt_speichern(self):
        """Legt das Pruefblatt als CSV ab und oeffnet es."""
        blatt = self.geprueft()
        if not blatt:
            self._pruefmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfpruefung.ORDNER)
        pfad = trdfpruefung.schreiben(ordner, self.v_serie.get().strip(),
                                      blatt, self.um_kuerzel)
        if not pfad:
            self._pruefmelden(
                f"Die Datei liess sich nicht schreiben. Steht der Ordner "
                f"„{ordner}“ zur Verfuegung?", Style.ERROR)
            return
        self._pruefmelden(f"{len(blatt)} Zeilen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)


class Einfuegefenster(tk.Toplevel):
    """Die Liste aus der Probenvorbereitung - in einem eigenen Fenster.

    Gross, damit die Liste ganz zu sehen ist, und ausserhalb der Seite,
    damit sie den Tabellen keinen Platz nimmt. Was hier steht, bleibt
    liegen, wenn das Fenster zugeht, und steht beim naechsten Oeffnen
    wieder da.
    """

    def __init__(self, seite):
        super().__init__(seite)
        self.seite = seite
        serie = seite.v_serie.get().strip()
        self.title("UM einfuegen"
                   + (f" - Serie {serie}" if serie else ""))
        self.configure(bg=Style.BG)
        self.geometry("1200x720")
        self.minsize(600, 300)
        try:
            self.transient(seite.winfo_toplevel())
        except tk.TclError:
            pass
        kopf = tk.Frame(self, bg=Style.BG)
        kopf.pack(fill="x", padx=10, pady=(8, 4))
        self.hinweis = tk.Label(kopf, text=getattr(seite, "quellhinweis", ""),
                                bg=Style.BG, fg=Style.MUTED,
                                font=Style.font(9), anchor="w",
                                justify="left")
        self.hinweis.pack(side="left", fill="x", expand=True)
        # Der Hinweis bricht an der Fensterbreite um, statt abzureissen.
        kopf.bind("<Configure>", lambda e: self.hinweis.config(
            wraplength=max(200, e.width - 10)))
        knoepfe = tk.Frame(self, bg=Style.BG)
        knoepfe.pack(side="bottom", fill="x", padx=10, pady=8)
        RoundedButton(knoepfe, text="Uebernehmen", width=150, height=32,
                      bg="#15803d", command=self._uebernehmen).pack(
            side="left")
        RoundedButton(knoepfe, text="Leeren", width=110, height=32,
                      bg="#6b7268", command=seite._text_leeren).pack(
            side="left", padx=(8, 0))
        RoundedButton(knoepfe, text="Schliessen", width=130, height=32,
                      bg="#334155", command=self._schliessen).pack(
            side="right")
        rahmen = tk.Frame(self, bg=Style.BG)
        rahmen.pack(fill="both", expand=True, padx=10)
        self.textfeld = tk.Text(rahmen, wrap="none", font=("Consolas", 11),
                                bg=Style.CARD, fg=Style.TEXT, undo=True,
                                highlightbackground=Style.BORDER,
                                highlightthickness=1)
        senkrecht = tk.Scrollbar(rahmen, orient="vertical",
                                 command=self.textfeld.yview)
        waagerecht = tk.Scrollbar(rahmen, orient="horizontal",
                                  command=self.textfeld.xview)
        self.textfeld.configure(yscrollcommand=senkrecht.set,
                                xscrollcommand=waagerecht.set)
        self.textfeld.grid(row=0, column=0, sticky="nsew")
        senkrecht.grid(row=0, column=1, sticky="ns")
        waagerecht.grid(row=1, column=0, sticky="we")
        rahmen.grid_rowconfigure(0, weight=1)
        rahmen.grid_columnconfigure(0, weight=1)
        self.textfeld.insert("1.0", getattr(seite, "_einfuegetext", "")
                             .rstrip("\n"))
        self.textfeld.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._schliessen)
        self.bind("<Escape>", lambda e: self._schliessen())

    def _uebernehmen(self):
        """Lesen und rechnen - und bei Erfolg zugehen."""
        if self.seite._text_uebernehmen():
            self._schliessen()

    def _schliessen(self):
        self.seite._einfuegetext = self.textfeld.get("1.0", "end")
        self.destroy()


class Grossansicht(tk.Toplevel):
    """Die Rohwerte in einem eigenen, grossen Fenster.

    Dieselbe Tabelle wie im Reiter, nur mit doppelter Zeilenhoehe und
    fast nichts drumherum: wer eine Serie eintippt, sieht die Zahlen und
    sonst wenig. Sie ist keine Kopie - es ist eine zweite Ansicht
    desselben Standes. Was hier getippt wird, steht im selben Augenblick
    auch im Reiter, und was dort steht, steht auch hier.

    Alles geht wie im Reiter: Tabulator und Pfeile wechseln die Zelle,
    ein aus Excel kopierter Block laeuft von der offenen Zelle nach
    unten und rechts, der Klick auf die Probennummer oeffnet ihren
    Bodenblock - und der liegt ueber diesem Fenster, nicht dahinter.
    """

    def __init__(self, seite):
        super().__init__(seite)
        self.seite = seite
        serie = seite.v_serie.get().strip()
        self.title(f"Rohwerte gross - {serie}" if serie
                   else "Rohwerte gross")
        self.configure(bg=Style.BG)
        self._maximieren()

        leiste = tk.Frame(self, bg=Style.BG)
        leiste.pack(fill="x", padx=10, pady=(8, 6))
        knopf = RoundedButton(leiste, text="Speichern", width=140, height=30,
                              bg="#166534", command=self._schliessen)
        knopf.pack(side="left")
        ToolTip(knopf,
                "Schliesst dieses Fenster. Die Werte stehen dann im\n"
                "Reiter - sie stehen dort ohnehin schon, denn beide\n"
                "Ansichten zeigen denselben Stand. In das LIMS\n"
                "geschrieben wird weiter nur mit dem gruenen Knopf\n"
                "oben im Hauptfenster.")
        Infozeichen(leiste, "Tastenkuerzel\n\n" + TASTEN,
                    dezent=True).pack(side="left", padx=(10, 0))
        self.stand = tk.Label(leiste, text="", bg=Style.BG, fg=Style.MUTED,
                              font=Style.font(9), anchor="w")
        self.stand.pack(side="left", padx=(14, 0))

        self.tabelle = eingaberaster.Eingaberaster(
            self, hoehe=GROSS_ZEILEN, schriftgroesse=GROSS_SCHRIFT,
            zeilenluft=GROSS_LUFT,
            bei_aenderung=seite._von_hand_geaendert,
            bei_klick=self._angeklickt,
            bei_block=seite._block_eingefuegt,
            bei_zeile=seite._arbeitszeile_setzen,
            bei_fuellen=seite.leere_fuellen,
            ist_leer=seite.ist_leer,
            bei_nach_unten=seite._nach_unten_eingefuegt)
        self.tabelle.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        seite.rohansicht_anmelden(self.tabelle)
        # Erst wenn das Fenster seine Masse hat, weiss die Tabelle, wo
        # ihre Zellen liegen - und erst dann findet das Eingabefeld die
        # Zelle, auf die es sich legen soll.
        self.update_idletasks()
        self.stand.config(text=f"{len(seite.proben)} Proben  |  "
                               f"{len(seite.rohliste)} Rohwerte")
        self.protocol("WM_DELETE_WINDOW", self._schliessen)
        self.bind("<Escape>", lambda ereignis: self._schliessen())

    def _maximieren(self):
        """So gross, wie der Bildschirm es hergibt.

        Unter Windows ist das "zoomed"; wo der Fenstermanager das nicht
        kennt, wird der Bildschirm ausgemessen. Beides kann scheitern -
        dann steht das Fenster eben in normaler Groesse da, und das ist
        kein Grund, es gar nicht zu zeigen.
        """
        try:
            self.state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            self.geometry(f"{self.winfo_screenwidth()}x"
                          f"{self.winfo_screenheight()}+0+0")
        except tk.TclError:
            pass

    def _angeklickt(self, zeile, spalte):
        """Der Bodenblock gehoert ueber dieses Fenster."""
        self.seite._block_zeigen(zeile, spalte, ueber=self)

    def _schliessen(self):
        self.seite.rohansicht_abmelden(self.tabelle)
        self.destroy()


class Exportvorschau(tk.Toplevel):
    """Was in das LIMS geschrieben wuerde - Zeile fuer Zeile, alt und neu.

    Der Riegel vor dem einzigen Weg, der einen Messwert ueberschreibt.
    Er zeigt jede betroffene Zeile mit ihrer Pruefmethode, dem Stand im
    LIMS und dem, was an seine Stelle traete. Erst der gruene Knopf
    schreibt - und auch der erst, nachdem der alte Stand gesichert ist.
    """

    def __init__(self, eltern, aenderungen, serie: str, wenn_ja,
                 zurueck=False, nur_anhang=False):
        super().__init__(eltern)
        self.title(("Load backup - " if zurueck
                    else "Teilprobenanhang angleichen - Serie " if nur_anhang
                    else "Export in das LIMS - Serie ") + serie)
        self.configure(bg=Style.BG)
        self.geometry("1180x580")
        self.aenderungen = list(aenderungen)
        self._wenn_ja = wenn_ja

        tk.Label(self, text=f"{len(self.aenderungen)} Werte werden "
                            f"ueberschrieben", bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(12, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(14, 2))
        ohne = trdfexport.ohne_zeile(self.aenderungen)
        wieder = [] if zurueck or nur_anhang else trdfexport.schon_korrigiert(
            self.aenderungen)
        if nur_anhang:
            hinweis = ("Geschrieben wird nur der Teilprobenanhang: er "
                       "bekommt den Wert, der in der Ergebniszeile steht. "
                       "Die Ergebniszeile selbst wird nicht angefasst - sie "
                       "ist hier die Vorlage. „Wert aktuell LIMS“ ist der "
                       "Stand am Anhang, „Wert neu“ der aus der "
                       "Ergebnistabelle. Der bisherige Wert des Anhangs "
                       "geht wie immer nach MW_OLD, und der Stand von jetzt "
                       f"vorher in den Ordner „{trdfexport.ORDNER}“.")
        elif zurueck:
            hinweis = ("Wiederhergestellt wird der ganze Stand von damals: "
                       "MW_ROH und MW, der Bearbeitungsstand, das "
                       "Korrekturkennzeichen und FC8 - und am "
                       "Teilprobenanhang MW und MW_OLD. Eine neue Sicherung "
                       "entsteht dabei nicht: die Datei, die gerade gelesen "
                       "wird, ist sie.")
            allein = trdfexport.ohne_anhang(self.aenderungen)
            if allein:
                hinweis += (
                    f" ACHTUNG: {len(allein)} Rohwerte dieser Sicherung "
                    "tragen keine ROHW_ID - fuer sie wird nur die "
                    "Ergebniszeile zurueckgestellt, waehrend der "
                    "Teilprobenanhang auf dem korrigierten Wert stehen "
                    "bleibt. Danach rechnet das LIMS mit einer anderen "
                    "Zahl als der, die in der Ergebnistabelle steht; die "
                    "Pruefung meldet das als „Rohwert am Anhang weicht "
                    "ab“. Solche Sicherungen stammen aus einer aelteren "
                    "Fassung von LabControl.")
            leer = trdfexport.geleert(self.aenderungen)
            if leer:
                hinweis += (f" Bei {len(leer)} Werten stand vor der "
                            "Korrektur nichts - dort steht danach wieder "
                            f"nichts („{trdf.MARKE}“ in der Spalte "
                            "„Wert neu“).")
        else:
            hinweis = ("In ERGEBNISSE werden MW_ROH und MW mit demselben "
                       f"Wert geschrieben, dazu FC8 = „{lims_db.TRDF_FC8}“, "
                       "der Bearbeitungsstand und das Korrekturkennzeichen. "
                       "Ein Rohwert haengt zusaetzlich am Teilprobenanhang - "
                       "aus ihm rechnet das LIMS -, dort wird MW mitgesetzt "
                       "und der bisherige Wert nach MW_OLD gehoben. Der "
                       "Stand von jetzt geht vorher in den Ordner "
                       f"„{trdfexport.ORDNER}“.")
        mit_x = trdfexport.markiert(self.aenderungen)
        leer = trdfexport.geleert(self.aenderungen)
        if not zurueck and (mit_x or leer):
            teile = []
            if mit_x:
                teile.append(f"{len(mit_x)} Werte bekommen ein „"
                             f"{trdf.MARKE}“ (hier soll nichts stehen)")
            if leer:
                teile.append(f"{len(leer)} Werte werden geleert")
            hinweis += (" " + " und ".join(teile) + " - so, wie es die "
                        "Eingabemaske des LIMS beim Wechsel der Variante "
                        "auch tut.")
        if ohne:
            hinweis += (f" {len(ohne)} Werte haben im LIMS keine "
                        "Ergebniszeile - sie werden gemeldet und nicht "
                        "angelegt.")
        if wieder:
            hinweis += (f" {len(wieder)} Zeilen tragen schon ein "
                        "Korrekturkennzeichen: dort war bereits jemand.")
        tk.Label(self, text=hinweis, bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w", justify="left",
                 wraplength=960).pack(fill="x", padx=16, pady=(0, 10))

        rahmen = tk.Frame(self, bg=Style.CARD,
                          highlightbackground=Style.BORDER,
                          highlightthickness=1)
        rahmen.pack(fill="both", expand=True, padx=16)
        self.baum = ttk.Treeview(rahmen, show="headings",
                                 columns=list(trdfexport.SPALTEN))
        senkrecht = ttk.Scrollbar(rahmen, orient="vertical",
                                  command=self.baum.yview)
        # Zehn Spalten passen nicht in jedes Fenster, und gerade die
        # letzte - der neue Wert - ist die, um die es geht. Ohne Leiste
        # waere sie auf einem kleinen Bildschirm einfach weg.
        waagerecht = ttk.Scrollbar(rahmen, orient="horizontal",
                                   command=self.baum.xview)
        self.baum.configure(yscrollcommand=senkrecht.set,
                            xscrollcommand=waagerecht.set)
        self.baum.grid(row=0, column=0, sticky="nsew")
        senkrecht.grid(row=0, column=1, sticky="ns")
        waagerecht.grid(row=1, column=0, sticky="we")
        rahmen.grid_rowconfigure(0, weight=1)
        rahmen.grid_columnconfigure(0, weight=1)
        breiten = {"Zeile": 56, "Probe-Nr.": 104, "Groesse": 110,
                   "Art": 80, "Pruefmethode": 190, "PM_ID": 70,
                   "PM_VER": 70, "Ziel": 150, "Wert aktuell LIMS": 150,
                   "Wert neu": 150}
        for name in trdfexport.SPALTEN:
            self.baum.heading(name, text=name)
            self.baum.column(name, width=breiten.get(name, 100), minwidth=50,
                             stretch=False)
        self.baum.tag_configure("ohne", background="#fef3c7")
        self.baum.tag_configure("wieder", background="#ede9fe")
        schon = {id(eine) for eine in wieder}
        for nummer, (eine, zeile) in enumerate(
                zip(self.aenderungen,
                    trdfexport.uebersicht(self.aenderungen,
                                          trdfpruefung.stellen_fuer))):
            if not eine.get("zeile"):
                marke = ("ohne",)
            elif id(eine) in schon:
                marke = ("wieder",)
            else:
                marke = ()
            self.baum.insert("", "end", iid=str(nummer), values=zeile,
                             tags=marke)

        knoepfe = tk.Frame(self, bg=Style.BG)
        knoepfe.pack(fill="x", padx=16, pady=12)
        RoundedButton(knoepfe, text="Abbrechen", width=130, height=32,
                      bg="#6b7268", command=self.destroy).pack(side="right")
        self.knopf_ja = RoundedButton(
            knoepfe, text="Zurueckspielen" if zurueck
            else "Sichern und schreiben", width=210, height=32,
            bg="#15803d", command=self._schreiben)
        self.knopf_ja.pack(side="right", padx=(0, 10))
        self.bind("<Escape>", lambda e: self.destroy())

    def _schreiben(self):
        self.destroy()
        self._wenn_ja()


class Bildfenster(tk.Toplevel):
    """Das Streubild einer Serie - ein Klick auf einen Punkt oeffnet ihn."""

    def __init__(self, eltern, serie: str, punkte, bei_klick=None):
        super().__init__(eltern)
        self.title(f"Trockenrohdichte ueber Kohlenstoff - Serie {serie}")
        self.configure(bg=Style.BG)
        self.resizable(False, False)
        self._bei_klick = bei_klick
        tk.Label(self, text=f"Serie {serie}  ·  {len(punkte)} Proben",
                 bg=Style.BG, fg=Style.TEXT, font=Style.font(11, "bold"),
                 anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(self,
                 text="Jede Probe ein Punkt, der Sollbereich ihrer "
                      "Kohlenstoffklasse als Band dahinter: das dunklere "
                      "gilt ohne Carbonat, das hellere mit. Rot liegt "
                      "ausserhalb, violett wurde von Hand bewegt, grau hat "
                      "keinen Aufschluss und steht am linken Rand. Ein "
                      "Klick auf einen Punkt oeffnet seinen Bodenblock.",
                 bg=Style.BG, fg=Style.MUTED, font=Style.font(9), anchor="w",
                 justify="left", wraplength=700).pack(
            fill="x", padx=16, pady=(0, 10))
        self.bild = trdfbild.Streubild(self, bei_klick=self._punkt_geklickt)
        self.bild.pack(padx=16)
        self.stand = tk.Label(self, text="", bg=Style.BG, fg=Style.MUTED,
                              font=Style.font(9), anchor="w")
        self.stand.pack(fill="x", padx=16, pady=(8, 14))
        self.bild.zeichnen(punkte)
        self.bind("<Escape>", lambda e: self.destroy())

    def _punkt_geklickt(self, probe):
        self.stand.config(text=f"Probe {probe}")
        if self._bei_klick is not None:
            self._bei_klick(probe, "Probe-Nr.")
