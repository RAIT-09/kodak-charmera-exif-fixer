from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class VolumeDetectorPort(ABC):

    @abstractmethod
    def find_camera_volume(self, expected_name: str = "Untitled") -> Optional[Path]:
        ...
