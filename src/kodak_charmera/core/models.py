from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from datetime import datetime
from typing import Optional


class FileType(Enum):
    PHOTO = "photo"
    VIDEO = "video"


class ProcessingStatus(Enum):
    PENDING = "pending"
    COPYING = "copying"
    FIXING_EXIF = "fixing_exif"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ExifData:
    modify_date: Optional[str] = None
    datetime_original: Optional[str] = None
    create_date: Optional[str] = None
    exif_image_width: Optional[int] = None
    exif_image_height: Optional[int] = None
    actual_image_width: Optional[int] = None
    actual_image_height: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    lens_model: Optional[str] = None
    f_number: Optional[float] = None
    user_comment: Optional[str] = None


@dataclass(frozen=True)
class ExifFix:
    fixed_modify_date: Optional[str] = None
    fixed_datetime_original: Optional[str] = None
    fixed_create_date: Optional[str] = None
    fixed_width: Optional[int] = None
    fixed_height: Optional[int] = None
    fixed_make: Optional[str] = None
    fixed_model: Optional[str] = None
    fixed_lens_model: Optional[str] = None
    fixed_f_number: Optional[float] = None
    fixed_user_comment: Optional[str] = None

    @property
    def has_fixes(self) -> bool:
        return any([
            self.fixed_modify_date,
            self.fixed_datetime_original,
            self.fixed_create_date,
            self.fixed_width,
            self.fixed_height,
            self.fixed_make,
            self.fixed_model,
            self.fixed_lens_model,
            self.fixed_f_number,
            self.fixed_user_comment,
        ])


@dataclass
class CameraFile:
    source_path: Path
    file_type: FileType
    file_size: int
    file_modified: datetime
    exif_data: Optional[ExifData] = None
    exif_fix: Optional[ExifFix] = None
    destination_path: Optional[Path] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ProcessingPlan:
    files: list[CameraFile]
    destination_dir: Path
    total_copy_bytes: int

    @property
    def photo_count(self) -> int:
        return sum(1 for f in self.files if f.file_type == FileType.PHOTO)

    @property
    def video_count(self) -> int:
        return sum(1 for f in self.files if f.file_type == FileType.VIDEO)


@dataclass(frozen=True)
class ProgressEvent:
    file: CameraFile
    status: ProcessingStatus
    progress_percent: float
    message: str
    error: Optional[str] = None
    file_progress_percent: Optional[float] = None
    completed_files: int = 0
    total_files: int = 0
