from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Iterator


class FilesystemPort(ABC):

    @abstractmethod
    def list_files(self, directory: Path, recursive: bool = False) -> Iterator[Path]:
        ...

    @abstractmethod
    def copy_file(self, src: Path, dst: Path, preserve_mtime: bool = True) -> Path:
        ...

    @abstractmethod
    def ensure_directory(self, path: Path) -> Path:
        ...

    @abstractmethod
    def file_size(self, path: Path) -> int:
        ...

    @abstractmethod
    def file_mtime(self, path: Path) -> datetime:
        ...

    @abstractmethod
    def exists(self, path: Path) -> bool:
        ...

    @abstractmethod
    def delete(self, path: Path) -> None:
        ...
