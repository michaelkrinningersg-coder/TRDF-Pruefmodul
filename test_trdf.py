"""Prueft den Rechenkern der TRDF-Pruefung - ohne Datenbank, ohne GUI.

Hier wird nachgerechnet, was das LIMS gerechnet hat. Ein Fehler faellt
nicht beim Ausprobieren auf, sondern erst, wenn eine Pruefung eine
Abweichung meldet, die keine ist - oder schlimmer: eine echte nicht
meldet.

Die Formeln und die Zeilen unten sind *echt*: sie stammen aus
PRUEFMETHODEN.FORMEL und aus der Serie 2026B051. Nachgebaute Formeln
haetten hier keinen Wert - geprueft werden soll ja gerade, dass die
Sprache des LIMS richtig gelesen wird.

Drei der sieben Zeilen sind die Faelle, in denen LabControl und LIMS
auseinandergehen. Sie stehen hier als Festpunkt: was heute als
Abweichung erkannt wird, soll morgen noch als Abweichung erkannt werden.

Aufruf:  python test_trdf.py
"""

from __future__ import annotations

import decimal

import trdf
import trdfformel

D = decimal.Decimal


# Die zwoelf Formeln, wie sie in PRUEFMETHODEN.FORMEL stehen.
FORMELN = {
    'FBMMini':
        'local_var child_rec_hnd,v_prob,v_wgh; child_rec_hnd=ws_get_this_rec_hnd(); $v_prob=ws_read_field_in_rec(child_rec_hnd,"PROB_ID",1); v_wgh = 0; {sql("select mw into :v_wgh from ergebnisse where prob_id= :v_prob and pm_id =(701)");} if (isnum($v_wgh) != 1 ) {   v_wgh = 0;}  if (isnum($_TRDV) != 1) {$FBMMini="x";}  else if ( _TRDV == 5 )  {FBMMini=(MMini/(1+(v_wgh/100)));}  else if ( _TRDV == 1 || _TRDV == 2 || _TRDV == 4 || _TRDV == 6 || _TRDV == 7 ) {$FBMMini="x";}',
    'FBMSchaufel':
        'local_var child_rec_hnd,v_prob,v_wgh; child_rec_hnd=ws_get_this_rec_hnd(); $v_prob=ws_read_field_in_rec(child_rec_hnd,"PROB_ID",1); v_wgh = 0; {sql("select mw into :v_wgh from ergebnisse where prob_id= :v_prob and pm_id =(701)");} if (isnum($v_wgh) != 1 ) {   v_wgh = 0;}  if (isnum($_TRDV) != 1) {$FBMSchaufel="x";}  else if ( _TRDV == 4 || _TRDV == 5 || _TRDV == 7)  {FBMSchaufel=(MSchaufel-GBM63Schaufel-GBM263Schaufel)/(1+(v_wgh/100));}  else if ( _TRDV == 1 || _TRDV == 2 || _TRDV == 6)  {$FBMSchaufel="x";}',
    'FBVSgs':
        'if (isnum($_TRDV) != 1) {$FBVSgs= "x";}  else if (_TRDV == 4 || _TRDV == 5 || _TRDV == 7)  {FBVSgs=_TSM*TRD_TRDF*100*(1-_SKASgs/100);}  else if (_TRDV == 1 || _TRDV == 2 || _TRDV == 6)  {$FBVSgs="x";}',
    'FBVS':
        'if (isnum($_TRDV) != 1) {$FBVS="x";}  else if (_TRDV == 4 || _TRDV == 5|| _TRDV == 7) {FBVS=_TSM*TRD_TRDF*100*(1-_SKAS/100);}  else if (_TRDV == 1 || _TRDV == 2 || _TRDV == 6)  {$FBVS="x";}',
    'FBVb':
        'if (isnum($_TRDV) != 1) {$FBVb="x";}  else if (_TRDV == 2 || _TRDV == 4 || _TRDV == 5|| _TRDV == 6 || _TRDV == 7) {FBVb=_TSM*TRD_TRDF*100*(1-_SKA/100);}  else if (_TRDV == 1) {FBVb=FBMSZ/VOLSZ*_TSM*100;}',
    'FBMSZ':
        'local_var child_rec_hnd,v_prob,v_wgh; child_rec_hnd=ws_get_this_rec_hnd(); $v_prob=ws_read_field_in_rec(child_rec_hnd,"PROB_ID",1); v_wgh = 0; { sql("select mw into :v_wgh from ergebnisse where prob_id= :v_prob and pm_id =(701)"); } if (isnum($v_wgh) != 1 ) {   v_wgh = 0;}  if (isnum($_TRDV) != 1) {$FBMSZ="x";}  else if ( _TRDV == 2 || _TRDV == 4 || _TRDV == 6)  {FBMSZ=(GMSZ-GBMSZ)/(1+(v_wgh/100));}  else if ( _TRDV == 1)  {FBMSZ=GMSZ/(1+(v_wgh/100));}  else if ( _TRDV == 5 || _TRDV == 7)  {$FBMSZ="x";}',
    '_SKASgs':
        'if (isnum($_TRDV) != 1) {$_SKASgs="x";}  else if (_TRDV == 4 || _TRDV == 5 || _TRDV == 7) {_SKASgs=VOLGB63gs+((100-VOLGB63gs)*(GBM263Schaufel/DichteGB/(GBM263Schaufel/DichteGB+FBMSchaufel/TRD_TRDF)));}  else if (_TRDV == 1|| _TRDV == 2|| _TRDV == 6) {$_SKASgs="x";}',
    '_SKAS':
        'if (isnum($_TRDV) != 1) {$_SKAS="x";}  else if (_TRDV == 4 || _TRDV == 5 || _TRDV == 7) {_SKAS=100*(GBM63Schaufel+GBM263Schaufel)/DichteGB/((GBM63Schaufel+GBM263Schaufel)/DichteGB+FBMSchaufel/TRD_TRDF);}  else if (_TRDV == 1|| _TRDV == 2|| _TRDV == 6) {$_SKAS="x";}',
    '_SKA':
        'if (isnum($SKAFoto)) {     _SKA = SKAFoto; } else if (isnum($_TRDV) != 1) {$_SKA="x"; } else if (_TRDV == 4 || _TRDV == 5 || _TRDV == 7) {     _SKA = _SKASgs; } else if (_TRDV == 2) {     _SKA = (GBMSZ / DichteGB) / VOLSZ * 100; } else if (_TRDV == 1) {     _SKA = 0; } else if (_TRDV == 6 ) {     _SKA = ((GBMSZ / DichteGB) / VOLSZ) * (100-VOLGB63gs) + VOLGB63gs; }',
    'TRD_TRDF':
        'if (isnum($_TRDV) != 1) {$TRD_TRDF="x";}  else if (_TRDV == 1 ) {TRD_TRDF=FBMSZ/VOLSZ;}  else if (_TRDV == 2 || _TRDV == 6) {TRD_TRDF=FBMSZ/(VOLSZ-(GBMSZ/DichteGB));}  else if (_TRDV == 4 ) {TRD_TRDF=((FBMSZ)/(VOLSZ-(GBMSZ/DichteGB)));}  else if (_TRDV == 5 ) {TRD_TRDF=FBMMini*(1-GBMSchaufel/(FBMSchaufel+GBMSchaufel))/(VOLMiniSZ-FBMMini*GBMSchaufel/(FBMSchaufel+GBMSchaufel)/DichteGB);}  else if (_TRDV == 7 ) {TRD_TRDF=TRDFgesch;}',
    'VOLAntGB263':
        'if (isnum($_TRDV) != 1) {$VOLAntGB263="x";}  else if (_TRDV == 1 || _TRDV == 2) {VOLAntGB263=_SKA;}  else if (_TRDV == 4 || _TRDV == 5 || _TRDV == 6 || _TRDV == 7) {VOLAntGB263=_SKA-VOLGB63gs;}',
    'VOLGB63gs':
        'if (isnum($_TRDV) != 1) {$VOLGB63gs="x";}  else if (_TRDV == 4 || _TRDV == 5 || _TRDV == 6 || _TRDV == 7) {VOLGB63gs=GBFAnt*FBLFL;}  else if (_TRDV == 1 || _TRDV == 2) {$VOLGB63gs="x";}',
}

