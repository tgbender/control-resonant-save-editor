"""Build a source-only ZIP from an explicit allowlist, with a privacy preflight."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = (
    '.gitattributes', '.gitignore', 'README.md', 'FORMAT.md', 'LICENSE',
    'THIRD_PARTY_NOTICES.md', 'Launch Editor.cmd', 'resonant_save.py', 'editor_gui.py',
    'progression.py', 'cosmetics.py', 'artist_abilities.py', 'alternate_abilities.py',
    'cityhash64.py', 'identified_items.json', 'cosmetic_definitions.json',
    'progression_definitions.json', 'fact_defaults.json', 'test_editor.py',
    'package_release.py', 'test_packaging.py',
)
IGNORED = {'.git', '__pycache__', '.venv', 'dist'}
PATTERNS = {
    'Windows user path': r'(?i)[a-z]:[\\/]+users[\\/]+[a-z0-9_.-]+',
    'Unix home path': r'/(?:home|Users)/[a-zA-Z0-9_.-]+/',
    'Steam account folder': r'(?i)userdata[\\/]+[0-9]+[\\/]',
    'Steam64 identifier': r'\b7656119[0-9]{10}\b',
    'Email address': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    'GitHub token': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
    'Private key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
}


def scan_text(text):
    return [label for label, pattern in PATTERNS.items() if re.search(pattern, text)]


def collect(root):
    root = Path(root)
    actual = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(part in IGNORED for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink excluded: {relative.as_posix()}')
        if path.is_file():
            actual.add(relative.as_posix())
    expected = set(FILES)
    if 'SHA256SUMS.json' in actual:
        # A previously extracted release includes this generated manifest.
        # Validate its shape, then regenerate it from current source bytes.
        manifest = json.loads((root / 'SHA256SUMS.json').read_text(encoding='utf8'))
        if not isinstance(manifest, dict) or set(manifest) != expected or not all(
            isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value)
            for value in manifest.values()
        ):
            raise ValueError('Invalid generated release manifest')
        actual.remove('SHA256SUMS.json')
    if actual != expected:
        raise ValueError(f'Release inventory mismatch. Missing: {sorted(expected-actual)}; unexpected: {sorted(actual-expected)}')
    result = {}
    for name in FILES:
        path = root / name
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            raise ValueError(f'Unsafe release path: {name}')
        data = path.read_bytes()
        findings = scan_text(data.decode('utf8'))
        if findings:
            raise ValueError(f'Privacy scan failed for {name}: {", ".join(findings)}')
        result[name] = data
    return result


def build(root=ROOT):
    root = Path(root)
    files = collect(root)
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    files['SHA256SUMS.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output = root / 'dist' / 'control-resonant-save-editor-source.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            # Fixed metadata avoids retaining source timestamps or owner details.
            info = zipfile.ZipInfo('control-resonant-save-editor/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive verification failed')
        for name, data in files.items():
            if archive.read('control-resonant-save-editor/' + name) != data:
                raise ValueError('Archive content mismatch')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    print(f'Packaged {len(FILES)} source files; privacy scan and ZIP verification passed.')
    print(f'dist/{output.name}')
    return output


if __name__ == '__main__':
    build()
