"""TRDF-Pruefmodul - das Fenster „Info“ zu einer Tabelle (Tk).

Was in der Legende steht, baut trdflegende.py; hier wird nur gezeigt.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import eingaberaster
from widgets import RoundedButton, Style

from trdflegende import (  # noqa: F401
    BESCHREIBUNG,
    BLEIBT,
    BREITEN,
    FEST,
    GESPEICHERT,
    HINWEIS,
    JA,
    KOPFHINWEIS,
    KOPFSPALTE,
    KOPFWAHL,
    NEIN,
    NICHT_GESPEICHERT,
    TITEL,
    ZEIGEN,
    naechste_kopfwahl,
)


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
