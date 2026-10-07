# TRDF-Prüfmodul

Die **TRDF-Prüfung aus LabControl** (Repository TestLims) als eigenes,
schlankes Windows-Programm: eine **Einzelauswertung** je Serie und
Untersuchungsmethode. Es rechnet die Größen einer TRDF-Serie mit den Formeln
aus dem LIMS nach, prüft die bodenphysikalischen Werte und schreibt
Korrekturen an den Rohwerten in das LIMS zurück.

Wie LabControl ist es eine portable Anwendung **ohne Installation, ohne
Server und ohne Internet**.

**Zur Bedienung: [ANLEITUNG.md](ANLEITUNG.md)** – Kurzanleitung mit Bildern
und allen Tastenkürzeln, auch als PDF:
[docs/Anleitung_TRDF-Pruefmodul.pdf](docs/Anleitung_TRDF-Pruefmodul.pdf).
Bilder und PDF lassen sich neu erzeugen (`docs/anleitung_bilder.py`,
`docs/anleitung_pdf.py`).

## Was drin ist – und was nicht

| drin | nicht drin |
|---|---|
| Anmeldung wie in LabControl (Oracle-Benutzer, Passwort, Datenbank) – Datenbank **nur LIMS** | ECO, LIMSTEST |
| Serie → **Abfragen** → Untersuchungsmethode (alle mit `TRDF` im Kürzel) | Abruf einzelner Probennummern, Probenart-Filter |
| Reiter *Rohwerte*, *Ergebnisse*, *Pruefung*, *Exportbericht* | Profilansichten (Profil-CSV, Plot/Tiefenstufe, Profilfenster) |
| Rohwerte von Hand ändern (auch Einfügen aus Excel, Großansicht) | Plotvergleich |
| **Blockbild** beim Klick auf die Probe | |
| **LIMS-Export**: *Export*, *Load backup*, *Anhang angleichen* | |
| „UM einfuegen …“ (Liste aus der Probenvorbereitung) – als Option in eigenem Fenster; ist eine UM eingefügt, wird automatisch mit ihr gerechnet, sonst mit dem LIMS; im LIMS fehlende Werte werden zum Export vorgemerkt | |
| Excel-Kürzel im Raster: Strg+C/V, Strg+D, Strg+Shift+D, Strg+L, Strg+I, Strg+E, Strg+Shift+E | |
| Info/Legende je Tabelle (gespeichert, beim nächsten Start wieder da), CSV-Blätter inkl. Ergebnisblatt, Streubild TRDF über Kohlenstoff | |

## Ablauf

1. **Anmelden** – Oracle-Benutzer, Passwort, Datenbank. In der Auswahl steht
   nur `LIMS`. Das Passwort wird nirgends gespeichert.
2. **Serie** wählen (Liste der TRDF-Serien aus dem Fahrplan) oder eintippen.
3. **Abfragen** – gefragt wird, welche Untersuchungsmethoden die Serie
   führt (`TEILPROBEN`, ersatzweise `ERGEBNISSE` oder `SERIEN_MW_ANHANG`).
   Angeboten werden alle, deren Kürzel `TRDF` trägt; `TRDF3.1` bleibt
   ausgeschlossen (siehe `lims_db.AUSGESCHLOSSENE_METHODEN`).
   * genau eine Methode → die Serie wird gleich geholt,
   * mehrere → im Feld *Untersuchungsmethode* wählen; die Wahl holt die
     Serie. Tragen zwei dasselbe Kürzel (Boden/Humus), steht die UM_ID dabei.
4. **Prüfen und ändern** – Rohwerte überschreiben, es wird sofort neu
   gerechnet. Ein Klick auf die Probennummer öffnet den **Bodenblock** als
   eigenes Fenster, das jede Änderung live mitzeichnet; mit Pfeil
   rauf/runter blättert er durch die Serie.

   Über den Rohwerten lassen sich mit **„▸ Berechnete Groessen
   einblenden“** die berechneten Größen aufklappen – eine eigene Tabelle,
   die Grenze zu den Rohwerten lässt sich ziehen, zugeklappt gehört das
   Fenster ganz den Rohwerten. Wer unten in einer Probenzeile tippt, sieht
   oben dieselbe Probe unterlegt und in den Blick gerollt; die Probe, in der
   von Hand geändert wurde, und jede dadurch bewegte Größe stehen rot.

   Die Erklärtexte stehen hinter den kleinen **i** neben Überschrift und
   Knopfleisten (Maus darauf oder Klick).
