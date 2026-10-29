import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_dos_device_with_spaces_before_extension(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/"bad.zip"
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr("docs/CON .txt","not safe")
            with zipfile.ZipFile(archive) as z, self.assertRaisesRegex(ValueError,"unsafe"):
                github._validated_zip_members(z)


if __name__ == "__main__": unittest.main()
