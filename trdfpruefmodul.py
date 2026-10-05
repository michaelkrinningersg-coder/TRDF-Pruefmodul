"""
TRDF-Pruefmodul - Einzelauswertung einer TRDF-Serie (Tkinter)
=============================================================

Die TRDF-Pruefung aus LabControl (TestLims) als eigenes Programm: anmelden,
eine Serie waehlen, ihre TRDF-Untersuchungsmethoden abfragen, eine davon
waehlen - und dann nachrechnen, pruefen, Rohwerte von Hand aendern und die
Korrektur in das LIMS zurueckschreiben.

Was gegenueber dem Reiter in LabControl fehlt, fehlt mit Absicht: keine
Profilansichten, kein Plotvergleich, kein Abruf einzelner Probennummern.
Der Bodenblock beim Klick auf die Probe ist geblieben.

Anmeldung wie in LabControl - Oracle-Benutzer, Passwort, Datenbank -, nur
dass die Datenbank LIMS ist und nichts anderes. Der Connect-Deskriptor
kommt aus der tnsnames.ora (siehe lims_db.py).

Startpunkt: `python trdfpruefmodul.py`  (bzw. die gebaute
TRDF-Pruefmodul-x86.exe). Zugangsdaten leben nur im Arbeitsspeicher,
solange die Anwendung laeuft.
"""

import os
import sys
import threading
import tkinter as tk
import traceback
from tkinter import messagebox, ttk

import lims_db
import protokoll
import trdfreiter
from config import Config
from widgets import RoundedButton, Style, apply_window_icon, maximieren

APP_TITLE = "TRDF-Pruefmodul - NW-FVA"
APP_VERSION = "v1.0"


def beschriftetes_feld(eltern, beschriftung, variable, spalte, zeige_stern=False,
                       breite=18):
    """Legt Label und Eingabefeld untereinander in eine Rasterspalte."""
    tk.Label(eltern, text=beschriftung, bg=eltern["bg"], fg=Style.MUTED,
             font=Style.font(9)).grid(row=0, column=spalte, sticky="w", padx=(0, 12))
    feld = ttk.Entry(eltern, textvariable=variable, width=breite,
                     show="*" if zeige_stern else "")
    feld.grid(row=1, column=spalte, sticky="we", padx=(0, 12), pady=(2, 0))
    eltern.grid_columnconfigure(spalte, weight=1)
    return feld


def zulaessige_datenbank(gemerkt) -> str:
    """Die Datenbank fuer das Auswahlfeld - nur eine zugelassene.

    In einer alten Einstellungsdatei kann LIMSTEST stehen; das Feld zeigt
    dann trotzdem LIMS, statt eine Wahl vorzuschlagen, die es nicht gibt.
    """
    name = str(gemerkt or "").strip().upper()
    return name if name in lims_db.DATENBANKEN else lims_db.DATENBANKEN[0]


class PruefmodulAnwendung(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} {APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(900, 600)
        self.configure(bg=Style.BG)
        apply_window_icon(self)
        self._stile_setzen()
        maximieren(self)

        self.konfig = Config()
        self.zugang = None
        self.trdf_seite = None

        # Bei --windowed gibt es keine Konsole; ein unbehandelter Fehler waere
        # sonst unsichtbar und die App scheinbar einfach "kaputt".
        self.report_callback_exception = self._unerwarteter_fehler

