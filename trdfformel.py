"""
TRDF-Pruefmodul - die Formelsprache der Pruefmethoden
=====================================================

PRUEFMETHODEN.FORMEL traegt kleine Programme, mit denen das LIMS aus
Rohwerten die berechneten Groessen bildet. Ein Beispiel, gekuerzt:

    if (isnum($_TRDV) != 1) {$TRD_TRDF="x";}
    else if (_TRDV == 1 ) {TRD_TRDF=FBMSZ/VOLSZ;}
    else if (_TRDV == 2 || _TRDV == 6) {TRD_TRDF=FBMSZ/(VOLSZ-(GBMSZ/DichteGB));}

Warum ausgewertet und nicht nachgebaut
--------------------------------------
Diese zwoelf Formeln in Python nachzuschreiben waere schneller getippt.
Nur waere damit genau das verloren, worum es geht: aendert das Labor eine
Formel im LIMS, rechnete LabControl weiter das Alte - und die Pruefung,
die eine Abweichung finden soll, faende keine mehr. Deshalb wird die
Formel gelesen, die dort steht.

Was die Sprache kann
--------------------
Zuweisungen (mit oder ohne `$`), `if / else if / else`, die Vergleiche
`== != < > <= >=`, `||` und `&&`, `isnum(...)`, Grundrechenarten und
Klammern. Dazu zwei Eigenheiten des LIMS:

  * Aufrufe wie `ws_get_this_rec_hnd()` gibt es hier nicht. Sie liefern
    keine Zahl; die Formeln pruefen das mit `isnum()` selbst ab.
  * `sql("select mw into :v_wgh from ...")` holt im LIMS einen Wert
    nach. Ausgefuehrt wird hier nichts - der Aufrufer reicht ihn unter
    dem Namen herein, der hinter `into :` steht.

Was sie nicht kann, faellt auf: eine unbekannte Wendung gibt einen
Fehler zurueck, statt still ein falsches Ergebnis.

Kein Wert ist kein Wert
-----------------------
`MARKE` ("x") steht fuer "nicht anwendbar" - so schreiben es auch die
Formeln selbst. Rechnen mit einem fehlenden Wert ergibt wieder MARKE;
eine Division durch null ebenso. Ein fehlender Rohwert wird also *nicht*
als Null behandelt. Das ist der Unterschied zwischen "hier gibt es
nichts" und "hier ist nichts drin", und in einer Pruefung ist er
entscheidend.
"""

import decimal
import functools
import re

D = decimal.Decimal
decimal.getcontext().prec = 28

MARKE = "x"          # nicht anwendbar

_ZEICHEN = re.compile(r"""
    (?P<zahl>\d+(?:\.\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<text>"[^"]*")
  | (?P<op>==|!=|<=|>=|\|\||&&|[-+*/()<>=,;{}$:])
  | (?P<leer>\s+)
""", re.X)
_INTO = re.compile(r"into\s+:(\w+)", re.I)


@functools.lru_cache(maxsize=256)
def _zerlegt(quelle) -> tuple:
    """Die Zeichen einer Formel - einmal je Formeltext.

    Eine Serie hat ein Dutzend Formeln, gerechnet wird aber je Probe und
    je Aenderung: bei dreihundert Proben zerlegte jede Handeingabe
    sonst dieselben zwoelf Texte siebentausendmal. Der Auswerter liest
    die Zeichen nur, deshalb darf er sich ein gemerktes Tupel teilen.
    """
    return tuple(zerlegen(quelle))


def zerlegen(quelle):
    stelle, marken = 0, []
    while stelle < len(quelle):
        treffer = _ZEICHEN.match(quelle, stelle)
        if treffer is None:
            raise ValueError(f"Unbekanntes Zeichen bei {quelle[stelle:stelle+20]!r}")
        stelle = treffer.end()
        if treffer.lastgroup != "leer":
            marken.append((treffer.lastgroup, treffer.group()))
    return marken


