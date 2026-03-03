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
        dcim = volume_path / "DCIM"
        files: list[CameraFile] = []

        for path in self._fs.list_files(dcim):
            # Skip macOS metadata files
            if path.name.startswith("._"):
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
        return ExifFix(
            fixed_modify_date=self._fix_date(exif.modify_date),
            fixed_datetime_original=self._fix_date(exif.datetime_original),
            fixed_create_date=self._fix_date(exif.create_date),
            fixed_width=self._fix_dimension(exif.exif_image_width, exif.actual_image_width),
            fixed_height=self._fix_dimension(exif.exif_image_height, exif.actual_image_height),
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
        if exif_value is not None and actual_value is not None and exif_value != actual_value:
            return actual_value
        return None
