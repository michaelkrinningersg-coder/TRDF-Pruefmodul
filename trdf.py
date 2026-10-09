"""
TRDF-Pruefmodul - die Pruefung der TRDF-Rechnung
================================================

Das LIMS rechnet aus den Rohwerten einer TRDF-Serie ein Dutzend Groessen
aus - wie viele es genau sind, sagt die Serie selbst:
Feinbodenmasse, Trockenrohdichte, Skelettanteil, Feinbodenvorrat. Hier
wird dasselbe noch einmal gerechnet - aus denselben Formeln, aber
unabhaengig - und danebengestellt. Wo beides auseinandergeht, ist etwas
zu klaeren.

Woher die Zahlen kommen
-----------------------
Drei Quellen, und sie gehoeren nebeneinander:

  * der **eingefuegte Text** aus der Probenvorbereitung - was gemessen
    und eingetragen wurde,
  * die **Rohwerte im LIMS** - was davon gebucht ankam,
  * die **berechneten Groessen im LIMS** - was das LIMS daraus gemacht
    hat.

Dass die ersten beiden auseinandergehen koennen, ist keine Theorie: in
der Serie, an der das hier entwickelt wurde, trugen 47 Zeilen im Text
einen Faktor Bergland/Flachland, den das LIMS nicht gebucht hat.

Kein Wert ist kein Wert
-----------------------
Fehlt ein Rohwert, wird nicht mit null gerechnet, sondern das Ergebnis
ist "nicht anwendbar". Das LIMS haelt sich daran nicht immer - in einer
gepruefte Zeile behandelte es denselben fehlenden Wert einmal als 0 und
einmal als fehlend. Genau solche Faelle soll die Pruefung zeigen, und
das kann sie nur, wenn sie selbst die strengere Regel anwendet.

Jedes "x" ist ein x
-------------------
Gross, klein, und auch die Textbrocken, die das LIMS gelegentlich in
MW_ROH hinterlaesst ("##1093"): alles heisst "kein Wert".
"""

from __future__ import annotations

import decimal
import re

import trdfformel

D = decimal.Decimal
MARKE = trdfformel.MARKE

# Die Untersuchungsmethoden, um die es geht - erkannt am Kuerzel.
METHODENMARKE = "TRDF"

# Die Pruefmethode, die den Wiederfindungsgrad traegt. Sie steht so auch
# in den Formeln des LIMS ("... where prob_id = :v_prob and pm_id =(701)").
WGH_PM_ID = 701
# Unter diesem Namen erwarten die Formeln ihn.
WGH_NAME = "v_wgh"

# Die Untersuchungsmethode mit dem Aufschluss und die beiden Parameter,
# die von dort danebengestellt werden.
ATNULL_MARKE = "ATNULL"
ATNULL_PARAMETER = {31: "Cges", 33: "CO3"}

# Woran ein leerer Wert zu erkennen ist. Das LIMS schreibt "x", "X" und
# gelegentlich einen Verweis wie "##1093" in MW_ROH.
_VERWEIS = re.compile(r"^\s*#")


def leer(wert) -> bool:
    """Steht hier kein Wert?"""
    if wert is None:
        return True
    text = str(wert).strip()
    return (not text) or text.lower() == MARKE or bool(_VERWEIS.match(text))


def marke_klein(wert):
    """Ein x ist ein x - gross oder klein. Geschrieben wird es klein.

    Das LIMS kennt beide Schreibweisen fuer "hier soll nichts stehen";
    verglichen werden sie immer gleich, und was das Pruefmodul selbst
    hinschreibt, ist das kleine x.
    """
    if wert is None:
        return wert
    text = str(wert).strip()
    return MARKE if text.lower() == MARKE else text


def ist_grosses_x(wert) -> bool:
    """Steht hier ein grosses X - eines, das beim Angleichen klein wird?"""
    return str(wert if wert is not None else "").strip() == MARKE.upper()


def zahl(wert):
    """Die Zahl hinter einem Feld - None, wo keine steht.

    Dezimalkomma und Tausenderpunkt kommen aus der Probenvorbereitung so
    herein, wie Excel sie schreibt.
    """
    if isinstance(wert, D):
        return wert
    if leer(wert):
        return None
    text = str(wert).strip().replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return D(text)
    except decimal.InvalidOperation:
        return None


