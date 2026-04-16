import { resolve } from "path";
import { defineConfig } from "vite";

// datamaps pulls in d3 v3, whose top-level IIFE reads globals off `this`
// (this.document, this.navigator, etc.). Under ESM/strict `this` is undefined,
// crashing at load. Bind the IIFE's `this` to globalThis so those reads work.
//
// Datamaps itself also has a sloppy-mode bug: `hoverover = ...` is written in
// one function without ever being declared, relying on implicit global in
// non-strict mode. Under ESM/strict that throws ReferenceError. Hoist a
// declaration into the top-level IIFE so the bare assignment resolves.
const fixDatamapsStrictMode = {
  name: "fix-datamaps-strict-mode",
  transform(code, id) {
    if (id.includes("datamaps/node_modules/d3/d3.js")) {
      return code.replace(/\}\(\);\s*$/, "}.call(globalThis);\n");
    }
    if (id.match(/datamaps\/dist\/datamaps\.[^/]+\.js$/)) {
      return code.replace("var svg;", "var svg, hoverover;");
    }
  },
};

export default defineConfig({
  plugins: [fixDatamapsStrictMode],
  build: {
    outDir: resolve(__dirname, "status/static"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        base: resolve(__dirname, "status/static_src/index.js"),
        pages: resolve(__dirname, "pages/static_src/index.js"),
        properties: resolve(__dirname, "properties/static_src/index.js"),
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: (assetInfo) => {
          if (/\.(png|jpg|gif|svg|webp)$/.test(assetInfo.name)) {
            return "images/[name][extname]";
          }
          return "[name][extname]";
        },
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        quietDeps: true,
      },
    },
  },
});
