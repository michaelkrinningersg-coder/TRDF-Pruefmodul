"""
TRDF-Pruefmodul - das Modell einer Serie, ohne Oberflaeche
==========================================================

Was die Seite "TRDF Pruefung" weiss und rechnet - ohne ein einziges
Fenster. Die Tk-Seite (trdfreiter.py) und die Weboberflaeche
(trdfweb.py) stehen beide darauf: die eine zeichnet daraus Text-Raster,
die andere schickt es als JSON an das Svelte-Frontend. Gerechnet,
geprueft und zum Schreiben vorbereitet wird nur hier, damit beide
Oberflaechen dasselbe sagen.

Die Tabellen kommen als Woerterbuecher (`rohtafel`, `ergebnistafel`,
`prueftafel`): Spalten, Kopfzeilen, Zeilen und Marken. Eine Marke ist
"geaendert" (von Hand bewegt - rot), "abweichung" (Befund - amber),
"gruppe" (Toenung eines Spaltenpaares) oder "ersatz" (Wert aus einer
anderen Anlage derselben Probe).
"""

from __future__ import annotations

import config
import lims_db
import trdf
import trdfexport
import trdflegende
import trdfpruefung
import trdfrohpruefung
import trdfserie

# Wie viele Nachkommastellen die Anzeige zeigt.
STELLEN = 3

# Der Wiederfindungsgrad steht in Prozent und wird gelesen, nicht
# nachgerechnet - eine Stelle genuegt. Gerechnet wird weiter mit dem
# vollen Wert, wie ihn das LIMS liefert.
STELLEN_WGH = 1

# Woher die Rohwerte kommen, mit denen gerechnet wird - es ergibt sich
# von selbst:
#
#   eingefuegte UM  die Liste aus der Probenvorbereitung, sobald eine
#                   eingefuegt und uebernommen ist. Damit prueft man,
#                   ob die Uebernahme ins LIMS stimmt.
#   LIMS            sonst die Rohwerte der Ergebniszeilen im LIMS.
#
# Wo die eingefuegte UM eine Luecke hat, tritt das LIMS ein; von Hand
# geaenderte Werte stechen immer. "Leeren" im Einfuegefenster schaltet
# zurueck auf das LIMS. Ob der Teilprobenanhang - aus ihm rechnet das
# LIMS - dasselbe sagt wie die Ergebniszeile, prueft die Rohwertpruefung
# ohnehin ("Rohwert am Anhang weicht ab"), und "Anhang angleichen"
# bringt beides zusammen.
QUELLE_TEXT = "eingefuegte UM"
QUELLE_LIMS = "LIMS"
QUELLEN = (QUELLE_TEXT, QUELLE_LIMS)

# Die Probenart steckt im Seriennamen: 2026B051 - das Zeichen hinter
# der Jahreszahl. Dieselben Namen wie in der Tabelle PROBENART des
# LIMS: 1 Boden, 2 Pflanze, 3 Wasser, 4 Humus. Ein "H" ist damit
# Humus und nicht Holz - Holz gibt es dort nicht, und eine Humusserie
# unter falschem Namen zu fuehren heisst, sie nicht zu finden.
PROBENARTEN = {"B": "Boden", "P": "Pflanze", "H": "Humus", "W": "Wasser"}

# Und dieselben Namen zur PART_ID der Ergebniszeile. Das ist die
# Auskunft des LIMS; der Buchstabe im Seriennamen ist die
# Hausschreibweise davon.
PROBENART_ZU_ID = {1: "Boden", 2: "Pflanze", 3: "Wasser", 4: "Humus"}

# Wie die Spalte heisst, in der das Urteil steht - in beiden Tabellen
# dieselbe, damit sie an derselben Stelle gesucht wird.
BEWERTUNGSSPALTE = trdfrohpruefung.BEWERTUNGSSPALTE

# Wie die drei Tabellen in den Einstellungen heissen. Unter diesen
# Namen liegen ihre Spaltenreihenfolge und die Spalten, die links
# stehen bleiben - und unter denselben stehen sie im Fenster „Info“.
BLATT_ROH = "Rohwerte"
BLATT_ERGEBNIS = "Ergebnisse"
BLATT_PRUEFUNG = "Pruefung"

# Was in der Ergebnistabelle steht, wenn gebucht und gerechnet
# auseinandergehen. Genannt werden die Groessen selbst: bei zwoelf
# Paaren ist "hier stimmt etwas nicht" keine Auskunft.
AUSEINANDER = "LIMS ungleich gerechnet: {}"

# Was im Pruefblatt vor jedem anderen Urteil steht: ohne vollstaendige
# Rohwerte hat das LIMS nichts gerechnet, und LabControl auch nicht.
ROHWERTE_UNVOLLSTAENDIG = "Rohwerte unvollstaendig"

# Wie breit die Spalten des Pruefblattes stehen. Die Kopfzeile traegt
# den Parameternamen; wird sie abgeschnitten, ist die Spalte nicht mehr
# zu erkennen - deshalb steht die Breite hier und nicht auf Vorgabe.
BREITEN = {"Zeile": 56, "Probe-Nr.": 104, "Skelettanteil": 104,
           "SKA63": 88, "SKAgs63": 88, "Faktor B/F": 80,
           "GBFAnt63gs": 104, "FBVorrat": 100, "TRDF": 88, "Cges": 84,
           "CO3": 84, "Bewertung": 320}

# Was ueber einer Zelle steht, deren Wert von einer anderen Anlage
# derselben Probe kommt. Die PROB_ID gehoert dazu: ohne sie ist die
# Zahl nicht nachzusehen.
NACHGETRAGEN = ("nachgetragen aus PROB_ID {prob_id}{woher} - an dieser "
                "Probe der Serie ist kein Aufschluss gebucht")


def _nachtragsteil(geholt) -> dict:
    """Das Ergebnis von `_nachtrag_holen` als Eintraege des Abrufs."""
    liste, fehler = geholt
    return {"aufschlussnachtrag": liste, "nachtragsfehler": fehler}


def _probenkennungen(ergebnisse) -> list:
    """Die PROB_ID eines Abrufs - einmal je Probe.

    Sie stehen in den Ergebniszeilen schon da. Eine Abfrage, die sie
    benutzt, greift ueber den Primaerschluessel; eine, die die
    Probennummer gross schreibt, geht die ganze Tabelle durch.
    """
    return sorted({zeile["prob_id"] for zeile in ergebnisse or []
                   if zeile.get("prob_id") is not None})


def _ohne_anhang(ergebnisse, anhang) -> list:
    """Die PROB_ID der Proben, zu denen kein Teilprobenanhang kam.

    Nur nach diesen wird nachgefragt. Steht der Anhang an jeder Probe
    der Serie - der Regelfall -, bleibt die Liste leer und die
    Abfrage entfaellt ganz.

    Gefragt wird nach der Probe und nicht nach der Anlage: kam der
    Anhang unter einer anderen PROB_ID derselben Probennummer, ist er
    da, und ein zweites Mal zu fragen brachte dieselben Zeilen.
    """
    haben = {zeile.get("prob_id") for zeile in anhang or ()}
    nummern = {trdf.probenschluessel(zeile.get("probe_nr"))
               for zeile in anhang or ()}
    nummern.discard("")
    offen = []
    for zeile in ergebnisse or ():
        if zeile.get("prob_id") in haben:
            continue
        if trdf.probenschluessel(zeile.get("probe_nr")) in nummern:
            continue
        offen.append(zeile.get("prob_id"))
    return sorted({kennung for kennung in offen if kennung is not None})


def _mit_nachtrag(zugang, um_id, ergebnisse, anhang, verbindung=None) -> list:
    """Den Anhang um die Zeilen anderer Anlagen derselben Probe ergaenzen.

    Der Teilprobenanhang haengt an der PROB_ID, und dieselbe Probe
    steht im LIMS mehrfach - einmal je Untersuchungsmethode. Die
    Serie sieht dann nur die eine Anlage, und die Rohwerte bleiben
    leer, obwohl sie gebucht sind.

    Nachgefragt wird unter derselben Methode: wer TRDF3.2 abruft,
    bekommt die Rohwerte der TRDF3.2 und nicht die der verworfenen
    TRDF3.1, die daneben an derselben Probe haengt.
    """
    offen = _ohne_anhang(ergebnisse, anhang)
    if not offen:
        return list(anhang or [])
    return list(anhang or []) + lims_db.trdf_rohwerte_nachtrag(
        zugang, offen, um_id, verbindung=verbindung)


def _ohne_aufschluss(ergebnisse, aufschluss) -> list:
    """Die PROB_ID der Proben, denen Cges oder CO3 fehlt.

    Nur nach diesen wird nachgefragt. Steht der Aufschluss an jeder
    Probe der Serie - der Regelfall -, bleibt die Liste leer und die
    Abfrage entfaellt ganz.
    """
    gebucht = {}
    for eintrag in aufschluss or []:
        name = trdf.ATNULL_PARAMETER.get(eintrag.get("para_id"))
        if name and str(eintrag.get("mw") or "").strip():
            gebucht.setdefault(eintrag["prob_id"], set()).add(name)
    vollstaendig = set(trdf.ATNULL_PARAMETER.values())
    return [kennung for kennung in _probenkennungen(ergebnisse)
            if gebucht.get(kennung, set()) != vollstaendig]


