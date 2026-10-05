"""
TRDF-Pruefmodul - die Pruefung der TRDF-Rohwerte
================================================

Die Pruefung der Ergebnisse (trdfpruefung.py) fragt, ob das Ergebnis in
einem Boden vorkommen kann. Diese hier fragt, was davor kommt: ob die
Zahlen, aus denen es gerechnet wurde, ueberhaupt zueinander passen.

Warum das die wichtigere Haelfte ist
------------------------------------
Ein fehlender Rohwert macht keinen falschen Wert, sondern gar keinen -
das LIMS schreibt dann "##1093" in jede Groesse, die daran haengt. In
der Serie 2026B051 erklaert allein das zwei der drei Faelle, in denen
LabControl und LIMS auseinandergehen: LNR 92 ist Variante 7 ohne
geschaetzte Trockenrohdichte, LNR 269 ist Variante 4 ohne die
Grobbodenmasse 2-63 mm der Schaufelprobe. Beides steht als "x" in der
Spalte, und beides faellt beim Durchsehen nicht auf, weil dort so viele
x stehen - in jeder Variante bleibt der groessere Teil der Spalten leer.

Drei Fragen, in dieser Reihenfolge
----------------------------------
1. *Ist alles da?* Aus den Formeln des LIMS laesst sich ablesen, welche
   Rohwerte eine Variante braucht. Fehlt einer, wird nichts gerechnet;
   steht einer da, den die Variante nie benutzt, ist meist die Variante
   falsch.
2. *Sind die Zahlen moeglich?* Eine Gesteinsdichte von 26 g/cm^3, ein
   Anteil von 120 Prozent, eine negative Masse.
3. *Passen sie zueinander?* Ein Grobboden, der schwerer ist als die
   ganze Probe. Ein Stechzylinder, dessen Steine mehr Raum einnehmen als
   er selbst - dann wird der Feinbodenraum negativ und die
   Trockenrohdichte ein Fantasiewert. Eine Feuchtdichte von 5 g/cm^3,
   die von einem verrutschten Komma erzaehlt.

Wie hier nicht geprueft wird
----------------------------
Nichts davon verwirft einen Wert. Jede fehlgeschlagene Pruefung ist ein
Satz in der Spalte "Bewertung" der Rohwerttabelle, mit Komma getrennt
wie im Pruefblatt. Was daraus folgt, entscheidet das Labor.
"""

from __future__ import annotations

import decimal
import os

import lims_db
import trdf
from trdf import D

# --------------------------------------------------------------------------
# Die Rohwerte, mit denen gerechnet wird
# --------------------------------------------------------------------------
VARIANTE = "_TRDV"
TIEFENSTUFE = "_TSM"
FAKTOR = "FBLFL"
VOL_SZ = "VOLSZ"
MASSE_SZ = "GMSZ"
GROBBODEN_SZ = "GBMSZ"
MASSE_SCHAUFEL = "MSchaufel"
GROBBODEN_63 = "GBM63Schaufel"
GROBBODEN_263 = "GBM263Schaufel"
GROBBODEN_SCHAUFEL = "GBMSchaufel"
MASSE_MINI = "MMini"
VOL_MINI = "VOLMiniSZ"
DICHTE_GB = "DichteGB"
GBF_ANTEIL = "GBFAnt"
TRDF_GESCHAETZT = "TRDFgesch"
SKA_FOTO = "SKAFoto"

