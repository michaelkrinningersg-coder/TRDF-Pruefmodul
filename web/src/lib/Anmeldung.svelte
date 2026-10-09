<script>
  // Anmeldung wie in LabControl: Oracle-Benutzer, Passwort, Datenbank -
  // und die Datenbank ist LIMS. Das Passwort wird nirgends gespeichert.
  import { onMount, untrack } from "svelte";
  let { start, onAnmelden } = $props();
  const anfang = untrack(() => start);
  let benutzer = $state(anfang.benutzer ?? "");
  let passwort = $state("");
  let datenbank = $state(anfang.datenbanken?.[0] ?? "LIMS");
  let fehler = $state("");
  let arbeitet = $state(false);
  let feldBenutzer = $state(null);
  let feldPasswort = $state(null);

  // Nur einmal beim Oeffnen: mit gemerktem Benutzer ins Passwort, sonst
  // in den Benutzer. Ein $effect, der `benutzer` liest, liefe bei jedem
  // Tastendruck wieder - und sprang mitten im Namen ins Passwortfeld.
  onMount(() => {
    (anfang.benutzer ? feldPasswort : feldBenutzer)?.focus();
  });

  async function anmelden(e) {
    e.preventDefault();
    fehler = "";
    arbeitet = true;
    try {
      const antwort = await onAnmelden(benutzer, passwort, datenbank);
      if (!antwort.ok) fehler = antwort.fehler ?? "Anmeldung fehlgeschlagen.";
    } catch (f) {
      fehler = String(f);
    } finally {
      arbeitet = false;
      passwort = fehler ? "" : passwort;
    }
  }
</script>

<div class="flaeche">
  <form class="karte" onsubmit={anmelden}>
    <div class="marke">
      <div class="logo">
        <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
          <rect x="4" y="18" width="24" height="9" rx="2" fill="#d2b48c" />
          <rect x="4" y="11" width="24" height="7" rx="2" fill="#5b3a1e" />
          <rect x="4" y="5" width="24" height="6" rx="2" fill="#4b5563" />
        </svg>
      </div>
      <div>
        <h1>{start.titel}</h1>
        <p>Die Rechnung des LIMS nachrechnen und prüfen</p>
      </div>
    </div>

    <label>
      <span class="beschriftung">Oracle-Benutzer</span>
      <input class="feld" bind:this={feldBenutzer} bind:value={benutzer} autocomplete="username" placeholder="in der Regel der Nachname" />
    </label>
    <label>
      <span class="beschriftung">Passwort</span>
      <input class="feld" type="password" bind:this={feldPasswort} bind:value={passwort} autocomplete="current-password" />
    </label>
    <label>
      <span class="beschriftung">Datenbank</span>
      <select class="feld" bind:value={datenbank}>
        {#each start.datenbanken as name}<option>{name}</option>{/each}
      </select>
    </label>

    {#if fehler}
      <div class="fehler">{fehler}</div>
    {/if}

    <button class="knopf primaer gross" type="submit" disabled={arbeitet || !benutzer.trim() || !passwort}>
      {arbeitet ? "Verbinde …" : "Anmelden"}
    </button>

    <div class="tns {start.tnsnames?.art}">{start.tnsnames?.text}</div>
    {#if start.demo}
      <div class="demo">Demo-Betrieb: erfundene Serie, es wird nichts in eine Datenbank geschrieben.</div>
    {/if}
    <div class="version">{start.version} · NW-FVA</div>
  </form>
</div>

<style>
  .flaeche {
    height: 100%;
    display: grid;
    place-items: center;
    background:
      radial-gradient(1200px 600px at 10% -10%, #dbeafe 0%, transparent 60%),
      radial-gradient(900px 500px at 110% 110%, #e0e7ff 0%, transparent 55%),
      var(--bg);
  }
  .karte {
    width: 420px;
    padding: 30px 32px 22px;
    background: var(--flaeche);
    border-radius: 18px;
    box-shadow: var(--schatten-hoch);
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .marke {
    display: flex;
    gap: 14px;
    align-items: center;
    margin-bottom: 8px;
  }
  .logo {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: var(--flaeche-2);
    border: 1px solid var(--rand);
    display: grid;
    place-items: center;
  }
  h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
  }
  .marke p {
    margin: 2px 0 0;
    font-size: 13px;
    color: var(--text-2);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .feld {
    height: 40px;
  }
  .gross {
    height: 42px;
    justify-content: center;
    margin-top: 6px;
    font-size: 15px;
  }
  .fehler {
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--rot-zart);
    color: #991b1b;
    font-size: 13px;
    white-space: pre-wrap;
  }
  .tns {
    font-size: 11.5px;
    color: var(--text-3);
    word-break: break-all;
  }
  .tns.fehler {
    padding: 0;
    background: none;
    color: var(--rot);
  }
  .demo {
    font-size: 12px;
    color: var(--amber);
  }
  .version {
    font-size: 11.5px;
    color: var(--text-3);
    text-align: right;
  }
</style>
