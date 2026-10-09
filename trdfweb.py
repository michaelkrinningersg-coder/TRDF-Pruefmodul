"""
TRDF-Pruefmodul - die Weboberflaeche (pywebview + Svelte)
=========================================================

Dieselbe Einzelauswertung wie trdfpruefmodul.py, nur mit einem anderen
Gesicht: ein Fenster mit Edge WebView2, darin eine Svelte-Seite, und
dazwischen die Python-JS-Bruecke von pywebview - ohne HTTP-Server und
ohne Konsolenfenster.

Gerechnet, geprueft und geschrieben wird mit denselben Modulen wie in
der Tk-Fassung: das Modell (trdfmodell.TrdfModell) haelt die Serie, und
was hier steht, ist nur die Bruecke. Jede oeffentliche Methode von `Api`
ist aus JavaScript als `window.pywebview.api.<name>(...)` erreichbar und
gibt JSON-taugliche Woerterbuecher zurueck.

Startpunkte
-----------
    python trdfweb.py               das Fenster (Windows: WebView2)
    python trdfweb.py --selbsttest  Bestandteile pruefen, ohne Fenster
    python trdfweb.py --dienst 8765 [--demo]
                                    dieselbe Seite im Browser - fuer die
                                    Entwicklung und die Bilder der
                                    Anleitung; --demo nimmt eine
                                    erfundene Serie statt des LIMS

Zugangsdaten leben nur im Arbeitsspeicher, solange das Programm laeuft.
"""

from __future__ import annotations

import datetime as dt
import decimal
import importlib
import json
import logging
import os
import sys
import threading
import traceback

import config
import lims_db
import trdf
import trdfbild
import trdfblock
import trdfexport
import trdflegende
import trdfpruefung
import trdfrohpruefung
from trdfmodell import (BEWERTUNGSSPALTE, BLATT_ERGEBNIS, BLATT_PRUEFUNG,
                        BLATT_ROH, QUELLE_TEXT, TrdfModell, methodentexte,
                        vorschauhinweis)

APP_TITEL = "TRDF-Prüfmodul"
APP_VERSION = "v2.0"

# Wo die gebaute Svelte-Seite liegt - im Quelltext neben dieser Datei,
# in der exe im ausgepackten Ordner.
WEBORDNER = "webdist"

# Was im Protokoll steht, sobald die Seite Python erreicht hat.
SEITE_VERBUNDEN = "Seite mit Python verbunden"

# Das Fenstersymbol: unter Windows nur als .ico.
SYMBOL_WINDOWS = "Icon.ico"
SYMBOL = "Icon.png"

# Die Breiten der Spalten in Bildpunkten - wie in der Tk-Fassung, nur
# etwas grosszuegiger, weil die Schrift der Seite breiter laeuft.
BREITEN_ROH = {"Zeile": 64, "Probe": 112, "WGH": 80, BEWERTUNGSSPALTE: 460}
BREITEN_ERGEBNIS = {"Zeile": 64, "Probe": 112, BEWERTUNGSSPALTE: 420}
BREITEN_PRUEFUNG = {"Zeile": 64, "Probe-Nr.": 112, "Bewertung": 520}
BREITE_VORGABE = 92
BREITE_ZEICHEN = 7.6

# Wie die Tabellen in den Einstellungen heissen und wie in der Seite.
BLAETTER = {"roh": BLATT_ROH, "ergebnis": BLATT_ERGEBNIS,
            "pruefung": BLATT_PRUEFUNG}


def ressource(*teile) -> str:
    """Ein Pfad im Programm - im Quelltext wie in der ausgepackten exe."""
    basis = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(basis, *teile)


def klar(wert):
    """Macht einen Wert JSON-tauglich - Decimal, Datum und Tupel."""
    if isinstance(wert, dict):
        return {str(k): klar(v) for k, v in wert.items()}
    if isinstance(wert, (list, tuple, set)):
        return [klar(v) for v in wert]
    if isinstance(wert, decimal.Decimal):
        return format(wert.normalize(), "f").replace(".", ",") \
            if wert.is_finite() else str(wert)
    if isinstance(wert, (dt.datetime, dt.date)):
        return lims_db.als_text(wert)
    if wert is None or isinstance(wert, (str, int, float, bool)):
        return wert
    return str(wert)


class Hinweis(Exception):
    """Was der Anwender anders machen muss - kein Fehler im Programm."""


def _stand(satz, art="text") -> dict:
    return {"text": satz, "art": art}


class Websitzung(TrdfModell):
    """Das Modell einer Serie - und was die Weboberflaeche dazu braucht.

    Die Bruecke ruft aus mehreren Threads; alles, was den Stand aendert
    oder liest, geht deshalb unter einer Sperre.
    """

    def __init__(self, ordner=None, konfig=None):
        super().__init__(ordner, konfig)
        self.zugang = None
        self.auskunftszeile = ""
        self.um_text = ""
        self.letzter_export = None
        self.export_nach_zurueck = ""
        self.vorschau = None             # (Art, Aenderungen, Pfad)
        self.sperre = threading.RLock()
        # Je Probe, ob sie in einer Tabelle auffaellt - daraus die Zeile
        # unter der Tabelle, ohne nach jeder Eingabe alle durchzugehen.
        self.zaehler = {"roh": {}, "ergebnis": {}, "pruefung": {}}

    # ------------------------------------------------------- Tabellen
    def _spalten(self, tafel, breiten, aenderbar=(), quellen=None,
                 gruppen=None) -> list:
        hinweise = trdflegende.hinweise(tafel["spalten"], self.methoden,
                                        quellen, self.beschreibungen())
        gefunden = []
        for name in tafel["spalten"]:
            kopf = [teil for teil in str(tafel["koepfe"].get(name, name)
                                         or name).split("\n")
                    if teil.strip()] or [name]
            # So breit, dass die Ueberschrift ganz dasteht - eine
            # abgeschnittene ist nicht mehr zu erkennen.
            noetig = BREITE_ZEICHEN * max(len(teil) for teil in kopf) + 22
            gefunden.append({
                "name": name,
                "kopf": kopf,
                "hinweis": hinweise.get(name, ""),
                "fest": name in tafel["fest"],
                "aenderbar": name in aenderbar,
                "gruppe": bool((gruppen or {}).get(name)),
                "breite": breiten.get(name, max(BREITE_VORGABE,
                                                min(noetig, 220)))})
        return gefunden

    def _rohzeile(self, lnr, probe) -> dict:
        werte, marken, befund = self.rohzeile(lnr, probe)
        self.zaehler["roh"][probe] = befund
        return {"id": probe, "w": klar(werte), "m": marken,
                "b": befund, "x": self.variante_x(probe),
                "l": [k for k in self.rohliste if self.ist_leer(probe, k)],
                "h": self.von_hand_bewegt(probe)}

    def _ergebniszeile(self, lnr, probe, gruppen) -> dict:
        werte, marken, auseinander = self.ergebniszeile(lnr, probe, gruppen)
        self.zaehler["ergebnis"][probe] = len(auseinander)
        return {"id": probe, "w": klar(werte), "m": marken,
                "b": bool(auseinander), "x": self.variante_x(probe)}

    def _pruefzeile(self, eintrag, spalten) -> dict:
        werte, marken = self.pruefzeile(eintrag, spalten)
        befund = bool(eintrag["bewertung"])
        self.zaehler["pruefung"][eintrag["probe"]] = befund
        return {"id": eintrag["probe"], "w": klar(werte), "m": marken,
                "b": befund, "x": self.variante_x(eintrag["probe"])}

    def rohstand(self) -> dict:
        gesamt = len(self.proben)
        auffaellig = sum(1 for wert in self.zaehler["roh"].values() if wert)
        if not gesamt:
            return _stand("")
        return _stand(f"{gesamt - auffaellig} von {gesamt} Proben mit "
                      f"sauberen Rohwerten"
                      + (f"  |  {auffaellig} zu pruefen" if auffaellig
                         else ""), "warn" if auffaellig else "text")

    def ergebnisstand(self) -> dict:
        gesamt = len(self.proben) * len(self.folge)
        abweichungen = sum(self.zaehler["ergebnis"].values())
        if not self.proben:
            return _stand("")
        return _stand(f"{gesamt - abweichungen} von {gesamt} Werten stimmen"
                      + (f"  |  {abweichungen} Abweichungen" if abweichungen
                         else ""), "warn" if abweichungen else "text")

    def pruefstand(self) -> dict:
        gesamt = len(self.proben)
        auffaellig = sum(1 for wert in self.zaehler["pruefung"].values()
                         if wert)
        if not gesamt:
            return _stand("")
        return _stand(f"{gesamt - auffaellig} von {gesamt} Proben ohne Befund"
                      + (f"  |  {auffaellig} zu pruefen" if auffaellig
                         else ""), "warn" if auffaellig else "text")

    def tafeln(self) -> dict:
        """Alle drei Tabellen - nach einem Abruf oder einer neuen Ordnung."""
        self.zaehler = {"roh": {}, "ergebnis": {}, "pruefung": {}}
        roh = self.rohtafel()
        ergebnis = self.ergebnistafel()
        pruefung = self.prueftafel()
        lnr = dict((probe, nummer) for nummer, probe in self.proben)
        gruppen = ergebnis["gruppen"]
        spalten_pruefung = pruefung["spalten"]
        return {
            "roh": {"spalten": self._spalten(roh, BREITEN_ROH, self.rohliste),
                    "zeilen": [self._rohzeile(lnr[probe], probe)
                               for _, probe in self.proben],
                    "stand": self.rohstand()},
            "ergebnis": {"spalten": self._spalten(ergebnis, BREITEN_ERGEBNIS,
                                                  gruppen=gruppen),
                         "zeilen": [self._ergebniszeile(lnr[probe], probe,
                                                        gruppen)
                                    for _, probe in self.proben],
                         "stand": self.ergebnisstand()},
            "pruefung": {"spalten": self._spalten(pruefung, BREITEN_PRUEFUNG,
                                                  quellen=trdfpruefung.QUELLEN),
                         "zeilen": [self._pruefzeile(eintrag,
                                                     spalten_pruefung)
                                    for eintrag in pruefung["blatt"]],
                         "stand": self.pruefstand()}}

    def zeilen_fuer(self, proben) -> dict:
        """Nur die Zeilen dieser Proben - nach einer Eingabe."""
        lnr = dict((probe, nummer) for nummer, probe in self.proben)
        gruppen = self._ergebnisspalten()[1]
        spalten_pruefung = self._pruefspalten()[0]
        aus_der_serie = self._serienblick()
        proben = [probe for probe in proben if probe in lnr]
        return {
            "roh": [self._rohzeile(lnr[p], p) for p in proben],
            "ergebnis": [self._ergebniszeile(lnr[p], p, gruppen)
                         for p in proben],
            "pruefung": [self._pruefzeile(self.gepruefte_probe(
                lnr[p], p, aus_der_serie), spalten_pruefung)
                for p in proben],
            "staende": {"roh": self.rohstand(),
                        "ergebnis": self.ergebnisstand(),
                        "pruefung": self.pruefstand()}}

    # ------------------------------------------------------ Legende
    def legendenstand(self) -> str:
        """Welche Spalte des Pruefblatts welchen Parameter zeigt."""
        teile = []
        for name in trdfpruefung.SPALTEN[2:-2]:
            kuerzel = trdfpruefung.QUELLEN[name]
            teile.append(f"{name} = {self.parameternamen.get(kuerzel) or kuerzel}")
        return (f"U-Methode {self.um_kuerzel}  |  Cges aus "
                f"{lims_db.ATNULL_MARKE}, CO3 aus {lims_db.ATNULL_CO3_MARKE}"
                "\n" + "  ·  ".join(teile))


