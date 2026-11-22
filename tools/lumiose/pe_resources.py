"""Extract the icon group and manifest from a PE file's resources into an .ico and a .manifest."""
import struct, sys
exe, ico_out, man_out = sys.argv[1:4]
d = open(exe, 'rb').read()
pe = struct.unpack_from('<I', d, 0x3c)[0]
nsec = struct.unpack_from('<H', d, pe + 6)[0]; opt = struct.unpack_from('<H', d, pe + 20)[0]
rva_rsrc = struct.unpack_from('<I', d, pe + 24 + 112 + 2 * 8)[0]  # data directory 2 (PE32+)
secs = []
for i in range(nsec):
    o = pe + 24 + opt + i * 40
    vsize, va, rsize, raw = struct.unpack_from('<IIII', d, o + 8); secs.append((va, max(vsize, rsize), raw))
def off(rva):
    for va, size, raw in secs:
        if va <= rva < va + size: return raw + rva - va
    raise ValueError(hex(rva))
base = off(rva_rsrc)
def entries(o):
    named, ids = struct.unpack_from('<HH', d, base + o + 12)
    for i in range(named + ids):
        name, target = struct.unpack_from('<II', d, base + o + 16 + i * 8)
        yield name, target
def leaf_data(target):  # follow subdirectories to the first data entry
    while target & 0x80000000:
        target = next(entries(target & 0x7fffffff))[1]
    rva, size = struct.unpack_from('<II', d, base + target)
    return d[off(rva):off(rva) + size]
types = {n: t for n, t in entries(0)}
icons = {n: leaf_data(t) for n, t in entries(types[3] & 0x7fffffff)}   # RT_ICON
group = leaf_data(next(entries(types[14] & 0x7fffffff))[1])            # RT_GROUP_ICON
manifest = leaf_data(types[24])                                         # RT_MANIFEST
_, _, count = struct.unpack_from('<HHH', group, 0)
hdr = struct.pack('<HHH', 0, 1, count); body = b''; offset = 6 + 16 * count
for i in range(count):
    w, h, cc, r, planes, bits, size, nid = struct.unpack_from('<BBBBHHIH', group, 6 + i * 14)
    img = icons[nid]; hdr += struct.pack('<BBBBHHII', w, h, cc, r, planes, bits, len(img), offset + len(body)); body += img
open(ico_out, 'wb').write(hdr + body); open(man_out, 'wb').write(manifest)
print(count, 'icon images,', len(manifest), 'byte manifest')