def probenschluessel(nummer) -> str:
    """Die Probennummer ohne Leerzeichen und Bindestrich.

    Im eingefuegten Text steht "2023B - 01944", im LIMS "2023B01944".
    """
    return re.sub(r"[\s-]+", "", str(nummer or "")).upper()


# --------------------------------------------------------------------------
# Der eingefuegte Text
# --------------------------------------------------------------------------
#
# Zeile 1  Serie <Tab> 2026B051
# Zeile 2  Untersuchungsmethode <Tab> TRDF3.2
# Zeile 3  Sortiernummern
# Zeile 4  Spaltenkoepfe: LNR, Text, Probenummer, UM, Me, Faktor, dann die
#          Rohwertparameter
# Zeile 5  Einheiten
# ab 6     die Daten

VORSPANN = ("lnr", "text", "probenummer", "um", "me", "faktor")


class Einfuegefehler(ValueError):
    """Der Text sieht nicht aus wie eine Probenvorbereitungsliste."""


def text_lesen(inhalt: str) -> dict:
    """Zerlegt den eingefuegten Block.

    Zurueck kommt {"serie", "methode", "spalten", "zeilen"}. `zeilen` ist
    eine Liste von {"lnr", "probe", "wdh_um", "wdh_me", "werte"}, und
    `werte` ist auf die Spaltennamen geschluesselt - die Uebersetzung in
    Formelkuerzel macht der Aufrufer, denn sie steht im LIMS.
    """
    roh = [z.split("\t") for z in str(inhalt or "").splitlines()]
    if len(roh) < 6:
        raise Einfuegefehler(
            "Der Text hat weniger als sechs Zeilen. Erwartet werden Serie, "
            "Untersuchungsmethode, Sortiernummern, Spaltenkoepfe, Einheiten "
            "und darunter die Proben.")
    serie = _hinter(roh[0], "serie")
    methode = _hinter(roh[1], "untersuchungsmethode")
    kopf = [feld.strip() for feld in roh[3]]
    if len(kopf) <= len(VORSPANN) or \
            [t.strip().lower() for t in kopf[:len(VORSPANN)]] != list(VORSPANN):
        raise Einfuegefehler(
            f"Die vierte Zeile traegt nicht die erwarteten Spaltenkoepfe "
            f"({', '.join(VORSPANN)} und dann die Rohwerte).")
    spalten = kopf[len(VORSPANN):]
    zeilen = []
    for felder in roh[5:]:
        if not felder or not felder[0].strip().isdigit():
            continue
        werte = {}
        for stelle, name in enumerate(spalten):
            platz = len(VORSPANN) + stelle
            werte[name] = felder[platz].strip() if platz < len(felder) else ""
        zeilen.append({
            "lnr": int(felder[0].strip()),
            "probe": probenschluessel(felder[2] if len(felder) > 2 else ""),
            "wdh_um": _ganz(felder[3] if len(felder) > 3 else "1"),
            "wdh_me": _ganz(felder[4] if len(felder) > 4 else "1"),
            "werte": werte})
    if not zeilen:
        raise Einfuegefehler("Unter den Spaltenkoepfen steht keine Probe.")
    return {"serie": serie, "methode": methode,
            "spalten": spalten, "zeilen": zeilen}


def _hinter(felder, beschriftung: str) -> str:
    """Der Wert hinter einer Kopfzeile - "" wenn sie nicht passt."""
    if len(felder) < 2 or felder[0].strip().lower() != beschriftung:
        return ""
    return felder[1].strip()


def _ganz(wert, vorgabe=1) -> int:
    try:
        return int(str(wert).strip())
    except (TypeError, ValueError):
        return vorgabe


def ohne_wiederholungen(zeilen):
    """Nur die Erstmessungen - Wiederholungen bleiben aussen vor."""
    return [z for z in zeilen if z["wdh_um"] == 1 and z["wdh_me"] == 1]


# --------------------------------------------------------------------------
# Die Rechnung
# --------------------------------------------------------------------------

_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def abhaengigkeiten(formel: str, bekannt) -> set:
    """Welche Formelkuerzel eine Formel benutzt."""
    return {name for name in _NAME.findall(str(formel or "")) if name in bekannt}


