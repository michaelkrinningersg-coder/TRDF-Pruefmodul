"""Schneller End-to-End-Test der Datenschicht (headless, keine GUI, keine DB).

Geprueft wird, was schiefgehen darf, bevor eine Zeile geschrieben wird:

  * Bezeichner kommen nur durch, wenn es sie in der Tabelle wirklich gibt.
  * Werte werden typrichtig gebunden und landen nie im Anweisungstext.
  * Ohne Bedingung wird abgebrochen - ein UPDATE ohne WHERE traefe alles.
  * Eine offene Aenderung laesst sich genau einmal abschliessen.

Aufruf:  python test_lims_db.py
"""

from __future__ import annotations

import datetime
import os
import pathlib
import re
import sys
import tempfile

import oracledb

import lims_db
from lims_db import als_csv, als_text

# Die Platzhalter einer Anweisung (:name) - zum Abgleich mit den
# Bindungen, die der Cursor bekommt.
PLATZHALTER = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


class Spalte:
    """Ersatz fuer oracledb.FetchInfo, so viel wie der Code davon braucht."""

    def __init__(self, name: str, typ):
        self.name = name
        self.type_code = typ


class Cursor:
    """Ersatz-Cursor, der nur die Spaltenliste einer gedachten Tabelle liefert."""

    def __init__(self, spalten: list[Spalte], zeilen: list[tuple] | None = None):
        self.description = spalten
        self.zeilen = zeilen or []
        self.ausgefuehrt: list[str] = []
        self.bindungen: list = []

    def execute(self, sql, *args, **kwargs):
        bindungen = args[0] if args else kwargs
        # Oracle nimmt keinen Bindungsnamen an, den die Anweisung nicht
        # kennt - es bricht mit DPY-4008 ab. Der Ersatz-Cursor tut das
        # auch, sonst faellt so ein Fehler erst beim Anwender auf: genau
        # so ging das Umsetzen mit ":neu_geme" schief, waehrend hier alles
        # gruen war.
        if isinstance(bindungen, dict):
            im_text = set(PLATZHALTER.findall(sql))
            zuviel = sorted(set(bindungen) - im_text)
            if zuviel:
                raise oracledb.DatabaseError(
                    f"DPY-4008: no bind placeholder named \":{zuviel[0]}\" "
                    f"was found in the SQL text")
            fehlt = sorted(im_text - set(bindungen))
            if fehlt:
                raise oracledb.DatabaseError(
                    f"DPY-4010: the values or expressions for the bind "
                    f"placeholder \":{fehlt[0]}\" were not provided")
        self.ausgefuehrt.append(sql)
        self.bindungen.append(bindungen)

    def fetchall(self):
        return self.zeilen

    def fetchone(self):
        return self.zeilen[0] if self.zeilen else None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Verbindung:
    """Ersatz-Verbindung, die nur mitschreibt, was mit ihr geschehen ist."""

    def __init__(self, spalten: list[Spalte], zeilen: list[tuple] | None = None):
        self.spalten = spalten
        self.zeilen = zeilen or []
        self.commits = 0
        self.rollbacks = 0
        self.geschlossen = False
        self.letzter_cursor = None

    def cursor(self):
        self.letzter_cursor = Cursor(self.spalten, self.zeilen)
        return self.letzter_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.geschlossen = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False


class Zugang:
    """Ersatz-Zugang, der immer dieselbe Ersatz-Verbindung herausgibt.

    Eingepackt wird sie wie im Betrieb: `verbinden` geht durch denselben
    Umschlag, der jede Aenderung ins Protokoll schreibt. Ohne Protokoll
    kommt die Verbindung unveraendert heraus - so pruefen die uebrigen
    Pruefungen weiter den blanken Weg.
    """

    def __init__(self, verbindung, protokollbuch=None):
        self.verbindung = verbindung
        self.modus = "Thin Mode"
        self.benutzer = "pruefer"
        self.alias = "LIMS"
        self.protokoll = protokollbuch

    def verbinden(self):
        return lims_db._mit_protokoll(self.verbindung, self.protokoll)


PROBEN = [
    Spalte("PROBEN_ID", oracledb.DB_TYPE_NUMBER),
    Spalte("SERIE", oracledb.DB_TYPE_VARCHAR),
    Spalte("PSTA_ID", oracledb.DB_TYPE_NUMBER),
    Spalte("BEMERKUNG", oracledb.DB_TYPE_VARCHAR),
]

# --- Vorrat an Verbindungen -----------------------------------------------

class VorratsAttrappe:
    """So viel von einem Verbindungsvorrat, wie Zugang davon braucht."""

    def __init__(self):
        self.ausgegeben = 0
        self.geschlossen = False

    def acquire(self):
        self.ausgegeben += 1
        return Verbindung([], [])

    def close(self, force=False):
        self.geschlossen = True


def mit_vorrat(bauen, verbinden=None, an=True):
    """Setzt create_pool, connect und den Schalter fuer eine Pruefung."""
    echt = (oracledb.create_pool, oracledb.connect,
            os.environ.get(lims_db.Zugang.VORRAT_SCHALTER))
    oracledb.create_pool = bauen
    if verbinden is not None:
        oracledb.connect = verbinden
    if an:
        os.environ[lims_db.Zugang.VORRAT_SCHALTER] = "1"
    else:
        os.environ.pop(lims_db.Zugang.VORRAT_SCHALTER, None)
    return echt


def zurueck(echt):
    oracledb.create_pool, oracledb.connect = echt[:2]
    if echt[2] is None:
        os.environ.pop(lims_db.Zugang.VORRAT_SCHALTER, None)
    else:
        os.environ[lims_db.Zugang.VORRAT_SCHALTER] = echt[2]


def test_ohne_schalter_gibt_es_keinen_vorrat() -> None:
    """Von Haus aus wird wie bisher je Abfrage verbunden: auf Oracle 11.2
    liess sich nicht pruefen, ob ein Sitzungsvorrat traegt, und ein leerer
    Startbildschirm ist teurer als die Sekunden, die er spart."""
    verbunden = []

    def bauen(**rest):
        raise AssertionError("Ohne Schalter darf kein Vorrat entstehen")

    def verbinden(**rest):
        verbunden.append(rest)
        return Verbindung([], [])

    echt = mit_vorrat(bauen, verbinden, an=False)
    try:
        zugang = lims_db.Zugang("pruefer", "geheim", "LIMS")
        zugang.verbinden()
        zugang.verbinden()
        assert len(verbunden) == 2
        assert "ohne Vorrat" in zugang.verbindungsart()
    finally:
        zurueck(echt)


def test_ein_kaputter_vorrat_haelt_das_programm_nicht_auf() -> None:
    """Auch ein Fehler, den der Treiber nicht als Datenbankfehler meldet,
    darf den Startbildschirm nicht leer lassen."""
    verbunden = []

    def bauen(**rest):
        raise TypeError("create_pool() got an unexpected keyword argument")

    def verbinden(**rest):
        verbunden.append(rest)
        return Verbindung([], [])

    echt = mit_vorrat(bauen, verbinden)
    try:
        zugang = lims_db.Zugang("pruefer", "geheim", "LIMS")
        zugang.verbinden()
        zugang.verbinden()
        assert len(verbunden) == 3      # einmal zum Klaeren, dann je Abfrage
        assert "unexpected keyword" in zugang.verbindungsart()
    finally:
        zurueck(echt)


def test_der_vorrat_wird_einmal_gebaut_und_dann_nur_geholt() -> None:
    """Jede Abfrage baute sonst ihre eigene Verbindung auf - mit
    Anmeldung, und das ist eine Rundreise mehr als die Abfrage selbst."""
    vorrat = VorratsAttrappe()
    gebaut, geprueft = [], []

    def bauen(**rest):
        gebaut.append(rest)
        return vorrat

    def verbinden(**rest):
        geprueft.append(rest)
        return Verbindung([], [])

    echt = mit_vorrat(bauen, verbinden)
    try:
        zugang = lims_db.Zugang("pruefer", "geheim", "LIMS")
        for _ in range(5):
            zugang.verbinden()
        assert len(gebaut) == 1, gebaut
        # Einmal wird einzeln verbunden, um den Modus zu klaeren.
        assert len(geprueft) == 1
        assert vorrat.ausgegeben == 5
        assert gebaut[0]["user"] == "pruefer"
        assert gebaut[0]["min"] == 1 and gebaut[0]["max"] >= 2
        zugang.schliessen()
        assert vorrat.geschlossen
        # Nach dem Schliessen wird wieder einer gebaut.
        zugang.verbinden()
        assert len(gebaut) == 2
    finally:
        zurueck(echt)


def test_ohne_vorrat_wird_wie_bisher_verbunden() -> None:
    """Laesst sich kein Vorrat anlegen, muss es trotzdem laufen."""
    verbunden = []

    def bauen(**rest):
        raise oracledb.DatabaseError("ORA-12516: kein Prozess frei")

    def verbinden(**rest):
        verbunden.append(rest)
        return Verbindung([], [])

    echt = mit_vorrat(bauen, verbinden)
    try:
        zugang = lims_db.Zugang("pruefer", "geheim", "LIMS")
        zugang.verbinden()
        zugang.verbinden()
        # Der Versuch mit dem Vorrat klaert erst den Modus (eine
        # Verbindung), danach je Abfrage eine.
        assert len(verbunden) == 3
    finally:
        zurueck(echt)


