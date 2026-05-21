"""OpenCLIP-based per-frame scene/context features.

We compute two things per frame:

1. ``embedding``   -- raw image embedding (L2-normalized), float32, ~512-D.
2. ``prompt_sim``  -- cosine similarity of the embedding against a fixed bag
                      of natural-language prompts. The order of prompts is
                      preserved (it defines feature columns downstream).

Heavy torch / open_clip imports are deferred so importing this module never
fails at FastAPI startup, even on machines where torch isn't installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np

from ..utils.logging import get_logger

log = get_logger("roomos.features.clip")


@dataclass
class ClipFrameFeatures:
    embedding: np.ndarray         # (E,) float32
    prompt_sim: np.ndarray        # (P,) float32, cosine similarity per prompt
    prompt_labels: List[str]


class ClipExtractor:
    """Wraps an OpenCLIP model + tokenizer + transform.

    Use as a context manager or just call :meth:`extract` directly. The model
    is loaded lazily on first use.
    """

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: str = "auto",
        prompts: Optional[Sequence[str]] = None,
        keep_embedding: bool = True,
    ) -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        self.device_pref = device
        self.prompts: List[str] = list(prompts or [])
        self.keep_embedding = bool(keep_embedding)

        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._text_features = None
        self._device: Optional[str] = None

    # --- lifecycle -----------------------------------------------------

    def _resolve_device(self) -> str:
        if self.device_pref != "auto":
            return self.device_pref
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    def load(self) -> None:
        if self._model is not None:
            return
        import open_clip
        import torch

        device = self._resolve_device()
        log.info("Loading OpenCLIP %s/%s on %s", self.model_name, self.pretrained, device)
        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name,
            pretrained=self.pretrained,
            device=device,
        )
        model.eval()
        tokenizer = open_clip.get_tokenizer(self.model_name)

        text_features = None
        if self.prompts:
            with torch.no_grad():
                tokens = tokenizer(list(self.prompts)).to(device)
                tf = model.encode_text(tokens)
                tf = tf / (tf.norm(dim=-1, keepdim=True) + 1e-8)
                text_features = tf.detach()

        self._model = model
        self._preprocess = preprocess
        self._tokenizer = tokenizer
        self._text_features = text_features
        self._device = device

    def close(self) -> None:
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._text_features = None

    def __enter__(self) -> "ClipExtractor":
        self.load()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- feature extraction --------------------------------------------

    def extract(self, image_bgr: np.ndarray) -> ClipFrameFeatures:
        """Run CLIP on a single BGR image."""
        if self._model is None:
            self.load()
        assert self._model is not None
        import torch
        from PIL import Image

        rgb = image_bgr[:, :, ::-1]  # BGR -> RGB
        pil = Image.fromarray(rgb)
        with torch.no_grad():
            x = self._preprocess(pil).unsqueeze(0).to(self._device)  # type: ignore[misc]
            emb = self._model.encode_image(x)
            emb = emb / (emb.norm(dim=-1, keepdim=True) + 1e-8)

            if self._text_features is not None:
                sims = (emb @ self._text_features.T).squeeze(0)
                prompt_sim = sims.detach().cpu().numpy().astype(np.float32)
            else:
                prompt_sim = np.zeros((0,), dtype=np.float32)

            embedding = emb.squeeze(0).detach().cpu().numpy().astype(np.float32)

        if not self.keep_embedding:
            embedding = np.zeros((0,), dtype=np.float32)

        return ClipFrameFeatures(
            embedding=embedding,
            prompt_sim=prompt_sim,
            prompt_labels=list(self.prompts),
        )