# Welche Variante welche Rohwerte braucht - abgelesen an den Formeln in
# PRUEFMETHODEN.FORMEL. Variante 3 gibt es nicht.
#
# Die Liste ist der Kern dieses Moduls: aus ihr kommt die Meldung
# "Rohwert fehlt" ebenso wie "fuer diese Variante ohne Belang".
GEBRAUCHT = {
    1: (MASSE_SZ, VOL_SZ, TIEFENSTUFE),
    2: (MASSE_SZ, GROBBODEN_SZ, VOL_SZ, DICHTE_GB, TIEFENSTUFE),
    4: (MASSE_SZ, GROBBODEN_SZ, VOL_SZ, DICHTE_GB, TIEFENSTUFE,
        MASSE_SCHAUFEL, GROBBODEN_63, GROBBODEN_263, GBF_ANTEIL, FAKTOR),
    5: (MASSE_MINI, VOL_MINI, GROBBODEN_SCHAUFEL, MASSE_SCHAUFEL,
        GROBBODEN_63, GROBBODEN_263, DICHTE_GB, GBF_ANTEIL, FAKTOR,
        TIEFENSTUFE),
    6: (MASSE_SZ, GROBBODEN_SZ, VOL_SZ, DICHTE_GB, GBF_ANTEIL, FAKTOR,
        TIEFENSTUFE),
    7: (TRDF_GESCHAETZT, MASSE_SCHAUFEL, GROBBODEN_63, GROBBODEN_263,
        DICHTE_GB, GBF_ANTEIL, FAKTOR, TIEFENSTUFE),
}

VARIANTEN = tuple(sorted(GEBRAUCHT))

# Die Fotoauswertung sticht jede Variante und darf ueberall stehen; die
# Variante selbst ist nie ueberzaehlig.
IMMER_ERLAUBT = (SKA_FOTO, VARIANTE)

# --------------------------------------------------------------------------
# Was die Variante mit den Rohwerten macht
# --------------------------------------------------------------------------
# Im LIMS setzt die Eingabemaske beim Wechsel der Variante die Rohwerte,
# die diese Variante nicht braucht, auf "x" - dann steht in der Zeile,
# dass dort nichts stehen soll, und nicht bloss nichts. Das ist die
# Vorlage, Zeichen fuer Zeichen (kurze Kuerzel des Rohwertparameters):
#
#   if(C==1){$A=$x;$D=$x;$G=$x;$J=$x;$K=$x;$N=$x;$O=$x;$S=$x;$U=$x;
#            $Z=$x;$FBF=$x;}
#   if(C==2){$A=$x;$J=$x;$K=$x;$N=$x;$O=$x;$S=$x;$U=$x;$Z=$x;$FBF=$x;}
#   if(C==4){$A=$x;$J=$x;$K=$x;$N=$x;}
#   if(C==5){$G=$x;$I=$x;$J=$x;$Y=$x;}
#   if(C==6){$A=$x;$J=$x;$K=$x;$N=$x;$O=$x;$S=$x;$Z=$x;}
#   if(C==7){$A=$x;$G=$x;$I=$x;$K=$x;$N=$x;$Y=$x;}
#   if(isnum($FS)==0){$FS=$x;}
#
# Uebersetzt wird ueber die Liste des Labors in trdf.ZUORDNUNG - hier
# stehen die kurzen Kuerzel, gerechnet wird mit den langen.
_MASKIERT_KURZ = {
    1: ("A", "D", "G", "J", "K", "N", "O", "S", "U", "Z", "FBF"),
    2: ("A", "J", "K", "N", "O", "S", "U", "Z", "FBF"),
    4: ("A", "J", "K", "N"),
    5: ("G", "I", "J", "Y"),
    6: ("A", "J", "K", "N", "O", "S", "Z"),
    7: ("A", "G", "I", "K", "N", "Y"),
}

MASKIERT = {nummer: tuple(trdf.ZUORDNUNG[kurz] for kurz in kurze)
            for nummer, kurze in _MASKIERT_KURZ.items()}

# Zwei Eingaben, die keine Variante sind, sondern eine Anweisung: die
# Null raeumt die Zeile leer, das x belegt sie ganz mit x. Beides steht
# so in der Maske des LIMS und ist hier dasselbe.
LEEREN = "0"


