import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from kodak_charmera.adapters.local_filesystem import LocalFilesystemAdapter
from kodak_charmera.adapters.macos_volume import MacOSVolumeDetector
from kodak_charmera.core.config import AppConfig
from kodak_charmera.core.exif_fixer import ExifFixer
from kodak_charmera.core.file_copier import FileCopier
from kodak_charmera.core.models import CameraFile, ExifData, ExifFix, FileType, ProcessingPlan, ProcessingStatus
from kodak_charmera.core.pipeline import ProcessingPipeline
from kodak_charmera.core.scanner import CameraScanner
from kodak_charmera.core.video_converter import VideoConverter
from kodak_charmera.ui.cli_app import CliPresenter


class SafeImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'card'
        self.source.mkdir()
        self.dest = self.root / 'output'
        self.dest.mkdir()
        self.fs = LocalFilesystemAdapter()
        self.presenter = Mock()
        self.presenter.confirm_overwrite.return_value = False
        self.ffmpeg = Mock()
        self.ffmpeg.probe_duration.return_value = 1.0
        def convert(**kwargs):
            kwargs['output_path'].write_bytes(b'new mp4')
        self.ffmpeg.convert_avi_to_mp4.side_effect = convert
        self.fixer = Mock()
        self.pipeline = ProcessingPipeline(
            Mock(), FileCopier(self.fs), self.fixer,
            VideoConverter(self.ffmpeg, AppConfig()), self.presenter,
        )

    def file(self, name='photo.jpg'):
        path = self.source / name
        path.write_bytes(b'original')
        return CameraFile(path, FileType.VIDEO if name.endswith('.avi') else FileType.PHOTO,
                          8, datetime(2026, 9, 6, 12))

    def run_files(self, files):
        return self.pipeline.execute(ProcessingPlan(files, self.dest, 8 * len(files)))

    def test_card_detection_ignores_label_and_handles_multiple_cards(self):
        for name in ['HOLIDAY 2026', 'Untitled', 'unrelated']:
            (self.root / name).mkdir()
        (self.root / 'HOLIDAY 2026' / 'dcim').mkdir()
        detector = MacOSVolumeDetector(self.root)
        self.assertEqual(detector.find_camera_volume(), self.root / 'HOLIDAY 2026')
        (self.root / 'Untitled' / 'DCIM').mkdir()
        self.assertEqual(len(detector.find_camera_volumes()), 2)
        self.assertIsNone(detector.find_camera_volume())

    def test_scan_nested_and_lowercase_dcim(self):
        folder = self.source / 'dcim' / '100MEDIA'
        folder.mkdir(parents=True)
        (folder / 'PHOTO.JPG').write_bytes(b'jpeg')
        (folder / '._PHOTO.JPG').write_bytes(b'metadata')
        exif = Mock()
        exif.read_exif.return_value = ExifData()
        files = CameraScanner(self.fs, exif).scan(self.source)
        self.assertEqual([f.source_path.name for f in files], ['PHOTO.JPG'])

    def test_existing_photo_is_skipped_without_consent(self):
        existing = self.dest / 'IMG_20260906_120000.jpg'
        existing.write_bytes(b'old')
        file = self.file()
        self.run_files([file])
        self.assertEqual(file.status, ProcessingStatus.SKIPPED)
        self.assertEqual(existing.read_bytes(), b'old')
        self.fixer.fix.assert_not_called()
        self.presenter.confirm_overwrite.assert_called_once_with([existing])

    def test_existing_mp4_is_prompted_even_without_avi(self):
        existing = self.dest / 'VID_20260906_120000.mp4'
        existing.write_bytes(b'old video')
        file = self.file('video.avi')
        self.run_files([file])
        self.assertEqual(file.status, ProcessingStatus.SKIPPED)
        self.assertEqual(existing.read_bytes(), b'old video')
        self.ffmpeg.convert_avi_to_mp4.assert_not_called()
        self.presenter.confirm_overwrite.assert_called_once_with([existing])

    def test_approved_replacement_publishes_and_keeps_source(self):
        existing = self.dest / 'VID_20260906_120000.mp4'
        existing.write_bytes(b'old video')
        self.presenter.confirm_overwrite.return_value = True
        file = self.file('video.avi')
        self.run_files([file])
        self.assertEqual(file.status, ProcessingStatus.COMPLETED)
        self.assertEqual(existing.read_bytes(), b'new mp4')
        self.assertEqual(file.source_path.read_bytes(), b'original')
        self.assertEqual(list(self.dest.iterdir()), [existing])
        self.assertAlmostEqual(existing.stat().st_mtime, file.file_modified.timestamp())

    def test_failed_replacement_preserves_old_video(self):
        existing = self.dest / 'VID_20260906_120000.mp4'
        existing.write_bytes(b'old video')
        self.presenter.confirm_overwrite.return_value = True
        self.ffmpeg.probe_duration.return_value = 0
        file = self.file('video.avi')
        self.run_files([file])
        self.assertEqual(file.status, ProcessingStatus.FAILED)
        self.assertEqual(existing.read_bytes(), b'old video')
        self.assertEqual(list(self.dest.iterdir()), [existing])

    def test_failed_exif_repair_preserves_existing_photo(self):
        existing = self.dest / 'IMG_20260906_120000.jpg'
        existing.write_bytes(b'old photo')
        self.presenter.confirm_overwrite.return_value = True
        self.fixer.fix.side_effect = RuntimeError('bad EXIF')
        file = self.file()
        self.run_files([file])
        self.assertEqual(existing.read_bytes(), b'old photo')
        self.assertEqual(file.status, ProcessingStatus.FAILED)
        self.assertEqual(list(self.dest.iterdir()), [existing])

    def test_file_appearing_during_processing_is_not_overwritten(self):
        existing = self.dest / 'IMG_20260906_120000.jpg'
        self.fixer.fix.side_effect = lambda _: existing.write_bytes(b'another process')
        file = self.file()
        self.run_files([file])
        self.assertEqual(existing.read_bytes(), b'another process')
        self.assertEqual(file.status, ProcessingStatus.FAILED)

    def test_same_timestamp_uses_stable_distinct_names(self):
        self.run_files([self.file('a.jpg'), self.file('b.jpg')])
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()),
                         ['IMG_20260906_120000.jpg', 'IMG_20260906_120000_1.jpg'])
        self.run_files([self.file('a.jpg'), self.file('b.jpg')])
        self.assertEqual(self.presenter.confirm_overwrite.call_count, 2)
        self.assertEqual(len(list(self.dest.iterdir())), 2)

    def test_auto_mode_never_confirms_overwrite_or_guesses_card(self):
        with patch('sys.stdout', io.StringIO()), patch('builtins.input') as prompt:
            presenter = CliPresenter(auto_confirm=True)
            self.assertFalse(presenter.confirm_overwrite([self.dest / 'exists.jpg']))
            self.assertIsNone(presenter.select_source([self.source, self.dest]))
            prompt.assert_not_called()

    def test_cli_requires_explicit_yes(self):
        with patch('sys.stdout', io.StringIO()):
            presenter = CliPresenter()
            for response, expected in [('', False), ('n', False), ('y', True)]:
                with patch('builtins.input', return_value=response):
                    self.assertEqual(presenter.confirm_overwrite([self.dest]), expected)

    def test_exif_readback_rejects_unapplied_fix(self):
        exif = Mock()
        exif.read_exif.return_value = ExifData(exif_image_width=640)
        file = self.file()
        file.destination_path = file.source_path
        file.exif_fix = ExifFix(fixed_width=1440)
        with self.assertRaisesRegex(RuntimeError, 'EXIF verification'):
            ExifFixer(exif).fix(file)

    def test_destination_on_source_is_rejected(self):
        self.pipeline._scanner.scan.return_value = [self.file()]
        self.presenter.show_preview.return_value = True
        self.presenter.prompt_destination.return_value = self.source / 'output'
        with self.assertRaisesRegex(ValueError, 'outside the source'):
            self.pipeline.scan_and_preview(self.source, self.dest)

    def test_keep_avi_checks_both_output_conflicts(self):
        self.pipeline._video_converter = VideoConverter(
            self.ffmpeg, AppConfig(delete_avi_after_convert=False))
        avi = self.dest / 'VID_20260906_120000.avi'
        avi.write_bytes(b'old avi')
        file = self.file('video.avi')
        self.run_files([file])
        self.presenter.confirm_overwrite.assert_called_once_with([avi])
        self.assertEqual(avi.read_bytes(), b'old avi')
        self.presenter.confirm_overwrite.return_value = True
        self.run_files([file])
        self.assertEqual(avi.read_bytes(), b'original')
        self.assertEqual(file.status, ProcessingStatus.COMPLETED)


if __name__ == '__main__':
    unittest.main()
