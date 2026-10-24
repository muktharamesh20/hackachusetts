"""Policy abstraction bridging Drake observations and LeRobot policies.

Two backends share one interface:

* ``ScriptedPolicy`` — a deterministic planner (no learning). Given a target
  grasp position and a drop location it emits an end-effector waypoint action.
  This is the fallback so the simulation runs with zero trained weights.
* ``LeRobotPolicy`` — wraps a trained 🤗 LeRobot policy (e.g. ACT, Diffusion,
  pi0/SmolVLA). It is imported lazily so the package stays importable even when
  heavy ML deps or weights are absent.

The pipeline only ever sees ``Policy.select_action(observation) -> PolicyAction``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

import numpy as np


@dataclass
class PolicyObservation:
    """What a policy sees at one control step."""

    # End-effector pose [x, y, z] and the current gripper opening in [0, 1].
    ee_position: np.ndarray
    gripper: float
    # Target grasp point for the current item (world frame), if known.
    target_position: Optional[np.ndarray] = None
    # Drop/goal position for the current item's storage location.
    goal_position: Optional[np.ndarray] = None
    # Optional camera frames keyed by camera name (H, W, 3) uint8.
    images: dict[str, np.ndarray] = field(default_factory=dict)


@dataclass
class PolicyAction:
    """Commanded end-effector delta/target and gripper command."""

    ee_target: np.ndarray        # desired end-effector position [x, y, z]
    gripper: float               # 0 = open, 1 = closed
    done: bool = False           # policy signals the sub-task is complete


class Policy(Protocol):
    def reset(self) -> None: ...
    def select_action(self, obs: PolicyObservation) -> PolicyAction: ...


class ScriptedPolicy:
    """A finite-state pick-and-place controller used as the default backend.

    Phases: approach -> grasp -> lift -> transport -> release -> retract.
    It needs ``target_position`` and ``goal_position`` on the observation.
    """

    APPROACH_H = 0.12   # hover height above target before descending (m)
    REACH_TOL = 0.01    # position tolerance to consider a waypoint reached (m)

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._phase = "approach"

    @staticmethod
    def _reached(a: np.ndarray, b: np.ndarray, tol: float) -> bool:
        return bool(np.linalg.norm(a - b) <= tol)

    def select_action(self, obs: PolicyObservation) -> PolicyAction:
        if obs.target_position is None or obs.goal_position is None:
            # Nothing to do; hold position, open gripper.
            return PolicyAction(ee_target=obs.ee_position.copy(), gripper=0.0, done=True)

        target = np.asarray(obs.target_position, dtype=float)
        goal = np.asarray(obs.goal_position, dtype=float)
        hover_t = target + np.array([0, 0, self.APPROACH_H])
        hover_g = goal + np.array([0, 0, self.APPROACH_H])

        if self._phase == "approach":
            if self._reached(obs.ee_position, hover_t, self.REACH_TOL):
                self._phase = "descend"
            return PolicyAction(ee_target=hover_t, gripper=0.0)

        if self._phase == "descend":
            if self._reached(obs.ee_position, target, self.REACH_TOL):
                self._phase = "grasp"
            return PolicyAction(ee_target=target, gripper=0.0)

        if self._phase == "grasp":
            self._phase = "lift"
            return PolicyAction(ee_target=target, gripper=1.0)

        if self._phase == "lift":
            if self._reached(obs.ee_position, hover_t, self.REACH_TOL):
                self._phase = "transport"
            return PolicyAction(ee_target=hover_t, gripper=1.0)

        if self._phase == "transport":
            if self._reached(obs.ee_position, hover_g, self.REACH_TOL):
                self._phase = "release"
            return PolicyAction(ee_target=hover_g, gripper=1.0)

        if self._phase == "release":
            self._phase = "retract"
            return PolicyAction(ee_target=hover_g, gripper=0.0)

        # retract
        return PolicyAction(ee_target=hover_g, gripper=0.0, done=True)


class LeRobotPolicy:
    """Adapter around a trained LeRobot policy.

    Imports are lazy: constructing this with a valid ``policy_path`` is the only
    thing that pulls in ``lerobot`` and ``torch``.
    """

    def __init__(self, policy_path: str, device: str = "cpu") -> None:
        if not policy_path:
            raise ValueError(
                "LeRobotPolicy requires a policy_path (local dir or HF hub id)."
            )
        try:
            import torch  # noqa: F401
            from lerobot.policies.factory import get_policy_class  # type: ignore
            from lerobot.policies.pretrained import PreTrainedPolicy  # type: ignore # noqa: F401
        except Exception as exc:  # pragma: no cover - env dependent
            raise ImportError(
                "LeRobot/torch are required for the 'lerobot' backend. "
                "Install with `pip install -e .` and provide a trained policy. "
                f"Underlying import error: {exc}"
            ) from exc

        self._device = device
        self._policy_path = policy_path
        self._torch = torch
        self._get_policy_class = get_policy_class
        self._policy = self._load(policy_path, device)

    def _load(self, policy_path: str, device: str):  # pragma: no cover - env dependent
        # LeRobot policies expose `from_pretrained`. The concrete class is
        # discovered from the saved config; we try the generic path first.
        try:
            from lerobot.policies.pretrained import PreTrainedPolicy  # type: ignore

            policy = PreTrainedPolicy.from_pretrained(policy_path)  # type: ignore[attr-defined]
        except Exception:
            # Fall back to a named policy type via the factory if needed.
            policy_cls = self._get_policy_class("act")
            policy = policy_cls.from_pretrained(policy_path)
        policy.to(device)
        policy.eval()
        return policy

    def reset(self) -> None:  # pragma: no cover - env dependent
        if hasattr(self._policy, "reset"):
            self._policy.reset()

    def select_action(self, obs: PolicyObservation) -> PolicyAction:  # pragma: no cover
        torch = self._torch
        batch: dict[str, object] = {
            "observation.state": torch.tensor(
                np.concatenate([obs.ee_position, [obs.gripper]]),
                dtype=torch.float32,
                device=self._device,
            ).unsqueeze(0)
        }
        for name, img in obs.images.items():
            t = torch.from_numpy(img).to(self._device)
            batch[f"observation.images.{name}"] = t.permute(2, 0, 1).unsqueeze(0).float() / 255.0

        with torch.no_grad():
            action = self._policy.select_action(batch)
        action_np = action.squeeze(0).cpu().numpy()
        ee_target = action_np[:3]
        gripper = float(action_np[3]) if action_np.shape[0] > 3 else obs.gripper
        return PolicyAction(ee_target=ee_target, gripper=gripper)


def make_policy(backend: str, policy_path: str = "", device: str = "cpu") -> Policy:
    """Factory selecting a policy backend by name."""
    backend = backend.lower()
    if backend == "scripted":
        return ScriptedPolicy()
    if backend == "lerobot":
        return LeRobotPolicy(policy_path=policy_path, device=device)
    raise ValueError(f"Unknown policy backend: {backend!r} (use 'scripted' or 'lerobot')")
