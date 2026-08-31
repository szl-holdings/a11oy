// web/src/main.tsx — React entrypoint for the a11oy web app.
//
// Authored per founder reframe 2026-05-30 ~15:27 EDT (a11oy is the Warhacker focal
// demo target). web/index.html references /src/main.tsx but the file was absent;
// this mounts the existing <App/> so `vite build` produces web/dist.
//
// SPDX-License-Identifier: Apache-2.0
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error('a11oy: #root element not found in index.html');
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