def nach_variante(werte: dict, eingabe) -> dict:
    """Was der Wechsel der Variante an den uebrigen Rohwerten aendert.

    Zurueck kommt nur, was sich aendert: {Formelkuerzel: neuer Wert}.
    Die Variante selbst bleibt stehen, wie sie eingegeben wurde.

    Vorhandene Werte werden dabei ueberschrieben - das ist der Sinn der
    Sache: nach dem Wechsel soll in der Zeile stehen, was die neue
    Variante braucht, und sonst ein x.
    """
    text = str(eingabe or "").strip()
    uebrige = [kuerzel for kuerzel in werte if kuerzel != VARIANTE]
    if not text:
        return {}
    if text == LEEREN:
        return {kuerzel: "" for kuerzel in uebrige}
    if trdf.leer(text):                     # ein eingegebenes x
        return {kuerzel: trdf.MARKE for kuerzel in uebrige}
    nummer = variante({VARIANTE: text})
    if nummer not in MASKIERT:
        return {}                           # unbekannt - dann lieber nichts
    neu = {kuerzel: trdf.MARKE for kuerzel in MASKIERT[nummer]
           if kuerzel in werte}
    # Die Fotoauswertung haengt an keiner Variante: steht dort keine
    # Zahl, steht dort ein x.
    if SKA_FOTO in werte and _zahl(werte.get(SKA_FOTO)) is None:
        neu[SKA_FOTO] = trdf.MARKE
    return {kuerzel: wert for kuerzel, wert in neu.items()
            if str(werte.get(kuerzel) or "").strip() != wert}

# --------------------------------------------------------------------------
# Die Grenzen der einzelnen Werte
# --------------------------------------------------------------------------
# Je Rohwert (unten, oben, Meldung). None heisst: nach dieser Seite
# offen. Geprueft wird nur, was dasteht - ein fehlender Wert ist Sache
# der Vollstaendigkeit weiter oben.
GRENZEN = {
    TIEFENSTUFE: (D(0), D(100), "Tiefenstufe unplausibel"),
    FAKTOR: (D(0), D(1), "Faktor Bergland/Flachland unplausibel"),
    VOL_SZ: (D(0), None, "Volumen Stechzylinder unplausibel"),
    VOL_MINI: (D(0), None, "Volumen Ministechzylinder unplausibel"),
    MASSE_SZ: (D(0), None, "Masse Stechzylinder unplausibel"),
    MASSE_MINI: (D(0), None, "Masse Ministechzylinder unplausibel"),
    MASSE_SCHAUFEL: (D(0), None, "Masse Schaufelprobe unplausibel"),
    GROBBODEN_SZ: (D(0), None, "Grobbodenmasse negativ"),
    GROBBODEN_63: (D(0), None, "Grobbodenmasse negativ"),
    GROBBODEN_263: (D(0), None, "Grobbodenmasse negativ"),
    GROBBODEN_SCHAUFEL: (D(0), None, "Grobbodenmasse negativ"),
    DICHTE_GB: (D(2), D(3), "Gesteinsdichte unplausibel"),
    GBF_ANTEIL: (D(0), D(100), "Grobbodenanteil ausserhalb 0-100 %"),
    SKA_FOTO: (D(0), D(100), "Skelettanteil Foto ausserhalb 0-100 %"),
    TRDF_GESCHAETZT: (D("0.2"), D("2.5"),
                      "geschaetzte Trockenrohdichte unplausibel"),
}

# Ein Volumen von null ist kein Volumen: dadurch wird geteilt.
OHNE_NULL = (VOL_SZ, VOL_MINI, DICHTE_GB, MASSE_SZ, MASSE_SCHAUFEL,
             MASSE_MINI)

# In welchem Fenster die feuchte Masse je Volumen liegen darf. Darunter
# waere der Zylinder halb leer, darueber massives Gestein - beides sagt,
# dass eine Zahl nicht zu der anderen gehoert.
DICHTE_UNTEN = D("0.3")
DICHTE_OBEN = D("2.8")

# Der Wiederfindungsgrad geht in jede Masse ein.
WGH_UNTEN = D(0)
WGH_OBEN = D(20)

