from .models import CameraFile, ProcessingStatus
from ..ports.exiftool_port import ExiftoolPort


class ExifFixer:

    def __init__(self, exiftool: ExiftoolPort):
        self._exiftool = exiftool

    def fix(self, file: CameraFile) -> CameraFile:
        fix = file.exif_fix
        if fix is None or not fix.has_fixes:
            file.status = ProcessingStatus.COMPLETED
            return file

        assert file.destination_path is not None
        file.status = ProcessingStatus.FIXING_EXIF
        self._exiftool.write_exif(
            file.destination_path,
            modify_date=fix.fixed_modify_date,
            datetime_original=fix.fixed_datetime_original,
            create_date=fix.fixed_create_date,
            exif_image_width=fix.fixed_width,
            exif_image_height=fix.fixed_height,
            make=fix.fixed_make,
            model=fix.fixed_model,
            lens_model=fix.fixed_lens_model,
            f_number=fix.fixed_f_number,
            user_comment=fix.fixed_user_comment,
        )
        actual = self._exiftool.read_exif(file.destination_path)
        for field, expected in (
            ("modify_date", fix.fixed_modify_date),
            ("datetime_original", fix.fixed_datetime_original),
            ("create_date", fix.fixed_create_date),
            ("exif_image_width", fix.fixed_width),
            ("exif_image_height", fix.fixed_height),
            ("make", fix.fixed_make),
            ("model", fix.fixed_model),
            ("lens_model", fix.fixed_lens_model),
            ("f_number", fix.fixed_f_number),
            ("user_comment", fix.fixed_user_comment),
        ):
            if expected is not None and getattr(actual, field) != expected:
                raise RuntimeError(f"EXIF verification failed for {field}")
        file.status = ProcessingStatus.COMPLETED
        return file
