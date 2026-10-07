<script>
  // "UM einfuegen": die Liste aus der Probenvorbereitung - gross, damit
  // sie ganz zu sehen ist. Was hier steht, bleibt beim Schliessen liegen.
  import { untrack } from "svelte";
  import Dialog from "./Dialog.svelte";
  import { ERKLAERUNG } from "./tasten.js";

  let { text = "", quelle = "", stand = null, onUebernehmen, onLeeren, onZu } = $props();
  let inhalt = $state(untrack(() => text));
  let feld = $state(null);
  let arbeitet = $state(false);

  $effect(() => {
    feld?.focus();
  });

  async function uebernehmen() {
    arbeitet = true;
    try {
      await onUebernehmen(inhalt);
    } finally {
      arbeitet = false;
    }
  }
  async function leeren() {
    inhalt = "";
    await onLeeren();
    feld?.focus();
  }
  let zeilen = $derived(inhalt.trim() ? inhalt.trim().split(/\r?\n/).length : 0);
</script>

<Dialog
  titel="UM einfügen"
  unter="Liste aus der Probenvorbereitung: aktueller Block → kopieren, hier Strg+V, dann Übernehmen."
  breite="min(1280px, 94vw)"
  hoehe="min(820px, 90vh)"
  onZu={() => onZu(inhalt)}
>
  <textarea
    bind:this={feld}
    bind:value={inhalt}
    spellcheck="false"
    placeholder="Hier mit Strg+V einfügen …"
  ></textarea>
  <div class="unten">
    <span class="hinweis">{ERKLAERUNG.einfuegen}</span>
  </div>
  {#snippet fuss()}
    <span class="stand {stand?.art ?? ''}">
      {stand?.text ?? `${zeilen} Zeilen  ·  ${quelle}`}
    </span>
    <span class="luecke"></span>
    <button class="knopf" onclick={leeren} type="button">Leeren</button>
    <button class="knopf" onclick={() => onZu(inhalt)} type="button">Schließen</button>
    <button class="knopf primaer" onclick={uebernehmen} disabled={arbeitet || !inhalt.trim()} type="button">
      Übernehmen
    </button>
  {/snippet}
</Dialog>

<style>
  textarea {
    flex: 1;
    min-height: 300px;
    width: 100%;
    resize: none;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid var(--rand-stark);
    background: var(--flaeche-2);
    font: 13px/1.5 var(--mono);
    white-space: pre;
    overflow: auto;
    tab-size: 14;
    outline: none;
  }
  textarea:focus {
    border-color: var(--akzent);
    box-shadow: 0 0 0 3px var(--akzent-hell);
    background: #fff;
  }
  .unten {
    padding: 10px 2px 0;
  }
  .hinweis {
    font-size: 12.5px;
    color: var(--text-2);
  }
  .luecke {
    flex: 1;
  }
  .stand {
    max-width: 60%;
  }
</style>
