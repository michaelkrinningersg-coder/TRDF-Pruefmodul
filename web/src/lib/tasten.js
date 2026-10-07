// Was im Raster wie in Excel geht - steht hinter dem grauen i.
export const TASTEN = [
  ["Tab / Pfeile / Eingabe", "Zelle wechseln"],
  ["Tippen / F2 / Doppelklick", "überschreiben / bearbeiten"],
  ["Strg+C / Strg+V", "kopieren / Block aus Excel einfügen"],
  ["Entf", "gewählte Zellen leeren"],
  ["Strg+D", "Wert der Zelle darüber übernehmen"],
  ["Strg+Shift+D", "Wert nach unten kopieren (bis zum Ende)"],
  ["Strg+L", "Wert nach unten, nur in leere Zellen"],
  ["Strg+I", "nach unten hochzählen (+1 je Zeile)"],
  ["Strg+E", "leere Zellen der Probe mit x füllen"],
  ["Strg+Shift+E", "leere Zellen der Spalte mit x füllen"],
  ["Shift+Klick / Shift+Pfeile", "Bereich wählen"],
];

export const VARIANTE = [
  ["x", "alle Rohwerte bekommen x"],
  ["0", "alle Rohwerte werden geleert"],
  ["1 – 7", "nicht benötigte Felder bekommen x"],
];

export const ERKLAERUNG = {
  kopf:
    "Das LIMS bildet aus den Rohwerten einer TRDF-Serie ein Dutzend Größen. " +
    "Das Prüfmodul rechnet sie mit denselben Formeln noch einmal, stellt " +
    "beides nebeneinander und prüft, ob die bodenphysikalischen Werte " +
    "zueinander passen.\n\nErst die Serie wählen, dann „Abfragen“: angeboten " +
    "werden alle Untersuchungsmethoden der Serie, deren Kürzel TRDF trägt.\n\n" +
    "Rohwerte lassen sich von Hand ändern – dann wird sofort neu gerechnet; " +
    "in das LIMS geht eine Änderung erst über „Export“.",
  roh:
    "Was aus der gewählten Quelle kommt – der eingefügten UM oder dem LIMS. " +
    "Eine Zelle anklicken und tippen überschreibt sie; Tab geht in der Zeile " +
    "weiter, die Pfeile in alle Richtungen, Eingabe eine Zeile tiefer. Aus " +
    "Excel kopierte Werte lassen sich in die obere Zelle einfügen – sie " +
    "laufen von dort nach unten und nach rechts weiter.\n\nRechts steht, was " +
    "an den Rohwerten auffällt: was der Variante fehlt, was außerhalb seines " +
    "Bereichs liegt und was nicht zueinander passt.\n\nRot: von Hand " +
    "geändert. Amber: die eingefügte UM weicht vom LIMS ab.",
  berechnet:
    "Je Größe zwei Spalten: gebucht im LIMS und gerechnet (ber.). Rot: durch " +
    "die Handeingabe bewegt – und die Probe, in der von Hand geändert wurde. " +
    "Unterlegt ist die Zeile, in der unten gerade getippt wird.",
  ergebnis:
    "Je Größe zwei Spalten: was das LIMS gebucht hat und was das Prüfmodul " +
    "aus denselben Formeln rechnet – zusammengehalten durch den Hintergrund, " +
    "der von Größe zu Größe wechselt. Amber heißt, dass beides " +
    "auseinandergeht; rechts steht, welche Größen es sind. Rot heißt, dass " +
    "der Wert von Hand bewegt wurde. Violett kursiv: Cges/CO3 aus einer " +
    "anderen Anlage derselben Probennummer.",
  pruefung:
    "Die bodenphysikalischen Werte, nach Probe-Nr. sortiert. Geprüft wird, " +
    "was das Prüfmodul gerechnet hat: der Skelettanteil gegen 0 und 100 " +
    "Prozent und gegen den geschätzten Grobboden, der Abstand zwischen " +
    "gemessenem und geschätztem Skelettanteil, der Feinbodenvorrat gegen " +
    "null und die Trockenrohdichte gegen den Sollbereich ihrer " +
    "Kohlenstoffklasse. Dazu, was erst im Vergleich mit der Serie auffällt: " +
    "ein Wiederfindungsgrad, der nicht zum organischen Kohlenstoff passt, " +
    "und Rohwerte, die im LIMS an zwei Stellen verschieden stehen. Was " +
    "auffällt, steht in der Bewertung.",
  bericht:
    "Der letzte Schreibweg in das LIMS, von der anderen Seite gesehen: eine " +
    "Probe je Zeile und eine Spalte je Größe, die sich bewegt hat – erst die " +
    "Rohwerte, dann die daraus berechneten Größen. In der Zelle steht, was " +
    "vorher im LIMS stand und was jetzt dort steht. Der Bericht bleibt " +
    "stehen, bis wieder geschrieben wird; als Datei liegt er neben der " +
    "Sicherung im Ordner „trdf_backup“.",
  einfuegen:
    "In der Probenvorbereitung „aktueller Block“ → kopieren, hier mit Strg+V " +
    "einfügen, dann „Übernehmen“ – danach wird mit dieser Liste gerechnet. " +
    "Werte, die im LIMS noch fehlen, werden rot zum Export vorgemerkt; Werte, " +
    "die schon im LIMS stehen, werden nicht überschrieben (Abweichungen " +
    "amber). „Leeren“ schaltet zurück auf die Rohwerte aus dem LIMS.",
};
