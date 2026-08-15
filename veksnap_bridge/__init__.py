"""
Vek-Snap ComfyUI Bridge (web extension only)
--------------------------------------------
Lets the Vek-Snap app open the user's CURRENT studio workflow directly in the
local ComfyUI canvas (no clipboard paste, no default-workflow detour).

GPL note: this Python package imports NOTHING from ComfyUI and registers no
server routes. It only declares WEB_DIRECTORY so ComfyUI serves the front-end
glue in ./web. Declaring a data attribute that ComfyUI reads is not a derivative
work of ComfyUI, so no copyleft obligation attaches to this file. The workflow
relay lives in the Vek-Snap app, not in ComfyUI. See ./LICENSE.md.

How it works:
  1. The app POSTs the active workflow (ComfyUI API/prompt format) to its OWN
     route, /api/veksnap-bridge/open-workflow, which stashes it in a one-shot
     in-memory slot inside the Vek-Snap app process (not ComfyUI).
  2. The app opens ComfyUI at
     http://127.0.0.1:8188/?veksnap_open=1&veksnap_src=<app-origin>
  3. The web extension (web/veksnap_open_workflow.js, GPL-3.0) detects the flag,
     GETs the stashed workflow from <app-origin> (cross-origin, CORS-allowed),
     and loads it via app.loadApiJson(). The slot is cleared on read.
"""

# Data-only hook: ComfyUI reads WEB_DIRECTORY to serve ./web. No imports, no
# routes, no ComfyUI linkage.
WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
