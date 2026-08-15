"""
VekSnap utility nodes, GPL-3.0-or-later portion.

Copyright (c) 2025-2026 Squishy Code AI LLC.

These three helper nodes are DELIBERATELY released under the GNU General Public
License, version 3.0 or later (GPL-3.0-or-later):

  - VekSnapCleanVRAM         : trivial gc.collect() + CUDA cache flush pass-through.
  - VekSnapAppendGuideLatent : thin wrapper that delegates to ComfyUI's GPL
                               LTXVAddGuide internals (comfy_extras.nodes_lt).
  - VekSnapReferenceComposer : re-implements the public r2v
                               ReservedRegionFrameComposer pattern.

They are free for anyone to use, modify, and redistribute, including
commercially, under the terms of the GPL. See LICENSE-GPL-3.0.txt.

The genuinely original Vek-Snap work (VekSnapColorMatch, VekSnapAVNormSampler,
and the /api/reload-nodes helper) lives in __init__.py and is licensed under
PolyForm Noncommercial 1.0.0, NOT GPL. See LICENSE.md for the full rationale.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details.
"""
import torch


class _AnyType(str):
    """Matches any ComfyUI type for pass-through connections."""
    def __eq__(self, _):
        return True
    def __ne__(self, _):
        return False

_ANY = _AnyType("*")


class VekSnapCleanVRAM:
    """
    Lightweight VRAM cleanup node.  Pass-through that triggers garbage collection
    and CUDA cache flush between pipeline phases (e.g. after VAE encoding, before
    sampling).  Mirrors the role of ``easy cleanGpuUsed`` from comfyui-easy-use
    without requiring that large dependency.  Zero external deps, zero network calls.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "anything": (_ANY, {}),
            },
        }

    RETURN_TYPES = (_ANY,)
    RETURN_NAMES = ("output",)
    FUNCTION = "execute"
    CATEGORY = "veksnap/utils"
    DESCRIPTION = "Flush VRAM between pipeline phases. Pass-through - connect inline."

    def execute(self, anything=None):
        import gc
        import comfy.model_management
        gc.collect()
        comfy.model_management.soft_empty_cache()
        return (anything,)


class VekSnapAppendGuideLatent:
    """
    Append a pre-encoded VAE latent as a guide to an LTX video latent.
    Replicates the conditioning logic of LTXVAddGuide.append_keyframe /
    add_keyframe_index without re-encoding, so the heavy VAE encode can
    be done upstream with VAEEncodeTiled (which supports temporal tiling
    and is VRAM-safe for long video sequences at high resolution).

    Inputs
    ------
    positive / negative : conditioning with optional prior keyframe_idxs
    vae                 : needed only for scale_factors (downscale_index_formula)
    latent              : base video latent (from EmptyLTXVLatentVideo or prior guides)
    guide_latent        : pre-encoded guide (from VAEEncodeTiled)
    frame_idx           : pixel-space frame index where the guide starts (usually 0)
    strength            : guide strength (0 = ignore guide, 1 = full replacement)
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "vae": ("VAE",),
                "latent": ("LATENT",),
                "guide_latent": ("LATENT",),
                "frame_idx": ("INT", {"default": 0, "min": -9999, "max": 9999}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "negative", "latent")
    FUNCTION = "execute"
    CATEGORY = "veksnap/utils"
    DESCRIPTION = "Append a pre-encoded guide latent to LTX video conditioning. Use VAEEncodeTiled upstream for VRAM-safe temporal+spatial tiling."

    def execute(self, positive, negative, vae, latent, guide_latent, frame_idx=0, strength=1.0):
        from comfy_extras.nodes_lt import LTXVAddGuide, get_noise_mask

        scale_factors = vae.downscale_index_formula
        time_scale_factor = scale_factors[0]

        latent_image = latent["samples"]
        noise_mask = get_noise_mask(latent)
        guide = guide_latent["samples"]

        _, _, latent_length, _, _ = latent_image.shape

        # SetLatentNoiseMask stores mask as 4D (B, 1, H, W) but append_keyframe
        # expects 5D (B, 1, T, H, W). Reshape and broadcast across temporal frames.
        if noise_mask.dim() == 4:
            noise_mask = noise_mask.unsqueeze(2).expand(-1, -1, latent_length, -1, -1)

        # Recover the pixel-frame count so get_latent_index can validate
        guide_pixel_frames = (guide.shape[2] - 1) * time_scale_factor + 1

        frame_idx_resolved, latent_idx = LTXVAddGuide.get_latent_index(
            positive, latent_length, guide_pixel_frames, frame_idx, scale_factors
        )

        positive, negative, latent_image, noise_mask = LTXVAddGuide.append_keyframe(
            positive, negative, frame_idx_resolved,
            latent_image, noise_mask,
            guide, strength, scale_factors,
        )

        return (positive, negative, {"samples": latent_image, "noise_mask": noise_mask})


