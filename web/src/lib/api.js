// Die Bruecke zu Python.
//
// Im Programm ruft die Seite ueber pywebview: window.pywebview.api.<name>.
// Im Browser (Entwicklung, Bilder der Anleitung) geht derselbe Aufruf als
// POST /api/<name> an `python trdfweb.py --dienst`.

let bereit = null;

function pywebviewBereit() {
  if (bereit) return bereit;
  bereit = new Promise((fertig) => {
    if (window.pywebview?.api) return fertig("pywebview");
    if (location.protocol.startsWith("http")) {
      // Im Browser gibt es keine Bruecke - sofort ueber HTTP.
      return fertig("http");
    }
    window.addEventListener("pywebviewready", () => fertig("pywebview"), {
      once: true,
    });
  });
  return bereit;
}

export async function rufe(name, ...argumente) {
  const weg = await pywebviewBereit();
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
