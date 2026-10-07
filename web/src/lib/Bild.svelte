<script>
  // Trockenrohdichte ueber organischem Kohlenstoff - alle Proben auf
  // einmal. Die Geometrie rechnet Python (trdfbild.bild); hier wird nur
  // gezeichnet. Ein Klick auf einen Punkt oeffnet seinen Bodenblock.
  import Dialog from "./Dialog.svelte";
  let { bild, onProbe, onZu } = $props();
  let ueber = $state(null);
</script>

<Dialog
  titel="Trockenrohdichte über Kohlenstoff – Serie {bild.serie}"
  unter="{bild.anzahl} Proben · ein Klick auf einen Punkt öffnet seinen Bodenblock"
  breite="min(980px, 94vw)"
  {onZu}
>
  <svg viewBox="0 0 {bild.breite} {bild.hoehe}" class="bild" role="img" aria-label="Streubild">
    {#each bild.baender as b}
      <rect x={b.x} y={b.y} width={b.b} height={b.h} fill={b.farbe} />
    {/each}
    {#each bild.grenzen as x}
      <line x1={x} x2={x} y1={bild.oben} y2={bild.unten} stroke="#cbd5e1" />
    {/each}
    <line x1={bild.links} x2={bild.rechts} y1={bild.unten} y2={bild.unten} stroke="#94a3b8" />
    <line x1={bild.links} x2={bild.links} y1={bild.unten} y2={bild.oben} stroke="#94a3b8" />
    {#each bild.xmarken as m}
      <line x1={m.x} x2={m.x} y1={bild.unten} y2={bild.unten + 4} stroke="#94a3b8" />
      <text x={m.x} y={bild.unten + 16} text-anchor="middle" class="marke">{m.text}</text>
    {/each}
    {#each bild.ymarken as m}
      <line x1={bild.links - 4} x2={bild.links} y1={m.y} y2={m.y} stroke="#94a3b8" />
      <text x={bild.links - 7} y={m.y + 4} text-anchor="end" class="marke">{m.text}</text>
    {/each}
    <text x={bild.breite / 2} y={bild.unten + 34} text-anchor="middle" class="achse">organischer Kohlenstoff [g/kg]</text>
    <text x="14" y={(bild.unten + bild.oben) / 2} text-anchor="middle" class="achse"
      transform="rotate(-90 14 {(bild.unten + bild.oben) / 2})">Trockenrohdichte Feinboden [g/cm³]</text>
    {#each bild.punkte as p (p.probe)}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <circle
        cx={p.x} cy={p.y} r={ueber === p ? 6 : 4.2} fill={p.farbe}
        class="punkt"
        role="button"
        tabindex="-1"
        onmouseenter={() => (ueber = p)}
        onmouseleave={() => (ueber = null)}
        onclick={() => onProbe(p.probe)}
      />
    {/each}
    {#if ueber}
      <g transform="translate({Math.min(ueber.x + 10, bild.breite - 150)} {Math.max(ueber.y - 34, 4)})" pointer-events="none">
        <rect width="140" height="40" rx="6" fill="#0f172a" />
        <text x="10" y="17" class="tipp stark">{ueber.probe}</text>
        <text x="10" y="32" class="tipp">TRDF {ueber.trdf}{ueber.corg ? ` · Corg ${ueber.corg}` : ""}</text>
      </g>
    {/if}
  </svg>
  <div class="legende">
    <span><i style="background:#dbeafe"></i>Sollbereich ohne Carbonat</span>
    <span><i style="background:#eff6ff;border:1px solid #dbeafe"></i>mit Carbonat</span>
    <span><b style="background:#334155"></b>im Bereich</span>
    <span><b style="background:#b91c1c"></b>außerhalb</span>
    <span><b style="background:#7c3aed"></b>von Hand bewegt</span>
    <span><b style="background:#94a3b8"></b>ohne Aufschluss</span>
  </div>
  <div class="platz"></div>
</Dialog>

<style>
  .bild {
    width: 100%;
    height: auto;
    border: 1px solid var(--rand);
    border-radius: 10px;
    background: #fff;
  }
  .marke {
    font-size: 10px;
    fill: #64748b;
  }
  .achse {
    font-size: 11px;
    fill: #475569;
  }
  .punkt {
    cursor: pointer;
    stroke: #fff;
    stroke-width: 1;
    transition: r 0.1s;
  }
  .tipp {
    font-size: 11px;
    fill: #e2e8f0;
  }
  .tipp.stark {
    font-weight: 700;
    fill: #fff;
  }
  .legende {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-top: 10px;
    font-size: 12px;
    color: var(--text-2);
  }
  .legende i,
  .legende b {
    display: inline-block;
    width: 14px;
    height: 10px;
    margin-right: 6px;
    vertical-align: -1px;
  }
  .legende b {
    width: 10px;
    border-radius: 50%;
  }
  .platz {
    height: 18px;
  }
</style>
