import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from kodak_charmera.core.exif_fixer import ExifFixer
from kodak_charmera.core.models import CameraFile, ExifData, FileType
from kodak_charmera.core.scanner import CameraScanner


class CameraMetadataTests(unittest.TestCase):
    def setUp(self):
        self.exif = Mock()
        self.scanner = CameraScanner(Mock(), self.exif)

    def test_missing_camera_alone_triggers_repair(self):
        fix = self.scanner._compute_exif_fix(ExifData())
        self.assertTrue(fix.has_fixes)
        self.assertEqual((fix.fixed_make, fix.fixed_model), ('Kodak', 'Charmera'))
        file = CameraFile(Path('source.jpg'), FileType.PHOTO, 1, datetime.now(),
                          exif_fix=fix, destination_path=Path('copy.jpg'))
        self.exif.read_exif.return_value = ExifData(make='Kodak', model='Charmera')
        ExifFixer(self.exif).fix(file)
        kwargs = self.exif.write_exif.call_args.kwargs
        self.assertEqual((kwargs['make'], kwargs['model']), ('Kodak', 'Charmera'))

    def test_correct_camera_needs_no_repair(self):
        self.assertFalse(self.scanner._compute_exif_fix(
            ExifData(make='Kodak', model='Charmera')).has_fixes)

    def test_chipset_metadata_is_replaced(self):
        fix = self.scanner._compute_exif_fix(ExifData(make='Generalplus', model='CBB3'))
        self.assertEqual((fix.fixed_make, fix.fixed_model), ('Kodak', 'Charmera'))

    def test_failed_camera_write_is_rejected(self):
        file = CameraFile(Path('source.jpg'), FileType.PHOTO, 1, datetime.now(),
                          exif_fix=self.scanner._compute_exif_fix(ExifData()),
                          destination_path=Path('copy.jpg'))
        self.exif.read_exif.return_value = ExifData()
        with self.assertRaisesRegex(RuntimeError, 'verification failed for make'):
            ExifFixer(self.exif).fix(file)