# Echte Zeilen der Serie 2026B051, wie sie im LIMS stehen.
ZEILEN = {
    1: {"wgh": '0,306354382844253',
        "roh": {'_TRDV': '2', '_TSM': '30', 'FBLFL': 'x', 'VOLSZ': '400', 'GMSZ': '574', 'GBMSZ': '6,36', 'MSchaufel': 'x', 'GBM63Schaufel': 'x', 'GBM263Schaufel': 'x', 'GBMSchaufel': 'x', 'MMini': 'x', 'VOLMiniSZ': 'x', 'DichteGB': '2,64', 'GBFAnt': 'x', 'TRDFgesch': 'x', 'SKAFoto': 'x'},
        "lims": {'FBVSgs': 'x', 'FBVb': '4244,29740886698', 'FBVS': 'x', 'TRD_TRDF': '1,42333818063448', '_SKA': '0,602272727272727', '_SKAS': 'x', '_SKASgs': 'x', 'FBMSZ': '565,906321182265', 'FBMSchaufel': 'x', 'FBMMini': 'x', 'VOLAntGB263': '0,602272727272727', 'VOLGB63gs': 'x'}},
    5: {"wgh": '1,32096400120987',
        "roh": {'_TRDV': '4', '_TSM': '30', 'FBLFL': '1', 'VOLSZ': '500', 'GMSZ': '834,3', 'GBMSZ': '24,99', 'MSchaufel': '7938,1', 'GBM63Schaufel': '641,42', 'GBM263Schaufel': '660,42', 'GBMSchaufel': 'x', 'MMini': 'x', 'VOLMiniSZ': 'x', 'DichteGB': '2,2', 'GBFAnt': '10', 'TRDFgesch': 'x', 'SKAFoto': 'x'},
        "lims": {'FBVSgs': '4105,9465280043', 'FBVb': '4105,9465280043', 'FBVS': '4272,91535062616', 'TRD_TRDF': '1,63465373129843', '_SKA': '16,2728584982361', '_SKAS': '12,8680839492509', '_SKASgs': '16,2728584982361', 'FBMSZ': '798,758685310511', 'FBMSchaufel': '6549,74028861466', 'FBMMini': 'x', 'VOLAntGB263': '6,2728584982361', 'VOLGB63gs': '10'}},
    11: {"wgh": '1,20955548835796',
        "roh": {'_TRDV': '7', '_TSM': '30', 'FBLFL': '1', 'VOLSZ': 'x', 'GMSZ': 'x', 'GBMSZ': 'x', 'MSchaufel': '7317,7', 'GBM63Schaufel': '419,1', 'GBM263Schaufel': '4401,49', 'GBMSchaufel': 'x', 'MMini': 'x', 'VOLMiniSZ': 'x', 'DichteGB': '2,3', 'GBFAnt': '50', 'TRDFgesch': '1,8', 'SKAFoto': 'x'},
        "lims": {'FBVSgs': '1126,81340516432', 'FBVb': '1126,81340516432', 'FBVS': '2135,16823269475', 'TRD_TRDF': '1,8', '_SKA': '79,1330850895496', '_SKAS': '60,4598475426898', '_SKASgs': '79,1330850895496', 'FBMSZ': 'x', 'FBMSchaufel': '2467,26703615178', 'FBMMini': 'x', 'VOLAntGB263': '29,1330850895496', 'VOLGB63gs': '50'}},
    33: {"wgh": '1,46287328490709',
        "roh": {'_TRDV': '5', '_TSM': '50', 'FBLFL': '1', 'VOLSZ': 'x', 'GMSZ': 'x', 'GBMSZ': 'x', 'MSchaufel': '5047,3', 'GBM63Schaufel': '0', 'GBM263Schaufel': '1254,51', 'GBMSchaufel': '392,17', 'MMini': '797,3', 'VOLMiniSZ': '500', 'DichteGB': '2,64', 'GBFAnt': '9', 'TRDFgesch': 'x', 'SKAFoto': 'x'},
        "lims": {'FBVSgs': '5756,3840302028', 'FBVb': '5756,3840302028', 'FBVS': '6325,69673648659', 'TRD_TRDF': '1,50760118553143', '_SKA': '23,6351883316718', '_SKAS': '16,0826245402987', '_SKASgs': '23,6351883316718', 'FBMSZ': 'x', 'FBMSchaufel': '3738,10624241822', 'FBMMini': '785,804673361838', 'VOLAntGB263': '14,6351883316718', 'VOLGB63gs': '9'}},
    92: {"wgh": '0,935083618054344',
        "roh": {'_TRDV': '7', '_TSM': '30', 'FBLFL': '0,66', 'VOLSZ': 'x', 'GMSZ': 'x', 'GBMSZ': 'x', 'MSchaufel': '8075', 'GBM63Schaufel': '0', 'GBM263Schaufel': '5136,8', 'GBMSchaufel': 'x', 'MMini': 'x', 'VOLMiniSZ': 'x', 'DichteGB': '2,64', 'GBFAnt': '0', 'TRDFgesch': 'x', 'SKAFoto': 'x'},
        "lims": {'FBVSgs': '##1093', 'FBVb': '##1093', 'FBVS': '##1093', 'TRD_TRDF': '##1093', '_SKA': '53,1904067563391', '_SKAS': '##1093', '_SKASgs': '53,1904067563391', 'FBMSZ': 'x', 'FBMSchaufel': '2910,97990379476', 'FBMMini': 'x', 'VOLAntGB263': 'X', 'VOLGB63gs': '0'}},
    104: {"wgh": '0,29606237047279',
        "roh": {'_TRDV': '7', '_TSM': '10', 'FBLFL': '0,66', 'VOLSZ': 'x', 'GMSZ': 'x', 'GBMSZ': 'x', 'MSchaufel': '9195', 'GBM63Schaufel': '0', 'GBM263Schaufel': '1063,9', 'GBMSchaufel': 'x', 'MMini': 'x', 'VOLMiniSZ': 'x', 'DichteGB': '2,64', 'GBFAnt': '0', 'TRDFgesch': '1,8', 'SKAFoto': 'x'},
        "lims": {'FBVSgs': '', 'FBVb': '', 'FBVS': '', 'TRD_TRDF': '0', '_SKA': '', '_SKAS': '', '_SKASgs': '', 'FBMSZ': 'x', 'FBMSchaufel': '8107,09793368099', 'FBMMini': 'x', 'VOLAntGB263': 'X', 'VOLGB63gs': '0'}},
    269: {"wgh": '3,40964442279588',
        "roh": {'_TRDV': '4', '_TSM': '50', 'FBLFL': '1', 'VOLSZ': '500', 'GMSZ': '765', 'GBMSZ': '36,72', 'MSchaufel': '5897,2', 'GBM63Schaufel': '0', 'GBMSchaufel': 'x', 'MMini': 'x', 'VOLMiniSZ': 'x', 'DichteGB': '2,2', 'GBFAnt': '0', 'TRDFgesch': 'x', 'SKAFoto': 'x'},
        "lims": {'FBVSgs': '7285,8861210769', 'FBVb': '7285,8861210769', 'FBVS': '##1093', 'TRD_TRDF': '1,45717722421538', '_SKA': '0', '_SKAS': '##1093', '_SKASgs': '0', 'FBMSZ': '704,266999528969', 'FBMSchaufel': '##1093', 'FBMMini': 'x', 'VOLAntGB263': 'X', 'VOLGB63gs': '0'}},
}


