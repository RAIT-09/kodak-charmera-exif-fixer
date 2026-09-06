# 📷 Kodak Charmera EXIF Fixer

**Plug in your card. Repair your photos. Keep your originals.**

A small macOS app that repairs Charmera photo metadata and converts AVI clips to MP4.
Use the desktop window or a compact live terminal display.

**🍎 macOS · 🐍 Python 3.11+ · 🖥️ GUI + CLI · 📜 MIT**

## ✨ Tiny camera, tidier memories

| 📸 Photos & videos | 📥 Import experience |
| :--- | :--- |
| Sets camera to **Kodak / Charmera** | Finds SD cards regardless of their name |
| Adds missing lens info & nominal **f/2.4** | Includes files in DCIM subfolders |
| Fixes malformed EXIF date formatting | Offers desktop and terminal workflows |
| Corrects mismatched EXIF dimensions | Asks before replacing existing output |
| Converts AVI → **H.264 + AAC MP4** | Processes temporary copies before publishing |
| Preserves file modification times | Leaves files on the source card unchanged |

## 🚀 Get started

Requires **Python 3.11+**, **ExifTool**, and **FFmpeg** (including ffprobe).

```bash
brew install exiftool ffmpeg

git clone https://github.com/phobo-at/kodak-charmera-exif-fixer.git
cd kodak-charmera-exif-fixer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

kodak-charmera
```

The desktop window requires Tkinter in your Python installation. If it cannot be
imported, the app falls back to the CLI. Run `source .venv/bin/activate` again in a
new terminal before using the commands below.

## 🎛️ Pick your workflow

```bash
kodak-charmera                       # Desktop window
kodak-charmera --cli                 # Interactive terminal
kodak-charmera --auto                # Unattended; skips existing output
```

Choose a card or an existing photo folder explicitly:

```bash
kodak-charmera --cli --source "/Volumes/MY SD CARD" --dest ~/Pictures/Charmera
```

📁 **Default destination:** **`~/Pictures/KodakCharmera`**. With no `--source`, the app looks
for mounted volumes containing a DCIM folder. Multiple candidates prompt a choice;
use `--source` to resolve this in unattended mode.

⏳ **Live progress** — updates in place:

```text
[============----] 3/4 files | Converting 14% | MOVI0108.avi | 0:42
```

Narrow terminals get a compact view. Redirected output uses concise phase logs.
Set `NO_COLOR=1` to disable colors.

## 💡 Good to know

- 🛡️ **Existing files:** “Overwrite?” defaults to **No** (skip). `--auto` never overwrites.
  EXIF changes are read back and converted videos checked with ffprobe before publishing.
- 📷 **Camera identity:** imported photos are explicitly labeled `Make=Kodak`,
  `Model=Charmera`, replacing different values. Use this tool for Charmera photos;
  DCIM detection does not identify the camera model.
- 🗓️ **Dates:** repairs formatting such as `2026:03:03:12:16:29` → `2026:03:03 12:16:29`.
  It does not correct a wrongly set camera clock. Video dates use the source file's
  modification time.
- 🔎 **Lens:** fills missing lens identification and nominal **f/2.4** from the
  [manufacturer specifications](https://www.kodak.retopro.co/products/kodak-charmera-br-keychain-digital-camera-blind-box),
  recording provenance in the EXIF user comment. Existing lens/aperture values are
  preserved. The ambiguous advertised “35mm” is documented only in that comment;
  numeric focal length, ISO and shutter speed are never invented. Missing EXIF
  dimensions are filled from the JPEG itself.
- 📂 **Output:** timestamp-based names such as `IMG_20260906_120000.jpg` and
  `VID_20260906_120000.mp4`. Conflicts are name-based, not content-based deduplication.
  By default, the temporary AVI copy is removed after conversion; the source AVI stays.

<details>
<summary><strong>🔌 Optional: launch when a card is mounted</strong></summary>

From the activated environment in this source checkout:

```bash
python -m kodak_charmera.launcher.launchd_installer install
# To remove:
python -m kodak_charmera.launcher.launchd_installer uninstall
```

The LaunchAgent watches `/Volumes`, so unrelated disk changes can also launch the
app. Reinstall it if upgrading from the older name-specific configuration.
Logs: `/tmp/kodak-charmera-exif-fixer.stdout.log` and
`/tmp/kodak-charmera-exif-fixer.stderr.log`.

</details>

<details>
<summary><strong>🧰 Development & tests</strong></summary>

```bash
PYTHONPATH=src python -m unittest discover -v
```

Tests cover overwrite decisions, failed replacements, card discovery, camera tags,
and CLI progress. Generated-media integration tests use ExifTool, FFmpeg and ffprobe
when installed. Physical SD-card and native GUI behavior still need manual testing.

The Python runtime uses the standard library. Code is split into
[`core`](src/kodak_charmera/core), [`adapters`](src/kodak_charmera/adapters),
[`ports`](src/kodak_charmera/ports), and [`ui`](src/kodak_charmera/ui).
See [`AppConfig`](src/kodak_charmera/core/config.py) for encoding defaults.

</details>

---

🤝 Fork of [RAIT-09/kodak-charmera-exif-fixer](https://github.com/RAIT-09/kodak-charmera-exif-fixer).
📜 [MIT license](LICENSE).
