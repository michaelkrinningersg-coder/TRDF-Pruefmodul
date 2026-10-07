<script>
  // TRDF-Pruefmodul - die Seite.
  //
  // Erst anmelden, dann Serie -> Abfragen -> Untersuchungsmethode. Danach
  // vier Reiter: Rohwerte (aenderbar, die berechneten Groessen lassen
  // sich darueber aufklappen), Ergebnisse, Pruefung und Exportbericht.
  // Gerechnet wird in Python; die Seite zeigt und nimmt Eingaben an.
  import { onMount } from "svelte";
  import { rufe } from "./lib/api.js";
  import Anmeldung from "./lib/Anmeldung.svelte";
  import Raster from "./lib/Raster.svelte";
  import Info from "./lib/Info.svelte";
  import Block from "./lib/Block.svelte";
  import Bild from "./lib/Bild.svelte";
  import Vorschau from "./lib/Vorschau.svelte";
  import Einfuegen from "./lib/Einfuegen.svelte";
  import Legende from "./lib/Legende.svelte";
  import Meldung from "./lib/Meldung.svelte";
  import Dialog from "./lib/Dialog.svelte";
  import { ERKLAERUNG, TASTEN, VARIANTE } from "./lib/tasten.js";

  // ------------------------------------------------------------ Zustand
  let start = $state(null);
  let angemeldet = $state(false);
  let benutzer = $state("");
  let startfehler = $state("");

  let serien = $state([]);
  let serie = $state("");
  let abgefragt = $state("");
  let methoden = $state([]);
  let methode = $state("");

  let zustand = $state(null); // was Python ueber die Serie sagt
  let stand = $state({ text: "", art: "text" });
  let meldungZeile = $state({ roh: null, ergebnis: null, pruefung: null, bericht: null });
  let reiter = $state("roh");
  let berechneteOffen = $state(false);
  let teilung = $state(0.38);
  let nurRohBefunde = $state(false);
  let nurBefunde = $state(false);
  let dichte = $state(leseDichte());
  let arbeitszeile = $state(null);
  let bloecke = $state([]);
  let oberstes = $state(30);

  let laeuft = $state(0);
  let einfuegen = $state(null);
  let vorschau = $state(null);
  let bild = $state(null);
  let legende = $state(null);
  let meldung = $state(null);
  let sicherungen = $state(null);

  const HOEHEN = { kompakt: 28, normal: 34, gross: 42 };

  function leseDichte() {
    try {
      return localStorage.getItem("trdf-dichte") || "normal";
    } catch {
      return "normal";
    }
  }
  $effect(() => {
    try {
      localStorage.setItem("trdf-dichte", dichte);
    } catch {
      /* ohne Speicher eben nicht */
    }
  });

  let tafeln = $derived(zustand?.tafeln ?? null);
  let auswahl = $derived([
    ...(arbeitszeile ? [arbeitszeile] : []),
    ...bloecke.map((b) => b.probe),
  ]);
  let offeneBloecke = $derived(bloecke.map((b) => b.probe));
  let befunde = $derived({
    roh: tafeln?.roh.zeilen.filter((z) => z.b).length ?? 0,
    ergebnis: tafeln?.ergebnis.zeilen.filter((z) => z.b).length ?? 0,
    pruefung: tafeln?.pruefung.zeilen.filter((z) => z.b).length ?? 0,
  });

  // ------------------------------------------------------------- Rufen
  async function mit(arbeit) {
    laeuft += 1;
    try {
      return await arbeit();
    } catch (fehler) {
      stand = { text: String(fehler?.message ?? fehler), art: "fehler" };
      return null;
    } finally {
      laeuft -= 1;
    }
  }

  function fehlerFrei(antwort) {
    if (antwort?.fehler) {
      stand = { text: antwort.fehler, art: "fehler" };
      return false;
    }
    return true;
  }

  function uebernehmen(voll) {
    if (!voll || !fehlerFrei(voll)) return;
    if (voll.tafeln !== undefined) {
      zustand = voll;
      meldungZeile = { roh: null, ergebnis: null, pruefung: null, bericht: null };
      // Offene Bloecke zeigen den neuen Stand.
      for (const b of bloecke) auffrischen(b.probe);
    }
    if (voll.stand) stand = voll.stand;
    if (voll.meldung) meldung = voll.meldung;
    if (voll.reiter) reiter = voll.reiter;
  }

  onMount(async () => {
    const antwort = await mit(() => rufe("start"));
    if (!antwort || antwort.fehler) {
      startfehler = antwort?.fehler ?? "Die Verbindung zu Python fehlt.";
      return;
    }
    start = antwort;
    serie = antwort.serie ?? "";
    berechneteOffen = antwort.berechnete === "an";
    if (antwort.angemeldet) {
      angemeldet = true;
      uebernehmen(await rufe("zustand"));
      serienLaden();
    }
  });

  async function anmelden(name, passwort, datenbank) {
    const antwort = await rufe("anmelden", name, passwort, datenbank);
    if (antwort.ok) {
      angemeldet = true;
      benutzer = antwort.benutzer;
      serienLaden();
    }
    return antwort;
  }

  async function serienLaden() {
    const antwort = await mit(() => rufe("serien"));
    if (antwort && fehlerFrei(antwort)) {
      serien = antwort.serien;
      stand = antwort.stand;
    }
  }

  // ---------------------------------------------------- Serie, Methode
  async function abfragen() {
    const name = serie.trim();
    if (!name) {
      stand = { text: "Erst eine Serie wählen.", art: "warn" };
      return;
    }
    methoden = [];
    methode = "";
    abgefragt = "";
    stand = { text: `Die Untersuchungsmethoden der Serie ${name} werden abgefragt …`, art: "text" };
    const antwort = await mit(() => rufe("abfragen", name));
    if (!antwort || !fehlerFrei(antwort)) return;
    if (serie.trim() !== name) return; // inzwischen eine andere Serie
    methoden = antwort.methoden;
    if (antwort.stand) stand = antwort.stand;
    if (!methoden.length) return;
    abgefragt = name;
    if (methoden.length === 1) {
      methode = String(methoden[0].um_id);
      await laden();
    }
  }

  function serieGetippt() {
    if (abgefragt && serie.trim() !== abgefragt) {
      methoden = [];
      methode = "";
      abgefragt = "";
    }
  }

  async function laden() {
    if (!methode) return;
    const m = methoden.find((x) => String(x.um_id) === methode);
    stand = { text: `Serie ${abgefragt} – ${m?.kuerzel ?? ""} wird geholt …`, art: "text" };
    const antwort = await mit(() => rufe("laden", abgefragt, m.um_id));
    if (antwort && fehlerFrei(antwort)) {
      bloecke = [];
      arbeitszeile = null;
      uebernehmen(antwort);
    }
  }

  // ----------------------------------------------------------- Aendern
  function zeilenErsetzen(tafel, neue) {
    if (!tafel || !neue?.length) return;
    const stelle = new Map(tafel.zeilen.map((z, i) => [z.id, i]));
    for (const z of neue) {
      const i = stelle.get(z.id);
      if (i !== undefined) tafel.zeilen[i] = z;
    }
  }

  function delta(antwort, wo = "roh") {
    if (!antwort || !fehlerFrei(antwort)) return;
    if (!tafeln) return;
    zeilenErsetzen(tafeln.roh, antwort.roh);
    zeilenErsetzen(tafeln.ergebnis, antwort.ergebnis);
    zeilenErsetzen(tafeln.pruefung, antwort.pruefung);
    if (antwort.staende) {
      tafeln.roh.stand = antwort.staende.roh;
      tafeln.ergebnis.stand = antwort.staende.ergebnis;
      tafeln.pruefung.stand = antwort.staende.pruefung;
    }
    if (antwort.aenderungen !== undefined) zustand.aenderungen = antwort.aenderungen;
    for (const [probe, daten] of Object.entries(antwort.bloecke ?? {})) {
      const b = bloecke.find((x) => x.probe === probe);
      if (b) b.daten = daten;
    }
    meldungZeile[wo] = antwort.meldung ?? null;
  }

  async function setzen(zellen, art) {
    const antwort = await rufe("setzen", zellen, art, offeneBloecke);
    delta(antwort);
  }

  async function fuellen(probe, spalte) {
    const antwort = await rufe("leere_fuellen", probe, spalte, offeneBloecke);
    delta(antwort);
  }

  function rasterMeldung(text, art) {
    meldungZeile.roh = { text, art };
  }

  // ------------------------------------------------------------- Block
  async function blockOeffnen(probe) {
    const da = bloecke.find((b) => b.probe === probe);
    if (da) {
      vorne(da);
      auffrischen(probe);
      return;
    }
    const daten = await rufe("block", probe);
    if (!fehlerFrei(daten)) return;
    const versatz = (bloecke.length % 5) * 28;
    bloecke = [
      ...bloecke,
      {
        probe,
        daten,
        x: Math.max(20, window.innerWidth - 700 - versatz),
        y: 150 + versatz,
        z: ++oberstes,
      },
    ];
  }

  async function auffrischen(probe) {
    const b = bloecke.find((x) => x.probe === probe);
    if (!b) return;
    const daten = await rufe("block", probe);
    if (!daten.fehler) b.daten = daten;
  }

  async function blockWechseln(b, richtung) {
    const antwort = await rufe("nachbar", b.probe, richtung);
    if (!antwort?.probe) return;
    const schon = bloecke.find((x) => x.probe === antwort.probe);
    if (schon) {
      vorne(schon);
      return;
    }
    const daten = await rufe("block", antwort.probe);
    if (daten.fehler) return;
    b.probe = antwort.probe;
    b.daten = daten;
  }

  function vorne(b) {
    b.z = ++oberstes;
  }

  // ------------------------------------------------------ UM einfuegen
  async function einfuegenOeffnen() {
    const antwort = await rufe("um_text");
    einfuegen = { text: antwort.text ?? "", stand: null };
  }
  async function umUebernehmen(text) {
    const antwort = await mit(() => rufe("um_einfuegen", text));
    if (!antwort || !fehlerFrei(antwort)) return;
    if (!antwort.ok) {
      einfuegen.stand = antwort.stand;
      return;
    }
    uebernehmen(antwort);
    einfuegen = null;
  }
  async function umLeeren() {
    uebernehmen(await mit(() => rufe("um_leeren")));
    if (einfuegen) einfuegen.stand = null;
  }

  // ---------------------------------------------------------- Export
  async function exportVorschau() {
    const antwort = await mit(() => rufe("export_vorschau"));
    if (!antwort || !fehlerFrei(antwort)) return;
    if (antwort.vorschau) vorschau = antwort.vorschau;
    else if (antwort.stand) stand = antwort.stand;
  }
  async function anhangVorschau() {
    const antwort = await mit(() => rufe("anhang_vorschau"));
    if (!antwort || !fehlerFrei(antwort)) return;
    if (antwort.vorschau) vorschau = antwort.vorschau;
    else if (antwort.stand) meldungZeile.roh = antwort.stand;
  }
  async function backupWaehlen() {
    const antwort = await mit(() => rufe("backup_waehlen"));
    if (!antwort || !fehlerFrei(antwort)) return;
    if (antwort.abgebrochen && location.protocol.startsWith("http")) {
      // Im Browser gibt es keinen Dateidialog - die Liste aus dem Ordner.
      sicherungen = await rufe("sicherungen");
      return;
    }
    if (antwort.vorschau) vorschau = antwort.vorschau;
    else if (antwort.stand) stand = antwort.stand;
  }
  async function backupLesen(pfad) {
    sicherungen = null;
    const antwort = await mit(() => rufe("backup_lesen", pfad));
    if (antwort?.vorschau) vorschau = antwort.vorschau;
    else if (antwort?.stand) stand = antwort.stand;
  }
  async function vorschauJa() {
    const antwort = await rufe("vorschau_ausfuehren");
    vorschau = null;
    if (antwort?.fehler) {
      meldung = { titel: "Es wurde nichts geschrieben", art: "fehler", text: antwort.fehler };
      stand = { text: antwort.fehler, art: "fehler" };
      return;
    }
    uebernehmen(antwort);
  }
  function vorschauZu() {
    vorschau = null;
    rufe("vorschau_abbrechen");
  }

  // ------------------------------------------------------ Blaetter, Bild
  async function csv(blatt, wo) {
    const antwort = await mit(() => rufe("csv", blatt));
    if (antwort && fehlerFrei(antwort)) meldungZeile[wo] = antwort.stand;
  }
  async function bildZeigen() {
    const antwort = await mit(() => rufe("bild"));
    if (antwort && fehlerFrei(antwort)) bild = antwort;
  }
  async function legendeZeigen(blatt) {
    const antwort = await mit(() => rufe("legende", blatt));
    if (antwort && fehlerFrei(antwort)) legende = antwort;
  }
  async function legendeSpeichern(texte, ordnung) {
    const antwort = await rufe("legende_speichern", legende.blatt, texte, ordnung);
    if (antwort.fehler) return { text: antwort.fehler, art: "fehler" };
    if (antwort.tafeln !== undefined) {
      const behalten = stand;
      uebernehmen(antwort);
      stand = behalten;
    }
    return antwort.stand;
  }

  async function spalteVerschieben(blatt, wo, von, nach) {
    const antwort = await rufe("spalte_verschieben", blatt, von, nach);
    if (!fehlerFrei(antwort)) return;
    if (antwort.tafeln && zustand) zustand.tafeln = antwort.tafeln;
    if (antwort.stand) meldungZeile[wo] = antwort.stand;
  }

  function berechneteUmschalten() {
    berechneteOffen = !berechneteOffen;
    rufe("einstellung", "trdf_berechnete", berechneteOffen ? "an" : "aus");
  }

  // ---------------------------------------------------------- Teilung
  let teilRahmen = $state(null);
  let teilZug = false;
  function teilGreifen(e) {
    teilZug = true;
    e.preventDefault();
  }
  function teilBewegen(e) {
    if (!teilZug || !teilRahmen) return;
    const r = teilRahmen.getBoundingClientRect();
    teilung = Math.min(0.8, Math.max(0.12, (e.clientY - r.top) / r.height));
  }

  const REITER = [
    ["roh", "Rohwerte"],
    ["ergebnis", "Ergebnisse"],
    ["pruefung", "Prüfung"],
    ["bericht", "Exportbericht"],
  ];
  let zeilenhoehe = $derived(HOEHEN[dichte] ?? 34);
