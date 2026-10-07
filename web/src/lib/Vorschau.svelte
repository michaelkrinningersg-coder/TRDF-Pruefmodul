<script>
  // Der Riegel vor dem einzigen Weg, der einen Messwert ueberschreibt:
  // jede betroffene Zeile mit alt und neu. Erst der gruene Knopf
  // schreibt - und auch der erst, nachdem der alte Stand gesichert ist.
  import Dialog from "./Dialog.svelte";
  let { vorschau, onJa, onZu } = $props();
  let arbeitet = $state(false);

  const BREITEN = {
    Zeile: 64, "Probe-Nr.": 104, Groesse: 120, Art: 90, Pruefmethode: 200,
    PM_ID: 72, PM_VER: 72, Ziel: 160, "Wert aktuell LIMS": 150, "Wert neu": 150,
  };
  const KOPF = { Groesse: "Größe", Pruefmethode: "Prüfmethode" };

  async function ja() {
    arbeitet = true;
    try {
      await onJa();
    } finally {
      arbeitet = false;
    }
  }
</script>

<Dialog
  titel={vorschau.titel}
  unter="{vorschau.anzahl} Werte werden überschrieben"
  breite="min(1320px, 96vw)"
  hoehe="min(760px, 92vh)"
  onZu={arbeitet ? null : onZu}
>
  <p class="hinweis">{vorschau.hinweis}</p>
  <div class="legende">
    <span><i class="ohne"></i>keine Ergebniszeile im LIMS – wird nur gemeldet</span>
    {#if vorschau.art === "export"}
      <span><i class="wieder"></i>schon früher korrigiert</span>
    {/if}
  </div>
  <div class="tabelle">
    <table>
      <thead>
        <tr>
          {#each vorschau.spalten as s}
            <th style:min-width="{BREITEN[s] ?? 90}px" class:zahl={s.startsWith("Wert") || s.startsWith("PM")}>{KOPF[s] ?? s}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each vorschau.zeilen as zeile, i}
          <tr class={vorschau.marken[i]}>
            {#each zeile as wert, c}
              <td class:zahl={vorschau.spalten[c].startsWith("Wert") || vorschau.spalten[c].startsWith("PM")} class:neu={vorschau.spalten[c] === "Wert neu"}>{wert ?? ""}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#snippet fuss()}
    <span class="luecke"></span>
    <button class="knopf" onclick={onZu} disabled={arbeitet} type="button">Abbrechen</button>
    <button class="knopf gruen" onclick={ja} disabled={arbeitet} type="button">
      {arbeitet ? "Wird geschrieben …" : vorschau.knopf}
    </button>
  {/snippet}
</Dialog>

<style>
  .hinweis {
    margin: 0 0 10px;
    color: var(--text-2);
    font-size: 13px;
    line-height: 1.55;
  }
  .legende {
    display: flex;
    gap: 18px;
    font-size: 12px;
    color: var(--text-2);
    margin-bottom: 8px;
  }
  .legende i {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 3px;
    margin-right: 6px;
    vertical-align: -1px;
  }
  .legende .ohne, tr.ohne td {
    background: var(--amber-hell);
  }
  .legende .wieder, tr.wieder td {
    background: var(--violett-hell);
  }
  .tabelle {
    flex: 1;
    min-height: 0;
    overflow: auto;
    border: 1px solid var(--rand);
    border-radius: 10px;
  }
  table {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    font-variant-numeric: tabular-nums;
  }
  th {
    position: sticky;
    top: 0;
    background: var(--flaeche-2);
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 10px;
    border-bottom: 1px solid var(--rand-stark);
    white-space: nowrap;
  }
  td {
    padding: 6px 10px;
    border-bottom: 1px solid var(--rand);
    white-space: nowrap;
  }
  .zahl {
    text-align: right;
  }
  td.neu {
    font-weight: 600;
    color: var(--gruen);
  }
  .luecke {
    flex: 1;
  }
</style>