FOLGE = trdf.reihenfolge(FORMELN)

# Seit dem 1. September 2026 fuehrt das Labor die Trockenrohdichte
# zweimal. TRDF_Old (PM 1105) rechnet weiter nach der bisherigen Formel;
# TRD_TRDF (PM 1091) nimmt eine gemessene Schaetzung vorweg, wenn eine
# dasteht - unabhaengig von der Variante. Nicht jede Serie fuehrt die
# neue Methode, deshalb steht sie hier als eigener Satz neben dem alten:
# beide Faelle kommen vor, und beide muessen rechnen.
#
# Die Formeln stehen im LIMS und werden von dort geholt. Hier sind sie
# nur der Bauplan - damit sich pruefen laesst, dass die Formelsprache
# sie liest und die Reihenfolge stimmt.
FORMELN_NEU = dict(
    FORMELN,
    TRD_TRDF=('if (isnum($TRDFgesch))\n{TRD_TRDF = TRDFgesch;}\n\n'
              'else if (isnum($_TRDV) != 1)\n{$TRD_TRDF = "x";}\n\n'
              'else if (_TRDV == 1)\n{TRD_TRDF = FBMSZ/VOLSZ;}\n\n'
              'else if (_TRDV == 2 || _TRDV == 6)\n'
              '{TRD_TRDF = FBMSZ/(VOLSZ-(GBMSZ/DichteGB));}\n\n'
              'else if (_TRDV == 4)\n'
              '{TRD_TRDF = ((FBMSZ)/(VOLSZ-(GBMSZ/DichteGB)));}\n\n'
              'else if (_TRDV == 5)\n'
              '{TRD_TRDF = FBMMini*(1-GBMSchaufel/(FBMSchaufel+GBMSchaufel))'
              '/(VOLMiniSZ-FBMMini*GBMSchaufel/(FBMSchaufel+GBMSchaufel)'
              '/DichteGB);}\n\n'
              'else if (_TRDV == 7)\n{TRD_TRDF = TRDFgesch;}'),
    TRDF_Old=(' if (isnum($_TRDV) != 1) {$TRDF_Old="x";}'
              '  else if (_TRDV == 1 ) {TRDF_Old=FBMSZ/VOLSZ;}'
              '  else if (_TRDV == 2 || _TRDV == 6) '
              '{TRDF_Old=FBMSZ/(VOLSZ-(GBMSZ/DichteGB));}'
              '  else if (_TRDV == 4 ) '
              '{TRDF_Old=((FBMSZ)/(VOLSZ-(GBMSZ/DichteGB)));}'
              '  else if (_TRDV == 5 ) '
              '{TRDF_Old=FBMMini*(1-GBMSchaufel/(FBMSchaufel+GBMSchaufel))'
              '/(VOLMiniSZ-FBMMini*GBMSchaufel/(FBMSchaufel+GBMSchaufel)'
              '/DichteGB);}'
              '  else if (_TRDV == 7 ) {TRDF_Old=TRDFgesch;}'))
