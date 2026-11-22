"""Names and advisory locking shared by the Windows and Linux launchers."""
import os

WINDOWS = os.name == 'nt'
EXECUTABLE = 'lasrecomp.exe' if WINDOWS else 'lasrecomp'
GAME_LIBRARY = 'lasgame.dll' if WINDOWS else 'lasgame.so'
MODULE_LIBRARY = 'lumiose.dll' if WINDOWS else 'lumiose.so'
ZIG = 'zig.exe' if WINDOWS else 'zig'


def old_cpu_build():
    """True when this machine's game code is the x86-64-v2 build (a CPU without AVX2 / FMA / BMI2). The runtime decides it
    (runtime/gamelib.c gamelib_old_cpu) and names such a library GAMELIB_ID-v2-<build ID> (runtime/gamelib.h). Lumiose's
    builds must then target x86-64-v2 and link the v2 runtime libraries (zig/rt-v2) too: x86-64-v3 code and zig/rt stop at
    the first AVX2 instruction on that CPU (exception c000001d, "Isolated startup reported a crash")."""
    if os.environ.get('LUMIOSE_TEST_CPU_V2') == '1':  # (testing the v2 build on a newer CPU)
        return True
    path = os.environ.get('LUMIOSE_GAME_ID_FILE')
    if path:
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                return '-v2-' in f.read()
        except OSError:
            pass
    return False


def zig_cpu():
    """The zig -mcpu for Lumiose's game-code builds on this machine (see old_cpu_build)."""
    return 'x86_64_v2' if old_cpu_build() else 'x86_64_v3'


def zig_runtime(zigroot):
    """The zig runtime libraries folder to link with on this machine: zig/rt-v2 for the x86-64-v2 build, else zig/rt."""
    from pathlib import Path
    return Path(zigroot) / ('rt-v2' if old_cpu_build() else 'rt')

def lock_file(file):
    if WINDOWS:
        import msvcrt
        file.seek(0)
        if not file.read(1):
            file.write(b'0')
            file.flush()
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
