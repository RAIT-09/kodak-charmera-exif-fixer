import shutil
from pathlib import Path
from datetime import datetime
from typing import Iterator

from ..ports.filesystem_port import FilesystemPort


class LocalFilesystemAdapter(FilesystemPort):

    def list_files(self, directory: Path, recursive: bool = False) -> Iterator[Path]:
        if recursive:
            yield from (p for p in directory.rglob("*") if p.is_file())
        else:
            yield from (p for p in directory.iterdir() if p.is_file())

    def copy_file(self, src: Path, dst: Path, preserve_mtime: bool = True) -> Path:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return dst

    def ensure_directory(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    def file_size(self, path: Path) -> int:
        return path.stat().st_size

    def file_mtime(self, path: Path) -> datetime:
        return datetime.fromtimestamp(path.stat().st_mtime)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def delete(self, path: Path) -> None:
        path.unlink()