FOLGE_NEU = trdf.reihenfolge(FORMELN_NEU)


def gerechnet_neu(lnr):
    """Dieselbe Zeile, gerechnet mit dem neuen Satz Formeln."""
    zeile = ZEILEN[lnr]
    roh = {name: trdf.zahl(wert) for name, wert in zeile["roh"].items()}
    return trdf.rechnen(roh, FORMELN_NEU, trdf.zahl(zeile["wgh"]), FOLGE_NEU)


def gerechnet(lnr):
    """Die berechneten Groessen einer echten Zeile - aus den LIMS-Rohwerten."""
    zeile = ZEILEN[lnr]
    roh = {name: trdf.zahl(wert) for name, wert in zeile["roh"].items()}
    return trdf.rechnen(roh, FORMELN, trdf.zahl(zeile["wgh"]), FOLGE)


# --- Was kein Wert ist -----------------------------------------------------

def test_jedes_x_ist_ein_x():
    """Gross, klein - und die Verweise, die das LIMS in MW_ROH hinterlaesst."""
    for wert in ("x", "X", " x ", "##1093", "#", "", "   ", None):
        assert trdf.leer(wert), repr(wert)
    for wert in ("0", "0,000", "-1", "1,8"):
        assert not trdf.leer(wert), repr(wert)


