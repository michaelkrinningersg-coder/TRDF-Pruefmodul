# -*- coding: utf-8 -*-
"""Drucken, was auf dem Bildschirm steht.

Gedruckt wird dasselbe wie beim CSV-Export: die Tabellen des sichtbaren
Reiters, nichts sonst. Keine Erklaerungen, keine Knoepfe, keine
Reiterleiste - auf Papier gehoert das, was Zahlen traegt.

Der Weg dorthin ist eine HTML-Datei. Das klingt nach Umweg, ist aber der
kuerzeste, den es unter Windows ohne Fremdbibliothek gibt: der Browser
kann umbrechen, Kopfzeilen wiederholen und Querformat, und `os.startfile`
schickt die Datei mit dem Verb "print" an den Standarddrucker. Ein
eigener Zeichensatz-Umbruch waere mehr Code und schlechteres Papier.

Zahlen stehen rechtsbuendig, wenn eine Spalte durchgaengig Zahlen
enthaelt - so, wie sie auch am Bildschirm stehen. Farben kommen nicht
mit: sie tragen am Bildschirm eine Warnung, auf einem Schwarzweissdrucker
waeren sie ein Grauton unter anderen.
"""
import datetime
import html
import os
import re
import subprocess
import sys
import tempfile

# Ein Wert gilt als Zahl, wenn er wie eine aussieht - mit deutschem
# Komma, Tausenderpunkt, Vorzeichen und dem "<" der Grenzwerte.
ZAHL = re.compile(r"^[<>]?\s*[-+]?[\d.]*\d(?:,\d+)?\s*%?$")

# Der Abstand zwischen zwei Tabellen desselben Reiters. Ein Reiter zeigt
# manchmal mehrere - je Kontrollstandard eine -, und auf Papier muessen
# sie auseinanderzuhalten sein.
ABSTAND_MM = 10

# Was auf eine Seite passt. Consolas in 8pt ist rund 1,7 mm je Zeichen;
# dazu je Spalte etwas Rand und Rahmen. A4 hoch traegt 210 mm, quer 297,
# abzueglich der Raender.
ZEICHEN_MM = 1.7
SPALTE_MM = 3.0
BREITE_HOCH_MM = 210 - 2 * 12
BREITE_QUER_MM = 297 - 2 * 12

# Wie hoch eine Tabellenzeile in 8pt steht, und was nach Kopf und
# Ueberschrift von der Seite uebrig bleibt.
ZEILE_MM = 4.0
KOPF_MM = 20
HOEHE_HOCH_MM = 297 - 2 * 12
HOEHE_QUER_MM = 210 - 2 * 12


def zeilen_je_seite(lage: str) -> int:
    """Wie viele Tabellenzeilen auf ein Blatt passen - grob gerechnet."""
    hoehe = HOEHE_QUER_MM if lage == "landscape" else HOEHE_HOCH_MM
    return max(1, int((hoehe - KOPF_MM) / ZEILE_MM))


def _zahlenspalten(spalten, zeilen) -> set:
    """Welche Spalten durchgaengig Zahlen tragen."""
    zahlen = set()
    for nummer in range(len(spalten)):
        werte = [str(zeile[nummer]).strip()
                 for zeile in zeilen if nummer < len(zeile)]
        gefuellt = [wert for wert in werte if wert]
        if gefuellt and all(ZAHL.match(wert) for wert in gefuellt):
            zahlen.add(nummer)
    return zahlen


def tabellenbreite(spalten, zeilen) -> float:
    """Wie breit die Tabelle gedruckt ungefaehr wird - in Millimetern.

    Gerechnet wird mit der laengsten Zelle je Spalte: die Schrift ist
    eine Festbreitenschrift, da geht das auf.
    """
    breite = 0.0
    for nummer, spalte in enumerate(spalten):
        zeichen = len(str(spalte))
        for zeile in zeilen:
            if nummer < len(zeile):
                zeichen = max(zeichen, len(str(zeile[nummer])))
        breite += zeichen * ZEICHEN_MM + SPALTE_MM
    return breite


def ausrichtung(bloecke) -> str:
    """"portrait" oder "landscape" - je nachdem, was noetig ist.

    Hochkant ist die Vorgabe: so kommt das Blatt aus dem Drucker, wie
    man es erwartet, und die meisten Reiter haben eine Handvoll Spalten.
    Erst wenn die breiteste Tabelle nicht mehr auf die Seite passt, wird
    gedreht - das ist immer noch besser, als sie abzuschneiden.
    """
    breiteste = max((tabellenbreite(spalten, zeilen)
                     for _, spalten, zeilen in bloecke), default=0)
    return "portrait" if breiteste <= BREITE_HOCH_MM else "landscape"


