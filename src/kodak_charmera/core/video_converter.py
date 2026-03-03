from typing import Callable, Optional

from .models import CameraFile, ProcessingStatus
from .config import AppConfig
from ..ports.ffmpeg_port import FfmpegPort


class VideoConverter:

    def __init__(self, ffmpeg: FfmpegPort, config: AppConfig):
        self._ffmpeg = ffmpeg
        self._config = config

    def convert(
        self,
        file: CameraFile,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> CameraFile:
        assert file.destination_path is not None
        file.status = ProcessingStatus.CONVERTING

        output_path = file.destination_path.with_suffix(".mp4")
        self._ffmpeg.convert_avi_to_mp4(
            input_path=file.destination_path,
            output_path=output_path,
            video_codec=self._config.ffmpeg_video_codec,
            audio_codec=self._config.ffmpeg_audio_codec,
            crf=self._config.ffmpeg_crf,
            audio_bitrate=self._config.ffmpeg_audio_bitrate,
            preset=self._config.ffmpeg_preset,
            creation_time=file.file_modified,
            progress_callback=progress_callback,
        )

        # Replace destination with the MP4 path
        avi_copy = file.destination_path
        file.destination_path = output_path
        file.status = ProcessingStatus.COMPLETED

        if self._config.delete_avi_after_convert:
            avi_copy.unlink(missing_ok=True)

        return file