def test_eine_null_ist_ein_wert():
    """Der Unterschied, um den es geht: "hier ist nichts drin" ist nicht
    "hier gibt es nichts"."""
    assert trdf.zahl("0,000") == 0
    assert trdf.zahl("x") is None


def test_komma_und_tausenderpunkt():
    assert trdf.zahl("5136,800") == D("5136.8")
    assert trdf.zahl("1.063,900") == D("1063.9")
    assert trdf.zahl("1063.9") == D("1063.9")


def test_die_probennummer_verliert_leerzeichen_und_bindestrich():
    assert trdf.probenschluessel("2023B - 01944") == "2023B01944"
    assert trdf.probenschluessel("2023B01944") == "2023B01944"


# --- Die Formelsprache -----------------------------------------------------

def test_der_zweig_der_variante_entscheidet():
    formel = FORMELN["TRD_TRDF"]
    werte = {"_TRDV": D(1), "FBMSZ": D(500), "VOLSZ": D(400)}
    assert trdfformel.rechnen(formel, werte, "TRD_TRDF") == D("1.25")


def test_ohne_variante_kommt_x():
    """isnum($_TRDV) != 1 - die Formeln pruefen das selbst ab."""
    assert trdfformel.rechnen(FORMELN["TRD_TRDF"], {}, "TRD_TRDF") == trdf.MARKE


def test_ein_fehlender_wert_pflanzt_sich_fort():
    """Gerechnet wird nicht mit null - sonst rechnete die Pruefung den
    Fehler nach, den sie finden soll."""
    werte = {"_TRDV": D(1), "VOLSZ": D(400)}          # FBMSZ fehlt
    assert trdfformel.rechnen(FORMELN["TRD_TRDF"], werte, "TRD_TRDF") \
        == trdf.MARKE


def test_durch_null_geteilt_gibt_keinen_wert():
    werte = {"_TRDV": D(1), "FBMSZ": D(500), "VOLSZ": D(0)}
    assert trdfformel.rechnen(FORMELN["TRD_TRDF"], werte, "TRD_TRDF") \
        == trdf.MARKE


def test_der_wiederfindungsgrad_kommt_von_aussen():
    """Im LIMS holt ihn die Formel per SQL; hier reicht ihn der Aufrufer
    unter dem Namen herein, der hinter "into :" steht."""
    werte = {"_TRDV": D(2), "GMSZ": D(574), "GBMSZ": D("6.36")}
    ohne = trdfformel.rechnen(FORMELN["FBMSZ"], werte, "FBMSZ")
    mit = trdfformel.rechnen(FORMELN["FBMSZ"], werte, "FBMSZ",
                             {"v_wgh": D("0.306354382844253")})
    assert ohne == D("567.64")                       # v_wgh = 0
    assert mit == D("565.9063211822654544795587449")


def test_die_aufrufe_ins_lims_halten_nichts_auf():
    """ws_get_this_rec_hnd() und Verwandte gibt es hier nicht - sie
    duerfen die Formel trotzdem nicht zum Absturz bringen."""
    assert "FEHLER" not in str(
        trdfformel.rechnen(FORMELN["FBMSZ"], {"_TRDV": D(1), "GMSZ": D(100)},
                           "FBMSZ"))


def test_eine_unbekannte_wendung_faellt_auf():
    """Lieber ein Fehler als ein stillschweigend falsches Ergebnis."""
    assert str(trdfformel.rechnen("A = @@;", {}, "A")).startswith("FEHLER")


def test_die_fotoauswertung_sticht_die_variante():
    """In _SKA gewinnt sie vor jeder Variantenpruefung."""
    werte = {"SKAFoto": D("42.5"), "_TRDV": D(1)}
    assert trdfformel.rechnen(FORMELN["_SKA"], werte, "_SKA") == D("42.5")


# --- Die Reihenfolge -------------------------------------------------------

def test_jede_groesse_kommt_nach_denen_die_sie_braucht():
    """Der Feinbodenvorrat steht auf der Trockenrohdichte, die auf der
    Feinbodenmasse. Falsch sortiert rechnete die erste ins Leere."""
    for stelle, name in enumerate(FOLGE):
        vorher = set(FOLGE[:stelle])
        gebraucht = trdf.abhaengigkeiten(FORMELN[name], set(FORMELN)) - {name}
        assert gebraucht <= vorher, f"{name} braucht {gebraucht - vorher}"


def test_alle_zwoelf_kommen_genau_einmal_vor():
    assert sorted(FOLGE) == sorted(FORMELN)
    assert len(FOLGE) == 12


# --- Gegen die echten Zeilen -----------------------------------------------

def test_eine_gewoehnliche_zeile_stimmt_auf_die_letzte_stelle():
    """LNR 1, Variante 2 - der Normalfall."""
    ergebnis = gerechnet(1)
    for name, gebucht in ZEILEN[1]["lims"].items():
        assert trdf.gleich(ergebnis[name], gebucht), \
            f"{name}: LIMS {gebucht!r}, gerechnet {ergebnis[name]!r}"


