"""
TRDF-Pruefmodul - der Rueckweg der TRDF-Pruefung
================================================

Wer in der Pruefung einen Rohwert von Hand richtigstellt, sieht sofort,
was daraus folgt. Damit ist die Arbeit aber erst halb getan: im LIMS
steht weiter der alte Stand. Dieses Modul bereitet den Weg zurueck vor -
alles, was sich ohne Datenbank sagen laesst.

Was geschrieben wird
--------------------
Nur Geaendertes, und nur was von Hand angestossen wurde: der
richtiggestellte Rohwert selbst und die Groessen, die sich dadurch
verschoben haben. Eine Zahl, die LabControl schon vorher anders sah als
das LIMS, bleibt unberuehrt - sie ist ein Befund und keine Korrektur,
und ueber sie entscheidet nicht ein Knopf.

Warum es hier ueberschreiben darf
---------------------------------
Der gewoehnliche Export fuellt leere Zeilen und laesst jede vorhandene
Zahl stehen. Hier ist es umgekehrt: eine Korrektur, die den falschen
Wert daneben stehen laesst, waere keine. Deshalb drei Riegel davor -
eine Uebersicht, die Zeile fuer Zeile alt und neu zeigt und bestaetigt
werden muss; eine Sicherung des alten Standes im Ordner "trdf_backup",
bevor die erste Zeile angefasst wird; und der volle Schluessel der
Zeile, die es geben muss. Angelegt wird nichts.
"""

from __future__ import annotations

import csv
import decimal
import io
import os
import re

import lims_db
import protokoll
import trdf
from trdf import D

# Wohin die Sicherung geht - neben das Programm, ein Ordner je Lauf
# nicht noetig: der Dateiname traegt Serie und Zeitpunkt.
ORDNER = "trdf_backup"

# Auf so viele geltende Ziffern geht der geschriebene Wert. Das LIMS
# selbst bucht fuenfzehn; mehr waere keine genauere Aussage, weniger
# eine andere Zahl als die, die daneben in der Uebersicht stand.
STELLEN = 15

# Die beiden Arten von Werten, die den Weg gehen.
ROHWERT = "Rohwert"
BERECHNET = "berechnet"

SPALTEN = ("Zeile", "Probe-Nr.", "Groesse", "Art", "Pruefmethode", "PM_ID",
           "PM_VER", "Ziel", "Wert aktuell LIMS", "Wert neu")

# Wohin ein Wert geht. Ein Rohwert haengt im LIMS an zwei Stellen: als
# Ergebniszeile unter seiner Pruefmethode und am Teilprobenanhang, aus
# dem die Formeln rechnen. Beide muessen mitwandern - deshalb steht in
# der Uebersicht, welche Zeile welche Stellen trifft.
ZIEL_ERGEBNIS = "ERGEBNISSE"
ZIEL_BEIDE = "ERGEBNISSE + Anhang"
ZIEL_KEINS = "keine Zeile"

# Die Sicherung nimmt den ganzen Schluessel und alles, was der Rueckweg
# anfasst. Aus ihr laesst sich der alte Stand wiederherstellen, ohne
# noch einmal in die Datenbank sehen zu muessen.
SPALTEN_BACKUP = ("Serie", "Probe-Nr.", "Groesse", "PROB_ID", "PM_ID",
                  "PM_VER", "UM_ID", "GEGR_ID", "MW_ROH", "MW", "PSTA_ID",
                  "KORREKTUR_FLAG", "FC8", "ROHW_ID", "Anhang MW",
                  "Anhang MW_OLD", "Wert neu")

BLOCK_BACKUP = "Stand vor der Korrektur"

_VERBOTEN = re.compile(r"[^A-Za-z0-9 _.-]")


