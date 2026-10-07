<script>
  // Der Bodenblock einer Probe - ein schwebendes Fenster in der Seite.
  //
  // Links die Probe, wie sie im Boden stand; in der Mitte die Zahlen,
  // aus denen sie gerechnet ist; rechts die Schaufelprobe nach Volumen.
  // Es bleibt ueber den Tabellen liegen und zeichnet jede Eingabe sofort
  // mit. Pfeil rauf und runter blaettert durch die Serie.
  let { daten, x = 80, y = 120, z = 30, onZu, onWechsel, onVorne, onZiehen } = $props();

  const HOEHE = 300;
  const BREITE = 140;
  const BREITE_SCHAUFEL = 120;
  const BESCHRIFTBAR = 15;

  let fenster = $state(null);
  let zug = null;

  // Beim Oeffnen den Fokus nehmen - sonst gehen Pfeil rauf und runter an
  // die Tabelle dahinter statt an den Block.
  $effect(() => {
    fenster?.focus();
  });

  function greifen(e) {
    if (e.button !== 0 || e.target.closest("button")) return;
    onVorne?.();
    zug = { dx: e.clientX - x, dy: e.clientY - y };
    e.preventDefault();
  }
  function bewegen(e) {
    if (!zug) return;
    const nx = Math.max(-200, Math.min(window.innerWidth - 120, e.clientX - zug.dx));
    const ny = Math.max(0, Math.min(window.innerHeight - 60, e.clientY - zug.dy));
    onZiehen?.(nx, ny);
  }
  function loslassen() {
    zug = null;
  }
  function taste(e) {
    if (e.key === "ArrowUp" || e.key === "PageUp") {
      e.preventDefault();
      onWechsel(-1);
    } else if (e.key === "ArrowDown" || e.key === "PageDown") {
      e.preventDefault();
      onWechsel(1);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onZu();
    }
  }
  function lage(l, hoehe) {
    const h = l.hoehe * hoehe;
    return { y: hoehe - (l.unten + l.hoehe) * hoehe, h };
  }
</script>

<svelte:window onmousemove={bewegen} onmouseup={loslassen} />

<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<section
  class="block"
  bind:this={fenster}
  style:left="{x}px"
  style:top="{y}px"
  style:z-index={z}
  tabindex="0"
  onkeydown={taste}
  onmousedown={() => onVorne?.()}
  aria-label="Bodenblock {daten.probe}"
