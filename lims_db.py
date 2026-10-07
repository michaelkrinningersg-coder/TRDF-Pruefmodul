"""
TRDF-Pruefmodul - Datenschicht (Oracle)
=======================================

Ausgeloest aus der Datenschicht von LabControl (TestLims): hier steht
nur noch, was die TRDF-Pruefung braucht - die Anmeldung, die Abfragen
zu Serie und Untersuchungsmethode und der Rueckweg in das LIMS. Wie dort
ist diese Datei frei von jeder GUI-Abhaengigkeit, damit sie ohne
Fenster und ohne Datenbank geprueft werden kann.

Verbindungsweg
--------------
Die Connect-Deskriptoren kommen aus der vorhandenen **tnsnames.ora**.
Gesucht wird sie zuerst neben dem Programm - so laesst sich eine
geaenderte Datei ablegen, ohne neu zu bauen -, danach in der exe selbst,
in die der Bau sie mit hineinpackt. Weder TNS_ADMIN noch ORACLE_HOME
noch ein OLE-DB-Provider werden benoetigt.

Zugelassen ist ausschliesslich der Eintrag **LIMS**. Die Datei fuehrt
daneben ECO und LIMSTEST; die bleiben hier draussen, auch wenn sie in der
Datei stehen - das Pruefmodul schreibt Korrekturen in die Datenbank, und
eine Auswahlliste, in der eine zweite Datenbank steht, ist eine
Gelegenheit, in die falsche zu schreiben.

  * Thin Mode (Standard): python-oracledb spricht das Oracle-Protokoll direkt
    ueber TCP. Kein Oracle-Client noetig, setzt aber Datenbank 12.1+ voraus.
  * Thick Mode: wird automatisch nachgeladen, sobald die Datenbank fuer den
    Thin Mode zu alt ist (Fehler DPY-3010). Dafuer muss das Programm dieselbe
    Bitness haben wie der Client unter C:\\Oracle\\11.2.0 - der ist 32-bit,
    also die x86-Variante der exe verwenden.

Schreiben
---------
Geschrieben wird ausschliesslich ueber den TRDF-Rueckweg: UPDATE auf den
vollen Schluessel einer vorhandenen Zeile, alle Werte als
Bind-Variablen, nach einer bestaetigten Uebersicht und einer Sicherung.
"""

from __future__ import annotations

import contextlib
import csv
import decimal
import datetime as dt
import io
import os
import re
import struct
import sys
import threading

import oracledb

import protokoll

# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

# Die einzige Datenbank, an der sich das Pruefmodul anmeldet.
DATENBANKEN = ("LIMS",)

# Wie die Datei heisst, aus der die Deskriptoren kommen.
TNSNAMES = "tnsnames.ora"

# Suchpfade fuer den Thick-Mode-Fallback, erster Treffer gewinnt.
# Dieselben Umgebungsvariablen wie bei LabControl, damit eine am
# Arbeitsplatz bereits gesetzte Variable auch hier greift.
CLIENT_PFADE = [p for p in (os.environ.get("TRDF_ORACLE_CLIENT"),
                            os.environ.get("LABCONTROL_ORACLE_CLIENT"),
                            os.environ.get("LIMS_ORACLE_CLIENT"),
                            r"C:\Oracle\11.2.0\bin") if p]
BITNESS = 8 * struct.calcsize("P")          # 32 oder 64

oracledb.defaults.fetch_lobs = False        # CLOBs direkt als str

_thick_aktiv = False


# --------------------------------------------------------------------------
# tnsnames.ora
# --------------------------------------------------------------------------

