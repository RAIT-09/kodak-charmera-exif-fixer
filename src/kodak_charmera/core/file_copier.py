from pathlib import Path

from .models import CameraFile, FileType, ProcessingStatus
from ..ports.filesystem_port import FilesystemPort

_PREFIX = {
    FileType.PHOTO: "IMG",
    FileType.VIDEO: "VID",
}


class FileCopier:

    def __init__(self, filesystem: FilesystemPort):
        self._fs = filesystem

    def copy(self, file: CameraFile, dest_dir: Path) -> CameraFile:
        self._fs.ensure_directory(dest_dir)
        dest_path = self._build_dest_path(file, dest_dir)
        self._fs.copy_file(file.source_path, dest_path, preserve_mtime=True)
        file.destination_path = dest_path
        file.status = ProcessingStatus.COPYING
        return file

    def _build_dest_path(self, file: CameraFile, dest_dir: Path) -> Path:
        prefix = _PREFIX.get(file.file_type, "FILE")
        timestamp = file.file_modified.strftime("%Y%m%d_%H%M%S")
        suffix = file.source_path.suffix.lower()
        name = f"{prefix}_{timestamp}{suffix}"
        dest = dest_dir / name

        # Handle duplicates within the same second
        counter = 1
        while dest.exists():
            name = f"{prefix}_{timestamp}_{counter}{suffix}"
            dest = dest_dir / name
            counter += 1

        return dest