def methodentexte(methoden) -> list:
    """Je Untersuchungsmethode ein Text, der nur sie meint.

    Das Haus fuehrt dieselbe Methode je Probenart einmal: TRDF3.2
    fuer den Boden und TRDF3.2 fuer den Humus sind zwei UM_ID mit
    demselben Kuerzel. In einer Liste, die zweimal "TRDF3.2" zeigt,
    ist die zweite nicht zu waehlen - und welche die erste war, stand
    nirgends. Deshalb traegt der Text die UM_ID, sobald ein Kuerzel
    mehrfach vorkommt; kommt es einmal vor, bleibt es, wie es ist.

    Zurueck kommen (um_id, Kuerzel, Text) in der Folge der Liste.
    """
    haeufig = {}
    for _um, kuerzel in methoden or ():
        name = str(kuerzel or "").strip()
        haeufig[name] = haeufig.get(name, 0) + 1
    gebaut = []
    for um_id, kuerzel in methoden or ():
        name = str(kuerzel or "").strip()
        gebaut.append((um_id, name,
                       name if haeufig.get(name, 0) < 2
                       else f"{name} (UM {um_id})"))
    return gebaut



def probenart(serie: str) -> str:
    """Boden, Pflanze, Holz oder Wasser - aus dem Namen der Serie."""
    text = str(serie or "").strip().upper()
    if len(text) < 5 or not text[:4].isdigit():
        return ""
    return PROBENARTEN.get(text[4], "")


def zahltext(wert, stellen=STELLEN) -> str:
    """Eine Zahl fuer die Anzeige - mit Komma und fester Stellenzahl."""
    if not isinstance(wert, trdf.D):
        return trdf.MARKE if wert == trdf.MARKE else str(wert or "")
    gerundet = wert.quantize(trdf.D(1).scaleb(-stellen))
    return str(gerundet).replace(".", ",")


def vorschauhinweis(aenderungen, zurueck=False, nur_anhang=False) -> str:
    """Was ueber der Uebersicht vor dem Schreiben steht.

    Dieselben Saetze in beiden Oberflaechen: was geschrieben wird, wohin
    der alte Stand geht, und was an den Zeilen auffaellt.
    """
    ohne = trdfexport.ohne_zeile(aenderungen)
    wieder = [] if zurueck or nur_anhang else trdfexport.schon_korrigiert(
        aenderungen)
    if nur_anhang:
        hinweis = ("Geschrieben wird nur der Teilprobenanhang: er "
                   "bekommt den Wert, der in der Ergebniszeile steht. "
                   "Die Ergebniszeile selbst wird nicht angefasst - sie "
                   "ist hier die Vorlage. „Wert aktuell LIMS“ ist der "
                   "Stand am Anhang, „Wert neu“ der aus der "
                   "Ergebnistabelle. Der bisherige Wert des Anhangs "
                   "geht wie immer nach MW_OLD, und der Stand von jetzt "
                   f"vorher in den Ordner „{trdfexport.ORDNER}“.")
    elif zurueck:
        hinweis = ("Wiederhergestellt wird der ganze Stand von damals: "
                   "MW_ROH und MW, der Bearbeitungsstand, das "
                   "Korrekturkennzeichen und FC8 - und am "
                   "Teilprobenanhang MW und MW_OLD. Eine neue Sicherung "
                   "entsteht dabei nicht: die Datei, die gerade gelesen "
                   "wird, ist sie.")
        allein = trdfexport.ohne_anhang(aenderungen)
        if allein:
            hinweis += (
                f" ACHTUNG: {len(allein)} Rohwerte dieser Sicherung "
                "tragen keine ROHW_ID - fuer sie wird nur die "
                "Ergebniszeile zurueckgestellt, waehrend der "
                "Teilprobenanhang auf dem korrigierten Wert stehen "
                "bleibt. Danach rechnet das LIMS mit einer anderen "
                "Zahl als der, die in der Ergebnistabelle steht; die "
                "Pruefung meldet das als „Rohwert am Anhang weicht "
                "ab“. Solche Sicherungen stammen aus einer aelteren "
                "Fassung von LabControl.")
        leer = trdfexport.geleert(aenderungen)
        if leer:
            hinweis += (f" Bei {len(leer)} Werten stand vor der "
                        "Korrektur nichts - dort steht danach wieder "
                        f"nichts („{trdf.MARKE}“ in der Spalte "
                        "„Wert neu“).")
    else:
        hinweis = ("In ERGEBNISSE werden MW_ROH und MW mit demselben "
                   f"Wert geschrieben, dazu FC8 = „{lims_db.TRDF_FC8}“, "
                   "der Bearbeitungsstand und das Korrekturkennzeichen. "
                   "Ein Rohwert haengt zusaetzlich am Teilprobenanhang - "
                   "aus ihm rechnet das LIMS -, dort wird MW mitgesetzt "
                   "und der bisherige Wert nach MW_OLD gehoben. Der "
                   "Stand von jetzt geht vorher in den Ordner "
                   f"„{trdfexport.ORDNER}“.")
    mit_x = trdfexport.markiert(aenderungen)
    leer = trdfexport.geleert(aenderungen)
    if not zurueck and (mit_x or leer):
        teile = []
        if mit_x:
            teile.append(f"{len(mit_x)} Werte bekommen ein „"
                         f"{trdf.MARKE}“ (hier soll nichts stehen)")
        if leer:
            teile.append(f"{len(leer)} Werte werden geleert")
        hinweis += (" " + " und ".join(teile) + " - so, wie es die "
                    "Eingabemaske des LIMS beim Wechsel der Variante "
                    "auch tut.")
    if ohne:
        hinweis += (f" {len(ohne)} Werte haben im LIMS keine "
                    "Ergebniszeile - sie werden gemeldet und nicht "
                    "angelegt.")
    if wieder:
        hinweis += (f" {len(wieder)} Zeilen tragen schon ein "
                    "Korrekturkennzeichen: dort war bereits jemand.")
    return hinweis


