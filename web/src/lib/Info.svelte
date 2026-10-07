<script>
  // Ein kleines "i": der Erklaertext steht dahinter und nicht im Weg.
  // Blau fuer Erklaerungen, grau (dezent) fuer das, was man einmal
  // nachschlaegt und dann kann - wie die Tastenkuerzel.
  let { text = "", dezent = false, breit = false, children = null } = $props();
  let offen = $state(false);
  let gehalten = $state(false);
  let knopf = $state(null);
  let lage = $state({ x: 0, y: 0 });

  function zeigen() {
    const r = knopf.getBoundingClientRect();
    const breite = breit ? 460 : 380;
    lage = {
      x: Math.max(8, Math.min(r.left - 12, window.innerWidth - breite - 12)),
      y: r.bottom + 8,
    };
    offen = true;
  }
  function verbergen() {
    if (!gehalten) offen = false;
  }
  function klick(e) {
    e.stopPropagation();
    gehalten = !gehalten;
    if (gehalten) zeigen();
    else offen = false;
  }
</script>

<svelte:window onclick={() => { gehalten = false; offen = false; }} />

<button
  class="i"
  class:dezent
  bind:this={knopf}
  onmouseenter={zeigen}
  onmouseleave={verbergen}
  onclick={klick}
  aria-label="Erklärung"
  type="button">i</button>

{#if offen}
  <div
    class="blase"
    class:breit
    style:left="{lage.x}px"
    style:top="{lage.y}px"
    role="tooltip"
  >
    {#if children}{@render children()}{:else}{text}{/if}
  </div>
{/if}

<style>
  .i {
    width: 18px;
    height: 18px;
    padding: 0;
    border-radius: 50%;
    border: none;
    background: var(--akzent);
    color: #fff;
    font: italic 700 11px/18px Georgia, "Times New Roman", serif;
    cursor: help;
    flex: none;
    transition: transform 0.1s;
  }
  .i:hover {
    transform: scale(1.1);
  }
  .i.dezent {
    background: #e2e8f0;
    color: #64748b;
  }
  .blase {
    position: fixed;
    z-index: 60;
    width: 380px;
    padding: 12px 14px;
    border-radius: 10px;
    background: #0f172a;
    color: #e2e8f0;
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    box-shadow: var(--schatten-hoch);
  }
  .blase.breit {
    width: 460px;
  }
</style>
