"""
TRDF-Pruefmodul - alle Pruefungen nebeneinander, jede mit einer Frist
=====================================================================

Der Bau-Ablauf rief bisher achtundfuenfzig Zeilen `python test_x.py`
auf. Das hatte zwei Nachteile, und beide haben heute Zeit gekostet.

Der erste: eine neue Testdatei wirkt erst, wenn jemand daran denkt,
sie in die YAML-Datei nachzutragen. Vergisst er es, ist die Datei da,
sieht wie eine Pruefung aus, und niemand fuehrt sie aus. Hier wird
deshalb nichts aufgezaehlt: gefunden wird, was `test_*.py` heisst und
neben dieser Datei liegt.

Der zweite, und das ist der Grund fuer diese Datei: **eine haengende
Pruefung war nicht zu finden.** Bleibt ein einzelner Aufruf stehen -
ein Fenster, das auf eine Antwort wartet, ein Dialog, den auf dem
Bau-Rechner niemand wegklickt -, dann laeuft der Schritt, bis GitHub
ihn nach sechs Stunden abschneidet. Das Log ist bis dahin nicht zu
lesen, und am Ende steht kein Name, sondern nur "abgebrochen". Hier
bekommt jede Datei eine Frist. Wird sie gerissen, wird der Vorgang
beendet, der Name steht im Log, und der Schritt schlaegt fehl - nach
Minuten statt nach Stunden.

Dazu eine Kleinigkeit, die im Log den Unterschied macht: geschrieben
wird sofort und nicht gepuffert. So sagt selbst ein Log, das mitten
im Satz abbricht, noch, wo es abgebrochen ist.

Mehrere gleichzeitig
--------------------
Die Dateien laufen nebeneinander, so viele wie der Rechner Kerne hat.
Das ist hier ohne Risiko und spart auf dem Bau-Rechner Minuten: jede
Pruefdatei laeuft ohnehin in ihrem eigenen Vorgang, keine haengt von
einer anderen ab, und was sie schreiben, schreiben sie in eigene
Ordner (`tempfile`). Gemessen im Bau vom 16.9.: 290 s der Reihe nach,
und davon 225 s in drei Dateien - nebeneinander ist die Sammlung so
lang wie ihre langsamste Datei.

Damit das Log lesbar bleibt, traegt **jede** Zeile den Namen ihrer
Datei. Der Reihe nach reichte der Name vor dem Lauf; nebeneinander
liefen sonst zwei Ausgaben ineinander, und bei einem Abbruch waere
nicht zu sehen, welche Datei haengt. Genau das war der Grund fuer
diese Datei, und er gilt weiter.

Aufruf:
    python pruefungen_laufen.py             # alle, Frist 300 s
    python pruefungen_laufen.py --frist 60  # kuerzere Frist
    python pruefungen_laufen.py --einzeln   # der Reihe nach
    python pruefungen_laufen.py --gleichzeitig 4
    python pruefungen_laufen.py test_qpreiter.py test_qpdaten.py
"""

from __future__ import annotations

import concurrent.futures
import os
import subprocess
import sys
import time
from pathlib import Path

# Nur fuer den Namen der Umgebungsvariablen. Er steht dort, wo er
# gelesen wird - zwei Schreibweisen an zwei Stellen liefen auseinander,
# und dann setzt die eine, was die andere nicht liest.
import druck

# Fuenf Minuten je Datei. Die langsamste Pruefung der Sammlung braucht
# unter Linux rund zwanzig Sekunden; unter Windows ist Tk deutlich
# langsamer, deshalb der grosse Abstand. Wer die Frist reisst, haengt -
# er ist nicht bloss langsam.
FRIST = 300

# Wie viele Dateien nebeneinander laufen: **so viele wie der Rechner
# Kerne hat**, hoechstens acht.
#
# Nicht mehr als Kerne, und das ist eine Erfahrung und keine
# Ueberlegung. Die Ueberlegung sprach dafuer: eine Pruefdatei rechnet
# kaum, sie startet Python und baut Tk-Fenster auf - unter `pytest`
# ist der langsamste echte Test 0,7 s, waehrend die Sammlung Minuten
# braucht. Also sollte ein weiterer Vorgang laufen koennen, solange
# gewartet wird.
#
# Gemessen auf dem Bau-Rechner (zwei Kerne) hielt das nicht:
#
#     der Reihe nach          290 s
#     zwei nebeneinander      131 s, dann 277 s
#     acht nebeneinander      251 s, dann ein Haenger
#
# Der Haenger war `test_vergleichsfenster.py`, das hier in einer
# Sekunde durchlaeuft und dort die Frist von fuenf Minuten riss.
# Woran es lag, ist nicht bewiesen - acht Tk-Vorgaenge auf zwei Kernen
# sind ein Verdacht und kein Befund. Aber gewonnen war dabei nichts,
# und ein Bau, der gelegentlich haengt, ist teurer als eine Minute.
#
# Nach oben begrenzt, weil jeder Vorgang Speicher fuer seine
# Tk-Fenster braucht und die Sammlung ohnehin nicht kuerzer werden
# kann als ihre langsamste Datei.
GLEICHZEITIG_HOECHSTENS = 8
JE_KERN = 1