def test_falsche_zugangsdaten_werden_nicht_zweimal_versucht() -> None:
    """Ein zweiter Versuch brachte nur eine zweite Fehlmeldung - und
    naehme dem Konto einen Versuch bis zur Sperrung."""
    def bauen(**rest):
        raise oracledb.DatabaseError("ORA-01017: invalid username/password")

    def verbinden(**rest):
        raise oracledb.DatabaseError("ORA-01017: invalid username/password")

    echt = mit_vorrat(bauen, verbinden)
    try:
        zugang = lims_db.Zugang("pruefer", "falsch", "LIMS")
        try:
            zugang.verbinden()
        except oracledb.DatabaseError as fehler:
            assert "ORA-01017" in str(fehler)
        else:
            raise AssertionError("Der Fehler haette durchschlagen muessen.")
    finally:
        zurueck(echt)


# --- Export ins LIMS ------------------------------------------------------

class ExportCursor(Cursor):
    """Zaehlt die geschriebenen Zeilen und kann auf Wunsch scheitern.

    `buendel` sagt, ob die Datenbank ein Buendel annimmt; sonst muss der
    Export Satz fuer Satz schreiben.
    """

    def __init__(self, rowcount=1, fehler=None, buendel=True, belegt=()):
        super().__init__([], [])
        self.je_zeile = rowcount        # was ein Satz trifft
        self.rowcount = rowcount
        self.fehler = fehler
        self.buendel = buendel
        self.saetze = []            # was wirklich geschrieben wurde
        self.rundreisen = 0
        # Was die Datenbank auf die Frage nach belegten MW_ROH antwortet:
        # (prob_id, pm_id, pm_ver, um_id, gegr_id, mw_roh).
        self.belegt = list(belegt)

    def execute(self, sql, *args, **kwargs):
        super().execute(sql, *args, **kwargs)
        if sql.lstrip().upper().startswith("SELECT"):
            # Eine Abfrage ist kein geschriebener Satz - sie darf weder
            # mitzaehlen noch den gestellten Fehler ausloesen.
            self.zeilen = self.belegt
            return
        self.rowcount = self.je_zeile
        self.rundreisen += 1
        self.saetze.append(args[0] if args else kwargs)
        if self.fehler is not None and len(self.saetze) >= self.fehler:
            raise oracledb.DatabaseError("ORA-00001")

    def executemany(self, sql, saetze, **kwargs):
        if not self.buendel:
            raise oracledb.NotSupportedError("DPI-1050: not supported")
        for satz in saetze:
            Cursor.execute(self, sql, satz)
        self.rundreisen += 1
        self.saetze.extend(saetze)
        if self.fehler is not None and len(self.saetze) >= self.fehler:
            raise oracledb.DatabaseError("ORA-00001")
        self.rowcount = self.je_zeile * len(saetze)


class ExportVerbindung(Verbindung):
    def __init__(self, rowcount=1, fehler=None, buendel=True, belegt=()):
        super().__init__([], [])
        self._rowcount = rowcount
        self._fehler = fehler
        self._buendel = buendel
        self._belegt = list(belegt)
        self.cursoren = []

    def cursor(self):
        self.letzter_cursor = ExportCursor(self._rowcount, self._fehler,
                                           self._buendel, self._belegt)
        self.cursoren.append(self.letzter_cursor)
        return self.letzter_cursor


def exportsatz(prob_id=11) -> dict:
    return {"prob_id": prob_id, "pm_id": 100, "pm_ver": 2, "um_id": 7,
            "gegr_id": 30, "mw_roh": "1,0", "mw_org": "1,0", "mw_n": 1,
            "mw": "3,0", "anwender": "pruefer", "v_faktor": 4,
            "fc7": None, "fc8": "OK", "fc9": "LabControl",
            "datum_zeit": datetime.datetime(2026, 9, 2),
            "psta_id": lims_db.PSTA_GESENDET,
            "korrektur_flag": lims_db.KORREKTUR_FLAG}


def belegt_zeile(prob_id, wert="0,5") -> tuple:
    return (prob_id, 100, 2, 7, 30, wert)


def test_csv_fuer_excel() -> None:
    daten = als_csv(["SERIE", "WERT"], [("2024B017", 1.5), ("2024B018", None)])
    assert daten.startswith(b"\xef\xbb\xbf")          # BOM, damit Excel passt
    text = daten.decode("utf-8-sig")
    assert text.splitlines()[0] == "SERIE;WERT"
    assert "1,5" in text                              # Dezimalkomma
    assert text.splitlines()[2] == "2024B018;"        # None wird leer


def test_als_text() -> None:
    import datetime as dt
    assert als_text(None) == ""
    assert als_text(dt.date(2024, 3, 7)) == "07.03.2024"
    assert als_text(dt.datetime(2024, 3, 7, 8, 5, 9)) == "07.03.2024 08:05:09"
    assert als_text(b"abc") == "<3 Byte>"


class ZweiAntworten(Verbindung):
    """Liefert der ersten Abfrage die eine, jeder weiteren die andere Liste.

    Damit laesst sich pruefen, was geschieht, wenn der Normalweg leer
    bleibt - bei einer alten Serie steht in SERIEN_MW_ANHANG nichts mehr.
    """

    def __init__(self, spalten, erste, weitere):
        super().__init__(spalten, erste)
        self.weitere = weitere
        self.aufrufe = 0
        self.abfragen = []

    def cursor(self):
        self.aufrufe += 1
        self.letzter_cursor = Cursor(
            self.spalten, self.zeilen if self.aufrufe == 1 else self.weitere)
        self.abfragen.append(self.letzter_cursor)
        return self.letzter_cursor


def test_alte_serie_findet_ihre_methode_in_ergebnissen() -> None:
    verbindung = ZweiAntworten(PROBEN, [], [(251, "ICP")])
    assert lims_db.methoden_fuer_serie(None, "2023W001",
                                       verbindung=verbindung) == [(251, "ICP")]
    assert "teilproben" in verbindung.abfragen[0].ausgefuehrt[0].lower()
    assert "ergebnisse" in verbindung.abfragen[1].ausgefuehrt[0].lower()


def test_die_zweite_abfrage_bleibt_aus_wenn_die_erste_traegt() -> None:
    """Sonst liefe sie bei jeder Auswahl mit - fuer nichts."""
    verbindung = ZweiAntworten(PROBEN, [(251, "ICP")], [(9, "falsch")])
    assert lims_db.methoden_fuer_serie(None, "2026P007",
                                       verbindung=verbindung) == [(251, "ICP")]
    assert verbindung.aufrufe == 1


class NachReihe(Verbindung):
    """Liefert je Abfrage die naechste Liste - fuer die Ersatzwege.

    `geraete_fuer` hat drei Wege und geht sie der Reihe nach, jeden
    spaeteren nur, wenn der vorige leer bleibt. Geprueft werden soll
    jeder einzeln.
    """

    def __init__(self, spalten, antworten):
        super().__init__(spalten, antworten[0] if antworten else [])
        self.antworten = list(antworten)
        self.aufrufe = 0
        self.abfragen = []

    def cursor(self):
        stelle = self.aufrufe
        self.aufrufe += 1
        zeilen = (self.antworten[stelle] if stelle < len(self.antworten)
                  else [])
        self.letzter_cursor = Cursor(self.spalten, zeilen)
        self.abfragen.append(self.letzter_cursor)
        return self.letzter_cursor


def test_methoden_binden_die_serie() -> None:
    verbindung = Verbindung(PROBEN, [(7, "TOC"), (9, "pH")])
    eintraege = lims_db.methoden_fuer_serie(None, "2024B017", verbindung=verbindung)
    assert eintraege == [(7, "TOC"), (9, "pH")]
    cursor = verbindung.letzter_cursor
    assert cursor.bindungen[0] == {"serie": "2024B017"}      # als Bind-Variable
    assert "2024B017" not in cursor.ausgefuehrt[0]           # nicht im Text
    assert "LEFT JOIN untersuchungsmethode" in cursor.ausgefuehrt[0]


def test_die_methode_kommt_notfalls_aus_der_zuordnung() -> None:
    """Eine frisch angesetzte Serie hat weder Teilproben noch
    Ergebniszeilen - die Methode steht dann nur in SERIEN_MW_ANHANG."""
    verbindung = Verbindung(PROBEN, [])          # beide ersten Abfragen leer
    lims_db.methoden_fuer_serie(None, "2026P0071", verbindung=verbindung)
    # Je Abfrage ein eigener Cursor - der letzte ist der dritte Weg.
    assert "FROM serien_mw_anhang" in verbindung.letzter_cursor.ausgefuehrt[-1]


def test_die_zuordnung_wird_nur_im_notfall_gefragt() -> None:
    """Steht die Methode schon in TEILPROBEN, bleibt es bei einer
    Abfrage - drei Wege zu gehen, wo einer reicht, waere Wartezeit."""
    verbindung = Verbindung(PROBEN, [(7, "TOC")])
    lims_db.methoden_fuer_serie(None, "2026P0071", verbindung=verbindung)
    assert "FROM teilproben" in verbindung.letzter_cursor.ausgefuehrt[-1]


# --- Die TRDF-Pruefung ----------------------------------------------------
#
# Hier wird die Rechnung des LIMS nachvollzogen. Geprueft wird vor allem
# die Verknuepfung: greift eine Abfrage daneben, rechnet die Pruefung mit
# fremden Zahlen und meldet Abweichungen, die keine sind.

