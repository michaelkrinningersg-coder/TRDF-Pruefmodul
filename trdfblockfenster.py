"""TRDF-Pruefmodul - das Fenster zum Bodenblock (Tk).

Die Lagen und Zahlen rechnet trdfblock.py; hier wird nur gezeichnet.
"""

from __future__ import annotations

import tkinter as tk

from trdf import D
from widgets import Style

from trdfblock import (  # noqa: F401
    BESCHRIFTUNG,
    BESCHRIFTUNG_SCHAUFEL,
    DICHTE,
    FARBEN,
    FEINBODEN,
    GROB_FEINST,
    GROB_GROSS,
    GROB_KLEIN,
    GROB_MITTEL,
    SCHRIFTFARBE,
    SKELETT,
    VARIANTE,
    VORRAT,
    _zahl,
    anteil_von,
    aus_werten,
    dichtetext,
    gruppen,
    prozent,
    schaufel,
    vorratstext)


# --------------------------------------------------------------------------
# Das Fenster
# --------------------------------------------------------------------------
BREITE = 140          # der Block der Probe
BREITE_SCHAUFEL = 120
HOEHE = 300

# Die hundert Prozent stehen als gestrichelte Linie da, ohne Beschriftung:
# neben dem Block braeuchte sie einen leeren Streifen, im Block liegt sie
# im Weg. Was ueber der Linie steht, sagt die Legende darunter.
RAND = 20

# Ab dieser Hoehe traegt eine Lage ihre Zahl; darunter stuende sie ueber
# den Rand hinaus.
BESCHRIFTBAR = 15


