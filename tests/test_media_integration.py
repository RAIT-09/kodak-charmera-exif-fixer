"""Small generated media fixtures; never reads a user's camera files."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from kodak_charmera.adapters.exiftool_cli import ExiftoolCliAdapter
from kodak_charmera.adapters.ffmpeg_cli import FfmpegCliAdapter
from kodak_charmera.adapters.local_filesystem import LocalFilesystemAdapter
from kodak_charmera.core.config import AppConfig
from kodak_charmera.core.exif_fixer import ExifFixer
from kodak_charmera.core.file_copier import FileCopier
from kodak_charmera.core.models import ProcessingPlan, ProcessingStatus
from kodak_charmera.core.pipeline import ProcessingPipeline
from kodak_charmera.core.scanner import CameraScanner
from kodak_charmera.core.video_converter import VideoConverter


@unittest.skipUnless(all(shutil.which(tool) for tool in ('ffmpeg', 'ffprobe', 'exiftool')),
                     'requires ffmpeg, ffprobe and exiftool')
class MediaIntegrationTests(unittest.TestCase):
    def test_generated_photo_and_video_import_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dcim = root / 'RENAMED CARD' / 'DCIM' / '100MEDIA'
            dcim.mkdir(parents=True)
            image, video = dcim / 'photo.jpg', dcim / 'movie.avi'
            for path, options in [(image, ['-frames:v', '1']),
                                  (video, ['-t', '0.2', '-c:v', 'mjpeg'])]:
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                'color=c=blue:s=64x48:r=10', *options, str(path)],
                               check=True, capture_output=True, timeout=30)
            subprocess.run(['exiftool', '-overwrite_original', '-ExifImageWidth=1',
                            '-ExifImageHeight=1', str(image)], check=True,
                           capture_output=True, timeout=30)
            originals = {p: p.read_bytes() for p in (image, video)}
            fs, exif, ffmpeg = LocalFilesystemAdapter(), ExiftoolCliAdapter(), FfmpegCliAdapter()
            scanner = CameraScanner(fs, exif)
            presenter = Mock()
            presenter.confirm_overwrite.return_value = False
            pipeline = ProcessingPipeline(scanner, FileCopier(fs), ExifFixer(exif),
                                          VideoConverter(ffmpeg, AppConfig()), presenter)
            files = scanner.scan(dcim.parent.parent)
            output = root / 'output'
            result = pipeline.execute(ProcessingPlan(files, output, sum(f.file_size for f in files)))
            self.assertTrue(all(f.status == ProcessingStatus.COMPLETED for f in result),
                            [f.error_message for f in result])
            fixed = next(output.glob('*.jpg'))
            self.assertEqual(exif.read_exif(fixed).exif_image_width, 64)
            metadata = exif.read_exif(fixed)
            self.assertEqual((metadata.make, metadata.model), ('Kodak', 'Charmera'))
            self.assertFalse(scanner._compute_exif_fix(metadata).has_fixes)
            self.assertGreater(ffmpeg.probe_duration(next(output.glob('*.mp4'))), 0)
            previous = {p: p.read_bytes() for p in output.iterdir()}
            result = pipeline.execute(ProcessingPlan(scanner.scan(dcim.parent.parent), output, 0))
            self.assertTrue(all(f.status == ProcessingStatus.SKIPPED for f in result))
            self.assertEqual({p: p.read_bytes() for p in output.iterdir()}, previous)
            self.assertEqual({p: p.read_bytes() for p in originals}, originals)


if __name__ == '__main__':
    unittest.main()