5. **Export** – eine Übersicht zeigt Zeile für Zeile alt und
   neu; erst nach Bestätigung wird der alte Stand in `trdf_backup` gesichert
   und dann geschrieben (Ergebniszeile und Teilprobenanhang in einer
   Transaktion, danach wird nachgelesen).

## Weboberfläche: pywebview + Svelte (Zweig `feature/pywebview-svelte`)

Dieselbe Einzelauswertung mit einem anderen Gesicht: ein Fenster mit **Edge
WebView2**, darin eine **Svelte**-Seite, dazwischen die Python-JS-Brücke von
**pywebview**. Gerechnet, geprüft und geschrieben wird mit denselben Modulen
wie in der Tk-Fassung – das gemeinsame Modell steht in `trdfmodell.py`.

| Schicht | Technik | Datei |
|---|---|---|
| Fenster | pywebview 6 (WebView2 über pythonnet), ohne Konsole | `trdfweb.py` |
| Brücke | `window.pywebview.api.<name>()` → `trdfweb.Api` | `trdfweb.py`, `web/src/lib/api.js` |
| Modell | Rechnen, Prüfen, Tabelleninhalt, Abruf, UM, Variante | `trdfmodell.py` |
| Datenbank | python-oracledb (Thin, Thick-Fallback 11.2, x86) | `lims_db.py` |
| Seite | Svelte 5 + Vite 8, eine einzige `index.html` (~130 KB) | `web/` → `webdist/` |
| Raster | eigenes virtualisiertes Raster mit Excel-Kürzeln | `web/src/lib/Raster.svelte` |
| Paket | PyInstaller `--onefile --windowed`, x86 | `.github/workflows/build-web-exe.yml` |

**Warum Svelte und nicht React:** Svelte kompiliert zu schlankem JavaScript
ohne virtuelles DOM – die ganze Seite ist rund 130 KB groß, startet sofort
und aktualisiert bei einer Eingabe nur die Zellen, die sich ändern. Für ein
Raster, in dem nach jeder Zahl ein paar Dutzend Zellen umfärben, ist das der
schnellste Weg. Statt TanStack/Tabulator steht ein eigenes Raster da (eine
Svelte-Datei): virtualisiert, feste Spalten links, und genau die Tastenkürzel
der Tk-Fassung (Strg+C/V, Strg+D, Strg+Shift+D, Strg+L, Strg+I, Strg+E,
Strg+Shift+E, Variante x/0/1–7).

**Schnell:** Eine Eingabe rechnet nur ihre Probe neu und schickt nur deren
Zeilen zurück (wenige Millisekunden); das Laden von 360 Proben dauert in
Python rund 0,7 s.

**Voraussetzung am Arbeitsplatz:** die WebView2-Laufzeit. Unter Windows 10/11
ist sie mit Edge in aller Regel schon da.

### exe herunterladen

Workflow **TRDF-Pruefmodul Web-EXE bauen** → Artefakt
`TRDF-Pruefmodul-Web-x86-<Zweig>` → `TRDF-Pruefmodul-Web-x86.exe` starten.
Vor dem Bauen laufen alle Prüfungen, danach ein Selbsttest der exe
(cryptography, pywebview, tnsnames.ora mit LIMS, Thin-Mode-Stack, Seite im
Paket) und ein Startversuch des Fensters.

### Aus dem Quelltext

```
cd web && npm ci && npm run build && cd ..     # baut webdist/index.html
pip install -r requirements-web.txt
python trdfweb.py                               # das Fenster
```

Entwicklung im Browser, ohne Datenbank, mit einer erfundenen Serie:

```
python trdfweb.py --dienst 8765 --demo          # Python-Seite
cd web && npm run dev                           # Vite mit Hot Reload, http://localhost:5173
```

`--dienst` liefert `webdist/` aus und beantwortet `POST /api/<Methode>` –
nur für Entwicklung und Bilder; das Programm selbst braucht keinen Server.

## Datenbankverbindung: tnsnames.ora

Der Connect-Deskriptor kommt aus der **`tnsnames.ora`** (die Datei aus
LabControl liegt im Repository). Gesucht wird:

