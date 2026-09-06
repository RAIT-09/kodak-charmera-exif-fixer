from pathlib import Path

from ..ports.volume_detector_port import VolumeDetectorPort


class MacOSVolumeDetector(VolumeDetectorPort):

    def __init__(self, volumes_root: Path = Path("/Volumes")):
        self._volumes_root = volumes_root

    def find_camera_volumes(self) -> list[Path]:
        """Find camera-card candidates by DCIM structure, never by volume label.

        DCIM identifies a media card, not a particular camera model. Let the user
        choose when multiple candidates are mounted.
        """
        candidates = []
        for volume in sorted(self._volumes_root.iterdir()):
            try:
                if volume.is_symlink() or not volume.is_dir():
                    continue
                if any(p.name.casefold() == "dcim" and p.is_dir()
                       for p in volume.iterdir()):
                    candidates.append(volume)
            except OSError:
                continue
        return candidates