def gleichzeitig_vorgabe() -> int:
    """So viele Dateien nebeneinander, wie der Rechner tragen kann."""
    kerne = os.cpu_count() or 1
    return max(1, min(kerne * JE_KERN, GLEICHZEITIG_HOECHSTENS))


HIER = Path(__file__).resolve().parent


def testdateien(ordner: Path = HIER) -> list[Path]:
    """Alle Pruefdateien, in der Reihenfolge ihres Namens.

    Die Reihenfolge ist der Sortierung des Namens und nicht der
    Wichtigkeit: eine Pruefung darf von keiner anderen abhaengen, und
    eine feste Reihenfolge macht zwei Laeufe vergleichbar.
    """
    return sorted(ordner.glob("test_*.py"))


def sagen(text: str) -> None:
    """Schreibt sofort. Ein gepuffertes Log hilft bei einem Haenger
    nicht - die letzte Zeile waere genau die, die fehlt."""
    print(text, flush=True)


# Was den Kindprozessen mitgegeben wird.
#
# Eine Pruefung darf die Arbeitsoberflaeche nicht anfassen. Zwei von
# ihnen legen eine Datei ab und liessen sie bisher oeffnen - auf dem
# Bau-Rechner heisst das: Windows stellt "Wie moechten Sie diese Datei
# oeffnen?" auf einen Schirm, den niemand sieht. Das Fenster nimmt den
# Fokus, und der naechste Tastendruck einer anderen Pruefung geht
# dorthin; `os.startfile` wartet auf den Klick, der nicht kommt.
#
# Beobachtet im Bau vom 18.09.2026 (b007aeb): `test_eingaberaster` fiel
# mit einer leeren Meldung, `test_vergleichsfenster` riss die Frist von
# 300 s - beide haben mit Drucken nichts zu tun, und beide Meldungen
# zeigten woandershin. Eine Stunde Suche, und die Ursache stand in
# keiner der beiden Ausgaben.
UMGEBUNG = {druck.OHNE_OBERFLAECHE: "1"}


def kindumgebung() -> dict:
    """Die Umgebung dieses Laufs, um den Riegel erweitert."""
    umgebung = dict(os.environ)
    umgebung.update(UMGEBUNG)
    return umgebung


def laufen(datei: Path, frist: int = FRIST) -> tuple[str, float, str]:
    """Fuehrt eine Pruefdatei aus und sagt, wie es ausging.

    Gibt (Urteil, Dauer, Ausgabe) zurueck; Urteil ist "ok", "fehler"
    oder "frist".
    """
    anfang = time.monotonic()
    try:
        fertig = subprocess.run(                       # noqa: S603
            # -u: ohne Puffer. Die Ausgabe laeuft hier in eine Pipe,
            # und print() puffert dann blockweise - bei einem Haenger
            # wird der Puffer nie geleert, und genau die Zeilen "ok
            # test_...", die sagen, *wo* es stehen bleibt, sind weg.
            # Mit -u steht jede Zeile sofort da, auch die letzte vor
            # dem Stillstand.
            [sys.executable, "-u", str(datei.name)],
            cwd=str(datei.parent),
            capture_output=True,
            text=True,
            timeout=frist,
            env=kindumgebung(),
        )
    except subprocess.TimeoutExpired as abgelaufen:
        dauer = time.monotonic() - anfang
        # Was bis zum Abbruch geschrieben wurde, ist die Spur zur
        # haengenden Pruefung - sie steht in der Ausgabe des Laufs.
        angefallen = abgelaufen.stdout or b""
        if isinstance(angefallen, bytes):
            angefallen = angefallen.decode("utf-8", "replace")
        return "frist", dauer, angefallen
    dauer = time.monotonic() - anfang
    ausgabe = fertig.stdout + fertig.stderr
    return ("ok" if fertig.returncode == 0 else "fehler"), dauer, ausgabe


# Woran eine Pruefdatei ihren Befund erkennbar macht. Die Sammlung
# schreibt jede nicht bestandene Pruefung so an den Anfang der Zeile.
BEFUNDMARKEN = ("FEHLGESCHLAGEN", "FEHLER ")


def wesentliche_zeilen(ausgabe: str, wieviele: int = 14) -> str:
    """Aus der Ausgabe einer Pruefdatei das, was die Ursache nennt.

    Die letzten Zeilen allein reichen nicht: Tk schreibt beim
    Aufraeumen gelegentlich noch Tcl-Meldungen hinterher ("application
    has been destroyed"), und die schoben genau die Zeile aus dem Bild,
    die sagt, *welche* Pruefung fehlgeschlagen ist. Deshalb werden die
    Befundzeilen zuerst gesucht und nur der Rest mit dem Ende
    aufgefuellt.
    """
    zeilen = [zeile for zeile in ausgabe.splitlines() if zeile.strip()]
    befunde = [zeile for zeile in zeilen
               if zeile.lstrip().startswith(BEFUNDMARKEN)]
    gewaehlt = befunde[:wieviele]
    rest = wieviele - len(gewaehlt)
    if rest > 0:
        for zeile in zeilen[-rest:]:
            if zeile not in gewaehlt:
                gewaehlt.append(zeile)
    return "\n".join(gewaehlt)


