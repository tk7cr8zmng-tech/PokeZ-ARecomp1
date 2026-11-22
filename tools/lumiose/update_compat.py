"""Persist validated compatibility data with the exact prepared module version.
No URL/protocol changes: embedded update metadata and optional adjacent sidecars.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys


@dataclass(frozen=True)
class ProfileBinding:
    profile_path: Path
    runtime_path: Path
    build_id32: str
    native_sha256: str
    download_sha256: str
    version: tuple

    @property
    def build_id(self):
        return _api().canonical_build_id(bytes.fromhex(self.build_id32))

    @property
    def files(self):
        return ((self.profile_path, 'compatibility.json'), (self.runtime_path, 'native-profile.bin'))


def _api():
    import native_compat
    return native_compat


def read_candidate(candidate):
    return _api().read_update_profile(Path(candidate))


def sidecar(candidate, info, *, active=None):
    if info.get('profile') is not None:
        return None  # Embedded metadata is bound to this exact downloaded blob.
    path = Path(active) / 'compatibility.json' if active is not None else Path(str(candidate) + '.compat.json')
    return path if path.is_file() else None


def _module(path):
    root = Path(__file__).resolve().parents[2]
    for directory in (root / 'tools', root / 'python-deps'):
        value = str(directory)
        if value not in sys.path:
            sys.path.insert(0, value)
    from nso import Nso
    return Nso(Path(path))


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def _version(value):
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 0xffffffff:
        return tuple((value >> shift) & 255 for shift in (24, 16, 8, 0))
    if isinstance(value, str):
        value = value.split('.')
        if len(value) != 4 or any(not part.isdecimal() for part in value):
            raise RuntimeError('Compatibility version must identify four nonnegative integers')
        value = [int(part) for part in value]
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(type(part) is not int or part < 0 for part in value)):
        raise RuntimeError('Compatibility version must identify four nonnegative integers')
    return tuple(value)


def validate_prepared(work, result, candidate, expected_download_hash, info, profile_path=None):
    """Called only after auto_prepare and the existing staged/candidate checks."""
    keys = ('compatibility_abi_revision', 'compatibility_profile', 'runtime_profile')
    if not any(key in result for key in keys):
        if info.get('profile') is not None or profile_path is not None:
            raise RuntimeError('This update supplied compatibility metadata but preparation did not retain it')
        return None  # Existing unprofiled legacy preparation remains supported.
    if (result.get('compatibility_abi_revision') != 1
            or result.get('compatibility_profile') != 'compatibility.json'
            or result.get('runtime_profile') != 'native-profile.bin'):
        raise RuntimeError('Prepared compatibility outputs have an unsupported schema or path')
    work = Path(work)
    staged = work / 'input/exefs/subsdk9'
    api = _api()
    if (_sha(candidate) != expected_download_hash or info['download_sha256'] != expected_download_hash
            or result.get('download_sha256') != expected_download_hash
            or result.get('native_sha256') != info['base_sha256']
            or _sha(staged) != info['base_sha256']):
        raise RuntimeError('Compatibility metadata does not bind the unchanged downloaded/base module')
    with staged.open('rb') as stream:
        header = stream.read(0x60)
    if len(header) != 0x60 or header[:4] != b'NSO0':
        raise RuntimeError('Prepared compatibility module is not an NSO')
    full_id = header[0x40:0x60].hex()
    if result.get('build_id32') != full_id or result.get('build_id') != api.canonical_build_id(header[0x40:0x60]):
        raise RuntimeError('Prepared compatibility identity differs from the actual module')
    module = _module(staged)
    metadata = work / 'compatibility.json'
    canonical = api.validate_candidate(module, staged, api.load_profile(metadata))
    supplied = info.get('profile')
    if supplied is None and profile_path is not None:
        supplied = api.load_profile(profile_path)
    if supplied is not None and canonical != api.validate_candidate(module, staged, supplied):
        raise RuntimeError('Prepared compatibility metadata differs from the supplied validated profile')
    version = _version(result['version'])
    if canonical.get('version') is not None and _version(canonical['version']) != version:
        raise RuntimeError('Compatibility version differs from the actual native version')
    runtime = work / 'native-profile.bin'
    if canonical['schema'] == api.SCHEMA:
        if (result.get('module_kind') != canonical['module_kind']
                or result.get('native_abi') is not (canonical['module_kind'] == 'native')
                or result.get('camera_query_count') != len(canonical['camera_query_returns'])
                or result.get('runtime_profile_format') != 2):
            raise RuntimeError('Prepared ABI flags/camera count differ from binary discovery')
    expected_runtime = api.runtime_profile_bytes(canonical)
    if canonical['build_id32'] != full_id or runtime.read_bytes() != expected_runtime:
        raise RuntimeError('Prepared runtime profile is not the exact binary-validated record')
    return ProfileBinding(metadata, runtime, full_id, info['base_sha256'], expected_download_hash, version)


def bind_active(active, state, env):
    """Never inherit a profile from a different active module/version."""
    env.pop('LUMIOSE_NATIVE_PROFILE_PATH', None)
    active = Path(active)
    metadata, runtime = active / 'compatibility.json', active / 'native-profile.bin'
    if not metadata.exists() and not runtime.exists():
        return  # Old versions without profile files use the existing builtin/legacy route.
    if not metadata.is_file() or not runtime.is_file():
        raise RuntimeError('The active compatibility profile is incomplete')
    hashes = state.get('active_hashes', {})
    for name, path in (('compatibility.json', metadata), ('native-profile.bin', runtime)):
        if not hashes.get(name) or _sha(path) != hashes[name]:
            raise RuntimeError('The active compatibility profile failed verification')
    module_path = active / 'subsdk9'
    if _sha(module_path) != hashes.get('subsdk9'):
        raise RuntimeError('The active module failed compatibility verification')
    api = _api()
    canonical = api.validate_candidate(_module(module_path), module_path, api.load_profile(metadata))
    expected = api.runtime_profile_bytes(canonical)
    if runtime.read_bytes() != expected:
        raise RuntimeError('The active runtime profile differs from validated compatibility metadata')
    with module_path.open('rb') as stream:
        header = stream.read(0x60)
    if header[:4] != b'NSO0' or canonical['build_id32'] != header[0x40:0x60].hex() or api.canonical_build_id(header[0x40:0x60]) != state.get('build_id'):
        raise RuntimeError('The active runtime profile belongs to a different module')
    env['LUMIOSE_NATIVE_PROFILE_PATH'] = str(runtime.resolve())
