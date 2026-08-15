# veksnap_utils licensing

This ComfyUI custom-node package is authored by **Squishy Code AI LLC** and is
**split-licensed by file**. Read this before reusing any of it.

## PolyForm Noncommercial 1.0.0: `__init__.py`

The following are original Vek-Snap work and are licensed under
**PolyForm Noncommercial 1.0.0** (see `LICENSE-PolyForm-Noncommercial-1.0.0.txt`):

- **`VekSnapColorMatch`**: per-channel CDF histogram matching for cross-segment
  color-drift correction.
- **`VekSnapAVNormSampler`**: LTX AV normalizing sampler with live video preview
  (unpacks the packed video+audio latent and rebuilds a previewer from the parent
  LTXV latent format).
- the **`/api/reload-nodes`** hot-reload helper endpoint.

You may use, copy, modify, and share these **for any noncommercial purpose**.
**Commercial use requires a separate license** from Squishy Code AI LLC.
Contact **legal@squishycode.ai**.

These nodes interface with ComfyUI solely through its public plugin/extension
API (`NODE_CLASS_MAPPINGS`, the routes table, and documented `comfy.*` entry
points). They are independent works and are **not** distributed under ComfyUI's
GPL-3.0 license.

## GPL-3.0-or-later: `veksnap_nodes_gpl.py`

The following are released under the **GNU General Public License v3.0 or later**
(see `LICENSE-GPL-3.0.txt`) and are free for anyone to use, including
commercially, under the GPL's terms:

- **`VekSnapCleanVRAM`**: trivial `gc.collect()` + CUDA cache flush pass-through.
- **`VekSnapAppendGuideLatent`**: thin wrapper that delegates to ComfyUI's GPL
  `LTXVAddGuide` internals.
- **`VekSnapReferenceComposer`**: re-implements the public r2v
  `ReservedRegionFrameComposer` pattern.

## Why the split

We're happy to give the community working, genuinely useful free code (the GPL
file above). The PolyForm-Noncommercial file is our non-trivial original work; it
stays free for noncommercial use, but a commercial license is required so that it
isn't simply absorbed into a third party's paid product with no effort on their
part. The two files run side-by-side; ComfyUI loads all five nodes from this one
package via the merged mappings in `__init__.py`.
