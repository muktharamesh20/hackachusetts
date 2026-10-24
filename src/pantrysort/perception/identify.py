"""Identify scene items by fusing QR reads from several cameras.

Each camera renders a frame; every QR in it is decoded and back-projected
through that camera's depth to a world point. Each world point is matched to the
nearest known item (within a tolerance, for robustness to small reprojection
error), and reads are fused across cameras by majority vote so a single bad
read cannot mislabel an item.

The result is a mapping ``item_label -> IdentifiedItem`` carrying the decoded
PantrySort payload, the fused world position, and which cameras agreed. The sort
loop uses this instead of a single-frame scan, so each physical item gets the QR
that is actually on it.

Pure-python matching/fusion (no pydrake); the Drake frames come in via a small
``CameraView`` the station fills.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from pantrysort.perception.qr import decode_qr_codes


@dataclass
class CameraView:
    """One camera's contribution: its name plus a function to back-project a
    pixel to a world point (``locate(u, v) -> np.ndarray | None``) and the RGBA
    frame to decode."""

    name: str
    image: np.ndarray
    locate: object  # Callable[[float, float], np.ndarray | None]
    watch: object = None            # world point this camera is meant to watch (or None)
    watch_radius: float = 0.25      # meters


@dataclass
class QrWorldHit:
    """A decoded QR placed in the world by one camera."""

    text: str
    world: np.ndarray
    camera: str
    corners: np.ndarray


@dataclass
class IdentifiedItem:
    """Fused identification for one scene item."""

    label: str
    text: str                       # the winning QR payload text
    position: np.ndarray            # item's known world position
    observed: np.ndarray            # fused back-projected QR world point
    cameras: tuple[str, ...]        # cameras that agreed on ``text``
    votes: int
    total_reads: int

    @property
    def confidence(self) -> float:
        """Fraction of reads for this item that agreed on the winning payload."""
        return self.votes / self.total_reads if self.total_reads else 0.0


def back_project_hits(views: list[CameraView]) -> list[QrWorldHit]:
    """Decode every QR in every view and back-project each to a world point."""
    hits: list[QrWorldHit] = []
    for view in views:
        for qr in decode_qr_codes(view.image):
            u, v = qr.center_px
            p = view.locate(u, v)
            if p is None:
                continue
            p = np.asarray(p, dtype=float)
            if view.watch is not None:
                if np.linalg.norm(p - np.asarray(view.watch, dtype=float)) > view.watch_radius:
                    continue  # QR is outside what this camera is meant to watch
            hits.append(QrWorldHit(text=qr.text, world=p,
                                   camera=view.name, corners=qr.corners))
    return hits


def match_hits_to_items(
    hits: list[QrWorldHit],
    item_positions: dict[str, np.ndarray],
    max_dist: float = 0.06,
) -> dict[str, IdentifiedItem]:
    """Assign each QR world hit to the nearest item within ``max_dist`` (m), then
    fuse by majority vote across cameras.

    ``max_dist`` gives robustness to small back-projection error (a hit near an
    item still binds to it). If two items are closer than ``max_dist`` a hit goes
    to the nearest, so keep item spacing >= that in the scene.
    """
    # label -> list of (text, world, camera)
    grouped: dict[str, list[QrWorldHit]] = {label: [] for label in item_positions}
    for hit in hits:
        best_label, best_d = None, max_dist
        for label, pos in item_positions.items():
            d = float(np.linalg.norm(hit.world - np.asarray(pos, dtype=float)))
            if d <= best_d:
                best_label, best_d = label, d
        if best_label is not None:
            grouped[best_label].append(hit)

    identified: dict[str, IdentifiedItem] = {}
    for label, group in grouped.items():
        if not group:
            continue
        votes = Counter(h.text for h in group)
        text, n = votes.most_common(1)[0]
        winners = [h for h in group if h.text == text]
        observed = np.mean([h.world for h in winners], axis=0)
        identified[label] = IdentifiedItem(
            label=label,
            text=text,
            position=np.asarray(item_positions[label], dtype=float),
            observed=observed,
            cameras=tuple(sorted({h.camera for h in winners})),
            votes=n,
            total_reads=len(group),
        )
    return identified


def identify(
    views: list[CameraView],
    item_positions: dict[str, np.ndarray],
    max_dist: float = 0.06,
) -> dict[str, IdentifiedItem]:
    """Full pipeline: back-project QR hits from all views, match + fuse to items."""
    return match_hits_to_items(back_project_hits(views), item_positions, max_dist)
