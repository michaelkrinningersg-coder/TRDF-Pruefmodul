"""
TRDF-Pruefmodul - Konfiguration, Pfade & Einstellungen
======================================================

Uebernommen aus LabControl: runtime_dir erkennt automatisch, ob die
Anwendung als .exe (PyInstaller) oder als Python-Skript laeuft, und legt
alles *neben* die Anwendung - portabel und ohne Installation.

Wo die Einstellungen liegen
---------------------------
Im Unterordner "einstellungen" neben dem Programm. Laesst sich dort
nicht schreiben - die exe liegt auf einem schreibgeschuetzten
Netzlaufwerk -, weicht die Datei in den Benutzerordner aus, statt still
verlorenzugehen.

Gespeichert werden der zuletzt benutzte Oracle-Benutzer, die zuletzt
abgefragte Serie und die Einstellungen der
Tabellen (Spaltenreihenfolge, Beschreibungen der Legende). Das Passwort
wird bewusst NICHT gespeichert. Es lebt nur im Arbeitsspeicher, solange
die Anwendung laeuft.
"""

import json
import os
import sys

EINSTELLUNGEN_ORDNER = "einstellungen"


def get_runtime_dir():
    """Ordner der Anwendung: bei .exe der Ordner der exe, sonst der
    Ordner dieses Skripts."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def ausweichordner():
    """Ort fuer den Fall, dass neben dem Programm nicht geschrieben werden darf."""
    basis = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
             or os.path.expanduser("~"))
    return os.path.join(basis, "TRDF-Pruefmodul")


def _zahl(wert) -> bool:
    """Eine Zahl - und nicht etwa ein Haken, den Python als 0/1 lesen wuerde."""
    return isinstance(wert, (int, float)) and not isinstance(wert, bool)


def _brauchbar(wert, tiefe: int = 2) -> bool:
    """Taugt dieser Wert als Eintrag einer freien Zuordnung?

    Text, Haken, Zahlen und Listen von Namen - und darueber bis zu zwei
    Ebenen Zuordnung (Tabelle -> [Spalten]).
    """
    if isinstance(wert, dict):
        return tiefe > 0 and all(isinstance(k, str)
                                 and _brauchbar(v, tiefe - 1)
                                 for k, v in wert.items())
    if isinstance(wert, list):
        return all(isinstance(eintrag, str) for eintrag in wert)
    return isinstance(wert, (str, bool, int, float))


class Config:
    """Haelt die Pfade und die gespeicherten Einstellungen."""

    SETTINGS_FILENAME = "trdfpruefmodul_settings.json"

    DEFAULTS = {
        "benutzer": "",
        # Angemeldet wird nur an LIMS - die Auswahl steht trotzdem in
        # der Maske, damit sichtbar ist, wohin geschrieben wird.
        "alias": "LIMS",
        # Die zuletzt abgefragte Serie - sie steht beim naechsten Start
        # wieder im Feld.
        "serie": "",
        # Was der Pruefer selbst zu einer Groesse des TRDF-Moduls notiert
        # hat: Formelkuerzel -> Beschreibung. Sie steht in der Legende
        # neben Name und Einheit und geht nirgendwo sonst hin - in die
        # Oracle-Datenbank schon gar nicht. Wer den Text loescht und
        # speichert, ist ihn wieder los.
        "trdf_beschreibung": {},
        # Die Reihenfolge der Spalten je Tabelle des TRDF-Moduls, als
        # Liste von Formelkuerzeln - so, wie der Pruefer sie unter
        # „Info“ zurechtgezogen hat. Was hier nicht steht, behaelt
        # seinen Platz am Ende.
        "trdf_reihenfolge": {},
        # Welche Spalten dabei links stehen bleiben, waehrend der Rest
        # waagerecht laeuft. Ohne Eintrag gilt, womit eine Tabelle
        # anfaengt: Zeile, Probe - und bei den Rohwerten die Variante.
        "trdf_fest": {},
        # Welche Spalten je Tabelle ausgeblendet sind. Ohne Eintrag
        # keine - wer eine Tabelle oeffnet, will erst einmal sehen, was
        # es gibt. Was fest steht, bleibt sichtbar.
        "trdf_versteckt": {},
        # Was in der Kopfzeile steht: das Formelkuerzel („Spalte“, so
        # wie das LIMS rechnet), der Name, das Para-Kuerzel, die
        # Einheit oder die eigene Beschreibung. Dies ist die Wahl fuer
        # alle Spalten.
        "trdf_kopfspalte": "Spalte",
        # Und was davon abweichend fuer einzelne Groessen gilt:
        # Formelkuerzel -> Wahl. Wie die Beschreibung haengt sie an der
        # Groesse und gilt damit in allen drei Tabellen.
        "trdf_kopfspalten": {},
        # Ob ueber den Rohwerten die berechneten Groessen aufgeklappt
        # stehen ("an") oder nicht ("aus").
        "trdf_berechnete": "aus",
        # Ob nach "Abfragen" gleich angeglichen wird - Anhang und
        # Ergebnisse, jeweils nach der gewohnten Uebersicht ("an"/"aus").
        # Von Haus aus an; wer den Haken wegnimmt, behaelt ihn weg.
        "trdf_auto_angleichen": "an",
    }

    def __init__(self, runtime_dir=None):
        # runtime_dir dient den Tests; im Betrieb gilt der Ordner der
        # Anwendung.
        self.runtime_dir = runtime_dir or get_runtime_dir()
        self.ordner = os.path.join(self.runtime_dir, EINSTELLUNGEN_ORDNER)
        self.settings_path = os.path.join(self.ordner, self.SETTINGS_FILENAME)
        self.quelle = ""            # aus welcher Datei tatsaechlich gelesen
        self.meldung = ""           # was beim letzten Speichern passiert ist
        self.settings = self._vorgaben()
        self.laden()

    def _vorgaben(self) -> dict:
        """Frische Vorgaben - verschachtelte Werte kopiert, nicht geteilt."""
        return {schluessel: dict(wert) if isinstance(wert, dict) else wert
                for schluessel, wert in self.DEFAULTS.items()}

    def kandidaten(self) -> list[str]:
        """Wo nach der Einstellungsdatei gesucht wird, in dieser Reihenfolge.

        Neben dem Programm zuerst: wer den Ordner kopiert, nimmt seine
        Einstellungen mit. Der Ausweichort im Benutzerprofil kommt danach.
        """
        return [
            self.settings_path,
            os.path.join(ausweichordner(), self.SETTINGS_FILENAME),
        ]

    # ------------------------------------------------------------------ Lesen
    def laden(self):
        """Liest die Einstellungen aus der ersten Datei, die sich lesen laesst.

        Eine kaputte Einstellungsdatei darf den Start nie verhindern - dann
        gelten die Vorgaben, und der Grund steht in `meldung`.
        """
        for pfad in self.kandidaten():
            if not os.path.isfile(pfad):
                continue
            try:
                with open(pfad, encoding="utf-8") as datei:
                    gespeichert = json.load(datei)
            except (OSError, ValueError) as fehler:
                self.meldung = f"{pfad} liess sich nicht lesen: {fehler}"
                continue
            if not isinstance(gespeichert, dict):
                self.meldung = f"{pfad} enthaelt keine Einstellungen"
                continue
            self._uebernehmen(gespeichert)
            self.quelle = pfad
            return

    def _uebernehmen(self, gespeichert: dict):
        for schluessel, vorgabe in self.DEFAULTS.items():
            wert = gespeichert.get(schluessel)
            if isinstance(vorgabe, dict):
                if isinstance(wert, dict):
                    # Eine leere Vorgabe ist eine freie Zuordnung (Geraet ->
                    # Spaltenname): dort sind die Schluessel nicht vorher
                    # bekannt, sonst kaeme nie etwas an. Sonst gelten nur
                    # die vorgesehenen Schluessel.
                    # Zahlen sind hier ebenso erlaubt wie Text und
                    # Haken: die Reihenfolge der Reiter steht als Zahl.
                    erlaubt = {k: v for k, v in wert.items()
                               if isinstance(k, str)
                               and _brauchbar(v)
                               and (not vorgabe or k in vorgabe)}
                    self.settings[schluessel] = dict(vorgabe, **erlaubt)
            elif isinstance(vorgabe, (int, float)) and not isinstance(
                    vorgabe, bool):
                # Zahlen kommen als Zahl zurueck - ein Text an dieser
                # Stelle waere eine kaputte Datei und bleibt draussen.
                if _zahl(wert):
                    self.settings[schluessel] = wert
                elif isinstance(wert, dict):
                    # Je Bearbeiter eine Zahl - so steht die Zeilenhoehe
                    # da, sobald jemand eine eigene gespeichert hat.
                    eigene = {name: zahl for name, zahl in wert.items()
                              if isinstance(name, str) and _zahl(zahl)}
                    if eigene:
                        self.settings[schluessel] = eigene
            elif isinstance(wert, str):
                self.settings[schluessel] = wert

    # --------------------------------------------------------------- Schreiben
    def speichern(self) -> bool:
        """Schreibt die Einstellungen und sagt, ob es geklappt hat.

        Zuerst neben das Programm. Ist der Ordner schreibgeschuetzt - die
        exe liegt auf einem Netzlaufwerk -, wird in den Benutzerordner
        ausgewichen: die Einstellungen sind sonst beim naechsten Start weg,
        ohne dass jemand erfaehrt warum.

        Geschrieben wird ueber eine Nebendatei, die anschliessend an ihren
        Platz geschoben wird. Bricht der Vorgang ab, steht dann noch der
        alte, vollstaendige Stand da statt einer halben Datei.
        """
        fehler = []
        for ordner in (self.ordner, ausweichordner()):
            pfad = os.path.join(ordner, self.SETTINGS_FILENAME)
            try:
                os.makedirs(ordner, exist_ok=True)
                vorlaeufig = pfad + ".neu"
                with open(vorlaeufig, "w", encoding="utf-8") as datei:
                    json.dump(self.settings, datei, indent=2,
                              ensure_ascii=False)
                os.replace(vorlaeufig, pfad)
            except OSError as ausnahme:
                fehler.append(f"{ordner}: {ausnahme}")
                continue
            self.settings_path = pfad
            self.quelle = pfad
            self.meldung = (f"Gespeichert in {pfad}" if not fehler else
                            f"Gespeichert in {pfad} - neben dem Programm ging "
                            f"es nicht ({fehler[0]})")
            return True
        self.meldung = ("Die Einstellungen liessen sich nicht speichern: "
                        + "; ".join(fehler))
        return False

    # ------------------------------------------------------------------ Zugriff
    def get(self, schluessel):
        return self.settings.get(schluessel, self.DEFAULTS.get(schluessel))

    def set(self, schluessel, wert):
        self.settings[schluessel] = wert