# Die Meldungen der Beziehungen.
FEHLT = "Rohwert fehlt: {}"
UEBERZAEHLIG = "fuer Variante {} ohne Belang: {}"
VARIANTE_UNBEKANNT = "Variante unbekannt, aber Daten vorhanden"
KEINE_DATEN = "Keine Daten vorhanden"
DICHTE_SZ = "Feuchtdichte Stechzylinder unplausibel"
DICHTE_MINI = "Feuchtdichte Ministechzylinder unplausibel"
GROBBODEN_SCHWERER = "Grobboden schwerer als die Probe"
GROBBODEN_ZU_GROSS = "Grobboden passt nicht in den Stechzylinder"
SCHAUFEL_GEHT_NICHT_AUF = "Grobboden schwerer als die Schaufelprobe"
FEINSTES_ZU_GROSS = "Grobboden 2-6,3 mm groesser als 2-63 mm"
WGH_UNPLAUSIBEL = "Wiederfindungsgrad unplausibel"
ANHANG_ANDERS = "Rohwert am Anhang weicht ab: {}"

TRENNER = ", "


def _zahl(wert):
    return trdf.zahl(wert)


def variante(werte: dict):
    """Die Variante als ganze Zahl - None, wo keine steht."""
    zahl = _zahl(werte.get(VARIANTE))
    if zahl is None:
        return None
    try:
        return int(zahl)
    except (ValueError, decimal.InvalidOperation):
        return None


# --------------------------------------------------------------------------
# 1. Ist alles da?
# --------------------------------------------------------------------------

def fehlende(werte: dict) -> list:
    """Die Rohwerte, die diese Variante braucht und nicht hat."""
    art = variante(werte)
    if art not in GEBRAUCHT:
        return []
    return [name for name in GEBRAUCHT[art] if _zahl(werte.get(name)) is None]


def ueberzaehlige(werte: dict) -> list:
    """Werte, die diese Variante nie benutzt - meist die falsche Variante."""
    art = variante(werte)
    if art not in GEBRAUCHT:
        return []
    gebraucht = set(GEBRAUCHT[art]) | set(IMMER_ERLAUBT)
    return [name for name in werte
            if name not in gebraucht and _zahl(werte.get(name)) is not None]


def ohne_variante(werte: dict) -> bool:
    """Steht in der Variante ein x - "diese Teilprobe bekommt keine"?

    Das ist etwas anderes als eine fehlende Variante. Ein leeres Feld
    heisst "hier fehlt noch die Angabe"; ein x heisst "hier soll keine
    stehen", und dann fehlt auch keiner der Rohwerte, die eine Variante
    braeuchte. Das LIMS haelt es genauso: die Maske setzt die Rohwerte
    einer Teilprobe ohne Variante selbst auf x.
    """
    text = str(werte.get(VARIANTE) or "").strip()
    return bool(text) and _zahl(text) is None


def leer(werte: dict) -> bool:
    """Steht ausser der Variante ueberhaupt etwas in dieser Zeile?

    Eine Probe ganz ohne Rohwerte ist kein Fehler, sondern eine Probe,
    die noch nicht gemessen wurde - sie soll auch nicht wie einer
    aussehen.
    """
    return not any(not trdf.leer(wert) for name, wert in werte.items()
                   if name != VARIANTE)


def vollstaendig(werte: dict) -> list:
    """Die Bewertung zur Vollstaendigkeit - Fehlendes zuerst.

    Ohne brauchbare Variante laesst sich nichts weiter sagen, und dann
    kommt es darauf an, ob sonst etwas dasteht: eine leere Zeile wartet
    auf ihre Messung, eine gefuellte ohne Variante ist ein Fehler - das
    LIMS rechnet an ihr nichts, obwohl alles da waere.
    """
    if ohne_variante(werte):
        return []                   # ein x ist eine Angabe, keine Luecke
    art = variante(werte)
    if art is None or art not in GEBRAUCHT:
        return [KEINE_DATEN] if leer(werte) else [VARIANTE_UNBEKANNT]
    saetze = [FEHLT.format(name) for name in fehlende(werte)]
    zuviel = ueberzaehlige(werte)
    if zuviel:
        saetze.append(UEBERZAEHLIG.format(art, ", ".join(sorted(zuviel))))
    return saetze


