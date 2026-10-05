"""Baut docs/Anleitung_TRDF-Pruefmodul.pdf aus ANLEITUNG.md.

Markdown -> HTML (mit Druckformatierung) -> PDF ueber ein kopfloses
Chromium. Aufruf aus dem Repository-Ordner:

    python docs/anleitung_pdf.py [Pfad zu chromium]
"""

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import markdown

WURZEL = pathlib.Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "ANLEITUNG.md"
ZIEL = WURZEL / "docs" / "Anleitung_TRDF-Pruefmodul.pdf"

STIL = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
body { font-family: "Segoe UI", "DejaVu Sans", Arial, sans-serif;
       font-size: 10.5pt; line-height: 1.45; color: #1e293b; }
h1 { font-size: 20pt; color: #0f172a; border-bottom: 3px solid #2563eb;
     padding-bottom: 4px; margin-top: 0; }
h2 { font-size: 14pt; color: #0f172a; margin-top: 18px;
     border-bottom: 1px solid #cbd5e1; padding-bottom: 2px;
     break-after: avoid; page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #1d4ed8; margin-top: 12px;
     break-after: avoid; page-break-after: avoid; }
p, li { margin: 3px 0; }
img { max-width: 100%; max-height: 118mm; width: auto; height: auto;
      border: 1px solid #cbd5e1; border-radius: 3px;
      display: block; margin: 6px auto 10px auto;
      break-inside: avoid; page-break-inside: avoid; }
p:has(> img) { break-inside: avoid; page-break-inside: avoid; }
table { border-collapse: collapse; margin: 6px 0 10px 0; width: 100%;
        break-inside: avoid; page-break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 3px 6px; text-align: left;
         vertical-align: top; font-size: 9.5pt; }
th { background: #e2e8f0; }
code { background: #f1f5f9; padding: 0 3px; border-radius: 2px;
       font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 9.5pt; }
strong { color: #0f172a; }
"""


LISTE = re.compile(r"^\s*(?:[*-]|\d+\.)\s")


def vorbereiten(text: str) -> str:
    """Das Markdown fuer python-markdown zurechtruecken.

    GitHub nimmt verschachtelte Listen mit zwei oder drei Leerzeichen
    und Listen direkt unter einem Satz; python-markdown will vier
    Leerzeichen und eine Leerzeile davor. Die Datei bleibt, wie sie ist -
    angepasst wird nur, was in das PDF geht.
    """
    zeilen = []
    for zeile in text.splitlines():
        eingerueckt = re.match(r"^( +)(\S.*)$", zeile)
        if eingerueckt:
            tiefe = (len(eingerueckt.group(1)) + 1) // 3
            zeile = "    " * max(tiefe, 1) + eingerueckt.group(2)
        if LISTE.match(zeile) and zeilen and zeilen[-1].strip() and \
                not LISTE.match(zeilen[-1]) and \
                not zeilen[-1].startswith("    ") and \
                not zeile.startswith("    "):
            zeilen.append("")
        zeilen.append(zeile)
    return "\n".join(zeilen)


def chromium(vorgabe=None) -> str:
    """Ein Chromium oder Chrome, das PDF drucken kann."""
    kandidaten = [vorgabe, os.environ.get("CHROMIUM"),
                  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                  shutil.which("chromium"), shutil.which("chromium-browser"),
                  shutil.which("google-chrome"), shutil.which("chrome"),
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    for pfad in kandidaten:
        if pfad and os.path.isfile(pfad):
            return pfad
    raise SystemExit("Kein Chromium/Chrome/Edge gefunden.")


def main() -> int:
    text = QUELLE.read_text(encoding="utf-8")
    inhalt = markdown.markdown(vorbereiten(text),
                               extensions=["tables", "sane_lists"])
    html = (f"<!doctype html><html lang='de'><head><meta charset='utf-8'>"
            f"<title>TRDF-Prüfmodul – Kurzanleitung</title>"
            f"<style>{STIL}</style></head><body>{inhalt}</body></html>")
    # Neben die Quelle, damit die relativen Bildpfade stimmen.
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=WURZEL,
                                     delete=False, encoding="utf-8") as datei:
        datei.write(html)
        seite = datei.name
    try:
        subprocess.run([chromium(sys.argv[1] if len(sys.argv) > 1 else None),
                        "--headless", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer",
                        f"--print-to-pdf={ZIEL}",
                        pathlib.Path(seite).as_uri()],
                       check=True, capture_output=True, timeout=120)
    finally:
        os.unlink(seite)
    print(ZIEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
