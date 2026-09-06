from pathlib import Path
import os
import shutil
import sys
import time
import unicodedata

from ..core.models import ProcessingPlan, ProgressEvent, CameraFile, FileType, ProcessingStatus
from ..ports.presenter_port import PresenterPort


class CliPresenter(PresenterPort):

    def __init__(self, auto_confirm: bool = False):
        self._auto_confirm = auto_confirm
        self._live = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"
        self._color = self._live and "NO_COLOR" not in os.environ
        self._line_visible = False
        self._last_update = 0.0
        self._last_phase = None
        self._started = None

    def select_source(self, candidates: list[Path]) -> Path | None:
        if len(candidates) == 1:
            return candidates[0]
        if self._auto_confirm:
            self.on_error("No unique camera card found. Specify --source PATH.")
            return None
        for index, path in enumerate(candidates, 1):
            print(f"  {index}. {self._safe_text(str(path))}")
        try:
            answer = input("Select card number or enter source folder (empty cancels): ").strip()
        except EOFError:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return candidates[int(answer) - 1]
        return Path(answer).expanduser() if answer else None

    def confirm_overwrite(self, paths: list[Path]) -> bool:
        self._clear_progress()
        print("Existing output(s):")
        for path in paths:
            print(f"  {self._safe_text(str(path))}")
        if self._auto_confirm:
            print("Skipped: automatic mode never overwrites existing files.")
            return False
        try:
            return input("Overwrite? [y/N] ").strip().lower() == "y"
        except EOFError:
            return False

    def show_scanning(self, volume_path: Path) -> None:
        print(f"Scanning {volume_path}...")

    def show_preview(self, plan: ProcessingPlan) -> bool:
        print(f"\nFound {plan.photo_count} photo(s), {plan.video_count} video(s)")
        print(f"Destination: {plan.destination_dir}")
        print(f"Total size: {plan.total_copy_bytes / 1024 / 1024:.1f} MB\n")

        for f in plan.files:
            label = f"  {f.source_path.name} ({f.file_type.value})"
            if f.file_type == FileType.PHOTO and f.exif_fix and f.exif_fix.has_fixes:
                fixes = []
                if f.exif_fix.fixed_lens_model or f.exif_fix.fixed_f_number is not None:
                    fixes.append("lens: manufacturer data")
                if f.exif_fix.fixed_make or f.exif_fix.fixed_model:
                    fixes.append("camera: Kodak Charmera")
                if f.exif_fix.fixed_modify_date:
                    fixes.append("date")
                if f.exif_fix.fixed_width:
                    fixes.append("dimensions")
                label += f" [fix: {', '.join(fixes)}]"
            elif f.file_type == FileType.VIDEO:
                label += " [convert to MP4]"
            print(label)

        print()
        if self._auto_confirm:
            print("Auto-confirm enabled. Proceeding...")
            return True
        response = input("Proceed? [y/N] ")
        return response.strip().lower() == "y"

    def on_progress(self, event: ProgressEvent) -> None:
        now = time.monotonic()
        if self._started is None:
            self._started = now
        phase = (event.file.source_path, event.status)
        changed = phase != self._last_phase
        if not self._live:
            # Logs describe phase changes, not every FFmpeg progress callback.
            if changed:
                print(f"  {self._safe_text(event.file.source_path.name)}: {event.message}")
            self._last_phase = phase
            return
        if not changed and now - self._last_update < 0.1:
            return
        self._last_phase = phase
        self._last_update = now

        percent = max(0.0, min(100.0, event.progress_percent))
        filled = int(percent / 100 * 16)
        bar = "=" * filled + "-" * (16 - filled)
        count = (f"{event.completed_files}/{event.total_files} files"
                 if event.total_files else f"{percent:.0f}%")
        elapsed = int(now - self._started)
        stage = {
            ProcessingStatus.COPYING: "Copying",
            ProcessingStatus.FIXING_EXIF: "Repairing EXIF",
            ProcessingStatus.CONVERTING: "Converting",
            ProcessingStatus.COMPLETED: "Done",
            ProcessingStatus.FAILED: "Failed",
            ProcessingStatus.SKIPPED: "Skipped",
        }.get(event.status, event.status.value)
        if event.file_progress_percent is not None:
            stage += f" {max(0, min(100, event.file_progress_percent)):.0f}%"
        name = self._safe_text(event.file.source_path.name)
        line = f"[{bar}] {count} | {stage} | {name} | {elapsed // 60}:{elapsed % 60:02d}"
        width = max(1, shutil.get_terminal_size().columns - 1)
        if len(line) > width:
            line = f"{count} | {stage} | {name}"
        line = self._fit(line, width)
        if self._color:
            line = f"\033[36m{line}\033[0m"
        sys.stdout.write("\r\033[2K" + line)
        sys.stdout.flush()
        self._line_visible = True

    @staticmethod
    def _safe_text(text: str) -> str:
        return "".join(c if c.isprintable() else "?" for c in text)

    @staticmethod
    def _fit(text: str, width: int) -> str:
        # Account for wide filenames so the live line never wraps.
        result = ""
        used = 0
        for char in text:
            cells = (0 if unicodedata.combining(char) else
                     2 if unicodedata.east_asian_width(char) in ("W", "F") else 1)
            if used + cells > width:
                break
            result += char
            used += cells
        return result

    def _clear_progress(self) -> None:
        if self._line_visible:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
            self._line_visible = False

    def on_complete(self, results: list[CameraFile]) -> None:
        self._clear_progress()
        succeeded = sum(1 for f in results if f.status.value == "completed")
        failed = sum(1 for f in results if f.status.value == "failed")
        skipped = sum(1 for f in results if f.status == ProcessingStatus.SKIPPED)
        summary = f"\nComplete: {succeeded} succeeded, {failed} failed"
        if skipped:
            summary += f", {skipped} skipped"
        print(summary)
        self._started = None
        self._last_phase = None

    def on_error(self, message: str, exception: Exception | None = None) -> None:
        self._clear_progress()
        print(f"Error: {self._safe_text(message)}")

    def prompt_destination(self, default: Path) -> Path:
        if self._auto_confirm:
            return default
        user_input = input(f"Destination [{default}]: ").strip()
        return Path(user_input) if user_input else default

    def show_no_camera(self) -> None:
        print("No Kodak Charmera detected. Please connect the camera and try again.")