class VekSnapReferenceComposer:
    """Composite reference image(s) into a reserved strip on each video frame.

    Matches the ReservedRegionFrameComposer pattern used in Alissonerdx r2v LoRA
    training.  The reference subject is scaled (preserving AR) to fit within a
    vertical strip of configurable width on the left or right edge of every frame.
    The strip background is filled with mid-gray (#808080) - neutral in LTX
    latent space - before the reference is centered within it.

    When multiple references are provided (batch dim > 1), they cycle through
    frames at the specified interval.

    Inputs
    ------
    frames    : VIDEO frame batch [B, H, W, C]
    reference : Reference image(s) [N, H, W, C]  (N = 1)
    strip_width : Pixel width of the reserved strip (default 256)
    position    : "left" or "right"
    interval    : Place a reference every N frames (1 = every frame)
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "frames": ("IMAGE",),
                "reference": ("IMAGE",),
                "strip_width": ("INT", {"default": 256, "min": 32, "max": 1024, "step": 8}),
                "position": (["left", "right"], {"default": "left"}),
                "interval": ("INT", {"default": 1, "min": 1, "max": 120}),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("frames", "strip_width")
    FUNCTION = "execute"
    CATEGORY = "veksnap/utils"
    DESCRIPTION = (
        "Composite reference image(s) into a reserved strip on video frames. "
        "Matches the r2v LoRA training pattern (ReservedRegionFrameComposer). "
        "Returns modified frames + the strip_width for downstream cropping."
    )

    def execute(self, frames, reference, strip_width=256, position="left", interval=1):
        import torch.nn.functional as F

        B, H, W, C = frames.shape
        N_ref = reference.shape[0]
        device = frames.device
        dtype = frames.dtype

        # Clamp strip_width to frame width
        strip_width = min(strip_width, W // 2)

        result = frames.clone()

        for i in range(B):
            if interval > 1 and (i % interval) != 0:
                # Non-reference frame: fill strip with mid-gray (neutral)
                if position == "left":
                    result[i, :, :strip_width, :] = 0.5
                else:
                    result[i, :, W - strip_width:, :] = 0.5
                continue

            # Pick which reference to use (cycle through)
            ref_idx = (i // max(interval, 1)) % N_ref
            ref = reference[ref_idx]  # [H_ref, W_ref, C]

            # Scale reference to fit strip: height=H, width=strip_width, contain mode
            ref_h, ref_w = ref.shape[0], ref.shape[1]
            scale = min(strip_width / ref_w, H / ref_h)
            new_w = max(1, int(ref_w * scale))
            new_h = max(1, int(ref_h * scale))

            # Resize via interpolate (CHW format required)
            ref_chw = ref.permute(2, 0, 1).unsqueeze(0).float()  # [1, C, H, W]
            ref_resized = F.interpolate(ref_chw, size=(new_h, new_w), mode="bilinear", align_corners=False)
            ref_resized = ref_resized.squeeze(0).permute(1, 2, 0).to(dtype=dtype)  # [new_h, new_w, C]

            # Create strip canvas (mid-gray background)
            strip = torch.full((H, strip_width, C), 0.5, dtype=dtype, device=device)
            y_off = (H - new_h) // 2
            x_off = (strip_width - new_w) // 2
            strip[y_off:y_off + new_h, x_off:x_off + new_w] = ref_resized

            # Paste into frame
            if position == "left":
                result[i, :, :strip_width, :] = strip
            else:
                result[i, :, W - strip_width:, :] = strip

        return (result, strip_width)


NODE_CLASS_MAPPINGS = {
    "VekSnapCleanVRAM": VekSnapCleanVRAM,
    "VekSnapAppendGuideLatent": VekSnapAppendGuideLatent,
    "VekSnapReferenceComposer": VekSnapReferenceComposer,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "VekSnapCleanVRAM": "VekSnap Clean VRAM (Flush)",
    "VekSnapAppendGuideLatent": "VekSnap Append Guide Latent (Tiled)",
    "VekSnapReferenceComposer": "VekSnap Reference Composer (r2v Strip)",
}
