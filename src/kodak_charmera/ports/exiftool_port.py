from abc import ABC, abstractmethod
from pathlib import Path

from ..core.models import ExifData


class ExiftoolPort(ABC):

    @abstractmethod
    def read_exif(self, file_path: Path) -> ExifData:
        ...

    @abstractmethod
    def write_exif(
        self,
        file_path: Path,
        *,
        modify_date: str | None = None,
        datetime_original: str | None = None,
        create_date: str | None = None,
        exif_image_width: int | None = None,
        exif_image_height: int | None = None,
    ) -> None:
        ...
