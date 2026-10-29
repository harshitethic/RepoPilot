import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_bidi_formatting_controls(self):
        import zipfile
        for control in ("\u202e","\u202d","\u2066","\u2069"):
            with self.subTest(code=hex(ord(control))), tempfile.TemporaryDirectory() as d:
                archive=Path(d)/"bad.zip"
                with zipfile.ZipFile(archive,"w") as z: z.writestr("src/safe"+control+"ev1l.py","unsafe")
                with zipfile.ZipFile(archive) as z, self.assertRaisesRegex(ValueError,"unsafe"):
                    github._validated_zip_members(z)


if __name__ == "__main__": unittest.main()