class TrdfModell:
    """Eine Serie unter einer Untersuchungsmethode - Daten, Rechnung, Urteil.

    Die Oberflaeche leitet ab oder haelt eines. Wo das Modell etwas zu
    sagen haette, das man sehen soll, ruft es einen Haken
    (`_quelle_zeigen`); die Oberflaeche ueberschreibt ihn, das Modell
    selbst tut dort nichts.
    """

    def __init__(self, ordner=None, konfig=None):
        self._ordner = ordner or config.get_runtime_dir()
        self._konfig = konfig
        self.serie = ""
        # Diese gehoeren *nicht* in `_leeren` - sie gehoeren der Auswahl
        # und nicht dem Abruf.
        self.serienliste = []
        self.abgefragte_serie = ""
        self.methodenwahl = []
        self._leeren()

    def seriename(self) -> str:
        """Die Serie, um die es gerade geht."""
        return str(self.serie or "").strip()

    # ---------------------------------------------------------- Haken
    def _quelle_zeigen(self):
        """Die Oberflaeche sagt, woher die Rohwerte kommen."""

    @staticmethod
    def trdf_methoden_der_serie(methoden) -> list:
        """Aus den Methoden einer Serie die, deren Kuerzel TRDF traegt.

        Die ausgeschlossenen bleiben draussen: TRDF3.1 traegt dieselben
        Groessen unter derselben Bezeichnung wie TRDF3.2, und welche der
        beiden Zahlen dann gilt, entschiede die Reihenfolge und nicht
        das Labor.
        """
        return [(um, str(k or "").strip()) for um, k in methoden or ()
                if lims_db.TRDF_MARKE in str(k or "").upper()
                and not lims_db.ist_ausgeschlossen(k)]

    def _nachtrag_holen(self, zugang, prob_ids, verbindung=None) -> tuple:
        """Cges und CO3 ueber alle Anlagen dieser Proben.

        `prob_ids` sind die Proben, denen der Aufschluss *fehlt* - nicht
        alle. Steht er an jeder Probe der Serie, ist die Liste leer, und
        der Abruf kostet keine Abfrage.

        Zurueck kommen (Liste, Grund). Gescheitert wird hier und nicht
        am Abruf: der Aufschluss ist eine Beigabe, die Serie ist die
        Arbeit. Gesagt wird es aber - eine Spalte, die leer bleibt,
        sieht sonst aus wie eine ohne gebuchten Wert.
        """
        if not prob_ids:
            return [], ""
        try:
            return lims_db.trdf_aufschluss_nachtrag(
                zugang, prob_ids, verbindung=verbindung), ""
        except Exception as fehler:               # noqa: BLE001
            return [], (f"Cges/CO3 nicht nachgefragt: "
                        f"{lims_db.fehlertext(fehler)}")

    def _probenart_der_zeilen(self, geholt) -> str:
        """Die Probenart aus den gebuchten Zeilen - PART_ID des LIMS.

        Nicht aus dem Seriennamen: der ist die Hausschreibweise, und
        bei einzelnen Proben gibt es keinen. Stehen mehrere darin,
        werden sie genannt - eine davon zu waehlen waere geraten.

        Ohne PART_ID bleibt der Name der Serie als Notnagel: eine
        Auskunft aus dem Namen ist besser als keine.
        """
        arten = []
        for zeile in geholt.get("ergebnisse") or ():
            name = PROBENART_ZU_ID.get(zeile.get("part_id"))
            if name and name not in arten:
                arten.append(name)
        if arten:
            return " und ".join(arten)
        return probenart(self.seriename())

    def _formelkuerzel(self, kurz):
        """Das Kuerzel, mit dem die Formeln rechnen - zu einem kurzen."""
        return self.rohkuerzel.get(str(kurz or "").strip(), kurz)

    def _namen_merken(self, rohwerte):
        """Wie die Groessen im LIMS heissen - fuer die Legende.

        Gerechnet wird mit den Formelkuerzeln, im Pruefplan des Labors
        stehen die Parameternamen. Wer beides nebeneinander sieht, muss
        nicht raten, welche Spalte gemeint ist.
        """
        for eintrag in rohwerte:
            if eintrag["formelkuerzel"]:
                self.parameternamen.setdefault(
                    self._formelkuerzel(eintrag["formelkuerzel"]),
                    eintrag["name"])
        for methode in self.methoden:
            name = methode.get("parameter") or methode.get("name")
            if methode["formelkuerzel"] and name:
                self.parameternamen[methode["formelkuerzel"]] = name

    def _anhang_zuordnen(self, geholt):
        """Die Rohwerte am Teilprobenanhang - die zweite Stelle im LIMS.

        Aus ihr rechnen die Formeln des LIMS. Wer nur die Ergebniszeile
        korrigiert, aendert am Rechenweg nichts - deshalb wird sie hier
        mitgelesen und beim Zurueckschreiben mit angefasst.

        Zugeordnet wird ueber die **Probennummer** und nicht ueber die
        PROB_ID. Dieselbe Probe steht im LIMS unter mehreren Anlagen -
        einmal je Untersuchungsmethode -, und der Anhang haengt dann an
        einer anderen als die Ergebniszeile. Vorher fiel er dabei still
        heraus: die Rohwerte standen im LIMS, im Reiter stand nichts,
        und keine Meldung sagte warum.

        Die PROB_ID bleibt der zweite Weg - fuer die Zeilen, die ihre
        Probennummer nicht mitbringen.
        """
        nummern = {zeile["prob_id"]: trdf.probenschluessel(zeile["probe_nr"])
                   for zeile in geholt["ergebnisse"]}
        bekannt = set(nummern.values())
        for zeile in geholt.get("anhang", ()):
            probe = (trdf.probenschluessel(zeile.get("probe_nr"))
                     or nummern.get(zeile["prob_id"]))
            kuerzel = self._formelkuerzel(zeile["formelkuerzel"])
            # Nur zu Proben, die auch in der Tabelle stehen: eine
            # Nummer, die der Abruf nicht gebracht hat, gehoert nicht
            # in diese Serie.
            if probe and kuerzel and probe in bekannt:
                self.anhang[(probe, kuerzel)] = zeile

    def _wgh_zuordnen(self, geholt):
        """Wiederfindungsgrad und Aufschluss haengen an der PROB_ID."""
        nummern = {zeile["prob_id"]: trdf.probenschluessel(zeile["probe_nr"])
                   for zeile in geholt["ergebnisse"]}
        for prob_id, wert in geholt["wgh"].items():
            probe = nummern.get(prob_id)
            if probe:
                self.wgh[probe] = wert
        for eintrag in geholt["aufschluss"]:
            probe = nummern.get(eintrag["prob_id"])
            name = trdf.ATNULL_PARAMETER.get(eintrag["para_id"])
            if probe and name:
                self.aufschluss.setdefault(probe, {})[name] = eintrag["mw"]
        self._aufschluss_nachtragen(geholt, set(nummern.values()))

    def _aufschluss_nachtragen(self, geholt, eigene):
        """Cges und CO3, die an einer anderen PROB_ID derselben Probe stehen.

        Dieselbe Probe steht im LIMS mehrfach - dieselbe PROBE_NR unter
        einer anderen PROB_ID, oft in einer anderen Serie -, und der
        Aufschluss ist nur an einer von ihnen gebucht. Die Spalte blieb
        dann leer, obwohl das Labor die Zahl hat, und die Pruefungen,
        die auf dem Kohlenstoff stehen, kamen zu keinem Urteil.

        Nachgetragen wird nur, wo an der eigenen PROB_ID nichts steht.
        Ein vorhandener Wert wird nie ersetzt: die Zahl zweier
        verschiedener Anlagen derselben Nummer ist nicht dieselbe Zahl,
        und welche gilt, entscheidet nicht die Reihenfolge einer
        Abfrage.
        """
        for eintrag in geholt.get("aufschlussnachtrag") or []:
            probe = trdf.probenschluessel(eintrag.get("probe_nr"))
            name = trdf.ATNULL_PARAMETER.get(eintrag.get("para_id"))
            if not name or probe not in eigene:
                continue
            if str(self.aufschluss.get(probe, {}).get(name) or "").strip():
                continue
            if (probe, name) in self.aufschlussherkunft:
                continue        # die erste Zeile gilt - die hoechste PROB_ID
            self.aufschluss.setdefault(probe, {})[name] = eintrag["mw"]
            serie = str(eintrag.get("serie") or "").strip()
            self.aufschlussherkunft[(probe, name)] = NACHGETRAGEN.format(
                prob_id=eintrag.get("prob_id"),
                woher=f", Serie {serie}" if serie else "")

    def aufschlusshinweis(self, probe: str, spalte: str):
        """Woher ein nachgetragener Aufschlusswert kommt - sonst None."""
        return self.aufschlussherkunft.get((probe, spalte))

    def _fehlende_vormerken(self) -> int:
        """Was die Liste bringt und im LIMS noch fehlt, wird geschrieben.

        Steht ein Rohwert im LIMS noch gar nicht, ist die Liste die
        einzige Quelle - er wird vorgemerkt wie eine Handeingabe: rot,
        aenderbar und ueber \u201eExport\u201c schickbar.
        Steht dort schon etwas, bleibt die Liste ein Vergleich (amber):
        ein gebuchter Wert wird nicht still durch einen eingefuegten
        ersetzt. Was schon von Hand dasteht, sticht.
        """
        eigene = {probe for _lnr, probe in self.proben}
        vorgemerkt = 0
        for probe, werte in self.eingefuegt.items():
            if probe not in eigene:
                continue
            for kuerzel, wert in werte.items():
                if kuerzel not in self.rohliste or \
                        not str(wert or "").strip() or \
                        (probe, kuerzel) in self.vonhand or \
                        str(self.limsroh.get(probe, {}).get(kuerzel)
                            or "").strip():
                    continue
                self.vonhand[(probe, kuerzel)] = str(wert).strip()
                vorgemerkt += 1
        return vorgemerkt

    def _quellstand(self) -> str:
        """Wie viele Werte die Quelle je Probe liefert."""
        if not self.proben:
            return f"Rohdaten aus: {self.quelle}"
        gefunden = sum(
            1 for _, probe in self.proben for kuerzel in self.rohliste
            if not trdf.leer(self.aus_der_quelle(probe, kuerzel)))
        moeglich = len(self.proben) * len(self.rohliste)
        return (f"Rohdaten aus: {self.quelle}  |  {gefunden} von {moeglich} "
                f"Zellen belegt")

    def von_hand_bewegt(self, probe: str) -> bool:
        """Ob in dieser Probe ein Rohwert von Hand steht."""
        return any(welche == probe for (welche, _k) in self.vonhand)

    def ist_leer(self, probe: str, kuerzel: str) -> bool:
        """Steht hier wirklich nichts - weder Zahl noch x?

        Die Tabelle zeigt eine leere Zelle als x; fuer das Fuellen und
        das Kopieren nach unten zaehlt aber der Unterschied: ein x heisst
        "hier soll nichts stehen" (so setzt es die Variante), leer heisst
        "hier steht noch nichts".
        """
        return not str(self.rohwert(probe, kuerzel) or "").strip()

    def rohwert(self, probe: str, kuerzel: str) -> str:
        """Der Wert, mit dem gerechnet wird - und woher er kommt.

        Von Hand geaendert sticht alles; danach der eingefuegte Text,
        zuletzt das LIMS. So rechnet die Pruefung mit dem, was der Mensch
        gerade vor sich hat.
        """
        if (probe, kuerzel) in self.vonhand:
            return self.vonhand[(probe, kuerzel)]
        return self.rohwert_ohne_hand(probe, kuerzel)

    def aus_der_quelle(self, probe: str, kuerzel: str):
        """Der Rohwert aus der eingefuegten UM - None, wo keiner steht.

        Ohne eingefuegte UM gibt es keinen, und es gilt das LIMS; mit
        ihr kann sie Luecken haben, und dort tritt das LIMS ein.
        """
        return self.eingefuegt.get(probe, {}).get(kuerzel)

    def rohwert_ohne_hand(self, probe: str, kuerzel: str) -> str:
        """Derselbe Wert, aber so, wie er ohne die Handeingabe waere.

        Er ist der Vergleichsmassstab: nur was sich zwischen dieser
        Rechnung und der mit den Handwerten bewegt, ist eine Korrektur.
        """
        aus_der_quelle = self.aus_der_quelle(probe, kuerzel)
        if aus_der_quelle is not None and not trdf.leer(aus_der_quelle):
            return aus_der_quelle
        return self.limsroh.get(probe, {}).get(kuerzel, "")

    def _rechnen(self, probe: str, mit_hand=True) -> dict:
        hole = self.rohwert if mit_hand else self.rohwert_ohne_hand
        roh = {kuerzel: trdf.zahl(hole(probe, kuerzel))
               for kuerzel in self.rohliste}
        return trdf.rechnen(roh, self.formeln,
                            trdf.zahl(self.wgh.get(probe)), self.folge)

    def gerechnet(self, probe: str) -> dict:
        """Die berechneten Groessen - mit allem, was gerade gilt.

        Gemerkt, weil dieselbe Probe in einem Durchgang mehrfach gefragt
        wird: einmal fuer die Ergebnisse, einmal fuer die Pruefung, und
        beim Bodenblock noch einmal. Zwoelf Formeln je Probe mal
        dreihundert Proben sind sonst dreimal so viel Arbeit wie noetig.
        """
        if probe not in self._mit_hand:
            self._mit_hand[probe] = self._rechnen(probe, mit_hand=True)
        return self._mit_hand[probe]

    def gerechnet_ohne_hand(self, probe: str) -> dict:
        """Wie es ohne die Handeingaben aussaehe.

        Hat diese Probe keine Handeingabe, ist es dieselbe Rechnung wie
        `gerechnet` - und muss nicht ein zweites Mal gerechnet werden.
        Bei dreihundert Proben und einer geaenderten Zelle war das der
        groesste Teil der Wartezeit nach einer Eingabe.
        """
        if not self.vonhand or not self.von_hand_bewegt(probe):
            return self.gerechnet(probe)
        if probe not in self._ohne_hand:
            self._ohne_hand[probe] = self._rechnen(probe, mit_hand=False)
        return self._ohne_hand[probe]

    def _rechnung_vergessen(self, proben=None):
        """Die gemerkten Rechnungen gelten nicht mehr - ganz oder je Probe.

        Ohne `proben` alle: nach einem Abruf, einer neuen Liste, einem
        Schreibweg. Mit `proben` nur diese: eine Eingabe aendert die
        Rohwerte genau einer Probe, und jede Probe rechnet nur mit ihren
        eigenen. Alle dreihundert neu zu rechnen hiesse, nach jeder Zahl
        eine Sekunde zu warten.
        """
        if proben is None:
            self._mit_hand, self._ohne_hand = {}, {}
            return
        for probe in proben:
            self._mit_hand.pop(probe, None)
            self._ohne_hand.pop(probe, None)

    def bewegt(self, probe: str) -> set:
        """Welche Groessen dieser Probe die Handeingabe verschoben hat."""
        bewegte = {kuerzel for (welche, kuerzel) in self.vonhand
                   if welche == probe}
        if not self.vonhand:
            return bewegte
        ohne, mit = self.gerechnet_ohne_hand(probe), self.gerechnet(probe)
        for kuerzel in self.folge:
            if trdfexport.verschoben(ohne.get(kuerzel), mit.get(kuerzel)):
                bewegte.add(kuerzel)
        return bewegte

    @staticmethod
    def eingetragen(wert):
        """Der Stand, den ein Feld meint - eine Zahl, ein x oder nichts.

        Das LIMS kennt diese drei, und alle drei sind eine Aussage: eine
        Zahl ist gemessen, ein „x“ heisst "hier soll nichts stehen"
        (so setzt es die Eingabemaske, wenn die Variante den Rohwert
        nicht braucht), und leer heisst "hier steht noch nichts".
        """
        zahl = trdf.zahl(wert)
        if zahl is not None:
            return zahl
        return trdf.MARKE if str(wert if wert is not None else "").strip() \
            else ""

    def aenderungen(self) -> list:
        """Was geschrieben wuerde: von Hand bewegt und im LIMS anders.

        Zwei Bedingungen, und beide muessen zutreffen. Eine Zahl, die
        LabControl schon immer anders sah als das LIMS, ist ein Befund
        der Pruefung - ueber sie entscheidet das Labor und nicht dieser
        Knopf. Erst die Handeingabe macht aus dem Befund eine Korrektur.

        Geschrieben wird jeder der drei Staende: eine Zahl, ein x und
        das Leeren. Wer die Variante wechselt, aendert damit nicht bloss
        Zahlen, sondern raeumt die Zeile auf - und das gehoert genauso
        in das LIMS wie eine berichtigte Zahl.
        """
        gefunden = []
        for lnr, probe in sorted(self.proben, key=lambda p: (p[1], p[0])):
            eckdaten = {"lnr": lnr, "probe": probe}
            for kuerzel in self.rohliste:
                if (probe, kuerzel) not in self.vonhand:
                    continue
                alt = self.limsroh.get(probe, {}).get(kuerzel)
                neu = self.eingetragen(self.vonhand[(probe, kuerzel)])
                if not trdfexport.bewegt(alt, neu):
                    continue
                gefunden.append(self._aenderung(eckdaten, kuerzel,
                                                trdfexport.ROHWERT, alt, neu))
            if not self.vonhand:
                continue
            ohne, mit = self.gerechnet_ohne_hand(probe), self.gerechnet(probe)
            for kuerzel in self.folge:
                neu = self.eingetragen(mit.get(kuerzel))
                if not trdfexport.verschoben(ohne.get(kuerzel), neu):
                    continue
                alt = self.gebucht.get(probe, {}).get(kuerzel)
                if not trdfexport.bewegt(alt, neu):
                    continue
                gefunden.append(self._aenderung(eckdaten, kuerzel,
                                                trdfexport.BERECHNET, alt,
                                                neu))
        return gefunden

    def _aenderung(self, eckdaten, kuerzel, art, alt, neu) -> dict:
        probe = eckdaten["probe"]
        return trdfexport.aenderung(
            eckdaten, kuerzel, art, alt, neu, self.zeilen.get((probe, kuerzel)),
            self.parameternamen.get(kuerzel, kuerzel),
            anhang=self.anhang.get((probe, kuerzel)))

    def pruefwerte(self, probe: str) -> dict:
        """Die Zahlen, mit denen die Pruefung arbeitet.

        Genommen wird, was LabControl gerechnet hat - danach wird ja
        gefragt. Wo keine Formel greift, tritt der gebuchte Wert des LIMS
        an seine Stelle: eine Probe ganz ohne Urteil hilft niemandem.
        """
        gerechnet = self.gerechnet(probe)
        werte = {}
        for kuerzel in (trdfpruefung.SKA, trdfpruefung.SKA_GEMESSEN,
                        trdfpruefung.SKA_GESCHAETZT, trdfpruefung.VORRAT,
                        trdfpruefung.TRDF):
            wert = trdf.zahl(gerechnet.get(kuerzel))
            if wert is None:
                wert = trdf.zahl(self.gebucht.get(probe, {}).get(kuerzel))
            werte[kuerzel] = wert
        for kuerzel in (trdfpruefung.GBFANT, trdfpruefung.FAKTOR):
            werte[kuerzel] = trdf.zahl(self.rohwert(probe, kuerzel))
        # Die zweite Trockenrohdichte nur, wo die Serie sie fuehrt: ohne
        # sie gibt es nichts zu vergleichen, und ein fehlender Wert
        # duerfte nicht wie eine Abweichung aussehen.
        if trdfpruefung.TRDF_ALT in self.formeln:
            werte[trdfpruefung.TRDF_ALT] = trdf.zahl(
                gerechnet.get(trdfpruefung.TRDF_ALT))
        werte[trdfpruefung.VARIANTE] = trdf.zahl(
            self.rohwert(probe, trdfpruefung.VARIANTE))
        aufschluss = self.aufschluss.get(probe, {})
        werte[trdfpruefung.CGES] = trdf.zahl(aufschluss.get("Cges"))
        werte[trdfpruefung.CO3] = trdf.zahl(aufschluss.get("CO3"))
        return werte

    def _serienblick(self) -> dict:
        """Was der Blick auf die ganze Serie sagt.

        Einmal je Durchgang. Heute ist es nur der Kohlenstoff - mehr
        Carbonat als Gesamt kann es nicht geben -, und das liesse sich
        auch je Probe fragen. Der Weg bleibt, weil hier eine Pruefung
        wieder hereinkommt, sobald der Plot der Bezug ist; siehe den
        Kopf von `trdfserie`.
        """
        return trdfserie.bewerten(
            [{"probe": probe,
              "cges": self.aufschluss.get(probe, {}).get("Cges"),
              "co3": self.aufschluss.get(probe, {}).get("CO3")}
             for _, probe in self.proben])

    def geprueft(self) -> list:
        """Alle Proben mit ihren Werten und ihrem Urteil - nach Probe-Nr.

        Was am Rohwert haengt, steht vorneweg: ein Urteil ueber eine
        Groesse aus einem fehlenden Rohwert ist keines, und wo die beiden
        Stellen im LIMS auseinandergehen, rechnet es mit einer Zahl, die
        in der Ergebnistabelle nicht steht.
        """
        aus_der_serie = self._serienblick()
        return [self.gepruefte_probe(lnr, probe, aus_der_serie)
                for lnr, probe in sorted(self.proben,
                                         key=lambda p: (p[1], p[0]))]

    def rohsatz(self, probe: str) -> dict:
        """Die Rohwerte einer Probe, so wie gerade gerechnet wird."""
        return {kuerzel: self.rohwert(probe, kuerzel)
                for kuerzel in self.rohliste}

    def rohbefund(self, probe: str) -> list:
        """Was an den Rohwerten dieser Probe auffaellt.

        Steht in der Variante ein x, faellt hier nichts mehr auf: die
        Teilprobe bekommt keine Variante, und damit fehlt auch keiner
        der Rohwerte, die eine braeuchte.
        """
        return trdfrohpruefung.bewerten(self.rohsatz(probe),
                                        self.wgh.get(probe),
                                        self._anhangvergleich(probe))

    def _anhangvergleich(self, probe: str) -> dict:
        """Rohwert je Stelle im LIMS - Ergebniszeile gegen Anhang.

        Nur was von Hand nicht angefasst wurde: ein Wert, den der
        Pruefer gerade aendert, steht ohnehin an beiden Stellen anders,
        und darueber gibt es schon eine rote Zelle.
        """
        vergleich = {}
        for kuerzel in self.rohliste:
            if (probe, kuerzel) in self.vonhand:
                continue
            am_anhang = self.anhang.get((probe, kuerzel))
            if am_anhang is None:
                continue
            vergleich[kuerzel] = (
                self.limsroh.get(probe, {}).get(kuerzel), am_anhang["mw"])
        return vergleich

    def auseinander(self) -> list:
        """Rohwerte, die im LIMS an den beiden Stellen verschieden stehen.

        Die Ergebniszeile zeigt der Mensch sich an, aus dem
        Teilprobenanhang rechnet das LIMS. Gehen die beiden auseinander,
        rechnet es mit einer Zahl, die in der Tabelle nicht steht - und
        niemand sieht es. Zurueck kommen Aenderungen im ueblichen
        Zuschnitt: der Anhang bekommt, was in der Ergebniszeile steht.
        """
        gefunden = []
        for lnr, probe in sorted(self.proben, key=lambda p: (p[1], p[0])):
            for kuerzel, (zeile, am_anhang) in sorted(
                    self._anhangvergleich(probe).items()):
                if trdf.zahl(zeile) is None or trdf.zahl(zeile) == trdf.zahl(
                        am_anhang):
                    continue
                gefunden.append(self._aenderung(
                    {"lnr": lnr, "probe": probe}, kuerzel,
                    trdfexport.ROHWERT, am_anhang, trdf.zahl(zeile)))
        return gefunden

    def rohblatt(self) -> list:
        """Alle Proben mit Rohwerten und Befund - fuer Tabelle und CSV."""
        return [{"lnr": lnr, "probe": probe, "werte": self.rohsatz(probe),
                 "wgh": zahltext(trdf.zahl(self.wgh.get(probe)),
                                 STELLEN_WGH),
                 "bewertung": self.rohbefund(probe)}
                for lnr, probe in self.proben]

    def _uebernommen(self, eine: dict):
        """Was geschrieben wurde, steht ab jetzt auch hier als LIMS-Stand."""
        probe, kuerzel = eine["probe"], eine["kuerzel"]
        text = trdfexport.wertfeld(eine["neu"])
        eimer = self.gebucht if eine["art"] == trdfexport.BERECHNET \
            else self.limsroh
        eimer.setdefault(probe, {})[kuerzel] = text
        zeile = self.zeilen.get((probe, kuerzel))
        if zeile is not None:
            zeile["mw_roh"] = zeile["mw"] = text
        am_anhang = self.anhang.get((probe, kuerzel))
        if am_anhang is not None:
            am_anhang["mw"] = text
        self.vonhand.pop((probe, kuerzel), None)

    def _gescheitert(self, geaendert, bericht: dict) -> list:
        """Die Aenderungen, bei denen nach dem Schreiben der alte Wert steht.

        Getroffen und trotzdem unveraendert - das ist der Fall, den man
        von aussen nicht sieht: die Anweisung lief durch, die Zeile gab
        es, und geschehen ist nichts.
        """
        zeilen = {(satz["prob_id"], satz["pm_id"], satz["pm_ver"])
                  for satz in bericht.get("nicht_uebernommen", ())}
        anhaenge = {(satz["prob_id"], satz["rohw_id"])
                    for satz in bericht.get("anhang_nicht_uebernommen", ())}
        gefunden = []
        for eine in geaendert:
            zeile, anhang = eine.get("zeile") or {}, eine.get("anhang") or {}
            if (zeile.get("prob_id"), zeile.get("pm_id"),
                    zeile.get("pm_ver")) in zeilen or (
                        anhang and (anhang.get("prob_id"),
                                    anhang.get("rohw_id")) in anhaenge):
                gefunden.append(eine)
        return gefunden

    def _einstellungen(self):
        """Die Einstellungen - erst wenn sie gebraucht werden.

        Das Hauptfenster gibt seine mit; ohne sie (im Bauplan, und wenn
        die Seite einmal allein steht) wird eine eigene geoeffnet.
        """
        if self._konfig is None:
            self._konfig = config.Config(runtime_dir=self._ordner)
        return self._konfig

    def beschreibungen(self) -> dict:
        """Was das Labor selbst zu den Groessen notiert hat."""
        gespeichert = self._einstellungen().get("trdf_beschreibung")
        return dict(gespeichert or {})

    def spaltenordnung(self, blatt: str) -> tuple:
        """Reihenfolge und feste Spalten einer Tabelle - aus den Einstellungen.

        Ohne Eintrag gilt, womit eine Tabelle von Haus aus anfaengt:
        die Zeile, die Probe und - bei den Rohwerten - die Variante.
        Ohne sie sagt keine Zahl der Zeile etwas.
        """
        konfig = self._einstellungen()
        reihenfolge = (konfig.get("trdf_reihenfolge") or {}).get(blatt) or []
        fest = (konfig.get("trdf_fest") or {}).get(blatt)
        if fest is None:
            fest = trdflegende.STANDARD_FEST
        return list(reihenfolge), list(fest)

    def kopfspalte(self) -> str:
        """Was in der Kopfzeile steht - das Kuerzel, der Name, die Einheit."""
        return str(self._einstellungen().get("trdf_kopfspalte")
                   or trdflegende.KOPFWAHL[0])

    def kopfspalten(self) -> dict:
        """Und was davon abweichend fuer einzelne Groessen gilt.

        Geschluesselt auf das Formelkuerzel wie die Beschreibung: eine
        Groesse heisst in den drei Tabellen verschieden, und wer sie
        einmal eingestellt hat, will das nicht dreimal tun.
        """
        return dict(self._einstellungen().get("trdf_kopfspalten") or {})

    def versteckt(self, blatt: str) -> list:
        """Welche Spalten dieser Tabelle ausgeblendet sind.

        Von Haus aus keine: wer eine Tabelle oeffnet, will erst einmal
        sehen, was es gibt.
        """
        gespeichert = (self._einstellungen().get("trdf_versteckt")
                       or {}).get(blatt)
        return list(gespeichert or [])

    def _geordnet(self, blatt: str, spalten, quellen=None,
                  roh=False) -> tuple:
        """Die Spalten einer Tabelle, wie der Pruefer sie sehen will.

        Zurueck kommen die Spalten, die die Tabelle zeigt, die, die
        links stehen bleiben, die Kopfzeile dazu - und alle Spalten,
        auch die ausgeblendeten. Die Legende braucht sie: aus einer
        Liste, in der eine ausgeblendete Spalte fehlt, liesse sie sich
        nicht wieder einblenden.
        """
        reihenfolge, fest = self.spaltenordnung(blatt)

        def schluessel(name):
            return trdflegende.schluessel(name, quellen)

        alle, gehalten = trdflegende.geordnet(spalten, schluessel,
                                              reihenfolge, fest)
        sortiert = trdflegende.sichtbar(alle, schluessel,
                                        self.versteckt(blatt), fest)
        koepfe = trdflegende.ueberschriften(
            alle, self.kopfspalte(), self.methoden, quellen,
            self.beschreibungen(), roh, self.kopfspalten())
        return sortiert, gehalten, koepfe, alle

    def _gemerkt(self, schluessel: str) -> str:
        """Was zuletzt in einem Feld stand - aus den Einstellungen."""
        try:
            return str(self._einstellungen().get(schluessel) or "")
        except Exception:                          # noqa: BLE001
            return ""

    def _leeren(self):
        self.um_id = None
        self.um_kuerzel = ""
        self.methoden = []           # Pruefmethoden mit Formeln
        self.formeln = {}            # Formelkuerzel -> Formel
        self.folge = []              # Rechenreihenfolge
        self.rohnamen = {}           # Spaltenname -> Formelkuerzel
        self.rohkuerzel = {}         # Kuerzel am Rohwert -> das der Formel
        self.parameternamen = {}     # Formelkuerzel -> Name im LIMS
        self.rohliste = []           # Formelkuerzel in der Reihenfolge des LIMS
        self.gebucht = {}            # probe -> Formelkuerzel -> Text
        self.limsroh = {}            # probe -> Formelkuerzel -> Text
        self.wgh = {}                # probe -> Text
        self.aufschluss = {}         # probe -> {"Cges", "CO3"}
        self.aufschlussherkunft = {}  # (probe, Name) -> woher der Wert kam
        self.eingefuegt = {}         # probe -> Formelkuerzel -> Text
        self.quelle = QUELLE_LIMS    # woher die Rohwerte kommen - von selbst
        self.vonhand = {}            # (probe, Formelkuerzel) -> Text
        self.zeilen = {}             # (probe, Kuerzel) -> Ergebniszeile
        self.anhang = {}             # (probe, Kuerzel) -> Zeile am Anhang
        self.bloecke = {}            # probe -> offenes Blockfenster
        self._mit_hand = {}          # gemerkte Rechnungen, mit Handwerten
        self._ohne_hand = {}         # dieselben ohne sie
        self.proben = []             # (lnr, probennummer)
        self.arbeitszeile = None     # die Probe, in der gerade getippt wird
        self.letzter_export = None   # der Bericht des letzten Schreibwegs

    def _rohspalten(self) -> tuple:
        """Die Spalten der Rohwerttabelle - auch die Legende fragt danach.

        Zurueck kommen die Spalten, die festen darunter und die
        Kopfzeile: beides steht in den Einstellungen und laesst sich
        unter „Info“ zurechtziehen.
        """
        return self._geordnet(
            BLATT_ROH,
            ["Zeile", "Probe"] + list(self.rohliste)
            + ["WGH", BEWERTUNGSSPALTE],
            roh=True)

    def _ergebnisspalten(self) -> tuple:
        """Die Spalten der Ergebnistabelle und ihre Gruppierung.

        Je Groesse zwei Spalten - und sie gehoeren zusammen. Damit das
        Auge sie als Paar liest und nicht als zwei Nachbarn, bekommt
        jede zweite Groesse einen zarten Hintergrund; die Zuordnung
        steht in `gruppen`.
        """
        gerechnet = list(self.folge)
        spalten = ["Zeile", "Probe"]
        for kuerzel in gerechnet:
            spalten += [f"{kuerzel} LIMS", f"{kuerzel} ber."]
        spalten += ["WGH", "Cges", "CO3", BEWERTUNGSSPALTE]
        spalten, fest, koepfe, alle = self._geordnet(BLATT_ERGEBNIS, spalten)
        # Getoent wird erst, wenn die Reihenfolge steht: der Wechsel
        # zaehlt Groesse fuer Groesse in der Reihenfolge, in der sie
        # dann tatsaechlich stehen.
        gruppen, nummer, vorheriges = {}, 0, None
        for name in spalten:
            if name in fest or name == BEWERTUNGSSPALTE:
                continue
            kuerzel = trdflegende.schluessel(name)
            if vorheriges is not None and kuerzel != vorheriges:
                nummer += 1
            vorheriges = kuerzel
            gruppen[name] = nummer % 2 == 1
        return spalten, gruppen, fest, koepfe, alle

    def _pruefspalten(self) -> tuple:
        """Die Spalten des Pruefblatts - in der Reihenfolge des Pruefers."""
        return self._geordnet(
            BLATT_PRUEFUNG,
            list(trdfpruefung.SPALTEN),
            trdfpruefung.QUELLEN)

    def spalten_ablegen(self, blatt: str, texte: dict,
                        ordnung=None) -> str:
        """Legt Beschreibungen und Spaltenordnung ab - "" wenn es klappte.

        Gespeichert wird nur, was auch dasteht: ein geleerter Text
        nimmt seinen Eintrag mit. Nichts davon geht in die Datenbank.
        """
        konfig = self._einstellungen()
        gespeichert = dict(konfig.get("trdf_beschreibung") or {})
        for schluessel, text in texte.items():
            if str(text or "").strip():
                gespeichert[schluessel] = str(text).strip()
            else:
                gespeichert.pop(schluessel, None)
        konfig.set("trdf_beschreibung", gespeichert)
        if ordnung:
            reihen = dict(konfig.get("trdf_reihenfolge") or {})
            reihen[blatt] = list(ordnung.get("reihenfolge") or [])
            konfig.set("trdf_reihenfolge", reihen)
            feste = dict(konfig.get("trdf_fest") or {})
            feste[blatt] = list(ordnung.get("fest") or [])
            konfig.set("trdf_fest", feste)
            verborgen = dict(konfig.get("trdf_versteckt") or {})
            verborgen[blatt] = list(ordnung.get("versteckt") or [])
            konfig.set("trdf_versteckt", verborgen)
            konfig.set("trdf_kopfspalte", str(ordnung.get("kopfspalte")
                                              or trdflegende.KOPFWAHL[0]))
            # Die Wahl je Groesse gilt ueber alle drei Tabellen: dieselbe
            # Groesse soll nicht in der einen ihren Namen und in der
            # anderen ihr Kuerzel tragen. Gespeichert wird, was in dieser
            # Legende zu sehen war - was sie nicht kannte, bleibt stehen.
            eigene = dict(konfig.get("trdf_kopfspalten") or {})
            for kuerzel in (ordnung.get("reihenfolge") or []):
                eigene.pop(str(kuerzel), None)
            for kuerzel, wert in (ordnung.get("kopfspalten") or {}).items():
                eigene[str(kuerzel)] = str(wert)
            konfig.set("trdf_kopfspalten", eigene)
        if not konfig.speichern():
            return konfig.meldung or "unbekannter Grund"
        return ""

    # ------------------------------------------------------------- Abruf
    def methoden_abfragen(self, zugang, serie: str) -> list:
        """Die TRDF-Methoden einer Serie - eine Verbindung dafuer."""
        with lims_db.sitzung(zugang) as verbindung:
            return self.trdf_methoden_der_serie(
                lims_db.methoden_fuer_serie(zugang, serie,
                                            verbindung=verbindung))

    def abruf_holen(self, zugang, serie: str, um_id, kuerzel: str) -> dict:
        """Holt alles, was zu Serie und Methode gehoert - eine Verbindung.

        Nicht eine Anmeldung je Abfrage: alle Abfragen dieses Abrufs
        laufen ueber dieselbe Verbindung.
        """
        with lims_db.sitzung(zugang) as v:
            ergebnisse = lims_db.trdf_ergebnisse(zugang, serie, um_id,
                                                 verbindung=v)
            # Der Aufschluss zuerst: danach steht fest, welchen Proben er
            # fehlt, und nur nach denen wird nachgefragt. Steht er an
            # jeder - der Regelfall -, entfaellt die Abfrage ganz.
            aufschluss = lims_db.trdf_aufschluss(zugang, serie, verbindung=v)
            return {
                "um_id": um_id, "kuerzel": kuerzel,
                "methoden": lims_db.trdf_pruefmethoden(
                    zugang, serie, um_id, verbindung=v),
                "rohwerte": lims_db.trdf_rohwertparameter(
                    zugang, um_id, verbindung=v),
                "ergebnisse": ergebnisse,
                "anhang": _mit_nachtrag(
                    zugang, um_id, ergebnisse,
                    lims_db.trdf_rohwerte_anhang(zugang, serie, um_id,
                                                 verbindung=v),
                    verbindung=v),
                "wgh": lims_db.trdf_wiederfindung(zugang, serie,
                                                  verbindung=v),
                "aufschluss": aufschluss,
                **_nachtragsteil(self._nachtrag_holen(
                    zugang, _ohne_aufschluss(ergebnisse, aufschluss),
                    verbindung=v))}

    def daten_uebernehmen(self, geholt) -> tuple:
        """Ein Abruf wird der neue Stand - zurueck kommt (Satz, Warnung)."""
        self._leeren()
        self.um_id, self.um_kuerzel = geholt["um_id"], geholt["kuerzel"]
        self.methoden = geholt["methoden"]
        self.formeln = {m["formelkuerzel"]: m["formel"] for m in self.methoden
                        if m["formelkuerzel"]
                        and str(m["formel"] or "").strip()}
        self.folge = trdf.reihenfolge(self.formeln)
        self.rohliste = [m["formelkuerzel"] for m in self.methoden
                         if m["formelkuerzel"] and m["formelkuerzel"]
                         not in self.formeln]
        # Ein Rohwert traegt zwei Kuerzel: ein kurzes am Parameter (und
        # damit am Teilprobenanhang und in der Vorbereitungsliste) und
        # das, mit dem die Formeln rechnen. Ohne die Bruecke gehoert
        # keiner der beiden Werte zu einer Groesse.
        self.rohkuerzel = trdf.zuordnen(geholt["rohwerte"], self.methoden,
                                        self.rohliste)
        self.rohnamen = {eintrag["name"]: self._formelkuerzel(
                             eintrag["formelkuerzel"])
                         for eintrag in geholt["rohwerte"]
                         if eintrag["name"] and eintrag["formelkuerzel"]}
        self._namen_merken(geholt["rohwerte"])
        nach_pm = {(m["pm_id"], m["pm_ver"]): m["formelkuerzel"]
                   for m in self.methoden}
        gesehen = {}
        for zeile in geholt["ergebnisse"]:
            probe = trdf.probenschluessel(zeile["probe_nr"])
            kuerzel = nach_pm.get((zeile["pm_id"], zeile["pm_ver"]))
            if kuerzel is None:
                continue
            gesehen.setdefault(probe, zeile["lnr"])
            eimer = self.gebucht if self.formeln.get(kuerzel) else self.limsroh
            eimer.setdefault(probe, {})[kuerzel] = zeile["mw_roh"]
            # Die Zeile selbst wird aufgehoben: ohne ihren vollen
            # Schluessel liesse sich eine Korrektur weder sichern noch
            # zurueckschreiben.
            self.zeilen[(probe, kuerzel)] = zeile
        self._wgh_zuordnen(geholt)
        self._anhang_zuordnen(geholt)
        self.proben = sorted(((lnr, probe) for probe, lnr in gesehen.items()),
                             key=lambda p: (p[0] is None, p[0], p[1]))
        satz = (f"Serie {self.seriename()} - {self.um_kuerzel}, "
                f"{len(self.proben)} Proben, {len(self.formeln)} berechnete "
                f"Groessen, {len(self.rohliste)} Rohwerte")
        ohne = [eintrag["formelkuerzel"] for eintrag in geholt["rohwerte"]
                if eintrag["formelkuerzel"]
                and eintrag["formelkuerzel"] not in self.rohkuerzel]
        if ohne:
            satz += ("  |  ohne Zuordnung zur Formel: " + ", ".join(ohne))
        if geholt.get("nachtragsfehler"):
            satz += f"  |  {geholt['nachtragsfehler']}"
        if self.aufschlussherkunft:
            satz += (f"  |  {len(self.aufschlussherkunft)} x Cges/CO3 aus "
                     f"einer anderen Anlage derselben Probennummer "
                     f"nachgetragen")
        return satz, bool(ohne)

    def auskunftstext(self, geholt) -> str:
        """Was oben neben der Ueberschrift steht: Methode und Probenart."""
        return (f"{self.um_kuerzel}  |  Probenart "
                f"{self._probenart_der_zeilen(geholt) or 'unbekannt'}")

    # ------------------------------------------------- Eingefuegte UM
    def um_lesen(self, inhalt: str) -> tuple:
        """Die Liste aus der Probenvorbereitung lesen.

        Zurueck kommt (geklappt, Satz, Art) - Art ist "text", "warn"
        oder "fehler". Was im LIMS noch fehlt, wird dabei zum Schreiben
        vorgemerkt.
        """
        if not str(inhalt or "").strip():
            return False, "Das Einfuegefeld ist leer.", "warn"
        try:
            gelesen = trdf.text_lesen(inhalt)
        except trdf.Einfuegefehler as fehler:
            return False, str(fehler), "fehler"
        unbekannt = [name for name in gelesen["spalten"]
                     if name not in self.rohnamen]
        self.eingefuegt = {}
        for zeile in trdf.ohne_wiederholungen(gelesen["zeilen"]):
            self.eingefuegt[zeile["probe"]] = {
                self.rohnamen[name]: wert
                for name, wert in zeile["werte"].items()
                if name in self.rohnamen}
        self._quelle_bestimmen()
        vorgemerkt = self._fehlende_vormerken()
        satz = (f"{len(self.eingefuegt)} Proben eingefuegt "
                f"(Serie {gelesen['serie']}, {gelesen['methode']}) - "
                f"gerechnet wird mit dieser Liste")
        if vorgemerkt:
            satz += (f"  |  {vorgemerkt} Werte, die im LIMS noch fehlen, "
                     f"zum Schreiben vorgemerkt")
        art = "text"
        if gelesen["serie"] and gelesen["serie"] != self.seriename():
            satz += f"  |  Achtung: abgerufen ist {self.seriename()}"
            art = "warn"
        if unbekannt:
            satz += ("  |  ohne Zuordnung: " + ", ".join(unbekannt))
            art = "warn"
        self._rechnung_vergessen()
        return True, satz, art

    def um_vergessen(self):
        """Die eingefuegte UM gilt nicht mehr - zurueck auf das LIMS."""
        self.eingefuegt = {}
        self._quelle_bestimmen()
        self._rechnung_vergessen()

    def _quelle_bestimmen(self):
        """Welche Quelle gilt - von selbst, nach dem, was eingefuegt ist.

        Ist eine UM eingefuegt und uebernommen, wird mit ihr gerechnet;
        sonst mit den Rohwerten des LIMS.
        """
        self.quelle = QUELLE_TEXT if self.eingefuegt else QUELLE_LIMS
        self._quelle_zeigen()

    def quelltext(self) -> str:
        """Woher die Rohwerte kommen - in einem Satz."""
        if self.quelle == QUELLE_TEXT:
            return (f"Rohwerte aus: eingefuegter UM "
                    f"({len(self.eingefuegt)} Proben)")
        return "Rohwerte aus: LIMS"

    # --------------------------------------------------- Von Hand
    def variante_setzen(self, probe: str, eingabe) -> dict:
        """Die neue Variante raeumt die Rohwerte auf, die sie nicht braucht.

        So haelt es die Eingabemaske des LIMS auch: was eine Variante
        nicht braucht, bekommt ein x - dann steht in der Zeile, dass
        dort nichts stehen soll, und nicht bloss nichts. Vorhandene
        Werte werden dabei ueberschrieben; "0" raeumt die Zeile ganz
        leer, ein eingegebenes x belegt sie ganz mit x.

        Nur beim Tippen in die Zelle und beim Kopieren nach unten - ein
        eingefuegter Block bringt seine Werte selbst mit.
        """
        neu = trdfrohpruefung.nach_variante(self.rohsatz(probe), eingabe)
        for kuerzel, wert in neu.items():
            self.vonhand[(probe, kuerzel)] = wert
        return neu

    # ------------------------------------------------------------ Tabellen
    #
    # Was in den drei Tabellen steht - Spalten, Kopfzeilen, Zeilen und
    # Marken -, fuer beide Oberflaechen gleich. Je Tabelle gibt es die
    # Zeile einer Probe allein: nach einer Eingabe aendert sich genau
    # eine, und die Weboberflaeche schickt nur sie.

    def rohzeile(self, lnr, probe: str) -> tuple:
        """(Werte, Marken, Befund) einer Probe in der Rohwerttabelle."""
        bewertung = self.rohbefund(probe)
        werte = {"Zeile": lnr, "Probe": probe,
                 "WGH": zahltext(trdf.zahl(self.wgh.get(probe)), STELLEN_WGH),
                 BEWERTUNGSSPALTE: trdfrohpruefung.bewertungstext(bewertung)}
        marken = {}
        for kuerzel in self.rohliste:
            werte[kuerzel] = self.rohwert(probe, kuerzel) or trdf.MARKE
            aus_der_quelle = self.aus_der_quelle(probe, kuerzel)
            im_lims = self.limsroh.get(probe, {}).get(kuerzel)
            if (probe, kuerzel) in self.vonhand:
                marken[kuerzel] = "geaendert"
            elif aus_der_quelle is not None and not (
                    trdf.leer(aus_der_quelle) and trdf.leer(im_lims)) and \
                    trdf.zahl(aus_der_quelle) != trdf.zahl(im_lims):
                marken[kuerzel] = "abweichung"
        if bewertung:
            marken[BEWERTUNGSSPALTE] = "abweichung"
        if self.von_hand_bewegt(probe):
            marken["Probe"] = "geaendert"
        return werte, marken, bool(bewertung)

    def variante_x(self, probe: str) -> bool:
        """Steht in der Variante ein x - "diese Teilprobe hat keine"?

        Solche Proben lassen sich ausblenden. Geschrieben werden sie
        trotzdem: der Export fragt nicht, was zu sehen ist.
        """
        return str(self.rohwert(probe, trdfrohpruefung.VARIANTE)
                   or "").strip().lower() == trdf.MARKE

    def _ohne_x(self, zeilen, ohne_x: bool) -> list:
        """Die Zeilen ohne Proben mit Variante x - nur fuer die Anzeige."""
        if not ohne_x:
            return zeilen
        return [(kennung, werte) for kennung, werte in zeilen
                if not self.variante_x(kennung)]

    def rohtafel(self, nur_befunde=False, ohne_x=False) -> dict:
        """Die Rohwerttabelle - wie sie dasteht, mit der Zeile darunter."""
        spalten, fest, koepfe, alle = self._rohspalten()
        zeilen, marken, auffaellig = [], {}, 0
        for lnr, probe in self.proben:
            werte, eigene, befund = self.rohzeile(lnr, probe)
            auffaellig += befund
            marken.update({(probe, name): marke
                           for name, marke in eigene.items()})
            zeilen.append((probe, werte))
        gesamt = len(zeilen)
        if nur_befunde:
            # Nur zeigen, wozu etwas zu sagen ist - gerechnet und
            # geschrieben wird weiter ueber die ganze Serie.
            zeilen = [(kennung, werte) for kennung, werte in zeilen
                      if werte.get(BEWERTUNGSSPALTE)]
        zeilen = self._ohne_x(zeilen, ohne_x)
        satz = (f"{gesamt - auffaellig} von {gesamt} Proben mit sauberen "
                f"Rohwerten"
                + (f"  |  {auffaellig} zu pruefen" if auffaellig else ""))
        if len(zeilen) < gesamt:
            satz += f"  |  {gesamt - len(zeilen)} ausgeblendet"
        return {"spalten": spalten, "fest": fest, "koepfe": koepfe,
                "alle": alle, "zeilen": zeilen, "marken": marken,
                "gesamt": gesamt, "auffaellig": auffaellig,
                "stand": (satz, "warn" if auffaellig else "text")}

    def ergebniszeile(self, lnr, probe: str, gruppen=None) -> tuple:
        """(Werte, Marken, auseinander) einer Probe in der Ergebnistabelle."""
        if gruppen is None:
            gruppen = self._ergebnisspalten()[1]
        ergebnis = self.gerechnet(probe)
        werte = {"Zeile": lnr, "Probe": probe,
                 "WGH": zahltext(trdf.zahl(self.wgh.get(probe)), STELLEN_WGH),
                 "Cges": zahltext(trdf.zahl(
                     self.aufschluss.get(probe, {}).get("Cges"))),
                 "CO3": zahltext(trdf.zahl(
                     self.aufschluss.get(probe, {}).get("CO3")))}
        marken = {name: "gruppe" for name, getoent in gruppen.items()
                  if getoent}
        # Erst nach der Toenung: sie ist Schmuck, dies ist eine Auskunft -
        # der Wert kommt von einer anderen Anlage derselben Nummer.
        for name in trdf.ATNULL_PARAMETER.values():
            if self.aufschlusshinweis(probe, name):
                marken[name] = "ersatz"
        bewegte = self.bewegt(probe)
        auseinander = []
        for kuerzel in self.folge:
            gebucht = self.gebucht.get(probe, {}).get(kuerzel)
            meins = ergebnis.get(kuerzel)
            stellen = trdfpruefung.stellen_fuer(kuerzel, STELLEN)
            werte[f"{kuerzel} LIMS"] = (
                trdf.MARKE if trdf.leer(gebucht)
                else zahltext(trdf.zahl(gebucht), stellen))
            werte[f"{kuerzel} ber."] = zahltext(meins, stellen)
            # Rot heisst: das habe *ich* gerade bewegt. Was nur anders
            # gebucht ist als gerechnet, bleibt ein Befund (amber).
            # Verglichen wird nur, wo im LIMS ueberhaupt etwas steht.
            if str(gebucht or "").strip() and not trdf.gleich(meins, gebucht):
                auseinander.append(kuerzel)
                marken[f"{kuerzel} LIMS"] = "abweichung"
                marken[f"{kuerzel} ber."] = "abweichung"
            if kuerzel in bewegte:
                marken[f"{kuerzel} LIMS"] = "geaendert"
                marken[f"{kuerzel} ber."] = "geaendert"
        if bewegte or self.von_hand_bewegt(probe):
            marken["Probe"] = "geaendert"
            marken["Zeile"] = "geaendert"
        werte[BEWERTUNGSSPALTE] = (AUSEINANDER.format(", ".join(auseinander))
                                   if auseinander else "")
        if auseinander:
            marken[BEWERTUNGSSPALTE] = "abweichung"
        return werte, marken, auseinander

    def ergebnistafel(self, ohne_x=False) -> dict:
        """Die berechneten Groessen neben dem, was das LIMS gebucht hat."""
        spalten, gruppen, fest, koepfe, alle = self._ergebnisspalten()
        zeilen, marken, abweichungen = [], {}, 0
        for lnr, probe in self.proben:
            werte, eigene, auseinander = self.ergebniszeile(lnr, probe,
                                                            gruppen)
            abweichungen += len(auseinander)
            marken.update({(probe, name): marke
                           for name, marke in eigene.items()})
            zeilen.append((probe, werte))
        gesamt = len(self.proben) * len(self.folge)
        satz = (f"{gesamt - abweichungen} von {gesamt} Werten stimmen"
                + (f"  |  {abweichungen} Abweichungen" if abweichungen
                   else ""))
        alle_zeilen = len(zeilen)
        zeilen = self._ohne_x(zeilen, ohne_x)
        if len(zeilen) < alle_zeilen:
            satz += f"  |  {alle_zeilen - len(zeilen)} Proben ausgeblendet"
        return {"spalten": spalten, "gruppen": gruppen, "fest": fest,
                "koepfe": koepfe, "alle": alle, "zeilen": zeilen,
                "marken": marken, "gesamt": gesamt,
                "abweichungen": abweichungen,
                "stand": (satz, "warn" if abweichungen else "text")}

    def gepruefte_probe(self, lnr, probe: str, aus_der_serie=None) -> dict:
        """Eine Probe des Pruefblatts - Werte und Urteil."""
        if aus_der_serie is None:
            aus_der_serie = self._serienblick()
        werte = self.pruefwerte(probe)
        bewertung = (trdfpruefung.bewerten(werte)
                     + aus_der_serie.get(probe, []))
        rohwerte = self.rohsatz(probe)
        vorneweg = trdfrohpruefung.anhang_ohne_variante(
            self._anhangvergleich(probe), rohwerte)
        if trdfrohpruefung.unvollstaendig(rohwerte):
            vorneweg = [ROHWERTE_UNVOLLSTAENDIG] + vorneweg
        return {"lnr": lnr, "probe": probe, "werte": werte,
                "bewertung": vorneweg + bewertung}

    def pruefzeile(self, eintrag: dict, spalten=None) -> tuple:
        """(Werte, Marken) einer Probe im Pruefblatt."""
        if spalten is None:
            spalten = self._pruefspalten()[0]
        probe = eintrag["probe"]
        werte = {"Zeile": eintrag["lnr"], "Probe-Nr.": probe,
                 "Bewertung": trdfpruefung.bewertungstext(
                     eintrag["bewertung"])}
        marken = {}
        bewegte = self.bewegt(probe)
        # Welche Zellen die Bewertung meint - sie werden wie die
        # Bewertung selbst gefaerbt.
        gemeint = trdfpruefung.betroffen(eintrag["bewertung"],
                                         trdfserie.BETROFFEN)
        for name in [eine for eine in spalten
                     if eine in trdfpruefung.QUELLEN]:
            kuerzel = trdfpruefung.QUELLEN[name]
            werte[name] = trdfpruefung.gerundet(
                eintrag["werte"].get(kuerzel),
                trdfpruefung.stellen_fuer(kuerzel))
            if kuerzel in bewegte:
                marken[name] = "geaendert"
            elif kuerzel in gemeint:
                marken[name] = "abweichung"
        for name in trdf.ATNULL_PARAMETER.values():
            if self.aufschlusshinweis(probe, name):
                marken[name] = "ersatz"
        if eintrag["bewertung"]:
            marken["Bewertung"] = "abweichung"
        if bewegte or self.von_hand_bewegt(probe):
            marken["Probe-Nr."] = "geaendert"
        return werte, marken

    def prueftafel(self, nur_befunde=False, ohne_x=False) -> dict:
        """Das Pruefblatt - eine Zeile je Probe, nach Probe-Nr."""
        spalten, fest, koepfe, alle = self._pruefspalten()
        zeilen, marken, auffaellig = [], {}, 0
        blatt = self.geprueft()
        for eintrag in blatt:
            werte, eigene = self.pruefzeile(eintrag, spalten)
            if eintrag["bewertung"]:
                auffaellig += 1
            marken.update({(eintrag["probe"], name): marke
                           for name, marke in eigene.items()})
            zeilen.append((eintrag["probe"], werte))
        gesamt = len(zeilen)
        if nur_befunde:
            mit_befund = {eintrag["probe"] for eintrag in blatt
                          if eintrag["bewertung"]}
            zeilen = [(kennung, werte) for kennung, werte in zeilen
                      if kennung in mit_befund]
        zeilen = self._ohne_x(zeilen, ohne_x)
        satz = (f"{gesamt - auffaellig} von {gesamt} Proben ohne Befund"
                + (f"  |  {auffaellig} zu pruefen" if auffaellig else ""))
        if len(zeilen) < gesamt:
            satz += f"  |  {gesamt - len(zeilen)} ausgeblendet"
        return {"spalten": spalten, "fest": fest, "koepfe": koepfe,
                "alle": alle, "zeilen": zeilen, "marken": marken,
                "blatt": blatt, "gesamt": gesamt, "auffaellig": auffaellig,
                "stand": (satz, "warn" if auffaellig else "text")}
