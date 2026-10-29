import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_unicode_superscript_device_names(self):
        import zipfile
        for name in ("COM¹.txt","COM².txt","COM³.txt","LPT¹.log","LPT².log","LPT³.log"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                archive=Path(d)/"bad.zip"
                with zipfile.ZipFile(archive,"w") as z: z.writestr(name,"unsafe")
                with zipfile.ZipFile(archive) as z, self.assertRaisesRegex(ValueError,"unsafe"):
                    github._validated_zip_members(z)


if __name__ == "__main__": unittest.main()