        self.rahmen = tk.Frame(self, bg=Style.BG)
        self.rahmen.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._beenden)
        self.anmeldemaske()

    # ----------------------------------------------------------------- Stil
    def _stile_setzen(self):
        stil = ttk.Style(self)
        try:
            stil.theme_use("clam")
        except tk.TclError:
            pass
        stil.configure("Treeview", background=Style.CARD, fieldbackground=Style.CARD,
                       foreground=Style.TEXT, rowheight=28, font=Style.font(10),
                       bordercolor=Style.BORDER)
        stil.configure("Treeview.Heading", background="#e2e8f0", foreground=Style.TEXT,
                       font=Style.font(9, "bold"), relief="flat")
        stil.map("Treeview", background=[("selected", Style.ACCENT)],
                 foreground=[("selected", Style.ACCENT_FG)])
        stil.configure("TEntry", fieldbackground="#ffffff", bordercolor=Style.BORDER)
        stil.configure("TNotebook", background=Style.BG, borderwidth=0)
        stil.configure("TNotebook.Tab", padding=(18, 8), font=Style.font(10),
                       background="#e2e8f0", foreground=Style.MUTED)
        # Ohne diese Zuordnung ist im clam-Thema kaum zu sehen, welcher Reiter
        # gerade offen ist.
        stil.map("TNotebook.Tab",
                 background=[("selected", Style.CARD)],
                 foreground=[("selected", Style.ACCENT)],
                 font=[("selected", Style.font(10, "bold"))])
        stil.map("TCombobox", fieldbackground=[("readonly", "#ffffff")],
                 background=[("readonly", "#ffffff")])
        stil.configure("TCheckbutton", background=Style.BG, foreground=Style.TEXT,
                       font=Style.font(9), focuscolor=Style.BG)
        stil.map("TCheckbutton", background=[("active", Style.BG)],
                 indicatorcolor=[("selected", Style.ACCENT)])

    def _unerwarteter_fehler(self, art, wert, spur):
        traceback.print_exception(art, wert, spur)
        messagebox.showerror(
            "Unerwarteter Fehler",
            f"{wert}\n\nDie Anwendung laeuft weiter. Wenn der Fehler bleibt, "
            f"bitte diese Meldung weitergeben.",
            parent=self)

    def _leeren(self):
        for kind in self.rahmen.winfo_children():
            kind.destroy()

    # ------------------------------------------------- Arbeit im Hintergrund
    def im_hintergrund(self, arbeit, fertig, wenn_fehler=None, warten_auf=None):
        """Fuehrt eine Datenbankoperation in einem Thread aus.

        Ohne das friert das Fenster waehrend jeder Abfrage ein - im Netz kann
        eine Oracle-Antwort mehrere Sekunden dauern. Die Rueckgabe wird per
        after() wieder im Tk-Thread zugestellt, weil Tkinter nur von dort
        bedient werden darf.
        """
        if warten_auf is not None:
            warten_auf.config(state="disabled")
            self.config(cursor="watch")

        def freigeben():
            if warten_auf is not None:
                warten_auf.config(state="normal")
                self.config(cursor="")

        def lauf():
            try:
                ergebnis = arbeit()
            except Exception as fehler:
                self.after(0, lambda f=fehler: (freigeben(), (wenn_fehler or
                                                self.fehler_zeigen)(f)))
                return
            self.after(0, lambda e=ergebnis: (freigeben(), fertig(e)))

        threading.Thread(target=lauf, daemon=True).start()

    def fehler_zeigen(self, fehler):
        messagebox.showerror("Datenbankfehler", lims_db.fehlertext(fehler),
                             parent=self)

    # =====================================================================
    # Anmeldung
    # =====================================================================
    def anmeldemaske(self):
        self._leeren()
        aussen = tk.Frame(self.rahmen, bg=Style.BG)
        aussen.place(relx=0.5, rely=0.42, anchor="center")

        tk.Label(aussen, text="TRDF-Pruefmodul", bg=Style.BG, fg=Style.TEXT,
                 font=Style.font(20, "bold")).pack(anchor="w")
        tk.Label(aussen, text="Anmeldung an der Oracle-Datenbank der NW-FVA",
                 bg=Style.BG, fg=Style.MUTED,
                 font=Style.font(10)).pack(anchor="w", pady=(0, 18))

        karte = tk.Frame(aussen, bg=Style.CARD, highlightbackground=Style.BORDER,
                         highlightthickness=1, padx=26, pady=22)
        karte.pack()

        self.v_benutzer = tk.StringVar(value=self.konfig.get("benutzer"))
        self.v_passwort = tk.StringVar()
        self.v_alias = tk.StringVar(
            value=zulaessige_datenbank(self.konfig.get("alias")))

        raster = tk.Frame(karte, bg=Style.CARD)
        raster.pack(fill="x")
        feld_benutzer = beschriftetes_feld(raster, "Oracle-Benutzer",
                                           self.v_benutzer, 0, breite=22)
        feld_passwort = beschriftetes_feld(raster, "Passwort", self.v_passwort, 1,
                                           zeige_stern=True, breite=22)

        tk.Label(raster, text="Datenbank", bg=Style.CARD, fg=Style.MUTED,
                 font=Style.font(9)).grid(row=0, column=2, sticky="w")
        # Nur LIMS: das Pruefmodul schreibt Korrekturen, und eine zweite
        # Datenbank in der Liste waere eine Gelegenheit, in die falsche
        # zu schreiben.
        self.feld_alias = ttk.Combobox(raster, textvariable=self.v_alias,
                                       state="readonly",
                                       values=list(lims_db.DATENBANKEN),
                                       width=12)
        self.feld_alias.grid(row=1, column=2, sticky="we", pady=(2, 0))

        self.knopf_anmelden = RoundedButton(karte, text="Anmelden", width=200,
                                            height=40, command=self._anmelden)
        self.knopf_anmelden.pack(pady=(20, 0))

        self.anmelde_hinweis = tk.Label(karte, text="", bg=Style.CARD,
                                        fg=Style.ERROR, font=Style.font(9),
                                        wraplength=520, justify="left")
        self.anmelde_hinweis.pack(pady=(12, 0))

        # Woher die Verbindung kommt - wer eine eigene tnsnames.ora neben
        # das Programm legt, soll sehen, dass sie gilt.
        pfad = lims_db.tnsnames_pfad()
        self.tns_hinweis = tk.Label(
            karte, text=(f"Verbindung aus {pfad}" if pfad else
                         "Keine tnsnames.ora gefunden."),
            bg=Style.CARD, fg=Style.MUTED if pfad else Style.ERROR,
            font=Style.font(8), wraplength=520, justify="left")
        self.tns_hinweis.pack(pady=(6, 0))

        for feld in (feld_benutzer, feld_passwort):
            feld.bind("<Return>", lambda e: self._anmelden())
        (feld_passwort if self.v_benutzer.get() else feld_benutzer).focus_set()

    def _anmelden(self):
        benutzer = self.v_benutzer.get().strip()
        passwort = self.v_passwort.get()
        alias = self.v_alias.get()
        self.anmelde_hinweis.config(text="Verbindung wird geprueft ...",
                                    fg=Style.MUTED)

        def arbeit():
            return lims_db.anmelden(benutzer, passwort, alias)

        def fertig(zugang):
            self.zugang = zugang
            # Von hier an schreibt jede Aenderung an der Datenbank mit.
            zugang.protokoll = protokoll.Protokoll(
                os.path.join(self.konfig.runtime_dir, protokoll.ORDNER),
                benutzer)
            self.konfig.set("benutzer", benutzer)
            self.konfig.set("alias", alias)
            self.konfig.speichern()
            self.arbeitsmaske()

        def schiefgegangen(fehler):
            self.anmelde_hinweis.config(text=lims_db.fehlertext(fehler),
                                        fg=Style.ERROR)

        self.im_hintergrund(arbeit, fertig, schiefgegangen,
                            warten_auf=self.knopf_anmelden)

    def _abmelden(self):
        # Der Vorrat haelt Verbindungen offen - beim Abmelden gehoeren sie
        # abgebaut, sonst haengt die Sitzung des Vorgaengers weiter an der
        # Datenbank.
        if self.zugang is not None:
            self.zugang.schliessen()
        self.zugang = None
        self.trdf_seite = None
        self.anmeldemaske()

    # =====================================================================
    # Arbeitsmaske
    # =====================================================================
    def arbeitsmaske(self):
        self._leeren()

        kopf = tk.Frame(self.rahmen, bg=Style.HEADER)
        kopf.pack(fill="x")
        tk.Label(kopf, text="TRDF-Pruefmodul", bg=Style.HEADER,
                 fg=Style.HEADER_FG, font=Style.font(13, "bold")).pack(
            side="left", padx=16, pady=10)
        tk.Label(kopf, text=self._zugangstext(), bg=Style.HEADER,
                 fg="#cbd5e1", font=Style.font(9)).pack(side="left", pady=10)
        knopf_ab = RoundedButton(kopf, text="Abmelden", width=110, height=30,
                                 bg="#334155", command=self._abmelden)
        knopf_ab.configure(bg=Style.HEADER)
        knopf_ab.config(bg="#334155")
        knopf_ab.pack(side="right", padx=16, pady=8)

        # Den Zugang holt sich die Seite beim Klicken, statt ihn einmal zu
        # bekommen: nach dem Abmelden ist er weg, und eine Seite, die ihn
        # sich gemerkt haette, schriebe mit dem alten weiter.
        self.trdf_seite = trdfreiter.TrdfSeite(
            self.rahmen, lambda: self.zugang, self.im_hintergrund,
            ordner=self.konfig.runtime_dir, konfig=self.konfig)
        self.trdf_seite.pack(fill="both", expand=True)

    def _zugangstext(self) -> str:
        """Benutzer, Datenbank, Modus und Verbindungsart in der Kopfzeile."""
        if self.zugang is None:
            return ""
        return (f"{self.zugang.benutzer} an {self.zugang.alias} "
                f"({self.zugang.modus or 'nicht verbunden'}, "
                f"{self.zugang.verbindungsart()})")

    def _beenden(self):
        self.konfig.speichern()
        if self.zugang is not None:
            self.zugang.schliessen()
        self.destroy()


# =========================================================================
# Start
# =========================================================================

def selbsttest_ausgeben() -> int:
    """Fuehrt den Selbsttest aus und schreibt das Ergebnis.

    Bei --windowed gibt es keine Konsole, stdout kann fehlen. Deshalb wandert
    die Ausgabe zusaetzlich in eine Datei neben der Anwendung, die der Build
    auslesen kann.
    """
    code, zeilen = lims_db.selbsttest()
    text = "\n".join(zeilen)
    try:
        print(text)
    except Exception:
        pass
    try:
        from config import get_runtime_dir
        pfad = os.path.join(get_runtime_dir(), "selbsttest.log")
        with open(pfad, "w", encoding="utf-8") as datei:
            datei.write(text + "\n")
    except OSError:
        pass
    return code


def main():
    if "--selbsttest" in sys.argv:
        raise SystemExit(selbsttest_ausgeben())
    PruefmodulAnwendung().mainloop()


if __name__ == "__main__":
    main()
