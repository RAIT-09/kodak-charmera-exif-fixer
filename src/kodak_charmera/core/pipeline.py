import os
from pathlib import Path

from .models import (
    CameraFile, FileType, ProcessingPlan, ProcessingStatus, ProgressEvent,
)
from .scanner import CameraScanner
from .file_copier import FileCopier
from .exif_fixer import ExifFixer
from .video_converter import VideoConverter
from ..ports.presenter_port import PresenterPort


class ProcessingPipeline:

    def __init__(
        self,
        scanner: CameraScanner,
        copier: FileCopier,
        exif_fixer: ExifFixer,
        video_converter: VideoConverter,
        presenter: PresenterPort,
    ):
        self._scanner = scanner
        self._copier = copier
        self._exif_fixer = exif_fixer
        self._video_converter = video_converter
        self._presenter = presenter

    def scan_and_preview(self, volume_path: Path, dest_dir: Path) -> ProcessingPlan | None:
        self._presenter.show_scanning(volume_path)
        files = self._scanner.scan(volume_path)

        if not files:
            self._presenter.on_error("No supported files found on camera.")
            return None

        total_bytes = sum(f.file_size for f in files)
        plan = ProcessingPlan(files=files, destination_dir=dest_dir, total_copy_bytes=total_bytes)

        if not self._presenter.show_preview(plan):
            return None

        # Let presenter override destination (GUI user may have changed it)
        final_dest = self._presenter.prompt_destination(dest_dir)
        if final_dest != dest_dir:
            plan = ProcessingPlan(
                files=files, destination_dir=final_dest, total_copy_bytes=total_bytes,
            )

        return plan

    def execute(self, plan: ProcessingPlan) -> list[CameraFile]:
        results: list[CameraFile] = []
        total = len(plan.files)

        for i, file in enumerate(plan.files):
            try:
                # Step 1: Copy
                self._emit(file, ProcessingStatus.COPYING, i, total, "Copying...")
                self._copier.copy(file, plan.destination_dir)

                # Step 2: Fix or Convert
                if file.file_type == FileType.PHOTO:
                    self._emit(file, ProcessingStatus.FIXING_EXIF, i, total, "Fixing EXIF...")
                    self._exif_fixer.fix(file)
                elif file.file_type == FileType.VIDEO:
                    self._emit(file, ProcessingStatus.CONVERTING, i, total, "Converting...")
                    self._video_converter.convert(
                        file,
                        progress_callback=lambda pct, f=file, idx=i: self._emit(
                            f, ProcessingStatus.CONVERTING, idx, total,
                            f"Converting... {pct:.0f}%",
                        ),
                    )

                # Restore original file modification time
                self._restore_mtime(file)

                file.status = ProcessingStatus.COMPLETED
                self._emit(file, ProcessingStatus.COMPLETED, i + 1, total, "Done")

            except Exception as e:
                file.status = ProcessingStatus.FAILED
                file.error_message = str(e)
                self._presenter.on_error(
                    f"Failed to process {file.source_path.name}: {e}", e,
                )

            results.append(file)

        self._presenter.on_complete(results)
        return results

    @staticmethod
    def _restore_mtime(file: CameraFile) -> None:
        """Restore the original file modification time after processing."""
        if file.destination_path and file.destination_path.exists():
            ts = file.file_modified.timestamp()
            os.utime(file.destination_path, (ts, ts))

    def _emit(
        self,
        file: CameraFile,
        status: ProcessingStatus,
        current: int,
        total: int,
        message: str,
    ) -> None:
        percent = (current / total) * 100 if total > 0 else 0
        self._presenter.on_progress(ProgressEvent(
            file=file, status=status, progress_percent=percent, message=message,
        ))