class Blockfenster(tk.Toplevel):
    """Ein kleines Fenster mit dem Block einer Probe.

    Links die Probe, wie sie im Boden stand; in der Mitte die Zahlen,
    aus denen sie gerechnet ist; rechts die Schaufelprobe, wie sie im
    Labor auf der Waage lag. Je Probe eines - ein zweiter Klick auf
    dieselbe Probe frischt es auf, statt ein zweites zu oeffnen.
    """

    def __init__(self, eltern, probe: str, lagen, dichte=None, variante=None,
                 skelett=None, vorrat=None, roh=None, gerechnet=None,
                 bei_wechsel=None):
        super().__init__(eltern)
        self.title(f"Bodenblock {probe}")
        self.configure(bg=Style.BG)
        self.resizable(False, False)
        # Ueber dem Hauptfenster bleiben: wer in der Tabelle einen
        # Rohwert aendert, will den Block dabei sehen und nicht erst
        # wieder hervorholen. `transient` haelt ihn oben, ohne ihn
        # ueber andere Programme zu legen.
        try:
            self.transient(eltern.winfo_toplevel())
        except tk.TclError:
            pass
        self.probe = probe
        self.lagen = list(lagen)
        # Pfeil rauf und runter blaettert durch die Probenliste: der
        # Block ist zum Vergleichen da, und dafuer muss man die Nachbarn
        # sehen koennen, ohne jedes Mal in die Tabelle zurueckzugehen.
        self._bei_wechsel = bei_wechsel
        for taste, richtung in (("<Up>", -1), ("<Down>", 1),
                                ("<Prior>", -1), ("<Next>", 1)):
            self.bind(taste, lambda ereignis, wohin=richtung:
                      self._wechseln(wohin))
        self.focus_set()

        kopfzeile = tk.Frame(self, bg=Style.BG)
        kopfzeile.pack(fill="x", padx=RAND, pady=(14, 2))
        self.kopf = tk.Label(kopfzeile, text="", bg=Style.BG, fg=Style.TEXT,
                             font=Style.font(11, "bold"), anchor="w")
        self.kopf.pack(side="left")
        tk.Label(self, text="Beide Bilder von unten nach oben: Feinboden, "
                            "gewogener Grobboden, geschaetzter Grobboden. "
                            "Links die Probe im Boden, rechts die "
                            "Schaufelprobe nach Volumen; ueber der "
                            "gestrichelten Linie steht, was groesser als 63 "
                            "mm war, und der hellere Streifen in der Lage 2 "
                            "bis 63 mm ist die Fraktion 2 bis 6,3 mm.",
                 bg=Style.BG, fg=Style.MUTED, font=Style.font(9), anchor="w",
                 justify="left", wraplength=640).pack(
            fill="x", padx=RAND, pady=(0, 10))

        mitte = tk.Frame(self, bg=Style.BG)
        mitte.pack(fill="both", expand=True, padx=RAND)

        links = tk.Frame(mitte, bg=Style.BG)
        links.pack(side="left", anchor="n")
        tk.Label(links, text="Probe", bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").pack(fill="x")
        self.bild = tk.Canvas(links, width=BREITE, height=HOEHE,
                              bg=Style.CARD, highlightthickness=1,
                              highlightbackground=Style.BORDER)
        self.bild.pack(anchor="w")

        daneben = tk.Frame(mitte, bg=Style.BG)
        daneben.pack(side="left", fill="y", padx=(18, 0), anchor="n")
        tk.Label(daneben, text="Trockenrohdichte Feinboden", bg=Style.BG,
                 fg=Style.MUTED, font=Style.font(9), anchor="w").pack(
            fill="x")
        self.feld_dichte = tk.Label(daneben, text="", bg=Style.BG,
                                    fg=Style.TEXT, font=Style.font(16, "bold"),
                                    anchor="w")
        self.feld_dichte.pack(fill="x")
        paar = tk.Frame(daneben, bg=Style.BG)
        paar.pack(fill="x", pady=(8, 0))
        self.feld_vorrat = self._kennzahl(paar, "Feinbodenvorrat")
        self.feld_skelett = self._kennzahl(paar, "Skelettanteil")
        self.zahlen = tk.Frame(daneben, bg=Style.BG)
        self.zahlen.pack(fill="x", pady=(10, 0))

        # Die Schaufelprobe steht nur da, wenn sie gewogen wurde - ohne
        # Masse (0 oder x) faellt die ganze Spalte weg.
        self.rechts = rechts = tk.Frame(mitte, bg=Style.BG)
        rechts.pack(side="left", anchor="n", padx=(18, 0))
        tk.Label(rechts, text="Schaufelprobe", bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").pack(fill="x")
        self.schaufelbild = tk.Canvas(rechts, width=BREITE_SCHAUFEL,
                                      height=HOEHE, bg=Style.CARD,
                                      highlightthickness=1,
                                      highlightbackground=Style.BORDER)
        self.schaufelbild.pack(anchor="w")

        # Die Legenden unter beiden Bildern, nebeneinander: je Lage eine
        # Zeile, die Prozente rechtsbuendig untereinander.
        legenden = tk.Frame(self, bg=Style.BG)
        legenden.pack(fill="x", padx=RAND, pady=(10, 0))
        self.legende = tk.Frame(legenden, bg=Style.BG)
        self.legende.pack(side="left", anchor="n")
        self.schaufellegende = tk.Frame(legenden, bg=Style.BG)
        self.schaufellegende.pack(side="left", anchor="n", padx=(28, 0))

        tk.Frame(self, bg=Style.BG, height=RAND).pack(fill="x")
        self._stellen(lagen, dichte, variante, skelett, vorrat, roh or {},
                      gerechnet or {})
        self.bind("<Escape>", lambda e: self.destroy())

    @staticmethod
    def _kennzahl(eltern, beschriftung: str) -> tk.Label:
        spalte = tk.Frame(eltern, bg=Style.BG)
        spalte.pack(side="left", padx=(0, 18))
        tk.Label(spalte, text=beschriftung, bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").pack(fill="x")
        feld = tk.Label(spalte, text="", bg=Style.BG, fg=Style.TEXT,
                        font=Style.font(12, "bold"), anchor="w")
        feld.pack(fill="x")
        return feld

    # ------------------------------------------------------------ Stellen
    def _stellen(self, lagen, dichte, variante, skelett, vorrat, roh,
                 gerechnet):
        """Setzt alle Zahlen und zeichnet beide Bloecke neu."""
        self.lagen = list(lagen)
        self.roh, self.gerechnet = dict(roh), dict(gerechnet)
        self.schaufelteile = schaufel(self.roh, self.gerechnet)
        self.kopf.config(text=f"Probe {self.probe}" + (
            f"  ·  Variante {variante}" if variante is not None else ""))
        self.feld_dichte.config(text=dichtetext(dichte))
        self.feld_vorrat.config(text=vorratstext(vorrat))
        self.feld_skelett.config(text=prozent(skelett))
        self._zeichnen()
        self._schaufel_zeichnen()
        self._zahlen_zeigen()
        self._legende_zeichnen()

    def _wechseln(self, richtung: int):
        """Eine Probe weiter - die Liste fuehrt der Aufrufer."""
        if self._bei_wechsel is not None:
            self._bei_wechsel(self, richtung)
        return "break"

    def uebernehmen(self, probe: str, roh: dict, gerechnet: dict):
        """Dasselbe Fenster, eine andere Probe."""
        self.probe = probe
        self.title(f"Bodenblock {probe}")
        self.neu_zeichnen(roh, gerechnet)

    def neu_zeichnen(self, roh: dict, gerechnet: dict):
        """Nimmt einen neuen Stand an - dasselbe Fenster, andere Zahlen."""
        art = _zahl(roh.get(VARIANTE))
        self._stellen(aus_werten(roh, gerechnet), gerechnet.get(DICHTE),
                      int(art) if art is not None else None,
                      gerechnet.get(SKELETT), gerechnet.get(VORRAT),
                      roh, gerechnet)

    # ----------------------------------------------------------- Zeichnen
    def _lage(self, flaeche, marke, unten, hoehe, breite, text=None):
        """Eine Lage auf die Flaeche legen - mit ihrer Zahl, wenn Platz ist."""
        oben = unten - hoehe
        flaeche.create_rectangle(0, oben, breite, unten,
                                 fill=FARBEN[marke], width=0)
        if hoehe >= BESCHRIFTBAR and text:
            flaeche.create_text(breite / 2, (oben + unten) / 2, text=text,
                                fill=SCHRIFTFARBE[marke],
                                font=Style.font(9, "bold"))
        return oben

    def _zeichnen(self):
        """Die Lagen der Probe von unten nach oben."""
        self.bild.delete("all")
        if not self.lagen:
            self.bild.create_text(BREITE / 2, HOEHE / 2,
                                  text="kein Skelettanteil\nberechnet",
                                  fill=Style.MUTED, font=Style.font(9),
                                  justify="center")
            return
        unten = float(HOEHE)
        for marke, anteil in self.lagen:
            unten = self._lage(self.bild, marke, unten,
                               float(anteil) / 100.0 * HOEHE, BREITE,
                               prozent(anteil))

    def _schaufel_zeichnen(self):
        """Die Schaufelprobe - Bezug unten, was ueber 63 mm war obendrauf."""
        self.schaufelbild.delete("all")
        teile = self.schaufelteile
        if not teile:
            self.rechts.pack_forget()
            return
        if not self.rechts.winfo_manager():
            self.rechts.pack(side="left", anchor="n", padx=(18, 0))
        bezug = teile["bezug"]
        gesamt = bezug + teile.get(GROB_GROSS, D(0))
        skala = float(HOEHE) / float(gesamt) if gesamt > 0 else 0.0
        unten = float(HOEHE)
        if teile.get(FEINBODEN):
            unten = self._lage(self.schaufelbild, FEINBODEN, unten,
                               float(teile[FEINBODEN]) * skala,
                               BREITE_SCHAUFEL,
                               anteil_von(teile[FEINBODEN], bezug))
        if teile.get(GROB_KLEIN):
            unten = self._grobboden(teile, bezug, skala, unten)
        if teile.get(GROB_GROSS):
            self._lage(self.schaufelbild, GROB_GROSS, unten,
                       float(teile[GROB_GROSS]) * skala, BREITE_SCHAUFEL,
                       anteil_von(teile[GROB_GROSS], bezug))
            self._hundert(unten)

    def _hundert(self, hoehe: float):
        """Die Linie der hundert Prozent - zuletzt, also ueber den Lagen.

        Nur die Linie: eine Beschriftung braucht entweder Platz neben
        dem Block oder liegt in ihm im Weg. Dass darueber der Grobboden
        ueber 63 mm steht, sagt die Legende darunter.
        """
        self.schaufelbild.create_line(0, hoehe, BREITE_SCHAUFEL, hoehe,
                                      fill="#111827", dash=(4, 3))

    def _grobboden(self, teile: dict, bezug, skala: float, unten: float):
        """Die Lage 2 bis 63 mm - innen geteilt, aussen eine Zahl.

        Steckt eine Fraktion 2 bis 6,3 mm darin, wird sie als eigener
        heller Streifen gezeichnet, bekommt aber keine eigene Zahl: im
        Block steht der Anteil der ganzen Lage, und was davon die feine
        Fraktion ist, sagt die Legende darunter. Zwei Zahlen
        uebereinander liest man sonst als zwei Lagen.
        """
        hoehe = float(teile[GROB_KLEIN]) * skala
        oben = unten - hoehe
        feinst = teile.get(GROB_FEINST)
        if feinst:
            self._lage(self.schaufelbild, GROB_FEINST, unten,
                       float(feinst) * skala, BREITE_SCHAUFEL)
            self._lage(self.schaufelbild, GROB_MITTEL,
                       unten - float(feinst) * skala,
                       float(teile[GROB_MITTEL]) * skala, BREITE_SCHAUFEL)
        else:
            self._lage(self.schaufelbild, GROB_KLEIN, unten, hoehe,
                       BREITE_SCHAUFEL)
        if hoehe >= BESCHRIFTBAR:
            self.schaufelbild.create_text(
                BREITE_SCHAUFEL / 2, (oben + unten) / 2,
                text=anteil_von(teile[GROB_KLEIN], bezug),
                fill=SCHRIFTFARBE[GROB_KLEIN], font=Style.font(9, "bold"))
        return oben

    # ------------------------------------------------------------ Zahlen
    def _zahlen_zeigen(self):
        """Die Rohwerte, nach Geraet geordnet."""
        for kind in self.zahlen.winfo_children():
            kind.destroy()
        for name, zeilen in gruppen(self.roh):
            tk.Label(self.zahlen, text=name, bg=Style.BG, fg=Style.MUTED,
                     font=Style.font(9, "bold"), anchor="w").pack(
                fill="x", pady=(6, 0))
            for beschriftung, wert in zeilen:
                zeile = tk.Frame(self.zahlen, bg=Style.BG)
                zeile.pack(fill="x")
                tk.Label(zeile, text=beschriftung, bg=Style.BG,
                         fg=Style.MUTED, font=Style.font(9), anchor="w",
                         width=22).pack(side="left")
                tk.Label(zeile, text=wert, bg=Style.BG, fg=Style.TEXT,
                         font=Style.font(9), anchor="w").pack(side="left")

    def _legende_zeichnen(self):
        """Was welche Farbe bedeutet - nur die Lagen, die vorkommen."""
        for rahmen in (self.legende, self.schaufellegende):
            for kind in rahmen.winfo_children():
                kind.destroy()
        if self.lagen:
            self._legendenkopf(self.legende, "Probe")
        for marke, anteil in self.lagen:
            self._legendenzeile(self.legende, marke, BESCHRIFTUNG[marke],
                                prozent(anteil))
        teile = self.schaufelteile
        if not teile:
            return
        self._legendenkopf(self.schaufellegende, "Schaufelprobe")
        # Unter dem Bild stehen beide Haelften der Lage 2 bis 63 mm:
        # im Block traegt sie eine Zahl, hier ist Platz fuer die
        # Aufteilung, um die es beim Sieben ging.
        for marke in (FEINBODEN, GROB_KLEIN, GROB_MITTEL, GROB_FEINST,
                      GROB_GROSS):
            if not teile.get(marke):
                continue
            self._legendenzeile(
                self.schaufellegende, marke, BESCHRIFTUNG_SCHAUFEL[marke],
                anteil_von(teile[marke], teile["bezug"]))

    @staticmethod
    def _legendenkopf(rahmen, titel):
        tk.Label(rahmen, text=titel, bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))

    @staticmethod
    def _legendenzeile(rahmen, marke, text, wert):
        """Eine Zeile: Farbe, Name, Prozent - der Prozent rechtsbuendig."""
        zeile = rahmen.grid_size()[1]
        tk.Frame(rahmen, bg=FARBEN[marke], width=12, height=12).grid(
            row=zeile, column=0, sticky="w", pady=1)
        tk.Label(rahmen, text=text, bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(9), anchor="w").grid(
            row=zeile, column=1, sticky="w", padx=(6, 12))
        tk.Label(rahmen, text=wert, bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(9, "bold"), anchor="e").grid(
            row=zeile, column=2, sticky="e")


def zeigen(eltern, probe: str, roh: dict, gerechnet: dict,
           bei_wechsel=None) -> Blockfenster:
    """Oeffnet den Block zu einer Probe."""
    art = _zahl(roh.get(VARIANTE))
    return Blockfenster(eltern, probe, aus_werten(roh, gerechnet),
                        dichte=gerechnet.get(DICHTE),
                        variante=int(art) if art is not None else None,
                        skelett=gerechnet.get(SKELETT),
                        vorrat=gerechnet.get(VORRAT),
                        roh=roh, gerechnet=gerechnet,
                        bei_wechsel=bei_wechsel)
