#!/bin/sh
# Builds "Lumiose Online.exe" (windows_launcher.c + splash_draw.h) with clang and lld only - no MSYS2, no C library.
#   tools/lumiose/build_windows_launcher.sh <release folder> <out.exe>
# <release folder>: an extracted ZA Recomp release. Its zig/rt has the Windows import libraries kernel32.lib and
# user32.lib; gdi32.lib is made here from the functions the launcher uses. The icon and manifest come from
# lumiose_icon.ico and windows.manifest beside this script, or else from that release's own "Lumiose Online.exe"
# (tools/lumiose/pe_resources.py).
# Needs: clang, lld-link, llvm-dlltool, llvm-rc (LLVM 15 or newer), python3.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
release=$1
out=$2
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if [ -f "$here/lumiose_icon.ico" ] && [ -f "$here/windows.manifest" ]; then
    cp "$here/lumiose_icon.ico" "$here/windows.manifest" "$work/"
else
    python3 -I "$here/pe_resources.py" "$release/Lumiose Online.exe" "$work/lumiose_icon.ico" "$work/windows.manifest"
fi
cp "$here/windows_launcher.rc" "$work/"
(cd "$work" && llvm-rc -no-preprocess -fo launcher.res windows_launcher.rc)

cat > "$work/gdi32.def" <<'EOF'
LIBRARY gdi32.dll
EXPORTS
BitBlt
CreateCompatibleDC
CreateDIBSection
CreateFontW
GdiFlush
GetDeviceCaps
GetTextExtentPoint32W
SelectObject
SetBkMode
SetTextColor
TextOutW
EOF
llvm-dlltool -m i386:x86-64 -d "$work/gdi32.def" -l "$work/gdi32.lib"

clang --target=x86_64-pc-windows-msvc -O2 -Wall -Wextra -ffreestanding -fno-stack-protector -mno-stack-arg-probe \
      -fno-asynchronous-unwind-tables -DLUMIOSE_NO_CRT -I"$here/win32_min" -I"$here" \
      -c "$here/windows_launcher.c" -o "$work/launcher.obj"
lld-link -nologo -subsystem:windows -entry:wWinMainCRTStartup -nodefaultlib -machine:x64 -Brepro -opt:ref -opt:icf \
         -out:"$out" "$work/launcher.obj" "$work/launcher.res" \
         "$release/zig/rt/kernel32.lib" "$release/zig/rt/user32.lib" "$work/gdi32.lib"
echo "built $out"
