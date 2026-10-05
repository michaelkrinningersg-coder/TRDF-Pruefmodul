"""Was pytest braucht und die Pruefdateien selbst mitbringen.

Jede Pruefdatei hier laeuft auch allein: `python test_x.py` ruft ihr
`main()`, und das baut, was sie braucht - bei den Fensterpruefungen ein
verstecktes Tk-Fenster, damit `tk.StringVar()` einen Ort hat.

pytest ruft `main()` nicht. Es sammelt die `test_*`-Funktionen ein und
ruft sie einzeln, und damit fehlt genau der Aufbau, den `main()` macht.
Sichtbar wurde das an `test_kartenauswahl.py`: zweiundfuenfzig Befunde,
alle mit derselben Meldung -

    RuntimeError: Too early to create variable: no default root window

- und keiner davon ein Fehler im Programm. Die Sammlung selbst war
gruen (`pruefungen_laufen.py`: 76 von 76), pytest sah dieselben
Pruefungen scheitern. Das ist die schlechteste Art von rotem Befund:
er sagt nichts ueber die Software und kostet jedes Mal die Zeit, das
noch einmal festzustellen.

Hier steht der Aufbau deshalb einmal fuer alle: ein verstecktes Fenster
fuer die ganze Sitzung. Es ist der Standardknoten, an dem `tk`
Variablen ohne eigene Angabe festmacht.

Warum eines fuer die ganze Sitzung, und nicht je Pruefung
---------------------------------------------------------
Die Pruefungen, die ein eigenes Fenster brauchen, bauen es selbst und
raeumen es selbst wieder ab - das soll so bleiben, denn sie pruefen
damit auch, dass sich ein Fenster schliessen laesst. Ein zweites `Tk()`
neben diesem ist in `tkinter` erlaubt und stoert nicht; abgeraeumt wird
das ihre, nicht dieses.

Umgekehrt war es vorher die Falle: ohne dieses Fenster wurde das erste
Fenster der ersten Pruefung zum Standardknoten - und als es abgeraeumt
wurde, stand die naechste Pruefung wieder ohne da. Welche scheiterte,
hing damit an der Reihenfolge.

Dieses Fenster wird nicht abgeraeumt. Es lebt, solange pytest lebt, und
faellt mit dem Vorgang - eine Zeile "destroy" am Ende waere ein
Aufraeumen nach dem Abriss.
"""

from __future__ import annotations

import tkinter as tk

import pytest


@pytest.fixture(scope="session", autouse=True)
def tk_standardknoten():
    """Ein verstecktes Fenster fuer die ganze pytest-Sitzung.

    Ohne Anzeige gibt es keines. Dann scheitern die Fensterpruefungen
    so, wie sie es ohne Anzeige immer tun - das hier zu verschleiern
    waere schlimmer als der Befund.
    """
    try:
        wurzel = tk.Tk()
    except tk.TclError:
        yield None
        return
    wurzel.withdraw()
    yield wurzel
