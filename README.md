# Vek-Snap ComfyUI Nodes

Companion ComfyUI custom nodes used by [Vek-Snap](https://squishycode.ai), a local,
offline creative AI suite for Windows. Two small packages live here:

- **`veksnap_bridge`**: a web-only extension that lets the Vek-Snap app open your
  current studio workflow directly in the local ComfyUI canvas.
- **`veksnap_utils`**: five utility nodes for color correction, LTX AV sampling with
  live preview, VRAM cleanup, guide-latent composition, and reference compositing.

> Made by Squishy Code AI LLC. https://squishycode.ai

These nodes ship bundled with the Vek-Snap Guided Installer. This repository is the
source for anyone running their own ComfyUI who wants the same helpers, and to satisfy
the source-availability terms of the GPL-licensed files.

## Nodes

### veksnap_utils
| Node | Purpose | License |
| --- | --- | --- |
| VekSnap Color Match (Histogram) | Per-channel CDF histogram matching that corrects cumulative color drift when chaining video segments, without transferring spatial content. | PolyForm Noncommercial 1.0.0 |
| VekSnap AV Normalizing Sampler (Preview) | Drop-in replacement for LTXVNormalizingSampler that emits live preview frames by unpacking the video latent from the combined audio+video tensor. Requires LTXAVModel (LTX 2.3+). | PolyForm Noncommercial 1.0.0 |
| VekSnap Clean VRAM (Flush) | Pass-through that triggers garbage collection and a CUDA cache flush between pipeline phases. Zero external deps, zero network. | GPL-3.0-or-later |
| VekSnap Append Guide Latent (Tiled) | Thin wrapper that delegates to ComfyUI's LTXVAddGuide internals; pair with VAEEncodeTiled upstream for VRAM-safe tiling. | GPL-3.0-or-later |
| VekSnap Reference Composer (r2v Strip) | Reserved-region frame composer for reference-guided generation. | GPL-3.0-or-later |

A `/api/reload-nodes` helper endpoint (hot-reload of newly installed node packs) is also
registered by `veksnap_utils`.

### veksnap_bridge
`veksnap_bridge` is a data-only Python package: it declares `WEB_DIRECTORY` so ComfyUI
serves the front-end glue in `web/`, and imports nothing from ComfyUI. The workflow relay
lives inside the Vek-Snap app (at `/api/veksnap-bridge/open-workflow`), not in ComfyUI.
The single front-end file, `web/veksnap_open_workflow.js`, uses the ComfyUI front-end API
and is licensed GPL-3.0-or-later to match ComfyUI.

## Install

Requires a working [ComfyUI](https://github.com/comfyanonymous/ComfyUI). The AV sampler
additionally requires an LTXAVModel (LTX 2.3 or newer).

```
# Clone this repo to a clear folder (avoids nesting it inside ComfyUI/custom_nodes):
git clone https://github.com/Vek-Snap/custom_nodes.git veksnap-nodes

# Copy (or symlink) the two packages into your ComfyUI/custom_nodes, then restart ComfyUI:
#   veksnap-nodes/veksnap_bridge  ->  ComfyUI/custom_nodes/veksnap_bridge
#   veksnap-nodes/veksnap_utils   ->  ComfyUI/custom_nodes/veksnap_utils
```

Restart ComfyUI. The new nodes appear under the `veksnap/...`, `image/postprocessing`,
and related categories. If you use the Vek-Snap Guided Installer, these are provisioned
for you and you do not need this repository.

## Licensing

This repository is **split-licensed by file** to keep GPL copyleft cleanly separated from
Vek-Snap's proprietary work. Read each package's `LICENSE.md` before reusing anything.

- **GPL-3.0-or-later** (free for any use, including commercial):
  `veksnap_bridge/web/veksnap_open_workflow.js`, and in `veksnap_utils`:
  `veksnap_nodes_gpl.py` (VekSnapCleanVRAM, VekSnapAppendGuideLatent, VekSnapReferenceComposer).
- **PolyForm Noncommercial 1.0.0** (free for noncommercial use; commercial use requires a
  separate license from Squishy Code AI LLC): `veksnap_utils/__init__.py`
  (VekSnapColorMatch, VekSnapAVNormSampler, and the `/api/reload-nodes` helper).

The full license texts are in `veksnap_utils/LICENSE-GPL-3.0.txt` and
`veksnap_utils/LICENSE-PolyForm-Noncommercial-1.0.0.txt`.

## Support

- Website: https://squishycode.ai
- Contact: contact@squishycode.ai
