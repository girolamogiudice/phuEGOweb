import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

const entry = fileURLToPath(new URL("./src/main.js", import.meta.url));

export default defineConfig({
  root: "src",
  base: "/static/js/dist/",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    rollupOptions: {
      input: entry,
      output: {
        entryFileNames: "assets/main.js"
      }
    }
  }
});