# --------------------------------------------------------------------------
# 2. Sind die Zahlen moeglich?
# --------------------------------------------------------------------------

def bereiche(werte: dict) -> list:
    """Jeder Wert gegen seine eigenen Grenzen."""
    saetze = []
    for name, (unten, oben, satz) in GRENZEN.items():
        zahl = _zahl(werte.get(name))
        if zahl is None:
            continue
        zu_klein = unten is not None and (
            zahl < unten or (zahl == unten and name in OHNE_NULL))
        if zu_klein or (oben is not None and zahl > oben):
            saetze.append(f"{satz} ({name})")
    return saetze


# --------------------------------------------------------------------------
# 3. Passen sie zueinander?
# --------------------------------------------------------------------------

def _dichte(masse, volumen):
    """Masse je Volumen - None, wo eines von beiden fehlt."""
    masse, volumen = _zahl(masse), _zahl(volumen)
    if masse is None or volumen is None or volumen <= 0:
        return None
    return masse / volumen


def beziehungen(werte: dict, wgh=None) -> list:
    """Was nur im Verhaeltnis zueinander auffaellt."""
    saetze = []
    feucht = _dichte(werte.get(MASSE_SZ), werte.get(VOL_SZ))
    if feucht is not None and not DICHTE_UNTEN <= feucht <= DICHTE_OBEN:
        saetze.append(DICHTE_SZ)
    mini = _dichte(werte.get(MASSE_MINI), werte.get(VOL_MINI))
    if mini is not None and not DICHTE_UNTEN <= mini <= DICHTE_OBEN:
        saetze.append(DICHTE_MINI)

    grob, ganz = _zahl(werte.get(GROBBODEN_SZ)), _zahl(werte.get(MASSE_SZ))
    if grob is not None and ganz is not None and grob > ganz:
        saetze.append(GROBBODEN_SCHWERER)
    raum = _dichte(werte.get(GROBBODEN_SZ), werte.get(DICHTE_GB))
    zylinder = _zahl(werte.get(VOL_SZ))
    if raum is not None and zylinder is not None and raum >= zylinder:
        saetze.append(GROBBODEN_ZU_GROSS)

    schaufel = _zahl(werte.get(MASSE_SCHAUFEL))
    steine = [_zahl(werte.get(name)) or D(0)
              for name in (GROBBODEN_63, GROBBODEN_263)]
    if schaufel is not None and any(
            _zahl(werte.get(name)) is not None
            for name in (GROBBODEN_63, GROBBODEN_263)) and \
            sum(steine) >= schaufel:
        saetze.append(SCHAUFEL_GEHT_NICHT_AUF)

    feinstes = _zahl(werte.get(GROBBODEN_SCHAUFEL))
    mittleres = _zahl(werte.get(GROBBODEN_263))
    if feinstes is not None and mittleres is not None and feinstes > mittleres:
        saetze.append(FEINSTES_ZU_GROSS)

    gefunden = _zahl(wgh)
    if gefunden is not None and not WGH_UNTEN <= gefunden <= WGH_OBEN:
        saetze.append(WGH_UNPLAUSIBEL)
    return saetze


# --------------------------------------------------------------------------
# Alles zusammen
# --------------------------------------------------------------------------

def anhang_bewerten(vergleich: dict) -> list:
    """Sagen beide Stellen im LIMS dasselbe?

    Ein Rohwert haengt zweimal: als Ergebniszeile unter seiner
    Pruefmethode und am Teilprobenanhang, aus dem die Formeln rechnen.
    Gehen sie auseinander, rechnet das LIMS mit einer Zahl, die in der
    Ergebnistabelle nicht steht - und niemand sieht es.

    `vergleich` ist {Formelkuerzel: (Ergebniszeile, Anhang)}.
    """
    anders = sorted(kuerzel for kuerzel, (zeile, anhang) in vergleich.items()
                    if _zahl(zeile) != _zahl(anhang))
    return [ANHANG_ANDERS.format(", ".join(anders))] if anders else []


