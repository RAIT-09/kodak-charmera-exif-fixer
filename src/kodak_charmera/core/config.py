from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    camera_volume: Path = field(default_factory=lambda: Path("/Volumes/Untitled"))
    dcim_subdir: str = "DCIM"
    destination_dir: Path = field(
        default_factory=lambda: Path.home() / "Pictures" / "KodakCharmera"
    )
    photo_extensions: frozenset[str] = frozenset({".jpg", ".jpeg"})
    video_extensions: frozenset[str] = frozenset({".avi"})
    ffmpeg_video_codec: str = "libx264"
    ffmpeg_audio_codec: str = "aac"
    ffmpeg_crf: int = 18
    ffmpeg_audio_bitrate: str = "128k"
    ffmpeg_preset: str = "medium"
    delete_avi_after_convert: bool = True