def reihenfolge(formeln: dict) -> list:
    """In welcher Folge die berechneten Groessen zu rechnen sind.

    Eine Groesse steht auf anderen: der Feinbodenvorrat braucht die
    Trockenrohdichte, die den Feinbodenanteil, der den Wiederfindungsgrad.
    Gerechnet wird deshalb topologisch sortiert - und nicht in der
    Reihenfolge, in der die Pruefmethoden zufaellig stehen.

    Bleibt ein Rest, der sich nicht aufloesen laesst - ein Kreis -, kommt
    er hinten an. Er rechnet dann mit dem, was da ist; falsch waere es,
    ihn stillschweigend wegzulassen.
    """
    offen = dict(formeln)
    fertig, folge = set(), []
    while offen:
        frei = [name for name, formel in offen.items()
                if not (abhaengigkeiten(formel, set(offen)) - {name})]
        if not frei:
            folge.extend(sorted(offen))
            break
        for name in sorted(frei):
            folge.append(name)
            fertig.add(name)
            del offen[name]
    return folge


def rechnen(rohwerte: dict, formeln: dict, wgh=None, folge=None) -> dict:
    """Die berechneten Groessen zu einer Probe.

    `rohwerte` ist auf Formelkuerzel geschluesselt und traegt Zahlen;
    was fehlt, fehlt. `formeln` ist {Formelkuerzel: Formeltext} der
    berechneten Groessen. `wgh` ist der Wiederfindungsgrad, den die
    Formeln sonst selbst per SQL holen.
    """
    umgebung = {name: wert for name, wert in rohwerte.items()
                if wert is not None}
    abfrage = {WGH_NAME: wgh if wgh is not None else D(0)}
    ergebnis = {}
    for name in (folge if folge is not None else reihenfolge(formeln)):
        wert = trdfformel.rechnen(formeln[name], umgebung, name, abfrage)
        umgebung[name] = wert
        ergebnis[name] = wert
    return ergebnis


def wgh_faktor(wert):
    """Der Faktor, mit dem der Wiederfindungsgrad eingeht: 1 + MW/100.

    Ohne gebuchten Wiederfindungsgrad gilt die Eins - dann ist nichts
    umzurechnen.
    """
    gefunden = zahl(wert)
    return D(1) if gefunden is None else D(1) + gefunden / D(100)


# --------------------------------------------------------------------------
# Der Vergleich
# --------------------------------------------------------------------------

# Bis hierher gelten zwei Zahlen als gleich. Gerechnet wird mit
# achtundzwanzig Stellen, das LIMS speichert fuenfzehn - ein Vergleich
# auf Gleichheit faende dort Abweichungen, wo keine sind.
GENAUIGKEIT = D("1e-9")


def gleich(meins, lims) -> bool:
    """Sind der gerechnete und der gebuchte Wert derselbe?

    Zwei fehlende Werte sind gleich; ein fehlender und eine Zahl nicht.
    """
    soll = zahl(lims)
    if not isinstance(meins, D):
        return soll is None
    if soll is None:
        return False
    return abs(meins - soll) <= abs(soll) * GENAUIGKEIT + GENAUIGKEIT


# Was eine Zelle ist. Die Marke steht in der Anzeige und sagt, woher der
# Wert kommt - darum ging es bei der ganzen Pruefung.
ROHWERT = "roh"
BERECHNET = "ber"
GEBUCHT = "lims"
VON_HAND = "hand"
WGH = "wgh"
AUFSCHLUSS = "atnull"


# --------------------------------------------------------------------------
# Zwei Namen fuer denselben Rohwert
# --------------------------------------------------------------------------
# Das LIMS fuehrt jeden Rohwert unter zwei Kuerzeln, und beide heissen
# "Formelkuerzel":
#
#   * am Rohwertparameter (ROHWERTPARAMETER, UM_ROHWERTE und damit auch
#     TEILPROBEN_ANHANG) steht ein kurzes - "D", "C", "FBF";
#   * an der Pruefmethode (PRUEFMETHODEN.FORMELKUERZEL) steht das, mit
#     dem die Formeln rechnen - "DichteGB", "_TRDV", "FBLFL".
#
# Wer die beiden nicht zusammenbringt, hat den Teilprobenanhang und die
# eingefuegte Liste voller Werte, die zu keiner Groesse gehoeren - und
# merkt es nicht, weil beides fuer sich betrachtet in Ordnung aussieht.
#
# Zusammengebracht wird ueber die Namen: der Rohwertparameter heisst
# "DichteGrobboden", und so heisst auch die Pruefmethode oder ihr
# Parameter. Verglichen wird ohne Rueck­sicht auf Gross- und
# Kleinschreibung, Leerzeichen und Zeichensetzung - "Skelettanteil
# (Fotoauswertung)" und "SkelettanteilFotoauswertung" sind dasselbe.
#
# Bleibt danach etwas uebrig, greift die Liste des Labors weiter unten.
# Sie steht hier, weil ohne sie nichts ginge; sie ist die letzte
# Auskunft und nicht die erste.

