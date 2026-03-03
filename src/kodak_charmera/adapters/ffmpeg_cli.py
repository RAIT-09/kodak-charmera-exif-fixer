import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

from ..ports.ffmpeg_port import FfmpegPort


class FfmpegCliAdapter(FfmpegPort):

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self._ffmpeg = ffmpeg_path
        self._ffprobe = ffprobe_path

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
        duration = self.probe_duration(input_path)

        cmd = [
            self._ffmpeg, "-y",
            "-i", str(input_path),
            "-c:v", video_codec,
            "-crf", str(crf),
            "-preset", preset,
            "-c:a", audio_codec,
            "-b:a", audio_bitrate,
            "-ar", "44100",
        ]
        if creation_time:
            cmd.extend(["-metadata", f"creation_time={creation_time.isoformat()}"])
        cmd.extend(["-progress", "pipe:1", str(output_path)])

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            if progress_callback and duration > 0:
                match = re.match(r"out_time_us=(\d+)", line.strip())
                if match:
                    elapsed_us = int(match.group(1))
                    percent = min((elapsed_us / 1_000_000) / duration * 100, 100.0)
                    progress_callback(percent)

        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"ffmpeg failed (rc={proc.returncode}): {stderr}")

        return output_path

    def probe_duration(self, file_path: Path) -> float:
        result = subprocess.run(
            [
                self._ffprobe,
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "json",
                str(file_path),
            ],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
