"""
VekSnap utility custom nodes for ComfyUI.

LICENSING (split by file, see LICENSE.md):
  * THIS FILE (__init__.py): original Vek-Snap work under **PolyForm
    Noncommercial 1.0.0**. Commercial use requires a separate license from
    Squishy Code AI LLC (legal@squishycode.ai). Contains:
      - the /api/reload-nodes hot-reload helper,
      - VekSnapColorMatch (per-channel histogram drift correction),
      - VekSnapAVNormSampler (LTX AV sampler with live video preview).
  * veksnap_nodes_gpl.py: VekSnapCleanVRAM, VekSnapAppendGuideLatent,
    VekSnapReferenceComposer under **GPL-3.0-or-later** (free for any use).

Copyright (c) 2025-2026 Squishy Code AI LLC. All rights reserved.
These nodes interface with ComfyUI through its public plugin/extension API and
are independent works; the PolyForm-licensed nodes are NOT distributed under
ComfyUI's GPL-3.0 license.
"""
import logging
import asyncio
import server
import nodes
import torch
import numpy as np

routes = server.PromptServer.instance.routes

@routes.get("/api/reload-nodes")
async def reload_nodes(request):
    """Re-scan custom_nodes/ and load any newly installed node packs."""
    from aiohttp import web
    import time

    before = set(nodes.NODE_CLASS_MAPPINGS.keys())
    t0 = time.perf_counter()

    try:
        await nodes.init_external_custom_nodes()
    except Exception as e:
        logging.error(f"Error reloading nodes: {e}")
        return web.json_response({"error": str(e)}, status=500)

    after = set(nodes.NODE_CLASS_MAPPINGS.keys())
    new_nodes = sorted(after - before)
    elapsed = time.perf_counter() - t0

    logging.info(f"Reload nodes: {len(new_nodes)} new nodes loaded in {elapsed:.1f}s")
    if new_nodes:
        logging.info(f"New nodes: {new_nodes}")

    return web.json_response({
        "success": True,
        "new_nodes": new_nodes,
        "total_nodes": len(after),
        "elapsed_seconds": round(elapsed, 2),
    })


