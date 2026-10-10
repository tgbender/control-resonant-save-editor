import shutil
import tempfile
from pathlib import Path
import unittest
import package_release as release


class PackagingTests(unittest.TestCase):
    def test_inventory_and_scan_pass(self):
        self.assertEqual(set(release.collect(release.ROOT)), set(release.FILES))

    def test_identifiers_are_detected(self):
        examples = [
            'C:' + '\\' + 'Users' + '\\' + 'ExamplePerson' + '\\Documents',
            '/home/' + 'exampleperson' + '/project',
            'userdata/' + '12345678' + '/game',
            '7656119' + '1234567890',
            'example' + '@' + 'example.invalid',
            'ghp_' + 'x' * 30,
        ]
        for text in examples:
            self.assertTrue(release.scan_text(text))

    def test_unexpected_files_stop_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in release.FILES:
                dest = root/name; dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(release.ROOT/name, dest)
            (root/'personal-note.txt').write_text('Should never be published')
            with self.assertRaises(ValueError): release.collect(root)


if __name__ == '__main__':
    unittest.main()
