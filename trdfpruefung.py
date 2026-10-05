"""
TRDF-Pruefmodul - die Plausibilitaetspruefung der TRDF-Serien
=============================================================

Die Rechnung nachzurechnen (trdf.py) sagt, ob das LIMS richtig gerechnet
hat. Sie sagt nicht, ob die Zahlen stimmen koennen: eine Trockenrohdichte
von 2,4 g/cm^3 ist sauber gerechnet und trotzdem falsch gemessen. Diese
Datei traegt die Sollbereiche, an denen so etwas auffaellt.

Woran gemessen wird
-------------------
Der Sollbereich der Trockenrohdichte haengt am Kohlenstoff: je mehr
organische Substanz, desto leichter der Boden. Deshalb gibt es nicht eine
Grenze, sondern fuenf Klassen nach Cges - und in jeder noch einmal zwei
Faelle, je nachdem, ob Karbonat gefunden wurde (CO3). Karbonat ist
schwer; wo es vorkommt, darf der Boden dichter sein.

Dazu kommen drei Pruefungen, die ohne Aufschluss auskommen:

* Der Skelettanteil liegt zwischen 0 und 100 Prozent - und er kann nicht
  wesentlich unter dem Grobbodenanteil liegen, der geschaetzt wurde.
* Gemessener und geschaetzter Skelettanteil duerfen nicht weit
  auseinandergehen; tun sie es, hilft die Fotoauswertung weiter.
* Der Feinbodenvorrat ist kein negativer Wert.

Was hier *nicht* passiert
-------------------------
Hier wird nichts verworfen und nichts geschrieben. Eine fehlgeschlagene
Pruefung ist ein Satz in der Spalte "Bewertung", mehr nicht - die
Entscheidung trifft das Labor. Was daraus folgt, geht einen eigenen Weg
(trdfexport.py) und nur ueber eine bestaetigte Uebersicht.
"""

from __future__ import annotations

import decimal
import os
import re

import druck
import lims_db
import trdf
from trdf import D

# Die Formelkuerzel, mit denen die Pruefung rechnet. Sie stehen im LIMS
# in PRUEFMETHODEN.FORMELKUERZEL beziehungsweise an den Rohwerten; hier
# stehen sie noch einmal, weil die Pruefung sie einzeln ansprechen muss.
TRDF = "TRD_TRDF"            # Trockenrohdichte Feinboden, g/cm^3
TRDF_ALT = "TRDF_Old"        # dieselbe, nach der bisherigen Formel
VARIANTE = "_TRDV"           # welche Variante gemessen wurde
SKA = "_SKA"                 # Skelettanteil, Prozent
SKA_GEMESSEN = "_SKAS"       # aus den gewogenen Steinen
SKA_GESCHAETZT = "_SKASgs"   # aus dem geschaetzten Grobbodenanteil
VORRAT = "FBVb"              # Feinbodenvorrat
GBFANT = "GBFAnt"            # geschaetzter Grobbodenanteil, Prozent
FAKTOR = "FBLFL"             # Faktor Bergland/Flachland
CGES = "Cges"                # aus der Methode ATNULL
CO3 = "CO3"                  # aus der Methode ATNULLCO3

# Die Sollbereiche der Trockenrohdichte, nach Cges (g/kg) gestaffelt.
# Je Klasse die obere Schranke des Kohlenstoffgehalts und dann zweimal
# (unten, oben): ohne Karbonat und mit. Die letzte Klasse ist offen.
KLASSEN = (
    (D(2),   (D("1"),   D("2")),   (D("1"),   D("2"))),
    (D(10),  (D("0.9"), D("1.8")), (D("0.9"), D("2"))),
    (D(40),  (D("0.6"), D("1.7")), (D("0.6"), D("1.9"))),
    (D(100), (D("0.4"), D("1.3")), (D("0.6"), D("1.9"))),
    (None,   (D("0.3"), D("0.8")), (D("0.5"), D("1.8"))),
)

# Steht kein Kohlenstoff zur Verfuegung, bleibt nur der weiteste
# Bereich: er schlaegt nur bei Werten an, die in keinem Boden vorkommen.
OHNE_AUFSCHLUSS = (D("0.5"), D(2))

# Der Skelettanteil darf den geschaetzten Grobbodenanteil um diese
# Spanne unterschreiten - die Schaetzung ist eine Schaetzung.
SKA_SPANNE = D(10)