def anhang_ohne_variante(vergleich: dict, werte: dict) -> list:
    """Dasselbe fuer eine Teilprobe, die keine Variante bekommt.

    Steht in der Ergebniszeile ein x, ist die Variante selbst kein
    Befund mehr: dass am Anhang noch eine Zahl steht, ist gerade der
    Zustand, den das x beschreibt. Die uebrigen Rohwerte werden weiter
    verglichen - dort rechnet das LIMS wirklich mit dem, was am Anhang
    steht.
    """
    if not ohne_variante(werte):
        return anhang_bewerten(vergleich)
    return anhang_bewerten({kuerzel: paar for kuerzel, paar
                            in vergleich.items() if kuerzel != VARIANTE})


def bewerten(werte: dict, wgh=None, vergleich=None) -> list:
    """Alle Pruefungen einer Probe - in der Reihenfolge des Pruefwegs."""
    return (vollstaendig(werte) + bereiche(werte) + beziehungen(werte, wgh)
            + anhang_ohne_variante(vergleich or {}, werte))


def bewertungstext(saetze) -> str:
    return TRENNER.join(saetze)


def unvollstaendig(werte: dict) -> bool:
    """Fehlt etwas, das diese Variante braucht?

    Danach fragt das Pruefblatt: ein Urteil ueber eine Groesse, die aus
    einem fehlenden Rohwert stammt, ist kein Urteil.
    """
    if ohne_variante(werte):
        return False                # es fehlt nichts, es soll nichts da sein
    return bool(fehlende(werte)) or variante(werte) not in GEBRAUCHT


# --------------------------------------------------------------------------
# Das Blatt
# --------------------------------------------------------------------------
BEWERTUNGSSPALTE = "Bewertung"
ORDNER = "TRDF-Pruefung"
BLOCK = "Pruefung der Rohwerte"


def spalten(rohliste) -> list:
    return ["Zeile", "Probe-Nr.", "UM", "ME", "Variante"] + list(rohliste) + \
        ["WGH", BEWERTUNGSSPALTE]


def zeile(probe: dict, rohliste) -> list:
    werte = probe.get("werte", {})
    gefunden = [probe.get("lnr", ""),
                probe.get("nummer", probe.get("probe", "")),
                probe.get("um", 1), probe.get("me", 1),
                werte.get(VARIANTE, trdf.MARKE)]
    for name in rohliste:
        wert = werte.get(name)
        gefunden.append(trdf.MARKE if trdf.leer(wert) else wert)
    gefunden.append(probe.get("wgh", ""))
    gefunden.append(bewertungstext(probe.get("bewertung", ())))
    return gefunden


def blatt(proben, rohliste, serie: str = "") -> list:
    titel = f"{BLOCK} - Serie {serie}" if serie else BLOCK
    return [(titel, spalten(rohliste),
             [zeile(probe, rohliste) for probe in proben])]


def dateiname(serie: str) -> str:
    name = "".join(zeichen for zeichen in str(serie or "Serie")
                   if zeichen.isalnum() or zeichen in " _-.")
    return f"Rohwerte {name.strip() or 'Serie'}.csv"


def schreiben(ordner: str, serie: str, proben, rohliste) -> str:
    """Legt das Rohwertblatt als CSV ab - "" wenn es nicht ging."""
    ziel = os.path.join(ordner, dateiname(serie))
    inhalt = lims_db.csv_bloecke(blatt(proben, rohliste, serie))
    try:
        os.makedirs(ordner, exist_ok=True)
        with open(ziel, "wb") as datei:
            datei.write(inhalt)
    except OSError:
        return ""
    return ziel