def trdf_sql(name, *rest, **wo):
    verbindung = Verbindung(PROBEN, [])
    getattr(lims_db, name)(None, *rest, verbindung=verbindung, **wo)
    return (verbindung.letzter_cursor.ausgefuehrt[-1],
            verbindung.letzter_cursor.bindungen[-1])


def test_die_methoden_kommen_ueber_das_kuerzel():
    text, bindungen = trdf_sql("trdf_methoden")
    assert "FROM untersuchungsmethode" in text
    assert "UPPER(kuerzel) LIKE :marke" in text
    assert bindungen["marke"] == "%TRDF%"


def test_die_serien_kommen_aus_dem_fahrplan():
    """S_FAHRPLAN sagt, was ansteht - aber nicht, mit welcher Methode.
    Die steht in TEILPROBEN, und danach wird je Serie gefragt statt die
    Ergebnistabelle nach allen Serien zu durchsuchen."""
    text, bindungen = trdf_sql("trdf_serien", [261, 94])
    assert "FROM s_fahrplan f" in text
    assert "EXISTS (SELECT 1 FROM teilproben t" in text
    assert "t.um_id IN (:um0, :um1)" in text
    assert bindungen["um0"] == 261 and bindungen["um1"] == 94
    assert "ergebnisse" not in text.lower()


def test_ohne_methode_wird_gar_nicht_gefragt():
    verbindung = Verbindung(PROBEN, [])
    assert lims_db.trdf_serien(None, [], verbindung=verbindung) == []
    assert verbindung.letzter_cursor is None


def test_die_rohwerte_bringen_ihr_formelkuerzel_mit():
    """Die eingefuegte Spalte traegt den Namen, gerechnet wird mit dem
    Kuerzel - beides steht im LIMS, nichts im Programm."""
    text, bindungen = trdf_sql("trdf_rohwertparameter", 261)
    assert "FROM um_rohwerte u" in text
    assert "JOIN rohwertparameter r" in text
    # Das Kuerzel an der Methode sticht das am Parameter.
    assert "NVL(u.formelkuerzel, r.formelkuerzel)" in text
    assert bindungen["um_id"] == 261


def test_die_pruefmethoden_nehmen_den_stand_der_ergebnisse():
    """Zu einer Pruefmethode gibt es mehrere Staende; gerechnet hat das
    LIMS mit dem, der an der Ergebniszeile haengt."""
    text, bindungen = trdf_sql("trdf_pruefmethoden", "2026B051", 261)
    assert "(p.id, p.version) IN (SELECT DISTINCT e.pm_id, e.pm_ver" in text
    assert "p.formel" in text and "p.formelkuerzel" in text
    assert bindungen["serie"] == "2026B051" and bindungen["um_id"] == 261


def test_die_ergebnisse_lassen_die_wiederholungen_draussen():
    """Geprueft wird die Erstmessung - die wollen wir betrachten."""
    text, _ = trdf_sql("trdf_ergebnisse", "2026B051", 261)
    assert "NVL(p.wdh_um, 1) = 1" in text and "NVL(p.wdh_me, 1) = 1" in text
    assert "e.mw_roh" in text and "e.mw" in text


# ------------------------------------------------- Einzelne Proben holen

def test_die_proben_kommen_ueber_probe_nr_und_prob_id():
    """Der ganze Weg: PROBEN.PROBE_NR -> PROBEN.ID = ERGEBNISSE.PROB_ID,
    dazu die Methode - und dann die Parameter dieser Zeilen."""
    text, bindungen = trdf_sql("trdf_ergebnisse", None, 261,
                               proben=["26B0001", "26B0002"])
    text = " ".join(text.split())
    # Direkt an p.probe_nr, denn diese Abfrage verbindet PROBEN - und
    # ohne UPPER auf der Spalte, damit Oracle den Index benutzen kann.
    assert "p.probe_nr IN (:pnr0, :pnr1)" in text
    assert "UPPER(probe_nr)" not in text
    assert "e.um_id = :um_id" in text
    assert bindungen["pnr0"] == "26B0001" and bindungen["pnr1"] == "26B0002"
    assert "serie" not in bindungen           # der Fahrplan bleibt aussen vor
    # Und die Serie kommt mit: die Sicherung braucht einen Namen.
    assert "e.serie" in text
    assert "serie" in lims_db.TRDF_ERGEBNIS_FELDER
    # Die Probenart auch: sie sagt, ob unter dieser Methode Boden
    # oder Humus gebucht ist (1 Boden, 2 Pflanze, 3 Wasser, 4 Humus).
    # Bisher stand sie im Kopf des Reiters aus dem Seriennamen - und
    # bei einzelnen Proben gibt es keinen.
    assert "e.part_id" in text
    assert lims_db.TRDF_ERGEBNIS_FELDER[-1] == "part_id"


def test_der_anhang_folgt_denselben_proben():
    """Die Kombination PROB_ID/UM_ID/ROHW_ID - ohne Umweg ueber die Serie."""
    text, bindungen = trdf_sql("trdf_rohwerte_anhang", None, 261,
                               proben=["26B0001"])
    text = " ".join(text.split())
    # Hier ohne Verbindung zu PROBEN - also die Unterabfrage, aber
    # auch die ohne UPPER auf der Spalte.
    assert "a.prob_id IN (SELECT id FROM proben WHERE probe_nr IN" in text
    assert "UPPER(probe_nr)" not in text
    assert "t.um_id = :um_id" in text
    assert "t.serie" not in text
    assert bindungen["pnr0"] == "26B0001"


def test_auch_wgh_aufschluss_und_methoden_gehen_ueber_die_proben():
    for name, weitere in (("trdf_wiederfindung", ()),
                          ("trdf_aufschluss", ()),
                          ("trdf_pruefmethoden", (261,))):
        text, bindungen = trdf_sql(name, None, *weitere,
                                   proben=["26B0001"])
        text = " ".join(text.split())
        assert ("e.prob_id IN (SELECT id FROM proben WHERE probe_nr IN"
                in text), name
        assert "UPPER(probe_nr)" not in text, name
        assert "serie" not in bindungen, name


def test_mit_serie_bleibt_alles_wie_bisher():
    text, bindungen = trdf_sql("trdf_ergebnisse", "2026B051", 261)
    text = " ".join(text.split())
    assert "e.serie = :serie" in text and "proben" not in text.lower().split(
        "from")[1].split("where")[0].replace("join proben p", "")
    assert bindungen["serie"] == "2026B051"


def test_kleingeschriebenes_wird_gebunden_und_nicht_gerechnet():
    """Gebucht ist die grosse Form ("2026W00500"). Wer klein tippt,
    soll trotzdem etwas finden - aber nicht auf Kosten des Index:
    gebunden werden beide Formen, und die Spalte bleibt unberuehrt.

    `UPPER(probe_nr)` auf der Spalte war der Grund, warum ein
    Profilabruf die ganze Tabelle PROBEN durchging."""
    text, bindungen = trdf_sql("trdf_ergebnisse", None, 261,
                               proben=["2026w00500", "2026W00501"])
    text = " ".join(text.split())
    # Die kleine Form bringt zwei Bindungen, die grosse eine.
    assert bindungen["pnr0"] == "2026w00500"
    assert bindungen["pnrg0"] == "2026W00500"
    assert bindungen["pnr1"] == "2026W00501"
    assert "pnrg1" not in bindungen
    assert "p.probe_nr IN (:pnr0, :pnrg0, :pnr1)" in text
    assert "UPPER(probe_nr)" not in text


def test_mehr_als_fuenfhundert_proben_werden_abgeschnitten():
    """Wer mehr hat, hat eine Serie - und Oracle hat eine Grenze."""
    viele = [f"26B{nummer:04d}" for nummer in range(600)]
    _, bindungen = trdf_sql("trdf_ergebnisse", None, 261, proben=viele)
    nummern = [name for name in bindungen if name.startswith("pnr")]
    assert len(nummern) == lims_db.PROBEN_HOECHSTENS == 500


def test_der_wiederfindungsgrad_haengt_an_seiner_eigenen_methode():
    """Nicht an der TRDF-Methode: die Formeln des LIMS holen ihn ueber
    die PM_ID, und genau so wird er hier geholt."""
    text, bindungen = trdf_sql("trdf_wiederfindung", "2026B051")
    assert "e.pm_id = :pm_id" in text
    assert bindungen["pm_id"] == 701 == lims_db.WGH_PM_ID
    assert "um_id" not in bindungen


def test_der_aufschluss_nimmt_den_gehalt():
    text, bindungen = trdf_sql("trdf_aufschluss", "2026B051")
    assert "e.mw" in text and "e.mw_roh" not in text
    assert bindungen["marke"] == "%ATNULL%"
    assert bindungen["cges"] == 31 and bindungen["co3"] == 33


