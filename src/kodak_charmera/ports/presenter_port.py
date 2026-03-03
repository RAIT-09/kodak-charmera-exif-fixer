from abc import ABC, abstractmethod
from pathlib import Path

from ..core.models import ProcessingPlan, ProgressEvent, CameraFile


class PresenterPort(ABC):

    @abstractmethod
    def show_scanning(self, volume_path: Path) -> None:
        ...

    @abstractmethod
    def show_preview(self, plan: ProcessingPlan) -> bool:
        """Return True if user confirms to proceed, False to cancel."""
        ...

    @abstractmethod
    def on_progress(self, event: ProgressEvent) -> None:
        ...

    @abstractmethod
    def on_complete(self, results: list[CameraFile]) -> None:
        ...

    @abstractmethod
    def on_error(self, message: str, exception: Exception | None = None) -> None:
        ...

    @abstractmethod
    def prompt_destination(self, default: Path) -> Path:
        ...

    @abstractmethod
    def show_no_camera(self) -> None:
        ...
