// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
// Authored for SZL Holdings. Signed-off per repository DCO.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";

const el = document.getElementById("root");
if (el) createRoot(el).render(<StrictMode><App /></StrictMode>);