def test_der_nachtrag_fragt_ueber_die_probennummer():
    """Dieselbe PROBE_NR steht im LIMS mehrfach - unter einer anderen
    PROB_ID und oft in einer anderen Serie. Gefragt wird deshalb ueber
    die Nummer; angesetzt aber an der PROB_ID, die der Aufrufer schon
    hat - und Spalte gegen Spalte, ohne UPPER, sonst geht Oracle die
    ganze Tabelle PROBEN durch."""
    text, bindungen = trdf_sql("trdf_aufschluss_nachtrag", [5, 11])
    text = " ".join(text.split())
    assert "p.probe_nr IN (SELECT q.probe_nr FROM proben q" in text
    assert "q.id IN (:pid0, :pid1)" in text
    assert "UPPER(p.probe_nr)" not in text
    assert "serie" not in bindungen
    # Die Serie kommt als Spalte mit: ohne sie ist die Zahl nicht
    # nachzusehen.
    assert "e.serie" in text and "p.probe_nr" in text
    assert bindungen["pid0"] == 5 and bindungen["pid1"] == 11
    assert bindungen["marke"] == "%ATNULL%"
    # Genommen wird der Gehalt, und nur wo einer steht.
    assert "e.mw IS NOT NULL" in text
    assert "e.mw_roh" not in text
    # Wiederholungen bleiben draussen - geprueft wird die Erstmessung.
    assert "NVL(p.wdh_um, 1) = 1" in text
    # Die hoechste PROB_ID zuerst: haben mehrere Anlagen einen
    # Aufschluss, gilt die zuletzt angelegte.
    assert "ORDER BY p.probe_nr, e.para_id, e.prob_id DESC" in text


def test_der_nachtrag_ohne_probe_holt_nichts():
    text, _ = trdf_sql("trdf_aufschluss_nachtrag", [None])
    assert "1 = 0" in " ".join(text.split())


def test_co3_kommt_nur_aus_seiner_eigenen_methode():
    """ATNULLCO3 steckt in ATNULL - unterschieden wird deshalb beim
    Lesen und nicht in der Anweisung."""
    assert lims_db.aufschluss_passt({"para_id": 33, "kuerzel": "ATNULLCO3"})
    assert not lims_db.aufschluss_passt({"para_id": 33, "kuerzel": "ATNULL"})
    assert lims_db.aufschluss_passt({"para_id": 31, "kuerzel": "ATNULL"})
    assert not lims_db.aufschluss_passt({"para_id": 31, "kuerzel": "ATNULLCO3"})


# --------------------------------------------------------------------------
# Dateien in den Stationsordner uebernehmen
# --------------------------------------------------------------------------

def _ablage(unterordner="ordner"):
    basis = tempfile.mkdtemp()
    ordner = os.path.join(basis, unterordner)
    os.makedirs(ordner)
    return basis, ordner


def geraetebasis(basis: str, *namen) -> str:
    """Legt die Geraeteordner an, wo sie hingehoeren: unter "Geraete"."""
    unten = lims_db.geraetebasis(basis)
    for name in namen:
        os.makedirs(os.path.join(unten, name))
    return unten


def katalog_sql(**rest) -> str:
    verbindung = Verbindung([], [])
    lims_db.standardkatalog(Zugang(verbindung), **rest)
    return verbindung.letzter_cursor.ausgefuehrt[-1]


def liste_sql(**rest) -> str:
    verbindung = Verbindung([], [])
    lims_db.standardliste(Zugang(verbindung), **rest)
    return verbindung.letzter_cursor.ausgefuehrt[-1]


def messungs_sql(**rest):
    verbindung = Verbindung([], [])
    rest.setdefault("para_id", 3)
    lims_db.standardmessungen(Zugang(verbindung), 21, 7, **rest)
    return (verbindung.letzter_cursor.ausgefuehrt[-1],
            verbindung.letzter_cursor.bindungen[-1])


def test_die_ora_nummer_wird_gelesen():
    assert lims_db.fehlernummer(
        Exception("ORA-00942: Tabelle oder View existiert nicht")) == 942
    assert lims_db.fehlernummer(Exception("nichts dergleichen")) is None


# --- Geraetewechsel -------------------------------------------------------
#
# Anders als der Export aendert das Umsetzen Schluesselspalten. Geprueft
# wird deshalb vor allem, was *nicht* passieren darf: mehr treffen als den
# Lauf, eine vorhandene Zielzeile ueberrennen, halb geschrieben liegen
# bleiben.

# Die Spalten von SERIEN_MW_ANHANG, wie das LIMS sie fuehrt - ohne ID.
SERIENZEILE = [
    Spalte("SERIE", oracledb.DB_TYPE_VARCHAR),
    Spalte("STAT_ID", oracledb.DB_TYPE_NUMBER),
    Spalte("LNR", oracledb.DB_TYPE_NUMBER),
    Spalte("UM_ID", oracledb.DB_TYPE_NUMBER),
    Spalte("FLAG", oracledb.DB_TYPE_VARCHAR),
    Spalte("SGRU_ID", oracledb.DB_TYPE_NUMBER),
    Spalte("LAUF", oracledb.DB_TYPE_VARCHAR),
    Spalte("BEARBEITER", oracledb.DB_TYPE_VARCHAR),
]


class WechselCursor(Cursor):
    """Beantwortet die COUNT-Abfragen und schreibt mit, was ausgefuehrt wird."""

    def __init__(self, kollisionen=0, serienzeile=0, geblieben=0,
                 fehler=None, verwaist=1):
        super().__init__(SERIENZEILE, [])
        self.kollisionen = kollisionen
        self.serienzeile = serienzeile
        self.geblieben = geblieben
        # Wieviel nach dem Umsetzen an der alten Station noch haengt.
        # Eins als Vorgabe: der vorsichtige Fall, in dem nichts
        # abgeraeumt wird.
        self.verwaist = verwaist
        self.fehler = fehler
        self.rowcount = 3
        self._antwort = None

    def execute(self, sql, *args, **kwargs):
        super().execute(sql, *args, **kwargs)
        if self.fehler is not None and len(self.ausgefuehrt) >= self.fehler:
            raise oracledb.DatabaseError("ORA-00001")
        text = " ".join(sql.split()).lower()
        if text.startswith("select count(*) from ergebnisse alt"):
            self._antwort = (self.kollisionen,)
        elif "gegr_id = :stat_id" in text:
            # Die Frage nach der verwaisten Station - sie kennt weder
            # Parameter noch Pruefmethode.
            self._antwort = (self.verwaist,)
        elif text.startswith("select count(*) from ergebnisse where"):
            self._antwort = (self.geblieben,)
        elif text.startswith("select count(*) from serien_mw_anhang"):
            self._antwort = (self.serienzeile,)
        elif text.startswith("select * from"):
            self._antwort = None            # spalteninfo
        else:
            self._antwort = None

    def fetchone(self):
        return self._antwort


class WechselVerbindung(Verbindung):
    def __init__(self, **rest):
        super().__init__(SERIENZEILE, [])
        self._rest = rest

    def cursor(self):
        self.letzter_cursor = WechselCursor(**self._rest)
        return self.letzter_cursor


def vorhaben(**rest) -> dict:
    plan = {"serie": "2026W052", "um_id": 251, "alt_stat": 41, "neu_stat": 50,
            "serie_umstellen": True,
            "schritte": [{"para_id": 39, "part_id": 2, "parameter": "Chlorid",
                          "alt_pm_id": 39, "alt_pm_ver": 122,
                          "neu_pm_id": 39, "neu_pm_ver": 148,
                          "neu_geme": 148, "neu_vkd": 1}]}
    plan.update(rest)
    return plan


# --------------------------------------------------------------------------
# Die Serienzeile der alten Station
# --------------------------------------------------------------------------
#
# Beim Umsetzen einzelner Parameter bekommt die Serie eine zweite Zeile in
# SERIEN_MW_ANHANG. Wandert spaeter alles zurueck, bliebe die Zeile der
# Zwischenstation stehen - die Serie taucht dann an einem Geraet auf, an
# dem nichts mehr von ihr liegt. Entfernt wird sie genau dann, wenn dort
# keine Ergebniszeile dieser Serie mehr steht.

def _ausgefuehrt(cursor, anfang: str) -> list:
    """Die Anweisungen, die mit diesem Text beginnen."""
    return [nummer for nummer, sql in enumerate(cursor.ausgefuehrt)
            if " ".join(sql.split()).lower().startswith(anfang)]


def test_der_ersatzcursor_meldet_einen_falschen_bindungsnamen() -> None:
    """Die Gegenprobe zur Pruefung darueber: haette der Ersatz-Cursor das
    frueher gemeldet, waere der Fehler nie beim Anwender gelandet."""
    cursor = Cursor(PROBEN)
    try:
        cursor.execute("SELECT COUNT(*) FROM ergebnisse WHERE serie = :serie",
                       {"serie": "2026P007", "neu_geme": 148})
    except oracledb.DatabaseError as fehler:
        assert "neu_geme" in str(fehler)
    else:
        raise AssertionError("der ueberzaehlige Bindungsname blieb ungeruegt")


# --------------------------------------------------------------------------
# Geschrieben wird nur, wo nichts steht
# --------------------------------------------------------------------------
#
# Die Regel des ganzen Werkzeugs: LabControl fuellt leere Zeilen, es
# ueberschreibt keine. Wer das aendert, aendert die Zusage, dass ein
# gebuchtes Ergebnis im LIMS sicher ist - und damit die Frage, ob vor
# einem Export gesichert werden muss. Diese Pruefungen stehen deshalb
# hier und nicht als Kommentar in der Anweisung.

def _gesetzt(sql: str) -> str:
    """Der SET-Teil einer UPDATE-Anweisung, in einer Zeile."""
    ohne_where = sql.lower().split(" where ")[0]
    return " ".join(ohne_where.split()).split(" set ", 1)[1]


