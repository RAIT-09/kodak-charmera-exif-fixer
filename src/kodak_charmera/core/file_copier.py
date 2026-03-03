from pathlib import Path

from .models import CameraFile, ProcessingStatus
from ..ports.filesystem_port import FilesystemPort


class FileCopier:

    def __init__(self, filesystem: FilesystemPort):
        self._fs = filesystem

    def copy(self, file: CameraFile, dest_dir: Path) -> CameraFile:
        self._fs.ensure_directory(dest_dir)
        dest_path = dest_dir / file.source_path.name
        self._fs.copy_file(file.source_path, dest_path, preserve_mtime=True)
        file.destination_path = dest_path
        file.status = ProcessingStatus.COPYING
        return file
