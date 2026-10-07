"""
TRDF-Pruefmodul - die Seite "TRDF Pruefung"
===========================================

Hier laeuft zusammen, was trdf.py rechnet und was trdfpruefung.py davon
haelt: eine Serie waehlen, ihre TRDF-Untersuchungsmethoden abfragen,
eine davon waehlen - und daneben steht, was das LIMS daraus gemacht hat
und ob das Ergebnis in einem Boden vorkommen kann.

Ausgeloest aus dem Reiter "TRDF Pruefung" von LabControl (TestLims) als
Einzelauswertung: eine Serie, eine Untersuchungsmethode. Nicht
mitgekommen sind die Profilansichten (Profil-CSV, Plot und Tiefenstufe,
Profilfenster mit dem Plotvergleich) und der Weg ueber einzelne
Probennummern. Geblieben sind die drei Tabellen, das Aendern der
Rohwerte, der Bodenblock beim Klick auf die Probe und der Rueckweg in
das LIMS.

Der Weg zur Serie
-----------------
Erst die Serie, dann "Abfragen": gefragt wird, welche
Untersuchungsmethoden die Serie fuehrt, und davon bleiben alle, deren
Kuerzel "TRDF" traegt (ohne die ausgeschlossenen, siehe
lims_db.AUSGESCHLOSSENE_METHODEN). Fuehrt die Serie genau eine, wird sie
gleich geholt; fuehrt sie mehrere, wird im Feld daneben gewaehlt - und
mit der Wahl geholt.

Zwei Wege zu den Rohwerten
--------------------------
Die Untersuchungsmethode aus der Probenvorbereitung laesst sich
einfuegen ("UM einfuegen") - damit prueft man, ob die Uebernahme ins
LIMS stimmt. Sonst kommen die Rohwerte aus dem Teilprobenanhang, also
aus der Stelle, aus der das LIMS selbst rechnet. Welcher Weg gilt,
ergibt sich von selbst: ist eine UM eingefuegt, gilt sie. Von Hand
geaenderte Werte stechen in beiden Faellen.

Drei Unterreiter, und warum es drei sind
-----------------------------------------
Ein Rohwert kann an drei Stellen anders aussehen: im eingefuegten Text,
in der Ergebnistabelle des LIMS, und in dem, was das LIMS daraus
gerechnet hat. "Rohwerte" und "Ergebnisse" stellen das nebeneinander -
sonst sieht man zwar, *dass* etwas nicht stimmt, aber nicht, wo es
angefangen hat. "Pruefung" fragt etwas anderes: die Rechnung kann
stimmen und der Wert trotzdem nicht in den Boden passen.

Von Hand aendern
----------------
Die Rohwerte lassen sich ueberschreiben. Damit laesst sich die Frage
beantworten, die beim Pruefen als naechstes kommt: "und wenn hier 1,8
staende - kaeme dann das heraus, was gebucht ist?" Gerechnet und
geprueft wird sofort neu. In das LIMS geht eine Aenderung erst ueber den
Knopf "Export" - nach einer bestaetigten Uebersicht und
einer Sicherung (trdfexport.py).
"""

from __future__ import annotations

import datetime as dt
import os
import textwrap
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import eingaberaster
import lims_db
import trdf
import trdfbild
import trdfblock
import trdfexport
import trdflegende
import trdfpruefung
import trdfrohpruefung
import trdfserie
# Was hier nicht mehr selbst gebraucht wird, steht trotzdem unter
# trdfreiter bereit - so heisst es seit LabControl.
from trdfmodell import (AUSEINANDER, BEWERTUNGSSPALTE, BLATT_ERGEBNIS,  # noqa: F401
                        BLATT_PRUEFUNG, BLATT_ROH, BREITEN, NACHGETRAGEN,
                        PROBENART_ZU_ID, PROBENARTEN, QUELLE_LIMS, QUELLE_TEXT,
                        QUELLEN, ROHWERTE_UNVOLLSTAENDIG, STELLEN, STELLEN_WGH,
                        TrdfModell, _mit_nachtrag, _nachtragsteil,
                        _ohne_anhang, _ohne_aufschluss, _probenkennungen,
                        methodentexte, probenart, vorschauhinweis,
                        zahltext)
from widgets import RoundedButton, Style, ToolTip

# Was im Exportbericht steht, solange nichts geschrieben wurde. Der
# Reiter ist dann kein Fehler, sondern nur noch leer.
BERICHT_LEER = "Es wurde in dieser Sitzung noch nichts geschrieben."

# Was im Methodenfeld steht, solange keine Serie abgefragt ist.
METHODE_OFFEN = "erst abfragen"

# Schrift und Zeilenluft der Tabellen auf der Seite. Groesser als in
# LabControl: hier wird getippt, und eine Zelle, die man trifft, ohne
# hinzusehen, ist die halbe Arbeit.
SCHRIFT = 11
ZEILENLUFT = 3

# Wie die berechneten Groessen ueber den Rohwerten stehen: eingeklappt
# oder offen. Von Haus aus eingeklappt - dann gehoert das ganze Fenster
# den Rohwerten.
BERECHNETE_AN = "an"
BERECHNETE_AUS = "aus"
BERECHNETE_EIN_TEXT = "\u25b8 Berechnete Groessen"
EINFUEGEN_TEXT = "UM einfuegen ..."
BERECHNETE_AUS_TEXT = "\u25be Berechnete Groessen"

# Die Grossansicht der Rohwerte: eine Zeile doppelt so hoch wie im
# Reiter. Die Haelfte davon kommt aus der groesseren Schrift, die
# andere aus Luft ueber und unter der Zeile - waere die Schrift allein
# doppelt so gross, passten nur noch halb so viele Spalten
# nebeneinander, und darum geht es hier gerade.
GROSS_SCHRIFT = 13
GROSS_LUFT = 5
GROSS_ZEILEN = 18


def erklaerung(*saetze) -> str:
    """Ein Erklaertext fuer das i - in Zeilen, die ein Hinweisfenster traegt."""
    return "\n".join(textwrap.fill(" ".join(saetze), 72).splitlines())


# Was im Rohwertraster wie in Excel geht - steht im i der Rohwerte.
TASTEN = ("Tab / Pfeile / Eingabe   Zelle wechseln\n"
          "Strg+C / Strg+V          kopieren / Block aus Excel einfuegen\n"
          "Strg+D                   Wert der Zelle darueber uebernehmen\n"
          "Strg+Shift+D             Wert nach unten kopieren (bis zum Ende)\n"
          "Strg+L                   Wert nach unten, nur in leere Zellen\n"
          "Strg+I                   nach unten hochzaehlen (+1 je Zeile)\n"
          "Strg+E                   leere Zellen der Probe mit x fuellen\n"
          "Strg+Shift+E             leere Zellen der Spalte mit x fuellen\n"
          "Variante (_TRDV):  x = alles x,  0 = Zeile leeren,\n"
          "                   1-7 = nicht benoetigte Felder bekommen x")

PRUEF_ERKLAERUNG = erklaerung(
    "Die bodenphysikalischen Werte, nach Probe-Nr. "
    "sortiert. Geprueft wird, was das Pruefmodul gerechnet "
    "hat: der Skelettanteil gegen 0 und 100 Prozent und "
    "gegen den geschaetzten Grobboden, der Abstand "
    "zwischen gemessenem und geschaetztem Skelettanteil, "
    "der Feinbodenvorrat gegen null und die "
    "Trockenrohdichte gegen den Sollbereich ihrer "
    "Kohlenstoffklasse. Dazu, was erst im Vergleich mit "
    "der Serie auffaellt: ein Wiederfindungsgrad, der "
    "nicht zum organischen Kohlenstoff passt, und "
    "Rohwerte, die im LIMS an zwei Stellen verschieden "
    "stehen. Was auffaellt, steht in der Bewertung.")


class Infozeichen(tk.Label):
    """Ein kleines "i": der Erklaertext steht dahinter und nicht im Weg.

    Die Seite traegt sonst ueber jeder Tabelle einen Absatz, den man
    einmal liest und danach nur noch ueberspringt. Hier kommt er, wenn
    die Maus auf dem i steht - oder sofort bei einem Klick darauf.
    """

    def __init__(self, eltern, text: str, dezent=False):
        # Dezent: grau statt blau - fuer das, was man einmal nachschlaegt
        # und dann kann, wie die Tastenkuerzel.
        super().__init__(eltern, text="i",
                         fg="#64748b" if dezent else "#ffffff",
                         bg="#e2e8f0" if dezent else Style.ACCENT,
                         font=(Style.FONT, 8, "bold italic"), width=2,
                         cursor="question_arrow", padx=0, pady=0)
        self._hinweis = ToolTip(self, text)
        if dezent:
            self._hinweis.font = ("Consolas", 9)
        self.bind("<Button-1>", lambda e: self._sofort())

    @property
    def text(self) -> str:
        return self._hinweis.text

    def setzen(self, text: str):
        self._hinweis.text = text

    def _sofort(self):
        self._hinweis.hidetip()
        self._hinweis.showtip()