def test_jeder_satz_traegt_den_bearbeitungsstand() -> None:
    """Sonst nimmt Oracle den Satz nicht an - DPY-4010."""
    assert exportsatz()["psta_id"] == lims_db.PSTA_GESENDET
    assert exportsatz()["korrektur_flag"] == lims_db.KORREKTUR_FLAG


def test_ergebnisse_wird_nur_an_zwei_stellen_geschrieben() -> None:
    """Die TRDF-Korrektur und ihr Rueckweg - sonst niemand.

    Die Suche laeuft ueber den Quelltext: eine dritte Anweisung waere
    ein neuer Weg an dieser Zusage vorbei, und der soll auffallen,
    bevor er in einem Lauf auffaellt.

    Die Korrektur (`trdf_export_sql`) fasst fuenf benannte Spalten an
    und faehrt nur ueber eine bestaetigte Uebersicht und nach einer
    Sicherung. Ihr Rueckweg (`trdf_zurueck_sql`) muss eine eigene sein:
    die Korrektur schreibt MW_ROH und MW denselben Wert, das
    Zurueckspielen jedem seinen eigenen aus der Sicherung.
    """
    quelle = pathlib.Path(lims_db.__file__).parent
    gefunden = []
    for datei in sorted(quelle.glob("*.py")):
        if datei.name.startswith("test_"):
            continue
        text = " ".join(datei.read_text(encoding="utf-8").split()).lower()
        for anweisung in ("update ergebnisse", "delete from ergebnisse",
                          "insert into ergebnisse"):
            gefunden += [f"{datei.name}: {anweisung}"] * text.count(anweisung)
    assert gefunden == ["lims_db.py: update ergebnisse"] * 2, gefunden


def test_die_trdf_methodenliste_bietet_nichts_ausgeschlossenes_an() -> None:
    """Was nicht in der Liste steht, ist nicht zu waehlen - und damit
    fragt keine der Abfragen, die an einer UM_ID haengen, danach."""
    text, bindungen = trdf_sql("trdf_methoden")
    text = " ".join(text.split())
    assert "NOT IN" in text
    assert bindungen["ausum0"] == "TRDF3.1"


def test_die_liste_der_ausgeschlossenen_ist_eine_stelle() -> None:
    """Sie gilt fuer die TRDF-Pruefung, das Blockprofil, die Profile
    und den Profilvergleich. Die Qualitaetspruefung fragt weiter
    alles: dort ist eine alte Zeile eine Zeile des Hauses."""
    assert lims_db.AUSGESCHLOSSENE_METHODEN == ("TRDF3.1",)
    assert lims_db.ist_ausgeschlossen("TRDF3.1")
    assert lims_db.ist_ausgeschlossen(" trdf3.1 ")
    assert not lims_db.ist_ausgeschlossen("TRDF3.2")
    assert not lims_db.ist_ausgeschlossen("TRDF3.10")
    assert not lims_db.ist_ausgeschlossen("")
    assert not lims_db.ist_ausgeschlossen(None)


def test_csv_bloecke_trennt_die_tabellen() -> None:
    """Ein Reiter zeigt manchmal mehrere Tabellen untereinander - in der
    Datei muessen sie auseinanderzuhalten sein."""
    daten = lims_db.csv_bloecke([
        ("K26MS", ["Zeile", "Wert"], [[1, "10,0"]]),
        ("K27MS", ["Zeile", "Wert"], [[2, "11,0"], [3, "12,0"]]),
    ]).decode("utf-8-sig")
    zeilen = daten.split("\r\n")
    assert zeilen[0] == "K26MS"
    assert zeilen[1] == "Zeile;Wert"
    assert zeilen[2] == "1;10,0"
    assert zeilen[3:6] == ["", "", ""]          # drei Leerzeilen Abstand
    assert zeilen[6] == "K27MS"
    assert zeilen[7] == "Zeile;Wert"            # jeder Block mit Ueberschrift


def test_csv_ohne_titel_faengt_mit_der_ueberschrift_an() -> None:
    daten = lims_db.csv_bloecke([("", ["A", "B"], [[1, 2]])]).decode("utf-8-sig")
    assert daten.split("\r\n")[0] == "A;B"


def test_csv_bloecke_sind_leer_wenn_nichts_da_ist() -> None:
    assert lims_db.csv_bloecke([]) == lims_db.csv_bytes([])


# --------------------------------------------------------------------------
# Der Rueckweg der TRDF-Pruefung - der einzige Weg, der ueberschreibt
# --------------------------------------------------------------------------

def test_der_trdf_rueckweg_fasst_nur_fuenf_spalten_an() -> None:
    """Ueberschreiben darf er, aber nur, was benannt ist.

    Der gewoehnliche Export laesst jede Zahl durch NVL stehen. Dieser
    Weg tut das Gegenteil - und genau deshalb muss hier stehen, was er
    anfasst: ein zusaetzliches Feld in dieser Anweisung waere ein
    geloeschter Messwert.
    """
    sql = " ".join(lims_db.trdf_export_sql().lower().split())
    assert "nvl" not in sql
    assert sql.count("set") == 1
    gesetzt = sql[sql.index("set") + 3:sql.index("where")]
    for spalte in ("mw_roh = :wert", "mw = :wert", "fc8 = :fc8",
                   "psta_id = :psta_id", "korrektur_flag = :korrektur_flag"):
        assert spalte in gesetzt, spalte
    assert gesetzt.count("=") == 5          # und nichts sonst
    # Der volle Schluessel - weniger davon koennte mehr als eine Zeile
    # treffen.
    for teil in ("prob_id = :prob_id", "pm_id = :pm_id",
                 "pm_ver = :pm_ver", "um_id = :um_id",
                 "gegr_id = :gegr_id"):
        assert teil in sql, teil
    assert sql.startswith("update ergebnisse")


def test_mw_und_mw_roh_bekommen_denselben_wert() -> None:
    """Bei TRDF gibt es keine Faktorverrechnung - zwei Werte waeren zwei
    Aussagen ueber dieselbe Sache."""
    sql = lims_db.trdf_export_sql()
    assert sql.count(":wert") == 2


def test_ein_unvollstaendiger_satz_kommt_nicht_in_die_datenbank() -> None:
    ganz = {"wert": "1,7", "fc8": "x", "psta_id": 2, "korrektur_flag": "F",
            "prob_id": 1, "pm_id": 2, "pm_ver": 1, "um_id": 3, "gegr_id": 4}
    lims_db.trdf_satz_pruefen(ganz)                    # wirft nicht
    for feld in ganz:
        if feld in lims_db.TRDF_DARF_LEER:
            continue                    # die GEGR_ID darf im LIMS leer sein
        fehlt = dict(ganz, **{feld: None})
        try:
            lims_db.trdf_satz_pruefen(fehlt)
        except ValueError:
            continue
        raise AssertionError(f"{feld} fehlte und fiel nicht auf")


def test_ein_leerer_wert_wuerde_loeschen_und_wird_abgewiesen() -> None:
    satz = {"wert": "  ", "fc8": "x", "psta_id": 2, "korrektur_flag": "F",
            "prob_id": 1, "pm_id": 2, "pm_ver": 1, "um_id": 3, "gegr_id": 4}
    try:
        lims_db.trdf_satz_pruefen(satz)
    except ValueError as fehler:
        assert "loeschen" in str(fehler)
    else:
        raise AssertionError("Der leere Wert kam durch")


def test_der_anhang_hebt_den_alten_wert_auf() -> None:
    """MW_OLD bekommt, was in MW stand - wie das LIMS es selbst haelt.

    Und zwar aus der Spalte, nicht aus einer Bindevariablen: Oracle
    wertet die Zuweisungen einer UPDATE-Anweisung gegen den Stand vor
    der Aenderung aus, damit kommt der Wert hinein, der wirklich in der
    Zeile stand.
    """
    sql = " ".join(lims_db.trdf_anhang_sql().lower().split())
    assert sql.startswith("update teilproben_anhang set ")
    gesetzt = sql[sql.index("set") + 3:sql.index("where")]
    assert "mw_old = mw" in gesetzt and "mw = :wert" in gesetzt
    assert gesetzt.count("=") == 2 and "nvl" not in gesetzt
    for teil in ("prob_id = :prob_id", "um_id = :um_id",
                 "rohw_id = :rohw_id"):
        assert teil in sql, teil


def test_teilproben_anhang_wird_nur_an_zwei_stellen_geschrieben() -> None:
    """Der Anhang traegt die Rohwerte, aus denen das LIMS rechnet.

    Genau zwei Anweisungen darf es geben, und beide gehen ueber eine
    bestaetigte Uebersicht: die Korrektur (`trdf_anhang_sql`, sie hebt
    den bisherigen Wert nach MW_OLD) und das Zurueckspielen
    (`trdf_anhang_zurueck_sql`, es stellt beide Spalten auf den
    gesicherten Stand). Eine dritte waere ein Weg daran vorbei - und der
    soll auffallen, bevor er in einer Serie auffaellt.
    """
    quelle = pathlib.Path(lims_db.__file__).parent
    gefunden = []
    for datei in sorted(quelle.glob("*.py")):
        if datei.name.startswith("test_"):
            continue
        text = " ".join(datei.read_text(encoding="utf-8").split()).lower()
        for anweisung in ("update teilproben_anhang",
                          "delete from teilproben_anhang",
                          "insert into teilproben_anhang"):
            gefunden += [f"{datei.name}: {anweisung}"] * text.count(anweisung)
    assert gefunden == ["lims_db.py: update teilproben_anhang"] * 2, gefunden