# So weit duerfen gemessener und geschaetzter Skelettanteil
# auseinanderliegen (Prozentpunkte).
DIFFERENZ = D(20)

# Die Saetze, die in der Bewertung stehen.
SKA_ZU_HOCH = "SKA > 100"
SKA_NEGATIV = "SKA < 0"
SKA_ZU_GERING = "SKA zu gering"
DIFFERENZ_ZU_GROSS = ("ggf. Differenz zu groß "
                      "(hier ist ggf. Fotoauswertung nötig)")
VORRAT_NEGATIV = "FBVorratTRDF3.2 < 0"
TRDF_ZU_GERING = "TRDF zu gering"
TRDF_ZU_HOCH = "TRDF zu hoch"
SCHAETZUNG = "Schätzung TRDF erfolgt"

# Die Variante, die die Schaetzung von sich aus nimmt: bei ihr ist die
# Trockenrohdichte die geschaetzte, und dass beide Formeln dasselbe
# sagen, ist der Normalfall und kein Befund.
SCHAETZVARIANTE = D(7)

TRENNER = ", "

# Welchen Wert eine fehlgeschlagene Pruefung meint. Damit faerbt das
# Blatt nicht nur die Bewertung, sondern die Zelle, um die es geht -
# bei zwoelf Spalten ist das der Unterschied zwischen "hier stimmt
# etwas nicht" und "dieser Wert stimmt nicht".
#
# Genannt wird, worueber die Pruefung urteilt, nicht, was sie als
# Massstab nimmt: dass die Trockenrohdichte zu hoch ist, sagt etwas
# ueber sie und nicht ueber den Kohlenstoff, an dem ihre Grenze haengt.
BETROFFEN = {
    SCHAETZUNG: (TRDF,),
    SKA_ZU_HOCH: (SKA,),
    SKA_NEGATIV: (SKA,),
    SKA_ZU_GERING: (SKA,),
    DIFFERENZ_ZU_GROSS: (SKA_GEMESSEN, SKA_GESCHAETZT),
    VORRAT_NEGATIV: (VORRAT,),
    TRDF_ZU_GERING: (TRDF,),
    TRDF_ZU_HOCH: (TRDF,),
}


def betroffen(saetze, weitere=None) -> set:
    """Die Formelkuerzel, um die es in diesen Saetzen geht.

    `weitere` nimmt die Zuordnung anderer Pruefungen dazu - der
    Serienblick etwa urteilt ueber Groessen, die dieses Modul nicht
    kennt.
    """
    zuordnung = dict(BETROFFEN)
    zuordnung.update(weitere or {})
    gefunden = set()
    for satz in saetze:
        gefunden.update(zuordnung.get(satz, ()))
    return gefunden


# --------------------------------------------------------------------------
# Die einzelnen Pruefungen
# --------------------------------------------------------------------------
def karbonathaltig(co3) -> bool:
    """Traegt diese Probe Karbonat?

    Nur ein gemessener Gehalt ueber null. Eine gemessene Null heisst,
    dass keines da ist - und ein Wert darunter heisst dasselbe: so
    streut eine Messung um die Null. Beides ist eine Aussage ueber die
    Probe und darf ihr nicht den weiteren Sollbereich der karbonat-
    haltigen Boeden geben.
    """
    return co3 is not None and co3 > 0


def grenzen(cges, co3) -> tuple:
    """Der Sollbereich der Trockenrohdichte fuer diese Probe.

    `cges` und `co3` sind Zahlen oder None. Ohne Kohlenstoff gibt es
    keine Klasse - dann bleibt der weite Bereich, der nur das Unmoegliche
    abfaengt. Die Klassengrenzen sind unten offen und oben geschlossen:
    genau 2 g/kg gehoert zur zweiten Klasse.
    """
    if cges is None:
        return OHNE_AUFSCHLUSS
    for schranke, ohne, mit in KLASSEN:
        if schranke is None or cges < schranke:
            return mit if karbonathaltig(co3) else ohne
    return OHNE_AUFSCHLUSS