def _programmordner() -> str:
    """Der Ordner der exe - oder dieser Datei, wenn aus dem Quelltext."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def tnsnames_orte() -> list[str]:
    """Wo nach der tnsnames.ora gesucht wird, in dieser Reihenfolge.

    Neben dem Programm zuerst: wer dort eine Datei ablegt, meint sie.
    Danach die Kopie, die der Bau in die exe gepackt hat (PyInstaller
    entpackt sie nach `sys._MEIPASS`), zuletzt der Quelltextordner.
    """
    orte = [os.path.join(_programmordner(), TNSNAMES)]
    eingepackt = getattr(sys, "_MEIPASS", None)
    if eingepackt:
        orte.append(os.path.join(eingepackt, TNSNAMES))
    orte.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             TNSNAMES))
    return list(dict.fromkeys(orte))


def tnsnames_lesen(text: str) -> dict:
    """Die Eintraege einer tnsnames.ora als {ALIAS: Deskriptor}.

    Kommentare (#) fallen weg, der Deskriptor kommt in einer Zeile und
    ohne Leerraum zurueck - so, wie python-oracledb ihn als DSN nimmt.
    Gezaehlt werden Klammern und nicht Zeilen: wie der Eintrag
    umbrochen ist, sagt nichts ueber seinen Inhalt.
    """
    ohne = "\n".join(zeile.split("#", 1)[0] for zeile in text.splitlines())
    eintraege, stelle = {}, 0
    kopf = re.compile(r"\s*([A-Za-z0-9_.\-]+(?:\s*,\s*[A-Za-z0-9_.\-]+)*)"
                      r"\s*=\s*\(")
    while True:
        treffer = kopf.search(ohne, stelle)
        if treffer is None:
            break
        anfang = treffer.end() - 1
        tiefe, ende = 0, None
        for nummer in range(anfang, len(ohne)):
            if ohne[nummer] == "(":
                tiefe += 1
            elif ohne[nummer] == ")":
                tiefe -= 1
                if tiefe == 0:
                    ende = nummer + 1
                    break
        if ende is None:
            raise ValueError("tnsnames.ora: Klammern sind nicht geschlossen "
                             f"(bei {treffer.group(1).strip()}).")
        deskriptor = re.sub(r"\s+", "", ohne[anfang:ende])
        for alias in treffer.group(1).split(","):
            eintraege[alias.strip().upper()] = deskriptor
        stelle = ende
    return eintraege


def tnsnames_pfad() -> str:
    """Die tnsnames.ora, die gilt - "" wenn keine da ist."""
    for pfad in tnsnames_orte():
        if os.path.isfile(pfad):
            return pfad
    return ""


def deskriptoren(pfad: str | None = None) -> dict:
    """Die zugelassenen Eintraege der tnsnames.ora - nur LIMS.

    Was die Datei sonst fuehrt, bleibt draussen. Fehlt LIMS in der
    Datei, ist das ein Fehler und kein leeres Ergebnis: eine
    Anmeldemaske, die nichts zu waehlen hat, sagt nicht, warum.
    """
    pfad = pfad or tnsnames_pfad()
    if not pfad:
        raise FileNotFoundError(
            "Die tnsnames.ora wurde nicht gefunden. Gesucht in: "
            + "; ".join(tnsnames_orte()))
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        alle = tnsnames_lesen(datei.read())
    erlaubt = {alias: alle[alias] for alias in DATENBANKEN if alias in alle}
    if not erlaubt:
        raise ValueError(f"In {pfad} steht kein Eintrag "
                         f"{' / '.join(DATENBANKEN)}.")
    return erlaubt


def deskriptor(alias: str) -> str:
    """Der Connect-Deskriptor einer zugelassenen Datenbank."""
    name = str(alias or "").strip().upper()
    if name not in DATENBANKEN:
        raise ValueError(f"Die Datenbank '{alias}' ist nicht zugelassen - "
                         f"angemeldet wird nur an "
                         f"{', '.join(DATENBANKEN)}.")
    return deskriptoren()[name]


# --------------------------------------------------------------------------
# Verbindung
# --------------------------------------------------------------------------

def lade_client() -> None:
    """Laedt den Oracle Client fuer den Thick Mode aus dem ersten passenden Pfad."""
    letzter_fehler: Exception | None = None
    for pfad in CLIENT_PFADE:
        if not os.path.isdir(pfad):
            continue
        try:
            oracledb.init_oracle_client(lib_dir=pfad)
            return
        except Exception as fehler:          # falsche Bitness, unvollstaendig, ...
            letzter_fehler = fehler
    if letzter_fehler is not None:
        raise letzter_fehler
    # Kein Verzeichnis gefunden: Standardsuche ueber PATH versuchen.
    oracledb.init_oracle_client()


class Zugang:
    """Zugangsdaten einer angemeldeten Sitzung.

    Das Passwort lebt nur hier im Arbeitsspeicher und wird nirgends
    gespeichert oder protokolliert.
    """

    # Die Verbindungen koennen in einem Vorrat liegen. Jede Abfrage baut
    # sonst ihre eigene auf - mit Anmeldung, und das ist eine Rundreise
    # mehr als die Abfrage selbst: fuer einen Durchgang vom Anmelden bis
    # zum Export sind das ein Dutzend Anmeldungen. Aus dem Vorrat kommt
    # die Verbindung sofort, und `close()` gibt sie dorthin zurueck statt
    # sie abzubauen - der uebrige Code bleibt, wie er ist.
    #
    # Von Haus aus ist der Vorrat *aus*. Die NW-FVA arbeitet auf Oracle
    # 11.2 ueber den nachgeladenen Client, und dort liess sich nicht
    # pruefen, ob ein Sitzungsvorrat traegt - ein Startbildschirm, der
    # leer bleibt, ist teurer als die Sekunden, die er spart.
    # Eingeschaltet wird er ueber die Umgebungsvariable
    # LABCONTROL_VERBINDUNGSVORRAT=1; laesst er sich dann nicht anlegen,
    # wird ohne ihn weitergearbeitet und der Grund gemerkt.
    VORRAT_MIN = 1
    VORRAT_MAX = 4
    VORRAT_PRUEFUNG = 60        # Sekunden, ab denen vor der Ausgabe geprueft wird
    VORRAT_SCHALTER = "LABCONTROL_VERBINDUNGSVORRAT"
    VORRAT_AN = ("1", "ja", "an", "true", "wahr")

    def __init__(self, benutzer: str, passwort: str, alias: str):
        self.benutzer = benutzer
        self.passwort = passwort
        self.alias = alias
        self.modus = ""
        self._vorrat = None
        self._ohne_vorrat = not self.vorrat_gewuenscht()
        # Steht hier etwas, ist ein gewuenschter Vorrat gescheitert.
        self.vorrat_meldung = ""
        # Die Abfragen laufen im Hintergrundfaden; zwei zugleich duerfen
        # nicht zwei Vorraete anlegen.
        self._sperre = threading.Lock()
        # Das Aenderungsprotokoll. Wird von aussen gesetzt (der
        # Startbildschirm weiss, wo es hingehoert); ohne es laeuft alles
        # wie bisher, nur ungeschrieben.
        self.protokoll = None

    @classmethod
    def vorrat_gewuenscht(cls) -> bool:
        return os.environ.get(cls.VORRAT_SCHALTER, "").strip().lower() \
            in cls.VORRAT_AN

    def verbinden(self):
        """Eine Verbindung - aus dem Vorrat, wenn es einen gibt.

        Zurueck kommt sie eingepackt: der Umschlag schreibt jede
        aendernde Anweisung ins Protokoll, sobald sie festgeschrieben
        ist. Ohne Protokoll (`self.protokoll` ist None) gibt er die
        Verbindung unveraendert weiter - dann kostet er nichts.
        """
        return _mit_protokoll(self._verbinden(), self.protokoll)

    def _verbinden(self):
        with self._sperre:
            if self._ohne_vorrat:
                return self._einzeln()
            if self._vorrat is None:
                try:
                    self._vorrat = self._vorrat_bauen()
                    self.vorrat_meldung = ""
                except Exception as fehler:                 # noqa: BLE001
                    if isinstance(fehler, oracledb.Error) \
                            and _anmeldung_falsch(fehler):
                        raise
                    # Laesst sich kein Vorrat anlegen, wird wie bisher je
                    # Abfrage verbunden. Langsamer, aber es laeuft - und
                    # der Grund geht nicht verloren.
                    self._ohne_vorrat = True
                    self.vorrat_meldung = str(fehler).splitlines()[0]
                    return self._einzeln()
            vorrat = self._vorrat
        # Das Warten auf eine freie Verbindung gehoert nicht unter die
        # Sperre - sonst warteten alle Faeden auf denselben Riegel.
        return vorrat.acquire()

    def verbindungsart(self) -> str:
        """Woher die Verbindungen kommen - fuer die Kopfzeile."""
        if self._vorrat is not None:
            return "Vorrat"
        return f"ohne Vorrat ({self.vorrat_meldung})" if self.vorrat_meldung \
            else "ohne Vorrat"

    def schliessen(self):
        """Baut den Vorrat ab - beim Abmelden und beim Beenden."""
        with self._sperre:
            vorrat, self._vorrat = self._vorrat, None
        if vorrat is not None:
            try:
                vorrat.close(force=True)
            except Exception:                           # noqa: BLE001
                pass

    def _vorrat_bauen(self):
        """Legt den Vorrat an - im richtigen Modus.

        Welcher gilt, klaert eine einzelne Verbindung vorweg: der Thin
        Mode spricht erst mit Oracle 12.1, und der Umstieg auf den
        nachgeladenen Oracle Client haengt an der Fehlermeldung des ersten
        Verbindungsversuchs (DPY-3010). Die NW-FVA arbeitet auf 11.2, dort
        faellt diese Entscheidung immer. Sie hier zu treffen statt sie dem
        Vorrat zu ueberlassen kostet einmal je Sitzung eine Verbindung und
        erspart, dass ein Vorrat im falschen Modus scheitert und alles
        stillschweigend auf den langsamen Weg zurueckfaellt.
        """
        self._einzeln().close()
        angaben = dict(user=self.benutzer, password=self.passwort,
                       dsn=deskriptor(self.alias),
                       min=self.VORRAT_MIN, max=self.VORRAT_MAX, increment=1)
        try:
            return oracledb.create_pool(ping_interval=self.VORRAT_PRUEFUNG,
                                        **angaben)
        except TypeError:
            # Aeltere Treiber kennen die Pruefung vor der Ausgabe nicht.
            return oracledb.create_pool(**angaben)

    def _einzeln(self):
        """Der alte Weg: eine eigene Verbindung, im Thin oder Thick Mode."""
        global _thick_aktiv
        dsn = deskriptor(self.alias)
        try:
            verbindung = oracledb.connect(user=self.benutzer, password=self.passwort,
                                          dsn=dsn)
        except oracledb.Error as fehler:
            if _thick_aktiv or "DPY-3010" not in str(fehler):
                raise
            # Datenbank ist aelter als 12.1 -> Oracle Client nachladen.
            lade_client()
            _thick_aktiv = True
            verbindung = oracledb.connect(user=self.benutzer, password=self.passwort,
                                          dsn=dsn)
        self.modus = "Thick Mode" if _thick_aktiv else "Thin Mode"
        return verbindung


# Falsche Zugangsdaten sind kein Grund, es ohne Vorrat noch einmal zu
# versuchen - das kostete nur eine zweite Fehlmeldung und, bei mehreren
# Versuchen, die Sperrung des Kontos.
ANMELDEFEHLER = ("ORA-01017", "ORA-28000", "ORA-28001", "ORA-01005")


# --------------------------------------------------------------------------
# Der Umschlag um die Verbindung: jede Aenderung ins Protokoll
# --------------------------------------------------------------------------
#
# Angesetzt wird an *einer* Stelle - an der Verbindung, die jede Abfrage
# und jede Anweisung bekommt. Jeden Schreibweg einzeln zu protokollieren
# hiesse, den naechsten zu vergessen; hier kommt keiner vorbei.
#
# Geschrieben wird erst beim COMMIT. Was zurueckgerollt wird, ist nicht
# geschehen und gehoert nicht ins Protokoll - der Export etwa versucht
# das Buendel, rollt bei einer fehlenden Zeile zurueck und schreibt
# danach Satz fuer Satz. Ohne diese Zwischenstufe stuende der erste
# Versuch mit im Protokoll, obwohl ihn niemand mehr sieht.


class _Sammlung:
    """Die Aenderungen einer Transaktion - bis zum COMMIT."""

    def __init__(self, buch):
        self.buch = buch
        self.offen = []

    def merken(self, sql, bindungen, hinweis=""):
        self.offen.append(("einzeln", sql, bindungen, hinweis))

    def merken_viele(self, sql, saetze, hinweise=None):
        self.offen.append(("viele", sql, [dict(s) for s in saetze], hinweise))

    def bestaetigt(self):
        offen, self.offen = self.offen, []
        for art, sql, werte, hinweis in offen:
            if art == "viele":
                self.buch.viele(sql, werte, hinweis)
            else:
                self.buch.eintragen(sql, werte, hinweis)

    def verworfen(self):
        self.offen = []


class _Protokollcursor:
    """Ein Cursor, der jede aendernde Anweisung meldet.

    `hinweis` und `hinweise` lassen sich vor dem Ausfuehren setzen: dann
    steht im Protokoll ein Satz in Worten ueber der Anweisung. Ohne sie
    steht nur die Anweisung da - immer noch besser als nichts.
    """

    def __init__(self, cursor, sammlung):
        object.__setattr__(self, "_cursor", cursor)
        object.__setattr__(self, "_sammlung", sammlung)
        object.__setattr__(self, "hinweis", "")
        object.__setattr__(self, "hinweise", None)

    def execute(self, sql, *args, **rest):
        ergebnis = self._cursor.execute(sql, *args, **rest)
        # Erst ausfuehren, dann merken: was scheitert, ist nicht
        # geschehen. Und was keine Zeile getroffen hat, hat nichts
        # geaendert - eine Anweisung ins Leere gehoert nicht in ein
        # Protokoll ueber Aenderungen.
        if self._merkt(sql):
            bindungen = args[0] if args else rest
            self._sammlung.merken(sql, bindungen, self.hinweis)
        return ergebnis

    def executemany(self, sql, saetze, *args, **rest):
        ergebnis = self._cursor.executemany(sql, saetze, *args, **rest)
        if self._merkt(sql):
            self._sammlung.merken_viele(sql, saetze, self.hinweise)
        return ergebnis

    def _merkt(self, sql) -> bool:
        if self._sammlung is None or not protokoll.ist_aendernd(sql):
            return False
        return bool(self._cursor.rowcount)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *rest):
        return self._cursor.__exit__(*rest)

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_cursor"), name)

    def __setattr__(self, name, wert):
        if name in ("hinweis", "hinweise"):
            object.__setattr__(self, name, wert)
        else:
            setattr(self._cursor, name, wert)


class _Protokollverbindung:
    """Eine Verbindung, deren Cursor mitschreiben."""

    def __init__(self, verbindung, buch):
        object.__setattr__(self, "_verbindung", verbindung)
        object.__setattr__(self, "_sammlung", _Sammlung(buch))

    def cursor(self, *args, **rest):
        return _Protokollcursor(self._verbindung.cursor(*args, **rest),
                                self._sammlung)

    def commit(self, *args, **rest):
        ergebnis = self._verbindung.commit(*args, **rest)
        self._sammlung.bestaetigt()
        return ergebnis

    def rollback(self, *args, **rest):
        self._sammlung.verworfen()
        return self._verbindung.rollback(*args, **rest)

    def close(self, *args, **rest):
        # Nicht festgeschriebenes faellt beim Schliessen weg - dann ist
        # es auch nicht geschehen.
        self._sammlung.verworfen()
        return self._verbindung.close(*args, **rest)

    def __enter__(self):
        self._verbindung.__enter__()
        return self

    def __exit__(self, art, wert, spur):
        # Ein `with` auf der Verbindung schreibt beim sauberen Verlassen
        # fest und rollt sonst zurueck - dasselbe gilt fuers Protokoll.
        if art is None:
            self._sammlung.bestaetigt()
        else:
            self._sammlung.verworfen()
        return self._verbindung.__exit__(art, wert, spur)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_verbindung"), name)

    def __setattr__(self, name, wert):
        setattr(self._verbindung, name, wert)


def _mit_protokoll(verbindung, buch):
    """Packt die Verbindung ein - oder gibt sie unveraendert weiter."""
    if buch is None or verbindung is None:
        return verbindung
    return _Protokollverbindung(verbindung, buch)


def _anmeldung_falsch(fehler: Exception) -> bool:
    text = str(fehler)
    return any(code in text for code in ANMELDEFEHLER)


def anmelden(benutzer: str, passwort: str, alias: str) -> Zugang:
    """Prueft die Zugangsdaten mit einer echten Verbindung und gibt den Zugang."""
    deskriptor(alias)            # nur LIMS - und die tnsnames.ora muss es kennen
    if not benutzer.strip() or not passwort:
        raise ValueError("Benutzer und Passwort werden benoetigt.")
    zugang = Zugang(benutzer.strip(), passwort, alias)
    zugang.verbinden().close()
    return zugang


def fehlernummer(fehler: Exception):
    """Die ORA-Nummer einer Datenbankausnahme - None, wenn es keine gibt.

    Gebraucht wird sie, um *eine* Ursache abzufangen und alle anderen
    weiterzureichen. Ein pauschales "ging nicht" wuerde einen echten
    Fehler in der Abfrage still verschlucken.
    """
    for stelle in getattr(fehler, "args", ()):
        nummer = getattr(stelle, "code", None)
        if nummer is not None:
            try:
                return int(nummer)
            except (TypeError, ValueError):
                return None
    treffer = re.search(r"ORA-(\d+)", str(fehler))
    return int(treffer.group(1)) if treffer else None


def fehlertext(fehler: Exception) -> str:
    """Macht aus einer Ausnahme eine Meldung, die einem Anwender weiterhilft."""
    if isinstance(fehler, oracledb.Error) and fehler.args:
        info = fehler.args[0]
        text = getattr(info, "message", str(fehler))
    else:
        text = str(fehler)

    if "DPI-1047" in text or "DPI-1072" in text:
        pfade = ", ".join(CLIENT_PFADE) or "(kein Pfad konfiguriert)"
        text += (
            f"\n\nDer Oracle Client konnte nicht geladen werden. Gesucht wurde in: "
            f"{pfade}. Haeufigste Ursache: unterschiedliche Bitness. Dieses "
            f"Programm laeuft als {BITNESS}-bit; der Client unter "
            f"C:\\Oracle\\11.2.0 ist 32-bit. In dem Fall die Datei "
            f"TRDF-Pruefmodul-x86.exe verwenden. Ein anderer Client-Pfad laesst "
            f"sich ueber die Umgebungsvariable TRDF_ORACLE_CLIENT vorgeben."
        )
    return text


# --------------------------------------------------------------------------
# Lesen
# --------------------------------------------------------------------------

@contextlib.contextmanager
def sitzung(zugang):
    """Eine Verbindung fuer alle Abfragen einer Aktion.

    Ohne sie baut jede Abfrage ihre eigene Verbindung auf - mit
    Anmeldung, und die kostet im Netz und erst recht im Thick Mode ein
    Vielfaches der Abfrage selbst. Eine Serie zu laden waren so sechs
    bis acht Anmeldungen hintereinander.

    Hat der Zugang keine Verbindung zu bieten (in den Pruefungen ist er
    ein blosser Platzhalter), kommt None: dann verbindet jede Abfrage
    wie bisher selbst.
    """
    verbinden = getattr(zugang, "verbinden", None)
    if verbinden is None:
        yield None
        return
    verbindung = verbinden()
    try:
        yield verbindung
    finally:
        verbindung.close()


def _zeilen(zugang, sql: str, bindungen: dict | None = None, verbindung=None):
    """Fuehrt eine Leseabfrage aus und gibt die Zeilen.

    Mit `verbindung` laesst sich eine fertige Verbindung hereinreichen - das
    nutzen die Tests, um ohne Datenbank zu pruefen.
    """
    if verbindung is not None:
        with verbindung.cursor() as cursor:
            cursor.execute(sql, bindungen or {})
            return cursor.fetchall()
    verbindung = zugang.verbinden()
    with verbindung:
        with verbindung.cursor() as cursor:
            cursor.execute(sql, bindungen or {})
            return cursor.fetchall()


def _seriennamen(zeilen) -> list[str]:
    return [str(zeile[0]).strip() for zeile in zeilen
            if zeile[0] is not None and str(zeile[0]).strip()]


def methoden_fuer_serie(zugang, serie: str, verbindung=None) -> list[tuple]:
    """Die Untersuchungsmethoden, zu denen es in dieser Serie Teilproben gibt.

    LEFT JOIN, damit eine um_id ohne Eintrag in UNTERSUCHUNGSMETHODE nicht
    stillschweigend verschwindet - sie taucht dann mit ihrer ID auf.

    Findet sich in TEILPROBEN nichts, wird in ERGEBNISSE nachgesehen: bei
    einer alten Serie kann die Teilprobe geraeumt sein, waehrend ihre
    Ergebniszeilen stehen bleiben. Bleibt auch das leer, sagt
    SERIEN_MW_ANHANG, welche Methode angesetzt ist - eine frisch
    angelegte Serie hat noch keine Ergebniszeilen. Die weiteren Abfragen
    laufen nur dann, und
    sie fragt nach *einer* Serie - das ist keine Suche ueber die ganze
    Tabelle.

    """
    bindungen = {"serie": serie}
    zeilen = _zeilen(zugang, """
        SELECT DISTINCT t.um_id, u.kuerzel
          FROM teilproben t
          LEFT JOIN untersuchungsmethode u ON u.id = t.um_id
         WHERE t.serie = :serie AND t.um_id IS NOT NULL
         ORDER BY u.kuerzel, t.um_id
    """, bindungen, verbindung=verbindung)
    if not zeilen:
        zeilen = _zeilen(zugang, """
            SELECT DISTINCT e.um_id, u.kuerzel
              FROM ergebnisse e
              LEFT JOIN untersuchungsmethode u ON u.id = e.um_id
             WHERE e.serie = :serie AND e.um_id IS NOT NULL
             ORDER BY u.kuerzel, e.um_id
        """, bindungen, verbindung=verbindung)
    if not zeilen:
        # Zuletzt die Zuordnung selbst: eine angesetzte Serie steht in
        # SERIEN_MW_ANHANG mit ihrer Methode, auch bevor Teilproben
        # angelegt oder Ergebniszeilen geschrieben sind.
        zeilen = _zeilen(zugang, """
            SELECT DISTINCT a.um_id, u.kuerzel
              FROM serien_mw_anhang a
              LEFT JOIN untersuchungsmethode u ON u.id = a.um_id
             WHERE a.serie = :serie AND a.um_id IS NOT NULL
             ORDER BY u.kuerzel, a.um_id
        """, bindungen, verbindung=verbindung)
    return [(zeile[0], zeile[1]) for zeile in zeilen]


# Was der Rueckweg an der Ergebniszeile setzt: den Bearbeitungsstand
# "gesendet" und das Korrekturkennzeichen.
PSTA_GESENDET = 2
KORREKTUR_FLAG = "F"


def _dicts(zeilen, felder: tuple) -> list[dict]:
    return [dict(zip(felder, zeile)) for zeile in zeilen]


def als_zahl(wert):
    """Macht aus einem Datenbankwert eine Zahl - None, wenn es keine ist.

    STANDARD_PARA fuehrt SOLLWERT, GU und GO als VARCHAR2. Dort steht in der
    Regel eine Zahl, aber eben als Text und teils mit Dezimalkomma. Was sich
    nicht lesen laesst (etwa "<0,1"), gibt None zurueck statt zu raten - der
    Rohtext bleibt daneben stehen, damit nichts still verschwindet.
    """
    if wert is None:
        return None
    if ist_zahl(wert):
        return decimal.Decimal(str(wert))
    text = str(wert).strip().replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        return decimal.Decimal(text)
    except (decimal.InvalidOperation, ValueError):
        return None


# --------------------------------------------------------------------------
# Darstellung von Werten
# --------------------------------------------------------------------------

def als_text(wert) -> str:
    """Stellt einen Datenbankwert fuer die Anzeige dar."""
    if wert is None:
        return ""
    if isinstance(wert, bool):
        return str(wert)
    if isinstance(wert, dt.datetime):
        return wert.strftime("%d.%m.%Y %H:%M:%S")
    if isinstance(wert, dt.date):
        return wert.strftime("%d.%m.%Y")
    if isinstance(wert, bytes):
        return f"<{len(wert)} Byte>"
    return str(wert)


def ist_zahl(wert) -> bool:
    return isinstance(wert, (int, float, decimal.Decimal)) and not isinstance(wert, bool)


def csv_bytes(zeilen: list) -> bytes:
    """Schreibt Zeilen als CSV fuer Excel.

    Semikolon als Trennzeichen, Komma als Dezimaltrennzeichen, BOM damit Excel
    die Umlaute richtig liest.
    """
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    for zeile in zeilen:
        schreiber.writerow(
            "" if w is None
            else str(w).replace(".", ",") if isinstance(w, (float, decimal.Decimal))
            else als_text(w)
            for w in zeile
        )
    return puffer.getvalue().encode("utf-8-sig")


def als_csv(spalten: list, zeilen: list) -> bytes:
    """Baut eine CSV-Datei aus Ueberschriften und Zeilen."""
    return csv_bytes([list(spalten)] + [list(z) for z in zeilen])


def csv_bloecke(bloecke, abstand: int = 3) -> bytes:
    """Mehrere Tabellen in einer Datei, durch Leerzeilen getrennt.

    `bloecke` sind (Titel, Ueberschriften, Zeilen). Ein Reiter zeigt
    manchmal mehrere Tabellen untereinander - je Kontrollstandard eine.
    In einer CSV muessen sie auseinanderzuhalten sein: deshalb je Block
    seine eigene Ueberschriftenzeile und dazwischen Luft.
    """
    zeilen = []
    for titel, spalten, inhalt in bloecke:
        if zeilen:
            zeilen += [[] for _ in range(max(0, abstand))]
        if titel:
            zeilen.append([titel])
        zeilen.append(list(spalten))
        zeilen += [list(zeile) for zeile in inhalt]
    return csv_bytes(zeilen)


# --------------------------------------------------------------------------
# Selbsttest
# --------------------------------------------------------------------------

def selbsttest(oberflaeche=("tkinter",)) -> tuple[int, list[str]]:
    """Prueft ohne Datenbank, ob alle Laufzeitbestandteile mitgeliefert wurden.

    python-oracledb laedt cryptography erst beim Verbindungsaufbau nach; fehlt
    es im Paket, meldet es DPY-3016 - und zwar bevor ueberhaupt ein
    Netzwerkversuch stattfindet. Ein Verbindungsversuch ins Leere trennt daher
    die beiden Faelle.

    Dazu die tnsnames.ora: ohne sie und ohne den Eintrag LIMS kommt
    niemand ueber die Anmeldung hinaus - das soll beim Bau auffallen und
    nicht am Arbeitsplatz.
    """
    zeilen = [f"TRDF-Pruefmodul Selbsttest ({BITNESS}-bit)"]
    try:
        import cryptography
        zeilen.append(f"  cryptography {cryptography.__version__} vorhanden")
    except Exception as fehler:
        zeilen.append(f"  FEHLER: cryptography fehlt ({fehler})")
        return 1, zeilen

    # Was die Oberflaeche braucht: tkinter fuer die Tk-Fassung, pywebview
    # fuer die Weboberflaeche.
    for modul in oberflaeche:
        try:
            __import__(modul)
            zeilen.append(f"  {modul} vorhanden")
        except Exception as fehler:
            zeilen.append(f"  FEHLER: {modul} fehlt ({fehler})")
            return 1, zeilen

    try:
        gefunden = deskriptoren()
        zeilen.append(f"  {TNSNAMES} gelesen ({tnsnames_pfad()}): "
                      f"{', '.join(sorted(gefunden))}")
    except Exception as fehler:                             # noqa: BLE001
        zeilen.append(f"  FEHLER: {fehler}")
        return 1, zeilen

    dsn = ("(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=127.0.0.1)(PORT=1521))"
           "(CONNECT_DATA=(SERVICE_NAME=SELBSTTEST)))")
    try:
        oracledb.connect(user="selbsttest", password="selbsttest", dsn=dsn)
        zeilen.append("  unerwartet: es kam eine Verbindung zustande")
    except Exception as fehler:
        meldung = str(fehler).splitlines()[0]
        if "DPY-3016" in meldung or "cryptography" in meldung:
            zeilen.append(f"  FEHLER: Thin Mode unvollstaendig verpackt - {meldung}")
            return 1, zeilen
        zeilen.append(f"  Thin Mode einsatzbereit (erwarteter Netzwerkfehler: {meldung})")
    return 0, zeilen


# --------------------------------------------------------------------------
# Die TRDF-Pruefung
# --------------------------------------------------------------------------
#
# Eine Serie der Probenvorbereitung, in der das LIMS aus Rohwerten zwoelf
# Groessen rechnet. Was hier geholt wird, ist alles, was noetig ist, um
# dieselbe Rechnung noch einmal zu machen: die Rohwertparameter mit ihren
# Formelkuerzeln, die Pruefmethoden mit ihren Formeln, und was das LIMS
# gebucht hat.
#
# Die Kette:
#   UNTERSUCHUNGSMETHODE  Kuerzel traegt "TRDF"
#     -> S_FAHRPLAN       welche Serien anstehen
#       -> UM_ROHWERTE    welcher Rohwert unter welchem Formelkuerzel
#         -> ROHWERTPARAMETER  wie er heisst
#       -> ERGEBNISSE     was gebucht ist, je PROB_ID und PM_ID
#         -> PRUEFMETHODEN  die Formel dahinter

# Woran eine TRDF-Methode zu erkennen ist.
TRDF_MARKE = "TRDF"

# --------------------------------------------------------------------------
# Untersuchungsmethoden, die die Bodenphysik nicht mehr liest
# --------------------------------------------------------------------------
#
# TRDF3.1 ist der Vorgaenger von TRDF3.2. Ihre Zeilen stehen weiter im
# LIMS und werden gelegentlich noch eingelesen - im Profil und in der
# TRDF-Pruefung sind sie aber nicht gewollt: sie tragen dieselben
# Groessen unter derselben Bezeichnung, und welche der beiden Zahlen
# dann gilt, entscheidet die Methodenfolge und nicht das Labor.
#
# Draussen bleiben sie deshalb in der TRDF-Pruefung, im Blockprofil,
# in den Profilen und im Profilvergleich. Die Qualitaetspruefung
# fragt weiter alles: dort ist eine alte Zeile eine Zeile des Hauses
# und keine Stoerung.
#
# Ausgeschlossen wird ueber das *Kuerzel* und nicht ueber eine
# UM_ID: dieselbe Methode steht unter mehreren UM_ID, je Probenart
# eine, und eine Liste von Nummern waere beim naechsten Projekt falsch.
AUSGESCHLOSSENE_METHODEN = ("TRDF3.1",)


def ausgeschlossene_methoden_sql(bindungen: dict) -> str:
    """Die Unterabfrage auf die UM_ID der ausgeschlossenen Methoden."""
    namen = []
    for nummer, kuerzel in enumerate(AUSGESCHLOSSENE_METHODEN):
        schluessel = f"ausum{nummer}"
        bindungen[schluessel] = str(kuerzel).strip().upper()
        namen.append(f":{schluessel}")
    return (f"SELECT id FROM untersuchungsmethode "
            f"WHERE UPPER(TRIM(kuerzel)) IN ({', '.join(namen)})")


def ohne_ausgeschlossene(spalte: str, bindungen: dict) -> str:
    """Die Bedingung, die eine ausgeschlossene Methode draussen laesst.

    Leer, wo nichts ausgeschlossen ist - dann steht kein "AND 1=1" in
    der Abfrage, das jemand erklaeren muesste.

    **Die leere UM_ID bleibt drin.** ERGEBNISSE.UM_ID ist nullable und
    in diesem Haus haeufig leer; `spalte NOT IN (...)` ist fuer NULL
    aber nicht wahr, sondern unbekannt - eine Zeile ohne Methode waere
    damit stillschweigend verschwunden. Sie nennt keine
    ausgeschlossene Methode, also bleibt sie.
    """
    if not AUSGESCHLOSSENE_METHODEN:
        return ""
    return (f"({spalte} IS NULL OR {spalte} NOT IN "
            f"({ausgeschlossene_methoden_sql(bindungen)}))")


def ist_ausgeschlossen(kuerzel) -> bool:
    """Ob dieses Methodenkuerzel draussen bleibt - fuer die Listen.

    Dieselbe Frage wie in der Abfrage, nur an einer Zeile, die schon
    da ist: so faellt eine alte Methode auch aus dem
    Zwischenspeicher, in dem sie vor dieser Aenderung gelandet ist.
    """
    name = str(kuerzel or "").strip().upper()
    return any(name == str(eine).strip().upper()
               for eine in AUSGESCHLOSSENE_METHODEN)

# Der Wiederfindungsgrad steht unter dieser Pruefmethode - so steht es
# auch in den Formeln des LIMS selbst.
WGH_PM_ID = 701

# Der Aufschluss daneben. CO3 kommt aus einer eigenen Methode, deren
# Kuerzel den Parameter im Namen traegt; Cges aus der allgemeinen.
ATNULL_MARKE = "ATNULL"
ATNULL_CO3_MARKE = "ATNULLCO3"
PARA_CGES = 31
PARA_CO3 = 33


def trdf_methoden(zugang, verbindung=None) -> list[tuple]:
    """Die Untersuchungsmethoden, deren Kuerzel "TRDF" traegt.

    Ohne die ausgeschlossenen: was nicht in der Liste steht, ist auch
    nicht zu waehlen - und damit fragt keine der Abfragen, die an
    einer UM_ID haengen, mehr danach.
    """
    bindungen = {"marke": f"%{TRDF_MARKE}%"}
    zeilen = _zeilen(zugang, f"""
        SELECT id, kuerzel FROM untersuchungsmethode
         WHERE UPPER(kuerzel) LIKE :marke
           AND {ohne_ausgeschlossene("id", bindungen)}
         ORDER BY kuerzel, id
    """, bindungen, verbindung=verbindung)
    return [(zeile[0], str(zeile[1] or "").strip()) for zeile in zeilen]


def trdf_serien(zugang, um_ids, verbindung=None) -> list[str]:
    """Die Serien aus dem Fahrplan, die eine TRDF-Methode fuehren.

    Derselbe Weg wie bei jeder anderen Methode - deshalb steht er in
    serien_mit_methoden(). Der eigene Name bleibt: der TRDF-Reiter
    fragt nach TRDF-Serien, nicht nach "Serien zu diesen IDs".
    """
    return serien_mit_methoden(zugang, um_ids, verbindung=verbindung)


ROHWERT_FELDER = ("rohw_id", "lnr", "formelkuerzel", "name", "kuerzel")


def trdf_rohwertparameter(zugang, um_id, verbindung=None) -> list[dict]:
    """Die Rohwerte dieser Methode - Name und Formelkuerzel.

    Damit wird die eingefuegte Spalte zum Formelkuerzel: der Kopf der
    Liste traegt den Namen, gerechnet wird mit dem Kuerzel. Beides steht
    im LIMS, nichts davon wird im Programm gepflegt.

    Das Formelkuerzel kann an der Methode haengen (UM_ROHWERTE) oder am
    Parameter selbst; das erste sticht.
    """
    zeilen = _zeilen(zugang, """
        SELECT r.id, u.lnr,
               NVL(u.formelkuerzel, r.formelkuerzel), r.name, r.kuerzel
          FROM um_rohwerte u
          JOIN rohwertparameter r ON r.id = u.rohw_id
         WHERE u.um_id = :um_id
         ORDER BY u.lnr, r.sort, r.id
    """, {"um_id": um_id}, verbindung=verbindung)
    return _dicts(zeilen, ROHWERT_FELDER)


TRDF_METHODEN_FELDER = ("pm_id", "pm_ver", "para_id", "name", "kurzname",
                        "formelkuerzel", "formel", "gegr_id", "geme_id",
                        "format", "parameter")


def trdf_pruefmethoden(zugang, serie: str, um_id, verbindung=None,
                       proben=None) -> list[dict]:
    """Die Pruefmethoden dieser Serie - mit ihren Formeln.

    Eingegrenzt auf das, was in ERGEBNISSE zu dieser Serie und Methode
    wirklich vorkommt, und mit *deren* PM_VER: zu einer Pruefmethode gibt
    es mehrere Staende, und gerechnet hat das LIMS mit dem, der an der
    Ergebniszeile haengt.

    Ohne GEME_ID ist es eine berechnete Groesse, mit ist es ein Rohwert -
    bis auf zwei Ausnahmen, die das Labor kennt. Verlassen wird sich
    darauf nicht: was eine Formel hat, wird gerechnet.
    """
    bindungen = {"um_id": um_id}
    wo = _wonach("e", serie, proben, bindungen)
    zeilen = _zeilen(zugang, f"""
        SELECT p.id, p.version, p.para_id, p.name, p.kurzname,
               p.formelkuerzel, p.formel, p.gegr_id, p.geme_id, p.format,
               pa.name
          FROM pruefmethoden p
          LEFT JOIN parameter pa ON pa.id = p.para_id
         WHERE (p.id, p.version) IN (SELECT DISTINCT e.pm_id, e.pm_ver
                                       FROM ergebnisse e
                                      WHERE {wo}
                                        AND e.um_id = :um_id)
         ORDER BY p.id, p.version
    """, bindungen, verbindung=verbindung)
    return _dicts(zeilen, TRDF_METHODEN_FELDER)


def serien_mit_methoden(zugang, um_ids, verbindung=None) -> list[str]:
    """Die Serien aus dem Fahrplan, die eine dieser Methoden fuehren.

    S_FAHRPLAN sagt, was ansteht, kennt aber keine UM_ID; die steht in
    TEILPROBEN. Deshalb der Weg ueber EXISTS - er fragt je Serie nach
    einer Teilprobe und nicht die Ergebnistabelle nach allen Serien.
    """
    if not um_ids:
        return []
    namen = [f":um{nummer}" for nummer in range(len(um_ids))]
    bindungen = {f"um{nummer}": wert for nummer, wert in enumerate(um_ids)}
    zeilen = _zeilen(zugang, f"""
        SELECT DISTINCT f.serie
          FROM s_fahrplan f
         WHERE f.serie IS NOT NULL
           AND EXISTS (SELECT 1 FROM teilproben t
                        WHERE t.serie = f.serie
                          AND t.um_id IN ({', '.join(namen)}))
         ORDER BY f.serie DESC
    """, bindungen, verbindung=verbindung)
    return _seriennamen(zeilen)


# Wie viele Probennummern eine Abfrage auf einmal vertraegt. Oracle
# nimmt in einer IN-Liste tausend; wer mehr hat, hat eine Serie.
PROBEN_HOECHSTENS = 500


def _wonach(alias: str, serie, proben, bindungen: dict, spalte=None,
            nummernspalte: str = "") -> str:
    """Woran eine TRDF-Abfrage haengt: an der Serie oder an Proben.

    Das ist der ganze Unterschied zwischen den beiden Wegen. Alles
    andere - die Methode, die Verbindung ueber PROB_ID, die Felder -
    bleibt gleich, und deshalb bleiben es dieselben Abfragen.

    `nummernspalte` fuer die Abfragen, die PROBEN schon verbunden
    haben: dort geht es ohne Unterabfrage. Siehe `_probenfilter`.
    """
    if proben:
        return _probenfilter(spalte or f"{alias}.prob_id", proben,
                             bindungen, nummernspalte)
    bindungen["serie"] = serie
    return f"{alias}.serie = :serie"


def _idfilter(spalte: str, ids, bindungen: dict, vorsilbe="pid") -> str:
    """Die Bedingung auf eine Liste von IDs - ueber den Schluessel.

    Der Unterschied zu `_probenfilter` ist der Schluessel: dort die
    Probennummer, hier der Primaerschluessel. Beide sind indiziert -
    seit `_probenfilter` ohne `UPPER` auf der Spalte vergleicht -, und
    wo der Aufrufer die ID schon hat (die Ergebniszeilen tragen sie),
    ist sie der kuerzeste Weg.
    """
    namen = []
    for nummer, wert in enumerate(list(ids)[:PROBEN_HOECHSTENS]):
        if wert is None:
            continue
        schluessel = f"{vorsilbe}{nummer}"
        bindungen[schluessel] = int(wert)
        namen.append(f":{schluessel}")
    if not namen:
        return "1 = 0"           # keine ID genannt, keine Zeile zurueck
    return f"{spalte} IN ({', '.join(namen)})"


def _probenfilter(spalte: str, proben, bindungen: dict,
                  nummernspalte: str = "") -> str:
    """Die Bedingung, die eine Abfrage auf einzelne Proben einschraenkt.

    Gesucht wird ueber PROBEN.PROBE_NR; die Verbindung zu den
    Ergebnissen ist PROBEN.ID = ERGEBNISSE.PROB_ID.

    **Ohne `UPPER` auf der Spalte** - und das ist hier die ganze
    Geschwindigkeit. `UPPER(probe_nr)` ist ein Funktionsaufruf auf der
    Spalte, und damit kann Oracle den Index auf PROBEN.PROBE_NR nicht
    benutzen: es geht die Tabelle durch, je Abruf, und bei einem
    Profilvergleich ueber dreissig Plots dauerte das ein Vielfaches
    der ganzen Rechnung darueber.

    Die Gross- und Kleinschreibung geht dabei nicht verloren, sie
    wandert nur auf die andere Seite: das Haus fuehrt die Probennummer
    als Ziffern mit einem *grossen* Buchstaben ("2026W00500"), und
    gebunden wird beides - der Wert, wie er kam, und seine Grossform,
    wo sie sich unterscheidet. Zwei Bindungen statt einer kosten
    nichts; eine Funktion auf der Spalte kostet den Index.

    `nummernspalte` ist der Weg fuer Abfragen, die PROBEN schon
    verbunden haben: dann wird direkt an `p.probe_nr` gefiltert, ohne
    Unterabfrage. Oracle kann dann vom Index auf PROBE_NR ueber den
    Fremdschluessel in ERGEBNISSE treiben - die Richtung, die bei
    zweihundert Proben aus einer Tabelle mit Millionen Zeilen die
    richtige ist.
    """
    namen = []
    echte = [str(wert).strip() for wert in proben if str(wert).strip()]
    for nummer, wert in enumerate(echte[:PROBEN_HOECHSTENS]):
        schluessel = f"pnr{nummer}"
        bindungen[schluessel] = wert
        namen.append(f":{schluessel}")
        # Die Grossform dazu, wo sie eine andere ist. Gebucht ist die
        # grosse; wer von Hand tippt, tippt manchmal klein, und eine
        # zweite Bindung ist billiger als ein Tabellendurchgang.
        if wert.upper() != wert:
            gross = f"pnrg{nummer}"
            bindungen[gross] = wert.upper()
            namen.append(f":{gross}")
    if not namen:
        return "1 = 0"           # keine Probe genannt, keine Zeile zurueck
    if nummernspalte:
        return f"{nummernspalte} IN ({', '.join(namen)})"
    return (f"{spalte} IN (SELECT id FROM proben "
            f"WHERE probe_nr IN ({', '.join(namen)}))")


TRDF_ERGEBNIS_FELDER = ("prob_id", "probe_nr", "wdh_um", "wdh_me", "lnr",
                        "pm_id", "pm_ver", "um_id", "gegr_id", "mw_roh", "mw",
                        "psta_id", "korrektur_flag", "fc8", "serie",
                        "part_id")


def trdf_ergebnisse(zugang, serie: str, um_id, verbindung=None,
                    proben=None) -> list[dict]:
    """Was das LIMS zu dieser Serie gebucht hat - Rohwerte und Gerechnetes.

    Wiederholungen bleiben draussen: geprueft wird die Erstmessung.

    Mitgelesen wird der ganze Schluessel der Zeile - UM_ID und GEGR_ID
    gehoeren dazu - und ihr Bearbeitungsstand. Beides braucht der
    Ruecksprung: eine Zeile laesst sich nur ueber ihren vollstaendigen
    Schluessel ansprechen, und was vorher darin stand, muss in die
    Sicherung, bevor etwas ueberschrieben wird.

    Die PART_ID kommt mit: sie sagt, an welcher Probenart gebucht
    wurde (1 Boden, 2 Pflanze, 3 Wasser, 4 Humus). Bisher stand die
    Probenart im Kopf des Reiters aus dem *Seriennamen* - das ist die
    Hausschreibweise und nicht die Auskunft des LIMS, und bei
    einzelnen Proben gibt es keinen Seriennamen, aus dem sie zu raten
    waere.
    """
    bindungen = {"um_id": um_id}
    wo = _wonach("e", serie, proben, bindungen,
                 nummernspalte="p.probe_nr")
    zeilen = _zeilen(zugang, f"""
        SELECT e.prob_id, p.probe_nr, p.wdh_um, p.wdh_me, e.lnr,
               e.pm_id, e.pm_ver, e.um_id, e.gegr_id, e.mw_roh, e.mw,
               e.psta_id, e.korrektur_flag, e.fc8, e.serie, e.part_id
          FROM ergebnisse e
          JOIN proben p ON p.id = e.prob_id
         WHERE {wo} AND e.um_id = :um_id
           AND NVL(p.wdh_um, 1) = 1 AND NVL(p.wdh_me, 1) = 1
         ORDER BY e.lnr, p.probe_nr, e.pm_id
    """, bindungen, verbindung=verbindung)
    return _dicts(zeilen, TRDF_ERGEBNIS_FELDER)


TRDF_ANHANG_FELDER = ("probe_nr", "prob_id", "um_id", "rohw_id", "lnr",
                      "formelkuerzel",
                      "art", "mw", "mw_old", "format")


def trdf_rohwerte_anhang(zugang, serie: str, um_id, verbindung=None,
                         proben=None) -> list:
    """Die Rohwerte, wie sie am Teilprobenanhang haengen.

    Das LIMS fuehrt sie zweimal: als Ergebniszeile unter ihrer
    Pruefmethode und hier, an der Teilprobe, unter ihrem Formelkuerzel.
    Aus dieser Stelle rechnen die Formeln - wer nur die Ergebniszeile
    korrigiert, aendert am Rechenweg des LIMS nichts.

    Der Schluessel ist (PROB_ID, UM_ID, ROHW_ID); die Serie steht nicht
    darin und kommt ueber TEILPROBEN dazu.
    """
    bindungen = {"um_id": um_id}
    wo = _wonach("t", serie, proben, bindungen, spalte="a.prob_id")
    zeilen = _zeilen(zugang, f"""
        SELECT p.probe_nr, a.prob_id, a.um_id, a.rohw_id, a.lnr,
               a.formelkuerzel, a.art, a.mw, a.mw_old, a.format
          FROM teilproben_anhang a
          JOIN teilproben t ON t.prob_id = a.prob_id AND t.um_id = a.um_id
          JOIN proben p ON p.id = a.prob_id
         WHERE {wo} AND t.um_id = :um_id
         ORDER BY a.prob_id, a.lnr
    """, bindungen, verbindung=verbindung)
    return _anhangzeilen(zeilen)


def _anhangzeilen(zeilen) -> list:
    """Die Anhangzeilen als Woerterbuecher - Kuerzel und Nummer gesaeubert."""
    gefunden = _dicts(zeilen, TRDF_ANHANG_FELDER)
    for eintrag in gefunden:
        eintrag["formelkuerzel"] = str(eintrag["formelkuerzel"] or "").strip()
        eintrag["probe_nr"] = str(eintrag["probe_nr"] or "").strip()
    return gefunden


def trdf_rohwerte_nachtrag(zugang, prob_ids, um_id, verbindung=None) -> list:
    """Der Teilprobenanhang zu diesen Probennummern - ueber alle PROB_ID.

    Dieselbe Probe steht im LIMS mehrfach: dieselbe PROBE_NR unter
    einer anderen PROB_ID, oft in einer anderen Serie. Der
    Teilprobenanhang haengt dann an einer Anlage, die die Serie nicht
    sieht - die Rohwerte bleiben leer, obwohl sie gebucht sind.
    Dieselbe Lage wie beim Aufschluss, und derselbe Weg hinaus.

    Gefragt wird unter **derselben** Untersuchungsmethode. Das ist die
    ganze Auswahl: wer TRDF3.2 abruft, bekommt die Rohwerte der
    TRDF3.2 und nicht die der TRDF3.1, die daneben an derselben Probe
    haengen. TRDF3.1 ist der Vorgaenger, das Haus hat sie verworfen,
    und ihre Zahlen sind nicht dieselben - welche von beiden gilt,
    darf nicht die Reihenfolge entscheiden.

    Zur Sicherheit bleiben die ausgeschlossenen Methoden auch dann
    draussen, wenn eine von ihnen als `um_id` hereinkaeme: ein Weg,
    der eine verworfene Methode nur deshalb nicht liest, weil sie
    nirgends zu waehlen ist, ist einen Handgriff davon entfernt, sie
    doch zu lesen.

    Sortiert wird nach PROB_ID aufsteigend. Haben mehrere Anlagen
    derselben Probe einen Anhang, gilt die zuletzt angelegte: der
    Aufrufer legt die Zeilen der Reihe nach ab, und die letzte
    ueberschreibt. Das ist eine Festlegung und keine Wahrheit -
    deshalb steht die PROB_ID an der Zeile, und wer sie nachsieht,
    findet auch die andere.
    """
    bindungen = {"um_id": um_id}
    wo = _idfilter("q.id", prob_ids, bindungen)
    ohne_alte = ohne_ausgeschlossene("a.um_id", bindungen)
    zeilen = _zeilen(zugang, f"""
        SELECT p.probe_nr, a.prob_id, a.um_id, a.rohw_id, a.lnr,
               a.formelkuerzel, a.art, a.mw, a.mw_old, a.format
          FROM teilproben_anhang a
          JOIN proben p ON p.id = a.prob_id
         WHERE p.probe_nr IN (SELECT q.probe_nr FROM proben q WHERE {wo})
           AND a.um_id = :um_id
           AND NVL(p.wdh_um, 1) = 1 AND NVL(p.wdh_me, 1) = 1
           {f"AND {ohne_alte}" if ohne_alte else ""}
         ORDER BY p.probe_nr, a.prob_id, a.lnr
    """, bindungen, verbindung=verbindung)
    return _anhangzeilen(zeilen)


def trdf_wiederfindung(zugang, serie: str, verbindung=None,
                       proben=None) -> dict:
    """Der Wiederfindungsgrad je Probe - PROB_ID auf MW.

    Er haengt nicht an der TRDF-Methode, sondern an seiner eigenen; die
    Formeln des LIMS holen ihn ueber die PM_ID, und genau so wird er
    hier geholt.
    """
    bindungen = {"pm_id": WGH_PM_ID}
    wo = _wonach("e", serie, proben, bindungen)
    zeilen = _zeilen(zugang, f"""
        SELECT e.prob_id, e.mw
          FROM ergebnisse e
         WHERE {wo} AND e.pm_id = :pm_id
    """, bindungen, verbindung=verbindung)
    return {zeile[0]: zeile[1] for zeile in zeilen}


AUFSCHLUSS_FELDER = ("prob_id", "para_id", "kuerzel", "mw")


def trdf_aufschluss(zugang, serie: str, verbindung=None,
                    proben=None) -> list[dict]:
    """Cges und CO3 aus dem Aufschluss - zum Danebenstellen.

    Genommen wird MW, der Gehalt. Zwei Methoden: CO3 steht unter der,
    deren Kuerzel den Parameter im Namen traegt (ATNULLCO3), Cges unter
    der allgemeinen. Weil das eine im anderen steckt, wird beim Lesen
    nach dem Kuerzel unterschieden und nicht in der Anweisung.
    """
    bindungen = {"marke": f"%{ATNULL_MARKE}%",
                 "cges": PARA_CGES, "co3": PARA_CO3}
    wo = _wonach("e", serie, proben, bindungen)
    zeilen = _zeilen(zugang, f"""
        SELECT e.prob_id, e.para_id, u.kuerzel, e.mw
          FROM ergebnisse e
          JOIN untersuchungsmethode u ON u.id = e.um_id
         WHERE {wo}
           AND UPPER(u.kuerzel) LIKE :marke
           AND e.para_id IN (:cges, :co3)
    """, bindungen, verbindung=verbindung)
    gefunden = _dicts(zeilen, AUFSCHLUSS_FELDER)
    for eintrag in gefunden:
        eintrag["kuerzel"] = str(eintrag["kuerzel"] or "").strip()
    return [eintrag for eintrag in gefunden if aufschluss_passt(eintrag)]


# Dieselben Felder, und die Probennummer dazu: der Nachtrag kommt von
# einer *anderen* PROB_ID, und ueber die liesse er sich der Probe nicht
# zuordnen.
AUFSCHLUSS_NACHTRAG_FELDER = ("probe_nr", "prob_id", "serie", "para_id",
                              "kuerzel", "mw")


def trdf_aufschluss_nachtrag(zugang, prob_ids, verbindung=None) -> list[dict]:
    """Cges und CO3 zu diesen Probennummern - ueber alle PROB_ID.

    Dieselbe Probe steht im LIMS mehrfach: dieselbe PROBE_NR unter
    einer anderen PROB_ID, oft in einer anderen Serie. Der Aufschluss
    ist dann nur an einer von ihnen gebucht, und die TRDF-Serie sieht
    ihn nicht - die Spalten Cges und CO3 bleiben leer, obwohl das Labor
    die Zahl hat.

    Gesucht wird deshalb ueber die Probennummer - aber angesetzt wird
    an der PROB_ID, die der Aufrufer schon hat: die Nummern dazu holt
    eine Unterabfrage ueber den Primaerschluessel, und verglichen wird
    Spalte mit Spalte. Kein UPPER, denn beide Seiten kommen aus
    derselben Spalte; mit UPPER ginge Oracle die ganze Tabelle PROBEN
    durch, und das kostete bei jedem Serienabruf Sekunden.

    *Welcher* Wert dann gilt, entscheidet der Aufrufer: er nimmt den
    Nachtrag nur, wo an seiner eigenen PROB_ID keiner steht. Anders
    waere es eine stille Ersetzung - und die Zahl zweier verschiedener
    Proben mit derselben Nummer ist nicht dieselbe Zahl.

    Die Serie kommt mit, damit im Hinweis stehen kann, woher der Wert
    stammt. Eine Zahl aus einer anderen Serie ohne diese Auskunft waere
    nicht nachzupruefen.

    Sortiert wird nach PROB_ID absteigend: haben mehrere Anlagen der
    Probe einen Aufschluss, gilt die zuletzt angelegte. Das ist eine
    Festlegung und keine Wahrheit - deshalb steht die PROB_ID im
    Hinweis, und wer sie nachsieht, findet auch die anderen.
    """
    bindungen = {"marke": f"%{ATNULL_MARKE}%",
                 "cges": PARA_CGES, "co3": PARA_CO3}
    wo = _idfilter("q.id", prob_ids, bindungen)
    zeilen = _zeilen(zugang, f"""
        SELECT p.probe_nr, e.prob_id, e.serie, e.para_id, u.kuerzel, e.mw
          FROM ergebnisse e
          JOIN proben p ON p.id = e.prob_id
          JOIN untersuchungsmethode u ON u.id = e.um_id
         WHERE p.probe_nr IN (SELECT q.probe_nr FROM proben q WHERE {wo})
           AND UPPER(u.kuerzel) LIKE :marke
           AND e.para_id IN (:cges, :co3)
           AND e.mw IS NOT NULL
           AND NVL(p.wdh_um, 1) = 1 AND NVL(p.wdh_me, 1) = 1
         ORDER BY p.probe_nr, e.para_id, e.prob_id DESC
    """, bindungen, verbindung=verbindung)
    gefunden = _dicts(zeilen, AUFSCHLUSS_NACHTRAG_FELDER)
    for eintrag in gefunden:
        eintrag["kuerzel"] = str(eintrag["kuerzel"] or "").strip()
        eintrag["probe_nr"] = str(eintrag["probe_nr"] or "").strip()
        eintrag["serie"] = str(eintrag["serie"] or "").strip()
    return [eintrag for eintrag in gefunden if aufschluss_passt(eintrag)]


def aufschluss_passt(eintrag: dict) -> bool:
    """Kommt dieser Wert aus der Methode, die fuer ihn zustaendig ist?"""
    co3_methode = ATNULL_CO3_MARKE in str(eintrag.get("kuerzel", "")).upper()
    if eintrag.get("para_id") == PARA_CO3:
        return co3_methode
    return not co3_methode


# --------------------------------------------------------------------------
# Der Rueckweg der TRDF-Pruefung
# --------------------------------------------------------------------------
# Dies ist der einzige Weg im Programm, der einen Messwert in ERGEBNISSE
# ueberschreibt. Er steht deshalb hier fuer sich, mit eigenem Namen und
# eigener Anweisung, und nicht im gewoehnlichen Export - dort laesst NVL
# jede Zahl stehen, und das soll dort so bleiben.
#
# Erlaubt ist er, weil er etwas anderes tut als der Export einer
# Laufdatei: dort kommen Werte von einem Geraet und fuellen leere
# Zeilen; hier korrigiert ein Mensch einen Rohwert, den das Labor als
# falsch erkannt hat, und die daraus folgenden Groessen muessen
# mitwandern. Ein zweiter Wert daneben waere keine Korrektur, sondern
# ein Widerspruch.
#
# Drei Riegel liegen davor, und sie liegen ausserhalb dieser Datei:
# geschrieben wird nur, was in der Uebersicht Zeile fuer Zeile mit altem
# und neuem Wert bestaetigt wurde; vorher geht der alte Stand in eine
# Sicherung; und getroffen wird ausschliesslich der volle Schluessel
# einer vorhandenen Zeile - angelegt wird nichts.

# Was in FC8 steht, damit im LIMS zu sehen ist, woher der Wert kommt.
TRDF_FC8 = "TRDF-Korrektur"

# MW und MW_ROH tragen bei TRDF denselben Wert: die Faktoren des LIMS
# (FAKTOR, FAKTOR_WGH, END_FAKTOR) gelten hier nicht, gerechnet wird
# ausschliesslich mit dem, was in den Formeln steht.
TRDF_EXPORT_SPALTEN = ("MW_ROH", "MW", "FC8", "PSTA_ID", "KORREKTUR_FLAG")


def trdf_export_sql() -> str:
    """Die Anweisung, die eine korrigierte Ergebniszeile ueberschreibt.

    Kein NVL: hier ist das Ueberschreiben der Zweck. Dafuer ist die
    Anweisung so eng wie moeglich - fuenf Spalten, der volle Schluessel,
    und keine Zeile, die es nicht schon gibt (ohne Treffer meldet der
    Aufrufer die Zeile, statt sie anzulegen).

    MW und MW_ROH bekommen denselben Wert. Bei TRDF gibt es keine
    Faktorverrechnung; ein Gehalt, der vom gemessenen Wert abweicht,
    waere hier eine zweite Aussage ueber dieselbe Sache.

    Die GEGR_ID darf leer sein - in ERGEBNISSE ist sie laut Schema
    nullable. Ein schlichtes `gegr_id = :gegr_id` traefe eine solche
    Zeile nie: in SQL ist NULL mit nichts gleich, auch nicht mit NULL,
    und die Anweisung liefe ins Leere, ohne dass etwas schiefginge.
    Deshalb der zweite Zweig; die Gleichheit steht zuerst, damit der
    Index weiter benutzt wird.
    """
    return """
        UPDATE ergebnisse SET
               mw_roh = :wert,
               mw     = :wert,
               fc8    = :fc8,
               psta_id = :psta_id,
               korrektur_flag = :korrektur_flag
         WHERE prob_id = :prob_id AND pm_id = :pm_id AND pm_ver = :pm_ver
           AND um_id = :um_id
           AND (gegr_id = :gegr_id OR (gegr_id IS NULL AND :gegr_id IS NULL))
    """


TRDF_SATZ_FELDER = ("wert", "fc8", "psta_id", "korrektur_flag", "prob_id",
                    "pm_id", "pm_ver", "um_id", "gegr_id")

# Zurueck gilt ein Feld mehr: MW steht in der Sicherung als eigene
# Spalte, und nur die Korrektur darf annehmen, dass es dasselbe ist wie
# MW_ROH. Vor ihr kann dort etwas anderes gestanden haben - eine alte
# Faktorverrechnung etwa -, und eine Sicherung, die das wegwirft,
# stellt nicht den Stand von vorher wieder her.
TRDF_ZURUECK_FELDER = TRDF_SATZ_FELDER + ("mw",)


def trdf_zurueck_sql() -> str:
    """Die Anweisung, die eine Ergebniszeile auf ihren Stand zurueckstellt.

    Wie `trdf_export_sql`, mit einem Unterschied: MW_ROH und MW bekommen
    nicht denselben Wert, sondern jeder seinen eigenen aus der
    Sicherung. Der Schluessel ist Wort fuer Wort derselbe - auch der
    zweite Zweig fuer die leere GEGR_ID.
    """
    return """
        UPDATE ergebnisse SET
               mw_roh = :wert,
               mw     = :mw,
               fc8    = :fc8,
               psta_id = :psta_id,
               korrektur_flag = :korrektur_flag
         WHERE prob_id = :prob_id AND pm_id = :pm_id AND pm_ver = :pm_ver
           AND um_id = :um_id
           AND (gegr_id = :gegr_id OR (gegr_id IS NULL AND :gegr_id IS NULL))
    """

# Der Anhang traegt den Wert und den Stand davor - kein Kennzeichen.
# Was geschehen ist, steht in der Ergebniszeile daneben und im Protokoll.
TRDF_ANHANG_SATZ_FELDER = ("wert", "prob_id", "um_id", "rohw_id")


def trdf_anhang_sql() -> str:
    """Die Anweisung, die einen Rohwert am Teilprobenanhang richtigstellt.

    MW_OLD nimmt den bisherigen Wert auf - so, wie das LIMS es selbst
    haelt: die Spalte traegt den Stand, der gerade ersetzt wurde. Dafuer
    steht dort `mw` und keine Bindevariable: Oracle wertet alle
    Zuweisungen einer UPDATE-Anweisung gegen den Stand *vor* der
    Aenderung aus, es kommt also der Wert hinein, der wirklich in der
    Zeile stand - und nicht der, den LabControl vor einer Minute gelesen
    hat.
    """
    return """
        UPDATE teilproben_anhang SET mw_old = mw, mw = :wert
         WHERE prob_id = :prob_id AND um_id = :um_id AND rohw_id = :rohw_id
    """


# Beim Zurueckspielen wird auch MW_OLD wieder gesetzt: die Sicherung
# haelt den ganzen Stand fest, und ein halb wiederhergestellter waere
# keiner. Deshalb eine zweite Anweisung - die Korrektur darf MW_OLD
# nicht binden (sonst schriebe sie einen veralteten Stand fort), das
# Zurueckspielen muss es.
TRDF_ANHANG_ZURUECK_FELDER = ("wert", "alt", "prob_id", "um_id", "rohw_id")


def trdf_anhang_zurueck_sql() -> str:
    """Die Anweisung, die den Anhang auf den gesicherten Stand zurueckstellt."""
    return """
        UPDATE teilproben_anhang SET mw = :wert, mw_old = :alt
         WHERE prob_id = :prob_id AND um_id = :um_id AND rohw_id = :rohw_id
    """


def trdf_anhang_satz_pruefen(satz: dict, leeren: bool = False):
    """Wie beim Ergebnis: nichts Halbes in die Anweisung."""
    fehlend = [feld for feld in TRDF_ANHANG_SATZ_FELDER
               if satz.get(feld) is None]
    if fehlend:
        raise ValueError("Unvollstaendiger Satz fuer den Teilprobenanhang: "
                         + ", ".join(fehlend))
    if not str(satz["wert"]).strip() and not leeren:
        raise ValueError("Ein leerer Wert wuerde die Zahl im LIMS loeschen.")


# Der eine Schluesselteil, der leer sein darf: ERGEBNISSE.GEGR_ID ist
# nullable, und eine Zeile ohne Geraetegruppe ist trotzdem eine Zeile.
# Die Anweisung faengt den Fall mit einem eigenen Zweig ab.
TRDF_DARF_LEER = ("gegr_id",)


def trdf_satz_pruefen(satz: dict, leeren: bool = False):
    """Laesst nur durch, was vollstaendig ist - und wirft sonst.

    Ein fehlender Schluesselteil wuerde die Anweisung nicht auf eine
    andere Zeile lenken (sie faende dann gar keine), aber ein leerer Wert
    wuerde eine Zahl loeschen. Beides wird hier abgefangen, bevor die
    Transaktion beginnt.

    Die GEGR_ID ist die Ausnahme: sie darf im LIMS leer sein, und dann
    muss auch der Satz sie leer tragen - sonst faende die Anweisung die
    Zeile nicht.

    `leeren` ist die zweite: die TRDF-Pruefung darf einen Wert auch
    loeschen. Das LIMS kennt dort drei Staende - eine Zahl, ein „x“
    (hier soll nichts stehen) und eine leere Zelle -, und wer eine
    Variante wechselt, stellt genau diese Staende her. Es geschieht nur
    ueber eine bestaetigte Uebersicht, die sagt, wie viele Werte
    geleert werden, und nach einer Sicherung.
    """
    fehlend = [feld for feld in TRDF_SATZ_FELDER
               if satz.get(feld) is None and feld not in TRDF_DARF_LEER]
    if "gegr_id" not in satz:
        fehlend.append("gegr_id")
    if fehlend:
        raise ValueError("Unvollstaendiger Satz fuer den TRDF-Rueckweg: "
                         + ", ".join(fehlend))
    if not str(satz["wert"]).strip() and not leeren:
        raise ValueError("Ein leerer Wert wuerde die Zahl im LIMS loeschen.")


# Beim Zurueckspielen gelten andere Regeln als beim Korrigieren, und
# zwar strengere und lockerere zugleich. Der Schluessel muss vollstaendig
# sein wie immer - er sucht die Zeile. Die geschriebenen Spalten aber
# duerfen leer sein, denn zurueckgestellt wird der Stand, den die
# Sicherung festhaelt: PSTA_ID ist im LIMS nullable, und wo vor der
# Korrektur kein Bearbeitungsstand und kein Wert stand, darf danach
# auch keiner stehen. Sonst waere das Zurueckspielen keines, sondern
# eine zweite Korrektur.
TRDF_ZURUECK_SCHLUESSEL = ("prob_id", "pm_id", "pm_ver", "um_id")


def trdf_zurueck_pruefen(satz: dict):
    """Der Schluessel muss stehen - der gesicherte Stand darf leer sein."""
    fehlend = [feld for feld in TRDF_ZURUECK_SCHLUESSEL
               if satz.get(feld) is None]
    # Da sein muessen sie alle: was die Anweisung bindet und der Satz
    # nicht traegt, faende Oracle nicht - und der Stand von damals
    # bliebe halb wiederhergestellt.
    fehlend += [feld for feld in TRDF_ZURUECK_FELDER if feld not in satz]
    if fehlend:
        raise ValueError("Unvollstaendiger Satz fuer das Zurueckspielen: "
                         + ", ".join(fehlend))


NACHLESEN_JE_FRAGE = 200
"""So viele Saetze fragt eine Nachlese-Abfrage auf einmal ab.

Eine Liste in IN (...) darf bei Oracle hoechstens 1000 Eintraege haben;
200 bleibt weit darunter und haelt die Anweisung kurz genug fuer den
Statement-Cache.
"""

ERGEBNIS_SCHLUESSEL = ("prob_id", "pm_id", "pm_ver", "um_id", "gegr_id")
ANHANG_SCHLUESSEL = ("prob_id", "um_id", "rohw_id")


def _in_liste(spalten: tuple, anzahl: int) -> str:
    """`(a, b) IN ((:a0, :b0), (:a1, :b1), ...)` fuer `anzahl` Saetze."""
    tupel = ", ".join(
        "(" + ", ".join(f":{spalte}{nummer}" for spalte in spalten) + ")"
        for nummer in range(anzahl))
    return f"({', '.join(spalten)}) IN ({tupel})"


def trdf_nachlesen_sql(anzahl: int = 1) -> str:
    """Was jetzt wirklich in den Ergebniszeilen steht - fuer `anzahl`
    Saetze in einer Abfrage.

    Gefragt wird mit demselben Schluessel wie beim Schreiben. GEGR_ID
    darf leer sein, und NULL faende in einer IN-Liste nie etwas; deshalb
    steht sie nur in der Antwort und wird in Python verglichen.
    """
    return f"""
        SELECT prob_id, pm_id, pm_ver, um_id, gegr_id, mw_roh
          FROM ergebnisse
         WHERE {_in_liste(ERGEBNIS_SCHLUESSEL[:-1], anzahl)}
    """


def trdf_anhang_nachlesen_sql(anzahl: int = 1) -> str:
    """Dasselbe fuer den Teilprobenanhang."""
    return f"""
        SELECT prob_id, um_id, rohw_id, mw
          FROM teilproben_anhang
         WHERE {_in_liste(ANHANG_SCHLUESSEL, anzahl)}
    """


def _angekommen(steht_da, gewollt) -> bool:
    """Steht jetzt da, was hingeschrieben werden sollte?

    Verglichen wird erst als Text, dann als Zahl: das LIMS speichert
    Messwerte als Zeichenkette, und ein angehaengtes Leerzeichen oder
    eine fehlende Null waere kein Unterschied in der Sache.
    """
    hier, dort = str(steht_da or "").strip(), str(gewollt or "").strip()
    if hier == dort:
        return True
    eine, andere = als_zahl(hier), als_zahl(dort)
    return eine is not None and andere is not None and eine == andere


def _schluesselwert(wert):
    """Eine ID so, dass 7, 7.0 und Decimal("7") derselbe Schluessel sind."""
    if wert is None:
        return None
    if isinstance(wert, bool):
        return wert
    try:
        ganz = int(wert)
        if ganz == wert:
            return ganz
    except (TypeError, ValueError):
        pass
    return str(wert).strip()


def _nachpruefen(cursor, sql_fuer, saetze, schluessel: tuple,
                 gefragt: tuple | None = None) -> list:
    """Liest die geschriebenen Zeilen zurueck und meldet, was nicht ankam.

    Ein UPDATE, das keine Zeile trifft, ist kein Fehler - es ist nur
    nichts geschehen. Ein UPDATE, das eine Zeile trifft und trotzdem den
    alten Wert stehen laesst, waere einer, und beides sieht von aussen
    gleich aus. Deshalb wird nachgesehen, nachdem festgeschrieben wurde.

    Gefragt wird als Sammelabfrage: je `NACHLESEN_JE_FRAGE` Saetze eine
    Rundreise statt einer je Satz. `sql_fuer(anzahl)` liefert die
    Anweisung, die Antwort traegt vorne `schluessel` und zuletzt den
    Wert. `gefragt` sind die Spalten, die in der Anweisung gebunden
    werden (ohne Angabe: alle aus `schluessel`).
    """
    saetze = list(saetze)
    gefragt = schluessel if gefragt is None else gefragt
    steht_da = {}
    for anfang in range(0, len(saetze), NACHLESEN_JE_FRAGE):
        stueck = saetze[anfang:anfang + NACHLESEN_JE_FRAGE]
        bindungen = {f"{feld}{nummer}": satz[feld]
                     for nummer, satz in enumerate(stueck)
                     for feld in gefragt}
        cursor.execute(sql_fuer(len(stueck)), bindungen)
        for zeile in cursor.fetchall() or ():
            zeile = tuple(zeile)
            schluesselteil = tuple(_schluesselwert(wert)
                                   for wert in zeile[:len(schluessel)])
            steht_da.setdefault(schluesselteil, zeile[-1])
    geblieben = []
    for satz in saetze:
        ziel = tuple(_schluesselwert(satz[feld]) for feld in schluessel)
        if ziel not in steht_da or not _angekommen(steht_da[ziel],
                                                    satz["wert"]):
            geblieben.append(satz)
    return geblieben


def _schreiben(cursor, sql: str, saetze, hinweise=None) -> tuple:
    """Fuehrt die Anweisung Satz fuer Satz aus - und zaehlt beides mit."""
    geschrieben, ohne_zeile = 0, []
    for nummer, satz in enumerate(saetze):
        if hinweise is not None and nummer < len(hinweise):
            cursor.hinweis = hinweise[nummer]
        cursor.execute(sql, satz)
        if cursor.rowcount:
            geschrieben += cursor.rowcount
        else:
            ohne_zeile.append(satz)
    return geschrieben, ohne_zeile


def trdf_anhang_zurueck_pruefen(satz: dict):
    """Beim Zurueckspielen darf MW_OLD leer sein - vorher war es das auch."""
    fehlend = [feld for feld in TRDF_ANHANG_ZURUECK_FELDER
               if feld != "alt" and satz.get(feld) is None]
    if fehlend:
        raise ValueError("Unvollstaendiger Satz fuer den Teilprobenanhang: "
                         + ", ".join(fehlend))
    if "alt" not in satz:
        raise ValueError("Ohne MW_OLD ist es kein Zurueckspielen.")


def trdf_exportieren(zugang: Zugang, saetze: list[dict], hinweise=None,
                     anhang=None, anhang_hinweise=None,
                     zurueck: bool = False, leeren: bool = False) -> dict:
    """Schreibt die korrigierten Werte - alles oder nichts.

    Zwei Stellen, eine Transaktion: die Ergebniszeile und der
    Teilprobenanhang, an dem derselbe Rohwert ein zweites Mal haengt.
    Nur eine der beiden zu schreiben waere schlimmer als keine - dann
    stuenden im LIMS zwei Staende nebeneinander, und der Rechenweg des
    LIMS nutzt den, den man nicht sieht.

    Zurueck kommt, was geschah: `geschrieben` sind die getroffenen
    Ergebniszeilen, `ohne_zeile` die Saetze, zu denen es im LIMS keine
    gibt (sie werden gemeldet und nicht angelegt), und dasselbe fuer den
    Anhang unter `anhang_geschrieben` und `anhang_ohne_zeile`.

    `leeren` erlaubt es, einen Wert zu loeschen - die TRDF-Pruefung
    stellt damit die Staende her, die eine Variante verlangt. Ohne die
    Erlaubnis bleibt ein leerer Wert, was er war: ein Fehler.

    `zurueck` sagt, in welche Richtung geschrieben wird. Zurueck gilt
    der gesicherte Stand, und der darf leere Spalten haben - beim
    Korrigieren waere eine leere Spalte eine geloeschte Zahl.

    Nach dem Festschreiben wird nachgelesen: unter
    `nicht_uebernommen` stehen die Saetze, bei denen jetzt immer noch
    der alte Wert in der Datenbank steht. Getroffen und trotzdem nicht
    geaendert - das kann ein Ausloeser gewesen sein, ein Recht, das
    fehlt, oder eine Sicht statt einer Tabelle. Von aussen sieht es
    aus wie ein gelungener Export, und genau deshalb wird gefragt.
    """
    anhang = list(anhang or [])
    zurueck = zurueck or (bool(anhang) and "alt" in anhang[0])
    for satz in saetze:
        if zurueck:
            trdf_zurueck_pruefen(satz)
        else:
            trdf_satz_pruefen(satz, leeren)
    for satz in anhang:
        if zurueck:
            trdf_anhang_zurueck_pruefen(satz)
        else:
            trdf_anhang_satz_pruefen(satz, leeren)
    if not saetze and not anhang:
        return {"geschrieben": 0, "ohne_zeile": [], "versucht": 0,
                "anhang_geschrieben": 0, "anhang_ohne_zeile": [],
                "nicht_uebernommen": [], "anhang_nicht_uebernommen": []}
    verbindung = zugang.verbinden()
    try:
        with verbindung.cursor() as cursor:
            geschrieben, ohne_zeile = _schreiben(
                cursor,
                trdf_zurueck_sql() if zurueck else trdf_export_sql(),
                saetze, hinweise)
            am_anhang, anhang_ohne = _schreiben(
                cursor,
                trdf_anhang_zurueck_sql() if zurueck else trdf_anhang_sql(),
                anhang, anhang_hinweise)
        verbindung.commit()
        # Erst nach dem Festschreiben: vorher saehe die eigene
        # Transaktion ohnehin ihre eigenen Aenderungen.
        with verbindung.cursor() as cursor:
            geblieben = _nachpruefen(
                cursor, trdf_nachlesen_sql,
                [satz for satz in saetze if satz not in ohne_zeile],
                ERGEBNIS_SCHLUESSEL, gefragt=ERGEBNIS_SCHLUESSEL[:-1])
            anhang_geblieben = _nachpruefen(
                cursor, trdf_anhang_nachlesen_sql,
                [satz for satz in anhang if satz not in anhang_ohne],
                ANHANG_SCHLUESSEL)
    except Exception:
        verbindung.rollback()
        raise
    finally:
        verbindung.close()
    return {"geschrieben": geschrieben, "ohne_zeile": ohne_zeile,
            "versucht": len(saetze), "anhang_geschrieben": am_anhang,
            "anhang_ohne_zeile": anhang_ohne,
            "nicht_uebernommen": geblieben,
            "anhang_nicht_uebernommen": anhang_geblieben}