def test_das_zurueckspielen_stellt_beide_spalten_wieder_her() -> None:
    """Ein halb wiederhergestellter Stand waere keiner."""
    sql = " ".join(lims_db.trdf_anhang_zurueck_sql().lower().split())
    gesetzt = sql[sql.index("set") + 3:sql.index("where")]
    assert "mw = :wert" in gesetzt and "mw_old = :alt" in gesetzt
    assert gesetzt.count("=") == 2
    # Und die Korrektur bindet MW_OLD gerade nicht - sie nimmt die
    # Spalte, damit kein veralteter Stand fortgeschrieben wird.
    assert ":alt" not in lims_db.trdf_anhang_sql()


def test_ein_leeres_mw_old_ist_beim_zurueckspielen_in_ordnung() -> None:
    satz = {"wert": "1,8", "alt": "", "prob_id": 1, "um_id": 2, "rohw_id": 3}
    lims_db.trdf_anhang_zurueck_pruefen(satz)          # wirft nicht
    try:
        lims_db.trdf_anhang_zurueck_pruefen({"wert": "1,8", "prob_id": 1,
                                             "um_id": 2, "rohw_id": 3})
    except ValueError as fehler:
        assert "Zurueckspielen" in str(fehler)
    else:
        raise AssertionError("Der fehlende alte Stand fiel nicht auf")


# --- Die Stammdaten eines Standards ---------------------------------------

def test_der_rueckweg_erkennt_das_zurueckspielen_am_satz() -> None:
    verbindung = Verbindung([], [])
    cursor = ExportCursor(rowcount=1)
    verbindung.cursor = lambda: cursor
    lims_db.trdf_exportieren(
        Zugang(verbindung), [],
        anhang=[{"wert": "1,8", "alt": "1,9", "prob_id": 1, "um_id": 2,
                 "rohw_id": 3}])
    geschrieben = [" ".join(sql.lower().split()) for sql in cursor.ausgefuehrt
                   if sql.lstrip().upper().startswith("UPDATE")]
    assert any("mw_old = :alt" in sql for sql in geschrieben)


def test_beim_zurueckspielen_darf_der_gesicherte_stand_leer_sein() -> None:
    """Zurueckgestellt wird, was die Sicherung festhaelt.

    PSTA_ID ist im LIMS nullable, und wo vor der Korrektur weder ein
    Bearbeitungsstand noch ein Wert stand, darf danach wieder keiner
    stehen - sonst waere das Zurueckspielen keines, sondern eine zweite
    Korrektur. Beim Korrigieren bleibt beides ein Fehler.
    """
    leer = _zurueck_satz(psta_id=None, wert="", mw="", fc8="",
                         korrektur_flag="")
    lims_db.trdf_zurueck_pruefen(leer)                 # wirft nicht
    for feld in ("psta_id", "wert"):
        try:
            lims_db.trdf_satz_pruefen(_trdf_satz(**{feld: None if feld ==
                                                    "psta_id" else ""}))
        except ValueError:
            continue
        raise AssertionError(f"{feld} war leer und fiel beim Korrigieren "
                             f"nicht auf")


def test_auch_zurueck_muss_der_schluessel_vollstaendig_sein() -> None:
    """Ohne Schluessel findet die Anweisung die Zeile nicht wieder."""
    for feld in lims_db.TRDF_ZURUECK_SCHLUESSEL:
        try:
            lims_db.trdf_zurueck_pruefen(_zurueck_satz(**{feld: None}))
        except ValueError as fehler:
            assert feld in str(fehler)
            continue
        raise AssertionError(f"{feld} fehlte und fiel nicht auf")
    # Die GEGR_ID darf leer sein, aber im Satz stehen muss sie.
    lims_db.trdf_zurueck_pruefen(_zurueck_satz(gegr_id=None))
    ohne = _zurueck_satz()
    ohne.pop("gegr_id")
    try:
        lims_db.trdf_zurueck_pruefen(ohne)
    except ValueError as fehler:
        assert "gegr_id" in str(fehler)
    else:
        raise AssertionError("Die fehlende GEGR_ID fiel nicht auf")


def test_ein_x_ist_ein_wert_und_kommt_immer_durch() -> None:
    """Das LIMS kennt drei Staende: eine Zahl, ein „x“ (hier soll nichts
    stehen) und leer. Das x ist eine Aussage und kein fehlender Wert."""
    lims_db.trdf_satz_pruefen(_trdf_satz(wert="x"))          # wirft nicht
    lims_db.trdf_anhang_satz_pruefen(
        {"wert": "x", "prob_id": 1, "um_id": 2, "rohw_id": 3})


def test_geleert_wird_nur_mit_erlaubnis() -> None:
    """Der Schutz bleibt, wo er hingehoert - die TRDF-Pruefung bekommt
    ihn abgenommen, weil sie den Stand herstellt, den die Variante
    verlangt, und weil vorher eine Uebersicht und eine Sicherung stehen."""
    for pruefen, satz in (
            (lims_db.trdf_satz_pruefen, _trdf_satz(wert="")),
            (lims_db.trdf_anhang_satz_pruefen,
             {"wert": "", "prob_id": 1, "um_id": 2, "rohw_id": 3})):
        try:
            pruefen(satz)
        except ValueError as fehler:
            assert "loeschen" in str(fehler)
        else:
            raise AssertionError("Der leere Wert fiel nicht auf")
        pruefen(satz, leeren=True)                           # wirft nicht


def test_die_erlaubnis_geht_bis_in_die_anweisung() -> None:
    verbindung = Verbindung([], [])
    verbindung.cursor = lambda: ExportCursor(rowcount=1)
    lims_db.trdf_exportieren(
        Zugang(verbindung), [_trdf_satz(wert="")], None,
        [{"wert": "", "prob_id": 1, "um_id": 2, "rohw_id": 3}], None,
        leeren=True)                                         # wirft nicht
    try:
        lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz(wert="")])
    except ValueError as fehler:
        assert "loeschen" in str(fehler)
    else:
        raise AssertionError("Ohne Erlaubnis haette es auffallen muessen")


def test_der_rueckweg_stellt_mw_und_mw_roh_einzeln_zurueck() -> None:
    """Die Korrektur schreibt beiden denselben Wert - vorher kann dort
    etwas anderes gestanden haben, und die Sicherung haelt beides fest."""
    sql = " ".join(lims_db.trdf_zurueck_sql().lower().split())
    gesetzt = sql[sql.index("set") + 3:sql.index("where")]
    assert "mw_roh = :wert" in gesetzt and "mw = :mw" in gesetzt
    assert ":wert" not in gesetzt.split("mw_roh = :wert")[1]
    # Der Schluessel ist derselbe wie beim Korrigieren - Wort fuer Wort.
    korrektur = " ".join(lims_db.trdf_export_sql().lower().split())
    assert (sql[sql.index("where"):]
            == korrektur[korrektur.index("where"):])


def test_zurueckspielen_schreibt_wirklich_zurueck() -> None:
    """Beide Stellen, eine Transaktion, und die richtigen Werte darin."""
    verbindung = Verbindung([], [])
    cursor = ExportCursor(rowcount=1)
    verbindung.cursor = lambda: cursor
    lims_db.trdf_exportieren(
        Zugang(verbindung), [_zurueck_satz(wert="1,8", mw="1,9")], None,
        [{"wert": "1,8", "alt": "2,0", "prob_id": 11, "um_id": 42,
          "rohw_id": 13}], None, zurueck=True)
    anweisungen = [" ".join(sql.lower().split())
                   for sql in cursor.ausgefuehrt
                   if sql.lstrip().upper().startswith("UPDATE")]
    assert len(anweisungen) == 2, anweisungen
    assert any("update ergebnisse" in sql and "mw = :mw" in sql
               for sql in anweisungen)
    assert any("update teilproben_anhang" in sql and "mw_old = :alt" in sql
               for sql in anweisungen)
    geschrieben = [satz for satz in cursor.saetze if "wert" in satz]
    assert geschrieben[0]["mw"] == "1,9"          # nicht "1,8"
    assert geschrieben[1]["alt"] == "2,0"
    assert verbindung.commits == 1


def test_zurueck_wird_auch_ohne_anhang_erkannt() -> None:
    """Eine gerechnete Groesse haengt an keinem Anhang.

    Dann sagt kein Satz mehr, in welche Richtung geschrieben wird -
    deshalb sagt es der Aufrufer.
    """
    verbindung = Verbindung([], [])
    verbindung.cursor = lambda: ExportCursor(rowcount=1)
    lims_db.trdf_exportieren(Zugang(verbindung),
                             [_zurueck_satz(psta_id=None, wert="", mw="")],
                             zurueck=True)             # wirft nicht
    try:
        lims_db.trdf_exportieren(Zugang(verbindung),
                                 [_trdf_satz(psta_id=None)])
    except ValueError as fehler:
        assert "psta_id" in str(fehler)
    else:
        raise AssertionError("Beim Korrigieren waere das ein Fehler")


def test_ein_unvollstaendiger_anhangsatz_kommt_nicht_durch() -> None:
    ganz = {"wert": "1,7", "prob_id": 1, "um_id": 2, "rohw_id": 3}
    lims_db.trdf_anhang_satz_pruefen(ganz)
    for feld in ganz:
        try:
            lims_db.trdf_anhang_satz_pruefen(dict(ganz, **{feld: None}))
        except ValueError:
            continue
        raise AssertionError(f"{feld} fehlte und fiel nicht auf")