class Auswerter:
    def __init__(self, marken, werte, abfragen=None):
        self.m, self.i, self.werte = marken, 0, werte
        self.abfragen = abfragen or {}

    def schau(self, weit=0):
        return self.m[self.i + weit] if self.i + weit < len(self.m) else (None, None)

    def nimm(self, text=None):
        art, wert = self.schau()
        if text is not None and wert != text:
            raise ValueError(f"Erwartet {text!r}, gefunden {wert!r}")
        self.i += 1
        return wert

    # ------------------------------------------------------- Anweisungen
    def block(self):
        if self.schau()[1] == "{":
            self.nimm("{")
            while self.schau()[1] not in ("}", None):
                self.anweisung()
            self.nimm("}")
        else:
            self.anweisung()

    def anweisung(self):
        art, wert = self.schau()
        if wert in (";", ):
            self.nimm(); return
        if wert == "{":
            self.block(); return
        if wert == "local_var":
            while self.schau()[1] not in (";", None):
                self.nimm()
            self.nimm(); return
        if wert == "sql":
            self.nimm("sql"); self.nimm("(")
            text = self.nimm() if self.schau()[0] == "text" else ""
            self.klammer_rest()
            if self.schau()[1] == ";":
                self.nimm()
            treffer = _INTO.search(str(text))
            if treffer and treffer.group(1) in self.abfragen:
                self.werte[treffer.group(1)] = self.abfragen[treffer.group(1)]
            return
        if wert == "if":
            self.nimm("if"); self.nimm("(")
            bedingung = self.ausdruck(); self.nimm(")")
            if self.wahr(bedingung):
                self.block()
                self.zweig_ueberspringen()
            else:
                self.block_ueberspringen()
                if self.schau()[1] == "else":
                    self.nimm("else")
                    if self.schau()[1] == "if":
                        self.anweisung()
                    else:
                        self.block()
            return
        if wert == "$":
            self.nimm("$")
        name = self.nimm()
        self.nimm("=")
        self.werte[name] = self.ausdruck()
        if self.schau()[1] == ";":
            self.nimm()

    def zweig_ueberspringen(self):
        while self.schau()[1] == "else":
            self.nimm("else")
            if self.schau()[1] == "if":
                self.nimm("if"); self.nimm("("); self.klammer_rest()
            self.block_ueberspringen()

    def block_ueberspringen(self):
        if self.schau()[1] == "{":
            tiefe = 0
            while self.schau()[1] is not None:
                z = self.nimm()
                tiefe += (z == "{") - (z == "}")
                if tiefe == 0:
                    return
        else:
            while self.schau()[1] not in (";", None):
                self.nimm()
            if self.schau()[1] == ";":
                self.nimm()

    def klammer_rest(self):
        tiefe = 1
        while self.schau()[1] is not None:
            z = self.nimm()
            tiefe += (z == "(") - (z == ")")
            if tiefe == 0:
                return

    # -------------------------------------------------------- Ausdruecke
    @staticmethod
    def wahr(wert):
        return isinstance(wert, D) and wert != 0

    def ausdruck(self):
        links = self.und()
        while self.schau()[1] == "||":
            self.nimm()
            rechts = self.und()
            links = D(1) if self.wahr(links) or self.wahr(rechts) else D(0)
        return links

    def und(self):
        links = self.vergleich()
        while self.schau()[1] == "&&":
            self.nimm()
            rechts = self.vergleich()
            links = D(1) if self.wahr(links) and self.wahr(rechts) else D(0)
        return links

    def vergleich(self):
        links = self.summe()
        while self.schau()[1] in ("==", "!=", "<", ">", "<=", ">="):
            op = self.nimm()
            links = D(1) if self._vergleichen(op, links, self.summe()) else D(0)
        return links

    @staticmethod
    def _vergleichen(op, a, b):
        if not isinstance(a, D) or not isinstance(b, D):
            a, b = str(a), str(b)
            return {"==": a == b, "!=": a != b}.get(op, False)
        return {"==": a == b, "!=": a != b, "<": a < b, ">": a > b,
                "<=": a <= b, ">=": a >= b}[op]

    def summe(self):
        links = self.produkt()
        while self.schau()[1] in ("+", "-"):
            op = self.nimm()
            rechts = self.produkt()
            if not isinstance(links, D) or not isinstance(rechts, D):
                links = MARKE
            else:
                links = links + rechts if op == "+" else links - rechts
        return links

    def produkt(self):
        links = self.vorzeichen()
        while self.schau()[1] in ("*", "/"):
            op = self.nimm()
            rechts = self.vorzeichen()
            if not isinstance(links, D) or not isinstance(rechts, D) \
                    or (op == "/" and rechts == 0):
                links = MARKE
            else:
                links = links / rechts if op == "/" else links * rechts
        return links

    def vorzeichen(self):
        if self.schau()[1] == "-":
            self.nimm()
            wert = self.vorzeichen()
            return -wert if isinstance(wert, D) else MARKE
        if self.schau()[1] == "+":
            self.nimm()
        return self.grundwert()

    def grundwert(self):
        art, wert = self.schau()
        if wert in ("$", ":"):
            self.nimm(); return self.grundwert()
        if wert == "(":
            self.nimm("(")
            innen = self.ausdruck()
            self.nimm(")")
            return innen
        if art == "zahl":
            self.nimm(); return D(wert)
        if art == "text":
            self.nimm(); return wert[1:-1]
        if art == "name":
            name = self.nimm()
            if name == "isnum":
                self.nimm("(")
                innen = self.ausdruck()
                self.nimm(")")
                return D(1) if isinstance(innen, D) else D(0)
            if self.schau()[1] == "(":
                # Ein Aufruf ins LIMS - ws_get_this_rec_hnd() und
                # Verwandte. Was dahintersteht, gibt es hier nicht; der
                # Aufruf liefert keine Zahl, und die Formeln pruefen das
                # mit isnum() selbst ab.
                self.nimm("(")
                self.klammer_rest()
                return MARKE
            return self.werte.get(name, MARKE)
        raise ValueError(f"Unerwartet: {wert!r}")


def rechnen(formel, werte, ziel, abfragen=None):
    """Fuehrt eine Formel aus und gibt den Wert des Zielkuerzels."""
    umgebung = dict(werte)
    try:
        marken = (_zerlegt(formel) if isinstance(formel, str)
                  else zerlegen(formel))
        auswerter = Auswerter(marken, umgebung, abfragen)
        while auswerter.schau()[1] is not None:
            auswerter.anweisung()
    except Exception as fehler:                      # noqa: BLE001
        return f"FEHLER: {fehler}"
    return umgebung.get(ziel, MARKE)