def _tabelle(titel, spalten, zeilen, passt_aufs_blatt=True) -> str:
    """Eine Tabelle als Block.

    `passt_aufs_blatt` entscheidet, ob der Block zusammengehalten wird.
    Zusammenhalten heisst fuer den Browser: lieber eine leere Seite als
    ein Umbruch mittendrin. Bei einer Handvoll Zeilen ist das richtig -
    bei dreihundert Proben schiebt es die ganze Tabelle auf Seite zwei,
    und Seite eins kommt mit nichts als der Kopfzeile aus dem Drucker.
    Genau das war der Fehler in Ergebnis und ErgVFak.
    """
    zahlen = _zahlenspalten(spalten, zeilen)
    klasse = "block" if passt_aufs_blatt else "block lang"
    teile = [f'<section class="{klasse}">']
    if titel:
        teile.append(f"<h2>{html.escape(str(titel))}</h2>")
    teile.append("<table><thead><tr>")
    for nummer, spalte in enumerate(spalten):
        klasse = ' class="zahl"' if nummer in zahlen else ""
        teile.append(f"<th{klasse}>{html.escape(str(spalte))}</th>")
    teile.append("</tr></thead><tbody>")
    for zeile in zeilen:
        teile.append("<tr>")
        for nummer in range(len(spalten)):
            wert = zeile[nummer] if nummer < len(zeile) else ""
            klasse = ' class="zahl"' if nummer in zahlen else ""
            teile.append(f"<td{klasse}>{html.escape(str(wert))}</td>")
        teile.append("</tr>")
    teile.append("</tbody></table></section>")
    return "".join(teile)


