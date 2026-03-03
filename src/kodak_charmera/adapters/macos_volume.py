from pathlib import Path
from typing import Optional

from ..ports.volume_detector_port import VolumeDetectorPort


class MacOSVolumeDetector(VolumeDetectorPort):

    def find_camera_volume(self, expected_name: str = "Untitled") -> Optional[Path]:
        volume = Path("/Volumes") / expected_name
        dcim = volume / "DCIM"
        if dcim.is_dir():
            return volume
        return None
