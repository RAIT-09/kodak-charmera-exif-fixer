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
        self.exif.read_exif.return_value = ExifData(
            make='Kodak', model='Charmera', lens_model=fix.fixed_lens_model,
            f_number=fix.fixed_f_number, user_comment=fix.fixed_user_comment)
        ExifFixer(self.exif).fix(file)
        kwargs = self.exif.write_exif.call_args.kwargs
        self.assertEqual((kwargs['make'], kwargs['model']), ('Kodak', 'Charmera'))

    def test_correct_camera_needs_no_repair(self):
        self.assertFalse(self.scanner._compute_exif_fix(
            ExifData(make='Kodak', model='Charmera', lens_model='Existing lens', f_number=2.4)).has_fixes)

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

    def test_existing_lens_and_aperture_are_preserved(self):
        fix = self.scanner._compute_exif_fix(ExifData(
            lens_model='Recorded lens', f_number=2.8, user_comment='Personal note'))
        self.assertIsNone(fix.fixed_lens_model)
        self.assertIsNone(fix.fixed_f_number)
        self.assertIsNone(fix.fixed_user_comment)

    def test_provenance_preserves_comment_and_missing_dimensions_are_filled(self):
        fix = self.scanner._compute_exif_fix(ExifData(
            user_comment='Personal note', actual_image_width=1440, actual_image_height=1080))
        self.assertTrue(fix.fixed_user_comment.startswith('Personal note\n'))
        self.assertIn('not measured exposure', fix.fixed_user_comment)
        self.assertEqual((fix.fixed_width, fix.fixed_height), (1440, 1080))
