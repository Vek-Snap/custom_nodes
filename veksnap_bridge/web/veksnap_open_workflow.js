/*
 * Vek-Snap "Open in ComfyUI" bridge extension.
 *
 * Copyright (C) Squishy Code AI LLC.
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This single front-end glue file is the ONLY part of veksnap_bridge that uses
 * the ComfyUI front-end API (app.loadApiJson, etc.). It is therefore licensed
 * under the GNU General Public License v3.0 or later, matching ComfyUI, and is
 * deliberately isolated from Vek-Snap's proprietary code. It contains no
 * Vek-Snap proprietary logic. See ../LICENSE.md.
 *
 * When ComfyUI is opened with ?veksnap_open=...&veksnap_src=<app-origin>, fetch
 * the workflow the Vek-Snap app staged (from the APP's relay, NOT ComfyUI) and
 * load it directly into the canvas.
 */
import { app } from "../../scripts/app.js";

app.registerExtension({
  name: "VekSnap.OpenWorkflow",
  async setup() {
    let params;
    try {
      params = new URLSearchParams(window.location.search);
    } catch (e) {
      return;
    }
    if (!params.has("veksnap_open")) return;

    const src = params.get("veksnap_src");

    // Strip our flags right away so a manual refresh won't try to reload them.
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete("veksnap_open");
      url.searchParams.delete("veksnap_src");
      window.history.replaceState({}, "", url.toString());
    } catch (e) { /* ignore */ }

    if (!src) {
      console.warn("[VekSnap] No app origin (veksnap_src) provided; cannot fetch workflow.");
      return;
    }

    let data;
    try {
      // Fetch from the Vek-Snap APP relay (cross-origin; the app allows loopback
      // origins via CORS). We never send credentials.
      const res = await fetch(`${src}/api/veksnap-bridge/open-workflow`, {
        method: "GET",
        credentials: "omit",
      });
      if (!res.ok) {
        console.warn("[VekSnap] bridge fetch failed:", res.status);
        return;
      }
      data = await res.json();
    } catch (e) {
      console.error("[VekSnap] bridge fetch error:", e);
      return;
    }

    const workflow = data && data.workflow;
    if (!workflow) {
      console.warn("[VekSnap] No pending workflow to open.");
      return;
    }
    const name = (data && data.name) || "Vek-Snap Workflow";

    // Defer a tick so node definitions + canvas are fully ready.
    setTimeout(() => {
      try {
        const isApi =
          typeof app.isApiJson === "function" ? app.isApiJson(workflow) : true;
        if (isApi) {
          // API/prompt format -> rebuild graph + auto-arrange.
          app.loadApiJson(workflow, name);
        } else {
          // Full UI (litegraph) format -> load as-is.
          app.loadGraphData(workflow);
        }
        console.log("[VekSnap] Opened workflow in ComfyUI:", name);
      } catch (e) {
        console.error("[VekSnap] Failed to load workflow:", e);
      }
    }, 300);
  },
});
