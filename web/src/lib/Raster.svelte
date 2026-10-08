<script>
  // Ein Raster wie in Excel - virtualisiert, mit festen Spalten links.
  //
  // Gezeichnet werden nur die Zeilen, die gerade im Blick sind; bei
  // dreihundert Proben und dreissig Spalten sind das ein paar hundert
  // Zellen statt zehntausend. Aendern laesst sich, was `aenderbar` ist:
  // anklicken und tippen ueberschreibt, F2 oder Doppelklick bearbeitet,
  // Eingabe geht eine Zeile tiefer, Tab nach rechts. Dazu die Kuerzel
  // aus der Tk-Fassung - siehe TASTEN in tasten.js.
  import { tick } from "svelte";
  import { MARKE, alsZahl, zahltext, zerlegen, alsTsv } from "./zellen.js";

  let {
    spalten = [],
    zeilen = [],
    auswahl = [],
    nurBefunde = false,
    ohneX = false,
    zeilenhoehe = 32,
    bearbeitbar = false,
    sehen = null,
    leerText = "Keine Serie geladen.",
    onSetzen = null,
    onFuellen = null,
    onProbe = null,
    onZeile = null,
    onMeldung = null,
    onSpalteVerschieben = null,
    onZeileGewaehlt = null,
  } = $props();

  const PROBENSPALTEN = new Set(["Probe", "Probe-Nr."]);
  const KOPF_ZEILE = 17;

  // ------------------------------------------------------------ Spalten
  let geordnet = $derived([
    ...spalten.filter((s) => s.fest),
    ...spalten.filter((s) => !s.fest),
  ]);
  let links = $derived.by(() => {
    const lage = [];
    let x = 0;
    for (const s of geordnet) {
      lage.push(x);
      x += s.breite;
    }
    return lage;
  });
  let gesamtbreite = $derived(
    geordnet.reduce((summe, s) => summe + s.breite, 0),
  );
  let festbreite = $derived(
    geordnet.filter((s) => s.fest).reduce((summe, s) => summe + s.breite, 0),
  );
  let aenderbare = $derived(
    geordnet.map((s, i) => (s.aenderbar ? i : -1)).filter((i) => i >= 0),
  );
  let kopfhoehe = $derived(
    14 + KOPF_ZEILE * Math.max(1, ...geordnet.map((s) => s.kopf.length)),
  );

  // ------------------------------------------------------------- Zeilen
  // Ausgeblendet wird nur in der Anzeige - gerechnet und geschrieben wird
  // weiter ueber die ganze Serie.
  let sichtbar = $derived(
    nurBefunde || ohneX
      ? zeilen.filter((z) => (!nurBefunde || z.b) && (!ohneX || !z.x))
      : zeilen,
  );
  let gewaehlt = $derived(new Set(auswahl));

  // ----------------------------------------------------- Virtualisieren
  let rumpf = $state(null);
  let oben = $state(0);
  let hoehe = $state(400);
  const VORRAT = 6;
  let erste = $derived(Math.max(0, Math.floor(oben / zeilenhoehe) - VORRAT));
  let letzte = $derived(
    Math.min(
      sichtbar.length,
      Math.ceil((oben + hoehe) / zeilenhoehe) + VORRAT,
    ),
  );
  let fenster = $derived(sichtbar.slice(erste, letzte));

  function gerollt() {
    oben = rumpf.scrollTop;
  }

  // ------------------------------------------------- Zeiger und Bereich
  let zeiger = $state({ r: 0, c: 0 });
  let anker = $state(null);
  let bearbeitung = $state(null); // {r, c, wert, modus}
  let eingabe = $state(null);

  let bereich = $derived.by(() => {
    if (!anker) return null;
    return {
      r1: Math.min(anker.r, zeiger.r),
      r2: Math.max(anker.r, zeiger.r),
      c1: Math.min(anker.c, zeiger.c),
      c2: Math.max(anker.c, zeiger.c),
    };
  });

  function imBereich(r, c) {
    const b = bereich;
    return b && r >= b.r1 && r <= b.r2 && c >= b.c1 && c <= b.c2;
  }

  // Die Zeile, in der gerade gearbeitet wird - die anderen Tabellen
  // gehen mit.
  let gemeldet = null;
  $effect(() => {
    const zeile = sichtbar[zeiger.r];
    if (zeile && zeile.id !== gemeldet && onZeile && bearbeitbar) {
      gemeldet = zeile.id;
      onZeile(zeile.id);
    }
  });

  // Eine andere Tabelle sagt, welche Probe in den Blick soll.
  $effect(() => {
    if (!sehen || !rumpf) return;
    const r = sichtbar.findIndex((z) => z.id === sehen);
    if (r < 0) return;
    const y = r * zeilenhoehe;
    const sicht = rumpf.clientHeight - kopfhoehe;
    if (y < rumpf.scrollTop || y + zeilenhoehe > rumpf.scrollTop + sicht) {
      rumpf.scrollTop = Math.max(0, y - sicht / 2);
    }
  });

  // Bleibt der Zeiger in der Tabelle, wenn sie kuerzer wird.
  $effect(() => {
    if (zeiger.r >= sichtbar.length && sichtbar.length) {
      zeiger = { r: sichtbar.length - 1, c: zeiger.c };
    }
  });

  function zeigen(r, c) {
    if (!rumpf) return;
    const y = r * zeilenhoehe;
    const sicht = rumpf.clientHeight - kopfhoehe;
    if (y < rumpf.scrollTop) rumpf.scrollTop = y;
    else if (y + zeilenhoehe > rumpf.scrollTop + sicht)
      rumpf.scrollTop = y + zeilenhoehe - sicht;
    const s = geordnet[c];
    if (!s || s.fest) return;
    const x = links[c];
    const breite = rumpf.clientWidth - festbreite;
    if (x - festbreite < rumpf.scrollLeft) rumpf.scrollLeft = x - festbreite;
    else if (x + s.breite - festbreite > rumpf.scrollLeft + breite)
      rumpf.scrollLeft = x + s.breite - festbreite - breite;
  }

  function setzeZeiger(r, c, erweitern = false) {
    r = Math.max(0, Math.min(sichtbar.length - 1, r));
    c = Math.max(0, Math.min(geordnet.length - 1, c));
    if (erweitern) {
      if (!anker) anker = { ...zeiger };
    } else {
      anker = null;
    }
    zeiger = { r, c };
    zeigen(r, c);
    // Eine andere Probe gewaehlt - ein offener Block geht mit.
    const id = sichtbar[r]?.id;
    if (id && id !== letzteWahl) {
      letzteWahl = id;
      onZeileGewaehlt?.(id);
    }
  }
  let letzteWahl = null;

  // ------------------------------------------------------------ Werte
  function istLeer(zeile, name) {
    return (zeile.l || []).includes(name);
  }
  function anzeige(zeile, name) {
    const wert = zeile.w[name];
    return wert === null || wert === undefined ? "" : String(wert);
  }
  function eigentlich(zeile, name) {
    // Was in der Zelle *steht*: eine leere Rohwertzelle zeigt x, ist
    // aber leer - und das ist ein Unterschied.
    return istLeer(zeile, name) ? "" : anzeige(zeile, name);
  }

  // ------------------------------------------------------- Bearbeiten
  async function beginne(modus, erstes = null) {
    const s = geordnet[zeiger.c];
    const zeile = sichtbar[zeiger.r];
    if (!bearbeitbar || !s?.aenderbar || !zeile) return;
    anker = null;
    bearbeitung = {
      r: zeiger.r,
      c: zeiger.c,
      id: zeile.id,
      name: s.name,
      wert: erstes ?? eigentlich(zeile, s.name),
      modus,
    };
    await tick();
    if (eingabe) {
      eingabe.focus();
      if (erstes === null) eingabe.select();
      else eingabe.setSelectionRange(erstes.length, erstes.length);
    }
  }

  function abbrechen() {
    bearbeitung = null;
    rumpf?.focus();
  }

  function uebernehmen() {
    const b = bearbeitung;
    if (!b) return false;
    bearbeitung = null;
    const zeile = zeilen.find((z) => z.id === b.id);
    const neu = String(b.wert ?? "").trim();
    if (!zeile || neu === eigentlich(zeile, b.name)) return false;
    vorab(zeile, b.name, neu);
    onSetzen?.([[b.id, b.name, neu]], "tippen");
    return true;
  }

  // Sofort zeigen, was getippt wurde - die Antwort aus Python faerbt
  // danach alles, was sich mitbewegt hat.
  function vorab(zeile, name, wert) {
    zeile.w[name] = wert || MARKE;
    zeile.m = { ...zeile.m, [name]: "geaendert" };
    zeile.l = (zeile.l || []).filter((n) => n !== name);
    if (!wert) zeile.l = [...zeile.l, name];
  }

  function nachbar(r, c, zeilenSchritt, spaltenSchritt) {
    // Wie in der Tk-Fassung: Tab laeuft durch die aenderbaren Spalten
    // und am Zeilenende in die naechste Zeile.
    if (!aenderbare.length) return { r: r + zeilenSchritt, c };
    let stelle = aenderbare.indexOf(c);
    if (stelle < 0) stelle = 0;
    if (spaltenSchritt) {
      stelle += spaltenSchritt;
      if (stelle >= aenderbare.length) {
        stelle = 0;
        r += 1;
      } else if (stelle < 0) {
        stelle = aenderbare.length - 1;
        r -= 1;
      }
    } else {
      r += zeilenSchritt;
    }
    return { r, c: aenderbare[stelle] };
  }

  function weiter(zeilenSchritt, spaltenSchritt) {
    uebernehmen();
    const ziel = nachbar(zeiger.r, zeiger.c, zeilenSchritt, spaltenSchritt);
    if (ziel.r >= 0 && ziel.r < sichtbar.length) setzeZeiger(ziel.r, ziel.c);
    rumpf?.focus();
  }

  function eingabeTaste(e) {
    const b = bearbeitung;
    if (!b) return;
    if (kuerzel(e)) return;
    const pfeile = b.modus === "eingabe";
    switch (e.key) {
      case "Enter":
        e.preventDefault();
        weiter(e.shiftKey ? -1 : 1, 0);
        break;
      case "Tab":
        e.preventDefault();
        weiter(0, e.shiftKey ? -1 : 1);
        break;
      case "Escape":
        e.preventDefault();
        abbrechen();
        break;
      case "ArrowUp":
        e.preventDefault();
        weiter(-1, 0);
        break;
      case "ArrowDown":
        e.preventDefault();
        weiter(1, 0);
        break;
      case "ArrowLeft":
        if (pfeile) {
          e.preventDefault();
          weiter(0, -1);
        }
        break;
      case "ArrowRight":
        if (pfeile) {
          e.preventDefault();
          weiter(0, 1);
        }
        break;
    }
    e.stopPropagation();
  }

  // -------------------------------------------------- Excel-Kuerzel
  function kuerzel(e) {
    if (!(e.ctrlKey || e.metaKey) || e.altKey) return false;
    const taste = e.key.toLowerCase();
    if (!["d", "l", "i", "e"].includes(taste)) return false;
    e.preventDefault();
    e.stopPropagation();
    if (!bearbeitbar) return true;
    if (taste === "d" && !e.shiftKey) vonOben();
    else if (taste === "d") nachUnten("alle");
    else if (taste === "l") nachUnten("leere");
    else if (taste === "i") nachUnten("plus");
    else if (taste === "e") fuellen(e.shiftKey);
    return true;
  }

  function aktuelleZelle() {
    const s = geordnet[zeiger.c];
    const zeile = sichtbar[zeiger.r];
    if (!s || !zeile || !s.aenderbar) return null;
    return { s, zeile };
  }

  async function vonOben() {
    // Strg+D: der Wert der Zelle darueber, wie in Excel.
    uebernehmen();
    const zelle = aktuelleZelle();
    if (!zelle || zeiger.r === 0) return;
    const darueber = sichtbar[zeiger.r - 1];
    const wert = anzeige(darueber, zelle.s.name).trim();
    if (wert === eigentlich(zelle.zeile, zelle.s.name)) return;
    vorab(zelle.zeile, zelle.s.name, wert);
    await onSetzen?.([[zelle.zeile.id, zelle.s.name, wert]], "tippen");
    rumpf?.focus();
  }

  async function nachUnten(art) {
    // Strg+Shift+D bis zum Ende, Strg+L nur in leere Zellen,
    // Strg+I hochzaehlen.
    uebernehmen();
    const zelle = aktuelleZelle();
    if (!zelle) return;
    const name = zelle.s.name;
    const wert = anzeige(zelle.zeile, name).trim();
    const darunter = sichtbar.slice(zeiger.r + 1);
    const gesetzt = [];
    if (art === "plus") {
      const zahl = alsZahl(wert);
      if (zahl === null) {
        onMeldung?.("Hochzaehlen braucht eine Zahl in der Zelle.", "warn");
        return;
      }
      darunter.forEach((z, i) =>
        gesetzt.push([z.id, name, zahltext(zahl + i + 1, wert)]),
      );
    } else {
      for (const z of darunter) {
        if (art === "leere" && !istLeer(z, name)) continue;
        if (anzeige(z, name).trim() === wert && !istLeer(z, name)) continue;
        gesetzt.push([z.id, name, wert]);
      }
    }
    if (!gesetzt.length) {
      onMeldung?.("Darunter ist nichts zu fuellen.", "text");
      return;
    }
    for (const [id, n, w] of gesetzt) {
      const z = zeilen.find((x) => x.id === id);
      if (z) vorab(z, n, w);
    }
    await onSetzen?.(gesetzt, "nach_unten");
    rumpf?.focus();
  }

  async function fuellen(spaltenweise) {
    // Strg+E die Zeile, Strg+Shift+E die Spalte: leere Zellen bekommen x.
    uebernehmen();
    const zelle = aktuelleZelle();
    const zeile = sichtbar[zeiger.r];
    if (!zeile) return;
    if (spaltenweise) {
      if (!zelle) return;
      await onFuellen?.(null, zelle.s.name);
    } else {
      await onFuellen?.(zeile.id, null);
    }
    rumpf?.focus();
  }

  // ------------------------------------------------ Kopieren, Einfuegen
  function auswahlText() {
    const b = bereich ?? {
      r1: zeiger.r,
      r2: zeiger.r,
      c1: zeiger.c,
      c2: zeiger.c,
    };
    const tafel = [];
    for (let r = b.r1; r <= b.r2; r++) {
      const zeile = sichtbar[r];
      if (!zeile) continue;
      const werte = [];
      for (let c = b.c1; c <= b.c2; c++)
        werte.push(anzeige(zeile, geordnet[c].name));
      tafel.push(werte);
    }
    return alsTsv(tafel);
  }

  function kopiert(e) {
    if (bearbeitung) return;
    e.clipboardData.setData("text/plain", auswahlText());
    e.preventDefault();
    onMeldung?.("Kopiert.", "text");
  }

  function kopieren() {
    // Strg+C ohne markierten Text: ueber ein unsichtbares Feld, das geht
    // in jeder Umgebung - auch dort, wo die Zwischenablage-API fehlt.
    const feld = document.createElement("textarea");
    feld.value = auswahlText();
    feld.style.cssText = "position:fixed;opacity:0;left:-9999px";
    document.body.appendChild(feld);
    feld.select();
    document.execCommand("copy");
    feld.remove();
    rumpf?.focus();
    onMeldung?.("Kopiert.", "text");
  }

  async function eingefuegt(e) {
    if (!bearbeitbar) return;
    const text = e.clipboardData?.getData("text/plain") ?? "";
    const block = zerlegen(text);
    const einzeln = block.length <= 1 && (block[0]?.length ?? 0) <= 1;
    if (bearbeitung && einzeln) return; // gewoehnlich ins Feld
    e.preventDefault();
    if (bearbeitung) {
      bearbeitung = null;
    }
    const zelle = aktuelleZelle();
    if (!zelle) return;
    if (einzeln) {
      const wert = (block[0]?.[0] ?? "").trim();
      if (!wert) return;
      vorab(zelle.zeile, zelle.s.name, wert);
      await onSetzen?.([[zelle.zeile.id, zelle.s.name, wert]], "tippen");
      rumpf?.focus();
      return;
    }
    // Ein Block aus Excel: ab der Zelle nach unten und nach rechts,
    // nur in aenderbare Spalten; leere Felder ueberspringen.
    const spaltenListe = aenderbare.map((c) => geordnet[c].name);
    const links0 = spaltenListe.indexOf(zelle.s.name);
    const gesetzt = [];
    let uebrig = 0;
    block.forEach((werte, unten) => {
      werte.forEach((roh, rechts) => {
        const wert = String(roh).trim();
        const zeile = sichtbar[zeiger.r + unten];
        const name = spaltenListe[links0 + rechts];
        if (!zeile || !name) {
          if (wert) uebrig += 1;
          return;
        }
        if (!wert || anzeige(zeile, name) === wert) return;
        gesetzt.push([zeile.id, name, wert]);
      });
    });
    for (const [id, n, w] of gesetzt) {
      const z = zeilen.find((x) => x.id === id);
      if (z) vorab(z, n, w);
    }
    if (gesetzt.length) await onSetzen?.(gesetzt, "block");
    if (uebrig)
      onMeldung?.(
        `${uebrig} Werte passten nicht mehr in die Tabelle und wurden nicht uebernommen.`,
        "warn",
      );
    rumpf?.focus();
  }

  async function loeschen() {
    // Entf leert die gewaehlten Zellen - wie in Excel.
    const b = bereich ?? {
      r1: zeiger.r,
      r2: zeiger.r,
      c1: zeiger.c,
      c2: zeiger.c,
    };
    const gesetzt = [];
    for (let r = b.r1; r <= b.r2; r++) {
      const zeile = sichtbar[r];
      for (let c = b.c1; c <= b.c2; c++) {
        const s = geordnet[c];
        if (zeile && s?.aenderbar && !istLeer(zeile, s.name))
          gesetzt.push([zeile.id, s.name, ""]);
      }
    }
    if (!gesetzt.length) return;
    for (const [id, n] of gesetzt) {
      const z = zeilen.find((x) => x.id === id);
      if (z) vorab(z, n, "");
    }
    await onSetzen?.(gesetzt, gesetzt.length > 1 ? "block" : "tippen");
  }

  // ------------------------------------------------------ Tastatur
  function taste(e) {
    if (bearbeitung) return;
    if (kuerzel(e)) return;
    const { r, c } = zeiger;
    const seite = Math.max(1, Math.floor((hoehe - kopfhoehe) / zeilenhoehe) - 1);
    switch (e.key) {
      case "ArrowUp":
        e.preventDefault();
        setzeZeiger(e.ctrlKey ? 0 : r - 1, c, e.shiftKey);
        return;
      case "ArrowDown":
        e.preventDefault();
        setzeZeiger(e.ctrlKey ? sichtbar.length - 1 : r + 1, c, e.shiftKey);
        return;
      case "ArrowLeft":
        e.preventDefault();
        setzeZeiger(r, e.ctrlKey ? 0 : c - 1, e.shiftKey);
        return;
      case "ArrowRight":
        e.preventDefault();
        setzeZeiger(r, e.ctrlKey ? geordnet.length - 1 : c + 1, e.shiftKey);
        return;
      case "PageDown":
        e.preventDefault();
        setzeZeiger(r + seite, c, e.shiftKey);
        return;
      case "PageUp":
        e.preventDefault();
        setzeZeiger(r - seite, c, e.shiftKey);
        return;
      case "Home":
        e.preventDefault();
        setzeZeiger(e.ctrlKey ? 0 : r, 0, e.shiftKey);
        return;
      case "End":
        e.preventDefault();
        setzeZeiger(e.ctrlKey ? sichtbar.length - 1 : r, geordnet.length - 1, e.shiftKey);
        return;
      case "Tab": {
        e.preventDefault();
        const ziel = nachbar(r, c, 0, e.shiftKey ? -1 : 1);
        if (ziel.r >= 0 && ziel.r < sichtbar.length) setzeZeiger(ziel.r, ziel.c);
        return;
      }
      case "Enter":
        e.preventDefault();
        setzeZeiger(r + (e.shiftKey ? -1 : 1), c);
        return;
      case "F2":
        e.preventDefault();
        beginne("bearbeiten");
        return;
      case "Delete":
      case "Backspace":
        if (bearbeitbar) {
          e.preventDefault();
          loeschen();
        }
        return;
      case "Escape":
        anker = null;
        return;
    }
    if (e.key.toLowerCase() === "c" && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
      e.preventDefault();
      kopieren();
      return;
    }
    if (e.key === "a" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      anker = { r: 0, c: 0 };
      zeiger = { r: sichtbar.length - 1, c: geordnet.length - 1 };
      return;
    }
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (geordnet[c]?.aenderbar && bearbeitbar) {
        e.preventDefault();
        beginne("eingabe", e.key);
      }
    }
  }

  // ----------------------------------------------------------- Maus
  let ziehen = false;
  function gedrueckt(e, r, c) {
    if (e.button !== 0) return;
    if (bearbeitung && (bearbeitung.r !== r || bearbeitung.c !== c))
      uebernehmen();
    if (bearbeitung) return;
    e.preventDefault();
    rumpf?.focus();
    setzeZeiger(r, c, e.shiftKey);
    ziehen = true;
    const s = geordnet[c];
    if (PROBENSPALTEN.has(s?.name) && !e.shiftKey) onProbe?.(sichtbar[r].id);
  }
  function ueberfahren(r, c) {
    if (!ziehen) return;
    if (!anker) anker = { ...zeiger };
    zeiger = { r, c };
  }
  function losgelassen() {
    ziehen = false;
  }
  function doppelt(r, c) {
    setzeZeiger(r, c);
    beginne("bearbeiten");
  }

  // --------------------------------------------------- Kopfhinweis
  let hinweis = $state(null);
  let hinweisZeit = null;
  function kopfRein(e, s) {
    clearTimeout(hinweisZeit);
    if (!s.hinweis) return;
    const rahmen = e.currentTarget.getBoundingClientRect();
    hinweisZeit = setTimeout(() => {
      hinweis = {
        text: s.hinweis,
        x: Math.min(rahmen.left, window.innerWidth - 380),
        y: rahmen.bottom + 6,
      };
    }, 450);
  }
  function kopfRaus() {
    clearTimeout(hinweisZeit);
    hinweis = null;
  }

  // ------------------------------------------- Spalten am Kopf ziehen
  let gezogen = $state(null);
  let ueberKopf = $state(null);
  function kopfZiehen(e, s) {
    if (!onSpalteVerschieben || s.fest) {
      e.preventDefault();
      return;
    }
    kopfRaus();
    gezogen = s.name;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", s.name);
  }
  function kopfUeber(e, s) {
    if (!gezogen || s.fest || s.name === gezogen) return;
    e.preventDefault();
    ueberKopf = s.name;
  }
  function kopfAbgelegt(e, s) {
    e.preventDefault();
    const von = gezogen;
    gezogen = null;
    ueberKopf = null;
    if (von && von !== s.name && !s.fest) onSpalteVerschieben(von, s.name);
  }

  // Von aussen: die Tabelle bekommt den Fokus.
  export function fokus() {
    rumpf?.focus();
  }
