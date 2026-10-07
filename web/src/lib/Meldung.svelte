<script>
  import Dialog from "./Dialog.svelte";
  let { meldung, onZu } = $props();
  const symbol = { info: "✓", warn: "!", fehler: "✕" };
</script>

<Dialog titel={meldung.titel} breite="560px" {onZu}>
  <div class="meldung {meldung.art}">
    <span class="symbol">{symbol[meldung.art] ?? "i"}</span>
    <p>{meldung.text}</p>
  </div>
  {#snippet fuss()}
    <button class="knopf primaer" onclick={onZu} type="button">OK</button>
  {/snippet}
</Dialog>

<style>
  .meldung {
    display: flex;
    gap: 14px;
    align-items: flex-start;
  }
  .symbol {
    flex: none;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-weight: 700;
    background: var(--gruen-hell);
    color: var(--gruen);
  }
  .warn .symbol {
    background: var(--amber-hell);
    color: var(--amber);
  }
  .fehler .symbol {
    background: var(--rot-hell);
    color: var(--rot);
  }
  p {
    margin: 6px 0 0;
    white-space: pre-wrap;
    line-height: 1.55;
    word-break: break-word;
  }
</style>
