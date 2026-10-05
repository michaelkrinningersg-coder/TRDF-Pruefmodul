# TRDF-Prüfmodul

Die **TRDF-Prüfung aus LabControl** (Repository TestLims) als eigenes,
schlankes Windows-Programm: eine **Einzelauswertung** je Serie und
Untersuchungsmethode. Es rechnet die Größen einer TRDF-Serie mit den Formeln
aus dem LIMS nach, prüft die bodenphysikalischen Werte und schreibt
Korrekturen an den Rohwerten in das LIMS zurück.

Wie LabControl ist es eine portable Anwendung **ohne Installation, ohne
Server und ohne Internet**.

## Was drin ist – und was nicht

| drin | nicht drin |
|---|---|
| Anmeldung wie in LabControl (Oracle-Benutzer, Passwort, Datenbank) – Datenbank **nur LIMS** | ECO, LIMSTEST |
| Serie → **Abfragen** → Untersuchungsmethode (alle mit `TRDF` im Kürzel) | Abruf einzelner Probennummern, Probenart-Filter |
| Reiter *Rohwerte*, *Ergebnisse*, *Pruefung*, *Exportbericht* | Profilansichten (Profil-CSV, Plot/Tiefenstufe, Profilfenster) |
| Rohwerte von Hand ändern (auch Einfügen aus Excel, Großansicht) | Plotvergleich |
| **Blockbild** beim Klick auf die Probe | |
| **LIMS-Export**: *In das LIMS schreiben*, *Sicherung zurueckspielen*, *Anhang angleichen* | |
| Einfügefeld für die Liste der Probenvorbereitung – als Option, erst nach Klick sichtbar; Quelle umschalten | |
| Info/Legende je Tabelle, CSV-Blätter, Streubild TRDF über Kohlenstoff | |

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
5. **In das LIMS schreiben** – eine Übersicht zeigt Zeile für Zeile alt und
   neu; erst nach Bestätigung wird der alte Stand in `trdf_backup` gesichert
   und dann geschrieben (Ergebniszeile und Teilprobenanhang in einer
   Transaktion, danach wird nachgelesen).

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
| `trdfreiter.py` | die Seite *TRDF Pruefung* (Auswahl, Tabellen, Rückweg) |
| `trdf.py`, `trdfformel.py` | Nachrechnen mit den Formeln aus `PRUEFMETHODEN.FORMEL` |
| `trdfpruefung.py`, `trdfrohpruefung.py`, `trdfserie.py` | Plausibilitätsprüfungen |
| `trdfblock.py`, `trdfbild.py` | Bodenblock und Streubild |
| `trdfexport.py` | Rückweg in das LIMS: Übersicht, Sicherung, Zurückspielen |
| `trdflegende.py` | Legende und Spaltenordnung |
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