def seite(titel: str, untertitel: str, bloecke, stand=None,
          dialog=True, vorspann="", stil="") -> str:
    """Die Druckseite als HTML.

    `bloecke` sind (Titel, Ueberschriften, Zeilen) - dieselbe Form, die
    auch der CSV-Export bekommt. Mehrere Tabellen stehen mit Abstand
    untereinander und werden nach Moeglichkeit nicht auseinandergerissen.

    `dialog` laesst die Seite beim Oeffnen den Druckdialog rufen. Dort
    steht, was zum Drucken gehoert und was dieses Programm nicht wissen
    kann: welcher Drucker, welches Fach, ein- oder beidseitig. Ueber
    "Drucken mit Systemdialog" kommt der volle Windows-Dialog dazu.

    `vorspann` steht als fertiges HTML ueber den Tabellen - dort haengt
    das Bild einer Regelkarte. `stil` kommt dann zusaetzlich in den
    Kopf; beides wird ungeprueft uebernommen und darf deshalb nur aus
    dem Programm kommen, nie aus einer Datei oder aus der Datenbank.
    """
    stand = stand or datetime.datetime.now()
    kopf = html.escape(titel)
    unter = html.escape(untertitel)
    zeitpunkt = html.escape(stand.strftime("%d.%m.%Y %H:%M"))
    lage = ausrichtung(bloecke)
    # Ein Block wird nur zusammengehalten, solange er auch zusammen auf
    # ein Blatt passt - sonst haelt der Browser ihn zusammen, indem er
    # ihn ganz auf die naechste Seite schiebt.
    grenze = zeilen_je_seite(lage)
    inhalt = "".join(_tabelle(titel, spalten, zeilen,
                              passt_aufs_blatt=len(zeilen) <= grenze)
                     for titel, spalten, zeilen in bloecke)
    ruf = ("<script>window.addEventListener(\"load\", "
           "function () { window.print(); });</script>" if dialog else "")
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>{kopf}</title>
<style>
  @page {{ size: A4 {lage}; margin: 12mm; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; font-size: 9pt;
          color: #000; margin: 0; }}
  header {{ border-bottom: 1pt solid #000; padding-bottom: 4pt;
            margin-bottom: 8pt; }}
  h1 {{ font-size: 12pt; margin: 0 0 2pt 0; }}
  .unter {{ font-size: 8pt; }}
  .stand {{ font-size: 8pt; float: right; }}
  .block {{ margin-bottom: {ABSTAND_MM}mm; page-break-inside: avoid; }}
  /* Eine Tabelle, die laenger ist als ein Blatt, darf umbrechen. Ohne
     das schiebt der Browser sie als Ganzes auf die naechste Seite und
     die erste bleibt leer. */
  .block.lang {{ page-break-inside: auto; }}
  h2 {{ font-size: 10pt; margin: 0 0 3pt 0; page-break-after: avoid; }}
  /* Umbrochen wird zwischen Zeilen, nie mitten in einer. */
  tr {{ page-break-inside: avoid; }}
  /* Nur so breit wie noetig: eine Tabelle mit drei Spalten soll nicht
     ueber die halbe Seite gezogen werden. */
  table {{ border-collapse: collapse; width: auto; max-width: 100%; }}
  th, td {{ border: 0.5pt solid #999; padding: 1.5pt 4pt;
            font-family: Consolas, "Courier New", monospace;
            font-size: 8pt; }}
  th {{ background: #eee; text-align: left; }}
  /* Zahlen bleiben zusammen; eine lange Bezeichnung darf umbrechen,
     sonst laeuft ein Lauf mit zwanzig Elementen ueber den Rand. */
  td.zahl, th.zahl {{ text-align: right; white-space: nowrap; }}
  thead {{ display: table-header-group; }}
{stil}
</style></head><body>
<header><span class="stand">{zeitpunkt}</span>
<h1>{kopf}</h1><div class="unter">{unter}</div></header>
{vorspann}
{inhalt}
{ruf}</body></html>
"""


def ablegen(text: str, name: str, ordner=None) -> str:
    """Schreibt die Druckseite und gibt ihren Pfad zurueck."""
    sauber = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "Druck"
    ziel = os.path.join(ordner or tempfile.gettempdir(), sauber + ".html")
    with open(ziel, "w", encoding="utf-8") as datei:
        datei.write(text)
    return ziel


# Der Riegel gegen die Schaltflaeche, die niemand druecken kann.
#
# `drucken` gibt die Datei an die Arbeitsoberflaeche weiter, und die
# entscheidet, was damit geschieht. Vor einem Menschen ist das richtig:
# der Browser kommt, der Druckdialog kommt. In einem Lauf ohne Menschen
# ist es ein Haenger - und zwar ein teurer, weil er nicht dort
# auffaellt, wo er entsteht.
#
# Gesehen am Build vom 18.09.2026: zwei Pruefungen legten eine CSV ab
# und liessen Windows sie oeffnen. Windows kannte die Endung nicht und
# stellte "Wie moechten Sie diese Datei oeffnen?" auf den Schirm - ein
# Fenster, das den Fokus nimmt und auf einen Klick wartet. Sieben
# Sekunden spaeter fiel `test_eingaberaster`, weil sein Pfeiltastendruck
# in dieses Fenster ging; drei Minuten spaeter blieb
# `test_vergleichsfenster` stehen, weil `os.startfile` auf die Antwort
# wartete, die keiner gab. Beide Pruefungen haben mit Drucken nichts zu
# tun, und keine der beiden Meldungen zeigte auf die Ursache.
#
# Steht diese Umgebungsvariable, wird nichts weitergegeben. Das ist
# keine Vorkehrung fuer die Pruefungen allein: jeder Lauf ohne Bediener
# will das - eine Datei ablegen, ja; sie der Oberflaeche in die Hand
# druecken, nein.
OHNE_OBERFLAECHE = "TRDF_PRUEFMODUL_NICHT_OEFFNEN"


def oberflaeche_erlaubt() -> bool:
    """Ob eine Datei der Arbeitsoberflaeche uebergeben werden darf."""
    return not os.environ.get(OHNE_OBERFLAECHE, "").strip()


def drucken(pfad: str) -> str:
    """Oeffnet die Seite, damit der Druckdialog kommt.

    Nicht still an den Standarddrucker: welcher Drucker, welches Fach,
    ein- oder beidseitig - das entscheidet sich am Geraet und nicht hier.
    Deshalb geht die Seite an den Browser, und der ruft beim Laden seinen
    Druckdialog auf; ueber "Drucken mit Systemdialog" liegt der volle
    Windows-Dialog mit Fach und Duplex einen Klick daneben.

    Zurueck kommt, was geschehen ist - fuer die Meldung im Fenster. Die
    Datei steht in jedem Fall da; "abgelegt" heisst, dass sie geschrieben
    ist und der Dialog ausblieb.
    """
    if not oberflaeche_erlaubt():
        return "abgelegt"
    if sys.platform.startswith("win"):
        try:
            os.startfile(pfad)               # noqa: S606  (Windows-eigen)
            return "dialog"
        except OSError:
            return "abgelegt"
    for befehl in (["xdg-open", pfad],):
        try:
            subprocess.run(befehl, check=True, capture_output=True)
            return "dialog"
        except (OSError, subprocess.SubprocessError):
            continue
    return "abgelegt"