# Der alte Name bleibt: aufgerufen wird er nur hier, aber eine
# Pruefung haengt daran.
letzte_zeilen = wesentliche_zeilen


def _melden(stelle: str, datei: Path, urteil: str, dauer: float,
            ausgabe: str) -> None:
    """Wie eine Datei ausging - in Zeilen, die ihren Namen tragen.

    Der Name steht in *jeder* Zeile und nicht nur ueber dem Block:
    nebeneinander laufen sonst zwei Ausgaben ineinander, und dann ist
    nicht zu sehen, welche Datei den Befund hat.
    """
    if urteil == "ok":
        sagen(f"{stelle} bestanden ({dauer:.0f}s)  {datei.name}")
        return
    if urteil == "frist":
        sagen(f"{stelle} ZEITUEBERSCHREITUNG nach {dauer:.0f}s - "
              f"{datei.name} haengt")
    else:
        sagen(f"{stelle} FEHLGESCHLAGEN ({dauer:.0f}s)  {datei.name}")
    # Nur bei einem Befund die Ausgabe zeigen: das Log einer
    # bestandenen Pruefung ist Rauschen, das der fehlgeschlagenen
    # ist die Auskunft.
    gezeigt = wesentliche_zeilen(ausgabe)
    if gezeigt:
        sagen(f"          --- Ausgabe {datei.name} ---")
        for zeile in gezeigt.splitlines():
            sagen(f"          {zeile}")


def alle(dateien: list[Path], frist: int = FRIST,
         gleichzeitig: int | None = None) -> int:
    """Laeuft alle Dateien und gibt die Zahl der nicht bestandenen.

    `gleichzeitig` ist die Zahl der Dateien, die nebeneinander laufen;
    1 ist der Reihe nach. Gewartet wird auf Vorgaenge, nicht gerechnet
    - Faeden reichen dafuer, und sie halten die Ausgabe in einem Log.
    """
    gescheitert: list[tuple[Path, str]] = []
    anfang = time.monotonic()
    zahl = gleichzeitig_vorgabe() if gleichzeitig is None else gleichzeitig
    zahl = max(1, min(int(zahl), len(dateien)))
    stellen = {datei: f"[{nummer}/{len(dateien)}]"
               for nummer, datei in enumerate(dateien, start=1)}
    if zahl > 1:
        sagen(f"{len(dateien)} Pruefdateien, {zahl} nebeneinander, "
              f"Frist {frist}s je Datei")
    with concurrent.futures.ThreadPoolExecutor(max_workers=zahl) as riege:
        laeufe = {riege.submit(laufen, datei, frist): datei
                  for datei in dateien}
        for fertig in concurrent.futures.as_completed(laeufe):
            datei = laeufe[fertig]
            urteil, dauer, ausgabe = fertig.result()
            _melden(stellen[datei], datei, urteil, dauer, ausgabe)
            if urteil != "ok":
                gescheitert.append((datei, urteil))
    # Die Befunde in der Folge der Namen und nicht in der, in der sie
    # fertig wurden: zwei Laeufe sollen dieselbe Liste ergeben.
    gescheitert.sort(key=lambda paar: paar[0].name)
    sagen("")
    gesamt = time.monotonic() - anfang
    sagen(f"{len(dateien) - len(gescheitert)} von {len(dateien)} "
          f"Pruefdateien bestanden ({gesamt:.0f}s)")
    for datei, urteil in gescheitert:
        grund = "haengt" if urteil == "frist" else "fehlgeschlagen"
        sagen(f"  - {datei.name}: {grund}")
    return len(gescheitert)


def main(argumente: list[str] | None = None) -> int:
    argumente = list(sys.argv[1:] if argumente is None else argumente)
    frist = FRIST
    if "--frist" in argumente:
        stelle = argumente.index("--frist")
        frist = int(argumente[stelle + 1])
        del argumente[stelle:stelle + 2]
    gleichzeitig = None
    if "--gleichzeitig" in argumente:
        stelle = argumente.index("--gleichzeitig")
        gleichzeitig = int(argumente[stelle + 1])
        del argumente[stelle:stelle + 2]
    if "--einzeln" in argumente:
        # Der Reihe nach - fuer den Fall, dass eine Pruefung sich mit
        # einer anderen ins Gehege kommt und man es sehen will.
        argumente.remove("--einzeln")
        gleichzeitig = 1
    dateien = [HIER / name for name in argumente] if argumente \
        else testdateien()
    fehlend = [datei for datei in dateien if not datei.is_file()]
    if fehlend:
        for datei in fehlend:
            sagen(f"Keine solche Pruefdatei: {datei.name}")
        return 1
    if not dateien:
        sagen("Keine Pruefdateien gefunden - das ist kein Erfolg.")
        return 1
    return 1 if alle(dateien, frist, gleichzeitig) else 0


if __name__ == "__main__":
    raise SystemExit(main())
