// Die Bruecke zu Python.
//
// Im Programm ruft die Seite ueber pywebview: window.pywebview.api.<name>.
// pywebview liefert die Seite dabei selbst ueber einen kleinen HTTP-Server
// aus - "http:" heisst also nicht "Browser". Ueber HTTP (POST /api/<name>)
// geht es nur, wenn sich der Entwicklungsdienst (`python trdfweb.py
// --dienst`) unter /api/bereit meldet.

let bereit = null;

function bruecke() {
  return window.pywebview?.api && typeof window.pywebview.api.start === "function";
}

async function dienstDa() {
  try {
    const r = await fetch("/api/bereit", { cache: "no-store" });
    if (!r.ok) return false;
    return (await r.json())?.dienst === true;
  } catch {
    return false;
  }
}

function wegFinden() {
  if (bereit) return bereit;
  bereit = new Promise((fertig) => {
    if (bruecke()) return fertig("pywebview");
    let erledigt = false;
    const nimm = (weg) => {
      if (!erledigt) {
        erledigt = true;
        fertig(weg);
      }
    };
    window.addEventListener("pywebviewready", () => nimm("pywebview"), { once: true });
    // Falls das Ereignis vor dem Lauschen kam: nachsehen.
    const pruefen = setInterval(() => {
      if (bruecke()) {
        clearInterval(pruefen);
        nimm("pywebview");
      }
    }, 50);
    if (location.protocol.startsWith("http")) {
      dienstDa().then((da) => {
        if (da) {
          clearInterval(pruefen);
          nimm("http");
        }
      });
    }
  });
  return bereit;
}

export async function rufe(name, ...argumente) {
  const weg = await wegFinden();
  let antwort;
  if (weg === "pywebview") {
    antwort = await window.pywebview.api[name](...argumente);
  } else {
    const r = await fetch(`/api/${name}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(argumente),
    });
    if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
    antwort = await r.json();
  }
  return antwort ?? {};
}