_UNWICHTIG = re.compile(r"[^0-9a-z]+")


def _schluessel(text) -> str:
    """Ein Name, wie er sich vergleichen laesst."""
    return _UNWICHTIG.sub("", str(text or "").strip().lower())


# Die Zuordnung, wie sie im Labor der NW-FVA gilt: das kurze Kuerzel des
# Rohwertparameters auf den Namen, unter dem die Formeln ihn kennen.
ZUORDNUNG = {
    "D": "DichteGB",            # DichteGrobboden
    "FBF": "FBLFL",             # Faktor Bergland Flachland
    "Y": "GMSZ",                # GesamtmasseStechzylinderprobe
    "U": "GBFAnt",              # GrobbodenFlaechenanteil > 63 mm
    "K": "GBMSchaufel",         # GrobbodenmasseSchaufel 2 - 6,3 mm
    "Z": "GBM263Schaufel",      # GrobbodenmasseSchaufel 2 - 63 mm
    "O": "GBM63Schaufel",       # GrobbodenmasseSchaufel > 63 mm
    "G": "GBMSZ",               # GrobbodenmasseStechzylinder
    "S": "MSchaufel",           # MasseSchaufelprobe
    "A": "MMini",               # MasseStechkappenprobe + Stechkappe
    "FS": "SKAFoto",            # Skelettanteil (Fotoauswertung)
    "M": "_TSM",                # Tiefenstufenmaechtigkeit
    "J": "TRDFgesch",           # TrockenraumdichteFeinboden geschaetzt
    "C": "_TRDV",               # Variante
    "N": "VOLMiniSZ",           # VolumenStechkappen
    "I": "VOLSZ",               # VolumenStechzylinder
}


def zuordnen(rohwerte, methoden, rohliste=()) -> dict:
    """Kuerzel des Rohwertparameters auf Kuerzel der Pruefmethode.

    `rohwerte` sind die Zeilen aus UM_ROHWERTE/ROHWERTPARAMETER (mit
    "formelkuerzel", "name" und "kuerzel"), `methoden` die Pruefmethoden
    der Serie (mit "formelkuerzel", "name", "kurzname", "parameter"),
    `rohliste` die Kuerzel, um die es geht - die Groessen ohne Formel.

    Gesucht wird in dieser Reihenfolge: dasselbe Kuerzel, derselbe Name,
    dasselbe Kurzzeichen, und zuletzt die Liste des Labors. Was sich
    nirgends findet, bleibt draussen und faellt damit auf.
    """
    ziele = {kuerzel for kuerzel in rohliste} or {
        m.get("formelkuerzel") for m in methoden if m.get("formelkuerzel")}
    nach_namen = {}
    for methode in methoden:
        kuerzel = methode.get("formelkuerzel")
        if not kuerzel or kuerzel not in ziele:
            continue
        for feld in ("name", "kurzname", "parameter"):
            name = _schluessel(methode.get(feld))
            if name:
                nach_namen.setdefault(name, kuerzel)
    gefunden = {}
    for eintrag in rohwerte:
        kurz = str(eintrag.get("formelkuerzel") or "").strip()
        if not kurz:
            continue
        if kurz in ziele:
            gefunden[kurz] = kurz            # beide Namen sind derselbe
            continue
        for feld in ("name", "kuerzel"):
            ziel = nach_namen.get(_schluessel(eintrag.get(feld)))
            if ziel:
                gefunden[kurz] = ziel
                break
        else:
            ziel = ZUORDNUNG.get(kurz.upper())
            if ziel in ziele or (ziel and not ziele):
                gefunden[kurz] = ziel
    return gefunden
