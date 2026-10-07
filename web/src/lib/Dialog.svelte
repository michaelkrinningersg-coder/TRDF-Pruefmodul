<script>
  // Ein Dialog ueber der Seite - Esc oder der Hintergrund schliesst.
  let {
    titel = "",
    unter = "",
    breite = "720px",
    hoehe = null,
    onZu = null,
    children,
    fuss = null,
  } = $props();

  function taste(e) {
    if (e.key === "Escape" && onZu) {
      e.stopPropagation();
      onZu();
    }
  }
</script>

<svelte:window onkeydown={taste} />

<div class="hinten" role="presentation" onmousedown={(e) => e.target === e.currentTarget && onZu?.()}>
  <div
    class="dialog"
    style:width={breite}
    style:height={hoehe}
    role="dialog"
    aria-modal="true"
    aria-label={titel}
  >
    <header>
      <div>
        <h2>{titel}</h2>
        {#if unter}<p>{unter}</p>{/if}
      </div>
      {#if onZu}
        <button class="zu" onclick={onZu} aria-label="Schließen" type="button">✕</button>
      {/if}
    </header>
    <div class="inhalt">{@render children()}</div>
    {#if fuss}
      <footer>{@render fuss()}</footer>
    {/if}
  </div>
</div>

<style>
  .hinten {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: rgb(15 23 42 / 35%);
    display: grid;
    place-items: center;
    animation: ein 0.12s ease-out;
    backdrop-filter: blur(1.5px);
  }
  .dialog {
    max-width: calc(100vw - 48px);
    max-height: calc(100vh - 48px);
    display: flex;
    flex-direction: column;
    background: var(--flaeche);
    border-radius: 14px;
    box-shadow: var(--schatten-hoch);
    overflow: hidden;
    animation: hoch 0.16s ease-out;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    padding: 18px 22px 12px;
  }
  h2 {
    margin: 0;
    font-size: 17px;
    font-weight: 650;
  }
  header p {
    margin: 4px 0 0;
    color: var(--text-2);
    font-size: 13px;
  }
  .zu {
    border: none;
    background: transparent;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    color: var(--text-2);
    cursor: pointer;
    font-size: 15px;
  }
  .zu:hover {
    background: var(--gruppe);
  }
  .inhalt {
    flex: 1;
    min-height: 0;
    padding: 0 22px;
    overflow: auto;
    display: flex;
    flex-direction: column;
  }
  footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    padding: 14px 22px 18px;
  }
  @keyframes ein {
    from {
      opacity: 0;
    }
  }
  @keyframes hoch {
    from {
      transform: translateY(8px) scale(0.99);
      opacity: 0;
    }
  }
</style>