def zahlfeld(wert) -> str:
    """Eine Zahl, wie das LIMS sie in MW_ROH schreibt.

    Komma statt Punkt, keine Exponenten, kein Tausenderpunkt und
    hoechstens fuenfzehn geltende Ziffern - so, wie die Werte dort schon
    stehen. Eine Zahl in Exponentenschreibweise waere fuer das LIMS kein
    Wert, sondern Text.
    """
    zahl = trdf.zahl(wert)
    if zahl is None:
        return ""
    gerundet = decimal.Context(prec=STELLEN).create_decimal(zahl)
    text = format(gerundet, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


# Was in der Uebersicht steht, wo gar nichts mehr stehen soll. Eine
# leere Zelle liesse sich als "hier geschieht nichts" lesen, und das ist
# das Gegenteil dessen, was geschieht.
LEER_TEXT = "(leer)"


def wertfeld(wert) -> str:
    """Was in MW_ROH geschrieben wird - eine Zahl, ein x oder nichts.

    Das LIMS kennt drei Staende, nicht zwei: eine Zahl, ein „x“ (hier
    soll nichts stehen - so setzt es die Eingabemaske, wenn eine
    Variante den Rohwert nicht braucht) und eine leere Zelle (hier steht
    noch nichts). Alle drei sind Ergebnisse einer Pruefung und muessen
    geschrieben werden koennen; ein Verweis wie „##1093“ wird dabei zum
    x, denn das ist es, was er sagt.
    """
    zahl = trdf.zahl(wert)
    if zahl is not None:
        return zahlfeld(zahl)
    return trdf.MARKE if str(wert if wert is not None else "").strip() else ""


def anzeige(wert, stellen=None) -> str:
    """Derselbe Wert fuer die Uebersicht - mit Namen fuer das Nichts."""
    zahl = trdf.zahl(wert)
    if zahl is not None:
        return berichtszahl(zahl, stellen)
    return trdf.MARKE if str(wert if wert is not None else "").strip() \
        else LEER_TEXT


def bewegt(alt, neu) -> bool:
    """Ist der neue Stand ein anderer als der, der im LIMS steht?

    Drei Faelle, und jeder wird gegen das gehalten, was dort steht: eine
    Zahl gegen die Zahl, ein x gegen alles, was noch keins ist, und das
    Leeren gegen alles, was ueberhaupt dasteht. Ein x ueber ein x zu
    schreiben - oder ueber einen Verweis, der dasselbe sagt - aendert
    nichts und unterbleibt.
    """
    if isinstance(neu, D):
        return not trdf.gleich(neu, alt)
    text = str(alt if alt is not None else "").strip()
    if str(neu or "").strip():                 # ein x
        return not text or trdf.zahl(alt) is not None
    return bool(text)                          # leeren


def verschoben(vorher, nachher) -> bool:
    """Hat die Handeingabe diesen Wert bewegt?

    Verglichen wird die Rechnung ohne die Handwerte mit der Rechnung mit
    ihnen. Nur was sich dabei bewegt, ist eine Korrektur - alles andere
    stand schon vorher so da.
    """
    if isinstance(nachher, D):
        return not trdf.gleich(nachher, vorher)
    return isinstance(vorher, D)


def aenderung(probe: dict, kuerzel: str, art: str, alt, neu,
              zeile: dict = None, name: str = "", anhang: dict = None) -> dict:
    """Eine Zeile der Uebersicht - und spaeter ein Satz fuer die Datenbank."""
    return {"lnr": probe.get("lnr"), "probe": probe.get("probe"),
            "kuerzel": kuerzel, "art": art, "name": name or kuerzel,
            "alt": alt, "neu": neu, "zeile": zeile, "anhang": anhang}


def ziel(eine: dict) -> str:
    """Welche Stellen im LIMS diese Aenderung trifft."""
    if not eine.get("zeile"):
        return ZIEL_KEINS
    return ZIEL_BEIDE if eine.get("anhang") else ZIEL_ERGEBNIS


def gegenueber(eine: dict, stellen=None) -> tuple:
    """Der alte und der neue Wert, wie sie nebeneinander stehen.

    Gerundet wird wie in den Tabellen: die Groesse bestimmt, wie viele
    Nachkommastellen sie traegt - fuenfzehn Ziffern liest niemand, und
    in der Zeile darueber standen sie auch nicht so.

    Eine Ausnahme macht der Fall, in dem das Runden die Aenderung
    verschwinden liesse: zweimal dieselbe Zahl in einer Uebersicht, mit
    der jemand ein Ueberschreiben freigibt, waere die falsche Auskunft.
    Dann stehen beide Werte ungerundet da.
    """
    alt, neu = eine["alt"], eine["neu"]
    if stellen is None:
        return anzeige(alt), anzeige(neu)
    kurz = anzeige(alt, stellen), anzeige(neu, stellen)
    lang = anzeige(alt), anzeige(neu)
    if kurz[0] == kurz[1] and lang[0] != lang[1]:
        return lang
    return kurz


def uebersicht(aenderungen, stellen=None) -> list:
    """Was geschrieben wuerde - alt und neu nebeneinander.

    `stellen` ist, wenn gegeben, eine Auskunft "Kuerzel ->
    Nachkommastellen" fuer die Anzeige. Ohne sie steht die Zahl so da,
    wie sie geschrieben wird.
    """
    zeilen = []
    for eine in aenderungen:
        zeile = eine.get("zeile") or {}
        alt, neu = gegenueber(eine, stellen(eine["kuerzel"])
                              if stellen else None)
        zeilen.append([eine.get("lnr"), eine.get("probe"), eine["kuerzel"],
                       eine["art"], eine.get("name", ""),
                       zeile.get("pm_id", ""), zeile.get("pm_ver", ""),
                       ziel(eine), alt, neu])
    return zeilen


def geleert(aenderungen) -> list:
    """Die Aenderungen, nach denen im LIMS kein Wert mehr steht.

    Beim Zurueckspielen kommt das vor - wo vor der Korrektur nichts
    stand, darf danach auch nichts stehen -, und beim Wechsel der
    Variante: eine „0“ raeumt die Zeile leer. Das ist richtig so und
    soll trotzdem dastehen, bevor jemand zustimmt.

    Gefragt wird nach dem Feld, das geschrieben wird, und nicht danach,
    ob der Wert "wahr" ist: die Zahl Null ist ein Messwert.
    """
    return [eine for eine in aenderungen if not wertfeld(eine.get("neu"))]


def markiert(aenderungen) -> list:
    """Die Aenderungen, nach denen im LIMS ein „x“ steht.

    Kein Messwert und trotzdem eine Aussage: hier soll nichts stehen,
    weil die Variante diesen Rohwert nicht braucht. So haelt es die
    Eingabemaske des LIMS auch.
    """
    return [eine for eine in aenderungen
            if wertfeld(eine.get("neu")) == trdf.MARKE]


def ohne_anhang(aenderungen) -> list:
    """Rohwerte, zu denen keine Zeile am Teilprobenanhang bekannt ist.

    Ein Rohwert haengt im LIMS an zwei Stellen. Fehlt die zweite, wird
    nur die Ergebniszeile geschrieben - und danach stehen im LIMS zwei
    verschiedene Staende nebeneinander, von denen der unsichtbare der
    ist, aus dem gerechnet wird.

    Beim Korrigieren faellt das kaum vor. Beim Zurueckspielen schon:
    aeltere Sicherungen wurden ohne ROHW_ID geschrieben, weil LabControl
    die Anhangzeile damals nicht gefunden hat. Wer so eine Datei
    zurueckspielt, stellt die Ergebniszeile zurueck und laesst den
    Anhang auf dem korrigierten Wert stehen. Das soll vorher dastehen.
    """
    return [eine for eine in aenderungen
            if eine.get("art") == ROHWERT and not eine.get("anhang")]


def ohne_zeile(aenderungen) -> list:
    """Die Aenderungen, zu denen es im LIMS keine Ergebniszeile gibt."""
    return [eine for eine in aenderungen if not eine.get("zeile")]


def schon_korrigiert(aenderungen) -> list:
    """Die Zeilen, die im LIMS bereits ein Korrekturkennzeichen tragen.

    Kein Hindernis, aber eine Auskunft: an dieser Zeile war schon einmal
    jemand. Entweder wird gerade zum zweiten Mal dieselbe Stelle
    gedreht, oder zwei Pruefer sind an derselben Serie - beides sollte
    man wissen, bevor man schreibt.
    """
    return [eine for eine in aenderungen
            if str((eine.get("zeile") or {}).get("korrektur_flag")
                   or "").strip()]


def satz(eine: dict, psta_id=None, korrektur_flag=None, fc8=None) -> dict:
    """Der Satz, den die Anweisung bekommt - ohne Ueberraschungen darin."""
    zeile = eine.get("zeile") or {}
    return {"wert": wertfeld(eine["neu"]),
            "fc8": lims_db.TRDF_FC8 if fc8 is None else fc8,
            "psta_id": (lims_db.PSTA_GESENDET if psta_id is None
                        else psta_id),
            "korrektur_flag": (lims_db.KORREKTUR_FLAG
                               if korrektur_flag is None else korrektur_flag),
            "prob_id": zeile.get("prob_id"), "pm_id": zeile.get("pm_id"),
            "pm_ver": zeile.get("pm_ver"), "um_id": zeile.get("um_id"),
            "gegr_id": zeile.get("gegr_id")}


def saetze(aenderungen, **angaben) -> list:
    """Alle Saetze, die eine Ergebniszeile haben."""
    return [satz(eine, **angaben) for eine in aenderungen if eine.get("zeile")]


def anhangsatz(eine: dict) -> dict:
    """Der Satz fuer den Teilprobenanhang - der Wert und sein Schluessel.

    Der bisherige Wert wandert dabei nach MW_OLD; er steht nicht im
    Satz, weil die Anweisung ihn aus der Zeile selbst nimmt.
    """
    anhang = eine.get("anhang") or {}
    return {"wert": wertfeld(eine["neu"]), "prob_id": anhang.get("prob_id"),
            "um_id": anhang.get("um_id"), "rohw_id": anhang.get("rohw_id")}


def anhangsaetze(aenderungen) -> list:
    """Dieselben Werte fuer die zweite Stelle, an der sie haengen.

    Nur Rohwerte: die berechneten Groessen stehen nicht am Anhang, sie
    entstehen ja erst aus ihm.
    """
    return [anhangsatz(eine) for eine in aenderungen
            if eine.get("anhang") and eine.get("zeile")]


def anhanghinweise(aenderungen, serie: str) -> list:
    return [f"TRDF-Korrektur {serie} (Anhang): Probe {eine.get('probe')}, "
            f"{eine['kuerzel']} von "
            f"{zahlfeld((eine.get('anhang') or {}).get('mw')) or trdf.MARKE} "
            f"auf {anzeige(eine['neu'])}"
            for eine in aenderungen
            if eine.get("anhang") and eine.get("zeile")]


def hinweise(aenderungen, serie: str) -> list:
    """Je Satz ein Satz in Worten - fuer das Aenderungsprotokoll."""
    return [f"TRDF-Korrektur {serie}: Probe {eine.get('probe')}, "
            f"{eine['kuerzel']} von {zahlfeld(eine['alt']) or trdf.MARKE} "
            f"auf {anzeige(eine['neu'])}"
            for eine in aenderungen if eine.get("zeile")]


# --------------------------------------------------------------------------
# Die Sicherung
# --------------------------------------------------------------------------

def backup_zeilen(serie: str, aenderungen) -> list:
    """Der Stand, wie er jetzt in der Datenbank steht."""
    zeilen = []
    for eine in aenderungen:
        zeile = eine.get("zeile") or {}
        anhang = eine.get("anhang") or {}
        zeilen.append([serie, eine.get("probe"), eine["kuerzel"],
                       zeile.get("prob_id", ""), zeile.get("pm_id", ""),
                       zeile.get("pm_ver", ""), zeile.get("um_id", ""),
                       zeile.get("gegr_id", ""), zeile.get("mw_roh", ""),
                       zeile.get("mw", ""), zeile.get("psta_id", ""),
                       zeile.get("korrektur_flag", ""), zeile.get("fc8", ""),
                       anhang.get("rohw_id", ""), anhang.get("mw", ""),
                       anhang.get("mw_old", ""), wertfeld(eine["neu"])])
    return zeilen


def dateiname(serie: str, zeitpunkt) -> str:
    """Serie und Zeitpunkt im Namen - je Lauf eine eigene Sicherung.

    Der Zeitpunkt gehoert dazu: wer zweimal korrigiert, hat sonst nur
    noch den vorletzten Stand, und der ist der falsche.
    """
    name = _VERBOTEN.sub("", str(serie or "Serie")).strip() or "Serie"
    return f"{name} {zeitpunkt:%Y-%m-%d %H%M%S}.csv"


def backup_schreiben(ordner: str, serie: str, aenderungen,
                     zeitpunkt) -> str:
    """Legt die Sicherung ab und gibt ihren Pfad - "" wenn es nicht ging.

    Ohne sie wird nicht geschrieben. Der Aufrufer bricht ab, wenn hier
    nichts zurueckkommt: ein ueberschriebener Wert ohne Sicherung ist
    unwiederbringlich.
    """
    ziel = os.path.join(ordner, dateiname(serie, zeitpunkt))
    inhalt = lims_db.csv_bloecke([(f"{BLOCK_BACKUP} - {serie}",
                                   list(SPALTEN_BACKUP),
                                   backup_zeilen(serie, aenderungen))])
    try:
        os.makedirs(ordner, exist_ok=True)
        with open(ziel, "wb") as datei:
            datei.write(inhalt)
    except OSError:
        return ""
    return ziel


def blatt_schreiben(ordner: str, serie: str, aenderungen,
                    zeitpunkt) -> str:
    """Dieselben Aenderungen als Blatt zum Ansehen und Drucken."""
    ziel = os.path.join(ordner, "Aenderungen " + dateiname(serie, zeitpunkt))
    inhalt = lims_db.csv_bloecke([(f"Von Hand geaenderte Werte - {serie}",
                                   list(SPALTEN), uebersicht(aenderungen))])
    try:
        os.makedirs(ordner, exist_ok=True)
        with open(ziel, "wb") as datei:
            datei.write(inhalt)
    except OSError:
        return ""
    return ziel


# Wie viele Eintraege der Korrekturlog haelt. Das Aenderungsprotokoll
# neben dem Programm fuehrt alles, was LabControl je geschrieben hat;
# dieser hier steht bei den Sicherungen und beantwortet eine engere
# Frage: was hat die TRDF-Pruefung in diese Datenbank geschrieben?
# Fuenftausend Eintraege sind mehrere Serien weit zurueck.
LOGZAHL = 5000


def protokollieren(ordner: str, benutzer: str, saetze, hinweise=None,
                   sql=None) -> int:
    """Schreibt die Korrekturen in den Log neben den Sicherungen.

    Dieselbe Anweisung, dieselbe Schreibweise wie im Aenderungsprotokoll -
    nur eben dort, wo auch der alte Stand liegt. Wer eine Sicherung
    zurueckspielen will, findet daneben, was seinerzeit geschrieben wurde.
    """
    if not saetze:
        return 0
    buch = protokoll.Protokoll(ordner, benutzer, hoechstzahl=LOGZAHL)
    return buch.viele(sql or lims_db.trdf_export_sql(), saetze, hinweise)


# --------------------------------------------------------------------------
# Der Weg zurueck aus der Sicherung
# --------------------------------------------------------------------------
# Es gibt einen Weg, der ueberschreibt - also muss es einen zurueck
# geben. Gelesen wird die Sicherung, die vor dem Schreiben angelegt
# wurde: sie traegt den ganzen Schluessel und jede Spalte, die der
# Rueckweg angefasst hat. Geschrieben wird mit denselben Anweisungen,
# nur mit den alten Werten darin - und wieder erst nach einer
# bestaetigten Uebersicht.


def gesichertes_lesen(pfad: str) -> list:
    """Liest eine Sicherung und gibt ihre Zeilen als Woerterbuecher.

    Genommen wird nur, was zum Block der Sicherung gehoert: die Datei
    traegt eine Ueberschrift ueber der Tabelle, und Excel haengt beim
    Speichern gern Leerzeilen an.
    """
    with open(pfad, "rb") as datei:
        text = datei.read().decode("utf-8-sig", "replace")
    zeilen = list(csv.reader(io.StringIO(text), delimiter=";"))
    kopf, gefunden = None, []
    for zeile in zeilen:
        if kopf is None:
            if zeile[:1] == [SPALTEN_BACKUP[0]]:
                kopf = zeile
            continue
        if not any(feld.strip() for feld in zeile):
            continue
        gefunden.append(dict(zip(kopf, zeile)))
    if kopf is None:
        raise Einlesefehler(f"Das ist keine Sicherung: {os.path.basename(pfad)}")
    return gefunden


class Einlesefehler(ValueError):
    """Die Datei ist keine Sicherung oder unvollstaendig."""


def _ganz(wert):
    """Eine Zahl aus der Sicherung - Schluessel sind ganze Zahlen."""
    text = str(wert or "").strip()
    if not text:
        return None
    try:
        return int(D(text.replace(",", ".")))
    except (ValueError, decimal.InvalidOperation):
        return None


def zurueck(zeilen) -> list:
    """Aus den Zeilen einer Sicherung wieder Aenderungen machen.

    Alt und neu tauschen die Rollen: was damals geschrieben wurde, ist
    jetzt der Stand im LIMS, und was damals dastand, soll wieder
    hinein.
    """
    gefunden = []
    for zeile in zeilen:
        ergebnis = {"prob_id": _ganz(zeile.get("PROB_ID")),
                    "pm_id": _ganz(zeile.get("PM_ID")),
                    "pm_ver": _ganz(zeile.get("PM_VER")),
                    "um_id": _ganz(zeile.get("UM_ID")),
                    "gegr_id": _ganz(zeile.get("GEGR_ID")),
                    "mw_roh": zeile.get("MW_ROH", ""),
                    "mw": zeile.get("MW", ""),
                    "psta_id": _ganz(zeile.get("PSTA_ID")),
                    "korrektur_flag": zeile.get("KORREKTUR_FLAG", ""),
                    "fc8": zeile.get("FC8", "")}
        rohw = _ganz(zeile.get("ROHW_ID"))
        anhang = None
        if rohw is not None:
            anhang = {"prob_id": ergebnis["prob_id"], "um_id": ergebnis["um_id"],
                      "rohw_id": rohw, "mw": zeile.get("Anhang MW", ""),
                      "mw_old": zeile.get("Anhang MW_OLD", "")}
        gefunden.append({
            "lnr": _ganz(zeile.get("PROB_ID")),
            "probe": zeile.get("Probe-Nr.", ""), "kuerzel": zeile.get(
                "Groesse", ""),
            "art": ROHWERT if rohw is not None else BERECHNET,
            "name": zeile.get("Groesse", ""),
            "alt": zeile.get("Wert neu", ""),          # der Stand von jetzt
            "neu": zeile.get("MW_ROH", ""),            # der Stand von damals
            "zeile": ergebnis, "anhang": anhang})
    return gefunden


def zuruecksaetze(aenderungen) -> list:
    """Die Ergebniszeilen auf ihren gesicherten Stand - mit Kennzeichen.

    Zurueckgestellt wird die ganze Zeile: auch der Bearbeitungsstand,
    das Korrekturkennzeichen und FC8 waren vor der Korrektur andere.
    """
    gefunden = []
    for eine in aenderungen:
        zeile = eine.get("zeile") or {}
        gefunden.append({"wert": str(eine["neu"]).strip(),
                         # MW stand vor der Korrektur nicht zwingend auf
                         # demselben Wert wie MW_ROH - die Sicherung
                         # haelt beide fest, und beide gehen zurueck.
                         "mw": str(zeile.get("mw") or "").strip(),
                         "fc8": zeile.get("fc8") or "",
                         "psta_id": zeile.get("psta_id"),
                         "korrektur_flag": zeile.get("korrektur_flag") or "",
                         "prob_id": zeile.get("prob_id"),
                         "pm_id": zeile.get("pm_id"),
                         "pm_ver": zeile.get("pm_ver"),
                         "um_id": zeile.get("um_id"),
                         "gegr_id": zeile.get("gegr_id")})
    return gefunden


def zurueck_anhangsaetze(aenderungen) -> list:
    """Der Anhang auf seinen gesicherten Stand - MW und MW_OLD."""
    gefunden = []
    for eine in aenderungen:
        anhang = eine.get("anhang")
        if not anhang:
            continue
        gefunden.append({"wert": str(anhang.get("mw") or "").strip(),
                         "alt": anhang.get("mw_old") or "",
                         "prob_id": anhang.get("prob_id"),
                         "um_id": anhang.get("um_id"),
                         "rohw_id": anhang.get("rohw_id")})
    return gefunden


def zurueckhinweise(aenderungen, name: str) -> list:
    return [f"TRDF-Korrektur zurueckgespielt aus {name}: Probe "
            f"{eine.get('probe')}, {eine['kuerzel']} auf {eine['neu']}"
            for eine in aenderungen]


# --------------------------------------------------------------------------
# Der Exportbericht
# --------------------------------------------------------------------------
# Was der Weg in das LIMS bewegt hat, noch einmal von der anderen Seite
# gesehen: nicht ein Wert je Zeile, sondern eine Probe je Zeile und
# eine Spalte je Groesse. So sieht man auf einen Blick, welche Proben
# angefasst wurden und wo - die Uebersicht vor dem Schreiben beantwortet
# das nicht, sie ist nach Werten sortiert und dafuer zu lang.

BERICHT_KOPF = ("Zeile", "Probe-Nr.")

# Alter Wert und neuer in derselben Zelle - der Bericht soll ohne
# Zurueckblaettern lesbar sein.
BERICHT_PFEIL = " → "


def berichtsspalten(aenderungen) -> list:
    """Die Groessen dieses Exports - Rohwerte zuerst, dann Gerechnetes.

    Die Rohwerte sind die Ursache, die berechneten Groessen die Folge;
    in dieser Reihenfolge liest sich die Zeile.
    """
    roh, berechnet = [], []
    for eine in aenderungen:
        ziel = roh if eine.get("art") == ROHWERT else berechnet
        if eine["kuerzel"] not in ziel:
            ziel.append(eine["kuerzel"])
    return roh + [k for k in berechnet if k not in roh]


def berichtszahl(wert, stellen=None) -> str:
    """Der Wert fuer eine Zelle des Berichts.

    Ohne `stellen` steht die Zahl so da, wie sie geschrieben wurde -
    fuenfzehn Ziffern, wie in der Sicherung. Mit `stellen` wird
    gerundet: auf dem Bildschirm stehen zwei solche Zahlen mit einem
    Pfeil dazwischen in einer Spalte, und dafuer sind fuenfzehn Ziffern
    zu viel. Die Datei behaelt sie.
    """
    if stellen is None:
        return zahlfeld(wert)
    zahl = trdf.zahl(wert)
    if zahl is None:
        return ""
    try:
        fest = zahl.quantize(D(1).scaleb(-stellen),
                             rounding=decimal.ROUND_HALF_UP)
    except decimal.InvalidOperation:
        return zahlfeld(wert)
    return str(fest).replace(".", ",")


def berichtsfeld(eine: dict, stellen=None) -> str:
    """Was in der Zelle steht: der alte Wert, ein Pfeil, der neue."""
    return (f"{anzeige(eine['alt'], stellen)}{BERICHT_PFEIL}"
            f"{anzeige(eine['neu'], stellen)}")


def bericht(aenderungen, stellen=None) -> tuple:
    """Kopf und Zeilen des Berichts - eine Probe je Zeile.

    Zurueck kommt, was `Eingaberaster.fuellen` erwartet: die Spalten und
    Paare aus Probennummer und Werten. `stellen` ist, wenn gegeben, eine
    Auskunft "Kuerzel -> Nachkommastellen" fuer die Anzeige.
    """
    spalten = list(BERICHT_KOPF) + berichtsspalten(aenderungen)
    zeilen, nach_probe = [], {}
    for eine in aenderungen:
        probe = str(eine.get("probe") or "")
        werte = nach_probe.get(probe)
        if werte is None:
            werte = {"Zeile": eine.get("lnr"), "Probe-Nr.": probe}
            nach_probe[probe] = werte
            zeilen.append((probe, werte))
        werte[eine["kuerzel"]] = berichtsfeld(
            eine, stellen(eine["kuerzel"]) if stellen else None)
    return spalten, zeilen


def berichtszeilen(aenderungen) -> list:
    """Derselbe Bericht als flache Liste - fuer die CSV."""
    spalten, zeilen = bericht(aenderungen)
    return [[werte.get(name, "") for name in spalten]
            for _, werte in zeilen]


def bericht_schreiben(ordner: str, serie: str, aenderungen,
                      zeitpunkt) -> str:
    """Legt den Bericht neben die Sicherung - "" wenn es nicht ging."""
    ziel = os.path.join(ordner, "Bericht " + dateiname(serie, zeitpunkt))
    spalten, _ = bericht(aenderungen)
    inhalt = lims_db.csv_bloecke([(f"In das LIMS geschrieben - {serie}",
                                   spalten, berichtszeilen(aenderungen))])
    try:
        os.makedirs(ordner, exist_ok=True)
        with open(ziel, "wb") as datei:
            datei.write(inhalt)
    except OSError:
        return ""
    return ziel
