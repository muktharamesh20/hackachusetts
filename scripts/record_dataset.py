"""Record a LeRobot dataset from scripted sim rollouts.

Runs the scripted policy through the sort loop, capturing (state, action) pairs
per pick-and-place, and writes them in LeRobot's dataset format for later
training.

Usage:
    python scripts/record_dataset.py --repo-id your-user/pantry-sort --episodes 20
"""

from __future__ import annotations

import argparse
import logging

import numpy as np

from pantrysort.config import CONFIG
from pantrysort.perception.classifier import Detection
from pantrysort.policy.dataset import DatasetRecorder
from pantrysort.policy.lerobot_policy import PolicyObservation, make_policy
from pantrysort.sim.pantry_scene import LOCATION_DROP_POINTS, default_scene

logger = logging.getLogger("record_dataset")


def record_episode(recorder: DatasetRecorder, detection: Detection, drop) -> None:
    policy = make_policy("scripted")
    policy.reset()

    ee = np.array([0.3, 0.0, 0.4])
    gripper = 0.0
    for _ in range(400):
        obs = PolicyObservation(
            ee_position=ee.copy(),
            gripper=gripper,
            target_position=np.asarray(detection.position, dtype=float),
            goal_position=np.asarray(drop, dtype=float),
        )
        action = policy.select_action(obs)
        state = np.concatenate([ee, [gripper]]).astype("float32")
        act = np.concatenate([action.ee_target, [action.gripper]]).astype("float32")
        recorder.add_step(state=state, action=act)

        ee = ee + 0.25 * (np.asarray(action.ee_target, dtype=float) - ee)
        gripper = float(action.gripper)
        if action.done:
            break
    recorder.end_episode(task=f"sort {detection.label}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a LeRobot dataset from sim.")
    parser.add_argument("--repo-id", default="local/pantry-sort")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--root", default=None, help="Local dataset output dir")
    args = parser.parse_args()

    logging.basicConfig(level=CONFIG.log_level, format="%(levelname)s: %(message)s")

    recorder = DatasetRecorder(repo_id=args.repo_id, fps=args.fps, root=args.root)
    scene = default_scene()

    produced = 0
    while produced < args.episodes:
        for item in scene.items:
            if produced >= args.episodes:
                break
            det = item.to_detection()
            drop = LOCATION_DROP_POINTS.get("shelf-dry", (0.0, 0.7, 0.2))
            record_episode(recorder, det, drop)
            produced += 1

    logger.info("Recorded %d episode(s).", recorder.num_episodes)
    if recorder.num_episodes == 0:
        logger.warning(
            "No episodes written. Install lerobot (`pip install -e .`) to persist "
            "the dataset; the recording flow still ran."
        )


if __name__ == "__main__":
    main()
