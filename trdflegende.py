"""TRDF-Pruefmodul - die Legende zu den Tabellen.

Die Tabellen im Pruefmodul tragen in den Ueberschriften die Kuerzel,
mit denen das LIMS rechnet: `_TSM`, `TRD_TRDF`, `GBM263Schaufel`. Das
ist richtig so - unter diesen Namen stehen die Groessen in den Formeln,
und wer eine Formel liest, sucht genau sie. Nur weiss niemand
auswendig, dass `_TSM` die Tiefenstufenmaechtigkeit ist.

Deshalb dieses Modul: es haelt die Stammdaten des Labors - den Namen,
das Kuerzel, die Einheit und das Format je Groesse - und baut daraus
zu einer Tabelle die Legende, Spalte fuer Spalte in derselben
Reihenfolge, in der sie dort steht.

Zwei Quellen, weil das LIMS zwei fuehrt:

* die Pruefmethoden (PRUEFMETHODEN) mit Parametername, Para-Kuerzel,
  Einheit, Format und dem langen Formelkuerzel - das ist der Name, den
  die Spaltenueberschriften tragen;
* die Rohwertparameter (ROHWERTPARAMETER) mit ihrem eigenen Namen,
  ihrem eigenen Kuerzel und dem kurzen Formelkuerzel, unter dem der
  Rohwert am Teilprobenanhang haengt.

Beides steht in der Legende der Rohwerte nebeneinander: wer im
Teilprobenanhang nachsieht, findet dort das kurze Kuerzel und sonst
nichts.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import eingaberaster
import trdf
from widgets import RoundedButton, Style

# --------------------------------------------------------------------------
# Die Stammdaten
# --------------------------------------------------------------------------
# Die Pruefmethoden der TRDF3.2, wie sie das Labor fuehrt:
# Formelkuerzel, Parametername, Para-Kuerzel, Einheit, Format.
METHODEN = (
    ("FBLFL", "FaktorBerglandFlachland", "FBLFL", "ohne", "Dec03"),
    ("FBMMini", "Feinbodenmasse Mini SZ", "FBMMSZ", "g", "Dec02"),
    ("FBMSchaufel", "Feinbodenmasse Schaufel", "FBMSch", "g", "Dec02"),
    ("FBMSZ", "Feinbodenmasse SZ", "FBMSZ", "g", "Dec02"),
    ("FBVSgs", "Feinbodenvorrat_Schätzung63mm_2-63mm_Schaufel", "FBs",
     "t/ha", "Dec01"),
    ("FBVS", "Feinbodenvorrat_nur_Schaufel", "FBSch", "t/ha", "Dec01"),
    ("FBVb", "Feinbodenvorrat berechnet", "FBVB", "t/ha", "Dec01"),
    ("SKAFoto", "Fotoauswertung", "Foto", "Vol%", "Dec02"),
    ("GBFAnt", "GrobbodenFlächenanteil63mmgs", "GBFant63", "%", "Dec01"),
    ("GBM263Schaufel", "GrobbodenmasseSchaufel2-63mm", "GBSch263", "g",
     "Dec02"),
    ("GBMSchaufel", "GrobbodenmasseSchaufel2-6.3mm", "GBSch26_3", "g",
     "Dec02"),
    ("GBM63Schaufel", "GrobbodenmasseSchaufel63mm", "GBSch63", "g", "Dec02"),
    ("GBMSZ", "GrobbodenmasseStechzylinder", "GBSZ", "g", "Dec02"),
    ("GMSZ", "GesamtmasseStechzylinderprobe", "GMSZ", "g", "Dec02"),
    ("DichteGB", "Grobbodendichte", "GD", "g/cm3", "Dec02"),
    ("MMini", "MasseMiniStechzylinder", "MMSZ", "g", "Dec02"),
    ("MSchaufel", "MasseSchaufelprobe", "MSch", "g", "Dec02"),
    ("_SKASgs", "SkelettanteilSchätzung63mm_2-63mmSchaufel", "SKAgs", "%",
     "Dec02"),
    ("_SKAS", "Skelettaneil63mm_2-63mmSchaufel", "SKASch", "%", "Dec02"),
    ("_SKA", "Skelettanteil", "SKA", "%", "Dec02"),
    ("TRDFgesch", "TrockenrohdichteFeinbodengesch", "TRDFg", "g/cm3",
     "Dec02"),
    ("TRD_TRDF", "TrockenrohdichteFeinboden", "TRDF", "g/cm3", "Dec03"),
    # Seit dem 1. September 2026 fuehrt das Labor die Trockenrohdichte
    # zweimal: TRDF_Old rechnet weiter nach der bisherigen Formel,
    # TRD_TRDF nimmt eine gemessene Schaetzung vorweg. Beide schreiben
    # auf denselben Parameter - deshalb steht hier zweimal derselbe Name.
    # Nicht jede Serie fuehrt sie; welche, sagt die Serie selbst.
    ("TRDF_Old", "TrockenrohdichteFeinboden (alte Formel)", "TRDF",
     "g/cm3", "Dec03"),
    ("_TSM", "Tiefenstufenmächtigkeit", "TSM", "cm", "Dec01"),
    ("_TRDV", "TRDF Variante", "TRV", "ohne", "Dec00"),
    ("VOLAntGB263", "VolumenanteilGrobbodenSchaufelprobe263", "GBSch263",
     "%", "Dec02"),
    ("VOLGB63gs", "Volumenanteil Grobboden63_Schätzung_Profil", "VGB", "%",
     "Dec01"),
    ("VOLMiniSZ", "VolumenMiniStechzylinder", "VMSZ", "cm3", "Dec01"),
    ("VOLSZ", "VolumenStechzylinder", "VSZ", "cm3", "Dec01"),
)

# Die Rohwertparameter derselben Methode - eigener Name, eigenes
# Kuerzel, eigenes (kurzes) Formelkuerzel. Geschluesselt ist die Liste
# ueber das kurze Kuerzel, so wie sie im LIMS steht.
ROHWERTPARAMETER = (
    ("D", "DichteGrobboden", "DGB", "g/cm3"),
    ("FBF", "Faktor Bergland Flachland", "FBLFL", "ohne"),
    ("Y", "GesamtmasseStechzylinderprobe", "MgesSZ", "g"),
    ("U", "GrobbodenFlächenanteil>63mm", "GFL", "%"),
    ("K", "GrobbodenmasseSchaufel2-6,3", "MGB2-6,3SCH", "g"),
    ("Z", "GrobbodenmasseSchaufel2-63mm", "MGB2-63SCH", "g"),
    ("O", "GrobbodenmasseSchaufel>63mm", "MGB63SCH", "g"),
    ("G", "GrobbodenmasseStechzylinder", "MGBSZ", "g"),
    ("S", "MasseSchaufelprobe", "MgesSCH", "g"),
    ("A", "MasseStechkappenprobe+Stechkappe", "MSTK", "g"),
    ("FS", "Skelettanteil (Fotoauswertung)", "Foto", "%"),
    ("M", "Tiefenstufenmächtigkeit", "d", "cm"),
    ("J", "TrockenraumdichteFeinboden geschätzt", "TRDFG", "g/cm3"),
    ("C", "Variante", "VTRD", "ohne"),
    ("N", "VolumenStechkappen", "VSK", "cm3"),
    ("I", "VolumenStechzylinder", "VgesSZ", "cm3"),
)

# Was in den Tabellen steht, ohne aus der TRDF-Methode zu kommen: der
# Wassergehalt aus seiner eigenen Pruefmethode und der Aufschluss, aus
# dem die Kohlenstoffklasse folgt. Ohne Einheit, wo LabControl sie
# nicht kennt - eine erfundene Einheit waere schlimmer als keine.
ZUSATZ = {
    "WGH": ("Wassergehalt", "", "%"),
    "Cges": ("Gesamtkohlenstoff (aus dem Aufschluss der Serie)", "", ""),
    "CO3": ("Carbonat-Kohlenstoff C-CO3 (aus dem Aufschluss)", "", ""),
}

# Die Spalten, die keine Groesse zeigen, sondern die Zeile fuehren.
FUEHRUNG = {
    "Zeile": "Laufende Nummer im LIMS (LNR)",
    "Probe": "Probennummer",
    "Probe-Nr.": "Probennummer",
    "UM": "Wiederholung der Untersuchungsmethode (WDH_UM in PROBEN, 1 = "
          "Erstmessung)",
    "ME": "Wiederholung der Messung (WDH_ME in PROBEN, 1 = Erstmessung)",
    "Bewertung": "Was auffaellt - sonst leer",
    "Befund": "Was auffaellt - sonst leer",
}

# Wie die Ergebnistabelle ihre Spaltenpaare nennt.
ANHAENGSEL = (" LIMS", " ber.")
ERKLAERUNG = {" LIMS": "wie im LIMS gebucht",
              " ber.": "vom Pruefmodul aus denselben Formeln gerechnet"}

# Kein Wert, aber auch kein Fehler: eine Spalte, zu der die Stammdaten
# nichts sagen. Sie steht trotzdem in der Legende - eine Legende, die
# eine Spalte verschweigt, laesst gerade die Frage offen, wegen der
# jemand sie geoeffnet hat.
UNBEKANNT = "-"

NACH_KUERZEL = {kurz: (name, zeichen, einheit, format_)
                for kurz, name, zeichen, einheit, format_ in METHODEN}
NACH_ROHKUERZEL = {kurz: (name, zeichen, einheit)
                   for kurz, name, zeichen, einheit in ROHWERTPARAMETER}
# Das kurze Kuerzel zum langen - dieselbe Bruecke wie in trdf.zuordnen.
KURZ_ZU_LANG = dict(trdf.ZUORDNUNG)
LANG_ZU_KURZ = {lang: kurz for kurz, lang in KURZ_ZU_LANG.items()}


# --------------------------------------------------------------------------
# Die Legende zu einer Tabelle
# --------------------------------------------------------------------------

def zerlegen(spalte: str) -> tuple:
    """Trennt "TRDF ber." in das Kuerzel und den Zusatz dahinter."""
    text = str(spalte or "")
    for anhang in ANHAENGSEL:
        if text.endswith(anhang):
            return text[:-len(anhang)], anhang
    return text, ""


def name_von(kuerzel: str, methoden=()) -> tuple:
    """Name, Einheit und Format zu einem Formelkuerzel.

    Zuerst die Stammdaten, dann - fuer alles, was sie nicht kennen -
    was der Abruf zu dieser Serie mitgebracht hat. Was auch dort nicht
    steht, bleibt offen und wird so gezeigt.
    """
    if kuerzel in NACH_KUERZEL:
        name, _zeichen, einheit, format_ = NACH_KUERZEL[kuerzel]
        return name, einheit, format_
    if kuerzel in ZUSATZ:
        name, _zeichen, einheit = ZUSATZ[kuerzel]
        return name, einheit, ""
    for methode in methoden:
        if str(methode.get("formelkuerzel") or "").strip() == kuerzel:
            name = (methode.get("name") or methode.get("parameter")
                    or methode.get("kurzname") or "")
            return str(name), "", ""
    return "", "", ""


# Die letzte Spalte gehoert dem Pruefer: was er dort schreibt, bleibt
# in den Einstellungen und geht in keine Datenbank.
BESCHREIBUNG = "Beschreibung"

SPALTEN_ROH = ("Spalte", "Name", "Kuerzel", "Einheit", "Formelkuerzel",
               "Format", BESCHREIBUNG)
SPALTEN_ERGEBNIS = ("Spalte", "Parametername", "Einheit", "Formelkuerzel",
                    "Format", BESCHREIBUNG)


def schluessel(spalte: str, quellen=None) -> str:
    """Unter welchem Namen die Beschreibung dieser Spalte gespeichert wird.

    Es ist das Formelkuerzel und nicht die Ueberschrift: dieselbe
    Groesse heisst in den drei Tabellen verschieden ("TRD_TRDF",
    "TRDF ber.", "TRDF"), und wer sie einmal beschrieben hat, will das
    nicht dreimal tun.
    """
    if spalte in FUEHRUNG:
        return spalte
    if quellen and spalte in quellen:
        return quellen[spalte]
    return zerlegen(spalte)[0]


def _mit_beschreibung(zeilen, spalten, beschreibungen, quellen=None) -> list:
    """Haengt an jede Zeile, was der Pruefer dazu notiert hat."""
    texte = beschreibungen or {}
    for zeile, spalte in zip(zeilen, spalten):
        zeile.append(texte.get(schluessel(spalte, quellen), ""))
    return zeilen


def rohlegende(spalten, methoden=(), beschreibungen=None) -> list:
    """Die Legende zur Rohwerttabelle - mit beiden Kuerzeln.

    Der Rohwert haengt im LIMS an zwei Stellen und traegt dort zwei
    Namen: das lange Formelkuerzel an der Pruefmethode, mit dem gerechnet
    wird, und das kurze am Rohwertparameter, unter dem er im
    Teilprobenanhang steht. Beide gehoeren in die Legende.
    """
    zeilen = []
    for spalte in spalten:
        if spalte in FUEHRUNG:
            zeilen.append([spalte, FUEHRUNG[spalte], "", "", "", ""])
            continue
        kurz = LANG_ZU_KURZ.get(spalte, "")
        name, einheit, format_ = name_von(spalte, methoden)
        zeichen = ""
        if kurz in NACH_ROHKUERZEL:
            # Der Rohwertparameter fuehrt seinen eigenen Namen - und der
            # ist der, den das Labor benutzt.
            name, zeichen, einheit = NACH_ROHKUERZEL[kurz]
        zeilen.append([spalte, name or UNBEKANNT, zeichen or UNBEKANNT,
                       einheit or UNBEKANNT, kurz or UNBEKANNT,
                       format_ or ""])
    return _mit_beschreibung(zeilen, spalten, beschreibungen)


def ergebnislegende(spalten, methoden=(), beschreibungen=None) -> list:
    """Die Legende zur Ergebnis- oder Pruefungstabelle."""
    zeilen = []
    for spalte in spalten:
        if spalte in FUEHRUNG:
            zeilen.append([spalte, FUEHRUNG[spalte], "", "", ""])
            continue
        kuerzel, anhang = zerlegen(spalte)
        name, einheit, format_ = name_von(kuerzel, methoden)
        if anhang:
            name = f"{name or kuerzel} - {ERKLAERUNG[anhang]}"
        zeilen.append([spalte, name or UNBEKANNT, einheit or UNBEKANNT,
                       kuerzel, format_ or ""])
    return _mit_beschreibung(zeilen, spalten, beschreibungen)


# Was ueber einer Spaltenueberschrift steht, wenn die Maus dort wartet:
# dasselbe wie in der Legende, nur auf zwei bis vier Zeilen. Wer die
# Kuerzel nicht auswendig kennt, faehrt hinueber statt die Legende zu
# oeffnen - und wer sie kennt, sieht die Einheit nach.


def hinweis(spalte: str, methoden=(), quellen=None,
            beschreibungen=None) -> str:
    """Der Hinweis zu einer Spaltenueberschrift - "" wenn nichts zu sagen."""
    if spalte in FUEHRUNG:
        return FUEHRUNG[spalte]
    kuerzel, anhang = zerlegen(spalte)
    if quellen and spalte in quellen:
        kuerzel, anhang = quellen[spalte], ""
    name, einheit, format_ = name_von(kuerzel, methoden)
    kurz = LANG_ZU_KURZ.get(kuerzel, "")
    zeichen = NACH_ROHKUERZEL.get(kurz, ("", "", ""))[1] if kurz else \
        NACH_KUERZEL.get(kuerzel, ("", "", "", ""))[1]
    zeilen = [f"{name} ({kuerzel})" if name else kuerzel]
    if anhang:
        zeilen.append(ERKLAERUNG[anhang])
    unten = []
    if einheit:
        unten.append(f"Einheit: {einheit}")
    if zeichen:
        unten.append(f"Kuerzel: {zeichen}")
    if kurz:
        # Unter diesem Namen haengt der Rohwert am Teilprobenanhang.
        unten.append(f"am Anhang: {kurz}")
    if format_:
        unten.append(f"Format: {format_}")
    if unten:
        zeilen.append("  ·  ".join(unten))
    eigenes = (beschreibungen or {}).get(kuerzel, "")
    if eigenes:
        zeilen.append(eigenes)
    if len(zeilen) == 1 and not name:
        return ""            # nur die Ueberschrift noch einmal - dann nichts
    return "\n".join(zeilen)


# --------------------------------------------------------------------------
# Was in der Kopfzeile der Tabelle steht
# --------------------------------------------------------------------------
# Von Haus aus das Formelkuerzel: unter diesem Namen rechnet das LIMS,
# und wer eine Formel liest, sucht genau es. Wem das zu kryptisch ist,
# der stellt hier auf den Namen um - oder auf seine eigene Beschreibung.
# Die Spalte heisst innen weiter, wie sie heisst; nur die Ueberschrift
# wechselt.
KOPFWAHL = ("Spalte", "Name", "Kuerzel", "Einheit", "Beschreibung")


def _angaben(kuerzel: str, methoden=(), roh=False) -> tuple:
    """Name, Kuerzel und Einheit zu einem Formelkuerzel.

    `roh` sagt, dass die Rohwerttabelle fragt: dort fuehrt der
    Rohwertparameter seinen eigenen Namen, und der ist der, den das
    Labor benutzt.
    """
    name, einheit, _format = name_von(kuerzel, methoden)
    zeichen = NACH_KUERZEL.get(kuerzel, ("", "", "", ""))[1]
    kurz = LANG_ZU_KURZ.get(kuerzel, "")
    if roh and kurz in NACH_ROHKUERZEL:
        name, zeichen, einheit = NACH_ROHKUERZEL[kurz]
    return name, zeichen, einheit


def ueberschrift(spalte: str, eintrag: str, methoden=(), quellen=None,
                 beschreibungen=None, roh=False) -> str:
    """Was ueber dieser Spalte steht, wenn `eintrag` gewaehlt ist.

    Wo der gewaehlte Eintrag nichts hergibt - keine Einheit, keine
    Beschreibung -, bleibt es beim Spaltennamen: eine leere
    Ueberschrift waere schlimmer als eine kryptische.
    """
    spalte = str(spalte)
    if not eintrag or eintrag == KOPFWAHL[0] or spalte in FUEHRUNG:
        return spalte
    kuerzel, anhang = zerlegen(spalte)
    if quellen and spalte in quellen:
        kuerzel, anhang = quellen[spalte], ""
    name, zeichen, einheit = _angaben(kuerzel, methoden, roh)
    gewaehlt = {"Name": name, "Kuerzel": zeichen, "Einheit": einheit,
                BESCHREIBUNG: (beschreibungen or {}).get(kuerzel, "")}
    text = str(gewaehlt.get(eintrag, "") or "").strip()
    return (text + anhang) if text else spalte


def ueberschriften(spalten, eintrag: str, methoden=(), quellen=None,
                   beschreibungen=None, roh=False, wahl=None) -> dict:
    """Eine ganze Kopfzeile - je Spalte, was fuer sie gewaehlt ist.

    `eintrag` ist die Wahl fuer alle, `wahl` die fuer die einzelne
    Groesse: geschluesselt auf ihr Formelkuerzel, so wie die
    Beschreibung. Eine Spalte, zu der nichts gewaehlt ist, folgt der
    Wahl fuer alle - sonst muesste jede neue Pruefmethode erst einmal
    einzeln eingestellt werden.
    """
    eigene = dict(wahl or {})
    gefunden = {}
    for spalte in spalten:
        name = str(spalte)
        gilt = eigene.get(schluessel(name, quellen), eintrag)
        gefunden[name] = ueberschrift(name, gilt, methoden, quellen,
                                      beschreibungen, roh)
    return gefunden


def hinweise(spalten, methoden=(), quellen=None, beschreibungen=None) -> dict:
    """Dieselbe Auskunft fuer eine ganze Kopfzeile."""
    gefunden = {}
    for spalte in spalten:
        text = hinweis(spalte, methoden, quellen, beschreibungen)
        if text:
            gefunden[spalte] = text
    return gefunden


def pruefungslegende(spalten, quellen, methoden=(),
                     beschreibungen=None) -> list:
    """Dasselbe fuer das Pruefblatt - dort heissen die Spalten anders.

    "SKAgs63" ist keine Formel, sondern eine Ueberschrift; welches
    Kuerzel dahintersteht, weiss `quellen`.
    """
    zeilen = []
    for spalte in spalten:
        if spalte in FUEHRUNG:
            zeilen.append([spalte, FUEHRUNG[spalte], "", "", ""])
            continue
        kuerzel = quellen.get(spalte, spalte)
        name, einheit, format_ = name_von(kuerzel, methoden)
        zeilen.append([spalte, name or UNBEKANNT, einheit or UNBEKANNT,
                       kuerzel, format_ or ""])
    return _mit_beschreibung(zeilen, spalten, beschreibungen, quellen)


# --------------------------------------------------------------------------
# Das Fenster
# --------------------------------------------------------------------------
# Die Legende steht in demselben Raster wie die Tabellen, die sie
# erklaert - nur dass hier eine Spalte beschreibbar ist. Was der
# Pruefer dort notiert, geht in die Einstellungsdatei und sonst
# nirgendwohin; die Oracle-Datenbank sieht davon nichts.

TITEL = "Legende - {}"
HINWEIS = ("Die Spaltenueberschriften der Tabelle und was dahintersteht. "
           "Die Spalte „Beschreibung“ laesst sich beschreiben: anklicken, "
           "tippen, „Speichern“. Der Text steht beim naechsten Mal wieder "
           "da - er wird bei den Einstellungen abgelegt und geht in keine "
           "Datenbank. Die Beschreibung haengt am Formelkuerzel: einmal "
           "geschrieben, steht sie in allen drei Legenden.\n"
           "Die Reihenfolge dieser Zeilen ist die Reihenfolge der Spalten "
           "in der Tabelle: eine Zeile mit der Maus greifen und ziehen - "
           "sie haengt am Zeiger, und die anderen ruecken schon beim "
           "Ziehen zusammen. „Fest“ heisst, dass die Spalte links stehen "
           "bleibt, waehrend der Rest waagerecht laeuft; „Zeigen“ blendet "
           "sie aus und wieder ein - ein Klick auf „ja“/„nein“ schaltet "
           "um. Was fest steht, bleibt sichtbar und laesst sich nicht aus "
           "Versehen verschieben. „Kopfzeile“ sagt je Spalte, was oben "
           "steht: das Formelkuerzel, der Name, das Para-Kuerzel, die "
           "Einheit oder die eigene Beschreibung - anklicken schaltet "
           "weiter, die Wahl daneben stellt alle auf einmal. Alles gilt "
           "erst nach „Speichern“.")
GESPEICHERT = "{} Beschreibungen gespeichert."
NICHT_GESPEICHERT = "Die Einstellungen liessen sich nicht speichern: {}"
BLEIBT = ("Was fest steht, bleibt sichtbar - erst das „ja“ bei „Fest“ "
          "wegnehmen.")
KOPFHINWEIS = "Ueberschrift fuer alle:"

# Die Spalte, mit der sich eine Tabellenspalte festnageln laesst. Sie
# steht gleich hinter dem Namen - dort sucht man sie, und sie bleibt im
# Blick, weil die Legende selbst ihre ersten beiden Spalten festhaelt.
FEST = "Fest"
JA, NEIN = "ja", "nein"

# Ob die Spalte ueberhaupt dasteht. Von Haus aus alle - wer eine Tabelle
# oeffnet, will erst einmal sehen, was es gibt; das Ausduennen kommt
# danach. Was fest steht, bleibt sichtbar: eine ausgeblendete
# Probennummer nimmt der Zeile ihren Namen.
ZEIGEN = "Zeigen"

# Und was oben in der Kopfzeile dieser einen Spalte steht. Die Wahl in
# der Leiste stellt alle zugleich; hier geht es Spalte fuer Spalte -
# das Kuerzel bei den kryptischen, der Name bei den seltenen.
KOPFSPALTE = "Kopfzeile"


def naechste_kopfwahl(eintrag: str) -> str:
    """Ein Klick weiter in der Reihe der Wahlmoeglichkeiten."""
    reihe = list(KOPFWAHL)
    try:
        stelle = reihe.index(str(eintrag))
    except ValueError:
        return reihe[0]
    return reihe[(stelle + 1) % len(reihe)]

# Womit eine Tabelle anfaengt, solange niemand etwas anderes gesagt
# hat: die Zeile, die Probe mit UM und ME - und bei den Rohwerten die
# Variante, denn ohne sie sagt keine Zahl der Zeile etwas.
STANDARD_FEST = ("Zeile", "Probe", "Probe-Nr.", "UM", "ME", "_TRDV")

# Was neben der Probennummer steht und mit ihr erst die Zeile benennt:
# dieselbe Nummer kommt bei einer Wiederholung mehrfach vor.
PROBENSPALTEN = ("Probe", "Probe-Nr.")
WIEDERHOLUNG = ("UM", "ME")


def mit_wiederholung(reihenfolge, fest) -> tuple:
    """UM und ME gleich hinter die Probe - auch in einer alten Ordnung.

    Wer seine Spalten schon einmal zurechtgezogen hat, hat eine
    Reihenfolge gespeichert, die UM und ME noch nicht kennt. Neue
    Spalten wandern sonst ans Ende; diese beiden gehoeren aber zur
    Probennummer, denn erst mit ihnen ist die Zeile eindeutig. Steht
    die Probe fest, stehen sie mit fest. Was gespeichert ist, sobald
    sie einmal in der Legende waren, gilt wieder unveraendert.
    """
    reihenfolge, fest = list(reihenfolge or []), list(fest or [])
    neu = [name for name in WIEDERHOLUNG if name not in reihenfolge]
    if not neu or not reihenfolge:
        return reihenfolge, fest
    # Kennt die Reihenfolge die Probe, kommen sie gleich dahinter; sonst
    # bleiben sie, wo die Tabelle sie hinstellt - auch das ist hinter
    # der Probe.
    probe = next((name for name in PROBENSPALTEN if name in reihenfolge),
                 None)
    if probe:
        stelle = reihenfolge.index(probe) + 1
        reihenfolge[stelle:stelle] = neu
    if any(name in fest for name in PROBENSPALTEN):
        fest += [name for name in neu if name not in fest]
    return reihenfolge, fest

# Schmal gehalten, damit rechts genug fuer die Beschreibung bleibt -
# sie ist die einzige Spalte, in der jemand schreibt.
BREITEN = {"Spalte": 140, "Name": 260, "Parametername": 260, "Kuerzel": 90,
           "Einheit": 70, "Formelkuerzel": 120, "Format": 60, FEST: 50,
           ZEIGEN: 60, KOPFSPALTE: 110, BESCHREIBUNG: 380}


def geordnet(spalten, schluessel, reihenfolge=(), fest=()) -> tuple:
    """Bringt Tabellenspalten in die Reihenfolge, die der Pruefer wollte.

    Gearbeitet wird in Bloecken je Formelkuerzel: "TRDF LIMS" und
    "TRDF ber." zeigen dieselbe Groesse und gehoeren zusammen - wer die
    eine verschiebt, meint beide.

    Zurueck kommen die Spalten in ihrer neuen Reihenfolge und die, die
    stehen bleiben. Die festen stehen vorn, denn nur links laesst sich
    etwas festhalten. Was die gespeicherte Reihenfolge nicht kennt -
    eine neue Pruefmethode zum Beispiel -, behaelt seinen Platz am Ende
    statt zu verschwinden.
    """
    bloecke, folge = {}, []
    for spalte in spalten:
        kuerzel = schluessel(spalte)
        if kuerzel not in bloecke:
            bloecke[kuerzel] = []
            folge.append(kuerzel)
        bloecke[kuerzel].append(spalte)
    gewuenscht = [kuerzel for kuerzel in (reihenfolge or []) if kuerzel in bloecke]
    sortiert = gewuenscht + [kuerzel for kuerzel in folge
                             if kuerzel not in gewuenscht]
    gehalten = set(fest or ())
    vorn = [kuerzel for kuerzel in sortiert if kuerzel in gehalten]
    hinten = [kuerzel for kuerzel in sortiert if kuerzel not in gehalten]
    return ([spalte for kuerzel in vorn + hinten for spalte in bloecke[kuerzel]],
            [spalte for kuerzel in vorn for spalte in bloecke[kuerzel]])


def sichtbar(spalten, schluessel, versteckt=(), fest=()) -> list:
    """Die Spalten, die die Tabelle zeigt - die ausgeblendeten fehlen.

    Ausgeblendet wird je Groesse, nicht je Spalte: wer "TRDF"
    ausblendet, meint in der Ergebnistabelle beide Spalten des Paares.
    Was festgehalten ist, bleibt sichtbar - eine festgehaltene und
    gleichzeitig ausgeblendete Spalte waere ein Widerspruch, und die
    Zeile verlore mit der Probennummer ihren Namen.
    """
    weg = {str(name) for name in (versteckt or ())} - {str(name)
                                                       for name in (fest or ())}
    return [spalte for spalte in spalten if schluessel(spalte) not in weg]


class Legendenfenster(tk.Toplevel):
    """Was die Spalten einer Tabelle bedeuten - und Platz fuer Eigenes."""

    def __init__(self, eltern, titel: str, spalten, zeilen, speichern=None,
                 schluessel=None, ordnung=None):
        super().__init__(eltern)
        self.title(TITEL.format(titel))
        self.configure(bg=Style.BG)
        # Breit genug, dass neben den vier Schaltern links noch die
        # Beschreibung ohne Scrollen dasteht - sie ist die einzige
        # Spalte, in der jemand schreibt.
        self.geometry("1340x620")
        # Wie das Blockbild: ueber dem Hauptfenster, sonst verschwindet
        # es hinter ihm, sobald jemand dorthin klickt.
        self.transient(eltern.winfo_toplevel())
        self._speichern = speichern
        # Unter welchem Namen die Beschreibung einer Zeile abgelegt wird -
        # ohne Angabe unter der Spaltenueberschrift selbst.
        self._schluessel = dict(schluessel or {})
        ordnung = dict(ordnung or {})
        self._fest = [str(name) for name in (ordnung.get("fest") or ())]
        self._versteckt = [str(name)
                           for name in (ordnung.get("versteckt") or ())]
        self.v_kopf = tk.StringVar(
            value=str(ordnung.get("kopfspalte") or KOPFWAHL[0]))
        # Was je Spalte oben steht. Wo nichts gewaehlt ist, gilt die
        # Wahl fuer alle - so muss eine neue Pruefmethode nicht erst
        # eingestellt werden, um lesbar zu sein.
        self._kopfwahl = {str(kuerzel): str(wert) for kuerzel, wert
                          in (ordnung.get("kopfspalten") or {}).items()}
        # Die Schalter stehen gleich hinter dem Namen der Spalte: dort
        # sucht man sie, und sie bleiben im Blick, weil die Legende
        # ihre ersten Spalten festhaelt.
        self.spalten = ([str(spalten[0]), FEST, ZEIGEN, KOPFSPALTE]
                        + [str(name) for name in spalten[1:]])
        self._zeilen = [self._zeile(zeile) for zeile in zeilen]
        self._geladen = {zeile[0]: str(zeile[-1] or "")
                         for zeile in self._zeilen}

        tk.Label(self, text=HINWEIS, bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w", justify="left",
                 wraplength=1180).pack(fill="x", padx=16, pady=(14, 8))
        leiste = tk.Frame(self, bg=Style.BG)
        leiste.pack(fill="x", padx=16, pady=(0, 8))
        RoundedButton(leiste, text="Speichern", width=140, height=30,
                      bg="#166534", command=self._sichern).pack(side="left")
        RoundedButton(leiste, text="Schliessen", width=140, height=30,
                      bg="#6b7268", command=self.destroy).pack(
            side="left", padx=(8, 0))
        tk.Label(leiste, text=KOPFHINWEIS, bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(9)).pack(side="left", padx=(18, 6))
        self.kopfwahl = ttk.Combobox(leiste, textvariable=self.v_kopf,
                                     values=list(KOPFWAHL), state="readonly",
                                     width=14)
        self.kopfwahl.pack(side="left")
        # Eine Wahl hier heisst: alle Spalten so. Danach laesst sich
        # einzeln abweichen - der umgekehrte Weg (jede Spalte einzeln
        # stellen) waere bei dreissig Spalten Arbeit fuer nichts.
        self.kopfwahl.bind("<<ComboboxSelected>>", self._alle_koepfe)
        self.stand = tk.Label(leiste, text="", bg=Style.BG, fg=Style.MUTED,
                              font=Style.font(9), anchor="w")
        self.stand.pack(side="left", padx=(14, 0))

        self.tabelle = eingaberaster.Eingaberaster(
            self, hoehe=18, bei_klick=self._geklickt,
            bei_verschieben=self._verschieben, schriftgroesse=11,
            zeilenluft=3)
        self.tabelle.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self._zeigen()

    # ------------------------------------------------------------- Zeilen
    def _zeile(self, zeile) -> list:
        """Eine Legendenzeile mit ihren Schaltern davor."""
        zeile = list(zeile)
        kuerzel = self._kuerzel(zeile[0])
        fest = kuerzel in self._fest
        zeigt = NEIN if (kuerzel in self._versteckt and not fest) else JA
        return [zeile[0], JA if fest else NEIN, zeigt,
                self._kopfeintrag(kuerzel)] + zeile[1:]

    def _kopfeintrag(self, kuerzel: str) -> str:
        """Was fuer diese Groesse oben steht - sonst die Wahl fuer alle."""
        return self._kopfwahl.get(kuerzel, self.v_kopf.get())

    def _kuerzel(self, kennung: str) -> str:
        """Unter welchem Namen diese Zeile gespeichert wird."""
        return self._schluessel.get(kennung, kennung)

    def _zeigen(self):
        """Die Tabelle neu schreiben - nach jedem Verschieben."""
        self.tabelle.fuellen(
            self.spalten,
            [(zeile[0], dict(zip(self.spalten, zeile)))
             for zeile in self._zeilen],
            aenderbar=(BESCHREIBUNG,), breiten=BREITEN,
            passend=("Name", "Parametername", BESCHREIBUNG),
            linksbuendig=(BESCHREIBUNG,),
            fest=(self.spalten[0], FEST, ZEIGEN, KOPFSPALTE),
            # Was beim Ziehen am Zeiger haengt: die Spalte und ihr Name.
            zugspalten=(self.spalten[0], "Name", "Parametername"))

    def _einsammeln(self):
        """Holt zurueck, was gerade in der Tabelle steht.

        Vor jedem Neuschreiben: sonst faellt der Text, den jemand
        eingetippt und noch nicht gespeichert hat, beim Verschieben
        unter den Tisch.
        """
        for zeile in self._zeilen:
            if self.tabelle.hat(zeile[0]):
                zeile[-1] = self.tabelle.wert(zeile[0], BESCHREIBUNG)

    def _geklickt(self, kennung: str, spalte: str):
        """Ein Klick auf einen der drei Schalter - alles andere tut nichts."""
        if spalte not in (FEST, ZEIGEN, KOPFSPALTE):
            return
        kuerzel = self._kuerzel(kennung)
        self._einsammeln()
        if spalte == FEST:
            if kuerzel in self._fest:
                self._fest.remove(kuerzel)
            else:
                self._fest.append(kuerzel)
                # Fest und ausgeblendet widerspricht sich - fest gewinnt.
                if kuerzel in self._versteckt:
                    self._versteckt.remove(kuerzel)
        elif spalte == ZEIGEN:
            if kuerzel in self._fest:
                # Wer die Probennummer ausblendet, verliert den Namen
                # der Zeile. Erst das „ja“ bei „Fest“ wegnehmen.
                self.stand.config(text=BLEIBT, fg=Style.MUTED)
                return
            if kuerzel in self._versteckt:
                self._versteckt.remove(kuerzel)
            else:
                self._versteckt.append(kuerzel)
        else:
            self._kopfwahl[kuerzel] = naechste_kopfwahl(
                self._kopfeintrag(kuerzel))
        self._schalter_stellen(kuerzel)
        self._zeigen()

    def _schalter_stellen(self, kuerzel: str):
        """Die drei Schalter einer Groesse neu setzen - in allen ihren Zeilen.

        Ein Spaltenpaar ("TRDF LIMS" und "TRDF ber.") zeigt dieselbe
        Groesse und traegt deshalb dieselben Schalter.
        """
        fest = kuerzel in self._fest
        for zeile in self._zeilen:
            if self._kuerzel(zeile[0]) != kuerzel:
                continue
            zeile[1] = JA if fest else NEIN
            zeile[2] = NEIN if (kuerzel in self._versteckt
                                and not fest) else JA
            zeile[3] = self._kopfeintrag(kuerzel)

    def _alle_koepfe(self, _ereignis=None):
        """Die Wahl aus der Leiste gilt fuer alle Spalten."""
        self._einsammeln()
        self._kopfwahl = {}
        for zeile in self._zeilen:
            zeile[3] = self.v_kopf.get()
        self._zeigen()

    def _verschieben(self, von: str, nach: str):
        """Eine Zeile an eine andere Stelle ziehen.

        Feste Zeilen bleiben, wo sie sind, und nichts schiebt sich
        zwischen sie: sie stehen links und halten die Tabelle
        zusammen. Wer sie bewegen will, nimmt ihnen erst das „ja“.
        """
        quelle, ziel = self._kuerzel(von), self._kuerzel(nach)
        if quelle == ziel or quelle in self._fest or ziel in self._fest:
            return
        self._einsammeln()
        stellen = [nummer for nummer, zeile in enumerate(self._zeilen)
                   if self._kuerzel(zeile[0]) == quelle]
        block = [self._zeilen[nummer] for nummer in stellen]
        rest = [zeile for zeile in self._zeilen
                if self._kuerzel(zeile[0]) != quelle]
        treffer = [nummer for nummer, zeile in enumerate(rest)
                   if self._kuerzel(zeile[0]) == ziel]
        if not treffer:
            return
        # Nach unten gezogen heisst hinter das Ziel, nach oben davor -
        # sonst landet die Zeile eine Stelle vor dem Finger.
        hinunter = stellen[0] < min(
            nummer for nummer, zeile in enumerate(self._zeilen)
            if self._kuerzel(zeile[0]) == ziel)
        stelle = treffer[-1] + 1 if hinunter else treffer[0]
        self._zeilen = rest[:stelle] + block + rest[stelle:]
        self._zeigen()

    # ------------------------------------------------------------ Auskunft
    def texte(self) -> dict:
        """Was jetzt in der Beschreibungsspalte steht - je Schluessel.

        Zwei Zeilen koennen denselben Schluessel tragen: "TRDF LIMS" und
        "TRDF ber." zeigen dieselbe Groesse. Dann gilt die Zeile, an der
        gerade etwas geaendert wurde - die andere stand ja noch auf dem
        alten Stand und wuerde ihn zurueckschreiben.
        """
        gefunden, bewegt = {}, set()
        for kennung in self.tabelle.zeilen():
            schluessel = self._kuerzel(kennung)
            text = self.tabelle.wert(kennung, BESCHREIBUNG).strip()
            geaendert = text != self._geladen.get(kennung, "").strip()
            if schluessel in bewegt and not geaendert:
                continue
            gefunden[schluessel] = text
            if geaendert:
                bewegt.add(schluessel)
        return gefunden

    def ordnung(self) -> dict:
        """Reihenfolge, feste und ausgeblendete Spalten, Wahl der Kopfzeile."""
        reihenfolge = []
        for kennung in self.tabelle.zeilen():
            kuerzel = self._kuerzel(kennung)
            if kuerzel not in reihenfolge:
                reihenfolge.append(kuerzel)
        return {"reihenfolge": reihenfolge,
                "fest": [kuerzel for kuerzel in reihenfolge
                         if kuerzel in self._fest],
                "versteckt": [kuerzel for kuerzel in reihenfolge
                              if kuerzel in self._versteckt
                              and kuerzel not in self._fest],
                "kopfspalte": self.v_kopf.get(),
                # Nur, was von der Wahl fuer alle abweicht: so folgt
                # eine neue Pruefmethode ihr von allein.
                "kopfspalten": {kuerzel: wert for kuerzel, wert
                                in self._kopfwahl.items()
                                if wert != self.v_kopf.get()}}

    def _sichern(self):
        if self._speichern is None:
            return
        fehler = self._speichern(self.texte(), self.ordnung())
        if fehler:
            self.stand.config(text=NICHT_GESPEICHERT.format(fehler),
                              fg=Style.ERROR)
            return
        gefuellt = len([text for text in self.texte().values() if text])
        self.stand.config(text=GESPEICHERT.format(gefuellt), fg=Style.TEXT)