>
  <header onmousedown={greifen} role="toolbar" tabindex="-1">
    <div class="titel">
      <strong>Probe {daten.probe}</strong>
      {#if daten.variante !== null && daten.variante !== undefined}
        <span class="chip">Variante {daten.variante}</span>
      {/if}
      <span class="zaehler">{daten.stelle + 1} / {daten.anzahl}</span>
    </div>
    <div class="knoepfe">
      <button onclick={() => { onWechsel(-1); fenster?.focus(); }} disabled={daten.stelle <= 0} aria-label="Vorige Probe" type="button">▲</button>
      <button onclick={() => { onWechsel(1); fenster?.focus(); }} disabled={daten.stelle >= daten.anzahl - 1} aria-label="Nächste Probe" type="button">▼</button>
      <button onclick={onZu} aria-label="Schließen" type="button">✕</button>
    </div>
  </header>

  <div class="inhalt">
    <div class="spalte">
      <div class="klein">Probe</div>
      <svg width={BREITE} height={HOEHE} class="saeule">
        {#if !daten.lagen.length}
          <text x={BREITE / 2} y={HOEHE / 2 - 6} text-anchor="middle" class="leer">kein Skelettanteil</text>
          <text x={BREITE / 2} y={HOEHE / 2 + 10} text-anchor="middle" class="leer">berechnet</text>
        {/if}
        {#each daten.lagen as l}
          {@const g = lage(l, HOEHE)}
          <rect x="0" y={g.y} width={BREITE} height={g.h} fill={l.farbe} />
          {#if g.h >= BESCHRIFTBAR && l.text}
            <text x={BREITE / 2} y={g.y + g.h / 2 + 4} text-anchor="middle" fill={l.schrift} class="wert">{l.text}</text>
          {/if}
        {/each}
      </svg>
      <ul class="legende">
        {#each daten.legende as l}
          <li><i style:background={l.farbe}></i>{l.text}</li>
        {/each}
      </ul>
    </div>

    <div class="zahlen">
      <div class="klein">Trockenrohdichte Feinboden</div>
      <div class="gross">{daten.dichte}</div>
      <div class="paar">
        <div><div class="klein">Feinbodenvorrat</div><div class="mittel">{daten.vorrat}</div></div>
        <div><div class="klein">Skelettanteil</div><div class="mittel">{daten.skelett}</div></div>
      </div>
      {#each daten.gruppen as g}
        <div class="gruppe">{g.name}</div>
        {#each g.zeilen as z}
          <div class="zeile"><span>{z.text}</span><span>{z.wert}</span></div>
        {/each}
      {/each}
    </div>

    <div class="spalte">
      <div class="klein">Schaufelprobe</div>
      <svg width={BREITE_SCHAUFEL} height={HOEHE} class="saeule">
        {#if !daten.schaufel.length}
          <text x={BREITE_SCHAUFEL / 2} y={HOEHE / 2 - 6} text-anchor="middle" class="leer">keine</text>
          <text x={BREITE_SCHAUFEL / 2} y={HOEHE / 2 + 10} text-anchor="middle" class="leer">Schaufelprobe</text>
        {/if}
        {#each daten.schaufel as l}
          {@const g = lage(l, HOEHE)}
          {#if !l.nur_text}
            <rect x="0" y={g.y} width={BREITE_SCHAUFEL} height={g.h} fill={l.farbe} />
          {/if}
          {#if g.h >= BESCHRIFTBAR && l.text}
            <text x={BREITE_SCHAUFEL / 2} y={g.y + g.h / 2 + 4} text-anchor="middle" fill={l.schrift} class="wert">{l.text}</text>
          {/if}
        {/each}
        {#if daten.hundert !== null && daten.hundert !== undefined}
          <line x1="0" x2={BREITE_SCHAUFEL} y1={HOEHE - daten.hundert * HOEHE} y2={HOEHE - daten.hundert * HOEHE}
            stroke="#111827" stroke-dasharray="4 3" />
        {/if}
      </svg>
      <ul class="legende">
        {#each daten.schaufellegende as l}
          <li><i style:background={l.farbe}></i>{l.text}</li>
        {/each}
      </ul>
    </div>
  </div>
  <footer>Von unten nach oben: Feinboden, gewogener Grobboden, geschätzter Grobboden. Über der gestrichelten Linie: was größer als 63 mm war. ↑/↓ blättert.</footer>
</section>

<style>
  .block {
    position: fixed;
    width: 640px;
    background: var(--flaeche);
    border-radius: 14px;
    box-shadow: var(--schatten-hoch);
    border: 1px solid var(--rand);
    outline: none;
    animation: auf 0.14s ease-out;
  }
  .block:focus-within,
  .block:focus {
    border-color: #93c5fd;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px 10px 16px;
    border-bottom: 1px solid var(--rand);
    cursor: move;
    user-select: none;
    background: var(--flaeche-2);
    border-radius: 14px 14px 0 0;
  }
  .titel {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .chip {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--akzent-hell);
    color: #1e40af;
    font-weight: 600;
  }
  .zaehler {
    font-size: 12px;
    color: var(--text-3);
  }
  .knoepfe button {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 7px;
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
  }
  .knoepfe button:hover:not(:disabled) {
    background: var(--gruppe);
  }
  .knoepfe button:disabled {
    opacity: 0.3;
  }
  .inhalt {
    display: flex;
    gap: 18px;
    padding: 12px 16px 6px;
  }
  .spalte {
    flex: none;
  }
  .saeule {
    display: block;
    border: 1px solid var(--rand);
    border-radius: 4px;
    background: #fff;
  }
  .wert {
    font-size: 11px;
    font-weight: 700;
  }
  .leer {
    font-size: 11px;
    fill: var(--text-3);
  }
  .klein {
    font-size: 11.5px;
    color: var(--text-2);
    margin-bottom: 3px;
  }
  .gross {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 8px;
    font-variant-numeric: tabular-nums;
  }
  .mittel {
    font-size: 15px;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }
  .zahlen {
    flex: 1;
    min-width: 0;
  }
  .paar {
    display: flex;
    gap: 18px;
    margin-bottom: 8px;
  }
  .gruppe {
    font-size: 11.5px;
    font-weight: 700;
    color: var(--text-2);
    margin-top: 8px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .zeile {
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
    padding: 1px 0;
    font-variant-numeric: tabular-nums;
  }
  .zeile span:first-child {
    color: var(--text-2);
  }
  .legende {
    list-style: none;
    padding: 0;
    margin: 6px 0 0;
    font-size: 11.5px;
    max-width: 170px;
  }
  .legende li {
    display: flex;
    gap: 6px;
    align-items: flex-start;
    margin: 2px 0;
  }
  .legende i {
    flex: none;
    width: 11px;
    height: 11px;
    border-radius: 2px;
    margin-top: 2px;
  }
  footer {
    font-size: 11.5px;
    color: var(--text-3);
    padding: 4px 16px 12px;
  }
  @keyframes auf {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
  }
</style>
