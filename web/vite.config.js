import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { viteSingleFile } from "vite-plugin-singlefile";

// Eine einzige index.html mit allem darin: pywebview laedt sie als Datei,
// ohne Server und ohne Nachladen - das ist der schnellste Start.
export default defineConfig({
  plugins: [svelte(), viteSingleFile()],
  base: "./",
  build: {
    outDir: "../webdist",
    emptyOutDir: true,
    target: "es2022",
    reportCompressedSize: false,
  },
  server: {
    port: 5173,
    // Im Entwicklungsbetrieb beantwortet `python trdfweb.py --dienst`
    // die Aufrufe der Seite.
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
});