def test_die_uebrigen_gewoehnlichen_zeilen_ebenso():
    for lnr in (5, 11, 33):
        ergebnis = gerechnet(lnr)
        for name, gebucht in ZEILEN[lnr]["lims"].items():
            assert trdf.gleich(ergebnis[name], gebucht), \
                f"LNR {lnr}, {name}: LIMS {gebucht!r}, gerechnet {ergebnis[name]!r}"


def test_lnr_104_das_lims_hat_null_gebucht_wo_1_8_stehen_muesste():
    """Variante 7 heisst TRD_TRDF = TRDFgesch, und TRDFgesch ist 1,8.
    Das LIMS hat 0 eingetragen und daraufhin acht Groessen leer gelassen."""
    ergebnis = gerechnet(104)
    assert ergebnis["TRD_TRDF"] == D("1.8")
    assert ZEILEN[104]["lims"]["TRD_TRDF"] == "0"
    assert not trdf.gleich(ergebnis["TRD_TRDF"],
                           ZEILEN[104]["lims"]["TRD_TRDF"])
    # Und alles, was daran haengt, fehlt im LIMS, steht aber bei uns.
    for name in ("_SKA", "_SKAS", "_SKASgs", "FBVb", "FBVS", "FBVSgs"):
        assert trdf.leer(ZEILEN[104]["lims"][name])
        assert isinstance(ergebnis[name], D), name


def test_lnr_92_das_lims_rechnete_mit_einem_wert_den_es_nicht_hat():
    """TRDFgesch fehlt, also gibt es keine Trockenrohdichte - im LIMS
    ebenso wenig. Trotzdem steht dort ein Skelettanteil, der sie
    braucht."""
    ergebnis = gerechnet(92)
    assert trdf.leer(ZEILEN[92]["roh"]["TRDFgesch"])
    # Das LIMS traegt hier "##1093" ein - sein Zeichen dafuer, dass es
    # den Wert nicht bilden konnte.
    assert ZEILEN[92]["lims"]["TRD_TRDF"] == "##1093"
    assert trdf.leer(ZEILEN[92]["lims"]["TRD_TRDF"])
    assert ergebnis["TRD_TRDF"] == trdf.MARKE
    assert ergebnis["_SKASgs"] == trdf.MARKE
    assert not trdf.leer(ZEILEN[92]["lims"]["_SKASgs"])


def test_lnr_269_das_lims_ist_mit_sich_selbst_uneins():
    """GBM263Schaufel fehlt. Fuer die Feinbodenmasse hat das LIMS das als
    fehlend behandelt, fuer den Skelettanteil im selben Durchlauf als
    null - und aus dieser Null folgt ein Feinbodenvorrat."""
    ergebnis = gerechnet(269)
    assert trdf.leer(ZEILEN[269]["roh"].get("GBM263Schaufel"))
    assert trdf.leer(ZEILEN[269]["lims"]["FBMSchaufel"])      # fehlend
    assert ZEILEN[269]["lims"]["_SKASgs"] == "0"             # null
    assert ergebnis["_SKASgs"] == trdf.MARKE
    # Was beide gleich sehen, stimmt trotzdem.
    assert trdf.gleich(ergebnis["FBMSZ"], ZEILEN[269]["lims"]["FBMSZ"])
    assert trdf.gleich(ergebnis["TRD_TRDF"], ZEILEN[269]["lims"]["TRD_TRDF"])


def test_die_drei_faelle_sind_die_einzigen():
    """Ueber alle sieben Zeilen: nur dort geht es auseinander."""
    auffaellig = set()
    for lnr in ZEILEN:
        ergebnis = gerechnet(lnr)
        for name, gebucht in ZEILEN[lnr]["lims"].items():
            if not trdf.gleich(ergebnis[name], gebucht):
                auffaellig.add(lnr)
    assert auffaellig == {92, 104, 269}, auffaellig


# --- Der Wiederfindungsgrad ------------------------------------------------

def test_der_faktor_ist_eins_plus_hundertstel():
    assert trdf.wgh_faktor("3,409644") == D(1) + D("3.409644") / 100


def test_ohne_wiederfindungsgrad_gilt_die_eins():
    for wert in (None, "", "x"):
        assert trdf.wgh_faktor(wert) == D(1)


# --- Der eingefuegte Text --------------------------------------------------

TEXT = "\n".join([
    "Serie\t2026B051",
    "Untersuchungsmethode\tTRDF3.2",
    "\t\t\t\t\tSortier # -->\t1\t2",
    "LNR\tText\tProbenummer\tUM\tMe\tFaktor\tVariante\tTiefenstufenmächtigkeit",
    "\t\t\t\t\t\tohne\tcm",
    "1\t\t2023B - 01944\t1\t1\t1,0000\t2,000\t30,000",
    "2\t\t2023B - 01945\t2\t1\t1,0000\tx\tx",
    "3\t\t2023B - 01946\t1\t1\t1,0000\t4,000\t50,000",
])


def test_der_kopf_wird_gelesen():
    gelesen = trdf.text_lesen(TEXT)
    assert gelesen["serie"] == "2026B051"
    assert gelesen["methode"] == "TRDF3.2"
    assert gelesen["spalten"] == ["Variante", "Tiefenstufenmächtigkeit"]