def schaetzung_bewerten(wert, alt=None, variante=None) -> list:
    """Ist die Trockenrohdichte geschaetzt statt gerechnet?

    Seit dem 1. September 2026 nimmt die Formel des LIMS eine gemessene
    Schaetzung vorweg, wenn eine dasteht - unabhaengig von der Variante.
    Die zweite Methode (TRDF_Old) rechnet weiter nach der bisherigen
    Formel; gehen die beiden auseinander, wurde geschaetzt.

    Bei Variante 7 ist das der vorgesehene Weg und kein Befund. Fuehrt
    eine Serie die zweite Methode nicht, gibt es nichts zu vergleichen -
    dann steht `alt` nicht im Satz, und es bleibt still.
    """
    if variante is not None and variante == SCHAETZVARIANTE:
        return []
    if wert is None and alt is None:
        return []
    if wert is not None and alt is not None and wert == alt:
        return []
    return [SCHAETZUNG]


def trdf_bewerten(wert, cges=None, co3=None) -> list:
    """Liegt die Trockenrohdichte im Sollbereich ihrer Klasse?"""
    if wert is None:
        return []
    unten, oben = grenzen(cges, co3)
    if wert < unten:
        return [TRDF_ZU_GERING]
    if wert > oben:
        return [TRDF_ZU_HOCH]
    return []


def ska_untergrenze(gbfant, faktor):
    """Wie klein der Skelettanteil hoechstens sein darf - oder None.

    Der Grobbodenanteil wurde im Gelaende geschaetzt und mit dem Faktor
    Bergland/Flachland auf den Volumenanteil gebracht; das ist der Teil
    des Skeletts, den man gesehen hat. Faellt der gerechnete
    Skelettanteil deutlich darunter, passt eines von beiden nicht.
    """
    if gbfant is None or faktor is None:
        return None
    return gbfant * faktor - SKA_SPANNE


def ska_bewerten(wert, gbfant=None, faktor=None) -> list:
    """Der Skelettanteil - Bereich und Vergleich mit der Schaetzung."""
    if wert is None:
        return []
    saetze = []
    if wert > D(100):
        saetze.append(SKA_ZU_HOCH)
    if wert < D(0):
        saetze.append(SKA_NEGATIV)
    untergrenze = ska_untergrenze(gbfant, faktor)
    if untergrenze is not None and wert < untergrenze:
        saetze.append(SKA_ZU_GERING)
    return saetze


def differenz_bewerten(gemessen, geschaetzt) -> list:
    """Gehen gemessener und geschaetzter Skelettanteil auseinander?"""
    if gemessen is None or geschaetzt is None:
        return []
    if abs(gemessen - geschaetzt) > DIFFERENZ:
        return [DIFFERENZ_ZU_GROSS]
    return []


def vorrat_bewerten(wert) -> list:
    """Ein Feinbodenvorrat unter null ist keine Menge."""
    if wert is None or wert >= D(0):
        return []
    return [VORRAT_NEGATIV]


def bewerten(werte: dict) -> list:
    """Alle Pruefungen einer Probe - in der Reihenfolge des Blattes.

    `werte` ist auf die Formelkuerzel geschluesselt und traegt Zahlen
    oder None; was fehlt, wird nicht geprueft und nicht bemaengelt.
    """
    hole = werte.get
    # Die Schaetzung wird nur geprueft, wo die Serie die zweite Methode
    # ueberhaupt fuehrt - sonst gibt es nichts zu vergleichen.
    geschaetzt = (schaetzung_bewerten(hole(TRDF), hole(TRDF_ALT),
                                      hole(VARIANTE))
                  if TRDF_ALT in werte else [])
    return (ska_bewerten(hole(SKA), hole(GBFANT), hole(FAKTOR))
            + differenz_bewerten(hole(SKA_GEMESSEN), hole(SKA_GESCHAETZT))
            + vorrat_bewerten(hole(VORRAT))
            + trdf_bewerten(hole(TRDF), hole(CGES), hole(CO3))
            + geschaetzt)


def bewertungstext(saetze) -> str:
    """Die Bewertung, wie sie in der Zelle steht."""
    return TRENNER.join(saetze)


# --------------------------------------------------------------------------
# Das Arbeitsblatt
# --------------------------------------------------------------------------
# Die Spalten in der Reihenfolge, in der sie gelesen werden: erst die
# Probe, dann die drei Skelettanteile mit dem, woraus sie kommen, dann
# der Vorrat und die Dichte, zuletzt der Aufschluss und das Urteil.
SPALTEN = ("Zeile", "Probe-Nr.", "Skelettanteil", "SKA63", "SKAgs63",
           "Faktor B/F", "GBFAnt63gs", "FBVorrat", "TRDF", "Cges", "CO3",
           "Bewertung")

