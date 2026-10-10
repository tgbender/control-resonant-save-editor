"""Keep personal paths, account identifiers, credentials, and save files out of the repository."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parent.parent
SKIPPED = {'.git', '.venv', '__pycache__', 'dist', 'build'}
PATTERNS = {
    'Windows user path': r'(?i)[a-z]:[\\/]+users[\\/]+[a-z0-9_.-]+',
    'Unix home path': r'/(?:home|Users)/[a-zA-Z0-9_.-]+/',
    'Steam account folder': r'(?i)userdata[\\/]+[0-9]+[\\/]',
    'Steam64 identifier': r'\b7656119[0-9]{10}\b',
    'Email address': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    'GitHub token': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
    'Private key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
}
SAVE_FILE = re.compile(r'-(?:persi-global|header|player|bundle-container)$|\.(?:chunk|bundle|rmdtoc|vdf)$')


def scan_text(text):
    return [label for label, pattern in PATTERNS.items() if re.search(pattern, text)]


def repository_files():
    for path in REPO.rglob('*'):
        if path.is_file() and not SKIPPED & set(path.relative_to(REPO).parts):
            yield path


class PrivacyTests(unittest.TestCase):
    def test_repository_has_no_private_identifiers_or_saves(self):
        for path in repository_files():
            relative = path.relative_to(REPO).as_posix()
            with self.subTest(file=relative):
                self.assertIsNone(SAVE_FILE.search(path.name), 'save or Steam file in repository')
                self.assertEqual(scan_text(path.read_bytes().decode('utf8')), [])

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
            self.assertTrue(scan_text(text), text)


if __name__ == '__main__':
    unittest.main()
