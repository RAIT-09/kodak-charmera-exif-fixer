"""Entry point: python -m kodak_charmera"""
import argparse
import sys
from pathlib import Path

from .core.config import AppConfig
from .core.scanner import CameraScanner
from .core.file_copier import FileCopier
from .core.exif_fixer import ExifFixer
from .core.video_converter import VideoConverter
from .core.pipeline import ProcessingPipeline
from .adapters.exiftool_cli import ExiftoolCliAdapter
from .adapters.ffmpeg_cli import FfmpegCliAdapter
from .adapters.local_filesystem import LocalFilesystemAdapter
from .adapters.macos_volume import MacOSVolumeDetector
from .ports.presenter_port import PresenterPort


def _build_pipeline(presenter: PresenterPort, config: AppConfig) -> ProcessingPipeline:
    exiftool = ExiftoolCliAdapter()
    ffmpeg = FfmpegCliAdapter()
    filesystem = LocalFilesystemAdapter()

    scanner = CameraScanner(filesystem, exiftool)
    copier = FileCopier(filesystem)
    exif_fixer = ExifFixer(exiftool)
    converter = VideoConverter(ffmpeg, config)

    return ProcessingPipeline(scanner, copier, exif_fixer, converter, presenter)


def _run_pipeline(
    pipeline: ProcessingPipeline,
    volume: Path,
    config: AppConfig,
) -> None:
    plan = pipeline.scan_and_preview(volume, config.destination_dir)
    if plan:
        pipeline.execute(plan)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kodak Charmera EXIF Fixer")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (no GUI)")
    parser.add_argument(
        "--auto", action="store_true", help="Auto-confirm (for LaunchAgent use)"
    )
    parser.add_argument("--dest", type=str, help="Override destination directory")
    args = parser.parse_args()

    config = AppConfig()
    if args.dest:
        config.destination_dir = Path(args.dest)

    # Detect camera
    volume_detector = MacOSVolumeDetector()
    volume = volume_detector.find_camera_volume()

    # Choose presenter
    if args.cli or args.auto:
        from .ui.cli_app import CliPresenter
        presenter = CliPresenter(auto_confirm=args.auto)
    else:
        try:
            from .ui.tkinter_app import TkinterPresenter
            presenter = TkinterPresenter()
        except ImportError:
            from .ui.cli_app import CliPresenter
            presenter = CliPresenter()
            print("tkinter not available, falling back to CLI mode.")

    if volume is None:
        presenter.show_no_camera()
        sys.exit(1)

    pipeline = _build_pipeline(presenter, config)

    if hasattr(presenter, "run"):
        presenter.run(lambda: _run_pipeline(pipeline, volume, config))
    else:
        _run_pipeline(pipeline, volume, config)


if __name__ == "__main__":
    main()