# Welche Spalte welches Formelkuerzel zeigt. Was hier nicht steht -
# Zeile, Probe und die Bewertung - wird nicht gerechnet.
QUELLEN = {"Skelettanteil": SKA, "SKA63": SKA_GEMESSEN,
           "SKAgs63": SKA_GESCHAETZT, "Faktor B/F": FAKTOR,
           "GBFAnt63gs": GBFANT, "FBVorrat": VORRAT, "TRDF": TRDF,
           "Cges": CGES, "CO3": CO3}

# Die Spalten, in denen eine Zahl steht - sie werden gerundet und
# rechtsbuendig gezeigt.
ZAHLENSPALTEN = tuple(QUELLEN)

# Neben den Kenndaten ein eigener Ordner: hier liegt kein Messwert,
# sondern das Urteil ueber ihn.
ORDNER = "TRDF-Pruefung"

# Wie viele Nachkommastellen im Blatt stehen. Mehr sagt nichts: die
# Dichte wird auf zwei Stellen gemessen, der Vorrat auf ganze Gramm.
STELLEN = 3

# Groessen, bei denen schon die erste Nachkommastelle mehr ist als die
# Messung hergibt: Massen und Vorraete gehen in die Tausende, Anteile
# sind Prozent. Ein Feinbodenvorrat mit drei Stellen behauptet ein
# Milligramm je Hektar, ein Grobbodenanteil mit drei ein Promille
# eines im Gelaende geschaetzten Wertes.
GROB = ("FBM", "FBV", "SKA", "VOL", "GBFANT")
STELLEN_GROB = 1


def stellen_fuer(kuerzel, vorgabe: int = STELLEN) -> int:
    """Wie viele Nachkommastellen diese Groesse traegt."""
    name = str(kuerzel or "").lstrip("_").upper()
    return STELLEN_GROB if name.startswith(GROB) else vorgabe

BLOCK = "Pruefung der bodenphysikalischen Parameter"


def gerundet(wert, stellen: int = STELLEN) -> str:
    """Eine Zahl fuer das Blatt - mit Komma, ohne Exponent."""
    if wert is None:
        return trdf.MARKE
    if not isinstance(wert, D):
        return str(wert)
    try:
        fest = wert.quantize(D(1).scaleb(-stellen), rounding=decimal.ROUND_HALF_UP)
    except decimal.InvalidOperation:
        return str(wert)
    return str(fest).replace(".", ",")


def zeile(probe: dict) -> list:
    """Eine Zeile des Blattes aus einer geprueften Probe.

    `probe` traegt "lnr", "probe", die Zahlen unter ihren Formelkuerzeln
    und die Bewertung.
    """
    werte = probe.get("werte", {})
    zeilen = [probe.get("lnr", ""), probe.get("probe", "")]
    for name in SPALTEN[2:-1]:
        kuerzel = QUELLEN[name]
        zeilen.append(gerundet(werte.get(kuerzel), stellen_fuer(kuerzel)))
    zeilen.append(bewertungstext(probe.get("bewertung", ())))
    return zeilen


def blatt(proben, serie: str = "") -> list:
    """Das ganze Blatt als Block fuer die CSV."""
    titel = f"{BLOCK} - Serie {serie}" if serie else BLOCK
    return [(titel, list(SPALTEN), [zeile(probe) for probe in proben])]


def dateiname(serie: str, methode: str = "") -> str:
    """Serie und Methode im Namen - so liegt je Lauf eine Datei da."""
    teile = [str(serie or "Serie").strip(), str(methode or "").strip()]
    name = " ".join(teil for teil in teile if teil)
    return re.sub(r"[^A-Za-z0-9 _.-]", "", f"Pruefung {name}").strip() + ".csv"


def schreiben(ordner: str, serie: str, proben, methode: str = "") -> str:
    """Legt das Blatt als CSV ab und gibt den Pfad - "" wenn es nicht ging."""
    ziel = os.path.join(ordner, dateiname(serie, methode))
    inhalt = lims_db.csv_bloecke(blatt(proben, serie))
    try:
        os.makedirs(ordner, exist_ok=True)
        with open(ziel, "wb") as datei:
            datei.write(inhalt)
    except OSError:
        return ""
    return ziel


def oeffnen(pfad: str) -> str:
    """Uebergibt das Blatt dem Programm, das CSV oeffnet - meist Excel.

    Dort wird weitergearbeitet: sortiert, kommentiert, gedruckt. Zurueck
    kommt, was geschehen ist, fuer die Meldung im Fenster.
    """
    return druck.drucken(pfad)
