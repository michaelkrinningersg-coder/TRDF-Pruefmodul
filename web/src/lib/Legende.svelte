<script>
  // "Info": was die Spalten einer Tabelle bedeuten - und wie sie stehen.
  //
  // Wie die Legende der Tk-Fassung: Reihenfolge durch Ziehen, "Fest"
  // haelt eine Spalte links, "Zeigen" blendet aus, "Kopfzeile" sagt je
  // Spalte, was oben steht, und die Beschreibung ist frei. Gespeichert
  // wird in den Einstellungen neben der exe, nicht in der Datenbank.
  import { untrack } from "svelte";
  import Dialog from "./Dialog.svelte";

  let { legende: aussen, onSpeichern, onZu } = $props();
  // Die Legende gilt, wie sie beim Oeffnen kam - geaendert wird hier.
  const legende = untrack(() => aussen);

  const NAMEN = { Kuerzel: "Kürzel", Formelkuerzel: "Formelkürzel" };
  let kopfwahl = $state(legende.ordnung.kopfspalte || legende.kopfwahl[0]);
  let eigene = $state({ ...legende.ordnung.kopfspalten });
  let fest = $state([...legende.ordnung.fest]);
  let versteckt = $state([...legende.ordnung.versteckt]);
  let zeilen = $state(legende.zeilen.map((z) => [...z]));
  const geladen = Object.fromEntries(legende.zeilen.map((z) => [z[0], z[z.length - 1] ?? ""]));
  let stand = $state(null);
  let gezogen = $state(null);
  let ueber = $state(null);
  let arbeitet = $state(false);

  const kuerzel = (kennung) => legende.schluessel[kennung] ?? kennung;
  const eintrag = (k) => eigene[k] ?? kopfwahl;

  function schalteFest(k) {
    if (fest.includes(k)) fest = fest.filter((x) => x !== k);
    else {
      fest = [...fest, k];
      versteckt = versteckt.filter((x) => x !== k);
    }
  }
  function schalteZeigen(k) {
    if (fest.includes(k)) {
      stand = { text: "Was fest steht, bleibt sichtbar – erst das „ja“ bei „Fest“ wegnehmen.", art: "warn" };
      return;
    }
    versteckt = versteckt.includes(k) ? versteckt.filter((x) => x !== k) : [...versteckt, k];
  }
  function schalteKopf(k) {
    const reihe = legende.kopfwahl;
    const stelle = reihe.indexOf(eintrag(k));
    eigene = { ...eigene, [k]: reihe[(stelle + 1) % reihe.length] };
  }
  function alleKoepfe() {
    eigene = {};
  }

  function verschieben(von, nach) {
    // Feste Zeilen bleiben, wo sie sind - und nichts schiebt sich
    // zwischen sie.
    const quelle = kuerzel(von);
    const ziel = kuerzel(nach);
    if (quelle === ziel || fest.includes(quelle) || fest.includes(ziel)) return;
    const stellen = zeilen.map((z, i) => (kuerzel(z[0]) === quelle ? i : -1)).filter((i) => i >= 0);
    const block = stellen.map((i) => zeilen[i]);
    const rest = zeilen.filter((z) => kuerzel(z[0]) !== quelle);
    const treffer = rest.map((z, i) => (kuerzel(z[0]) === ziel ? i : -1)).filter((i) => i >= 0);
    if (!treffer.length) return;
    const zielStelle = Math.min(...zeilen.map((z, i) => (kuerzel(z[0]) === ziel ? i : Infinity)));
    const hinunter = stellen[0] < zielStelle;
    const stelle = hinunter ? treffer[treffer.length - 1] + 1 : treffer[0];
    zeilen = [...rest.slice(0, stelle), ...block, ...rest.slice(stelle)];
  }

  function texte() {
    const gefunden = {};
    const bewegt = new Set();
    for (const z of zeilen) {
      const k = kuerzel(z[0]);
      const text = String(z[z.length - 1] ?? "").trim();
      const geaendert = text !== String(geladen[z[0]] ?? "").trim();
      if (bewegt.has(k) && !geaendert) continue;
      gefunden[k] = text;
      if (geaendert) bewegt.add(k);
    }
    return gefunden;
  }

  function ordnung() {
    const reihenfolge = [];
    for (const z of zeilen) {
      const k = kuerzel(z[0]);
      if (!reihenfolge.includes(k)) reihenfolge.push(k);
    }
    return {
      reihenfolge,
      fest: reihenfolge.filter((k) => fest.includes(k)),
      versteckt: reihenfolge.filter((k) => versteckt.includes(k) && !fest.includes(k)),
      kopfspalte: kopfwahl,
      kopfspalten: Object.fromEntries(Object.entries(eigene).filter(([, w]) => w !== kopfwahl)),
    };
  }

  async function speichern() {
    arbeitet = true;
    try {
      stand = await onSpeichern(texte(), ordnung());
    } finally {
      arbeitet = false;
    }
  }

  let spaltenkopf = $derived(legende.kopf);
</script>

