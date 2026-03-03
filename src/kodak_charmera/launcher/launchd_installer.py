"""Install/uninstall the macOS LaunchAgent for USB auto-launch."""
import shutil
import subprocess
import sys
from pathlib import Path


PLIST_NAME = "com.kodakcharmera.exiffixer.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "resources" / "launchd" / PLIST_NAME


def install() -> None:
    """Install the LaunchAgent plist with the current Python path."""
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    dst = LAUNCH_AGENTS_DIR / PLIST_NAME

    template = TEMPLATE_PATH.read_text()
    python_path = sys.executable
    plist_content = template.replace("__PYTHON_PATH__", python_path)
    dst.write_text(plist_content)

    subprocess.run(["launchctl", "load", str(dst)], check=True)
    print(f"LaunchAgent installed: {dst}")
    print(f"Using Python: {python_path}")


def uninstall() -> None:
    """Uninstall the LaunchAgent plist."""
    dst = LAUNCH_AGENTS_DIR / PLIST_NAME
    if dst.exists():
        subprocess.run(["launchctl", "unload", str(dst)], check=False)
        dst.unlink()
        print(f"LaunchAgent uninstalled: {dst}")
    else:
        print("LaunchAgent not installed.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage Kodak Charmera LaunchAgent")
    parser.add_argument("action", choices=["install", "uninstall"])
    args = parser.parse_args()

    if args.action == "install":
        install()
    else:
        uninstall()