class Api:
    """Die Bruecke - was die Svelte-Seite aufrufen darf.

    Jede Methode faengt ihre Fehler selbst und gibt sie als
    {"fehler": Text} zurueck: eine Ausnahme, die bis in JavaScript
    durchschlaegt, liest dort niemand.
    """

    def __init__(self, sitzung: Websitzung | None = None, demo=False):
        self._s = sitzung or Websitzung(konfig=config.Config())
        self._demo = demo
        self._fenster = None

    # ------------------------------------------------------------ Hilfen
    def _fenster_setzen(self, fenster):
        self._fenster = fenster

    def _sicher(self, arbeit):
        try:
            with self._s.sperre:
                return klar(arbeit())
        except Hinweis as hinweis:
            return {"fehler": str(hinweis)}
        except Exception as fehler:                      # noqa: BLE001
            traceback.print_exc()
            return {"fehler": lims_db.fehlertext(fehler)}

    def _ordner(self, name: str) -> str:
        return os.path.join(self._s._ordner, name)

    def _voll(self, stand=None) -> dict:
        s = self._s
        return {"serie": s.seriename(), "um_id": s.um_id,
                "kuerzel": s.um_kuerzel,
                "auskunft": s.auskunftszeile,
                "quelle": s.quelltext(),
                "quelle_um": s.quelle == QUELLE_TEXT,
                "rohliste": list(s.rohliste),
                "variante": trdfrohpruefung.VARIANTE,
                "proben": [probe for _, probe in s.proben],
                "tafeln": s.tafeln() if s.proben else None,
                "aenderungen": len(s.aenderungen()) if s.proben else 0,
                "legende": s.legendenstand() if s.proben else "",
                "bericht": self._bericht(),
                "stand": stand}

    # ------------------------------------------------------------ Start
    def start(self) -> dict:
        """Was die Anmeldung zeigt - der gemerkte Benutzer, die Datenbank."""
        # Steht im Protokoll: die Seite hat Python erreicht. Der Bau prueft
        # genau diese Zeile - ein offenes Fenster allein heisst noch nicht,
        # dass die Bruecke steht.
        logging.getLogger("trdfweb").info(SEITE_VERBUNDEN)

        def arbeit():
            konfig = self._s._einstellungen()
            try:
                lims_db.deskriptor(lims_db.DATENBANKEN[0])
                tns = {"text": f"tnsnames.ora: {lims_db.tnsnames_pfad()}",
                       "art": "text"}
            except Exception as fehler:                  # noqa: BLE001
                tns = {"text": str(fehler), "art": "fehler"}
            return {"titel": APP_TITEL, "version": APP_VERSION,
                    "benutzer": str(konfig.get("benutzer") or ""),
                    "datenbanken": list(lims_db.DATENBANKEN),
                    "serie": str(konfig.get("serie") or ""),
                    "berechnete": str(konfig.get("trdf_berechnete") or "aus"),
                    "auto_angleichen": str(konfig.get("trdf_auto_angleichen")
                                           or "aus") == "an",
                    "tnsnames": tns, "demo": self._demo,
                    "angemeldet": self._s.zugang is not None}
        return self._sicher(arbeit)

    def anmelden(self, benutzer: str, passwort: str, datenbank: str = "LIMS"):
        """Prueft die Zugangsdaten mit einer echten Verbindung."""
        try:
            if self._demo:
                zugang = DemoZugang(benutzer or "demo")
            else:
                zugang = lims_db.anmelden(str(benutzer or ""),
                                          str(passwort or ""),
                                          str(datenbank or "LIMS"))
        except Exception as fehler:                      # noqa: BLE001
            return {"ok": False, "fehler": lims_db.fehlertext(fehler)}
        with self._s.sperre:
            self._s.zugang = zugang
            konfig = self._s._einstellungen()
            konfig.set("benutzer", str(benutzer or "").strip())
            konfig.speichern()
        return {"ok": True, "benutzer": zugang.benutzer}

    def abmelden(self) -> dict:
        with self._s.sperre:
            self._s.zugang = None
        return {"ok": True}

    def serien(self) -> dict:
        """Die TRDF-Serien aus dem Fahrplan - fuer die Liste im Serienfeld."""
        def arbeit():
            zugang = self._zugang()
            if self._demo:
                serien = DEMO_SERIEN
            else:
                with lims_db.sitzung(zugang) as verbindung:
                    methoden = lims_db.trdf_methoden(zugang,
                                                     verbindung=verbindung)
                    serien = lims_db.trdf_serien(
                        zugang, [um for um, _ in methoden],
                        verbindung=verbindung)
            self._s.serienliste = list(serien)
            return {"serien": list(serien),
                    "stand": _stand(f"{len(serien)} TRDF-Serien im Fahrplan "
                                    f"- Serie waehlen und „Abfragen“.")}
        return self._sicher(arbeit)

    def _zugang(self):
        if self._s.zugang is None:
            raise Hinweis("Erst anmelden.")
        return self._s.zugang

    # ---------------------------------------------------- Serie und Methode
    def abfragen(self, serie: str) -> dict:
        """Welche TRDF-Methoden fuehrt die Serie?"""
        def arbeit():
            name = str(serie or "").strip()
            if not name:
                return {"methoden": [], "stand": _stand(
                    "Erst eine Serie waehlen.", "warn")}
            if self._demo:
                passend = demo_methoden(name)
            else:
                passend = self._s.methoden_abfragen(self._zugang(), name)
            if not passend:
                self._s.abgefragte_serie, self._s.methodenwahl = "", []
                return {"methoden": [], "stand": _stand(
                    f"Die Serie {name} fuehrt keine Untersuchungsmethode "
                    f"mit TRDF im Kuerzel.", "warn")}
            self._s.abgefragte_serie = name
            self._s.methodenwahl = methodentexte(passend)
            texte = [text for _u, _k, text in self._s.methodenwahl]
            stand = (_stand(f"Die Serie {name} fuehrt {len(texte)} "
                            f"TRDF-Methoden ({', '.join(texte)}) - bitte "
                            f"eine waehlen.", "warn")
                     if len(texte) > 1 else None)
            return {"methoden": [{"um_id": um, "kuerzel": k, "text": t}
                                 for um, k, t in self._s.methodenwahl],
                    "stand": stand}
        return self._sicher(arbeit)

    def laden(self, serie: str, um_id) -> dict:
        """Holt Serie und Methode und gibt den ganzen Stand zurueck."""
        def arbeit():
            name = str(serie or "").strip()
            if name != self._s.abgefragte_serie:
                raise Hinweis("Erst die Serie abfragen.")
            gewaehlt = [(um, k) for um, k, _t in self._s.methodenwahl
                        if str(um) == str(um_id)]
            if not gewaehlt:
                raise Hinweis("Erst eine Untersuchungsmethode waehlen.")
            um, kuerzel = gewaehlt[0]
            geholt = (demo_abruf(name, um, kuerzel) if self._demo
                      else self._s.abruf_holen(self._zugang(), name, um,
                                               kuerzel))
            return self._uebernehmen(name, geholt)
        return self._sicher(arbeit)

    def _uebernehmen(self, name, geholt) -> dict:
        s = self._s
        s.serie = name
        # Eine eingefuegte UM gehoert zur Serie, mit der sie kam.
        s.um_text = ""
        satz, warnung = s.daten_uebernehmen(geholt)
        s.auskunftszeile = s.auskunftstext(geholt)
        konfig = s._einstellungen()
        konfig.set("serie", name)
        konfig.speichern()
        voll = self._voll()
        # Was die Ergebnisse sagen, steht nach dem Abruf darunter - wie in
        # der Tk-Fassung: erst die Auskunft ueber den Abruf, dann der
        # Stand der Werte.
        voll["stand"] = _stand(satz, "warn" if warnung else "text")
        return voll

    def zustand(self) -> dict:
        """Der ganze Stand - nach einem Neuladen der Seite."""
        return self._sicher(self._voll)

    # ------------------------------------------------------------ Aendern
    def setzen(self, zellen, art: str = "tippen", offen=()) -> dict:
        """Rohwerte von Hand - eine Zelle, ein Block oder nach unten.

        `zellen` sind [Probe, Kuerzel, Wert]. Bei "tippen" und
        "nach_unten" wirkt eine Variante auf ihre Zeile, ein Block
        ("block") bringt seine Werte selbst mit. Zurueck kommen nur die
        Zeilen der beruehrten Proben und - fuer offene Bloecke - deren
        neues Bild.
        """
        def arbeit():
            s = self._s
            proben, gesetzt, varianten = [], 0, 0
            for probe, kuerzel, wert in zellen or ():
                probe, kuerzel = str(probe), str(kuerzel)
                # Ein X wird ein x - das ist die Schreibweise hier.
                wert = trdf.marke_klein(
                    str(wert if wert is not None else "").strip())
                if kuerzel not in s.rohliste:
                    continue
                s.vonhand[(probe, kuerzel)] = wert
                gesetzt += 1
                if probe not in proben:
                    proben.append(probe)
                if kuerzel == trdfrohpruefung.VARIANTE and art in (
                        "tippen", "nach_unten"):
                    varianten += len(s.variante_setzen(probe, wert))
            s._rechnung_vergessen(proben)
            antwort = self._nach_eingabe(proben, offen)
            if art == "block":
                satz = f"{gesetzt} Werte eingefuegt"
            elif art == "nach_unten":
                satz = f"{gesetzt} Zellen nach unten gefuellt"
            elif varianten:
                satz = (f"Variante {str(zellen[0][2]).strip()}: {varianten} "
                        f"Rohwerte angepasst")
            else:
                satz = ""
            antwort["meldung"] = _stand(satz) if satz else None
            return antwort
        return self._sicher(arbeit)

    def leere_fuellen(self, probe=None, spalte=None, offen=()) -> dict:
        """Strg+E / Strg+Shift+E: leere Rohwertzellen bekommen ein x."""
        def arbeit():
            s = self._s
            if spalte:
                if spalte not in s.rohliste:
                    return {"meldung": _stand(f"Spalte {spalte}: kein "
                                              f"Rohwert", "warn")}
                zellen = [(name, spalte) for _lnr, name in s.proben]
                wo = f"Spalte {spalte}"
            else:
                zellen = [(str(probe), kuerzel) for kuerzel in s.rohliste]
                wo = str(probe)
            gesetzt = [(name, kuerzel) for name, kuerzel in zellen
                       if s.ist_leer(name, kuerzel)]
            if not gesetzt:
                return {"meldung": _stand(f"{wo}: keine leere Zelle")}
            proben = []
            for name, kuerzel in gesetzt:
                s.vonhand[(name, kuerzel)] = trdf.MARKE
                if name not in proben:
                    proben.append(name)
            s._rechnung_vergessen(proben)
            antwort = self._nach_eingabe(proben, offen)
            antwort["meldung"] = _stand(
                f"{wo}: {len(gesetzt)} leere Zellen mit „{trdf.MARKE}"
                f"“ gefuellt")
            return antwort
        return self._sicher(arbeit)

    def _nach_eingabe(self, proben, offen) -> dict:
        s = self._s
        antwort = s.zeilen_fuer(proben)
        antwort["aenderungen"] = len(s.aenderungen())
        antwort["bloecke"] = {probe: self._blockdaten(probe)
                              for probe in offen or () if probe in proben}
        return antwort

    # ------------------------------------------------------ Eingefuegte UM
    def um_text(self) -> dict:
        return {"text": self._s.um_text}

    def um_einfuegen(self, text: str) -> dict:
        """Die Liste aus der Probenvorbereitung - danach wird mit ihr gerechnet."""
        def arbeit():
            s = self._s
            s.um_text = str(text or "")
            ok, satz, art = s.um_lesen(s.um_text)
            if not ok:
                return {"ok": False, "stand": _stand(satz, art)}
            voll = self._voll(_stand(satz, art))
            voll["ok"] = True
            return voll
        return self._sicher(arbeit)

    def um_leeren(self) -> dict:
        def arbeit():
            s = self._s
            s.um_text = ""
            s.um_vergessen()
            return self._voll(_stand("Die eingefuegte UM ist geleert - "
                                     "gerechnet wird mit den Rohwerten aus "
                                     "dem LIMS."))
        return self._sicher(arbeit)

    # ------------------------------------------------------- Block und Bild
    def _blockdaten(self, probe: str) -> dict:
        s = self._s
        namen = [name for _lnr, name in s.proben]
        daten = trdfblock.blockdaten(probe, s.rohsatz(probe),
                                     s.gerechnet(probe))
        daten["stelle"] = namen.index(probe) if probe in namen else -1
        daten["anzahl"] = len(namen)
        return daten

    def block(self, probe: str) -> dict:
        """Der Bodenblock einer Probe - Lagen, Schaufel und Zahlen."""
        def arbeit():
            if probe not in {name for _l, name in self._s.proben}:
                raise Hinweis(f"Die Probe {probe} gehoert nicht zur "
                                   f"Serie.")
            return self._blockdaten(str(probe))
        return self._sicher(arbeit)

    def nachbar(self, probe: str, richtung: int) -> dict:
        """Pfeil rauf und runter im Block - eine Probe weiter."""
        def arbeit():
            namen = [name for _lnr, name in self._s.proben]
            if probe not in namen:
                return {"probe": None}
            stelle = namen.index(probe) + int(richtung)
            if not 0 <= stelle < len(namen):
                return {"probe": None}
            return {"probe": namen[stelle]}
        return self._sicher(arbeit)

    def bild(self) -> dict:
        """Trockenrohdichte ueber organischem Kohlenstoff - alle Proben."""
        def arbeit():
            s = self._s
            punkte = []
            for eintrag in s.geprueft():
                werte = eintrag["werte"]
                punkte.append({
                    "probe": eintrag["probe"],
                    "trdf": werte.get(trdfpruefung.TRDF),
                    "cges": werte.get(trdfpruefung.CGES),
                    "co3": werte.get(trdfpruefung.CO3),
                    "marke": "geaendert" if trdfblock.DICHTE in s.bewegt(
                        eintrag["probe"]) else None})
            daten = trdfbild.bild(punkte)
            daten["serie"] = s.seriename()
            daten["anzahl"] = len(punkte)
            return daten
        return self._sicher(arbeit)

    # ------------------------------------------------------- Export
    def _vorschau(self, art, geaendert, titel, pfad="") -> dict:
        self._s.vorschau = (art, list(geaendert), pfad)
        zurueck, nur_anhang = art == "zurueck", art == "anhang"
        nur_ergebnisse = art == "ergebnisse"
        wieder = {id(eine) for eine in (
            [] if zurueck or nur_anhang
            else trdfexport.schon_korrigiert(geaendert))}
        zeilen = trdfexport.uebersicht(geaendert, trdfpruefung.stellen_fuer)
        return {"vorschau": {
            "art": art, "titel": titel, "anzahl": len(geaendert),
            "hinweis": vorschauhinweis(geaendert, zurueck, nur_anhang,
                                       nur_ergebnisse),
            "spalten": list(trdfexport.SPALTEN),
            "zeilen": zeilen,
            "marken": ["ohne" if not eine.get("zeile")
                       else "wieder" if id(eine) in wieder else ""
                       for eine in geaendert],
            "knopf": ("Zurueckspielen" if zurueck
                      else "Angleichen" if nur_anhang or nur_ergebnisse
                      else "Sichern und schreiben")}}

    def export_vorschau(self) -> dict:
        """Was geschrieben wuerde - geschrieben wird erst nach Bestaetigung."""
        def arbeit():
            self._zugang()
            geaendert = self._s.aenderungen()
            if not geaendert:
                return {"stand": _stand("Es ist nichts von Hand geaendert - "
                                        "es gibt nichts zu schreiben.",
                                        "warn")}
            return self._vorschau("export", geaendert,
                                  "Export in das LIMS - Serie "
                                  + self._s.seriename())
        return self._sicher(arbeit)

    def anhang_vorschau(self) -> dict:
        """Den Teilprobenanhang auf den Stand der Ergebniszeile bringen."""
        def arbeit():
            self._zugang()
            geaendert = self._s.auseinander()
            if not geaendert:
                return {"stand": _stand("Ergebniszeile und Teilprobenanhang "
                                        "stimmen ueberein.")}
            return self._vorschau("anhang", geaendert,
                                  "Teilprobenanhang angleichen - Serie "
                                  + self._s.seriename())
        return self._sicher(arbeit)

    def ergebnisse_vorschau(self) -> dict:
        """Die berechneten Groessen in die Ergebniszeilen des LIMS.

        Fuer Serien, die im LIMS noch nicht gerechnet sind (dort steht
        ueberall x). Handwerte gehoeren vorher ueber den Export in das
        LIMS - sonst stuenden dort Ergebnisse aus Rohwerten, die es dort
        nicht gibt.
        """
        def arbeit():
            self._zugang()
            s = self._s
            if s.vonhand:
                return {"stand": _stand(
                    "Es gibt von Hand geaenderte Rohwerte - die zuerst ueber "
                    "\u201eExport\u201c schreiben, dann die Ergebnisse "
                    "angleichen.", "warn")}
            geaendert = s.ergebnis_angleichung()
            if not geaendert:
                return {"stand": _stand("Die Ergebnisse im LIMS stimmen mit "
                                        "den berechneten ueberein.")}
            return self._vorschau("ergebnisse", geaendert,
                                  "Ergebnisse angleichen - Serie "
                                  + s.seriename())
        return self._sicher(arbeit)

    def backup_waehlen(self) -> dict:
        """Load backup: eine Sicherung waehlen und zeigen, was sie zurueckbringt."""
        ordner = self._ordner(trdfexport.ORDNER)
        pfad = self._datei_waehlen(ordner)
        if not pfad:
            return {"abgebrochen": True}
        return self.backup_lesen(pfad)

    def backup_lesen(self, pfad: str) -> dict:
        def arbeit():
            self._zugang()
            try:
                zeilen = trdfexport.gesichertes_lesen(pfad)
            except (trdfexport.Einlesefehler, OSError) as fehler:
                return {"stand": _stand(str(fehler), "fehler")}
            geaendert = trdfexport.zurueck(zeilen)
            if not geaendert:
                return {"stand": _stand("In dieser Sicherung steht keine "
                                        "Zeile.", "warn")}
            return self._vorschau("zurueck", geaendert,
                                  "Load backup - " + os.path.basename(pfad),
                                  pfad)
        return self._sicher(arbeit)

    def sicherungen(self) -> dict:
        """Die Sicherungen im Ordner - neueste zuerst (fuer den Browser)."""
        ordner = self._ordner(trdfexport.ORDNER)
        try:
            namen = [name for name in os.listdir(ordner)
                     if name.lower().endswith(".csv")
                     and not name.startswith(("Bericht ", "Aenderungen "))]
        except OSError:
            namen = []
        namen.sort(key=lambda n: os.path.getmtime(os.path.join(ordner, n)),
                   reverse=True)
        return {"ordner": ordner,
                "dateien": [os.path.join(ordner, n) for n in namen]}

    def _datei_waehlen(self, ordner: str) -> str:
        if self._fenster is None:
            return ""
        import webview
        try:
            gewaehlt = self._fenster.create_file_dialog(
                webview.FileDialog.OPEN if hasattr(webview, "FileDialog")
                else webview.OPEN_DIALOG,
                directory=ordner if os.path.isdir(ordner) else self._s._ordner,
                file_types=("Sicherung (*.csv)", "Alle Dateien (*.*)"))
        except Exception:                                # noqa: BLE001
            traceback.print_exc()
            return ""
        if not gewaehlt:
            return ""
        return gewaehlt[0] if isinstance(gewaehlt, (list, tuple)) \
            else str(gewaehlt)

    def vorschau_abbrechen(self) -> dict:
        with self._s.sperre:
            self._s.vorschau = None
        return {"ok": True}

    def vorschau_ausfuehren(self) -> dict:
        """Der gruene Knopf der Uebersicht: sichern und schreiben."""
        def arbeit():
            vorgemerkt, self._s.vorschau = self._s.vorschau, None
            if not vorgemerkt:
                raise Hinweis("Es liegt keine Uebersicht vor.")
            art, geaendert, pfad = vorgemerkt
            zugang = self._zugang()
            if art in ("export", "ergebnisse"):
                return self._exportieren(zugang, geaendert)
            if art == "zurueck":
                return self._zurueckspielen(zugang, geaendert, pfad)
            return self._anhang_schreiben(zugang, geaendert)
        return self._sicher(arbeit)

    def _schreiben(self, zugang, *args, **kwargs):
        if self._demo:
            return demo_schreiben(*args, **kwargs)
        return lims_db.trdf_exportieren(zugang, *args, **kwargs)

    def _exportieren(self, zugang, geaendert) -> dict:
        s = self._s
        serie = s.seriename()
        ordner = self._ordner(trdfexport.ORDNER)
        sicherung = trdfexport.backup_schreiben(ordner, serie, geaendert,
                                                dt.datetime.now())
        if not sicherung:
            return {"meldung": {
                "titel": "Es wurde nichts geschrieben", "art": "fehler",
                "text": f"Ohne Sicherung wird nichts geschrieben. Der Ordner "
                        f"„{ordner}“ liess sich nicht anlegen."}}
        bericht = self._schreiben(
            zugang, trdfexport.saetze(geaendert),
            trdfexport.hinweise(geaendert, serie),
            trdfexport.anhangsaetze(geaendert),
            trdfexport.anhanghinweise(geaendert, serie), leeren=True)
        fehlend = {(satz["prob_id"], satz["pm_id"], satz["pm_ver"])
                   for satz in bericht["ohne_zeile"]}
        gescheitert = s._gescheitert(geaendert, bericht)
        angekommen = [eine for eine in geaendert
                      if eine.get("zeile") and eine not in gescheitert and
                      (eine["zeile"]["prob_id"], eine["zeile"]["pm_id"],
                       eine["zeile"]["pm_ver"]) not in fehlend]
        if angekommen:
            benutzer = getattr(zugang, "benutzer", "")
            trdfexport.protokollieren(ordner, benutzer,
                                      trdfexport.saetze(angekommen),
                                      trdfexport.hinweise(angekommen, serie))
            trdfexport.protokollieren(
                ordner, benutzer, trdfexport.anhangsaetze(angekommen),
                trdfexport.anhanghinweise(angekommen, serie),
                sql=lims_db.trdf_anhang_sql())
        for eine in angekommen:
            s._uebernommen(eine)
        s._rechnung_vergessen()
        s.letzter_export = {"serie": serie, "zeitpunkt": dt.datetime.now(),
                            "sicherung": sicherung,
                            "aenderungen": list(angekommen),
                            "offen": list(gescheitert)}
        s.export_nach_zurueck = ""
        getroffen = bericht["geschrieben"]
        am_anhang = bericht.get("anhang_geschrieben", 0)
        zahl_fehlend = (len(bericht["ohne_zeile"])
                        + len(bericht.get("anhang_ohne_zeile", ())))
        satz = (f"{getroffen} Ergebniszeilen und {am_anhang} Rohwerte am "
                f"Anhang geschrieben  |  Sicherung: {sicherung}")
        if zahl_fehlend:
            satz += f"  |  {zahl_fehlend} Zeilen im LIMS nicht gefunden"
        if gescheitert:
            satz += (f"  |  {len(gescheitert)} Werte stehen danach noch "
                     f"wie vorher da")
        stand = _stand(satz, "fehler" if gescheitert
                       else "warn" if zahl_fehlend else "text")
        if gescheitert:
            namen = ", ".join(f"{eine.get('probe')} {eine['kuerzel']}"
                              for eine in gescheitert[:12])
            if len(gescheitert) > 12:
                namen += f" und {len(gescheitert) - 12} weitere"
            meldung = {
                "titel": "Update fehlgeschlagen", "art": "fehler",
                "text": f"{len(gescheitert)} Werte stehen in der Datenbank "
                        "nach dem Schreiben immer noch so da wie vorher.\n\n"
                        "Die Anweisung lief durch, die Zeilen gibt es, und "
                        "geschrieben wurde trotzdem nichts - das deutet auf "
                        "einen Ausloeser, ein fehlendes Recht oder eine "
                        "Sicht statt einer Tabelle hin. Der Stand im Fenster "
                        "bleibt deshalb unveraendert.\n\n"
                        f"Betroffen: {namen}\n\nWas geschickt wurde, steht "
                        f"im Korrekturlog neben der Sicherung:\n{sicherung}"}
        elif not getroffen and not am_anhang:
            meldung = {
                "titel": "Es wurde nichts geschrieben", "art": "warn",
                "text": "Keine einzige Zeile wurde getroffen. Die Anweisung "
                        "lief fehlerfrei durch, hat aber im LIMS nichts "
                        "gefunden - der Schluessel aus PROB_ID, PM_ID, "
                        "PM_VER, UM_ID und GEGR_ID passt dort auf keine "
                        "Zeile.\n\nWas geschickt wurde, steht im "
                        "Aenderungsprotokoll und im Korrekturlog neben der "
                        f"Sicherung:\n{sicherung}"}
        else:
            text = (f"{getroffen} Ergebniszeilen und {am_anhang} Rohwerte am "
                    f"Teilprobenanhang wurden geschrieben und festgeschrieben "
                    f"(COMMIT).\n\nDie Sicherung liegt unter:\n{sicherung}")
            if zahl_fehlend:
                text += (f"\n\n{zahl_fehlend} Zeilen wurden im LIMS nicht "
                         "gefunden und deshalb nicht geschrieben.")
            meldung = {"titel": "In das LIMS geschrieben",
                       "art": "warn" if zahl_fehlend else "info",
                       "text": text}
        voll = self._voll(stand)
        voll["meldung"] = meldung
        voll["reiter"] = "bericht"
        return voll

    def _neu_holen(self) -> dict:
        """Nach dem Zurueckspielen gilt der Stand im Fenster nicht mehr."""
        s = self._s
        name, um, kuerzel = s.seriename(), s.um_id, s.um_kuerzel
        if um is None:
            return self._voll()
        geholt = (demo_abruf(name, um, kuerzel) if self._demo
                  else s.abruf_holen(self._zugang(), name, um, kuerzel))
        text = s.um_text
        voll = self._uebernehmen(name, geholt)
        if text.strip():
            s.um_text = text
            s.um_lesen(text)
            voll = self._voll(voll["stand"])
        return voll

    def _zurueckspielen(self, zugang, geaendert, pfad) -> dict:
        name = os.path.basename(pfad)
        saetze = trdfexport.zuruecksaetze(geaendert)
        anhang = trdfexport.zurueck_anhangsaetze(geaendert)
        hinweise = trdfexport.zurueckhinweise(geaendert, name)
        bericht = self._schreiben(zugang, saetze, hinweise, anhang, hinweise,
                                  zurueck=True)
        ordner = self._ordner(trdfexport.ORDNER)
        benutzer = getattr(zugang, "benutzer", "")
        trdfexport.protokollieren(ordner, benutzer, saetze, hinweise,
                                  sql=lims_db.trdf_zurueck_sql())
        trdfexport.protokollieren(ordner, benutzer, anhang, hinweise,
                                  sql=lims_db.trdf_anhang_zurueck_sql())
        satz = (f"{bericht['geschrieben']} Ergebniszeilen und "
                f"{bericht.get('anhang_geschrieben', 0)} Rohwerte am "
                f"Anhang zurueckgespielt aus {name}")
        fehlt = (len(bericht["ohne_zeile"])
                 + len(bericht.get("anhang_ohne_zeile", ())))
        if fehlt:
            satz += f"  |  {fehlt} Zeilen nicht gefunden"
        # Der Exportbericht stimmt jetzt nicht mehr: was er zeigt, ist
        # gerade zurueckgenommen worden.
        self._s.letzter_export = None
        self._s.export_nach_zurueck = name
        voll = self._neu_holen()
        voll["stand"] = _stand(satz, "warn" if fehlt else "text")
        voll["meldung"] = {"titel": "Sicherung zurueckgespielt",
                           "art": "warn" if fehlt else "info", "text": satz}
        return voll

    def _anhang_schreiben(self, zugang, geaendert) -> dict:
        serie = self._s.seriename()
        ordner = self._ordner(trdfexport.ORDNER)
        sicherung = trdfexport.backup_schreiben(ordner, serie, geaendert,
                                                dt.datetime.now())
        if not sicherung:
            return {"meldung": {
                "titel": "Es wurde nichts geschrieben", "art": "fehler",
                "text": f"Ohne Sicherung wird nichts geschrieben. Der Ordner "
                        f"„{ordner}“ liess sich nicht anlegen."}}
        anhang = trdfexport.anhangsaetze(geaendert)
        hinweise = trdfexport.anhanghinweise(geaendert, serie)
        # Die Ergebniszeile ist sonst die Vorlage und bleibt - ausser dort,
        # wo ein grosses X steht: das wird ein kleines.
        in_zeile = [eine for eine in geaendert if eine.get("auch_zeile")]
        saetze = trdfexport.saetze(in_zeile)
        zeilenhinweise = trdfexport.hinweise(in_zeile, serie)
        bericht = self._schreiben(zugang, saetze, zeilenhinweise, anhang,
                                  hinweise)
        benutzer = getattr(zugang, "benutzer", "")
        trdfexport.protokollieren(ordner, benutzer, anhang, hinweise,
                                  sql=lims_db.trdf_anhang_sql())
        if saetze:
            trdfexport.protokollieren(ordner, benutzer, saetze,
                                      zeilenhinweise)
        getroffen = bericht.get("anhang_geschrieben", 0)
        fehlt = (len(bericht.get("anhang_ohne_zeile", ()))
                 + len(bericht.get("ohne_zeile", ())))
        offen = (len(bericht.get("anhang_nicht_uebernommen", ()))
                 + len(bericht.get("nicht_uebernommen", ())))
        satz = (f"{getroffen} Rohwerte am Teilprobenanhang angeglichen  |  "
                f"Sicherung: {sicherung}")
        if saetze:
            satz += (f"  |  {bericht.get('geschrieben', 0)} x in der "
                     f"Ergebniszeile klein geschrieben")
        if fehlt:
            satz += f"  |  {fehlt} Zeilen nicht gefunden"
        if offen:
            satz += f"  |  {offen} stehen danach noch wie vorher da"
        art = "fehler" if offen else "warn" if fehlt else "info"
        voll = self._neu_holen()
        voll["stand"] = _stand(satz, "fehler" if offen
                               else "warn" if fehlt else "text")
        voll["meldung"] = {"titel": "Teilprobenanhang angeglichen",
                           "art": art, "text": satz}
        return voll

    # ------------------------------------------------------ Exportbericht
    def _bericht(self) -> dict:
        s = self._s
        stand = s.letzter_export
        if not stand:
            text = (f"Der letzte Export wurde aus {s.export_nach_zurueck} "
                    f"zurueckgespielt." if s.export_nach_zurueck
                    else "Es wurde in dieser Sitzung noch nichts "
                         "geschrieben.")
            return {"stand": _stand(text, "warn" if s.export_nach_zurueck
                                    else "leer"),
                    "spalten": list(trdfexport.BERICHT_KOPF), "zeilen": []}
        spalten, zeilen = trdfexport.bericht(stand["aenderungen"],
                                             trdfpruefung.stellen_fuer)
        marken = {}
        for eine in stand["aenderungen"]:
            if eine.get("art") == trdfexport.ROHWERT:
                marken.setdefault(str(eine.get("probe") or ""), {})[
                    eine["kuerzel"]] = "geaendert"
        satz = (f"{stand['serie']}  |  {stand['zeitpunkt']:%d.%m.%Y %H:%M}  "
                f"|  {len(zeilen)} Proben, {len(stand['aenderungen'])} Werte  "
                f"|  Sicherung: {stand['sicherung']}")
        if stand["offen"]:
            satz += (f"  |  {len(stand['offen'])} Werte stehen danach noch "
                     f"wie vorher da")
        return {"stand": _stand(satz, "fehler" if stand["offen"] else "text"),
                "spalten": spalten,
                "zeilen": [{"id": kennung, "w": klar(werte),
                            "m": marken.get(kennung, {})}
                           for kennung, werte in zeilen]}

    # ------------------------------------------------------------- CSV
    def csv(self, blatt: str) -> dict:
        """Ein Blatt als CSV ablegen und oeffnen."""
        def arbeit():
            s = self._s
            serie = s.seriename()
            if blatt == "bericht":
                stand = s.letzter_export
                if not stand or not stand["aenderungen"]:
                    return {"stand": _stand("Es wurde in dieser Sitzung "
                                            "noch nichts geschrieben.",
                                            "warn")}
                ordner = self._ordner(trdfexport.ORDNER)
                pfad = trdfexport.bericht_schreiben(
                    ordner, stand["serie"], stand["aenderungen"],
                    stand["zeitpunkt"])
                anzahl = len(stand["aenderungen"])
            elif not s.proben:
                return {"stand": _stand("Es ist keine Serie abgerufen.",
                                        "warn")}
            elif blatt == "roh":
                ordner = self._ordner(trdfrohpruefung.ORDNER)
                inhalt = s.rohblatt()
                pfad = trdfrohpruefung.schreiben(ordner, serie, inhalt,
                                                 s.rohliste)
                anzahl = len(inhalt)
            elif blatt == "aenderungen":
                geaendert = s.aenderungen()
                if not geaendert:
                    return {"stand": _stand("Es ist nichts von Hand "
                                            "geaendert.", "warn")}
                ordner = self._ordner(trdfexport.ORDNER)
                pfad = trdfexport.blatt_schreiben(ordner, serie, geaendert,
                                                  dt.datetime.now())
                anzahl = len(geaendert)
            elif blatt == "ergebnis":
                ordner = self._ordner(trdfpruefung.ORDNER)
                pfad, anzahl = self._ergebnisblatt(ordner, serie)
            elif blatt == "pruefung":
                ordner = self._ordner(trdfpruefung.ORDNER)
                inhalt = s.geprueft()
                pfad = trdfpruefung.schreiben(ordner, serie, inhalt,
                                              s.um_kuerzel)
                anzahl = len(inhalt)
            else:
                raise ValueError(f"Kein Blatt {blatt!r}")
            if not pfad:
                return {"stand": _stand(
                    f"Die Datei liess sich nicht schreiben. Steht der Ordner "
                    f"„{ordner}“ zur Verfuegung?", "fehler")}
            trdfpruefung.oeffnen(pfad)
            return {"pfad": pfad,
                    "stand": _stand(f"{anzahl} Zeilen  |  {pfad}")}
        return self._sicher(arbeit)

    def _ergebnisblatt(self, ordner: str, serie: str) -> tuple:
        """Die berechneten Groessen, wie sie dastehen - mit den Koepfen."""
        s = self._s
        tafel = s.ergebnistafel()
        kopf = [" ".join(teil for teil in str(
            tafel["koepfe"].get(name, name)).split("\n") if teil.strip())
            or name for name in tafel["spalten"]]
        zeilen = [[str(klar(werte.get(name, "")) or "").strip()
                   for name in tafel["spalten"]]
                  for _probe, werte in tafel["zeilen"]]
        name = "".join(zeichen for zeichen in serie
                       if zeichen.isalnum() or zeichen in " _-.") or "Serie"
        pfad = os.path.join(ordner, f"Ergebnisse {name}.csv")
        inhalt = lims_db.csv_bloecke([(
            f"Berechnete Groessen - Serie {serie} - {s.um_kuerzel}",
            kopf, zeilen)])
        try:
            os.makedirs(ordner, exist_ok=True)
            with open(pfad, "wb") as datei:
                datei.write(inhalt)
        except OSError:
            return "", 0
        return pfad, len(zeilen)

    # ----------------------------------------------------------- Legende
    def legende(self, blatt: str) -> dict:
        """Was die Spalten einer Tabelle bedeuten - und wie sie stehen."""
        def arbeit():
            s = self._s
            titel = BLAETTER[blatt]
            quellen = None
            if blatt == "roh":
                spalten = s._rohspalten()[3]
                kopf = list(trdflegende.SPALTEN_ROH)
                zeilen = trdflegende.rohlegende(spalten, s.methoden,
                                                s.beschreibungen())
            elif blatt == "ergebnis":
                spalten = s._ergebnisspalten()[4]
                kopf = list(trdflegende.SPALTEN_ERGEBNIS)
                zeilen = trdflegende.ergebnislegende(spalten, s.methoden,
                                                     s.beschreibungen())
            else:
                spalten = s._pruefspalten()[3]
                kopf = list(trdflegende.SPALTEN_ERGEBNIS)
                quellen = trdfpruefung.QUELLEN
                zeilen = trdflegende.pruefungslegende(
                    spalten, quellen, s.methoden, s.beschreibungen())
            reihenfolge, fest = s.spaltenordnung(titel)
            schluessel = {zeile[0]: trdflegende.schluessel(zeile[0], quellen)
                          for zeile in zeilen}
            bekannt = set(schluessel.values())
            return {
                "blatt": blatt, "titel": trdflegende.TITEL.format(titel),
                "hinweis": trdflegende.HINWEIS,
                "kopf": kopf, "zeilen": zeilen, "schluessel": schluessel,
                "kopfwahl": list(trdflegende.KOPFWAHL),
                "standard_fest": list(trdflegende.STANDARD_FEST),
                "ordnung": {
                    "reihenfolge": reihenfolge,
                    "fest": [k for k in fest if k in bekannt],
                    "versteckt": [k for k in s.versteckt(titel)
                                  if k in bekannt],
                    "kopfspalte": s.kopfspalte(),
                    "kopfspalten": {k: w for k, w in s.kopfspalten().items()
                                    if k in bekannt}}}
        return self._sicher(arbeit)

    def legende_speichern(self, blatt: str, texte: dict,
                          ordnung: dict) -> dict:
        def arbeit():
            fehler = self._s.spalten_ablegen(BLAETTER[blatt], dict(texte or {}),
                                             dict(ordnung or {}))
            if fehler:
                return {"stand": _stand(trdflegende.NICHT_GESPEICHERT.format(
                    fehler), "fehler")}
            voll = self._voll(_stand(trdflegende.GESPEICHERT.format(
                len([t for t in (texte or {}).values() if str(t).strip()]))))
            return voll
        return self._sicher(arbeit)

    def spalte_verschieben(self, blatt: str, von: str, nach: str) -> dict:
        """Eine Spalte am Kopf greifen und auf eine andere ziehen.

        Dieselbe Ordnung wie in der Legende - gespeichert in den
        Einstellungen. Feste Spalten bleiben, wo sie sind; ein Paar
        ("TRDF LIMS", "TRDF ber.") wandert zusammen.
        """
        def arbeit():
            s = self._s
            titel = BLAETTER[blatt]
            quellen = trdfpruefung.QUELLEN if blatt == "pruefung" else None
            alle = (s._rohspalten()[3] if blatt == "roh"
                    else s._ergebnisspalten()[4] if blatt == "ergebnis"
                    else s._pruefspalten()[3])
            reihenfolge = []
            for name in alle:
                kuerzel = trdflegende.schluessel(name, quellen)
                if kuerzel not in reihenfolge:
                    reihenfolge.append(kuerzel)
            quelle = trdflegende.schluessel(von, quellen)
            ziel = trdflegende.schluessel(nach, quellen)
            _vorher, fest = s.spaltenordnung(titel)
            if quelle == ziel or quelle not in reihenfolge \
                    or ziel not in reihenfolge:
                return {"stand": None}
            if quelle in fest or ziel in fest:
                return {"stand": _stand("Feste Spalten bleiben, wo sie sind "
                                        "- unter \u201eInfo\u201c laesst "
                                        "sich das \u201eja\u201c bei "
                                        "\u201eFest\u201c wegnehmen.",
                                        "warn")}
            hinunter = reihenfolge.index(quelle) < reihenfolge.index(ziel)
            reihenfolge.remove(quelle)
            stelle = reihenfolge.index(ziel) + (1 if hinunter else 0)
            reihenfolge.insert(stelle, quelle)
            fehler = s.spalten_ablegen(titel, {}, {
                "reihenfolge": reihenfolge,
                "fest": [k for k in fest if k in reihenfolge],
                "versteckt": [k for k in s.versteckt(titel)
                              if k in reihenfolge],
                "kopfspalte": s.kopfspalte(),
                "kopfspalten": {k: w for k, w in s.kopfspalten().items()
                                if k in reihenfolge}})
            if fehler:
                return {"stand": _stand(trdflegende.NICHT_GESPEICHERT.format(
                    fehler), "fehler")}
            return {"tafeln": s.tafeln(),
                    "stand": _stand(f"Spalte {von} verschoben - gespeichert.")}
        return self._sicher(arbeit)

    # ------------------------------------------------------- Einstellungen
    def einstellung(self, name: str, wert) -> dict:
        """Merkt sich eine Wahl der Seite - nur was die Seite selbst fuehrt."""
        if name not in ("trdf_berechnete", "trdf_auto_angleichen"):
            return {"fehler": f"Unbekannte Einstellung {name}"}

        def arbeit():
            konfig = self._s._einstellungen()
            konfig.set(name, wert)
            konfig.speichern()
            return {"ok": True}
        return self._sicher(arbeit)

    def ordner_oeffnen(self, welcher: str = "backup") -> dict:
        ordner = self._ordner(trdfexport.ORDNER if welcher == "backup"
                              else trdfpruefung.ORDNER)
        os.makedirs(ordner, exist_ok=True)
        trdfpruefung.oeffnen(ordner)
        return {"pfad": ordner}


