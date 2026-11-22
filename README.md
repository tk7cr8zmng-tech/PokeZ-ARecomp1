# PokeZ-ARecomp1

A fork of **ZA Recomp – Lumiose Online** (launcher v0.1.38, bundled mod 1.5.8 build 8): a native Windows port of
*Pokémon Legends: Z-A* made by static recompilation. The Switch's ARM64 code is translated ahead of time into C and
compiled on your own PC. NVN graphics run on Vulkan, or on DirectX 12 as an option. No emulator runs while you play.

> [!IMPORTANT]
> **This repository contains no game files, keys, ROMs or generated game code, and never will.**
> You must dump Pokémon Legends: Z-A from **your own** Switch, along with your own `prod.keys`. Do not open issues
> asking for game files or keys, and do not commit or attach them.

## What's in this repo

| Folder | Contents |
|---|---|
| `runtime/` | HLE Switch services, NVN → Vulkan backend (`runtime/nvn/`), Maxwell shader translator, launcher UI |
| `tools/` | The recompiler (lifter, passes, NSO reader), Z-A patches and address tables, Lumiose tooling, tests |
| `gamelib-src/` | Headers and entry stub the generated game library is compiled against |
| `docs/` | PC controls guide, mod-update notes, upstream README and release notes |

The repo holds source only. The prebuilt runtime (`lasrecomp.exe`, `Lumiose Online.exe`, DLLs), the bundled
toolchains (Zig, Python) and the prebuilt Lumiose mod binary are **not** in git. Get them from the Windows release zip
(see below).

## Playing (Windows)

**Requirements:** Windows 10 1903+ or 11 (64-bit), an AVX2 CPU, a Vulkan 1.2+ GPU (1.3 recommended), 8 GB RAM
(16 GB recommended), about 12 GB free disk space.

1. Download `ZA-Recomp-windows.zip` from this repo's **Releases** page. Extract the whole `ZA Recomp` folder to a
   writable location, for example `C:\Games\ZA Recomp`. Don't use Program Files.
2. Prepare **your own** game dump in one folder:
   - base game (`.xci` or `.nsp`)
   - update **2.0.2** (`.nsp`)
   - *Mega Dimension* DLC (`.nsp`), optional
   - `prod.keys` from your Switch (plus `title.keys` if the launcher asks for it)

   Extracted `exefs` / `romfs` folders also work, but they don't include the DLC.
3. Open **Lumiose Online.exe**. Choose that folder (or drag it onto the window) and click **Set up the game**.
4. Leave the preparation window open. The first setup compiles the game code on your PC once, which takes 10–30
   minutes.
5. Click **Play**.

Your dump is only read, never changed. Saves are kept in `save/save_0/` and are the same format as on the Switch, so
you can move them with JKSV. The full guide is in [docs/UPSTREAM-README.md](docs/UPSTREAM-README.md).

### Default PC controls (Lumiose Online)

WASD to move, mouse for the camera, E to interact, Shift to sprint, Space to dodge, Ctrl to crouch, Tab to lock on.
Hold RMB to aim a Poké Ball and press LMB to throw. Moves are on 1–4, Q is Mega Evolution, R is Plus. Esc opens the
menu, I the Satchel, B the Boxes, P the Pokédex, M the map. Full list: [docs/PC-CONTROLS.md](docs/PC-CONTROLS.md).

### Troubleshooting

- Logs are written to `logs/play.log`. Attach it to bug reports.
- If the game crashes on Vulkan (often on AMD cards), set **F1 > Display > Graphics API: DirectX 12**.
- For low FPS, lower the internal resolution or turn on Dynamic resolution.

### Lumiose server

The launcher only lets the game talk to one Lumiose server, `135.148.167.226:27777` by default. To change it, create
`lumiose-server.txt` next to `Lumiose Online.exe` with one line such as `192.168.1.20:27777`, or set the
`LUMIOSE_SERVER` environment variable. Only an IPv4 address and port work, not a host name. The address must be the
one the Lumiose mod connects to, because the launcher blocks every other destination. Updates keep this file.

## Publishing a release (in-app updates)

**Update now** on the start screen installs releases from this repo. For each release:

1. Set the same version in `runtime/ui/launcher.mm` (`LARECOMP_VERSION`) and `tools/lumiose/entry.py`
   (`LAUNCHER_VERSION`), for example `v0.1.39`. `tools/lumiose/test_entry.py` checks that they match.
2. Build the release folder and zip it as `ZA-Recomp-windows.zip`, with a top-level `ZA Recomp` folder.
3. Create a GitHub release whose tag is exactly that version and upload the zip. GitHub records the zip's SHA-256,
   and the launcher refuses to install a download that doesn't match it.

## Building from source

The build uses MSYS2 UCRT64 (clang, SDL3, FFmpeg, shaderc, Vulkan headers) plus Python 3. See the
*Building from source* section of [docs/UPSTREAM-README.md](docs/UPSTREAM-README.md).

## Credits

- [Peiikai](https://github.com/peiikai): [LAS Recomp](https://github.com/peiikai/LASRecomp), the static recompiler
  and runtime this port is built on
- [Hexveil404](https://github.com/Hexveil404): the Pokémon Legends: Z-A port
- [TheMagnumChad](https://github.com/TheMagnumChad/PokeZ-ARecomp-Online): Lumiose Online
- All ZA Recomp contributors listed in the upstream README

## Legal

MIT licensed. See [LICENSE](LICENSE) and [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES). This project is not affiliated
with or endorsed by Nintendo, Game Freak, Creatures Inc. or The Pokémon Company. Pokémon is a trademark of its
respective owners. You must own the game.
