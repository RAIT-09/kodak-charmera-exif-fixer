import json
import subprocess
from pathlib import Path

from ..core.models import ExifData
from ..ports.exiftool_port import ExiftoolPort


class ExiftoolCliAdapter(ExiftoolPort):

    def __init__(self, exiftool_path: str = "exiftool"):
        self._exe = exiftool_path

    def read_exif(self, file_path: Path) -> ExifData:
        result = subprocess.run(
            [
                self._exe, "-json",
                "-ImageWidth", "-ImageHeight",
                "-ExifImageWidth", "-ExifImageHeight",
                "-ModifyDate", "-DateTimeOriginal", "-CreateDate",
                "-Make", "-Model",
                str(file_path),
            ],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)[0]
        return ExifData(
            modify_date=data.get("ModifyDate"),
            datetime_original=data.get("DateTimeOriginal"),
            create_date=data.get("CreateDate"),
            exif_image_width=data.get("ExifImageWidth"),
            exif_image_height=data.get("ExifImageHeight"),
            actual_image_width=data.get("ImageWidth"),
            actual_image_height=data.get("ImageHeight"),
            make=data.get("Make"),
            model=data.get("Model"),
        )

    def rebuild_exif(self, file_path: Path) -> None:
        """Rebuild EXIF structure to fix corrupt MakerNote/IFD entries."""
        subprocess.run(
            [
                self._exe,
                "-all=", "-tagsfromfile", "@",
                "-all:all", "-unsafe",
                "-overwrite_original",
                str(file_path),
            ],
            capture_output=True, text=True, check=True,
        )

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
        # Rebuild EXIF first to fix corrupt structure from Charmera
        self.rebuild_exif(file_path)

        tag_map = {
            "ModifyDate": modify_date,
            "DateTimeOriginal": datetime_original,
            "CreateDate": create_date,
            "ExifImageWidth": exif_image_width,
            "ExifImageHeight": exif_image_height,
        }
        args = [self._exe, "-overwrite_original"]
        for tag, value in tag_map.items():
            if value is not None:
                args.append(f"-{tag}={value}")
        args.append(str(file_path))
        subprocess.run(args, capture_output=True, text=True, check=True)
