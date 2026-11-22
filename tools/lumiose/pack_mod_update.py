"""Append reviewed compatibility data to a raw NSO for the existing updater."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from native_compat import FOOTER, MAGIC, MAX_JSON, load_profile, read_update_profile, validate_candidate


def _module(path):
    # Use the SAME NSO parser and compatibility validator as auto_prepare.
    sys.path[:0] = [str(HERE.parent.parent / 'python-deps'), str(HERE.parent)]
    from nso import Nso
    return Nso(str(path))


def _identity(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns


def pack_update(nso, compatibility_profile, output):
    source = Path(nso).resolve(strict=True)
    profile_path = Path(compatibility_profile).resolve(strict=True)
    out = Path(output).resolve()
    if not source.is_file() or not profile_path.is_file():
        raise ValueError('A raw NSO file and reviewed compatibility JSON are required')
    if out in (source, profile_path) or out.exists():
        raise ValueError('Output must be a fresh separate file')
    original = _identity(source)
    if profile_path.stat().st_size > MAX_JSON:
        raise ValueError('Reviewed compatibility JSON exceeds 1 MiB')
    reviewed_bytes = profile_path.read_bytes()
    profile = load_profile(profile_path)
    if profile_path.read_bytes() != reviewed_bytes:
        raise ValueError('Reviewed compatibility profile changed during validation')
    info = read_update_profile(source)
    if info['embedded']:
        raise ValueError('Input already contains metadata; supply the original raw BASE NSO')
    accepted = validate_candidate(_module(source), source, profile)
    payload = json.dumps(accepted, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    if not 0 < len(payload) <= MAX_JSON:
        raise ValueError('Compatibility JSON must fit the launcher metadata bound')
    if _identity(source) != original or profile_path.read_bytes() != reviewed_bytes:
        raise ValueError('NSO/profile changed before packaging')
    out.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with out.open('xb') as dst:
            created = True
            digest = hashlib.sha256()
            length = 0
            with source.open('rb') as src:
                for block in iter(lambda: src.read(1 << 20), b''):
                    dst.write(block)
                    digest.update(block)
                    length += len(block)
            if length != info['base_length'] or digest.hexdigest() != accepted['sha256']:
                raise ValueError('BASE NSO changed during packaging')
            dst.write(payload)
            dst.write(FOOTER.pack(length, len(payload), MAGIC))
        if _identity(source) != original or profile_path.read_bytes() != reviewed_bytes:
            raise ValueError('NSO/profile changed during packaging')
        result = read_update_profile(out)
        if not result['embedded'] or result['profile'] != accepted or result['base_length'] != length:
            raise ValueError('Packed update failed the launcher round-trip reader')
        return dict(output=str(out), build_id=accepted['build_id'], build_id32=accepted['build_id32'],
                    base_length=length, base_sha256=accepted['sha256'], json_length=len(payload),
                    download_length=result['download_length'], download_sha256=result['download_sha256'],
                    reviewed_profile_sha256=hashlib.sha256(reviewed_bytes).hexdigest())
    except BaseException:
        if created:
            out.unlink()  # Only this invocation's fresh, incomplete output.
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nso', required=True, type=Path, help='Original raw BASE NSO from this exact build')
    parser.add_argument('--compatibility-profile', required=True, type=Path,
                        help='Reviewed CFG/ELF-derived compatibility JSON for the SAME build')
    parser.add_argument('--out', required=True, type=Path, help='Fresh packed server-update file')
    args = parser.parse_args(argv)
    try:
        result = pack_update(args.nso, args.compatibility_profile, args.out)
    except (OSError, ValueError, RuntimeError, AssertionError) as error:
        parser.exit(1, 'Cannot package native update: ' + str(error) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
