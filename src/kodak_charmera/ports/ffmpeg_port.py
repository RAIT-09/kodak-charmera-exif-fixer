from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional


class FfmpegPort(ABC):

    @abstractmethod
    def convert_avi_to_mp4(
        self,
        input_path: Path,
        output_path: Path,
        *,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        crf: int = 18,
        audio_bitrate: str = "128k",
        preset: str = "medium",
        creation_time: Optional[datetime] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Path:
        ...

    @abstractmethod
    def probe_duration(self, file_path: Path) -> float:
        ...