<Dialog titel={legende.titel} breite="min(1320px, 96vw)" hoehe="min(820px, 92vh)" {onZu}>
  <details class="hinweis">
    <summary>So funktioniert die Legende</summary>
    <p>{legende.hinweis}</p>
  </details>
  <div class="leiste">
    <span class="beschriftung">Überschrift für alle:</span>
    <select class="feld" bind:value={kopfwahl} onchange={alleKoepfe}>
      {#each legende.kopfwahl as w}<option value={w}>{NAMEN[w] ?? w}</option>{/each}
    </select>
  </div>
  <div class="tabelle">
    <table>
      <thead>
        <tr>
          <th class="griff"></th>
          <th>{NAMEN[spaltenkopf[0]] ?? spaltenkopf[0]}</th>
          <th class="schalter">Fest</th>
          <th class="schalter">Zeigen</th>
          <th class="schalter breit">Kopfzeile</th>
          {#each spaltenkopf.slice(1) as k}
            <th class:beschreibung={k === "Beschreibung"}>{NAMEN[k] ?? k}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each zeilen as zeile, i (zeile[0])}
          {@const k = kuerzel(zeile[0])}
          {@const istFest = fest.includes(k)}
          <tr
            draggable={!istFest}
            class:fest={istFest}
            class:ziel={ueber === zeile[0] && gezogen && gezogen !== zeile[0]}
            class:aus={versteckt.includes(k) && !istFest}
            ondragstart={(e) => { gezogen = zeile[0]; e.dataTransfer.effectAllowed = "move"; }}
            ondragover={(e) => { e.preventDefault(); ueber = zeile[0]; }}
            ondrop={(e) => { e.preventDefault(); verschieben(gezogen, zeile[0]); gezogen = null; ueber = null; }}
            ondragend={() => { gezogen = null; ueber = null; }}
          >
            <td class="griff">{istFest ? "📌" : "⋮⋮"}</td>
            <td class="name">{zeile[0]}</td>
            <td class="schalter"><button class="pille" class:ja={istFest} onclick={() => schalteFest(k)} type="button">{istFest ? "ja" : "nein"}</button></td>
            <td class="schalter"><button class="pille" class:ja={!versteckt.includes(k) || istFest} onclick={() => schalteZeigen(k)} type="button">{!versteckt.includes(k) || istFest ? "ja" : "nein"}</button></td>
            <td class="schalter"><button class="pille wahl" onclick={() => schalteKopf(k)} type="button">{NAMEN[eintrag(k)] ?? eintrag(k)}</button></td>
            {#each zeile.slice(1) as wert, c}
              {#if c === zeile.length - 2}
                <td class="beschreibung"><input class="feld klein" bind:value={zeile[zeile.length - 1]} placeholder="eigene Beschreibung …" /></td>
              {:else}
                <td>{wert}</td>
              {/if}
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#snippet fuss()}
    <span class="stand {stand?.art ?? ''}">{stand?.text ?? "Zeilen greifen und ziehen ändert die Reihenfolge der Spalten."}</span>
    <span class="luecke"></span>
    <button class="knopf" onclick={onZu} type="button">Schließen</button>
    <button class="knopf primaer" onclick={speichern} disabled={arbeitet} type="button">Speichern</button>
  {/snippet}
</Dialog>

<style>
  .hinweis {
    font-size: 13px;
    color: var(--text-2);
    margin-bottom: 10px;
  }
  .hinweis summary {
    cursor: pointer;
    color: var(--akzent);
  }
  .hinweis p {
    white-space: pre-wrap;
    line-height: 1.55;
  }
  .leiste {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  .tabelle {
    flex: 1;
    min-height: 0;
    overflow: auto;
    border: 1px solid var(--rand);
    border-radius: 10px;
  }
  table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 13px;
  }
  th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--flaeche-2);
    text-align: left;
    font-size: 12px;
    padding: 8px 8px;
    border-bottom: 1px solid var(--rand-stark);
    white-space: nowrap;
  }
  td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--rand);
    white-space: nowrap;
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  tr[draggable="true"] {
    cursor: grab;
  }
  tr.fest td {
    background: var(--flaeche-2);
  }
  tr.aus td {
    color: var(--text-3);
  }
  tr.ziel td {
    box-shadow: inset 0 2px 0 var(--akzent);
  }
  .griff {
    width: 30px;
    color: var(--text-3);
    text-align: center;
  }
  .name {
    font-weight: 600;
  }
  .schalter {
    width: 70px;
    text-align: center;
  }
  .schalter.breit {
    width: 120px;
  }
  .pille {
    border: 1px solid var(--rand-stark);
    background: #fff;
    border-radius: 12px;
    padding: 1px 10px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text-2);
  }
  .pille.ja {
    background: var(--akzent-hell);
    border-color: #93c5fd;
    color: #1e40af;
  }
  .pille.wahl {
    min-width: 92px;
  }
  .beschreibung {
    width: 32%;
    min-width: 260px;
    max-width: none;
  }
  .beschreibung input {
    width: 100%;
    height: 28px;
  }
  .luecke {
    flex: 1;
  }
</style>
