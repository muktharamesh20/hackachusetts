# Dev notes

Running notes for contributors. Read this if the Drake simulation will not
install or run on your machine.

---

## Running the Drake simulation on Windows: use WSL

**Drake publishes no Windows wheels.** `pip install drake` works only on Linux
and macOS. On Windows you must run the simulation inside WSL (Windows Subsystem
for Linux). The QR/inventory code runs fine on native Windows; only the Drake
pieces (`pantrysort.sim.station`, `run_sim.py`, the `RgbdSensor` camera) need
Linux/macOS.

Also note: a very new system Python can be too new for Drake. Drake wheels
target **Python 3.10-3.12**. Ubuntu 26.04 and recent Windows installers may ship
Python 3.14, which Drake does not support yet — create a 3.12 environment.

### WSL setup that is known to work (verified 2026)

From an Ubuntu WSL shell (`uv` is a fast Python/venv manager):

```bash
uv python install 3.12
uv venv --python 3.12 ~/.venvs/pantrysort

PROJ="/mnt/c/Users/<you>/.../hackachusetts"
cd "$PROJ"
uv pip install --python ~/.venvs/pantrysort/bin/python "drake>=1.30.0" numpy
uv pip install --python ~/.venvs/pantrysort/bin/python \
    opencv-python-headless pillow pydantic python-dateutil pyyaml rich \
    "segno==1.6.6" pytest
uv pip install --python ~/.venvs/pantrysort/bin/python --no-deps -e .
```

Verify:

```bash
# pydrake has no __version__; check an actual import instead:
~/.venvs/pantrysort/bin/python -c \
  "from pydrake.multibody.plant import MultibodyPlant; print('drake ok')"
~/.venvs/pantrysort/bin/python -m pytest tests/ -p no:cacheprovider
```

Meshcat prints an `http://localhost:7000` URL; open it in a Windows browser —
WSL forwards localhost automatically.

> Tip: run the venv's Python directly (`~/.venvs/pantrysort/bin/python ...`).
> The venv is created by `uv` and has no standalone `pip`; use `uv pip` to add
> packages.

---

## Current SO-101 sim (what is on `main`)

The merged SO-101 sim (`src/pantrysort/sim/station.py`) is **kinematic**: joint
angles come from inverse kinematics and are written straight to the plant
context, and a grasped item is rigidly attached to the gripper and moves with
it. There is no contact-dynamics grasping yet. This is fast, deterministic, and
ideal for the perception -> locate -> aim-camera -> move loop. The `Station`
API: `move_ee_to`, `scan_pose`, `move_joints_to`, `set_gripper`,
`attach_nearest`, `drop_held_onto`, plus the gripper QR `scanner`.

A separate, dynamics-based prototype (an `InverseDynamicsController` driving the
arm with real torques/contact) was explored and set aside in favor of the
kinematic sim. It lives in git stashes on the sim author's machine; ping before
reviving it. Trade-off summary: kinematic = better for camera-driven
localization and LeRobot episode recording; dynamic = needed only if a policy
must learn from physical grasp success/failure observed through the camera.

---

## In progress: fisheye camera for object localization

Next change (additive, on top of the kinematic station): a wide-FOV camera with
OpenCV fisheye post-distortion, plus pixel+depth -> world back-projection so the
arm can locate items from camera data rather than ground-truth scene positions.
It will reuse the existing VTK renderer / `RgbdSensor` pattern used by the QR
scanner. The arm will still need to pick items up afterward, so the camera is
being designed to feed target points into `move_ee_to`. This note will be
updated when that lands.