class TrdfSeite(tk.Frame, TrdfModell):
    """Die ganze Seite - Auswahl, Einfuegefeld und die drei Tabellen."""

    # Verdeckte Tabellen werden erst gezeichnet, wenn ihr Reiter
    # aufgeht (siehe `_zeichnen`). Die Pruefungen der Seite schalten das
    # ab: sie lesen die Tabellen, ohne den Reiter zu wechseln.
    sofort_zeichnen = False

    def __init__(self, eltern, zugang_holen, im_hintergrund, ordner=None,
                 konfig=None):
        super().__init__(eltern, bg=Style.BG, padx=8, pady=6)
        self._zugang_holen = zugang_holen
        self._im_hintergrund = im_hintergrund
        # Die Einstellungen: dort stehen die Beschreibungen der Legende
        # und die zuletzt gewaehlte Serie. Ohne uebergebene wird eine
        # eigene geoeffnet - im Betrieb gibt das Hauptfenster seine mit.
        TrdfModell.__init__(self, ordner, konfig)
        self._aufbauen()

    def seriename(self) -> str:
        """Die Serie steht hier im Feld - nicht im Modell."""
        variable = getattr(self, "v_serie", None)
        return variable.get().strip() if variable is not None else ""

    # ------------------------------------------------------------- Aufbau
    def _aufbauen(self):
        # Der Kopf ist so knapp wie moeglich: drei Zeilen, damit den
        # Tabellen darunter der Platz bleibt.
        kopf = tk.Frame(self, bg=Style.CARD, highlightbackground=Style.BORDER,
                        highlightthickness=1, padx=12, pady=6)
        kopf.pack(fill="x")
        titel = tk.Frame(kopf, bg=Style.CARD)
        titel.pack(fill="x", pady=(0, 4))
        tk.Label(titel, text="Die Rechnung des LIMS nachrechnen und pruefen",
                 bg=Style.CARD, fg=Style.TEXT, font=Style.font(11, "bold"),
                 anchor="w").pack(side="left")
        self.info_kopf = Infozeichen(titel, erklaerung(
            "Das LIMS bildet aus den Rohwerten einer TRDF-Serie ein Dutzend "
            "Groessen. Das Pruefmodul rechnet sie mit denselben Formeln noch "
            "einmal, stellt beides nebeneinander und prueft, ob die "
            "bodenphysikalischen Werte zueinander passen.",
            "Erst die Serie waehlen, dann \u201eAbfragen\u201c: angeboten "
            "werden alle Untersuchungsmethoden der Serie, deren Kuerzel TRDF "
            "traegt.",
            "Rohwerte lassen sich von Hand aendern - dann wird sofort neu "
            "gerechnet; in das LIMS geht eine Aenderung erst ueber "
            "\u201eExport\u201c."))
        self.info_kopf.pack(side="left", padx=(8, 0))
        wahl = tk.Frame(kopf, bg=Style.CARD)
        wahl.pack(fill="x")
        tk.Label(wahl, text="Serie", bg=Style.CARD, fg=Style.MUTED,
                 font=Style.font(9)).grid(row=0, column=0, sticky="w",
                                          padx=(0, 6))
        self.v_serie = tk.StringVar(value=self._gemerkt("serie"))
        self.feld_serie = ttk.Combobox(wahl, textvariable=self.v_serie,
                                       width=14)
        self.feld_serie.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.feld_serie.bind("<Return>", lambda e: self._abfragen())
        self.feld_serie.bind("<<ComboboxSelected>>",
                             lambda e: self._serie_gewechselt())
        self.v_serie.trace_add("write", lambda *_: self._serie_getippt())
        ToolTip(self.feld_serie,
                "Die Serien aus dem Fahrplan, die eine TRDF-Methode "
                "fuehren.\nEine andere laesst sich eintippen - sie muss "
                "nicht im Fahrplan stehen.")
        self.knopf_abfragen = RoundedButton(
            wahl, text="Abfragen", width=120, height=30, bg="#15803d",
            command=self._abfragen)
        self.knopf_abfragen.grid(row=0, column=2, sticky="w", padx=(0, 16))
        ToolTip(self.knopf_abfragen,
                "Fragt, welche Untersuchungsmethoden diese Serie fuehrt,\n"
                "und bietet alle an, deren Kuerzel TRDF traegt. Ist es\n"
                "genau eine, wird die Serie gleich geholt.")
        tk.Label(wahl, text="Untersuchungsmethode", bg=Style.CARD,
                 fg=Style.MUTED, font=Style.font(9)).grid(
            row=0, column=3, sticky="w", padx=(0, 6))
        self.v_methode = tk.StringVar()
        self.feld_methode = ttk.Combobox(
            wahl, textvariable=self.v_methode, width=18, state="disabled",
            values=[])
        self.feld_methode.grid(row=0, column=4, sticky="w", padx=(0, 12))
        self.v_methode.set(METHODE_OFFEN)
        self.feld_methode.bind("<<ComboboxSelected>>",
                               lambda e: self._methode_gewaehlt())
        ToolTip(self.feld_methode,
                "Die TRDF-Methoden der abgefragten Serie. Die Wahl holt\n"
                "die Serie unter dieser Methode.\n\n"
                "Das Haus fuehrt dieselbe Methode je Probenart einmal:\n"
                "TRDF3.2 fuer den Boden und TRDF3.2 fuer den Humus sind\n"
                "zwei UM_ID. Wo zwei dasselbe Kuerzel tragen, steht die\n"
                "UM_ID dabei.")
        # Was gerade geladen ist - Methode und Probenart - steht in der
        # Titelzeile; in der Auswahlzeile ist dafuer kein Platz.
        self.auskunft = tk.Label(titel, text="", bg=Style.CARD,
                                 fg=Style.MUTED, font=Style.font(9),
                                 anchor="w")
        self.auskunft.pack(side="left", padx=(16, 0))
        wahl.grid_columnconfigure(5, weight=1)
        self.knopf_export = RoundedButton(
            titel, text="Export", width=120, height=28,
            bg="#15803d", command=self._lims_schreiben)
        self.knopf_export.pack(side="right")
        self.knopf_zurueck = RoundedButton(
            titel, text="Load backup", width=140, height=28,
            bg="#6b7268", command=self._zurueckspielen)
        self.knopf_zurueck.pack(side="right", padx=(0, 10))
        ToolTip(self.knopf_zurueck,
                "Liest eine Datei aus dem Ordner „trdf_backup“ und stellt\n"
                "den Stand wieder her, der vor der Korrektur im LIMS\n"
                "stand - Ergebniszeile und Teilprobenanhang.")
        ToolTip(self.knopf_export,
                "Export in das LIMS: schreibt die von Hand geaenderten\n"
                "und die vorgemerkten Werte und die Groessen,\n"
                "die sich dadurch verschoben haben, in das LIMS zurueck.\n"
                "Vorher zeigt eine Uebersicht Zeile fuer Zeile, was alt und\n"
                "was neu waere; der alte Stand geht in eine Sicherung.")

        # Die Liste aus der Probenvorbereitung ist eine Option und hat ihr
        # eigenes Fenster - so bekommt sie den ganzen Platz und nimmt der
        # Seite keinen weg.
        # Woher die Rohwerte kommen, ergibt sich von selbst: ist eine UM
        # eingefuegt, gilt sie, sonst das LIMS. Hier steht nur, was gilt.
        self.quellanzeige = tk.Label(wahl, text="", bg=Style.CARD,
                                     fg=Style.MUTED, font=Style.font(9),
                                     anchor="e")
        self.quellanzeige.grid(row=0, column=7, sticky="e")
        ToolTip(self.quellanzeige,
                "Woher die Rohwerte kommen, mit denen gerechnet wird.\n"
                "Ist eine Untersuchungsmethode eingefuegt (\u201eUM einfuegen\u201c),\n"
                "gilt sie; sonst die Rohwerte des LIMS.\n"
                "\u201eLeeren\u201c im Einfuegefenster schaltet zurueck\n"
                "auf das LIMS.\n"
                "Von Hand geaenderte Werte stechen immer.")
        self.knopf_einfuegen = RoundedButton(
            wahl, text=EINFUEGEN_TEXT, width=170, height=28,
            bg="#334155", command=self.einfuegen_oeffnen)
        self.knopf_einfuegen.grid(row=0, column=6, sticky="e", padx=(0, 8))
        ToolTip(self.knopf_einfuegen,
                "Optional: die Untersuchungsmethode aus der\n"
                "Probenvorbereitung einfuegen\n"
                "(dort \u201eaktueller Block\u201c -> kopieren). Oeffnet ein\n"
                "eigenes Fenster. Nach \u201eUebernehmen\u201c wird mit dieser\n"
                "Liste gerechnet; Werte, die im LIMS noch fehlen, werden\n"
                "fuer den Export vorgemerkt.")

        # Die Statuszeile steht immer da - sie sagt, was gerade geschieht.
        self.stand = tk.Label(kopf, text="", bg=Style.CARD, fg=Style.MUTED,
                              font=Style.font(9), anchor="w", justify="left",
                              wraplength=1300)
        self.stand.pack(fill="x", pady=(4, 0))

        self.reiter = ttk.Notebook(self)
        self.reiter.pack(fill="both", expand=True, pady=(6, 0))
        # Was in einem verdeckten Reiter neu zu zeichnen waere, wartet,
        # bis er aufgeht: Tabelle -> Auftrag.
        self._veraltet = {}
        self.reiter.bind("<<NotebookTabChanged>>",
                         lambda e: self._nachziehen())
        self._rohwerte_reiter()
        self._ergebnis_reiter()
        self._pruef_reiter()
        self._bericht_reiter()
        self._quelle_zeigen()
        if self._gemerkt("trdf_berechnete") == BERECHNETE_AN:
            self._berechnete_umschalten(merken=False)
        self.serienliste_laden()

    def _rohwerte_reiter(self):
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Rohwerte ")
        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Rohwertblatt CSV", width=150,
                      height=28, bg="#334155",
                      command=self._rohblatt_speichern).pack(side="left")
        RoundedButton(leiste, text="Aenderungen CSV", width=150,
                      height=28, bg="#334155",
                      command=self._aenderungen_speichern).pack(
            side="left", padx=(8, 0))
        # Wie im Pruefblatt: aus ist das Blatt ueber die ganze Serie, an
        # der Arbeitsvorrat dessen, der die Befunde abarbeitet.
        self.v_nur_rohbefunde = tk.BooleanVar(value=False)
        self.schalter_rohbefunde = ttk.Checkbutton(
            leiste, variable=self.v_nur_rohbefunde,
            text="nur Eintraege mit Bewertung",
            command=self._rohwerte_zeigen)
        self.schalter_rohbefunde.pack(side="left", padx=(14, 0))
        ToolTip(self.schalter_rohbefunde,
                "Zeigt nur die Proben, zu deren Rohwerten etwas zu\n"
                "sagen ist. Gerechnet und geschrieben wird weiter\n"
                "ueber die ganze Serie, und das Rohwertblatt als CSV\n"
                "bleibt vollstaendig. Auch das grosse Fenster zeigt\n"
                "dann nur diese Proben.")
        self._infoknopf(leiste, self._rohlegende_zeigen)
        gross = RoundedButton(leiste, text="Maximieren", width=120,
                              height=28, bg="#1d4ed8",
                              command=self._gross_zeigen)
        gross.pack(side="left", padx=(8, 0))
        ToolTip(gross,
                "Dieselbe Tabelle in einem eigenen, grossen Fenster:\n"
                "doppelte Zeilenhoehe, wenig drumherum. Alles geht\n"
                "dort wie hier - Tabulator, Pfeile, Einfuegen aus\n"
                "Excel, Klick auf die Probennummer. Was dort steht,\n"
                "steht sofort auch hier.")
        knopf = RoundedButton(leiste, text="Anhang angleichen", width=170,
                              height=28, bg="#7c5e10",
                              command=self._anhang_angleichen)
        knopf.pack(side="left", padx=(8, 0))
        ToolTip(knopf,
                "Schreibt den Wert der Ergebniszeile in den\n"
                "Teilprobenanhang - fuer die Rohwerte, die im LIMS\n"
                "an den beiden Stellen verschieden stehen.\n"
                "Auch dieser Weg geht ueber eine bestaetigte\n"
                "Uebersicht und nach einer Sicherung.")
        self.info_roh = Infozeichen(leiste, erklaerung(
            "Was aus der gewaehlten Quelle kommt, daneben was in "
            "der Ergebnistabelle des LIMS steht. "
            "Eine Zelle laesst sich anklicken und ueberschreiben; "
            "Tab geht in der Zeile weiter, die Pfeile in alle "
            "Richtungen, Eingabe eine Zeile tiefer. Aus Excel "
            "kopierte Werte lassen sich in die obere Zelle "
            "einfuegen - sie laufen von dort nach unten und "
            "nach rechts weiter und ueberschreiben, was dort "
            "steht. Rechts steht, "
            "was an den Rohwerten auffaellt: was der Variante "
            "fehlt, was ausserhalb seines Bereichs liegt und was "
            "nicht zueinander passt."))
        self.info_roh.pack(side="left", padx=(10, 0))
        self.info_tasten = Infozeichen(leiste, "Tastenkuerzel\n\n" + TASTEN,
                                       dezent=True)
        self.info_tasten.pack(side="left", padx=(4, 0))
        self.rohstand = tk.Label(leiste, text="", bg=Style.BG, fg=Style.MUTED,
                                 font=Style.font(9), anchor="w")
        self.rohstand.pack(side="left", padx=(14, 0))

        # Oben die berechneten Groessen, unten die Rohwerte - zwei
        # getrennte Tabellen, die Grenze dazwischen laesst sich ziehen.
        # Oben ist von Haus aus zugeklappt: dann gehoert das Fenster
        # den Rohwerten.
        self.knopf_berechnete = RoundedButton(
            leiste, text=BERECHNETE_EIN_TEXT, width=200, height=28,
            bg="#334155", command=self._berechnete_umschalten)
        self.knopf_berechnete.pack(side="left", padx=(8, 0),
                                   before=self.info_roh)
        ToolTip(self.knopf_berechnete,
                "Zeigt ueber den Rohwerten die berechneten Groessen -\n"
                "dieselbe Tabelle wie im Reiter \u201eErgebnisse\u201c. Wer\n"
                "unten einen Rohwert aendert, sieht oben dieselbe Probe:\n"
                "die Zeile ist unterlegt, was sich bewegt hat, steht rot.\n"
                "Die Grenze zwischen beiden laesst sich ziehen.")
        self.rohteilung = ttk.PanedWindow(seite, orient="vertical")
        self.rohteilung.pack(fill="both", expand=True)
        self.berechnet_rahmen = tk.Frame(self.rohteilung, bg=Style.BG)
        obenkopf = tk.Frame(self.berechnet_rahmen, bg=Style.BG)
        obenkopf.pack(fill="x", pady=(0, 2))
        tk.Label(obenkopf, text="Berechnete Groessen", bg=Style.BG,
                 fg=Style.TEXT, font=Style.font(9, "bold"),
                 anchor="w").pack(side="left")
        Infozeichen(obenkopf, erklaerung(
            "Je Groesse zwei Spalten: gebucht im LIMS und gerechnet "
            "(ber.). Rot: durch die Handeingabe bewegt - und die Probe, in "
            "der von Hand geaendert wurde. Unterlegt ist die Zeile, in der "
            "unten gerade getippt wird.")).pack(side="left", padx=(8, 0))
        RoundedButton(obenkopf, text="Blatt als CSV", width=140, height=24,
                      bg="#334155",
                      command=self._ergebnisblatt_speichern).pack(
            side="left", padx=(12, 0))
        self.berechnet_oben = eingaberaster.Eingaberaster(
            self.berechnet_rahmen, hoehe=8, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.berechnet_oben.pack(fill="both", expand=True, pady=(0, 6))
        rohrahmen = tk.Frame(self.rohteilung, bg=Style.BG)
        self.rohtabelle = eingaberaster.Eingaberaster(
            rohrahmen, hoehe=16, bei_aenderung=self._von_hand_geaendert,
            bei_klick=self._block_zeigen,
            bei_block=self._block_eingefuegt,
            bei_zeile=self._arbeitszeile_setzen,
            bei_fuellen=self.leere_fuellen,
            ist_leer=self.ist_leer,
            bei_nach_unten=self._nach_unten_eingefuegt,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.rohtabelle.pack(fill="both", expand=True)
        self.rohteilung.add(rohrahmen, weight=3)
        # Dieselbe Tabelle kann zweimal dastehen - klein im Reiter und
        # gross im eigenen Fenster. Beide zeigen denselben Stand und
        # nehmen dieselben Eingaben an; was hier steht, wird ueberall
        # nachgezogen.
        self.rohtabellen = [self.rohtabelle]

    def _ergebnis_reiter(self):
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Ergebnisse ")
        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Ergebnisblatt als CSV", width=200,
                      height=28, bg="#334155",
                      command=self._ergebnisblatt_speichern).pack(side="left")
        self._infoknopf(leiste, self._ergebnislegende_zeigen)
        self.info_ergebnis = Infozeichen(leiste, erklaerung(
            "Je Groesse zwei Spalten: was das LIMS gebucht hat "
            "und was das Pruefmodul aus denselben Formeln rechnet - "
            "zusammengehalten durch den Hintergrund, der von "
            "Groesse zu Groesse wechselt. Amber heisst, dass "
            "beides auseinandergeht; rechts steht, welche "
            "Groessen es sind. Rot heisst, dass der Wert von "
            "Hand bewegt wurde."))
        self.info_ergebnis.pack(side="left", padx=(10, 0))
        self.ergebnistabelle = eingaberaster.Eingaberaster(
            seite, hoehe=16, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.ergebnistabelle.pack(fill="both", expand=True)
        # Die berechneten Groessen koennen ein zweites Mal dastehen - ueber
        # den Rohwerten. Beide werden mit demselben Stand gefuellt.
        self.ergebnistabellen = [self.ergebnistabelle]

    def _pruef_reiter(self):
        """Das Arbeitsblatt: ein Wert je Zeile und ein Urteil dazu."""
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Pruefung ")
        # Welche Spalte welchen Parameter zeigt: steht im i, nicht ueber
        # der Tabelle. Das Label bleibt als Traeger des Textes.
        self.legende = tk.Label(seite, text="", bg=Style.BG, fg=Style.MUTED,
                                font=Style.font(8), anchor="w",
                                justify="left", wraplength=980)

        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Blatt als CSV", width=150, height=28,
                      bg="#334155", command=self._blatt_speichern).pack(
            side="left")
        # Aus: das Blatt ist der Nachweis ueber die ganze Serie. An:
        # der Arbeitsvorrat dessen, der die Befunde abarbeitet.
        self.v_nur_befunde = tk.BooleanVar(value=False)
        self.schalter_befunde = ttk.Checkbutton(
            leiste, variable=self.v_nur_befunde,
            text="nur Eintraege mit Bewertung",
            command=self._pruefung_zeigen)
        self.schalter_befunde.pack(side="left", padx=(14, 0))
        ToolTip(self.schalter_befunde,
                "Zeigt nur die Proben, zu denen etwas zu sagen ist.\n"
                "Gerechnet und geschrieben wird weiter ueber die ganze\n"
                "Serie, und das Blatt als CSV bleibt vollstaendig - es\n"
                "ist der Nachweis ueber sie und nicht ueber ihre\n"
                "Auffaelligkeiten.")
        RoundedButton(leiste, text="Bild", width=110, height=28,
                      bg="#334155", command=self._bild_zeigen).pack(
            side="left", padx=(8, 0))
        self._infoknopf(leiste, self._prueflegende_zeigen)
        self.info_pruefung = Infozeichen(leiste, PRUEF_ERKLAERUNG)
        self.info_pruefung.pack(side="left", padx=(10, 0))
        self.pruefstand = tk.Label(leiste, text="", bg=Style.BG,
                                   fg=Style.MUTED, font=Style.font(9),
                                   anchor="w")
        self.pruefstand.pack(side="left", padx=(14, 0))

        self.pruefungstabelle = eingaberaster.Eingaberaster(
            seite, hoehe=16, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.pruefungstabelle.pack(fill="both", expand=True)

    def _bericht_reiter(self):
        """Was zuletzt in das LIMS gegangen ist - eine Probe je Zeile."""
        seite = tk.Frame(self.reiter, bg=Style.BG, padx=4, pady=4)
        self.reiter.add(seite, text=" Exportbericht ")
        leiste = tk.Frame(seite, bg=Style.BG)
        leiste.pack(fill="x", pady=(0, 4))
        RoundedButton(leiste, text="Bericht als CSV", width=170, height=28,
                      bg="#334155", command=self._bericht_speichern).pack(
            side="left")
        self.info_bericht = Infozeichen(leiste, erklaerung(
            "Der letzte Schreibweg in das LIMS, von der anderen "
            "Seite gesehen: eine Probe je Zeile und eine Spalte "
            "je Groesse, die sich bewegt hat - erst die "
            "Rohwerte, dann die daraus berechneten Groessen. In "
            "der Zelle steht, was vorher im LIMS stand und was "
            "jetzt dort steht. Der Bericht bleibt stehen, bis "
            "wieder geschrieben wird; als Datei - mit allen "
            "geschriebenen Stellen - liegt er neben "
            "der Sicherung im Ordner "
            f"„{trdfexport.ORDNER}“."))
        self.info_bericht.pack(side="left", padx=(10, 0))
        self.berichtstand = tk.Label(leiste, text=BERICHT_LEER, bg=Style.BG,
                                     fg=Style.MUTED, font=Style.font(9),
                                     anchor="w")
        self.berichtstand.pack(side="left", padx=(14, 0))
        self.berichtstabelle = eingaberaster.Eingaberaster(
            seite, hoehe=16, bei_klick=self._block_zeigen,
            schriftgroesse=SCHRIFT, zeilenluft=ZEILENLUFT)
        self.berichtstabelle.pack(fill="both", expand=True)

    # ------------------------------------------------------ Einfuegeliste
    def einfuegen_oeffnen(self):
        """Das Fenster fuer die Liste der Probenvorbereitung - eines."""
        vorhandenes = getattr(self, "einfuegefenster", None)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            vorhandenes.lift()
            vorhandenes.textfeld.focus_set()
            return vorhandenes
        self.einfuegefenster = Einfuegefenster(self)
        return self.einfuegefenster

    def einfuegetext(self) -> str:
        """Was in der Liste steht - aus dem Fenster, wenn es offen ist."""
        fenster = getattr(self, "einfuegefenster", None)
        if fenster is not None and fenster.winfo_exists():
            self._einfuegetext = fenster.textfeld.get("1.0", "end")
        return getattr(self, "_einfuegetext", "")

    # ------------------------------------- Berechnete Groessen ueber Rohwerten
    def berechnete_offen(self) -> bool:
        """Ob die berechneten Groessen ueber den Rohwerten stehen."""
        return self.berechnet_oben in self.ergebnistabellen

    def _berechnete_umschalten(self, merken=True):
        """Die berechneten Groessen ueber den Rohwerten auf- oder zuklappen."""
        if self.berechnete_offen():
            self.ergebnistabellen.remove(self.berechnet_oben)
            self.rohteilung.forget(self.berechnet_rahmen)
            self.knopf_berechnete.config(text=BERECHNETE_EIN_TEXT)
        else:
            self.rohteilung.insert(0, self.berechnet_rahmen, weight=2)
            self.ergebnistabellen.append(self.berechnet_oben)
            self.knopf_berechnete.config(text=BERECHNETE_AUS_TEXT)
            self._ergebnisse_zeigen()
            self._nachziehen()
            self._auswahl_stellen()
            self._teilung_setzen()
        if merken:
            konfig = self._einstellungen()
            konfig.set("trdf_berechnete", BERECHNETE_AN
                       if self.berechnete_offen() else BERECHNETE_AUS)
            konfig.speichern()

    def _teilung_setzen(self):
        """Oben gut ein Drittel, unten der Rest - ziehen laesst es sich."""
        try:
            self.rohteilung.update_idletasks()
            hoehe = self.rohteilung.winfo_height()
            if hoehe > 50:
                self.rohteilung.sashpos(0, int(hoehe * 0.38))
        except tk.TclError:
            pass

    def _arbeitszeile_setzen(self, probe: str):
        """In einer Rohwertzeile wird getippt - die anderen Tabellen gehen mit.

        Die Zeile wird ueberall unterlegt, und die berechneten Groessen
        und das Pruefblatt rollen zu ihr: wer unten einen Rohwert
        aendert, sieht oben dieselbe Probe.
        """
        self.arbeitszeile = str(probe)
        self._auswahl_stellen()
        self._mitgehen()

    def _mitgehen(self):
        """Die berechneten Tabellen zur Arbeitszeile rollen."""
        if not self.arbeitszeile:
            return
        for tabelle in list(self.ergebnistabellen) + [self.pruefungstabelle]:
            try:
                tabelle.sehen(self.arbeitszeile)
            except tk.TclError:
                pass

    def _bericht_merken(self, geaendert, serie: str, sicherung: str,
                        offen=()):
        """Haelt fest, was gerade geschrieben wurde, und zeigt es."""
        self.letzter_export = {
            "serie": serie, "zeitpunkt": dt.datetime.now(),
            "sicherung": sicherung,
            "aenderungen": list(geaendert), "offen": list(offen)}
        self._bericht_zeigen()

    def _bericht_zeigen(self):
        """Fuellt den Reiter aus dem gemerkten Export."""
        stand = self.letzter_export
        if not stand:
            self.berichtstabelle.fuellen(list(trdfexport.BERICHT_KOPF), [])
            self.berichtstand.config(text=BERICHT_LEER, fg=Style.MUTED)
            return
        # Auch ein Export, bei dem nichts angekommen ist, ist der letzte:
        # die leere Tabelle mit der Zeile darueber ist dann die Auskunft.
        spalten, zeilen = trdfexport.bericht(stand["aenderungen"],
                                             trdfpruefung.stellen_fuer)
        # Rot heisst hier dasselbe wie ueberall im Reiter: dieser Wert
        # ist von Hand bewegt worden. Der Rest ist seine Folge.
        marken = {(kennung, eine["kuerzel"]): "geaendert"
                  for eine in stand["aenderungen"]
                  for kennung in [str(eine.get("probe") or "")]
                  if eine.get("art") == trdfexport.ROHWERT}
        self.berichtstabelle.fuellen(spalten, zeilen, marken=marken,
                                     breiten=BREITEN, passend=spalten[2:])
        self._kopfhinweise(self.berichtstabelle, spalten)
        werte = len(stand["aenderungen"])
        satz = (f"{stand['serie']}  |  {stand['zeitpunkt']:%d.%m.%Y %H:%M}  "
                f"|  {len(zeilen)} Proben, {werte} Werte  |  Sicherung: "
                f"{stand['sicherung']}")
        if stand["offen"]:
            satz += (f"  |  {len(stand['offen'])} Werte stehen danach noch "
                     f"wie vorher da")
        self.berichtstand.config(
            text=satz, fg=Style.ERROR if stand["offen"] else Style.TEXT)

    def _bericht_verworfen(self, name: str):
        """Nach dem Zurueckspielen gilt der letzte Export nicht mehr."""
        self.letzter_export = None
        self._bericht_zeigen()
        self.berichtstand.config(
            text=f"Der letzte Export wurde aus {name} zurueckgespielt.",
            fg=Style.WARN)

    def _bericht_speichern(self):
        """Legt den Bericht als CSV ab und oeffnet ihn."""
        stand = self.letzter_export
        if not stand or not stand["aenderungen"]:
            self.berichtstand.config(text=BERICHT_LEER, fg=Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        pfad = trdfexport.bericht_schreiben(ordner, stand["serie"],
                                            stand["aenderungen"],
                                            stand["zeitpunkt"])
        if not pfad:
            self.berichtstand.config(
                text=f"Die Datei liess sich nicht schreiben. Steht der "
                     f"Ordner „{ordner}“ zur Verfuegung?", fg=Style.ERROR)
            return
        self.berichtstand.config(text=pfad, fg=Style.TEXT)
        trdfpruefung.oeffnen(pfad)

    # ------------------------------------------------------------- Legende
    #
    # Die Tabellen tragen die Kuerzel, mit denen das LIMS rechnet - unter
    # ihnen stehen die Groessen in den Formeln, und wer eine Formel
    # liest, sucht genau sie. Nur weiss niemand auswendig, dass „_TSM“
    # die Tiefenstufenmaechtigkeit ist. Der Knopf „Info“ sagt es, je
    # Reiter fuer dessen eigene Spalten - und laesst Platz fuer das, was
    # das Labor selbst dazu zu sagen hat.

    def _infoknopf(self, leiste, befehl):
        knopf = RoundedButton(leiste, text="Info", width=90, height=28,
                              bg="#3f4a5a", command=befehl)
        knopf.pack(side="left", padx=(8, 0))
        ToolTip(knopf, "Was die Spaltenueberschriften dieser Tabelle\n"
                       "bedeuten - Name, Einheit und Formelkuerzel.\n"
                       "Eine eigene Beschreibung laesst sich dort\n"
                       "eintragen und speichern. Dort steht auch, in\n"
                       "welcher Reihenfolge die Spalten kommen (Zeile\n"
                       "greifen und ziehen), welche links stehen\n"
                       "bleiben („Fest“), welche ueberhaupt dastehen\n"
                       "(„Zeigen“) und was oben in der Kopfzeile steht -\n"
                       "je Spalte einzeln oder fuer alle zugleich.")
        return knopf

    def _spalten_speichern(self, blatt: str, texte: dict,
                           ordnung=None) -> str:
        """Legt Beschreibungen und Spaltenordnung ab - "" wenn es klappte."""
        fehler = self.spalten_ablegen(blatt, texte, ordnung)
        if not fehler:
            # Sofort sichtbar: wer die Reihenfolge zurechtzieht, will sie
            # nicht erst beim naechsten Abruf sehen.
            self._ansichten_erneuern()
        return fehler

    def _ansichten_erneuern(self):
        """Die Tabellen neu schreiben - nach einer neuen Spaltenordnung."""
        try:
            self._zeigen()
        except tk.TclError:
            pass

    def _legende_zeigen(self, titel: str, spalten, zeilen, quellen=None):
        reihenfolge, fest = self.spaltenordnung(titel)
        schluessel = {spalte: trdflegende.schluessel(spalte, quellen)
                      for spalte in (zeile[0] for zeile in zeilen)}
        fenster = trdflegende.Legendenfenster(
            self, titel, spalten, zeilen,
            speichern=lambda texte, ordnung, blatt=titel:
                self._spalten_speichern(blatt, texte, ordnung),
            schluessel=schluessel,
            ordnung={"reihenfolge": reihenfolge,
                     # Nur die, die es in dieser Tabelle auch gibt -
                     # sonst stuende in der Legende ein „ja“ neben
                     # einer Spalte, die hier gar nicht festgehalten
                     # werden kann.
                     "fest": [kuerzel for kuerzel in fest
                              if kuerzel in set(schluessel.values())],
                     "versteckt": [kuerzel
                                   for kuerzel in self.versteckt(titel)
                                   if kuerzel in set(schluessel.values())],
                     "kopfspalte": self.kopfspalte(),
                     "kopfspalten": {kuerzel: wert for kuerzel, wert
                                     in self.kopfspalten().items()
                                     if kuerzel in set(schluessel.values())}})
        return fenster

    def _rohlegende_zeigen(self):
        # Alle Spalten, auch die ausgeblendeten: aus einer Liste, in der
        # sie fehlen, liessen sie sich nicht wieder einblenden.
        spalten = self._rohspalten()[3]
        return self._legende_zeigen(
            BLATT_ROH, list(trdflegende.SPALTEN_ROH),
            trdflegende.rohlegende(spalten, self.methoden,
                                   self.beschreibungen()))

    def _ergebnislegende_zeigen(self):
        spalten = self._ergebnisspalten()[4]
        return self._legende_zeigen(
            BLATT_ERGEBNIS, list(trdflegende.SPALTEN_ERGEBNIS),
            trdflegende.ergebnislegende(spalten, self.methoden,
                                        self.beschreibungen()))

    def _prueflegende_zeigen(self):
        spalten = self._pruefspalten()[3]
        return self._legende_zeigen(
            BLATT_PRUEFUNG, list(trdflegende.SPALTEN_ERGEBNIS),
            trdflegende.pruefungslegende(spalten, trdfpruefung.QUELLEN,
                                         self.methoden,
                                         self.beschreibungen()),
            quellen=trdfpruefung.QUELLEN)

    # ------------------------------------------------------------- Abrufen
    def _melden(self, text, farbe=Style.MUTED):
        self.stand.config(text=text, fg=farbe)

    def serienliste_laden(self, danach=None):
        """Die TRDF-Serien aus dem Fahrplan - im Hintergrund.

        Nur fuer die Liste im Serienfeld: welche Methoden eine Serie
        fuehrt, fragt erst "Abfragen". Ohne Zugang (beim Bauen der Seite
        ist noch niemand angemeldet) bleibt die Liste leer und das Feld
        nimmt eine eingetippte Serie.
        """
        zugang = self._zugang_holen()
        if zugang is None:
            return

        def arbeit():
            with lims_db.sitzung(zugang) as verbindung:
                methoden = lims_db.trdf_methoden(zugang, verbindung=verbindung)
                return lims_db.trdf_serien(zugang, [um for um, _ in methoden],
                                           verbindung=verbindung)

        def fertig(serien):
            self.serienliste = list(serien)
            self.feld_serie["values"] = self.serienliste
            self._melden(f"{len(self.serienliste)} TRDF-Serien im Fahrplan "
                         f"- Serie waehlen und \u201eAbfragen\u201c.")
            if danach is not None:
                danach()

        self._im_hintergrund(arbeit, fertig, self._schiefgegangen)

    def _schiefgegangen(self, fehler):
        self._melden(lims_db.fehlertext(fehler), Style.ERROR)

    def _schreiben_schiefgegangen(self, fehler):
        """Beim Schreiben reicht die Statuszeile nicht.

        Wer auf "Schreiben" gedrueckt hat, wartet auf eine Antwort und
        darf nicht raten muessen, ob etwas angekommen ist - eine
        gescheiterte Abfrage ist eine Unbequemlichkeit, ein gescheiterter
        Schreibweg eine offene Frage.
        """
        satz = lims_db.fehlertext(fehler)
        self._melden(satz, Style.ERROR)
        messagebox.showerror("Es wurde nichts geschrieben", satz, parent=self)

    # ------------------------------------------------------ Serie und Methode
    def _merken(self):
        """Die Serie fuer den naechsten Start ablegen.

        Die Methode nicht: welche gilt, sagt beim naechsten Mal wieder
        die Abfrage - eine gemerkte koennte zu einer anderen Serie
        gehoeren.
        """
        konfig = self._einstellungen()
        konfig.set("serie", self.v_serie.get().strip())
        konfig.speichern()

    def _methoden_leeren(self, text=METHODE_OFFEN):
        """Die Methodenliste gilt nicht mehr - etwa nach einer neuen Serie."""
        self.methodenwahl = []
        self.abgefragte_serie = ""
        self.feld_methode.config(values=[], state="disabled")
        self.v_methode.set(text)

    def _serie_gewechselt(self):
        """Eine Serie aus der Liste - die Methoden werden gleich gefragt."""
        self._abfragen()

    def _serie_getippt(self):
        """Steht eine andere Serie im Feld, ist die Methodenliste veraltet."""
        if not hasattr(self, "feld_methode"):
            return
        if self.abgefragte_serie and \
                self.v_serie.get().strip() != self.abgefragte_serie:
            self._methoden_leeren()

    def _abfragen(self):
        """Welche TRDF-Methoden fuehrt die Serie? - im Hintergrund."""
        serie = self.v_serie.get().strip()
        zugang = self._zugang_holen()
        if not serie or zugang is None:
            self._melden("Erst anmelden und eine Serie waehlen.", Style.WARN)
            return
        self._methoden_leeren("wird abgefragt ...")
        self._melden(f"Die Untersuchungsmethoden der Serie {serie} werden "
                     f"abgefragt ...")
        self.update_idletasks()

        def arbeit():
            return self.methoden_abfragen(zugang, serie)

        def fertig(passend):
            self._methoden_zeigen(serie, passend)

        self._im_hintergrund(arbeit, fertig, self._abfrage_schiefgegangen)

    def _abfrage_schiefgegangen(self, fehler):
        self._methoden_leeren()
        self._schiefgegangen(fehler)

    def _methoden_zeigen(self, serie: str, passend):
        """Die Methodenliste der Serie ins Feld - und bei einer gleich holen."""
        if self.v_serie.get().strip() != serie:
            # Inzwischen steht eine andere Serie im Feld - die Antwort
            # gehoert nicht mehr zu ihr.
            self._methoden_leeren()
            return
        if not passend:
            self._methoden_leeren("keine TRDF-Methode")
            self._melden(f"Die Serie {serie} fuehrt keine Untersuchungs"
                         f"methode mit TRDF im Kuerzel.", Style.WARN)
            return
        self.abgefragte_serie = serie
        self.methodenwahl = methodentexte(passend)
        texte = [text for _um, _k, text in self.methodenwahl]
        self.feld_methode.config(values=texte, state="readonly")
        if len(texte) == 1:
            self.v_methode.set(texte[0])
            self._methodenfeld_freigeben()
            self._abrufen()
            return
        self.v_methode.set("")
        namen = ", ".join(texte)
        self._melden(f"Die Serie {serie} fuehrt {len(texte)} TRDF-Methoden "
                     f"({namen}) - bitte eine waehlen.", Style.WARN)

    def _methode_gewaehlt(self):
        self._methodenfeld_freigeben()
        self._abrufen()

    def _methodenfeld_freigeben(self):
        """Fokus und Markierung weg vom Methodenfeld.

        Im clam-Thema zeichnet ein schreibgeschuetztes Auswahlfeld mit
        Fokus seinen Text nicht sichtbar - die gewaehlte Methode saehe
        aus wie keine. Ohne Fokus steht sie da.
        """
        try:
            self.feld_methode.selection_clear()
            self.focus_set()
        except tk.TclError:
            pass

    def gewaehlte_methode(self) -> tuple:
        """(UM_ID, Kuerzel) der gewaehlten Methode - (None, "") ohne.

        Kein stiller Ersatz: eine Methode, die nicht in der Liste der
        abgefragten Serie steht, ist keine Wahl.
        """
        gewaehlt = self.v_methode.get().strip()
        for um_id, name, text in self.methodenwahl:
            if text == gewaehlt:
                return um_id, name
        return None, ""

    def _abrufen(self):
        """Holt alles, was zu Serie und gewaehlter Methode gehoert."""
        serie = self.v_serie.get().strip()
        zugang = self._zugang_holen()
        if not serie or zugang is None:
            self._melden("Erst anmelden und eine Serie waehlen.", Style.WARN)
            return
        if serie != self.abgefragte_serie:
            # Die Methodenliste gehoert zu einer anderen Serie - erst
            # fragen, sonst kaeme die Serie unter einer Methode, die sie
            # vielleicht gar nicht fuehrt.
            self._abfragen()
            return
        um_id, kuerzel = self.gewaehlte_methode()
        if um_id is None:
            self._melden("Erst eine Untersuchungsmethode waehlen.", Style.WARN)
            return
        self._melden(f"Serie {serie} - {kuerzel} wird geholt ...")
        self.update_idletasks()

        def arbeit():
            return self.abruf_holen(zugang, serie, um_id, kuerzel)

        def fertig(geholt):
            self._uebernehmen(geholt)
            self._merken()

        self._im_hintergrund(arbeit, fertig, self._schiefgegangen)

    def _uebernehmen(self, geholt):
        satz, warnung = self.daten_uebernehmen(geholt)
        self._melden(satz, Style.WARN if warnung else Style.TEXT)
        self.auskunft.config(text=self.auskunftstext(geholt))
        self._legende_stellen()
        self._quelle_zeigen()
        self._zeigen()

    # -------------------------------------------------------- Einfuegetext
    def _text_leeren(self):
        self._einfuegetext = ""
        fenster = getattr(self, "einfuegefenster", None)
        if fenster is not None and fenster.winfo_exists():
            fenster.textfeld.delete("1.0", "end")
        self.um_vergessen()
        self._zeigen()
        for probe in list(self.bloecke):
            self._block_auffrischen(probe)
        # Nach dem Neuzeichnen: das schreibt sonst seine eigene Zeile
        # darueber.
        self._melden("Die eingefuegte UM ist geleert - gerechnet wird mit "
                     "den Rohwerten aus dem LIMS.", Style.TEXT)

    def _text_uebernehmen(self) -> bool:
        """Die eingefuegte Liste lesen - zurueck kommt, ob es geklappt hat."""
        ok, satz, art = self.um_lesen(self.einfuegetext())
        if not ok:
            self._melden(satz, Style.ERROR if art == "fehler" else Style.WARN)
            return False
        self._zeigen()
        for probe in list(self.bloecke):
            self._block_auffrischen(probe)
        # Erst jetzt: das Neuzeichnen schreibt sonst "x von y Werten
        # stimmen" darueber, und die Auskunft ueber die Liste waere weg.
        self._melden(satz, Style.WARN if art == "warn" else Style.TEXT)
        return True

    # ----------------------------------------------------------- Die Quelle
    def _quelle_zeigen(self):
        """Sagt, woher die Rohwerte kommen - oben und im Einfuegefenster."""
        if self.quelle == QUELLE_TEXT:
            text = (f"Rohwerte aus: eingefuegter UM "
                    f"({len(self.eingefuegt)} Proben)")
        else:
            text = "Rohwerte aus: LIMS"
        self.quellanzeige.config(
            text=text, fg=Style.ACCENT if self.quelle == QUELLE_TEXT
            else Style.MUTED)
        self.quellhinweis = (
            "In der Probenvorbereitung \u201eaktueller Block\u201c -> "
            "kopieren, hier mit Strg+V einfuegen, dann \u201eUebernehmen\u201c "
            "- danach wird mit dieser Liste gerechnet. \u201eLeeren\u201c "
            "schaltet zurueck auf die Rohwerte aus dem LIMS.")
        fenster = getattr(self, "einfuegefenster", None)
        if fenster is not None and fenster.winfo_exists():
            fenster.hinweis.config(text=self.quellhinweis)

    # ------------------------------------------------------------ Rechnen
    def _von_hand_geaendert(self, zeile, spalte, wert):
        self.vonhand[(zeile, spalte)] = wert
        if spalte == trdfrohpruefung.VARIANTE:
            self._variante_wirkt(zeile, wert)
        self._rechnung_vergessen([zeile])
        # Die Rohwerttabelle wird nicht neu gebaut - sonst faellt das
        # offene Eingabefeld heraus, und der naechste Tabulator ginge
        # ins Leere. Gefaerbt wird nur die eine Zelle.
        for tabelle in self.rohtabellen:
            tabelle.setzen(zeile, spalte, wert)
            tabelle.marke_setzen(zeile, spalte, "geaendert")
            tabelle.marke_setzen(zeile, "Probe", "geaendert")
        self._befund_nachtragen(zeile)
        self._zeigen(nur_ergebnisse=True)
        self._block_auffrischen(zeile)
        self.arbeitszeile = str(zeile)
        self._auswahl_stellen()
        self._mitgehen()

    def _befund_nachtragen(self, probe: str):
        """Die Bewertung einer Zeile neu setzen, ohne die Tabelle zu bauen.

        Die Rohwerttabelle wird nach einer Handeingabe nicht neu
        geschrieben - sonst faellt das offene Eingabefeld heraus. Die
        Bewertung stand darum bis zum naechsten Neuaufbau noch auf dem
        alten Stand, und gerade sie ist die Antwort auf das, was eben
        getippt wurde.
        """
        saetze = self.rohbefund(probe)
        text = trdfrohpruefung.bewertungstext(saetze)
        for tabelle in self.rohtabellen:
            if tabelle.setzen(probe, BEWERTUNGSSPALTE, text):
                tabelle.marke_setzen(probe, BEWERTUNGSSPALTE,
                                     "abweichung" if saetze else None)

    def _variante_wirkt(self, probe: str, eingabe):
        """Die neue Variante raeumt die Rohwerte auf - siehe Modell."""
        neu = self.variante_setzen(probe, eingabe)
        for kuerzel, wert in neu.items():
            for tabelle in self.rohtabellen:
                if tabelle.setzen(probe, kuerzel, wert):
                    tabelle.marke_setzen(probe, kuerzel, "geaendert")
                    tabelle.marke_setzen(probe, "Probe", "geaendert")
        if neu:
            self._rohmelden(
                f"Variante {str(eingabe).strip()}: {len(neu)} Rohwerte "
                f"angepasst", Style.TEXT)
        return neu

    def leere_fuellen(self, probe=None, spalte=None) -> list:
        """Strg+E / Strg+Shift+E: leere Rohwertzellen bekommen ein x.

        Mit `probe` die Zeile dieser Probe, mit `spalte` die ganze
        Spalte. Leer heisst: es steht wirklich nichts da (`ist_leer`).
        Ein x heisst im LIMS "hier soll nichts stehen", leer heisst
        "hier steht noch nichts"; die Taste macht aus dem einen das
        andere, so wie es die Eingabemaske des LIMS beim Setzen der
        Variante tut. Zahlen bleiben unberuehrt.
        """
        if spalte is not None:
            if spalte not in self.rohliste:
                return []
            zellen = [(name, spalte) for _lnr, name in self.proben]
            wo = f"Spalte {spalte}"
        else:
            zellen = [(probe, kuerzel) for kuerzel in self.rohliste]
            wo = str(probe)
        gesetzt = [(name, kuerzel, trdf.MARKE) for name, kuerzel in zellen
                   if self.ist_leer(name, kuerzel)]
        if not gesetzt:
            self._rohmelden(f"{wo}: keine leere Zelle", Style.TEXT)
            return []
        self._block_eingefuegt(gesetzt)
        self._rohmelden(f"{wo}: {len(gesetzt)} leere Zellen mit "
                        f"\u201e{trdf.MARKE}\u201c gefuellt", Style.TEXT)
        return gesetzt

    def _nach_unten_eingefuegt(self, gesetzt):
        """Nach unten kopiert - wie ein Block, die Variante wirkt dabei.

        Wer eine Variante nach unten zieht, will in jeder Zeile, was
        die Variante dort verlangt: die x in den Feldern, die sie nicht
        braucht. Ein Block aus Excel bringt seine Werte dagegen selbst
        mit; deshalb gilt das nur hier.
        """
        self._block_eingefuegt(gesetzt)
        varianten = [(zeile, wert) for zeile, spalte, wert in gesetzt
                     if spalte == trdfrohpruefung.VARIANTE]
        for zeile, wert in varianten:
            self._variante_wirkt(zeile, wert)
        if varianten:
            self._rechnung_vergessen([zeile for zeile, _ in varianten])
            self._zeigen(nur_ergebnisse=True)
            for zeile, _wert in varianten:
                self._befund_nachtragen(zeile)
                self._block_auffrischen(zeile)
        self._rohmelden(f"{len(gesetzt)} Zellen nach unten gefuellt",
                        Style.TEXT)

    def _block_eingefuegt(self, gesetzt, uebrig=0):
        """Ein Block aus der Zwischenablage - einmal rechnen, einmal zeigen.

        Je Zelle neu zu rechnen waere bei dreihundert eingefuegten Werten
        dreihundertmal dieselbe Arbeit; hier wird alles uebernommen und
        danach ein einziges Mal gerechnet und gezeichnet.
        """
        for zeile, spalte, wert in gesetzt:
            self.vonhand[(zeile, spalte)] = wert
            for tabelle in self.rohtabellen:
                tabelle.setzen(zeile, spalte, wert)
                tabelle.marke_setzen(zeile, spalte, "geaendert")
                tabelle.marke_setzen(zeile, "Probe", "geaendert")
        self._rechnung_vergessen({zeile for zeile, _, _ in gesetzt})
        self._zeigen(nur_ergebnisse=True)
        for probe in {zeile for zeile, _, _ in gesetzt}:
            self._befund_nachtragen(probe)
            self._block_auffrischen(probe)
        satz = f"{len(gesetzt)} Werte eingefuegt"
        if uebrig:
            satz += (f"  |  {uebrig} passten nicht mehr in die Tabelle und "
                     f"wurden nicht uebernommen")
        self._rohmelden(satz, Style.WARN if uebrig else Style.TEXT)

    # ------------------------------------------------------------- Anzeige
    def _tabelle_sichtbar(self, tabelle) -> bool:
        """Steht diese Tabelle gerade im Blick?

        Gemessen an den Reitern, nicht am Bildschirm: die Ergebnisse
        stehen im zweiten, das Pruefblatt im dritten; die berechneten
        Groessen ueber den Rohwerten, wenn sie aufgeklappt sind.
        """
        if self.sofort_zeichnen:
            return True
        try:
            aktiv = self.reiter.index(self.reiter.select())
        except tk.TclError:
            return True
        if tabelle is getattr(self, "berechnet_oben", None):
            return aktiv == 0 and self.berechnete_offen()
        reiter = {id(getattr(self, "ergebnistabelle", None)): 1,
                  id(getattr(self, "pruefungstabelle", None)): 2}
        return reiter.get(id(tabelle), aktiv) == aktiv

    def _zeichnen(self, tabelle, auftrag):
        """Eine Tabelle neu schreiben - jetzt, oder wenn sie aufgeht.

        Eine Eingabe in den Rohwerten aendert die Ergebnisse und das
        Pruefblatt. Beide jedes Mal neu zu schreiben, obwohl sie in einem
        anderen Reiter verdeckt liegen, kostete bei dreihundert Proben
        den groessten Teil der Wartezeit nach jeder Zahl. Gemerkt wird
        der letzte Auftrag; er laeuft, sobald der Reiter aufgeht.
        """
        if self._tabelle_sichtbar(tabelle):
            self._veraltet.pop(tabelle, None)
            auftrag(tabelle)
        else:
            self._veraltet[tabelle] = auftrag

    def _nachziehen(self, alle=False):
        """Was beim Verdecken liegen blieb, jetzt zeichnen."""
        for tabelle, auftrag in list(self._veraltet.items()):
            if alle or self._tabelle_sichtbar(tabelle):
                self._veraltet.pop(tabelle, None)
                auftrag(tabelle)
        self._auswahl_stellen()
        self._mitgehen()

    def _aktuell(self, tabelle):
        """Eine Tabelle auf den Stand bringen, bevor aus ihr gelesen wird."""
        auftrag = self._veraltet.pop(tabelle, None)
        if auftrag is not None:
            auftrag(tabelle)
        return tabelle

    def _zeigen(self, nur_ergebnisse=False):
        if not nur_ergebnisse:
            self._rohwerte_zeigen()
        self._ergebnisse_zeigen()
        # Das Pruefblatt ganz aufschieben, solange es verdeckt ist - auch
        # seine Bewertung: sie steht nur dort. Die Ergebnisse rechnen
        # weiter sofort, denn aus ihnen kommt die Statuszeile.
        if self._tabelle_sichtbar(self.pruefungstabelle):
            self._pruefung_zeigen()
        else:
            self._veraltet[self.pruefungstabelle] = \
                lambda _tabelle: self._pruefung_zeigen()

    def _kopfhinweise(self, tabelle, spalten, quellen=None):
        """Was ueber den Spaltenueberschriften steht, wenn die Maus wartet.

        Dieselbe Auskunft wie unter „Info“, nur auf zwei bis vier
        Zeilen: die Ueberschriften tragen die Kuerzel des LIMS, und wer
        sie nicht auswendig kennt, faehrt hinueber statt die Legende zu
        oeffnen.
        """
        tabelle.kopfhinweise(trdflegende.hinweise(
            spalten, self.methoden, quellen, self.beschreibungen()))

    def _rohwerte_zeigen(self):
        tafel = self.rohtafel(self.v_nur_rohbefunde.get())
        for tabelle in self.rohtabellen:
            tabelle.fuellen(
                tafel["spalten"], tafel["zeilen"], aenderbar=self.rohliste,
                marken=tafel["marken"],
                breiten={"Zeile": 56, "Probe": 110, "WGH": 110,
                         BEWERTUNGSSPALTE: 420},
                fest=tafel["fest"], ueberschriften=tafel["koepfe"],
                zugspalten=("Probe",))
            self._kopfhinweise(tabelle, tafel["spalten"])
        if tafel["gesamt"]:
            satz, art = tafel["stand"]
            self._rohmelden(satz, Style.WARN if art == "warn" else Style.TEXT)

    def _ergebnisse_zeigen(self):
        tafel = self.ergebnistafel()

        def auftrag(tabelle):
            tabelle.zellhinweise(self.aufschlusshinweis)
            tabelle.fuellen(
                tafel["spalten"], tafel["zeilen"], marken=tafel["marken"],
                breiten={"Zeile": 56, "Probe": 110, BEWERTUNGSSPALTE: 420},
                fest=tafel["fest"], ueberschriften=tafel["koepfe"])
            self._kopfhinweise(tabelle, tafel["spalten"])

        for tabelle in self.ergebnistabellen:
            self._zeichnen(tabelle, auftrag)
        if self.proben:
            satz, art = tafel["stand"]
            self._melden(satz, Style.WARN if art == "warn" else Style.TEXT)

    def _pruefung_zeigen(self):
        """Das Arbeitsblatt fuellen - eine Zeile je Probe."""
        tafel = self.prueftafel(self.v_nur_befunde.get())

        def auftrag(tabelle):
            tabelle.zellhinweise(self.aufschlusshinweis)
            tabelle.fuellen(
                tafel["spalten"], tafel["zeilen"], marken=tafel["marken"],
                breiten=dict(BREITEN),
                mitwachsend=(BEWERTUNGSSPALTE,), fest=tafel["fest"],
                ueberschriften=tafel["koepfe"])
            self._kopfhinweise(tabelle, tafel["spalten"],
                               trdfpruefung.QUELLEN)

        self._zeichnen(self.pruefungstabelle, auftrag)
        if tafel["gesamt"]:
            satz, art = tafel["stand"]
            self._pruefmelden(satz, Style.WARN if art == "warn"
                              else Style.TEXT)

    def _bild_zeigen(self):
        """Die Trockenrohdichte ueber dem Kohlenstoff - alle Proben auf einmal.

        Die Tabelle sagt, dass ein Wert ausserhalb liegt; das Bild sagt,
        wie weit - und ob die ganze Serie an einer Klassengrenze klebt
        oder eine einzelne Probe herausfaellt.
        """
        blatt = self.geprueft()
        if not blatt:
            self._pruefmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return
        vorhandenes = getattr(self, "bildfenster", None)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            vorhandenes.destroy()
        self.bildfenster = Bildfenster(self, self.v_serie.get().strip(),
                                       self._bildpunkte(blatt),
                                       self._block_zeigen)

    def _bildpunkte(self, blatt) -> list:
        punkte = []
        for probe in blatt:
            werte = probe["werte"]
            punkte.append({
                "probe": probe["probe"], "trdf": werte.get(trdfpruefung.TRDF),
                "cges": werte.get(trdfpruefung.CGES),
                "co3": werte.get(trdfpruefung.CO3),
                "marke": "geaendert" if trdfblock.DICHTE in self.bewegt(
                    probe["probe"]) else None})
        return punkte

    def _pruefmelden(self, text, farbe=Style.MUTED):
        self.pruefstand.config(text=text, fg=farbe)

    def _legende_stellen(self):
        """Welche Spalte welchen Parameter des LIMS zeigt."""
        teile = []
        for name in trdfpruefung.SPALTEN[2:-2]:
            kuerzel = trdfpruefung.QUELLEN[name]
            im_lims = self.parameternamen.get(kuerzel)
            teile.append(f"{name} = {im_lims or kuerzel}")
        methoden = (f"U-Methode {self.um_kuerzel}  |  Cges aus "
                    f"{lims_db.ATNULL_MARKE}, CO3 aus "
                    f"{lims_db.ATNULL_CO3_MARKE}")
        self.legende.config(text=methoden + "\n" + "  ·  ".join(teile))
        self.info_pruefung.setzen(
            PRUEF_ERKLAERUNG + "\n\n" + methoden + "\n"
            + "\n".join(teile))

    # ------------------------------------------------------------- Der Block
    # Ein Klick auf die Probennummer - in welcher der drei Tabellen auch
    # immer - oeffnet den Bodenblock: die Zahlen einer Zeile sagen, was
    # herauskam, das Bild sagt, ob Schaetzung und Wagung zusammenpassen.

    def _block_zeigen(self, zeile, spalte, ueber=None):
        """Der Bodenblock zu einer Probe - je Probe ein Fenster.

        `ueber` ist das Fenster, ueber dem er liegen soll. Wer in der
        Grossansicht auf die Probennummer klickt, will den Block nicht
        dahinter verschwinden sehen.
        """
        if spalte not in ("Probe", "Probe-Nr.") or not zeile:
            return
        vorhandenes = self.bloecke.get(zeile)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            self._block_auffrischen(zeile)
            vorhandenes.lift()
            return
        fenster = trdfblock.zeigen(
            ueber or self, zeile, self.rohsatz(zeile), self.gerechnet(zeile),
            bei_wechsel=self._block_wechseln)
        self.bloecke[zeile] = fenster
        # Geht das Fenster wieder zu, geht die Unterlegung mit ihm.
        fenster.bind("<Destroy>",
                     lambda ereignis, f=fenster:
                         self._block_geschlossen(ereignis, f), add="+")
        self._auswahl_stellen()

    def _gross_zeigen(self):
        """Die Rohwerte gross - zum Eintragen ohne Lupe."""
        vorhandenes = getattr(self, "_grossansicht", None)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            vorhandenes.lift()
            vorhandenes.focus_set()
            return vorhandenes
        if not self.proben:
            self._rohmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return None
        self._grossansicht = Grossansicht(self)
        return self._grossansicht

    def rohansicht_anmelden(self, tabelle):
        """Eine zweite Ansicht der Rohwerte - sie wird mitgefuehrt."""
        if tabelle not in self.rohtabellen:
            self.rohtabellen.append(tabelle)
        self._rohwerte_zeigen()
        # Auch die neue Ansicht zeigt, wo gerade gearbeitet wird.
        self._auswahl_stellen()

    def rohansicht_abmelden(self, tabelle):
        if tabelle in self.rohtabellen:
            self.rohtabellen.remove(tabelle)

    def _block_wechseln(self, block, richtung: int):
        """Pfeil rauf und runter im Blockfenster: eine Probe weiter.

        Geblaettert wird in der Reihenfolge, in der die Proben in den
        Tabellen stehen. Am Ende der Liste ist Schluss - wer unten
        ankommt, will nicht oben wieder anfangen, sondern merken, dass
        er unten ist.
        """
        namen = [probe for _lnr, probe in self.proben]
        if block.probe not in namen:
            return
        stelle = namen.index(block.probe) + richtung
        if not 0 <= stelle < len(namen):
            return
        neue = namen[stelle]
        vorhandenes = self.bloecke.get(neue)
        if vorhandenes is not None and vorhandenes.winfo_exists():
            # Diese Probe steht schon in einem eigenen Fenster - zwei
            # gleiche waeren nur verwirrend.
            vorhandenes.lift()
            vorhandenes.focus_set()
            return
        self.bloecke.pop(block.probe, None)
        self.bloecke[neue] = block
        block.uebernehmen(neue, self.rohsatz(neue), self.gerechnet(neue))
        self._auswahl_stellen()

    def _block_geschlossen(self, ereignis, fenster):
        """Ein Blockfenster ist zu - wessen Zeile also nicht mehr gewaehlt.

        `<Destroy>` kommt auch von jedem Kind des Fensters; gemeint ist
        nur das Fenster selbst.
        """
        if ereignis.widget is not fenster:
            return
        for probe, offenes in list(self.bloecke.items()):
            if offenes is fenster:
                self.bloecke.pop(probe, None)
        self._auswahl_stellen()

    def _auswahl_stellen(self):
        """Unterlegt in allen Tabellen die Proben mit offenem Blockbild.

        Wer im Blockbild mit den Pfeilen durch die Serie blaettert,
        sieht so in der Tabelle mit, wo er gerade ist - in der kleinen
        wie in der grossen.
        """
        offen = [probe for probe, fenster in self.bloecke.items()
                 if fenster is not None and fenster.winfo_exists()]
        # Dazu die Zeile, in der gerade getippt wird - sie ist der Ort,
        # an dem gearbeitet wird, auch ohne offenen Block.
        if self.arbeitszeile and self.arbeitszeile not in offen:
            offen.append(self.arbeitszeile)
        for tabelle in list(self.rohtabellen) + list(
                getattr(self, "ergebnistabellen", [])) + [
                getattr(self, "pruefungstabelle", None)]:
            if tabelle is None:
                continue
            try:
                tabelle.auswahl(offen)
            except tk.TclError:
                pass

    def _block_auffrischen(self, probe: str):
        """Ein offener Block folgt der Aenderung, ohne zu blinken.

        Genau dafuer ist er da: einen Rohwert aendern und zusehen, wie
        der Skelettanteil wandert. Ein Fenster, das sich dabei schliesst
        und neu aufgeht, waere das Gegenteil davon.
        """
        block = self.bloecke.get(probe)
        if block is None or not block.winfo_exists():
            self.bloecke.pop(probe, None)
            return
        block.neu_zeichnen(self.rohsatz(probe), self.gerechnet(probe))

    # ------------------------------------------------------ Zurueckschreiben
    # Der einzige Weg im Programm, der einen Messwert ueberschreibt. Er
    # geht nur ueber eine bestaetigte Uebersicht und nur nach einer
    # Sicherung - beides steht unten in dieser Reihenfolge und laesst
    # sich nicht umgehen.

    def _rohblatt_speichern(self):
        """Die Rohwerte mit ihrem Befund als Blatt."""
        blatt = self.rohblatt()
        if not blatt:
            self._rohmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfrohpruefung.ORDNER)
        pfad = trdfrohpruefung.schreiben(ordner, self.v_serie.get().strip(),
                                         blatt, self.rohliste)
        if not pfad:
            self._rohmelden(f"Die Datei liess sich nicht schreiben. Steht "
                            f"der Ordner „{ordner}“ zur Verfuegung?",
                            Style.ERROR)
            return
        self._rohmelden(f"{len(blatt)} Zeilen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)

    def _aenderungen_speichern(self):
        """Die von Hand geaenderten Werte als Blatt - zum Ansehen und Drucken."""
        geaendert = self.aenderungen()
        if not geaendert:
            self._rohmelden("Es ist nichts von Hand geaendert.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        pfad = trdfexport.blatt_schreiben(ordner, self.v_serie.get().strip(),
                                          geaendert, dt.datetime.now())
        if not pfad:
            self._rohmelden(f"Die Datei liess sich nicht schreiben. Steht "
                            f"der Ordner „{ordner}“ zur Verfuegung?",
                            Style.ERROR)
            return
        self._rohmelden(f"{len(geaendert)} Aenderungen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)

    def _rohmelden(self, text, farbe=Style.MUTED):
        self.rohstand.config(text=text, fg=farbe)

    def _lims_schreiben(self):
        """Zeigt, was geschrieben wuerde - geschrieben wird erst danach."""
        zugang = self._zugang_holen()
        if zugang is None:
            self._melden("Erst anmelden.", Style.WARN)
            return
        geaendert = self.aenderungen()
        if not geaendert:
            self._melden("Es ist nichts von Hand geaendert - es gibt nichts "
                         "zu schreiben.", Style.WARN)
            return
        Exportvorschau(self, geaendert, self.v_serie.get().strip(),
                       lambda: self._wirklich_schreiben(geaendert))

    def _anhang_angleichen(self):
        """Den Teilprobenanhang auf den Stand der Ergebniszeile bringen.

        Der Fall, fuer den es diesen Weg gibt: eine Korrektur ist nur an
        einer der beiden Stellen angekommen - aus einer aelteren
        Sicherung zurueckgespielt etwa, die keine ROHW_ID trug. Dann
        steht in der Ergebnistabelle die eine Zahl und in der Rechnung
        des LIMS die andere. Geschrieben wird nur der Anhang; die
        Ergebniszeile gilt und bleibt, wie sie ist.
        """
        zugang = self._zugang_holen()
        if zugang is None:
            self._rohmelden("Erst anmelden.", Style.WARN)
            return
        geaendert = self.auseinander()
        if not geaendert:
            self._rohmelden("Ergebniszeile und Teilprobenanhang stimmen "
                            "ueberein.", Style.TEXT)
            return
        Exportvorschau(self, geaendert, self.v_serie.get().strip(),
                       lambda: self._anhang_schreiben(geaendert),
                       nur_anhang=True)

    def _anhang_schreiben(self, geaendert):
        """Erst die Sicherung, dann der Anhang - wie ueberall hier."""
        zugang = self._zugang_holen()
        if zugang is None:
            return
        serie = self.v_serie.get().strip()
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        sicherung = trdfexport.backup_schreiben(ordner, serie, geaendert,
                                                dt.datetime.now())
        if not sicherung:
            self._melden(f"Ohne Sicherung wird nichts geschrieben. Der "
                         f"Ordner „{ordner}“ liess sich nicht anlegen.",
                         Style.ERROR)
            return
        anhang = trdfexport.anhangsaetze(geaendert)
        hinweise = trdfexport.anhanghinweise(geaendert, serie)
        self._melden(f"Sicherung: {sicherung}  |  {len(anhang)} Rohwerte am "
                     f"Anhang werden angeglichen ...")
        self.update_idletasks()

        def arbeit():
            # Ohne Ergebnissaetze: die Ergebniszeile ist die Vorlage und
            # wird nicht angefasst.
            return lims_db.trdf_exportieren(zugang, [], None, anhang,
                                            hinweise)

        def fertig(bericht):
            trdfexport.protokollieren(ordner,
                                      getattr(zugang, "benutzer", ""),
                                      anhang, hinweise,
                                      sql=lims_db.trdf_anhang_sql())
            getroffen = bericht.get("anhang_geschrieben", 0)
            fehlt = len(bericht.get("anhang_ohne_zeile", ()))
            offen = len(bericht.get("anhang_nicht_uebernommen", ()))
            satz = (f"{getroffen} Rohwerte am Teilprobenanhang angeglichen"
                    f"  |  Sicherung: {sicherung}")
            if fehlt:
                satz += f"  |  {fehlt} Zeilen nicht gefunden"
            if offen:
                satz += f"  |  {offen} stehen danach noch wie vorher da"
            self._melden(satz, Style.ERROR if offen
                         else Style.WARN if fehlt else Style.TEXT)
            (messagebox.showerror if offen else
             messagebox.showwarning if fehlt else messagebox.showinfo)(
                "Teilprobenanhang angeglichen", satz, parent=self)
            self._abrufen()      # der Stand im Fenster gilt nicht mehr

        self._im_hintergrund(arbeit, fertig, self._schreiben_schiefgegangen)

    def _zurueckspielen(self):
        """Den Stand vor einer Korrektur wiederherstellen.

        Es gibt einen Weg, der ueberschreibt - also muss es einen zurueck
        geben. Gelesen wird die Sicherung, die damals angelegt wurde;
        geschrieben wird erst nach derselben bestaetigten Uebersicht.
        """
        zugang = self._zugang_holen()
        if zugang is None:
            self._melden("Erst anmelden.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        pfad = filedialog.askopenfilename(
            parent=self, title="Sicherung waehlen",
            initialdir=ordner if os.path.isdir(ordner) else self._ordner,
            filetypes=[("Sicherung", "*.csv"), ("Alle Dateien", "*.*")])
        if not pfad:
            return
        try:
            zeilen = trdfexport.gesichertes_lesen(pfad)
        except (trdfexport.Einlesefehler, OSError) as fehler:
            self._melden(str(fehler), Style.ERROR)
            return
        geaendert = trdfexport.zurueck(zeilen)
        if not geaendert:
            self._melden("In dieser Sicherung steht keine Zeile.", Style.WARN)
            return
        Exportvorschau(self, geaendert, os.path.basename(pfad),
                       lambda: self._zurueck_schreiben(geaendert, pfad),
                       zurueck=True)

    def _zurueck_schreiben(self, geaendert, pfad: str):
        """Schreibt den gesicherten Stand - beide Stellen, eine Transaktion."""
        zugang = self._zugang_holen()
        if zugang is None:
            return
        name = os.path.basename(pfad)
        saetze = trdfexport.zuruecksaetze(geaendert)
        anhang = trdfexport.zurueck_anhangsaetze(geaendert)
        hinweise = trdfexport.zurueckhinweise(geaendert, name)
        self._melden(f"{len(saetze)} Zeilen werden aus {name} "
                     f"zurueckgespielt ...")
        self.update_idletasks()

        def arbeit():
            return lims_db.trdf_exportieren(zugang, saetze, hinweise, anhang,
                                            hinweise, zurueck=True)

        def fertig(bericht):
            ordner = os.path.join(self._ordner, trdfexport.ORDNER)
            benutzer = getattr(zugang, "benutzer", "")
            # Beide Anweisungen in den Log - der Anhang gehoert genauso
            # dazu wie die Ergebniszeile, sonst steht dort die halbe
            # Wahrheit ueber das, was geschehen ist.
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
            # Der Exportbericht stimmt jetzt nicht mehr: was er zeigt,
            # ist gerade zurueckgenommen worden.
            self._bericht_verworfen(name)
            self._melden(satz, Style.WARN if fehlt else Style.TEXT)
            (messagebox.showwarning if fehlt else messagebox.showinfo)(
                "Sicherung zurueckgespielt", satz, parent=self)
            self._abrufen()          # der Stand im Fenster gilt nicht mehr

        self._im_hintergrund(arbeit, fertig, self._schreiben_schiefgegangen)

    def _wirklich_schreiben(self, geaendert):
        """Erst die Sicherung, dann die Datenbank - in dieser Reihenfolge."""
        zugang = self._zugang_holen()
        if zugang is None:
            return
        serie = self.v_serie.get().strip()
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        sicherung = trdfexport.backup_schreiben(ordner, serie, geaendert,
                                                dt.datetime.now())
        if not sicherung:
            self._melden(f"Ohne Sicherung wird nichts geschrieben. Der "
                         f"Ordner „{ordner}“ liess sich nicht anlegen.",
                         Style.ERROR)
            return
        saetze = trdfexport.saetze(geaendert)
        hinweise = trdfexport.hinweise(geaendert, serie)
        anhang = trdfexport.anhangsaetze(geaendert)
        anhanghinweise = trdfexport.anhanghinweise(geaendert, serie)
        self._melden(f"Sicherung: {sicherung}  |  {len(saetze)} Zeilen "
                     f"und {len(anhang)} Rohwerte am Anhang werden "
                     f"geschrieben ...")
        self.update_idletasks()

        def arbeit():
            # Geleert werden darf: die Uebersicht davor hat gesagt, wie
            # viele Werte es trifft, und die Sicherung liegt schon.
            return lims_db.trdf_exportieren(zugang, saetze, hinweise,
                                            anhang, anhanghinweise,
                                            leeren=True)

        def fertig(bericht):
            self._geschrieben(geaendert, bericht, sicherung)

        self._im_hintergrund(arbeit, fertig, self._schreiben_schiefgegangen)

    def _geschrieben(self, geaendert, bericht: dict, sicherung: str):
        """Uebernimmt den neuen Stand in die Anzeige und meldet ihn."""
        fehlend = {(satz["prob_id"], satz["pm_id"], satz["pm_ver"])
                   for satz in bericht["ohne_zeile"]}
        gescheitert = self._gescheitert(geaendert, bericht)
        angekommen = [eine for eine in geaendert
                      if eine.get("zeile") and eine not in gescheitert and
                      (eine["zeile"]["prob_id"], eine["zeile"]["pm_id"],
                       eine["zeile"]["pm_ver"]) not in fehlend]
        self._mitschreiben(angekommen)
        for eine in angekommen:
            self._uebernommen(eine)
        self._rechnung_vergessen()
        self._zeigen()
        # Der Bericht haelt fest, was angekommen ist - nicht, was
        # geschickt wurde. Was steckengeblieben ist, steht daneben.
        self._bericht_merken(angekommen, self.v_serie.get().strip(),
                             sicherung, gescheitert)
        getroffen = bericht["geschrieben"]
        am_anhang = bericht.get("anhang_geschrieben", 0)
        fehlend = (len(bericht["ohne_zeile"])
                   + len(bericht.get("anhang_ohne_zeile", ())))
        satz = (f"{getroffen} Ergebniszeilen und {am_anhang} Rohwerte am "
                f"Anhang geschrieben  |  Sicherung: {sicherung}")
        if fehlend:
            satz += f"  |  {fehlend} Zeilen im LIMS nicht gefunden"
        if gescheitert:
            satz += (f"  |  {len(gescheitert)} Werte stehen danach noch "
                     f"wie vorher da")
        self._melden(satz, Style.ERROR if gescheitert
                     else Style.WARN if fehlend else Style.TEXT)
        if gescheitert:
            self._nicht_uebernommen(gescheitert, sicherung)
            return
        self._gemeldet(getroffen, am_anhang, fehlend, sicherung)

    def _nicht_uebernommen(self, gescheitert, sicherung: str):
        """Die Meldung, die nach dem Nachlesen wirklich zaehlt."""
        namen = ", ".join(f"{eine.get('probe')} {eine['kuerzel']}"
                          for eine in gescheitert[:12])
        if len(gescheitert) > 12:
            namen += f" und {len(gescheitert) - 12} weitere"
        messagebox.showerror(
            "Update fehlgeschlagen",
            f"{len(gescheitert)} Werte stehen in der Datenbank nach dem "
            "Schreiben immer noch so da wie vorher.\n\nDie Anweisung lief "
            "durch, die Zeilen gibt es, und geschrieben wurde trotzdem "
            "nichts - das deutet auf einen Ausloeser, ein fehlendes Recht "
            "oder eine Sicht statt einer Tabelle hin. Der Stand im Fenster "
            "bleibt deshalb unveraendert.\n\n"
            f"Betroffen: {namen}\n\nWas geschickt wurde, steht im "
            f"Korrekturlog neben der Sicherung:\n{sicherung}", parent=self)

    def _gemeldet(self, getroffen: int, am_anhang: int, fehlend: int,
                  sicherung: str):
        """Sagt es auch im Fenster - nicht nur in der Statuszeile.

        Ein Schreibweg, der still bleibt, laesst offen, ob er etwas
        getan hat. Vor allem der Fall "keine Zeile getroffen" faellt
        sonst niemandem auf: die Anweisung war fehlerfrei, sie hat nur
        nichts gefunden.
        """
        satz = (f"{getroffen} Ergebniszeilen und {am_anhang} Rohwerte am "
                f"Teilprobenanhang wurden geschrieben und festgeschrieben "
                f"(COMMIT).\n\nDie Sicherung liegt unter:\n{sicherung}")
        if fehlend:
            satz += (f"\n\n{fehlend} Zeilen wurden im LIMS nicht gefunden "
                     "und deshalb nicht geschrieben.")
        if not getroffen and not am_anhang:
            messagebox.showwarning(
                "Es wurde nichts geschrieben",
                "Keine einzige Zeile wurde getroffen. Die Anweisung lief "
                "fehlerfrei durch, hat aber im LIMS nichts gefunden - der "
                "Schluessel aus PROB_ID, PM_ID, PM_VER, UM_ID und GEGR_ID "
                "passt dort auf keine Zeile.\n\nWas geschickt wurde, "
                "steht im Aenderungsprotokoll und im Korrekturlog neben "
                f"der Sicherung:\n{sicherung}", parent=self)
            return
        (messagebox.showwarning if fehlend else messagebox.showinfo)(
            "In das LIMS geschrieben", satz, parent=self)

    def _mitschreiben(self, angekommen):
        """Der Korrekturlog neben den Sicherungen - die letzten 5000.

        Das Aenderungsprotokoll neben dem Programm fuehrt ohnehin jede
        Anweisung. Dieser Log steht dort, wo auch der alte Stand liegt,
        und beantwortet die engere Frage: was hat die TRDF-Pruefung in
        diese Datenbank geschrieben?
        """
        if not angekommen:
            return
        zugang = self._zugang_holen()
        ordner = os.path.join(self._ordner, trdfexport.ORDNER)
        benutzer = getattr(zugang, "benutzer", "")
        serie = self.v_serie.get().strip()
        trdfexport.protokollieren(ordner, benutzer,
                                  trdfexport.saetze(angekommen),
                                  trdfexport.hinweise(angekommen, serie))
        trdfexport.protokollieren(ordner, benutzer,
                                  trdfexport.anhangsaetze(angekommen),
                                  trdfexport.anhanghinweise(angekommen, serie),
                                  sql=lims_db.trdf_anhang_sql())

    def ergebnisblatt(self) -> tuple:
        """Die berechneten Groessen, wie sie dastehen: (Kopf, Zeilen).

        Gelesen wird aus der Tabelle selbst - mit ihrer Spaltenordnung
        und den Ueberschriften, die unter \u201eInfo\u201c gewaehlt sind -,
        damit im Blatt steht, was auf dem Schirm stand.
        """
        tabelle = self._aktuell(self.ergebnistabelle)
        spalten = tabelle.spalten()
        kopf = [" ".join(tabelle.ueberschriftzeilen(name)) or name
                for name in spalten]
        zeilen = [[tabelle.wert(kennung, name).strip() for name in spalten]
                  for kennung in tabelle.zeilen()]
        return kopf, zeilen

    def _ergebnisblatt_speichern(self):
        """Die berechneten Groessen als CSV ablegen und oeffnen."""
        kopf, zeilen = self.ergebnisblatt()
        if not zeilen:
            self._melden("Es ist keine Serie abgerufen.", Style.WARN)
            return ""
        serie = self.v_serie.get().strip() or "Serie"
        ordner = os.path.join(self._ordner, trdfpruefung.ORDNER)
        name = "".join(zeichen for zeichen in serie
                       if zeichen.isalnum() or zeichen in " _-.") or "Serie"
        pfad = os.path.join(ordner, f"Ergebnisse {name}.csv")
        inhalt = lims_db.csv_bloecke([(
            f"Berechnete Groessen - Serie {serie} - {self.um_kuerzel}",
            kopf, zeilen)])
        try:
            os.makedirs(ordner, exist_ok=True)
            with open(pfad, "wb") as datei:
                datei.write(inhalt)
        except OSError:
            self._melden(f"Die Datei liess sich nicht schreiben. Steht der "
                         f"Ordner \u201e{ordner}\u201c zur Verfuegung?",
                         Style.ERROR)
            return ""
        self._melden(f"{len(zeilen)} Zeilen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)
        return pfad

    def _blatt_speichern(self):
        """Legt das Pruefblatt als CSV ab und oeffnet es."""
        blatt = self.geprueft()
        if not blatt:
            self._pruefmelden("Es ist keine Serie abgerufen.", Style.WARN)
            return
        ordner = os.path.join(self._ordner, trdfpruefung.ORDNER)
        pfad = trdfpruefung.schreiben(ordner, self.v_serie.get().strip(),
                                      blatt, self.um_kuerzel)
        if not pfad:
            self._pruefmelden(
                f"Die Datei liess sich nicht schreiben. Steht der Ordner "
                f"„{ordner}“ zur Verfuegung?", Style.ERROR)
            return
        self._pruefmelden(f"{len(blatt)} Zeilen  |  {pfad}", Style.TEXT)
        trdfpruefung.oeffnen(pfad)


class Einfuegefenster(tk.Toplevel):
    """Die Liste aus der Probenvorbereitung - in einem eigenen Fenster.

    Gross, damit die Liste ganz zu sehen ist, und ausserhalb der Seite,
    damit sie den Tabellen keinen Platz nimmt. Was hier steht, bleibt
    liegen, wenn das Fenster zugeht, und steht beim naechsten Oeffnen
    wieder da.
    """

    def __init__(self, seite):
        super().__init__(seite)
        self.seite = seite
        serie = seite.v_serie.get().strip()
        self.title("UM einfuegen"
                   + (f" - Serie {serie}" if serie else ""))
        self.configure(bg=Style.BG)
        self.geometry("1200x720")
        self.minsize(600, 300)
        try:
            self.transient(seite.winfo_toplevel())
        except tk.TclError:
            pass
        kopf = tk.Frame(self, bg=Style.BG)
        kopf.pack(fill="x", padx=10, pady=(8, 4))
        self.hinweis = tk.Label(kopf, text=getattr(seite, "quellhinweis", ""),
                                bg=Style.BG, fg=Style.MUTED,
                                font=Style.font(9), anchor="w",
                                justify="left")
        self.hinweis.pack(side="left", fill="x", expand=True)
        # Der Hinweis bricht an der Fensterbreite um, statt abzureissen.
        kopf.bind("<Configure>", lambda e: self.hinweis.config(
            wraplength=max(200, e.width - 10)))
        knoepfe = tk.Frame(self, bg=Style.BG)
        knoepfe.pack(side="bottom", fill="x", padx=10, pady=8)
        RoundedButton(knoepfe, text="Uebernehmen", width=150, height=32,
                      bg="#15803d", command=self._uebernehmen).pack(
            side="left")
        RoundedButton(knoepfe, text="Leeren", width=110, height=32,
                      bg="#6b7268", command=seite._text_leeren).pack(
            side="left", padx=(8, 0))
        RoundedButton(knoepfe, text="Schliessen", width=130, height=32,
                      bg="#334155", command=self._schliessen).pack(
            side="right")
        rahmen = tk.Frame(self, bg=Style.BG)
        rahmen.pack(fill="both", expand=True, padx=10)
        self.textfeld = tk.Text(rahmen, wrap="none", font=("Consolas", 11),
                                bg=Style.CARD, fg=Style.TEXT, undo=True,
                                highlightbackground=Style.BORDER,
                                highlightthickness=1)
        senkrecht = tk.Scrollbar(rahmen, orient="vertical",
                                 command=self.textfeld.yview)
        waagerecht = tk.Scrollbar(rahmen, orient="horizontal",
                                  command=self.textfeld.xview)
        self.textfeld.configure(yscrollcommand=senkrecht.set,
                                xscrollcommand=waagerecht.set)
        self.textfeld.grid(row=0, column=0, sticky="nsew")
        senkrecht.grid(row=0, column=1, sticky="ns")
        waagerecht.grid(row=1, column=0, sticky="we")
        rahmen.grid_rowconfigure(0, weight=1)
        rahmen.grid_columnconfigure(0, weight=1)
        self.textfeld.insert("1.0", getattr(seite, "_einfuegetext", "")
                             .rstrip("\n"))
        self.textfeld.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._schliessen)
        self.bind("<Escape>", lambda e: self._schliessen())

    def _uebernehmen(self):
        """Lesen und rechnen - und bei Erfolg zugehen."""
        if self.seite._text_uebernehmen():
            self._schliessen()

    def _schliessen(self):
        self.seite._einfuegetext = self.textfeld.get("1.0", "end")
        self.destroy()


class Grossansicht(tk.Toplevel):
    """Die Rohwerte in einem eigenen, grossen Fenster.

    Dieselbe Tabelle wie im Reiter, nur mit doppelter Zeilenhoehe und
    fast nichts drumherum: wer eine Serie eintippt, sieht die Zahlen und
    sonst wenig. Sie ist keine Kopie - es ist eine zweite Ansicht
    desselben Standes. Was hier getippt wird, steht im selben Augenblick
    auch im Reiter, und was dort steht, steht auch hier.

    Alles geht wie im Reiter: Tabulator und Pfeile wechseln die Zelle,
    ein aus Excel kopierter Block laeuft von der offenen Zelle nach
    unten und rechts, der Klick auf die Probennummer oeffnet ihren
    Bodenblock - und der liegt ueber diesem Fenster, nicht dahinter.
    """

    def __init__(self, seite):
        super().__init__(seite)
        self.seite = seite
        serie = seite.v_serie.get().strip()
        self.title(f"Rohwerte gross - {serie}" if serie
                   else "Rohwerte gross")
        self.configure(bg=Style.BG)
        self._maximieren()

        leiste = tk.Frame(self, bg=Style.BG)
        leiste.pack(fill="x", padx=10, pady=(8, 6))
        knopf = RoundedButton(leiste, text="Speichern", width=140, height=30,
                              bg="#166534", command=self._schliessen)
        knopf.pack(side="left")
        ToolTip(knopf,
                "Schliesst dieses Fenster. Die Werte stehen dann im\n"
                "Reiter - sie stehen dort ohnehin schon, denn beide\n"
                "Ansichten zeigen denselben Stand. In das LIMS\n"
                "geschrieben wird weiter nur mit dem gruenen Knopf\n"
                "oben im Hauptfenster.")
        Infozeichen(leiste, "Tastenkuerzel\n\n" + TASTEN,
                    dezent=True).pack(side="left", padx=(10, 0))
        self.stand = tk.Label(leiste, text="", bg=Style.BG, fg=Style.MUTED,
                              font=Style.font(9), anchor="w")
        self.stand.pack(side="left", padx=(14, 0))

        self.tabelle = eingaberaster.Eingaberaster(
            self, hoehe=GROSS_ZEILEN, schriftgroesse=GROSS_SCHRIFT,
            zeilenluft=GROSS_LUFT,
            bei_aenderung=seite._von_hand_geaendert,
            bei_klick=self._angeklickt,
            bei_block=seite._block_eingefuegt,
            bei_zeile=seite._arbeitszeile_setzen,
            bei_fuellen=seite.leere_fuellen,
            ist_leer=seite.ist_leer,
            bei_nach_unten=seite._nach_unten_eingefuegt)
        self.tabelle.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        seite.rohansicht_anmelden(self.tabelle)
        # Erst wenn das Fenster seine Masse hat, weiss die Tabelle, wo
        # ihre Zellen liegen - und erst dann findet das Eingabefeld die
        # Zelle, auf die es sich legen soll.
        self.update_idletasks()
        self.stand.config(text=f"{len(seite.proben)} Proben  |  "
                               f"{len(seite.rohliste)} Rohwerte")
        self.protocol("WM_DELETE_WINDOW", self._schliessen)
        self.bind("<Escape>", lambda ereignis: self._schliessen())

    def _maximieren(self):
        """So gross, wie der Bildschirm es hergibt.

        Unter Windows ist das "zoomed"; wo der Fenstermanager das nicht
        kennt, wird der Bildschirm ausgemessen. Beides kann scheitern -
        dann steht das Fenster eben in normaler Groesse da, und das ist
        kein Grund, es gar nicht zu zeigen.
        """
        try:
            self.state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            self.geometry(f"{self.winfo_screenwidth()}x"
                          f"{self.winfo_screenheight()}+0+0")
        except tk.TclError:
            pass

    def _angeklickt(self, zeile, spalte):
        """Der Bodenblock gehoert ueber dieses Fenster."""
        self.seite._block_zeigen(zeile, spalte, ueber=self)

    def _schliessen(self):
        self.seite.rohansicht_abmelden(self.tabelle)
        self.destroy()


class Exportvorschau(tk.Toplevel):
    """Was in das LIMS geschrieben wuerde - Zeile fuer Zeile, alt und neu.

    Der Riegel vor dem einzigen Weg, der einen Messwert ueberschreibt.
    Er zeigt jede betroffene Zeile mit ihrer Pruefmethode, dem Stand im
    LIMS und dem, was an seine Stelle traete. Erst der gruene Knopf
    schreibt - und auch der erst, nachdem der alte Stand gesichert ist.
    """

    def __init__(self, eltern, aenderungen, serie: str, wenn_ja,
                 zurueck=False, nur_anhang=False):
        super().__init__(eltern)
        self.title(("Load backup - " if zurueck
                    else "Teilprobenanhang angleichen - Serie " if nur_anhang
                    else "Export in das LIMS - Serie ") + serie)
        self.configure(bg=Style.BG)
        self.geometry("1180x580")
        self.aenderungen = list(aenderungen)
        self._wenn_ja = wenn_ja

        tk.Label(self, text=f"{len(self.aenderungen)} Werte werden "
                            f"ueberschrieben", bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(12, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(14, 2))
        hinweis = vorschauhinweis(self.aenderungen, zurueck, nur_anhang)
        wieder = [] if zurueck or nur_anhang else trdfexport.schon_korrigiert(
            self.aenderungen)
        tk.Label(self, text=hinweis, bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(9), anchor="w", justify="left",
                 wraplength=960).pack(fill="x", padx=16, pady=(0, 10))

        rahmen = tk.Frame(self, bg=Style.CARD,
                          highlightbackground=Style.BORDER,
                          highlightthickness=1)
        rahmen.pack(fill="both", expand=True, padx=16)
        self.baum = ttk.Treeview(rahmen, show="headings",
                                 columns=list(trdfexport.SPALTEN))
        senkrecht = ttk.Scrollbar(rahmen, orient="vertical",
                                  command=self.baum.yview)
        # Zehn Spalten passen nicht in jedes Fenster, und gerade die
        # letzte - der neue Wert - ist die, um die es geht. Ohne Leiste
        # waere sie auf einem kleinen Bildschirm einfach weg.
        waagerecht = ttk.Scrollbar(rahmen, orient="horizontal",
                                   command=self.baum.xview)
        self.baum.configure(yscrollcommand=senkrecht.set,
                            xscrollcommand=waagerecht.set)
        self.baum.grid(row=0, column=0, sticky="nsew")
        senkrecht.grid(row=0, column=1, sticky="ns")
        waagerecht.grid(row=1, column=0, sticky="we")
        rahmen.grid_rowconfigure(0, weight=1)
        rahmen.grid_columnconfigure(0, weight=1)
        breiten = {"Zeile": 56, "Probe-Nr.": 104, "Groesse": 110,
                   "Art": 80, "Pruefmethode": 190, "PM_ID": 70,
                   "PM_VER": 70, "Ziel": 150, "Wert aktuell LIMS": 150,
                   "Wert neu": 150}
        for name in trdfexport.SPALTEN:
            self.baum.heading(name, text=name)
            self.baum.column(name, width=breiten.get(name, 100), minwidth=50,
                             stretch=False)
        self.baum.tag_configure("ohne", background="#fef3c7")
        self.baum.tag_configure("wieder", background="#ede9fe")
        schon = {id(eine) for eine in wieder}
        for nummer, (eine, zeile) in enumerate(
                zip(self.aenderungen,
                    trdfexport.uebersicht(self.aenderungen,
                                          trdfpruefung.stellen_fuer))):
            if not eine.get("zeile"):
                marke = ("ohne",)
            elif id(eine) in schon:
                marke = ("wieder",)
            else:
                marke = ()
            self.baum.insert("", "end", iid=str(nummer), values=zeile,
                             tags=marke)

        knoepfe = tk.Frame(self, bg=Style.BG)
        knoepfe.pack(fill="x", padx=16, pady=12)
        RoundedButton(knoepfe, text="Abbrechen", width=130, height=32,
                      bg="#6b7268", command=self.destroy).pack(side="right")
        self.knopf_ja = RoundedButton(
            knoepfe, text="Zurueckspielen" if zurueck
            else "Sichern und schreiben", width=210, height=32,
            bg="#15803d", command=self._schreiben)
        self.knopf_ja.pack(side="right", padx=(0, 10))
        self.bind("<Escape>", lambda e: self.destroy())

    def _schreiben(self):
        self.destroy()
        self._wenn_ja()


class Bildfenster(tk.Toplevel):
    """Das Streubild einer Serie - ein Klick auf einen Punkt oeffnet ihn."""

    def __init__(self, eltern, serie: str, punkte, bei_klick=None):
        super().__init__(eltern)
        self.title(f"Trockenrohdichte ueber Kohlenstoff - Serie {serie}")
        self.configure(bg=Style.BG)
        self.resizable(False, False)
        self._bei_klick = bei_klick
        tk.Label(self, text=f"Serie {serie}  ·  {len(punkte)} Proben",
                 bg=Style.BG, fg=Style.TEXT, font=Style.font(11, "bold"),
                 anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(self,
                 text="Jede Probe ein Punkt, der Sollbereich ihrer "
                      "Kohlenstoffklasse als Band dahinter: das dunklere "
                      "gilt ohne Carbonat, das hellere mit. Rot liegt "
                      "ausserhalb, violett wurde von Hand bewegt, grau hat "
                      "keinen Aufschluss und steht am linken Rand. Ein "
                      "Klick auf einen Punkt oeffnet seinen Bodenblock.",
                 bg=Style.BG, fg=Style.MUTED, font=Style.font(9), anchor="w",
                 justify="left", wraplength=700).pack(
            fill="x", padx=16, pady=(0, 10))
        self.bild = trdfbild.Streubild(self, bei_klick=self._punkt_geklickt)
        self.bild.pack(padx=16)
        self.stand = tk.Label(self, text="", bg=Style.BG, fg=Style.MUTED,
                              font=Style.font(9), anchor="w")
        self.stand.pack(fill="x", padx=16, pady=(8, 14))
        self.bild.zeichnen(punkte)
        self.bind("<Escape>", lambda e: self.destroy())

    def _punkt_geklickt(self, probe):
        self.stand.config(text=f"Probe {probe}")
        if self._bei_klick is not None:
            self._bei_klick(probe, "Probe-Nr.")
