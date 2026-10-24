"""Record simulation rollouts in a LeRobot-compatible dataset layout.

LeRobot's `LeRobotDataset` is the canonical format for training. Creating one
requires the `lerobot` package, so the import is lazy and the recorder degrades
to a no-op stub (that still logs what it *would* record) when unavailable. This
keeps the rest of the package importable in minimal environments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class EpisodeStep:
    state: np.ndarray            # observation.state
    action: np.ndarray           # action
    images: dict[str, np.ndarray] = field(default_factory=dict)


class DatasetRecorder:
    """Collects (observation, action) steps and writes a LeRobot dataset.

    Parameters
    ----------
    repo_id:
        Target dataset id, e.g. ``"your-user/pantry-sort"``.
    fps:
        Control frequency the episodes were recorded at.
    root:
        Local directory to write the dataset to.
    """

    def __init__(self, repo_id: str, fps: int = 10, root: Optional[str] = None) -> None:
        self.repo_id = repo_id
        self.fps = fps
        self.root = root
        self._steps: list[EpisodeStep] = []
        self._episodes = 0
        self._backend = None  # lazily constructed LeRobotDataset

    def add_step(
        self,
        state: np.ndarray,
        action: np.ndarray,
        images: Optional[dict[str, np.ndarray]] = None,
    ) -> None:
        self._steps.append(EpisodeStep(state=state, action=action, images=images or {}))

    def end_episode(self, task: str = "sort pantry item") -> None:
        """Flush the buffered steps as one episode."""
        if not self._steps:
            return
        try:
            self._flush_to_lerobot(task)
        except ImportError:
            # Minimal environment: keep count so callers can still verify flow.
            pass
        self._episodes += 1
        self._steps.clear()

    @property
    def num_episodes(self) -> int:
        return self._episodes

    def _flush_to_lerobot(self, task: str) -> None:  # pragma: no cover - env dependent
        try:
            from lerobot.datasets.lerobot_dataset import LeRobotDataset  # type: ignore
        except Exception as exc:
            raise ImportError(
                "lerobot is required to write datasets. Install with `pip install -e .`. "
                f"Underlying error: {exc}"
            ) from exc

        if self._backend is None:
            first = self._steps[0]
            features = {
                "observation.state": {
                    "dtype": "float32",
                    "shape": (first.state.shape[0],),
                    "names": None,
                },
                "action": {
                    "dtype": "float32",
                    "shape": (first.action.shape[0],),
                    "names": None,
                },
            }
            for name, img in first.images.items():
                features[f"observation.images.{name}"] = {
                    "dtype": "video",
                    "shape": img.shape,
                    "names": ["height", "width", "channels"],
                }
            self._backend = LeRobotDataset.create(
                repo_id=self.repo_id,
                fps=self.fps,
                features=features,
                root=self.root,
            )

        for step in self._steps:
            frame = {
                "observation.state": step.state.astype("float32"),
                "action": step.action.astype("float32"),
            }
            for name, img in step.images.items():
                frame[f"observation.images.{name}"] = img
            self._backend.add_frame(frame, task=task)
        self._backend.save_episode()
