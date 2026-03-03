from pathlib import Path

from ..core.models import ProcessingPlan, ProgressEvent, CameraFile, FileType
from ..ports.presenter_port import PresenterPort


class CliPresenter(PresenterPort):

    def __init__(self, auto_confirm: bool = False):
        self._auto_confirm = auto_confirm

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
        print(f"  [{event.progress_percent:5.1f}%] {event.file.source_path.name}: {event.message}")

    def on_complete(self, results: list[CameraFile]) -> None:
        succeeded = sum(1 for f in results if f.status.value == "completed")
        failed = sum(1 for f in results if f.status.value == "failed")
        print(f"\nComplete: {succeeded} succeeded, {failed} failed")

    def on_error(self, message: str, exception: Exception | None = None) -> None:
        print(f"Error: {message}")

    def prompt_destination(self, default: Path) -> Path:
        if self._auto_confirm:
            return default
        user_input = input(f"Destination [{default}]: ").strip()
        return Path(user_input) if user_input else default

    def show_no_camera(self) -> None:
        print("No Kodak Charmera detected. Please connect the camera and try again.")