# -- VekSnapColorMatch: Per-channel histogram matching --
# Corrects cumulative color drift in multi-segment video generation.
# Maps the color distribution of the input image to match a reference image
# WITHOUT transferring any spatial content (unlike ImageBlend which ghosts).
class VekSnapColorMatch:
    """Match the color histogram of an image to a reference.
    Designed to prevent runaway saturation/brightness drift when chaining
    video segments that each do a VAE decode->encode round-trip."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "reference": ("IMAGE",),
                "strength": ("FLOAT", {
                    "default": 0.15,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "0 = no correction, 0.10-0.20 = subtle drift fix, 1.0 = full histogram match"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "match_color"
    CATEGORY = "image/postprocessing"
    DESCRIPTION = "Per-channel histogram matching to correct cumulative color drift across video segments."

    def match_color(self, image, reference, strength):
        if strength <= 0.0:
            return (image,)

        result = image.clone()

        # Work on first frame of each (image may be a batch but reference is 1 frame)
        src = (image[0].cpu().numpy() * 255.0).astype(np.float64)
        ref = (reference[0].cpu().numpy() * 255.0).astype(np.float64)

        matched = np.zeros_like(src)
        channels = min(src.shape[2], ref.shape[2], 3)
        for c in range(channels):
            matched[:, :, c] = VekSnapColorMatch._match_channel(src[:, :, c], ref[:, :, c])

        matched_tensor = torch.from_numpy(matched / 255.0).float().to(image.device)

        # Blend: strength=1.0 -> full histogram match, strength=0.15 -> subtle correction
        result[0, :, :, :channels] = (
            image[0, :, :, :channels] * (1.0 - strength) +
            matched_tensor[:, :, :channels] * strength
        )
        result = torch.clamp(result, 0.0, 1.0)

        return (result,)

    @staticmethod
    def _match_channel(source, reference):
        """Map source channel values so its CDF matches the reference CDF."""
        src_vals, src_inv, src_counts = np.unique(
            source.ravel(), return_inverse=True, return_counts=True
        )
        ref_vals, ref_counts = np.unique(reference.ravel(), return_counts=True)

        # Build cumulative distribution functions
        src_cdf = np.cumsum(src_counts).astype(np.float64)
        src_cdf /= src_cdf[-1]
        ref_cdf = np.cumsum(ref_counts).astype(np.float64)
        ref_cdf /= ref_cdf[-1]

        # Map source CDF positions to reference values
        mapped = np.interp(src_cdf, ref_cdf, ref_vals)
        return mapped[src_inv].reshape(source.shape)


# -- VekSnapAVNormSampler: LTX AV Normalizing Sampler with live video preview --
# Drop-in replacement for LTXVNormalizingSampler.
# The original cannot emit previews because:
#   1. LTXAV format nulls out latent_rgb_factors -> no previewer is ever created
#   2. x0 in the callback is packed [B,1,N] (video+audio) -> standard decoders crash
# This node creates a previewer from the parent LTXV format (which has valid
# 128-channel -> RGB factors) and unpacks x0 to extract only the video tensor
# before generating preview frames.
class VekSnapAVNormSampler:
    """LTX AV Normalizing Sampler with live video preview.
    Drop-in replacement for LTXVNormalizingSampler that emits preview frames
    during sampling by unpacking the video latent from the combined AV tensor."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "noise": ("NOISE",),
                "guider": ("GUIDER",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "latent_image": ("LATENT",),
                "video_normalization_factors": ("STRING", {
                    "default": "1,1,1,1,1,1,1,1",
                }),
                "audio_normalization_factors": ("STRING", {
                    "default": "1,1,0.25,1,1,0.25,1,1",
                }),
            },
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("denoised_output",)
    FUNCTION = "execute"
    CATEGORY = "veksnap/sampling"
    DESCRIPTION = "LTX AV Normalizing Sampler with live video preview. Drop-in for LTXVNormalizingSampler."

    def execute(self, noise, guider, sampler, sigmas, latent_image,
                video_normalization_factors, audio_normalization_factors):
        import comfy.sample
        import comfy.model_management
        import comfy.utils
        import latent_preview
        from comfy.nested_tensor import NestedTensor
        from comfy.latent_formats import LTXV as LTXVFormat

        # Validate model type
        diff_model = guider.model_patcher.model.diffusion_model
        if diff_model.__class__.__name__ != "LTXAVModel":
            raise ValueError("VekSnapAVNormSampler requires LTXAVModel (LTX 2.3+)")
        ltxav = diff_model

        # Parse normalization factors
        vid_factors = [float(x) for x in video_normalization_factors.split(",")]
        aud_factors = [float(x) for x in audio_normalization_factors.split(",")]
        total_steps = len(sigmas) - 1

        # Extend factors to match total steps
        if vid_factors and len(vid_factors) < total_steps:
            vid_factors.extend([vid_factors[-1]] * (total_steps - len(vid_factors)))
        if aud_factors and len(aud_factors) < total_steps:
            aud_factors.extend([aud_factors[-1]] * (total_steps - len(aud_factors)))

        # Find split points where normalization != 1.0
        split_indices = [
            i + 1 for i, (v, a) in enumerate(zip(vid_factors, aud_factors))
            if v != 1.0 or a != 1.0
        ]
        print("[VekSnapAVNorm] Split indices: %s" % split_indices, flush=True)

        # Split sigmas into chunks at normalization points
        sigmas_chunks = VekSnapAVNormSampler._split_by_indices(sigmas, split_indices)
        print("[VekSnapAVNorm] Sigmas chunks: %s" % sigmas_chunks, flush=True)

        # --- Preview setup ---
        # LTXAV format nulls latent_rgb_factors; use parent LTXV format instead
        # which has valid 128-channel -> RGB projection weights.
        video_format = LTXVFormat()
        previewer = latent_preview.get_previewer(
            guider.model_patcher.load_device, video_format
        )

        # Latent shapes for unpacking x0 in the callback.
        # x0 arrives as packed [B, 1, video_elems + audio_elems]; we need the
        # individual tensor shapes to split it back into video [B,C,F,H,W].
        av_shapes = []  # mutable list for closure access
        if isinstance(latent_image["samples"], NestedTensor):
            av_shapes.extend([t.shape for t in latent_image["samples"].tensors])

        # Single progress bar spanning all chunks
        pbar = comfy.utils.ProgressBar(total_steps)
        global_step = [0]  # mutable for closure
        x0_store = {}

        def av_preview_callback(step, x0, x, chunk_total):
            """Per-step callback: unpack video from packed AV tensor for preview."""
            x0_store["x0"] = x0
            preview_bytes = None
            if previewer and av_shapes:
                try:
                    unpacked = comfy.utils.unpack_latents(x0, av_shapes)
                    video_x0 = unpacked[0]  # video: [B, C, F, H, W]
                    preview_bytes = previewer.decode_latent_to_preview_image(
                        "JPEG", video_x0
                    )
                except Exception:
                    pass
            current = global_step[0] + step + 1
            pbar.update_absolute(current, total_steps, preview_bytes)

        # --- Sampling loop (mirrors LTXVNormalizingSampler logic) ---
        i = 0
        for sigmas_chunk in sigmas_chunks:
            i += len(sigmas_chunk) - 1
            print("[VekSnapAVNorm] Sampling chunk: %s" % sigmas_chunk, flush=True)

            # Prepare latent (same steps as SamplerCustomAdvanced.execute)
            latent = latent_image.copy()
            lat = latent["samples"]
            lat = comfy.sample.fix_empty_latent_channels(
                guider.model_patcher, lat,
                latent.get("downscale_ratio_spacial")
            )
            latent["samples"] = lat
            noise_mask = latent.get("noise_mask")

            # Update av_shapes from the (possibly fixed) latent for accurate unpacking
            if isinstance(lat, NestedTensor):
                av_shapes.clear()
                av_shapes.extend([t.shape for t in lat.tensors])

            # Sample with our AV-aware preview callback
            x0_store.clear()
            samples = guider.sample(
                noise.generate_noise(latent),
                lat,
                sampler,
                sigmas_chunk,
                denoise_mask=noise_mask,
                callback=av_preview_callback,
                disable_pbar=True,
                seed=noise.seed,
            )
            samples = samples.to(comfy.model_management.intermediate_device())

            # Build denoised output (mirrors SamplerCustomAdvanced logic)
            if "x0" in x0_store:
                x0_out = guider.model_patcher.model.process_latent_out(
                    x0_store["x0"].cpu()
                )
                if hasattr(samples, "is_nested") and samples.is_nested:
                    shapes = [x.shape for x in samples.unbind()]
                    x0_out = NestedTensor(
                        comfy.utils.unpack_latents(x0_out, shapes)
                    )
                out = latent.copy()
                out["samples"] = x0_out
            else:
                out = latent.copy()
                out.pop("downscale_ratio_spacial", None)
                out["samples"] = samples

            latent_image = out
            global_step[0] = i

            # Apply normalization (same logic as LTXVNormalizingSampler)
            if isinstance(latent_image["samples"], NestedTensor):
                video_samples, audio_samples = ltxav.separate_audio_and_video_latents(
                    latent_image["samples"].tensors, None
                )
                if i - 1 < len(vid_factors) and i - 1 < len(aud_factors):
                    video_samples = video_samples * vid_factors[i - 1]
                    audio_samples = audio_samples * aud_factors[i - 1]
                    latent_image["samples"] = NestedTensor(
                        ltxav.recombine_audio_and_video_latents(
                            video_samples, audio_samples
                        )
                    )
                    print(
                        "[VekSnapAVNorm] After %d steps, normalized: video=%f audio=%f"
                        % (i, vid_factors[i - 1], aud_factors[i - 1]),
                        flush=True,
                    )

        return (latent_image,)

    @staticmethod
    def _split_by_indices(arr, indices):
        """Split array at specified indices (each index starts a new chunk)."""
        if not indices:
            return [arr]
        split_points = sorted(set(indices))
        chunks = []
        prev = 0
        for idx in split_points:
            if prev < idx:
                chunks.append(arr[prev : idx + 1])
            prev = idx
        if prev < len(arr):
            chunks.append(arr[prev:])
        return chunks




# --- PolyForm Noncommercial 1.0.0 nodes (defined above in this file) ---
NODE_CLASS_MAPPINGS = {
    "VekSnapColorMatch": VekSnapColorMatch,
    "VekSnapAVNormSampler": VekSnapAVNormSampler,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "VekSnapColorMatch": "VekSnap Color Match (Histogram)",
    "VekSnapAVNormSampler": "VekSnap AV Normalizing Sampler (Preview)",
}

# --- Merge in the GPL-3.0-or-later nodes (VekSnapCleanVRAM, VekSnapAppendGuideLatent,
# VekSnapReferenceComposer) from veksnap_nodes_gpl.py so ComfyUI registers all five
# nodes from this single package. See LICENSE.md for the per-file license split. ---
from .veksnap_nodes_gpl import (
    NODE_CLASS_MAPPINGS as _GPL_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as _GPL_DISPLAY_MAPPINGS,
)
NODE_CLASS_MAPPINGS.update(_GPL_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(_GPL_DISPLAY_MAPPINGS)