</script>

<svelte:window onmouseup={losgelassen} />

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="rumpf"
  bind:this={rumpf}
  bind:clientHeight={hoehe}
  onscroll={gerollt}
  onkeydown={taste}
  oncopy={kopiert}
  onpaste={eingefuegt}
  tabindex="0"
  role="grid"
  style:--zh="{zeilenhoehe}px"
>
  {#if !geordnet.length}
    <div class="leer">{leerText}</div>
  {:else}
    <div
      class="innen"
      style:width="{gesamtbreite}px"
      style:height="{kopfhoehe + sichtbar.length * zeilenhoehe}px"
    >
      <div class="kopf" style:height="{kopfhoehe}px" style:width="{gesamtbreite}px">
        {#each geordnet as s, c (s.name)}
          <div
            class="kz"
            class:fest={s.fest}
            class:letztfest={s.fest && !geordnet[c + 1]?.fest}
            class:aenderbar={s.aenderbar}
            class:aktiv={c === zeiger.c}
            style:width="{s.breite}px"
            style:left={s.fest ? `${links[c]}px` : null}
            class:ziehbar={!!onSpalteVerschieben && !s.fest}
            class:ziel={ueberKopf === s.name}
            class:gezogen={gezogen === s.name}
            draggable={!!onSpalteVerschieben && !s.fest}
            ondragstart={(e) => kopfZiehen(e, s)}
            ondragover={(e) => kopfUeber(e, s)}
            ondragleave={() => ueberKopf === s.name && (ueberKopf = null)}
            ondrop={(e) => kopfAbgelegt(e, s)}
            ondragend={() => { gezogen = null; ueberKopf = null; }}
            onmouseenter={(e) => kopfRein(e, s)}
            onmouseleave={kopfRaus}
            role="columnheader"
            tabindex="-1"
          >
            {#each s.kopf as teil, i}
              <span class:unter={i > 0}>{teil}</span>
            {/each}
          </div>
        {/each}
      </div>

      <div class="fenster" style:top="{kopfhoehe + erste * zeilenhoehe}px">
        {#each fenster as zeile, i (zeile.id)}
          {@const r = erste + i}
          <div
            class="zeile"
            class:gewaehlt={gewaehlt.has(zeile.id)}
            class:zeigerzeile={r === zeiger.r}
            style:width="{gesamtbreite}px"
            role="row"
          >
            {#each geordnet as s, c (s.name)}
              {@const marke = zeile.m?.[s.name]}
              {@const offen = bearbeitung && bearbeitung.r === r && bearbeitung.c === c}
              <div
                class="z {marke ?? ''}"
                class:fest={s.fest}
                class:letztfest={s.fest && !geordnet[c + 1]?.fest}
                class:zahl={!PROBENSPALTEN.has(s.name) && s.name !== "Bewertung" && s.name !== "Bewertung Rohwerte"}
                class:probe={PROBENSPALTEN.has(s.name)}
                class:gruppe={s.gruppe && !marke}
                class:aenderbar={s.aenderbar && bearbeitbar}
                class:leerwert={s.aenderbar && istLeer(zeile, s.name)}
                class:zeiger={r === zeiger.r && c === zeiger.c}
                class:bereich={imBereich(r, c)}
                style:width="{s.breite}px"
                style:left={s.fest ? `${links[c]}px` : null}
                title={zeile.t?.[s.name] ?? (s.breite < 200 ? null : anzeige(zeile, s.name)) ?? null}
                onmousedown={(e) => gedrueckt(e, r, c)}
                onmouseenter={() => ueberfahren(r, c)}
                ondblclick={() => doppelt(r, c)}
                role="gridcell"
                tabindex="-1"
              >
                {#if offen}
                  <input
                    class="eingabe"
                    bind:this={eingabe}
                    bind:value={bearbeitung.wert}
                    onkeydown={eingabeTaste}
                    onblur={() => uebernehmen()}
                    spellcheck="false"
                    autocomplete="off"
                  />
                {:else}
                  {anzeige(zeile, s.name)}
                {/if}
              </div>
            {/each}
          </div>
        {/each}
      </div>
    </div>
    {#if !sichtbar.length}
      <div class="leer unten">Keine Zeilen zu zeigen.</div>
    {/if}
  {/if}
</div>

{#if hinweis}
  <div class="kopfhinweis" style:left="{hinweis.x}px" style:top="{hinweis.y}px">
    {hinweis.text}
  </div>
{/if}

<style>
  .rumpf {
    position: relative;
    overflow: auto;
    height: 100%;
    background: var(--flaeche);
    outline: none;
    font-variant-numeric: tabular-nums;
    user-select: none;
  }
  .rumpf:focus-visible {
    box-shadow: inset 0 0 0 2px var(--akzent-hell);
  }
  .innen {
    position: relative;
  }
  .leer {
    padding: 48px 24px;
    color: var(--text-3);
    text-align: center;
  }
  .leer.unten {
    position: absolute;
    top: 80px;
    left: 0;
    right: 0;
  }

  /* ------------------------------------------------------- Kopf */
  .kopf {
    position: sticky;
    top: 0;
    z-index: 3;
    display: flex;
    background: var(--flaeche-2);
    border-bottom: 1px solid var(--rand-stark);
  }
  .kz {
    flex: none;
    padding: 7px 8px 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
    border-right: 1px solid var(--rand);
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    overflow: hidden;
    white-space: nowrap;
    background: var(--flaeche-2);
    cursor: default;
  }
  .kz span {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .kz .unter {
    font-weight: 400;
    color: var(--text-2);
  }
  .kz.aenderbar {
    background: #f1f5ff;
  }
  .kz.aktiv {
    box-shadow: inset 0 -2px 0 var(--akzent);
  }
  .kz.fest {
    position: sticky;
    z-index: 4;
  }
  .kz.ziehbar {
    cursor: grab;
  }
  .kz.gezogen {
    opacity: 0.45;
  }
  .kz.ziel {
    box-shadow: inset 3px 0 0 var(--akzent);
    background: var(--akzent-zart);
  }

  /* ------------------------------------------------------ Zeilen */
  .fenster {
    position: absolute;
    left: 0;
  }
  .zeile {
    display: flex;
    height: var(--zh);
  }
  .z {
    flex: none;
    height: var(--zh);
    line-height: calc(var(--zh) - 1px);
    padding: 0 8px;
    border-right: 1px solid var(--rand);
    border-bottom: 1px solid var(--rand);
    background: var(--flaeche);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    position: relative;
    cursor: cell;
  }
  .z.zahl {
    text-align: right;
  }
  .z.fest {
    position: sticky;
    z-index: 2;
  }
  .z.letztfest,
  .kz.letztfest {
    border-right: 1px solid var(--rand-stark);
    box-shadow: 4px 0 6px -4px rgb(15 23 42 / 12%);
  }
  .z.probe {
    color: var(--akzent);
    font-weight: 500;
    cursor: pointer;
  }
  .z.probe:hover {
    text-decoration: underline;
  }
  .z.gruppe {
    background: var(--gruppe);
  }
  .z.leerwert {
    color: var(--text-3);
  }
  .zeile.gewaehlt .z {
    background: var(--auswahl);
  }
  .zeile:hover .z:not(.geaendert):not(.abweichung) {
    background-image: linear-gradient(rgb(37 99 235 / 4%), rgb(37 99 235 / 4%));
  }

  /* Marken - dieselben Farben wie in der Tk-Fassung. */
  .z.geaendert {
    color: var(--rot);
    font-weight: 600;
    background: var(--rot-zart);
  }
  .zeile.gewaehlt .z.geaendert {
    background: #fde8e8;
  }
  .z.abweichung {
    background: var(--amber-hell);
    color: #92400e;
  }
  .z.ersatz {
    color: var(--violett);
    font-style: italic;
  }

  .z.bereich {
    background: #dbe7ff !important;
  }
  .z.zeiger {
    box-shadow: inset 0 0 0 2px var(--akzent);
    z-index: 1;
  }
  .z.fest.zeiger {
    z-index: 3;
  }
  /* Ohne Fokus nur angedeutet - sonst stehen in zwei Tabellen zwei
     gleich laute Zeiger. */
  .rumpf:not(:focus-within) .z.zeiger {
    box-shadow: inset 0 0 0 1px #93c5fd;
  }

  .eingabe {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: none;
    padding: 0 7px;
    font: inherit;
    font-variant-numeric: tabular-nums;
    text-align: right;
    color: var(--text);
    background: #fff;
    outline: 2px solid var(--akzent);
    outline-offset: -2px;
    box-shadow: 0 4px 14px rgb(37 99 235 / 18%);
  }

  .kopfhinweis {
    position: fixed;
    z-index: 50;
    max-width: 380px;
    padding: 8px 10px;
    border-radius: 8px;
    background: #0f172a;
    color: #f8fafc;
    font-size: 12px;
    line-height: 1.45;
    white-space: pre-wrap;
    box-shadow: var(--schatten-hoch);
    pointer-events: none;
  }
</style>
