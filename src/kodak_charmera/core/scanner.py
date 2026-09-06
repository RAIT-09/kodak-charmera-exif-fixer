from pathlib import Path
from typing import Optional

from .models import CameraFile, ExifData, ExifFix, FileType
from ..ports.exiftool_port import ExiftoolPort
from ..ports.filesystem_port import FilesystemPort


PHOTO_EXTENSIONS = frozenset({".jpg", ".jpeg"})
VIDEO_EXTENSIONS = frozenset({".avi"})


class CameraScanner:

    def __init__(self, filesystem: FilesystemPort, exiftool: ExiftoolPort):
        self._fs = filesystem
        self._exiftool = exiftool

    def scan(self, volume_path: Path) -> list[CameraFile]:
        dcim = next((p for p in sorted(volume_path.iterdir())
                     if p.name.casefold() == "dcim" and p.is_dir()), volume_path)
        files: list[CameraFile] = []

        for path in sorted(self._fs.list_files(dcim, recursive=True)):
            # Skip macOS metadata files
            if path.name.startswith("._") or path.is_symlink():
                continue

            file_type = self._classify_file(path)
            if file_type is None:
                continue

            camera_file = CameraFile(
                source_path=path,
                file_type=file_type,
                file_size=self._fs.file_size(path),
                file_modified=self._fs.file_mtime(path),
            )

            if file_type == FileType.PHOTO:
                exif = self._exiftool.read_exif(path)
                camera_file.exif_data = exif
                camera_file.exif_fix = self._compute_exif_fix(exif)

            files.append(camera_file)

        return files

    def _classify_file(self, path: Path) -> Optional[FileType]:
        ext = path.suffix.lower()
        if ext in PHOTO_EXTENSIONS:
            return FileType.PHOTO
        if ext in VIDEO_EXTENSIONS:
            return FileType.VIDEO
        return None

    def _compute_exif_fix(self, exif: ExifData) -> ExifFix:
        lens_model = "Kodak Charmera built-in lens" if not exif.lens_model else None
        f_number = 2.4 if exif.f_number is None else None
        comment = None
        if lens_model or f_number is not None:
            added = []
            if lens_model:
                added.append("LensModel is a descriptive label")
            if f_number is not None:
                added.append("FNumber=2.4 is the nominal manufacturer aperture, not measured exposure")
            note = ("Charmera EXIF Fixer: " + "; ".join(added) + ". "
                    "Manufacturer lists lens as 35mm F2.4; focal length fields are not inferred. "
                    "Source: https://www.kodak.retopro.co/products/"
                    "kodak-charmera-br-keychain-digital-camera-blind-box")
            comment = ((exif.user_comment + "\n") if exif.user_comment else "") + note
        return ExifFix(
            fixed_lens_model=lens_model,
            fixed_f_number=f_number,
            fixed_user_comment=comment,
            fixed_modify_date=self._fix_date(exif.modify_date),
            fixed_datetime_original=self._fix_date(exif.datetime_original),
            fixed_create_date=self._fix_date(exif.create_date),
            fixed_width=self._fix_dimension(exif.exif_image_width, exif.actual_image_width),
            fixed_height=self._fix_dimension(exif.exif_image_height, exif.actual_image_height),
            fixed_make="Kodak" if exif.make != "Kodak" else None,
            fixed_model="Charmera" if exif.model != "Charmera" else None,
        )

    @staticmethod
    def _fix_date(raw_date: Optional[str]) -> Optional[str]:
        """Fix '2026:03:03:12:16:29' -> '2026:03:03 12:16:29'."""
        if raw_date is None:
            return None
        parts = raw_date.split(":")
        if len(parts) == 6:
            return f"{parts[0]}:{parts[1]}:{parts[2]} {parts[3]}:{parts[4]}:{parts[5]}"
        return None

    @staticmethod
    def _fix_dimension(exif_value: Optional[int], actual_value: Optional[int]) -> Optional[int]:
        if actual_value is not None and actual_value > 0 and exif_value != actual_value:
            return actual_value
        return None
