# Kodak Charmera EXIF Fixer

A tool that fixes broken EXIF metadata from [Kodak Charmera](https://www.kodak.com/) toy cameras and converts AVI videos to MP4. Includes a GUI, a CLI, and optional macOS auto-launch when the camera is plugged in via USB.

## The Problem

The Kodak Charmera uses a **Generalplus CBB3** chipset that produces JPEG files with several EXIF issues:

| Issue | Example (Before) | After Fix |
|---|---|---|
| **Malformed date format** | `2026:03:03:12:16:29` (6 colon-separated parts) | `2026:03:03 12:16:29` (standard EXIF datetime) |
| **Wrong EXIF dimensions** | ExifImageWidth=640, ExifImageHeight=480 | ExifImageWidth=1440, ExifImageHeight=1080 (matches actual) |
| **Corrupt MakerNote/IFD** | `Error: Bad ExifIFD offset for MakerNoteUnknown` | Rebuilt before writing |

AVI videos also have problems:

| Issue | Detail |
|---|---|
| **Hardcoded wrong date** | Metadata says `2010-06-29` regardless of when the video was taken |
| **Uncompressed codec** | Motion JPEG + PCM 16-bit audio — 22 MB for just 10 seconds |

## What This Tool Does

1. **Copies** all files from the camera to your Mac (never modifies files on the camera)
2. **Fixes EXIF** on JPEGs — date format, image dimensions, and corrupt IFD structure
3. **Converts AVI to MP4** — H.264 + AAC with proper `creation_time` metadata
4. **Preserves file modification times** — output files retain the original timestamps

## Installation

### Prerequisites

[Homebrew](https://brew.sh/) is required to install the system dependencies:

```bash
brew install exiftool ffmpeg
```

Python 3.11+ is required. If you need tkinter (for the GUI), Python 3.13+ is recommended since it works with Homebrew's Tcl/Tk 9.x out of the box.

### Install from source

```bash
git clone https://github.com/your-username/kodak-charmera-exif-fixer.git
cd kodak-charmera-exif-fixer
pip install -e .
```

## Usage

### GUI Mode (default)

```bash
kodak-charmera
```

or:

```bash
python -m kodak_charmera
```

This opens a window where you can:
- See all detected files and what fixes will be applied
- Change the destination directory (default: `~/Pictures/KodakCharmera/`)
- Click **Start** to begin processing
- Watch real-time progress for each file

If tkinter is not available, it falls back to CLI mode automatically.

### CLI Mode

```bash
kodak-charmera --cli
```

Interactive CLI that shows a preview and asks for confirmation before processing.

### Automated Mode

```bash
kodak-charmera --auto
```

Processes everything without prompting. Useful for automation and the LaunchAgent.

### Custom Destination

```bash
kodak-charmera --dest /path/to/output
```

Works with any mode (`--cli`, `--auto`, or GUI).

### All Options

```
usage: kodak-charmera [-h] [--cli] [--auto] [--dest DEST]

Kodak Charmera EXIF Fixer

options:
  -h, --help   show this help message and exit
  --cli        Run in CLI mode (no GUI)
  --auto       Auto-confirm (for LaunchAgent use)
  --dest DEST  Override destination directory
```

## macOS Auto-Launch (LaunchAgent)

You can configure macOS to automatically launch the app whenever the Kodak Charmera is connected via USB.

### Install

```bash
python -m kodak_charmera.launcher.launchd_installer install
```

This installs a LaunchAgent that watches `/Volumes/Untitled` (the camera's mount point). When the camera is plugged in, the GUI opens automatically.

### Uninstall

```bash
python -m kodak_charmera.launcher.launchd_installer uninstall
```

### Logs

If something goes wrong, check the logs:

```bash
cat /tmp/kodak-charmera-exif-fixer.stdout.log
cat /tmp/kodak-charmera-exif-fixer.stderr.log
```

## Architecture

The project follows a **Ports & Adapters (Hexagonal Architecture)** pattern, making it easy to swap UI frameworks or underlying tools.

```
src/kodak_charmera/
├── core/               # Business logic — no dependencies on UI or external tools
│   ├── models.py       # Data classes: CameraFile, ExifData, ExifFix, ProgressEvent
│   ├── config.py       # AppConfig with all defaults
│   ├── scanner.py      # Scan camera, classify files, compute EXIF fixes
│   ├── file_copier.py  # Copy files from camera to destination
│   ├── exif_fixer.py   # Apply EXIF corrections
│   ├── video_converter.py  # AVI → MP4 conversion
│   └── pipeline.py     # Orchestrator: scan → preview → copy → fix → convert
│
├── ports/              # Abstract interfaces (ABCs)
│   ├── exiftool_port.py
│   ├── ffmpeg_port.py
│   ├── filesystem_port.py
│   ├── presenter_port.py       # ← The UI abstraction
│   └── volume_detector_port.py
│
├── adapters/           # Concrete implementations
│   ├── exiftool_cli.py     # Wraps `exiftool` CLI
│   ├── ffmpeg_cli.py       # Wraps `ffmpeg` / `ffprobe` CLI
│   ├── local_filesystem.py # os / shutil / pathlib
│   └── macos_volume.py     # Detects /Volumes/Untitled
│
├── ui/                 # Swappable UI layer
│   ├── tkinter_app.py  # GUI (tkinter)
│   └── cli_app.py      # CLI / headless
│
└── launcher/           # macOS integration
    └── launchd_installer.py
```

### Swapping the UI

The `PresenterPort` defines the entire UI contract:

```python
class PresenterPort(ABC):
    def show_scanning(self, volume_path: Path) -> None: ...
    def show_preview(self, plan: ProcessingPlan) -> bool: ...
    def on_progress(self, event: ProgressEvent) -> None: ...
    def on_complete(self, results: list[CameraFile]) -> None: ...
    def on_error(self, message: str, exception: Exception | None = None) -> None: ...
    def prompt_destination(self, default: Path) -> Path: ...
    def show_no_camera(self) -> None: ...
```

To add a new UI (e.g., TUI with [Textual](https://textual.textualize.io/), Qt with PySide6), simply implement `PresenterPort` and wire it up in `__main__.py`. The core business logic requires zero changes.

## Configuration Defaults

All defaults are defined in `core/config.py`:

| Setting | Default | Description |
|---|---|---|
| `camera_volume` | `/Volumes/Untitled` | Camera mount point |
| `dcim_subdir` | `DCIM` | Subdirectory containing media files |
| `destination_dir` | `~/Pictures/KodakCharmera` | Output directory |
| `photo_extensions` | `.jpg`, `.jpeg` | Photo file extensions to process |
| `video_extensions` | `.avi` | Video file extensions to process |
| `ffmpeg_video_codec` | `libx264` | Video codec for MP4 output |
| `ffmpeg_audio_codec` | `aac` | Audio codec for MP4 output |
| `ffmpeg_crf` | `18` | Quality factor (0–51, lower = better) |
| `ffmpeg_preset` | `medium` | Encoding speed/quality tradeoff |
| `ffmpeg_audio_bitrate` | `128k` | Audio bitrate |
| `delete_avi_after_convert` | `false` | Whether to delete the AVI copy after MP4 conversion |

## How EXIF Repair Works

The Kodak Charmera's Generalplus chipset creates EXIF data with a corrupt internal structure (bad MakerNote IFD offsets). Simply writing new tag values fails:

```
Error: Bad ExifIFD offset for MakerNoteUnknown
```

The fix is a two-step process:

1. **Rebuild the EXIF structure** while preserving all tag values:
   ```bash
   exiftool -all= -tagsfromfile @ -all:all -unsafe -overwrite_original photo.jpg
   ```
2. **Write the corrected values**:
   ```bash
   exiftool -overwrite_original \
     -ModifyDate="2026:03:03 12:16:29" \
     -DateTimeOriginal="2026:03:03 12:16:29" \
     -CreateDate="2026:03:03 12:16:29" \
     -ExifImageWidth=1440 \
     -ExifImageHeight=1080 \
     photo.jpg
   ```

## How Video Conversion Works

```bash
ffmpeg -y -i input.avi \
  -c:v libx264 -crf 18 -preset medium \
  -c:a aac -b:a 128k -ar 44100 \
  -metadata creation_time="2026-03-03T12:16:29" \
  -progress pipe:1 \
  output.mp4
```

- **Video**: Motion JPEG → H.264 (CRF 18 = visually lossless)
- **Audio**: PCM 16-bit 16kHz mono → AAC 128k 44.1kHz
- **Metadata**: `creation_time` set from the original file's modification timestamp (since the camera's embedded date is wrong)
- **Progress**: Real-time progress tracking by parsing ffmpeg's `out_time_us` output

## Runtime Dependencies

| Tool | Purpose | Install |
|---|---|---|
| Python 3.11+ | Runtime | [python.org](https://www.python.org/) or `pyenv install 3.13` |
| exiftool | EXIF read/write | `brew install exiftool` |
| ffmpeg | Video conversion | `brew install ffmpeg` |

No pip dependencies — the project uses only the Python standard library plus the system tools above.

## License

MIT
