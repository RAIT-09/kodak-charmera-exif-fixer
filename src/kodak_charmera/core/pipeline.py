import os
import tempfile
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

        source = volume_path.resolve()
        destination = plan.destination_dir.expanduser().resolve()
        if destination == source or source in destination.parents:
            raise ValueError("Destination must be outside the source folder.")
        # Protect the entire source volume when importing directly from a card.
        if source.is_relative_to(Path("/Volumes")) and len(source.parts) >= 3:
            card = Path(*source.parts[:3])
            if destination == card or card in destination.parents:
                raise ValueError("Destination must not be on the source SD card.")
        return ProcessingPlan(plan.files, destination, plan.total_copy_bytes)

    def execute(self, plan: ProcessingPlan) -> list[CameraFile]:
        results: list[CameraFile] = []
        total = len(plan.files)

        plan.destination_dir.mkdir(parents=True, exist_ok=True)
        used: set[Path] = set()
        for i, file in enumerate(plan.files):
            try:
                target = self._copier.target_path(file, plan.destination_dir)
                base = target
                counter = 1
                # Stable numbering for multiple inputs sharing the same timestamp.
                while target.with_suffix("") in used:
                    target = base.with_name(f"{base.stem}_{counter}{base.suffix}")
                    counter += 1
                used.add(target.with_suffix(""))
                final = target.with_suffix(".mp4") if file.file_type == FileType.VIDEO else target
                targets = [final]
                if file.file_type == FileType.VIDEO and self._video_converter.keep_avi:
                    targets.append(target)
                conflicts = [p for p in targets if os.path.lexists(p)]
                if conflicts and not self._presenter.confirm_overwrite(conflicts):
                    file.status = ProcessingStatus.SKIPPED
                    self._emit(file, ProcessingStatus.SKIPPED, i + 1, total, "Skipped")
                    results.append(file)
                    continue

                # Work on the destination filesystem so publishing can be atomic.
                with tempfile.TemporaryDirectory(prefix=".charmera-", dir=plan.destination_dir) as tmp:
                    self._emit(file, ProcessingStatus.COPYING, i, total, "Copying...")
                    self._copier.copy(file, Path(tmp))
                    copied = file.destination_path
                    if copied is None or copied.stat().st_size != file.file_size:
                        raise RuntimeError("Copy size does not match the source.")
                    if file.file_type == FileType.PHOTO:
                        self._emit(file, ProcessingStatus.FIXING_EXIF, i, total, "Fixing EXIF...")
                        self._exif_fixer.fix(file)
                    else:
                        self._emit(file, ProcessingStatus.CONVERTING, i, total, "Converting...")
                        self._video_converter.convert(
                            file,
                            progress_callback=lambda pct, f=file, idx=i: self._emit(
                                f, ProcessingStatus.CONVERTING, idx, total,
                                f"Converting... {pct:.0f}%", file_progress_percent=pct,
                            ),
                        )
                    self._restore_mtime(file)
                    output = file.destination_path
                    if output is None or not output.is_file() or output.stat().st_size == 0:
                        raise RuntimeError("No valid output was produced.")
                    publications = [(output, final)]
                    if len(targets) > 1:
                        ts = file.file_modified.timestamp()
                        os.utime(copied, (ts, ts))
                        publications.insert(0, (copied, target))
                    for staged, dest in publications:
                        if dest in conflicts:
                            os.replace(staged, dest)
                        else:
                            # Exclusive creation also protects files appearing after the prompt.
                            os.link(staged, dest)
                    file.destination_path = final

                file.status = ProcessingStatus.COMPLETED
                self._emit(file, ProcessingStatus.COMPLETED, i + 1, total, "Done")
            except Exception as e:
                file.destination_path = None
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
        file_progress_percent: float | None = None,
    ) -> None:
        percent = (current / total) * 100 if total > 0 else 0
        self._presenter.on_progress(ProgressEvent(
            file=file, status=status, progress_percent=percent, message=message,
            file_progress_percent=file_progress_percent,
            completed_files=current, total_files=total,
        ))
