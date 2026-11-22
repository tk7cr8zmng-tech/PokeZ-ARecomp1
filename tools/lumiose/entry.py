"""Start the packaged launcher, preparing Lumiose after initial game setup."""
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
GAME_CODE_REVISION = 'launcher-title-offset-null-guard-v1'
LAUNCHER_VERSION = 'v0.1.39'  # (= runtime/ui/launcher.mm LARECOMP_VERSION and the release tag; test_entry.py checks)
sys.path[:0] = [str(ROOT / 'python-deps'), str(ROOT / 'tools' / 'lumiose')]
from auto_launch import launch
from platform_paths import EXECUTABLE, GAME_LIBRARY, lock_file


def log_event(message):
    try:
        logs = ROOT / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / 'lumiose-launch.log').open('a', encoding='utf-8') as f:
            f.write(f'{datetime.now().isoformat(timespec="seconds")} {message}\n')
    except OSError:
        pass  # Diagnostics must not stop the launcher.


# Pokemon Legends Z-A exefs/main build IDs (first 8 bytes; runtime/main.c). ZA Recomp runs all three; Lumiose needs 2.0.2.
ZA_202 = 'B1F12FD919EAE86A'
ZA_VERSIONS = {'7222E13ECF6ADB32': '1.0.0 (the base game without its update)', '8A1C86C437394B69': '2.0.0', ZA_202: '2.0.2'}


def check_game_version():
    """Stop with the fix when the set-up game is not 2.0.2: Lumiose cannot be prepared for it, and the player used to see only
    "Isolated startup reported a crash" (capture.log: "FATAL: Lumiose test requires the 2.0.2 game build")."""
    main = ROOT / 'extracted' / 'exefs' / 'main'
    try:
        with main.open('rb') as f:
            head = f.read(0x48)
    except OSError:
        return  # (no game set up: the launcher's own check reports that)
    if len(head) < 0x48 or head[:4] != b'NSO0':
        return
    build = head[0x40:0x48].hex().upper()
    if build == ZA_202:
        return
    version = ZA_VERSIONS.get(build, 'an unknown version (main ' + build + ')')
    log_event('Game files are ' + version + ', not 2.0.2')
    raise RuntimeError(
        'Your game files are Pokemon Legends Z-A ' + version + '. Lumiose Online needs the 2.0.2 update.\n'
        '  1. Close this window.\n'
        '  2. Delete (or rename) the "extracted" folder in ' + str(ROOT) + '.\n'
        '  3. Open Lumiose Online.exe again and choose the base game, the 2.0.2 update and the DLC together.\n'
        'Your saves are not changed.')


# The Lumiose relay the runtime may talk to (runtime/hle/lumiose_network.c: LUMIOSE_TEST_SERVER, an allow-list - every
# other destination is blocked). The mod (subsdk9) chooses where it connects; this must name that same IPv4:port.
DEFAULT_SERVER = '135.148.167.226:27777'
SERVER_FILE = 'lumiose-server.txt'  # (next to Lumiose Online.exe; an update's files never include it, so it is kept)


def normalize_server(value):
    """'a.b.c.d:port' in the exact form the runtime compares (plain decimal), or a ValueError naming the problem."""
    import ipaddress
    host, sep, port = value.strip().rpartition(':')
    if not sep or not host or not port.isdigit():
        raise ValueError(f'"{value.strip()}" is not an address and port like 135.148.167.226:27777')
    try:
        ip = ipaddress.IPv4Address(host)
    except ValueError:
        raise ValueError(f'"{host}" is not an IPv4 address (host names are not supported)') from None
    if not 1 <= int(port) <= 65535:
        raise ValueError(f'port {port} is outside 1-65535')
    return f'{ip}:{int(port)}'


def server_override():
    """The player's server choice: LUMIOSE_SERVER, else the first non-comment line of lumiose-server.txt; None when
    neither is set (the configured server is kept). An invalid value stops the launcher with the reason."""
    value, source = os.environ.get('LUMIOSE_SERVER', '').strip(), 'LUMIOSE_SERVER'
    if not value:
        path = ROOT / SERVER_FILE
        try:
            lines = path.read_text(encoding='utf-8-sig').splitlines()
        except OSError:
            lines = []
        value = next((l.strip() for l in lines if l.strip() and not l.lstrip().startswith('#')), '')
        source = str(path)
    if not value:
        return None
    try:
        return normalize_server(value)
    except ValueError as e:
        raise RuntimeError(f'The Lumiose server in {source} is invalid: {e}.') from None


def desktop_notice(title, message, error=False):
    if os.name == 'nt': return
    command = shutil.which('kdialog') if error else shutil.which('notify-send')
    if command:
        args = [command, '--error', title + '\n\n' + message] if error else [command, title, message]
        try: subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError: pass