def _anhangsatz(**rest):
    satz = {"wert": "1,7", "prob_id": 11, "um_id": 42, "rohw_id": 7}
    satz.update(rest)
    return satz


def test_beide_stellen_gehen_in_einer_transaktion() -> None:
    """Nur eine von beiden zu schreiben waere schlimmer als keine."""
    verbindung = Verbindung([], [])
    cursor = ExportCursor(rowcount=1)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz()],
                                       anhang=[_anhangsatz()])
    assert bericht["geschrieben"] == 1
    assert bericht["anhang_geschrieben"] == 1
    assert verbindung.commits == 1
    # Erst die beiden Anweisungen, dann die Nachfrage an beide Stellen.
    anweisungen = [sql.split()[1].lower() for sql in cursor.ausgefuehrt]
    assert anweisungen[:2] == ["ergebnisse", "teilproben_anhang"]
    assert all(sql.lstrip().upper().startswith("SELECT")
               for sql in cursor.ausgefuehrt[2:])


def test_scheitert_der_anhang_bleibt_auch_das_ergebnis_draussen() -> None:
    verbindung = Verbindung([], [])
    verbindung.cursor = lambda: ExportCursor(rowcount=1, fehler=2)
    try:
        lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz()],
                                 anhang=[_anhangsatz()])
    except Exception:
        pass
    else:
        raise AssertionError("Der Fehler ging unter")
    assert verbindung.rollbacks == 1 and verbindung.commits == 0


def test_eine_fehlende_anhangzeile_wird_gemeldet() -> None:
    verbindung = Verbindung([], [])
    verbindung.cursor = lambda: ExportCursor(rowcount=0)
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), [],
                                       anhang=[_anhangsatz()])
    assert bericht["anhang_geschrieben"] == 0
    assert len(bericht["anhang_ohne_zeile"]) == 1


def test_der_anhang_wird_ueber_die_teilprobe_gefunden() -> None:
    """Die Serie steht nicht im Anhang - sie kommt ueber TEILPROBEN."""
    text, bindungen = trdf_sql("trdf_rohwerte_anhang", "2026B051", 261)
    text = " ".join(text.lower().split())
    assert "join teilproben t" in text
    assert "t.serie = :serie" in text and "t.um_id = :um_id" in text
    assert "a.rohw_id" in text and "a.formelkuerzel" in text
    assert bindungen == {"serie": "2026B051", "um_id": 261}


def test_der_anhang_traegt_seine_probennummer() -> None:
    """Die PROB_ID allein reicht nicht: dieselbe Probe steht im LIMS
    unter mehreren Anlagen, und der Anhang haengt dann an einer
    anderen als die Ergebniszeile. Ohne die Nummer faellt er beim
    Zuordnen still heraus."""
    text, _bindungen = trdf_sql("trdf_rohwerte_anhang", "2026B051", 261)
    text = " ".join(text.lower().split())
    assert "p.probe_nr" in text
    assert "join proben p on p.id = a.prob_id" in text
    assert lims_db.TRDF_ANHANG_FELDER[0] == "probe_nr"


def test_der_anhang_wird_bei_anderer_anlage_nachgefragt() -> None:
    """Dieselbe Probe unter zwei PROB_ID: die Serie sieht nur die eine,
    der Teilprobenanhang haengt an der anderen.

    Gefragt wird ueber die Probennummer - und unter *derselben*
    Methode. Wer TRDF3.2 abruft, bekommt die Rohwerte der TRDF3.2 und
    nicht die der verworfenen TRDF3.1, die daneben an derselben Probe
    haengt.
    """
    text, bindungen = trdf_sql("trdf_rohwerte_nachtrag", [447370], 261)
    text = " ".join(text.lower().split())
    assert "from teilproben_anhang a" in text
    assert "p.probe_nr in (select q.probe_nr from proben q" in text
    assert "a.um_id = :um_id" in text
    assert bindungen["um_id"] == 261
    # Und die verworfene Methode bleibt draussen, auch wenn sie ueber
    # die Probennummer erreichbar waere.
    assert "a.um_id not in" in text
    assert "TRDF3.1" in str(bindungen.values()).upper()
    # Wiederholungen bleiben draussen, wie ueberall.
    assert "nvl(p.wdh_um, 1) = 1" in text
    # Aufsteigend: haben mehrere Anlagen einen Anhang, gilt die
    # zuletzt angelegte - der Aufrufer legt sie der Reihe nach ab.
    assert "order by p.probe_nr, a.prob_id, a.lnr" in text


def _zurueck_satz(**rest):
    """Ein Satz, wie ihn das Zurueckspielen schickt - mit MW."""
    satz = _trdf_satz(mw="1,7")
    satz.update(rest)
    return satz


def _trdf_satz(**rest):
    satz = {"wert": "1,7", "fc8": lims_db.TRDF_FC8,
            "psta_id": lims_db.PSTA_GESENDET,
            "korrektur_flag": lims_db.KORREKTUR_FLAG,
            "prob_id": 11, "pm_id": 1084, "pm_ver": 1, "um_id": 42,
            "gegr_id": 7}
    satz.update(rest)
    return satz


def test_der_rueckweg_schreibt_und_bestaetigt() -> None:
    verbindung = Verbindung([], [])
    cursor = ExportCursor(rowcount=1)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung),
                                       [_trdf_satz(), _trdf_satz(pm_id=905)])
    assert bericht["geschrieben"] == 2 and bericht["ohne_zeile"] == []
    assert verbindung.commits == 1 and verbindung.geschlossen


def test_eine_zeile_die_es_nicht_gibt_wird_gemeldet_und_nicht_angelegt() -> None:
    verbindung = Verbindung([], [])
    cursor = ExportCursor(rowcount=0)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz()])
    assert bericht["geschrieben"] == 0
    assert len(bericht["ohne_zeile"]) == 1
    assert not any("insert" in sql.lower() for sql in cursor.ausgefuehrt)


def test_ein_fehler_rollt_den_ganzen_rueckweg_zurueck() -> None:
    verbindung = Verbindung([], [])
    cursor = ExportCursor(rowcount=1, fehler=2)
    verbindung.cursor = lambda: cursor
    try:
        lims_db.trdf_exportieren(Zugang(verbindung),
                                 [_trdf_satz(), _trdf_satz(pm_id=905)])
    except Exception:
        pass
    else:
        raise AssertionError("Der Fehler ging unter")
    assert verbindung.rollbacks == 1 and verbindung.commits == 0


class Buch:
    """Ein Protokollbuch, das nur mitschreibt."""

    def __init__(self):
        self.eintraege = []

    def eintragen(self, sql, werte, hinweis=""):
        self.eintraege.append((sql, werte, hinweis))

    def viele(self, sql, saetze, hinweise=None):
        self.eintraege.append((sql, saetze, hinweise))


class NachleseCursor(ExportCursor):
    """Ein Cursor, der auf die Nachfrage einen bestimmten Wert liefert.

    `steht_da` ist, was nach dem Schreiben in der Datenbank steht - eine
    Zeichenkette, oder None fuer "die Zeile gibt es nicht". Geantwortet
    wird wie Oracle auf die Sammelabfrage: je gefragtem Satz eine Zeile
    mit Schluessel und Wert, GEGR_ID aus `gegr_id`.
    """

    def __init__(self, steht_da="1,7", gegr_id=7, **rest):
        super().__init__(**rest)
        self.steht_da = steht_da
        self.gegr_id = gegr_id
        self.nachgefragt = []
        self.abfragen = 0

    def execute(self, sql, *args, **kwargs):
        if sql.lstrip().upper().startswith("SELECT"):
            Cursor.execute(self, sql, *args, **kwargs)
            bindungen = args[0] if args else kwargs
            self.nachgefragt.append(bindungen)
            self.abfragen += 1
            anhang = "teilproben_anhang" in sql
            felder = (("prob_id", "um_id", "rohw_id") if anhang
                      else ("prob_id", "pm_id", "pm_ver", "um_id"))
            self.zeilen = []
            nummer = 0
            while f"prob_id{nummer}" in bindungen and self.steht_da is not None:
                schluessel = tuple(bindungen[f"{feld}{nummer}"]
                                   for feld in felder)
                if not anhang:
                    schluessel += (self.gegr_id,)
                self.zeilen.append(schluessel + (self.steht_da,))
                nummer += 1
            return None
        return super().execute(sql, *args, **kwargs)


def test_nach_dem_schreiben_wird_nachgelesen() -> None:
    """Ein UPDATE, das eine Zeile trifft und trotzdem den alten Wert
    stehen laesst, sieht von aussen aus wie ein gelungener Export."""
    verbindung = Verbindung([], [])
    cursor = NachleseCursor(steht_da="1,7", rowcount=1)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz()])
    assert bericht["geschrieben"] == 1
    assert bericht["nicht_uebernommen"] == []
    # Gefragt wurde mit demselben Schluessel, mit dem geschrieben wurde.
    assert cursor.nachgefragt[0] == {"prob_id0": 11, "pm_id0": 1084,
                                     "pm_ver0": 1, "um_id0": 42}


