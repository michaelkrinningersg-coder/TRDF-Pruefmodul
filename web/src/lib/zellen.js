// Kleine Helfer fuer Zellen - Zahlen mit Komma, Text aus Excel.

// Was im LIMS "hier soll nichts stehen" heisst.
export const MARKE = "x";

// Eine Zahl aus der Zelle - auch mit Dezimalkomma; sonst null.
export function alsZahl(text) {
  const t = String(text ?? "").trim().replace(",", ".");
  if (!t || !/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(t)) return null;
  const zahl = Number(t);
  return Number.isFinite(zahl) ? zahl : null;
}

// Eine Zahl so geschrieben wie die Vorlage - Komma bleibt Komma, und
// so viele Nachkommastellen wie dort.
export function zahltext(zahl, vorlage) {
  const v = String(vorlage ?? "").trim();
  const trenner = v.includes(",") ? "," : ".";
  const nachkomma = v.split(/[.,]/)[1]?.length ?? 0;
  return zahl.toFixed(nachkomma).replace(".", trenner);
}

// Was aus der Zwischenablage kommt, als Zeilen und Spalten - so legt
// Excel einen Bereich ab. Der letzte Umbruch gehoert zur letzten Zeile.
export function zerlegen(inhalt) {
  let text = String(inhalt ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  while (text.endsWith("\n")) text = text.slice(0, -1);
  return text.split("\n").map((zeile) => zeile.split("\t"));
}

export function alsTsv(tafel) {
  return tafel.map((zeile) => zeile.join("\t")).join("\r\n");
}
