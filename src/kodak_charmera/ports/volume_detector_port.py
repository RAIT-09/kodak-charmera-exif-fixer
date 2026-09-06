from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class VolumeDetectorPort(ABC):

    @abstractmethod
    def find_camera_volumes(self) -> list[Path]:
        ...

    def find_camera_volume(self, expected_name: str | None = None) -> Optional[Path]:
        volumes = self.find_camera_volumes()
        return volumes[0] if len(volumes) == 1 else None