def test_ein_alter_wert_nach_dem_schreiben_faellt_auf() -> None:
    verbindung = Verbindung([], [])
    cursor = NachleseCursor(steht_da="1,8", rowcount=1)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz()])
    assert bericht["geschrieben"] == 1          # getroffen hat sie
    assert len(bericht["nicht_uebernommen"]) == 1   # geaendert nicht


def test_eine_fehlende_zeile_beim_nachlesen_faellt_auf() -> None:
    verbindung = Verbindung([], [])
    cursor = NachleseCursor(steht_da=None, rowcount=1)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz()])
    assert len(bericht["nicht_uebernommen"]) == 1


def test_eine_andere_gruppe_zaehlt_nicht_als_angekommen() -> None:
    """GEGR_ID steht nicht in der IN-Liste - verglichen wird sie trotzdem."""
    verbindung = Verbindung([], [])
    cursor = NachleseCursor(steht_da="1,7", gegr_id=8, rowcount=1)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), [_trdf_satz()])
    assert len(bericht["nicht_uebernommen"]) == 1


def test_eine_leere_gruppe_wird_gefunden() -> None:
    """NULL faende in der IN-Liste nichts; deshalb vergleicht Python."""
    verbindung = Verbindung([], [])
    cursor = NachleseCursor(steht_da="1,7", gegr_id=None, rowcount=1)
    verbindung.cursor = lambda: cursor
    bericht = lims_db.trdf_exportieren(Zugang(verbindung),
                                        [_trdf_satz(gegr_id=None)])
    assert bericht["nicht_uebernommen"] == []


def test_nachgelesen_wird_als_sammelabfrage() -> None:
    """Eine Rundreise je 200 Saetze statt einer je Satz."""
    verbindung = Verbindung([], [])
    cursor = NachleseCursor(steht_da="1,7", rowcount=1)
    verbindung.cursor = lambda: cursor
    saetze = [_trdf_satz(prob_id=1000 + n) for n in range(450)]
    anhang = [{"prob_id": 1000 + n, "um_id": 42, "rohw_id": 5, "wert": "1,7"}
              for n in range(3)]
    bericht = lims_db.trdf_exportieren(Zugang(verbindung), saetze,
                                        anhang=anhang)
    assert bericht["nicht_uebernommen"] == []
    assert bericht["anhang_nicht_uebernommen"] == []
    # 450 Ergebniszeilen in 3 Stuecken, der Anhang in einem.
    assert cursor.abfragen == 4
    assert len(cursor.nachgefragt[0]) == 4 * lims_db.NACHLESEN_JE_FRAGE
    assert "IN ((:prob_id0, :um_id0, :rohw_id0))" in " ".join(
        lims_db.trdf_anhang_nachlesen_sql(1).split())


def test_nachgelesen_wird_erst_nach_dem_festschreiben() -> None:
    """Vorher saehe die eigene Transaktion ohnehin ihre eigenen
    Aenderungen - die Frage waere dann keine."""
    quelle = pathlib.Path(lims_db.__file__).read_text(encoding="utf-8")
    text = quelle[quelle.index("def trdf_exportieren("):]
    assert text.index("verbindung.commit()") < text.index("_nachpruefen(")


def test_eine_zahl_bleibt_dieselbe_zahl() -> None:
    """Ein angehaengtes Leerzeichen ist kein Unterschied in der Sache."""
    assert lims_db._angekommen(" 1,7 ", "1,7")
    assert lims_db._angekommen("1,70", "1,7")
    assert not lims_db._angekommen("1,8", "1,7")
    assert not lims_db._angekommen(None, "1,7")
    assert not lims_db._angekommen("", "1,7")


def test_die_gegr_id_darf_leer_sein() -> None:
    """In ERGEBNISSE ist sie nullable - und `= :gegr_id` traefe eine
    solche Zeile nie, weil NULL mit nichts gleich ist."""
    sql = " ".join(lims_db.trdf_export_sql().lower().split())
    assert "(gegr_id = :gegr_id or (gegr_id is null and :gegr_id is null))" \
        in sql
    satz = _trdf_satz(gegr_id=None)
    lims_db.trdf_satz_pruefen(satz)             # wirft nicht
    ohne = dict(satz)
    del ohne["gegr_id"]
    try:
        lims_db.trdf_satz_pruefen(ohne)
    except ValueError as fehler:
        assert "gegr_id" in str(fehler)
    else:
        raise AssertionError("Die fehlende GEGR_ID fiel nicht auf")


def test_der_rueckweg_steht_im_aenderungsprotokoll() -> None:
    """Wer einen Messwert ueberschreibt, hinterlaesst eine Spur."""
    verbindung = Verbindung([], [])
    verbindung.cursor = lambda: ExportCursor(rowcount=1)
    buch = Buch()
    lims_db.trdf_exportieren(Zugang(verbindung, buch), [_trdf_satz()],
                             ["TRDF-Korrektur 2026B051: Probe 26B0011"])
    assert buch.eintraege
    sql, werte, hinweis = buch.eintraege[0]
    assert "update ergebnisse" in sql.lower()
    assert "TRDF-Korrektur" in hinweis
    assert werte["wert"] == "1,7"


# --------------------------------------------------------------------------
# tnsnames.ora und die Wahl der Datenbank
# --------------------------------------------------------------------------

TNS_BEISPIEL = """
# TNSNAMES.ORA Network Configuration File
ECO =
  (DESCRIPTION =
    (ADDRESS_LIST =
      (ADDRESS = (PROTOCOL = TCP)(HOST = db.nw-fva.de)(PORT = 1521))
    )
    (CONNECT_DATA =
      (SERVICE_NAME = ECO.NW-FVA)
    )
  )

LIMS =
  (DESCRIPTION =
    (ADDRESS_LIST =
      (ADDRESS = (PROTOCOL = TCP)(HOST = db.nw-fva.de)(PORT = 1521))  # Kommentar
    )
    (CONNECT_DATA =
      (SERVICE_NAME = LIMS.NW-FVA)
    )
  )

LIMSTEST =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = db.nw-fva.de)(PORT = 1521))
    (CONNECT_DATA = (SERVICE_NAME = LIMSTEST.NW-FVA))
  )
"""


def test_die_tnsnames_wird_gelesen() -> None:
    gelesen = lims_db.tnsnames_lesen(TNS_BEISPIEL)
    assert set(gelesen) == {"ECO", "LIMS", "LIMSTEST"}
    assert gelesen["LIMS"] == (
        "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)"
        "(HOST=db.nw-fva.de)(PORT=1521)))"
        "(CONNECT_DATA=(SERVICE_NAME=LIMS.NW-FVA)))")
    assert "LIMSTEST.NW-FVA" in gelesen["LIMSTEST"]


def test_eine_offene_klammer_faellt_auf() -> None:
    try:
        lims_db.tnsnames_lesen("LIMS = (DESCRIPTION = (ADDRESS = ")
    except ValueError as fehler:
        assert "LIMS" in str(fehler)
    else:
        raise AssertionError("Die offene Klammer fiel nicht auf")


def test_aus_der_datei_kommt_nur_lims() -> None:
    ordner = tempfile.mkdtemp(prefix="tns-")
    pfad = os.path.join(ordner, "tnsnames.ora")
    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write(TNS_BEISPIEL)
    assert list(lims_db.deskriptoren(pfad)) == ["LIMS"]


def test_ohne_lims_in_der_datei_gibt_es_keine_anmeldung() -> None:
    ordner = tempfile.mkdtemp(prefix="tns-")
    pfad = os.path.join(ordner, "tnsnames.ora")
    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write("ECO = (DESCRIPTION = (CONNECT_DATA = (SID = ECO)))")
    try:
        lims_db.deskriptoren(pfad)
    except ValueError as fehler:
        assert "LIMS" in str(fehler)
    else:
        raise AssertionError("Eine Datei ohne LIMS wurde angenommen")


def test_die_mitgelieferte_tnsnames_traegt_lims() -> None:
    """Dieselbe Datei, die der Bau in die exe packt."""
    pfad = os.path.join(os.path.dirname(os.path.abspath(lims_db.__file__)),
                        "tnsnames.ora")
    assert os.path.isfile(pfad)
    assert "LIMS.NW-FVA" in lims_db.deskriptoren(pfad)["LIMS"]
    assert lims_db.DATENBANKEN == ("LIMS",)


def test_eine_andere_datenbank_ist_nicht_zugelassen() -> None:
    for alias in ("LIMSTEST", "ECO", "", "lims-irgendwas"):
        try:
            lims_db.anmelden("pruefer", "geheim", alias)
        except ValueError as fehler:
            assert "nicht zugelassen" in str(fehler)
        else:
            raise AssertionError(f"{alias!r} wurde angenommen")


def test_neben_dem_programm_geht_vor() -> None:
    """Wer neben der exe eine tnsnames.ora ablegt, meint sie."""
    orte = lims_db.tnsnames_orte()
    assert orte[0] == os.path.join(lims_db._programmordner(), "tnsnames.ora")


def test_der_selbsttest_findet_die_tnsnames() -> None:
    code, zeilen = lims_db.selbsttest()
    text = "\n".join(zeilen)
    assert "tnsnames.ora gelesen" in text, text
    # Ohne Netz scheitert die Verbindung ins Leere - erwartet; ein
    # unvollstaendiges Paket waere ein Fehler mit Code 1.
    assert code == 0, text


def main() -> int:
    tests = [wert for name, wert in sorted(globals().items())
             if name.startswith("test_") and callable(wert)]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"{len(tests)} Pruefungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
