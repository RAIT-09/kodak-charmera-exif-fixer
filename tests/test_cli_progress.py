import io
import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from kodak_charmera.core.models import CameraFile, FileType, ProcessingStatus, ProgressEvent
from kodak_charmera.ui.cli_app import CliPresenter


class Terminal(io.StringIO):
    def isatty(self):
        return True


class ProgressTests(unittest.TestCase):
    def event(self, percent=13):
        return ProgressEvent(
            CameraFile(Path("MOVI0108.avi"), FileType.VIDEO, 123, datetime.now()),
            ProcessingStatus.CONVERTING, 75, f"Converting... {percent}%",
            file_progress_percent=percent, completed_files=3, total_files=4,
        )

    def test_terminal_updates_in_place_and_errors_remain_visible(self):
        output = Terminal()
        with patch("sys.stdout", output), patch.dict(os.environ, {"TERM": "xterm"}), \
                patch("time.monotonic", side_effect=[0, 1, 2]):
            presenter = CliPresenter()
            presenter.on_progress(self.event())
            presenter.on_progress(self.event(14))
            self.assertNotIn("\n", output.getvalue())
            self.assertIn("3/4 files", output.getvalue())
            self.assertIn("Converting 14%", output.getvalue())
            presenter.on_error("Bad file")
            presenter.on_progress(self.event(15))
            presenter.on_complete([])
        self.assertIn("Error: Bad file\n", output.getvalue())
        self.assertTrue(output.getvalue().endswith("Complete: 0 succeeded, 0 failed\n"))

    def test_redirected_output_has_no_escape_sequences_or_progress_spam(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            presenter = CliPresenter()
            for percent in range(100):
                presenter.on_progress(self.event(percent))
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertNotIn("\033", output.getvalue())

    def test_fast_updates_are_throttled(self):
        output = Terminal()
        with patch("sys.stdout", output), patch.dict(os.environ, {"TERM": "xterm"}), \
                patch("time.monotonic", side_effect=[1, 1.01, 1.02]):
            presenter = CliPresenter()
            for _ in range(3):
                presenter.on_progress(self.event())
        self.assertEqual(output.getvalue().count("\r"), 1)

    def test_narrow_terminal_and_no_color(self):
        output = Terminal()
        with patch("sys.stdout", output), \
                patch.dict(os.environ, {"TERM": "xterm", "NO_COLOR": "1"}), \
                patch("shutil.get_terminal_size", return_value=os.terminal_size((30, 24))):
            CliPresenter().on_progress(self.event())
        line = output.getvalue().replace("\r\033[2K", "")
        self.assertLessEqual(len(line), 29)
        self.assertNotIn("\033[36m", line)
        self.assertEqual(CliPresenter._fit("写真abc", 5), "写真a")


if __name__ == "__main__":
    unittest.main()
