# TRDF-Prüfmodul – Kurzanleitung

## 1. Starten und anmelden

1. **Doppelklick** auf `TRDF-Pruefmodul-x86.exe`. Eine Installation ist nicht nötig.
2. Anmelden mit den **LIMS-Anmeldedaten**:
   * **Oracle-Benutzer** – in der Regel der Nachname
   * **Passwort**
   * **Datenbank** – steht fest auf `LIMS`
3. **Anmelden** klicken. Der Benutzername wird gemerkt, das Passwort nie.

## 2. Serie abfragen

1. **Serie** aus der Liste wählen oder eintippen.
2. **Abfragen** klicken.
   * Führt die Serie **eine** TRDF-Methode, wird sie sofort geladen.
   * Führt sie **mehrere**, die gewünschte unter **Untersuchungsmethode** wählen. Die Auswahl lädt die Serie.

Die Statuszeile unter der Auswahl sagt, was gerade passiert.

## 3. Werte noch nicht im LIMS? Liste einfügen

1. Oben rechts auf **„Liste Probenvorbereitung einfuegen …“** klicken. Es öffnet sich ein eigenes, großes Fenster.
2. In der Probenvorbereitung **aktueller Block → kopieren**.
3. Im Fenster mit **Strg+V** einfügen und **Uebernehmen** klicken.

Werte, die im LIMS noch fehlen, werden übernommen und **rot** zum Schreiben vorgemerkt. Werte, die schon im LIMS stehen, werden nicht überschrieben; Abweichungen sind **amber** markiert. Der Inhalt bleibt erhalten, auch wenn das Fenster geschlossen wird.

## 4. Werte ändern – wie in Excel

* Zelle im Reiter **Rohwerte** anklicken und tippen. Der alte Inhalt ist markiert und wird überschrieben.
* **Tab** springt nach rechts, **Pfeile** in alle Richtungen, **Eingabe** eine Zeile tiefer.
* Jede Änderung wird **sofort neu gerechnet**.
  * Mit **„▸ Berechnete Groessen einblenden“** stehen die berechneten Größen oben über den Rohwerten. Die Grenze dazwischen lässt sich ziehen.
  * Die Probe, in der man tippt, ist in allen Tabellen unterlegt und wird oben in den Blick gerollt.
  * **Rot** markiert sind die geänderte Probe, der geänderte Wert und jede berechnete Größe, die sich dadurch verschoben hat.
* **Klick auf die Probennummer** öffnet den **Zusammensetzungsblock** der Probe als eigenes Fenster.
  * Er rechnet bei jeder Eingabe live mit.
  * **Pfeil hoch/runter** blättert zur nächsten Probe.

### Tastenkürzel

Die Tastenkürzel stehen auch im grauen **i** neben den Knöpfen der Rohwerte.

| Taste | Wirkung |
|---|---|
| Strg+C / Strg+V | Zelle kopieren / Block aus Excel einfügen (läuft nach unten und rechts weiter) |
| Strg+D | Wert der Zelle **darüber** übernehmen |
| Strg+Shift+D | Wert **nach unten** kopieren, bis zum Ende der Spalte (überschreibt) |
| Strg+L | Wert nach unten kopieren, **nur in leere** Zellen |
| Strg+I | nach unten **hochzählen**: Wert, Wert+1, Wert+2 … |
| Strg+E | leere Zellen der **Zeile** (Probe) mit `x` füllen |
| Strg+Shift+E | leere Zellen der **Spalte** mit `x` füllen |

„Leer“ heißt: Es steht wirklich nichts da. Ein `x` bedeutet „hier soll nichts stehen“ und wird von Strg+L und Strg+E nicht überschrieben.

### Spalte Variante (`_TRDV`)

| Eingabe | Wirkung in der Zeile |
|---|---|
| `x` | alle Rohwerte bekommen `x` |
| `0` | alle Rohwerte werden geleert |
| `1`–`7` | die Felder, die diese Variante nicht braucht, bekommen `x` |

Wer eine Variante mit Strg+Shift+D nach unten kopiert, bekommt das in jeder Zeile.

## 5. In das LIMS schreiben

1. **In das LIMS schreiben** klicken. Eine Übersicht zeigt Zeile für Zeile den alten und den neuen Wert.
2. **Sichern und schreiben** klicken.
   * Zuerst wird der alte Stand gesichert, danach geschrieben.
   * Geschrieben werden Ergebniszeile und Teilprobenanhang in einem Schritt.
   * Danach wird nachgelesen, ob die Werte angekommen sind.
3. Der Reiter **Exportbericht** zeigt, was geschrieben wurde.

**Sicherung:** im Ordner **`trdf_backup` neben der exe**. Je Schreibvorgang entsteht eine eigene Datei `<Serie> <Datum> <Uhrzeit>.csv`. Daneben liegen der Korrekturlog und, auf Knopfdruck, der Exportbericht.

**Rückgängig machen:** **Sicherung zurueckspielen** klicken, die Datei aus `trdf_backup` wählen, in der Übersicht prüfen und **Zurueckspielen** klicken. Dadurch wird der gesicherte Stand von Ergebniszeile und Teilprobenanhang wiederhergestellt.

## 6. Ansicht einrichten und Blätter

* **Info** öffnet die Legende einer Tabelle. Dort lassen sich festlegen:
  * eigene Beschreibungen der Spalten,
  * die Spaltenreihenfolge (ziehen),
  * welche Spalten fest stehen bleiben und welche ausgeblendet sind,
  * was in der Kopfzeile steht.

  Gespeichert wird in `einstellungen\` neben der exe; beim nächsten Start ist alles wieder da. Ebenso werden die zuletzt abgefragte Serie und das Auf-/Zuklappen der berechneten Größen gemerkt.
* Die blauen **i** erklären, was eine Tabelle zeigt.
* Als CSV ablegen lassen sich: **Rohwertblatt**, **Aenderungen**, **Ergebnisblatt** bzw. **Blatt als CSV** (berechnete Größen), **Blatt** im Reiter Pruefung und **Bericht**. Abgelegt wird im Ordner `TRDF-Pruefung` bzw. `trdf_backup`.