def main():
    os.chdir(ROOT)
    # A runtime restarted by the launcher updater must return through this entry point once. Child runtimes inherit
    # this marker so they do not route back here again while the update notification still exists.
    os.environ['LUMIOSE_ENTRY_ACTIVE'] = LAUNCHER_VERSION
    os.environ['PYTHONPATH'] = str(ROOT / 'python-deps') + os.pathsep + os.environ.get('PYTHONPATH', '')
    mod = ROOT / 'lumiose'
    config = mod / 'config.json'
    state = mod / 'update-state.json'
    revision = mod / 'launcher-code-revision.txt'
    first_setup = not state.exists()
    current_revision = revision.read_text(encoding='utf-8').strip() if revision.is_file() else ''
    log_event(f'Launcher started; initial setup required: {first_setup}; game-code revision check required: {current_revision != GAME_CODE_REVISION}')
    if current_revision != GAME_CODE_REVISION:
        (ROOT / 'textures/prompts/.made').unlink(missing_ok=True)
    if first_setup or current_revision != GAME_CODE_REVISION:
        print('Checking game setup for this launcher. Keep this window open.', flush=True)
        if first_setup:
            print('Choose your own Pokémon Legends Z-A 2.0.2 game files; Lumiose will prepare automatically.', flush=True)
        env = os.environ.copy()
        env['LARECOMP_DATA_ROOT'] = str(ROOT)
        env['LUMIOSE_FIRST_SETUP'] = '1'
        for key in ('LUMIOSE_TEST_MODULE', 'LUMIOSE_TEST_LIBRARY', 'LARECOMP_GAME_LIB',
                    'LARECOMP_NO_LAUNCHER', 'LUMIOSE_TEST_OFFLINE_CAPTURE'):
            env.pop(key, None)
        if os.environ.get('LUMIOSE_RELEASE_TEST_PREPARE_ONLY') != '1':
            env.pop('LARECOMP_HIDDEN', None)
        with tempfile.TemporaryDirectory(prefix='game-check-', dir=mod) as temp:
            done = Path(temp) / 'ready'
            # The launcher changes to ROOT before writing this marker. A relative ASCII path also avoids passing a
            # potentially non-ASCII Windows installation path through the C runtime's narrow fopen().
            env['LUMIOSE_SETUP_DONE'] = os.path.relpath(done, ROOT)
            result = subprocess.run([str(ROOT / EXECUTABLE), str(ROOT / 'extracted')], cwd=ROOT, env=env)
            if result.returncode or not done.is_file() or not (ROOT / 'extracted' / (GAME_LIBRARY + '.id')).is_file():
                raise RuntimeError('Game setup was not completed. Start Lumiose Online again when you are ready.')
        log_event('Game setup check completed')
    check_game_version()  # 11-22: 2.0.2 only, with the fix, before any preparation
    server = server_override()
    if first_setup:
        log_event('Preparing bundled Lumiose for first launch')
        cmd = [sys.executable, str(ROOT / 'tools/lumiose/setup.py'), '--install', str(ROOT),
               '--zig', str(ROOT / 'zig'), '--server', server or DEFAULT_SERVER]
        desktop_notice('Lumiose Online', 'Preparing the online mod. This may take several minutes.')
        if subprocess.run(cmd, cwd=ROOT).returncode:
            raise RuntimeError('Lumiose preparation did not finish; see the message above.')
        log_event('Bundled Lumiose preparation completed')
    if not config.is_file():
        raise RuntimeError('Lumiose configuration is missing. Your save files have not been changed.')
    # Rewrite paths when the player moves the installed folder.
    import json
    cfg = json.loads(config.read_text(encoding='utf-8'))
    cfg.update(install=str(ROOT), reference=str(ROOT / 'lumiose/subsdk9'),
               vanilla=str(ROOT / 'extracted' / GAME_LIBRARY), zig=str(ROOT / 'zig'),
               cache=str(ROOT / 'extracted/.gamebuild'))
    if server and cfg.get('server') != server:
        log_event(f'Lumiose server set to {server} (was {cfg.get("server")})')
        cfg['server'] = server
    config.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')
    log_event('Checking active Lumiose build and updates')
    launch(config, prepare_only=os.environ.get('LUMIOSE_RELEASE_TEST_PREPARE_ONLY') == '1')
    log_event('Lumiose preparation completed; launcher started')
    if current_revision != GAME_CODE_REVISION:
        tmp = revision.with_suffix('.tmp')
        tmp.write_text(GAME_CODE_REVISION + '\n', encoding='utf-8')
        os.replace(tmp, revision)


if __name__ == '__main__':
    if os.name != 'nt' and not sys.stderr.isatty():
        log_dir = ROOT / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log = (log_dir / 'lumiose-launch.log').open('a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stderr = log
    try:
        lock_path = ROOT / 'lumiose' / 'update.lock'
        with lock_path.open('a+b') as lock:
            try: lock_file(lock)
            except OSError: raise RuntimeError('Another Lumiose launcher is already preparing an update')
            main()
    except Exception as e:
        log_event('Launcher failed: ' + str(e))
        print('\nLumiose could not start:', e, file=sys.stderr, flush=True)
        desktop_notice('Lumiose Online could not start', str(e) + '\nDetails: logs/lumiose-launch.log', error=True)
        if sys.stdin.isatty(): input('Press Enter to close this window. ')
        sys.exit(1)