def test_jede_probe_kommt_mit_ihren_werten():
    zeilen = trdf.text_lesen(TEXT)["zeilen"]
    assert len(zeilen) == 3
    assert zeilen[0]["probe"] == "2023B01944"
    assert zeilen[0]["werte"]["Variante"] == "2,000"
    assert zeilen[1]["werte"]["Variante"] == "x"


def test_wiederholungen_bleiben_draussen():
    """Die wollen wir nicht betrachten."""
    zeilen = trdf.ohne_wiederholungen(trdf.text_lesen(TEXT)["zeilen"])
    assert [z["lnr"] for z in zeilen] == [1, 3]


def test_ein_falscher_text_sagt_was_fehlt():
    for kaputt in ("", "Serie\t2026B051", "eins\nzwei\ndrei\nvier\nfuenf\nsechs"):
        try:
            trdf.text_lesen(kaputt)
        except trdf.Einfuegefehler:
            continue
        raise AssertionError(f"haette auffallen muessen: {kaputt!r}")


# --- Der Vergleich ---------------------------------------------------------

def test_zwei_fehlende_werte_sind_gleich():
    assert trdf.gleich(trdf.MARKE, "x")
    assert trdf.gleich(trdf.MARKE, "##1093")
    assert not trdf.gleich(trdf.MARKE, "1,8")
    assert not trdf.gleich(D("1.8"), "x")


def test_die_letzten_stellen_zaehlen_nicht():
    """Gerechnet wird mit achtundzwanzig Stellen, gespeichert mit
    fuenfzehn - ein Vergleich auf Gleichheit faende ueberall Abweichungen."""
    assert trdf.gleich(D("565.9063211822654544795587449"), "565,906321182265")
    assert not trdf.gleich(D("565.91"), "565,906321182265")


# --- Die zweite Trockenrohdichte -------------------------------------------
#
# Die Formeln holt LabControl aus dem LIMS (PRUEFMETHODEN.FORMEL, in der
# Version, die an der Ergebniszeile haengt). Geprueft wird hier, dass
# die Formelsprache die neuen Faelle liest und dass beide Welten
# nebeneinander rechnen: Serien mit der neuen Methode und Serien ohne.

def test_die_alte_formel_lebt_unter_neuem_namen_weiter():
    """TRDF_Old rechnet, was TRD_TRDF bisher gerechnet hat."""
    for lnr in ZEILEN:
        alt = gerechnet(lnr).get("TRD_TRDF")
        neu = gerechnet_neu(lnr).get("TRDF_Old")
        assert trdf.gleich(alt, neu) or (alt == neu == trdf.MARKE), lnr


def test_eine_geschaetzte_dichte_sticht_jetzt_die_variante():
    """Der ganze Unterschied: steht eine Schaetzung da, gilt sie - auch
    bei einer Variante, die sonst gerechnet haette."""
    roh = {name: trdf.zahl(wert) for name, wert in ZEILEN[1]["roh"].items()}
    roh["TRDFgesch"] = D("1.5")               # Variante 2, sonst gerechnet
    ergebnis = trdf.rechnen(roh, FORMELN_NEU, D(0), FOLGE_NEU)
    assert ergebnis["TRD_TRDF"] == D("1.5")
    assert trdf.gleich(ergebnis["TRDF_Old"], "1,427698639533554")
    # Ohne Schaetzung rechnen beide dasselbe.
    roh.pop("TRDFgesch")
    ohne = trdf.rechnen(roh, FORMELN_NEU, D(0), FOLGE_NEU)
    assert ohne["TRD_TRDF"] == ohne["TRDF_Old"]


def test_die_echten_zeilen_rechnen_auch_mit_dem_neuen_satz():
    """An den Zeilen des Labors aendert sich nichts: dort steht die
    Schaetzung nur, wo die Variante sie ohnehin nimmt."""
    for lnr in (1, 5, 11, 33):
        alt, neu = gerechnet(lnr), gerechnet_neu(lnr)
        for name, wert in ZEILEN[lnr]["lims"].items():
            assert trdf.gleich(neu.get(name), wert), (lnr, name)
        assert trdf.gleich(alt.get("TRD_TRDF"), str(neu.get("TRD_TRDF")))


def test_die_reihenfolge_kennt_beide():
    """Keine der beiden haengt an der anderen - beide an den Rohwerten."""
    assert "TRDF_Old" in FOLGE_NEU and "TRD_TRDF" in FOLGE_NEU
    for name in ("FBMSZ", "FBMMini", "FBMSchaufel"):
        assert FOLGE_NEU.index(name) < FOLGE_NEU.index("TRDF_Old"), name
    # Und was auf der Trockenrohdichte aufbaut, kommt nach ihr.
    for name in ("FBVb", "_SKAS", "_SKASgs"):
        assert FOLGE_NEU.index("TRD_TRDF") < FOLGE_NEU.index(name), name