1. neben der exe – eine dort abgelegte Datei geht vor,
2. in der exe selbst (der Bau packt `tnsnames.ora` mit hinein).

Aus der Datei wird ausschließlich der Eintrag **`LIMS`** genommen. Steht er
nicht darin, ist keine Anmeldung möglich; die Anmeldemaske zeigt, welche
Datei gilt.

Thin Mode (Standard) braucht keinen Oracle-Client. Ist die Datenbank zu alt
(`DPY-3010`), wird der Client unter `C:\Oracle\11.2.0\bin` nachgeladen
(Thick Mode) – dafür die **x86-exe** verwenden. Ein anderer Client-Pfad lässt
sich über `TRDF_ORACLE_CLIENT` (oder wie bei LabControl
`LABCONTROL_ORACLE_CLIENT`) vorgeben.

## exe herunterladen

Der Workflow **TRDF-Pruefmodul EXE bauen** (`.github/workflows/build-exe.yml`)
läuft bei jedem Push, der Code, Abhängigkeiten, `tnsnames.ora` oder den
Workflow ändert, außerdem über *Run workflow* und bei einem Tag `v*`.

1. Reiter **Actions** → letzter erfolgreicher Lauf von *TRDF-Pruefmodul EXE
   bauen*
2. unter **Artifacts**: `TRDF-Pruefmodul-x86-<Zweig>`
3. ZIP entpacken, `TRDF-Pruefmodul-x86.exe` starten.

Ein Tag `v*` oder ein Zweig unter `stand/` hängt die exe zusätzlich an ein
GitHub-Release.

Vor dem Bauen laufen alle Prüfungen (`pruefungen_laufen.py`), danach ein
Selbsttest der fertigen exe (`--selbsttest`: cryptography, tkinter,
tnsnames.ora mit LIMS, Thin-Mode-Stack) und ein Startversuch der Oberfläche.

## Wo was abgelegt wird (neben der exe)

| Ordner | Inhalt |
|---|---|
| `einstellungen/` | Benutzername, zuletzt abgefragte Serie, Spaltenordnung und Beschreibungen der Legende |
| `trdf_backup/` | Sicherung vor jedem Schreiben, Korrekturlog, Exportbericht |
| `TRDF-Pruefung/` | Prüf- und Rohwertblätter als CSV |
| `protokoll/` | Änderungsprotokoll jeder schreibenden Anweisung |

Ist neben der exe kein Schreiben möglich, weichen die Einstellungen nach
`%LOCALAPPDATA%\TRDF-Pruefmodul` aus.

## Aufbau

| Datei | Rolle |
|---|---|
| `trdfpruefmodul.py` | Startpunkt: Anmeldung und Hauptfenster |
| `trdfreiter.py` | die Seite *TRDF Pruefung* (Tk: Auswahl, Tabellen, Rückweg) |
| `trdfmodell.py` | das Modell der Seite ohne Oberfläche – Tk und Web stehen darauf |
| `trdfweb.py`, `web/` | die Weboberfläche (pywebview + Svelte) |
| `trdf.py`, `trdfformel.py` | Nachrechnen mit den Formeln aus `PRUEFMETHODEN.FORMEL` |
| `trdfpruefung.py`, `trdfrohpruefung.py`, `trdfserie.py` | Plausibilitätsprüfungen |
| `trdfblock.py`, `trdfbild.py` | Bodenblock und Streubild (Daten); die Tk-Fenster in `trdfblockfenster.py`, `trdfbildfenster.py` |
| `trdfexport.py` | Rückweg in das LIMS: Übersicht, Sicherung, Zurückspielen |
| `trdflegende.py` | Legende und Spaltenordnung; das Tk-Fenster in `trdflegendefenster.py` |
| `lims_db.py` | Datenschicht (nur Anmeldung, TRDF-Abfragen, TRDF-Rückweg), GUI-frei |
| `eingaberaster.py`, `widgets.py` | GUI-Bausteine aus LabControl |
| `config.py`, `protokoll.py`, `druck.py` | Einstellungen, Änderungsprotokoll, Öffnen von Dateien |
| `test_*.py`, `pruefungen_laufen.py` | Prüfungen ohne Datenbank |

## Aus dem Quelltext starten

```
pip install -r requirements.txt
python trdfpruefmodul.py
```

Prüfungen (unter Linux mit `xvfb-run -a` davor):

```
python pruefungen_laufen.py
```