# --------------------------------------------------------------------------
# Eine erfundene Serie - fuer die Entwicklung und die Bilder der Anleitung
# --------------------------------------------------------------------------
DEMO_SERIEN = ["2026B051", "2026B048", "2026H012"]


class DemoZugang:
    def __init__(self, benutzer="demo"):
        self.benutzer = benutzer


def demo_methoden(serie: str) -> list:
    return [(42, "TRDF3.2"), (207, "TRDF3.2")] if serie == "2026B051" \
        else [(42, "TRDF3.2")]


def demo_abruf(serie, um_id, kuerzel, proben=None) -> dict:
    """Die Beispielserie der Pruefungen - auf Wunsch vervielfacht.

    TRDF_DEMO_PROBEN gibt die Zahl der Proben vor (Vorgabe 24);
    TRDF_DEMO_UNGERECHNET=1 laesst die berechneten Groessen im "LIMS"
    leer, wie bei einer Serie, die dort noch nicht gerechnet ist. Die
    ersten vier sind die Proben aus test_trdf, so wie sie sind - mit
    ihren Befunden. Die uebrigen wiederholen sie mit leicht
    verschobenen Messwerten, und das LIMS hat fuer sie richtig
    gerechnet: so sieht eine Serie aus, in der einiges stimmt und
    weniges nicht.
    """
    # Ueber importlib: PyInstaller soll die Pruefungen nicht in die exe
    # packen - der Demo-Betrieb laeuft nur aus dem Quelltext.
    vorlage = importlib.import_module("test_trdfreiter")
    anzahl = int(proben or os.environ.get("TRDF_DEMO_PROBEN", "24"))
    grund = vorlage.geholt(aufschluss=[
        {"prob_id": p, "para_id": 31, "kuerzel": "ATNULL", "mw": c}
        for p, c in ((1, "48"), (5, "22"), (11, "9,5"), (33, "3,1"))] + [
        {"prob_id": p, "para_id": 33, "kuerzel": "ATNULLCO3", "mw": "0"}
        for p in (1, 5, 11, 33)])
    nach_pm = {(m["pm_id"], m["pm_ver"]): m for m in grund["methoden"]}
    formeln = {m["formelkuerzel"]: m["formel"] for m in grund["methoden"]
               if str(m["formel"] or "").strip()}
    folge = trdf.reihenfolge(formeln)
    fest = (trdfrohpruefung.VARIANTE, trdfrohpruefung.TIEFENSTUFE,
            trdfrohpruefung.FAKTOR)
    vier = (1, 5, 11, 33)
    ergebnisse, anhang, wgh, aufschluss = [], [], {}, []
    for nummer in range(anzahl):
        alt, neu = vier[nummer % 4], nummer + 1
        probe = f"26B{neu:04d}"
        faktor = decimal.Decimal(1) + decimal.Decimal((nummer // 4) % 7) / 40
        zeilen, roh = [], {}
        for zeile in grund["ergebnisse"]:
            if zeile["prob_id"] != alt:
                continue
            kopie = dict(zeile, prob_id=neu, probe_nr=probe, lnr=neu,
                         serie=serie)
            name = nach_pm[(zeile["pm_id"], zeile["pm_ver"])]["formelkuerzel"]
            zahl = trdf.zahl(zeile["mw_roh"])
            if nummer >= 4 and name not in formeln and name not in fest \
                    and zahl is not None:
                text = str((zahl * faktor).quantize(
                    decimal.Decimal("0.1"))).replace(".", ",")
                kopie["mw_roh"] = kopie["mw"] = text
            if name not in formeln:
                roh[name] = trdf.zahl(kopie["mw_roh"])
            zeilen.append((name, kopie))
        wgh[neu] = grund["wgh"].get(alt)
        if nummer >= 4 and os.environ.get("TRDF_DEMO_UNGERECHNET"):
            # Wie eine Serie, die im LIMS noch nicht gerechnet ist: in den
            # berechneten Groessen steht x - hier und da ein grosses X.
            for name, kopie in zeilen:
                if name in formeln:
                    kopie["mw_roh"] = kopie["mw"] = "X" if nummer % 5 == 0 \
                        else "x"
        elif nummer >= 4:
            gerechnet = trdf.rechnen(roh, formeln, trdf.zahl(wgh[neu]), folge)
            for name, kopie in zeilen:
                if name in formeln:
                    wert = gerechnet.get(name)
                    text = (format(wert.quantize(
                        decimal.Decimal("1E-12")), "f").replace(".", ",")
                            if isinstance(wert, decimal.Decimal) else "")
                    kopie["mw_roh"] = kopie["mw"] = text
        ergebnisse += [kopie for _name, kopie in zeilen]
        rohwerte = {name: kopie["mw_roh"] for name, kopie in zeilen}
        for zeile in grund["anhang"]:
            if zeile["prob_id"] == alt:
                lang = vorlage.ROHWERTE[zeile["rohw_id"] - 1]
                anhang.append(dict(zeile, prob_id=neu,
                                   mw=rohwerte.get(lang, zeile["mw"])))
        for zeile in grund["aufschluss"]:
            if zeile["prob_id"] == alt:
                aufschluss.append(dict(zeile, prob_id=neu))
    return dict(grund, um_id=um_id, kuerzel=kuerzel, ergebnisse=ergebnisse,
                anhang=anhang, wgh=wgh, aufschluss=aufschluss,
                aufschlussnachtrag=[], nachtragsfehler="")


def demo_schreiben(saetze, hinweise=None, anhang=None, anhang_hinweise=None,
                   zurueck=False, leeren=False) -> dict:
    """Schreibt nichts - und tut so, als waere alles angekommen."""
    return {"geschrieben": len(saetze), "ohne_zeile": [],
            "versucht": len(saetze),
            "anhang_geschrieben": len(anhang or []),
            "anhang_ohne_zeile": [], "nicht_uebernommen": [],
            "anhang_nicht_uebernommen": []}


# --------------------------------------------------------------------------
# Der Dienst fuer die Entwicklung: dieselbe Seite im Browser
# --------------------------------------------------------------------------
def dienst(api: Api, port: int = 8765):
    """Liefert webdist/ aus und nimmt POST /api/<Methode> entgegen.

    Nur fuer die Entwicklung und die Bilder der Anleitung: das Programm
    selbst braucht keinen Server, dort ruft die Seite ueber die Bruecke
    von pywebview.
    """
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    wurzel = ressource(WEBORDNER)

    class Bearbeiter(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=wurzel, **kwargs)

        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.split("?")[0] == "/api/bereit":
                # Woran die Seite erkennt, dass sie ueber HTTP rufen soll -
                # im Programm liefert pywebview sie aus, und dort gibt es
                # diese Adresse nicht.
                antwort = json.dumps({"dienst": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(antwort)))
                self.end_headers()
                self.wfile.write(antwort)
                return
            super().do_GET()

        def do_POST(self):
            if not self.path.startswith("/api/"):
                self.send_error(404)
                return
            name = self.path[len("/api/"):]
            laenge = int(self.headers.get("Content-Length") or 0)
            argumente = json.loads(self.rfile.read(laenge) or b"[]")
            methode = getattr(api, name, None)
            if name.startswith("_") or not callable(methode):
                self.send_error(404)
                return
            antwort = json.dumps(methode(*argumente)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(antwort)))
            self.end_headers()
            self.wfile.write(antwort)

    server = ThreadingHTTPServer(("127.0.0.1", port), Bearbeiter)
    print(f"TRDF-Pruefmodul: http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()


# --------------------------------------------------------------------------
# Start
# --------------------------------------------------------------------------
def selbsttest() -> int:
    code, zeilen = lims_db.selbsttest(oberflaeche=("webview",))
    seite = ressource(WEBORDNER, "index.html")
    if code == 0:
        if os.path.isfile(seite):
            zeilen.append(f"  Oberflaeche gefunden ({seite})")
        else:
            zeilen.append(f"  FEHLER: {seite} fehlt")
            code = 1
    ausgabe = "\n".join(zeilen)
    try:
        print(ausgabe, flush=True)
    except Exception:                                    # noqa: BLE001
        pass            # bei --windowed gibt es kein stdout
    try:
        ziel = os.path.join(config.get_runtime_dir(), "selbsttest.log")
        with open(ziel, "w", encoding="utf-8") as datei:
            datei.write(ausgabe + "\n")
    except OSError:
        pass
    return code


def _protokoll_einrichten():
    """pywebview schreibt, was beim Fenster geschieht, in eine Datei.

    Ohne Konsole waere es sonst verloren - und gerade beim ersten Start
    an einem neuen Arbeitsplatz ist es die einzige Auskunft.
    """
    import logging
    try:
        ziel = os.path.join(config.get_runtime_dir(), "trdfweb.log")
        handler = logging.FileHandler(ziel, mode="w", encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    for name in ("pywebview", "trdfweb"):
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)


def _net_fehler_merken():
    """Eine unbehandelte .NET-Ausnahme beendet das Programm ohne Python.

    Sie kommt aus dem Fenster (WinForms/WebView2) und laeuft an Python
    vorbei - der Prozess ist einfach weg. Hier wird sie vorher noch in
    startfehler.txt geschrieben.
    """
    if sys.platform != "win32":
        return
    try:
        __import__("clr")      # laedt die .NET-Laufzeit (pythonnet)
        from System import AppDomain, UnhandledExceptionEventHandler

        def merken(_sender, args):
            try:
                ziel = os.path.join(config.get_runtime_dir(),
                                    "startfehler.txt")
                with open(ziel, "w", encoding="utf-8") as datei:
                    datei.write(str(args.ExceptionObject))
            except OSError:
                pass

        AppDomain.CurrentDomain.UnhandledException += \
            UnhandledExceptionEventHandler(merken)
    except Exception:                                    # noqa: BLE001
        traceback.print_exc()


def fenster_starten(api: Api):
    import webview

    _protokoll_einrichten()
    _net_fehler_merken()

    seite = ressource(WEBORDNER, "index.html")
    fenster = webview.create_window(
        f"{APP_TITEL} - NW-FVA", url=seite, js_api=api, width=1440,
        height=900, min_size=(1000, 640), background_color="#f4f6fa",
        text_select=True, maximized=True)
    api._fenster_setzen(fenster)
    # Unter Windows Edge WebView2. Das Fenstersymbol muss dort eine .ico
    # sein - WinForms (System.Drawing.Icon) nimmt kein PNG und beendet das
    # Programm sonst mit einer unbehandelten .NET-Ausnahme.
    windows = sys.platform == "win32"
    webview.start(gui="edgechromium" if windows else None,
                  debug=bool(os.environ.get("TRDF_WEB_DEBUG")),
                  icon=ressource(SYMBOL_WINDOWS if windows else SYMBOL))


def main(argumente=None) -> int:
    argumente = list(sys.argv[1:] if argumente is None else argumente)
    if "--selbsttest" in argumente:
        return selbsttest()
    demo = "--demo" in argumente
    if demo:
        os.environ.setdefault("TRDF_PRUEFMODUL_NICHT_OEFFNEN", "1")
    api = Api(demo=demo)
    if "--dienst" in argumente:
        stelle = argumente.index("--dienst")
        port = int(argumente[stelle + 1]) if len(argumente) > stelle + 1 \
            and argumente[stelle + 1].isdigit() else 8765
        dienst(api, port)
        return 0
    try:
        fenster_starten(api)
    except Exception as fehler:                          # noqa: BLE001
        # Ohne Konsole waere der Grund sonst unsichtbar: er geht in eine
        # Datei neben der exe.
        try:
            ziel = os.path.join(config.get_runtime_dir(), "startfehler.txt")
            with open(ziel, "w", encoding="utf-8") as datei:
                datei.write(f"{fehler}\n\n{traceback.format_exc()}")
        except OSError:
            pass
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