def test_eine_serie_ohne_die_neue_methode_rechnet_weiter():
    """Sie gibt es beide: mit TRDF_Old und ohne. Was das LIMS nicht
    fuehrt, fehlt hier einfach - und nichts sonst haengt daran."""
    ergebnis = gerechnet(11)
    assert "TRDF_Old" not in ergebnis
    assert "TRDF_Old" not in FOLGE
    assert trdf.gleich(ergebnis["TRD_TRDF"], "1,8")


# --- Die beiden Kuerzelsysteme ---------------------------------------------

# Im LIMS traegt derselbe Rohwert zwei Namen: ein kurzes Kuerzel am
# Rohwertparameter (und damit im Teilprobenanhang) und ein langes an der
# Pruefmethode, mit dem die Formeln rechnen. `trdf.zuordnen` schlaegt die
# Bruecke.

def test_dasselbe_kuerzel_bleibt_es():
    zu = trdf.zuordnen([{"formelkuerzel": "FBLFL", "name": "Faktor"}],
                       [{"formelkuerzel": "FBLFL", "name": "Faktor"}],
                       ["FBLFL"])
    assert zu == {"FBLFL": "FBLFL"}


def test_gleicher_name_findet_das_lange_kuerzel():
    """Der Name entscheidet, nicht die Schreibweise."""
    zu = trdf.zuordnen(
        [{"formelkuerzel": "FS", "name": "Skelettanteil (Fotoauswertung)"}],
        [{"formelkuerzel": "SKAFoto", "name": "SkelettanteilFotoauswertung"}],
        ["SKAFoto"])
    assert zu == {"FS": "SKAFoto"}


def test_das_kurzzeichen_zaehlt_auch():
    zu = trdf.zuordnen([{"formelkuerzel": "I", "name": "", "kuerzel": "VolSZ"}],
                       [{"formelkuerzel": "VOLSZ", "kurzname": "Vol SZ"}],
                       ["VOLSZ"])
    assert zu == {"I": "VOLSZ"}


def test_sonst_hilft_die_liste_des_labors():
    """Namen muessen nicht zusammenpassen - dann bleibt die Liste."""
    zu = trdf.zuordnen(
        [{"formelkuerzel": "D", "name": "Dichte des Grobbodens"},
         {"formelkuerzel": "M", "name": "Maechtigkeit"}],
        [{"formelkuerzel": "DichteGB", "name": "Rohdichte"},
         {"formelkuerzel": "_TSM", "name": "Tiefenstufe"}],
        ["DichteGB", "_TSM"])
    assert zu == {"D": "DichteGB", "M": "_TSM"}


def test_was_niemand_kennt_bleibt_draussen():
    """Lieber melden als raten - sonst schreiben wir in die falsche Zeile."""
    zu = trdf.zuordnen([{"formelkuerzel": "QQ", "name": "Unbekannt"}],
                       [{"formelkuerzel": "VOLSZ", "name": "Volumen"}],
                       ["VOLSZ"])
    assert zu == {}


def test_ohne_liste_der_gesuchten_reichen_die_methoden():
    zu = trdf.zuordnen([{"formelkuerzel": "C", "name": "Variante"}],
                       [{"formelkuerzel": "_TRDV", "name": "TRDF-Variante"}])
    assert zu == {"C": "_TRDV"}


def test_gross_und_kleinschreibung_stoert_die_liste_nicht():
    zu = trdf.zuordnen([{"formelkuerzel": "fs", "name": ""}],
                       [{"formelkuerzel": "SKAFoto", "name": ""}],
                       ["SKAFoto"])
    assert zu == {"fs": "SKAFoto"}


# --------------------------------------------------------------------------


def test_die_zerlegung_wird_je_formel_gemerkt():
    """Dieselbe Formel wird nicht bei jeder Probe neu zerlegt - und die
    gemerkten Marken werden beim Auswerten nicht veraendert."""
    formel = "if (_TRDV == 1) {X=A/B;} else {X=A*B;}"
    trdfformel.zerlegt.cache_clear()
    erst = trdfformel.rechnen(formel, {"_TRDV": D(1), "A": D(6), "B": D(3)},
                              "X")
    dann = trdfformel.rechnen(formel, {"_TRDV": D(2), "A": D(6), "B": D(3)},
                              "X")
    assert (erst, dann) == (D(2), D(18))
    assert trdfformel.zerlegt.cache_info().hits >= 1
    assert trdfformel.zerlegt(formel) == tuple(trdfformel.zerlegen(formel))

def main() -> int:
    pruefungen = [(name, wert) for name, wert in sorted(globals().items())
                  if name.startswith("test_") and callable(wert)]
    fehler = 0
    for name, pruefung in pruefungen:
        try:
            pruefung()
        except AssertionError as ausnahme:
            fehler += 1
            print(f"FEHLGESCHLAGEN {name}: {ausnahme}")
        except Exception as ausnahme:            # noqa: BLE001
            fehler += 1
            print(f"FEHLER {name}: {type(ausnahme).__name__}: {ausnahme}")
        else:
            print(f"  ok  {name}")
    print(f"{len(pruefungen) - fehler} von {len(pruefungen)} "
          f"Pruefungen bestanden")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