</script>

<svelte:window onmousemove={teilBewegen} onmouseup={() => (teilZug = false)} />

{#if laeuft}
  <div class="fortschritt"></div>
{/if}

{#if startfehler}
  <div class="startfehler">
    <h1>TRDF-Prüfmodul</h1>
    <p>{startfehler}</p>
  </div>
{:else if !start}
  <div class="startfehler"><p>Lädt …</p></div>
{:else if !angemeldet}
  <Anmeldung {start} onAnmelden={anmelden} />
{:else}
  <div class="seite">
    <!-- --------------------------------------------------------- Kopf -->
    <header class="kopf">
      <div class="zeile1">
        <div class="titel">
          <div class="logo" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="22" height="22">
              <rect x="4" y="18" width="24" height="9" rx="2" fill="#d2b48c" />
              <rect x="4" y="11" width="24" height="7" rx="2" fill="#5b3a1e" />
              <rect x="4" y="5" width="24" height="6" rx="2" fill="#4b5563" />
            </svg>
          </div>
          <div>
            <div class="name">TRDF-Prüfmodul</div>
            <div class="unter">Die Rechnung des LIMS nachrechnen und prüfen</div>
          </div>
          <Info text={ERKLAERUNG.kopf} />
          {#if zustand?.auskunft}
            <span class="auskunft">{zustand.auskunft}</span>
          {/if}
        </div>
        <div class="aktionen">
          {#if start.demo}<span class="demo">Demo</span>{/if}
          <span class="nutzer" title="angemeldet an LIMS">● {benutzer || start.benutzer} @ LIMS</span>
          <button class="knopf" onclick={backupWaehlen} type="button" title="Eine Sicherung aus trdf_backup zurückspielen">
            Load backup
          </button>
          <button class="knopf gruen" onclick={exportVorschau} disabled={!zustand?.aenderungen} type="button"
            title="Von Hand geänderte Werte nach bestätigter Übersicht in das LIMS schreiben">
            Export
            {#if zustand?.aenderungen}<span class="zahlmarke">{zustand.aenderungen}</span>{/if}
          </button>
        </div>
      </div>

      <div class="zeile2">
        <label class="gruppe">
          <span class="beschriftung">Serie</span>
          <input
            class="feld serie"
            list="serienliste"
            bind:value={serie}
            oninput={serieGetippt}
            onkeydown={(e) => e.key === "Enter" && abfragen()}
            onchange={() => serien.includes(serie.trim()) && serie.trim() !== abgefragt && abfragen()}
            placeholder="z. B. 2026B051"
            spellcheck="false"
          />
          <datalist id="serienliste">
            {#each serien as s}<option value={s}></option>{/each}
          </datalist>
        </label>
        <button class="knopf primaer" onclick={abfragen} type="button">Abfragen</button>
        <label class="gruppe">
          <span class="beschriftung">Untersuchungsmethode</span>
          <select class="feld methode" bind:value={methode} onchange={laden} disabled={!methoden.length}>
            {#if !methoden.length}
              <option value="">erst abfragen</option>
            {:else}
              <option value="" disabled>bitte wählen</option>
              {#each methoden as m}<option value={String(m.um_id)}>{m.text}</option>{/each}
            {/if}
          </select>
        </label>
        <button class="knopf" onclick={einfuegenOeffnen} disabled={!zustand?.tafeln} type="button">UM einfügen …</button>
        {#if zustand?.tafeln}
          <span class="quelle" class:um={zustand.quelle_um}>{zustand.quelle}</span>
        {/if}
        <span class="stand {stand.art} hauptstand" title={stand.text}>{stand.text}</span>
      </div>
    </header>

    <!-- ------------------------------------------------------- Reiter -->
    <nav class="reiter">
      {#each REITER as [schluessel, text]}
        <button class:aktiv={reiter === schluessel} onclick={() => (reiter = schluessel)} type="button">
          {text}
          {#if schluessel !== "bericht" && befunde[schluessel]}
            <span class="befund" title="Proben mit Befund">{befunde[schluessel]}</span>
          {/if}
        </button>
      {/each}
      <span class="luecke"></span>
      <div class="dichte" title="Zeilenhöhe">
        {#each [["kompakt", "S"], ["normal", "M"], ["gross", "L"]] as [wert, text]}
          <button class:aktiv={dichte === wert} onclick={() => (dichte = wert)} type="button">{text}</button>
        {/each}
      </div>
    </nav>

    <main class="inhalt">
      <!-- ---------------------------------------------------- Rohwerte -->
      <section class="blatt" class:weg={reiter !== "roh"}>
        <div class="leiste">
          <button class="knopf klein" class:an={berechneteOffen} onclick={berechneteUmschalten} type="button">
            {berechneteOffen ? "▾" : "▸"} Berechnete Größen
          </button>
          <button class="knopf klein" onclick={() => legendeZeigen("roh")} disabled={!tafeln} type="button">Info</button>
          <button class="knopf klein" onclick={() => csv("roh", "roh")} disabled={!tafeln} type="button">Rohwertblatt CSV</button>
          <button class="knopf klein" onclick={() => csv("aenderungen", "roh")} disabled={!zustand?.aenderungen} type="button">Änderungen CSV</button>
          <button class="knopf klein" onclick={anhangVorschau} disabled={!tafeln} type="button"
            title="Den Teilprobenanhang auf den Stand der Ergebniszeile bringen">Anhang angleichen</button>
          <label class="schalter"><input type="checkbox" bind:checked={nurRohBefunde} /> nur mit Bewertung</label>
          <Info text={ERKLAERUNG.roh} />
          <Info dezent breit>
            <div class="tasten">
              <strong>Tastenkürzel</strong>
              <table><tbody>
                {#each TASTEN as [taste, wirkung]}<tr><td>{taste}</td><td>{wirkung}</td></tr>{/each}
              </tbody></table>
              <strong>Variante (_TRDV)</strong>
              <table><tbody>
                {#each VARIANTE as [taste, wirkung]}<tr><td>{taste}</td><td>{wirkung}</td></tr>{/each}
              </tbody></table>
            </div>
          </Info>
          <span class="stand {(meldungZeile.roh ?? tafeln?.roh.stand)?.art}">
            {(meldungZeile.roh ?? tafeln?.roh.stand)?.text ?? ""}
          </span>
        </div>
        <div class="geteilt" bind:this={teilRahmen}>
          {#if berechneteOffen}
            <div class="oben" style:height="{teilung * 100}%">
              <div class="unterkopf">
                <span>Berechnete Größen</span>
                <Info text={ERKLAERUNG.berechnet} />
                <button class="knopf klein leise" onclick={() => csv("ergebnis", "roh")} disabled={!tafeln} type="button">Blatt als CSV</button>
              </div>
              <div class="karte">
                <Raster
                  spalten={tafeln?.ergebnis.spalten ?? []}
                  zeilen={tafeln?.ergebnis.zeilen ?? []}
                  {auswahl}
                  sehen={arbeitszeile}
                  zeilenhoehe={zeilenhoehe - 4}
                  onProbe={blockOeffnen}
                  onSpalteVerschieben={(von, nach) => spalteVerschieben("ergebnis", "roh", von, nach)}
                />
              </div>
            </div>
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
            <div class="trenner" onmousedown={teilGreifen} role="separator" aria-orientation="horizontal" tabindex="-1"></div>
          {/if}
          <div class="unten karte">
            <Raster
              spalten={tafeln?.roh.spalten ?? []}
              zeilen={tafeln?.roh.zeilen ?? []}
              {auswahl}
              nurBefunde={nurRohBefunde}
              {zeilenhoehe}
              bearbeitbar={true}
              leerText="Serie wählen, „Abfragen“, Untersuchungsmethode wählen."
              onSetzen={setzen}
              onFuellen={fuellen}
              onProbe={blockOeffnen}
              onZeile={(p) => (arbeitszeile = p)}
              onMeldung={rasterMeldung}
              onSpalteVerschieben={(von, nach) => spalteVerschieben("roh", "roh", von, nach)}
            />
          </div>
        </div>
      </section>

      <!-- -------------------------------------------------- Ergebnisse -->
      <section class="blatt" class:weg={reiter !== "ergebnis"}>
        <div class="leiste">
          <button class="knopf klein" onclick={() => legendeZeigen("ergebnis")} disabled={!tafeln} type="button">Info</button>
          <button class="knopf klein" onclick={() => csv("ergebnis", "ergebnis")} disabled={!tafeln} type="button">Ergebnisblatt CSV</button>
          <Info text={ERKLAERUNG.ergebnis} />
          <span class="stand {(meldungZeile.ergebnis ?? tafeln?.ergebnis.stand)?.art}">
            {(meldungZeile.ergebnis ?? tafeln?.ergebnis.stand)?.text ?? ""}
          </span>
        </div>
        <div class="karte voll">
          {#if reiter === "ergebnis"}
            <Raster
              spalten={tafeln?.ergebnis.spalten ?? []}
              zeilen={tafeln?.ergebnis.zeilen ?? []}
              {auswahl}
              sehen={arbeitszeile}
              {zeilenhoehe}
              onProbe={blockOeffnen}
              onSpalteVerschieben={(von, nach) => spalteVerschieben(reiter, reiter, von, nach)}
            />
          {/if}
        </div>
      </section>

      <!-- ---------------------------------------------------- Pruefung -->
      <section class="blatt" class:weg={reiter !== "pruefung"}>
        <div class="leiste">
          <button class="knopf klein" onclick={() => legendeZeigen("pruefung")} disabled={!tafeln} type="button">Info</button>
          <button class="knopf klein" onclick={() => csv("pruefung", "pruefung")} disabled={!tafeln} type="button">Blatt CSV</button>
          <button class="knopf klein primaer" onclick={bildZeigen} disabled={!tafeln} type="button">Bild</button>
          <label class="schalter"><input type="checkbox" bind:checked={nurBefunde} /> nur mit Befund</label>
          <Info text={ERKLAERUNG.pruefung + (zustand?.legende ? "\n\n" + zustand.legende : "")} breit />
          <span class="stand {(meldungZeile.pruefung ?? tafeln?.pruefung.stand)?.art}">
            {(meldungZeile.pruefung ?? tafeln?.pruefung.stand)?.text ?? ""}
          </span>
        </div>
        {#if zustand?.legende}
          <div class="legendenzeile">{zustand.legende.split("\n")[1] ?? ""}</div>
        {/if}
        <div class="karte voll">
          {#if reiter === "pruefung"}
            <Raster
              spalten={tafeln?.pruefung.spalten ?? []}
              zeilen={tafeln?.pruefung.zeilen ?? []}
              {auswahl}
              {nurBefunde}
              sehen={arbeitszeile}
              {zeilenhoehe}
              onProbe={blockOeffnen}
              onSpalteVerschieben={(von, nach) => spalteVerschieben(reiter, reiter, von, nach)}
            />
          {/if}
        </div>
      </section>

      <!-- ----------------------------------------------- Exportbericht -->
      <section class="blatt" class:weg={reiter !== "bericht"}>
        <div class="leiste">
          <button class="knopf klein" onclick={() => csv("bericht", "bericht")} disabled={!zustand?.bericht?.zeilen?.length} type="button">Bericht als CSV</button>
          <button class="knopf klein" onclick={() => rufe("ordner_oeffnen", "backup")} type="button">Ordner trdf_backup</button>
          <Info text={ERKLAERUNG.bericht} />
          <span class="stand {(meldungZeile.bericht ?? zustand?.bericht?.stand)?.art}">
            {(meldungZeile.bericht ?? zustand?.bericht?.stand)?.text ?? ""}
          </span>
        </div>
        <div class="karte voll">
          {#if reiter === "bericht"}
            <Raster
              spalten={(zustand?.bericht?.spalten ?? []).map((name) => ({
                name, kopf: [name], hinweis: "", fest: name === "Zeile" || name === "Probe-Nr.",
                aenderbar: false, gruppe: false, breite: name === "Zeile" ? 64 : name === "Probe-Nr." ? 112 : 170,
              }))}
              zeilen={zustand?.bericht?.zeilen ?? []}
              {zeilenhoehe}
              leerText="Es wurde in dieser Sitzung noch nichts geschrieben."
              onProbe={blockOeffnen}
            />
          {/if}
        </div>
      </section>
    </main>
  </div>

  {#each bloecke as b (b.z)}
    <Block
      daten={b.daten}
      x={b.x}
      y={b.y}
      z={b.z}
      onZu={() => (bloecke = bloecke.filter((x) => x !== b))}
      onWechsel={(r) => blockWechseln(b, r)}
      onVorne={() => vorne(b)}
      onZiehen={(x, y) => { b.x = x; b.y = y; }}
    />
  {/each}
{/if}

{#if einfuegen}
  <Einfuegen
    text={einfuegen.text}
    quelle={zustand?.quelle ?? ""}
    stand={einfuegen.stand}
    onUebernehmen={umUebernehmen}
    onLeeren={umLeeren}
    onZu={() => (einfuegen = null)}
  />
{/if}
{#if vorschau}
  <Vorschau {vorschau} onJa={vorschauJa} onZu={vorschauZu} />
{/if}
{#if bild}
  <Bild {bild} onProbe={(p) => { blockOeffnen(p); }} onZu={() => (bild = null)} />
{/if}
{#if legende}
  <Legende {legende} onSpeichern={legendeSpeichern} onZu={() => (legende = null)} />
{/if}
{#if sicherungen}
  <Dialog titel="Load backup" unter={sicherungen.ordner} breite="640px" onZu={() => (sicherungen = null)}>
    {#if !sicherungen.dateien.length}
      <p class="leerliste">In diesem Ordner liegt keine Sicherung.</p>
    {/if}
    <div class="dateien">
      {#each sicherungen.dateien as pfad}
        <button class="datei" onclick={() => backupLesen(pfad)} type="button">{pfad.split(/[\\/]/).pop()}</button>
      {/each}
    </div>
    <div style="height:18px"></div>
  </Dialog>
{/if}
{#if meldung}
  <Meldung {meldung} onZu={() => (meldung = null)} />
{/if}

<style>
  .fortschritt {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    z-index: 100;
    background: linear-gradient(90deg, transparent, var(--akzent), transparent);
    background-size: 40% 100%;
    background-repeat: no-repeat;
    animation: lauf 1s linear infinite;
  }
  @keyframes lauf {
    from {
      background-position: -40% 0;
    }
    to {
      background-position: 140% 0;
    }
  }
  .startfehler {
    height: 100%;
    display: grid;
    place-content: center;
    text-align: center;
    color: var(--text-2);
  }

  .seite {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  /* --------------------------------------------------------- Kopf */
  .kopf {
    background: var(--flaeche);
    border-bottom: 1px solid var(--rand);
    padding: 10px 18px 12px;
    box-shadow: 0 1px 2px rgb(15 23 42 / 4%);
    z-index: 5;
  }
  .zeile1 {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }
  .titel {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }
  .logo {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: var(--flaeche-2);
    border: 1px solid var(--rand);
    display: grid;
    place-items: center;
    flex: none;
  }
  .name {
    font-weight: 700;
    font-size: 16px;
  }
  .unter {
    font-size: 12px;
    color: var(--text-2);
  }
  .auskunft {
    margin-left: 6px;
    padding: 4px 10px;
    border-radius: 14px;
    background: var(--akzent-zart);
    color: #1e40af;
    font-size: 12.5px;
    font-weight: 600;
    white-space: nowrap;
  }
  .aktionen {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .nutzer {
    font-size: 12.5px;
    color: var(--text-2);
    margin-right: 6px;
    white-space: nowrap;
  }
  .nutzer::first-letter {
    color: #16a34a;
  }
  .demo {
    font-size: 12px;
    font-weight: 700;
    color: var(--amber);
    background: var(--amber-hell);
    border-radius: 10px;
    padding: 2px 8px;
  }
  .zeile2 {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    margin-top: 10px;
    min-width: 0;
  }
  .gruppe {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .serie {
    width: 150px;
    font-weight: 600;
  }
  .methode {
    width: 200px;
  }
  .quelle {
    align-self: center;
    margin-top: 18px;
    font-size: 12.5px;
    padding: 4px 10px;
    border-radius: 14px;
    background: var(--gruppe);
    color: var(--text-2);
    white-space: nowrap;
  }
  .quelle.um {
    background: var(--akzent-hell);
    color: #1e40af;
    font-weight: 600;
  }
  .hauptstand {
    flex: 1;
    min-width: 0;
    align-self: center;
    margin: 18px 0 0 8px;
  }

  /* ------------------------------------------------------- Reiter */
  .reiter {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    padding: 8px 18px 0;
  }
  .reiter > button {
    border: none;
    background: transparent;
    padding: 8px 14px 9px;
    font-weight: 600;
    color: var(--text-2);
    border-radius: 8px 8px 0 0;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    display: inline-flex;
    gap: 8px;
    align-items: center;
  }
  .reiter > button:hover {
    color: var(--text);
    background: rgb(255 255 255 / 60%);
  }
  .reiter > button.aktiv {
    color: var(--akzent);
    border-bottom-color: var(--akzent);
    background: var(--flaeche);
  }
  .befund {
    font-size: 11px;
    min-width: 20px;
    padding: 0 6px;
    height: 18px;
    border-radius: 9px;
    background: var(--amber-hell);
    color: var(--amber);
    display: inline-grid;
    place-items: center;
  }
  .luecke {
    flex: 1;
  }
  .dichte {
    display: flex;
    margin-bottom: 6px;
    border: 1px solid var(--rand-stark);
    border-radius: 8px;
    overflow: hidden;
    background: var(--flaeche);
  }
  .dichte button {
    border: none;
    background: transparent;
    width: 30px;
    height: 26px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-2);
    cursor: pointer;
  }
  .dichte button.aktiv {
    background: var(--akzent);
    color: #fff;
  }

  /* -------------------------------------------------------- Inhalt */
  .inhalt {
    flex: 1;
    min-height: 0;
    position: relative;
  }
  .blatt {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    padding: 10px 18px 16px;
    gap: 8px;
  }
  .blatt.weg {
    visibility: hidden;
    pointer-events: none;
  }
  .leiste {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .leiste .stand {
    flex: 1;
    min-width: 0;
    margin-left: 8px;
  }
  .knopf.an {
    background: var(--akzent-zart);
    border-color: #93c5fd;
    color: #1e40af;
  }
  .schalter {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    font-size: 13px;
    color: var(--text-2);
    margin-left: 4px;
    white-space: nowrap;
    cursor: pointer;
  }
  .schalter input {
    accent-color: var(--akzent);
  }
  .karte {
    background: var(--flaeche);
    border: 1px solid var(--rand);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--schatten);
    min-height: 0;
  }
  .karte.voll {
    flex: 1;
  }
  .geteilt {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .oben {
    display: flex;
    flex-direction: column;
    min-height: 80px;
  }
  .oben .karte {
    flex: 1;
  }
  .unterkopf {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-2);
    margin-bottom: 4px;
  }
  .trenner {
    height: 10px;
    cursor: row-resize;
    position: relative;
    flex: none;
  }
  .trenner::after {
    content: "";
    position: absolute;
    left: 50%;
    top: 3px;
    width: 46px;
    height: 4px;
    margin-left: -23px;
    border-radius: 2px;
    background: var(--rand-stark);
  }
  .trenner:hover::after {
    background: var(--akzent);
  }
  .unten {
    flex: 1;
  }
  .legendenzeile {
    font-size: 12px;
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tasten table {
    border-collapse: collapse;
    margin: 6px 0 12px;
    width: 100%;
  }
  .tasten td {
    padding: 2px 10px 2px 0;
    vertical-align: top;
  }
  .tasten td:first-child {
    font-family: var(--mono);
    font-size: 12px;
    color: #93c5fd;
    white-space: nowrap;
  }
  .dateien {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .datei {
    text-align: left;
    border: 1px solid var(--rand);
    background: var(--flaeche-2);
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-family: var(--mono);
    font-size: 12.5px;
  }
  .datei:hover {
    border-color: var(--akzent);
    background: var(--akzent-zart);
  }
  .leerliste {
    color: var(--text-2);
  }
</style>
