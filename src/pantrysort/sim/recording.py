"""Record per-camera videos from the station during a run.

Meshcat records the 3D scene; this records what the *cameras* see. A
``CameraVideoRecorder`` registers a frame hook on the station so that each
``publish()`` appends the current frame of one or more rig cameras to its own
MP4. One video per camera (e.g. the arm's base camera and an external camera),
written under ``outputs/`` (gitignored).

Only opencv is needed. Frames are captured at the sim's publish rate; ``fps``
just sets playback speed of the resulting file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger("pantrysort.sim.recording")


class CameraVideoRecorder:
    """Capture one MP4 per named camera via a station frame hook.

    Usage::

        rec = CameraVideoRecorder(station, {"robot_cam": "arm_view.mp4",
                                            "iphone_left": "external_view.mp4"},
                                  out_dir="outputs/run1", fps=20)
        rec.start()
        ... run the sort loop ...
        rec.stop()
    """

    def __init__(self, station, cameras: dict[str, str], out_dir, fps: float = 20.0,
                 distorted: dict[str, bool] | None = None):
        self.station = station
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        # Which cameras to record -> output filename. distorted[name]=True saves
        # the fisheye-distorted frame for that camera (e.g. the base lens).
        self.cameras = {n: self.out_dir / f for n, f in cameras.items()
                        if n in station.camera_names()}
        self.distorted = distorted or {}
        self._writers: dict[str, object] = {}
        self._sizes: dict[str, tuple[int, int]] = {}
        self._frames: dict[str, int] = {n: 0 for n in self.cameras}

    def start(self) -> None:
        if not self.cameras:
            logger.warning("CameraVideoRecorder: no matching cameras to record.")
            return
        self.station.frame_hooks.append(self._capture)

    def _capture(self, station) -> None:
        import cv2

        for name, path in self.cameras.items():
            frame = (station.camera_fisheye(name) if self.distorted.get(name)
                     else station.camera_rgb(name))
            if frame is None:
                continue
            bgr = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGBA2BGR)
            if name not in self._writers:
                h, w = bgr.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                self._writers[name] = cv2.VideoWriter(str(path), fourcc, self.fps, (w, h))
                self._sizes[name] = (w, h)
            self._writers[name].write(bgr)
            self._frames[name] += 1

    def stop(self) -> dict[str, Path]:
        """Finalize all videos and remove the hook. Returns {camera: path}."""
        if self._capture in self.station.frame_hooks:
            self.station.frame_hooks.remove(self._capture)
        written: dict[str, Path] = {}
        for name, writer in self._writers.items():
            writer.release()
            written[name] = self.cameras[name]
            logger.info("Recorded %s: %d frames -> %s", name, self._frames[name],
                        self.cameras[name])
        return written
