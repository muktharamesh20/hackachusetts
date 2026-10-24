"""Execute a pick-and-place for one item by stepping a policy in the station.

This is the bridge between a :class:`~pantrysort.policy.lerobot_policy.Policy`
and the Drake simulation. For the scripted backend it advances the end-effector
through the policy's waypoints and steps the simulator so the motion is
visualized in Meshcat. For a LeRobot backend, the same loop feeds observations
(including rendered camera frames, if wired up) and applies returned actions.

The task-space tracking here is deliberately simple: the focus of the scaffold
is the overall sort pipeline and the clean seams between simulation, policy,
and inventory. Swapping in a full differential-IK / operational-space controller
is a well-isolated change inside :func:`execute_pick_and_place`.
"""

from __future__ import annotations

import numpy as np

from pantrysort.policy.lerobot_policy import Policy, PolicyObservation


def execute_pick_and_place(
    station,
    policy: Policy,
    grasp_position: np.ndarray,
    drop_position: np.ndarray,
    max_steps: int = 400,
    dt: float = 0.05,
) -> bool:
    """Run the policy until it reports ``done`` or ``max_steps`` elapses.

    Returns True if the policy signalled completion.

    The end-effector state is tracked in task space. When a real Drake arm and
    IK controller are wired into the station, replace ``_ee_position`` /
    ``_apply_action`` with reads/writes against the plant context.
    """
    policy.reset()

    ee = _ee_position(station)
    gripper = 0.0
    done = False
    steps = 0

    while not done and steps < max_steps:
        obs = PolicyObservation(
            ee_position=ee.copy(),
            gripper=gripper,
            target_position=np.asarray(grasp_position, dtype=float),
            goal_position=np.asarray(drop_position, dtype=float),
        )
        action = policy.select_action(obs)

        # First-order tracking toward the commanded target (task-space proxy).
        ee = _step_toward(ee, np.asarray(action.ee_target, dtype=float), rate=0.25)
        gripper = float(action.gripper)
        done = action.done

        _advance_sim(station, dt)
        steps += 1

    return done


def _ee_position(station) -> np.ndarray:
    """Current end-effector position. Falls back to a nominal home pose."""
    try:  # pragma: no cover - env dependent
        plant = station.plant
        context = station.simulator.get_context()
        plant_context = plant.GetMyContextFromRoot(context)
        frame = plant.GetFrameByName("iiwa_link_7")
        pose = plant.CalcRelativeTransform(
            plant_context, plant.world_frame(), frame
        )
        return np.asarray(pose.translation(), dtype=float)
    except Exception:
        return np.array([0.3, 0.0, 0.4])


def _step_toward(current: np.ndarray, target: np.ndarray, rate: float) -> np.ndarray:
    return current + rate * (target - current)


def _advance_sim(station, dt: float) -> None:
    try:  # pragma: no cover - env dependent
        sim = station.simulator
        sim.AdvanceTo(sim.get_context().get_time() + dt)
    except Exception:
        pass
