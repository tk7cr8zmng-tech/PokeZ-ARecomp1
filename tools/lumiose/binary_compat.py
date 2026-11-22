"""Discover supported raw module ABI/camera/CFG structure, never from build IDs.

No game execution. Switch recovery uses the generator's bounded ARM64 emulator
on the NSO image and its private scratch only; no host/native function calls.
"""
import bisect
import hashlib
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent.parent / 'python-deps'), str(HERE.parent)]
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64_const import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG

MAX_TEXT = 32 << 20
MAX_CAMERA = 64
MAX_TABLES = 512
MAX_CASES = 4096
IMPORTS = ('vmp_recomp_camera_find', 'vmp_recomp_name_ready')


def _decoder():
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    return md


def _branch(word, pc):
    value = word & 0x3ffffff
    return pc + (value - (1 << 26) if value & (1 << 25) else value) * 4


def _text(module, offset):
    lo, size = module.text
    return lo <= offset < lo + size and offset % 4 == 0


def classify_abi(module):
    qualified = []
    for name in IMPORTS:
        indices = [i for i, symbol in enumerate(module.syms) if symbol[0] == name and symbol[2] == 0]
        if len(indices) > 1:
            raise ValueError('Ambiguous native ABI import: ' + name)
        if not indices:
            qualified.append(False)
            continue
        relocs = [r for r in module.relocs if r[2] == indices[0]]
        if not relocs or any(r[1] not in (257, 1025, 1026) or r[3] != 0 or
                             r[0] % 8 or not module.rodata[0] <= r[0] <= len(module.image) - 8 for r in relocs):
            raise ValueError('Invalid native ABI import relocation: ' + name)
        qualified.append(True)
    if any(qualified) and not all(qualified):
        raise ValueError('Partial native ABI: camera_find and name_ready must both be qualified')
    return 'native' if all(qualified) else 'legacy'


def _starts(module, words):
    # Same seed sources as gen.Module.boundaries, plus all direct BL targets.
    from analyze import eh_frame_functions
    lo, size = module.text
    found = {lo}
    found.update(x for x in eh_frame_functions(module) if _text(module, x))
    for symbol in module.syms:
        if symbol[2] and symbol[1] & 15 == 2 and _text(module, symbol[3]):
            found.add(symbol[3])
    for off, kind, symbol, addend in module.relocs:
        if kind == 1027 and _text(module, addend):
            found.add(addend)
    for i, word in enumerate(words):
        if word >> 26 == 0b100101:
            target = _branch(word, lo + i * 4)
            if _text(module, target):
                found.add(target)
    return sorted(found)


def _reg(ins, operand):
    return ins.reg_name(operand.reg) if operand.type == ARM64_OP_REG else None


def _same_reg(a, b):
    return a == b or (a and b and a[0] in 'wx' and b[0] in 'wx' and a[1:] == b[1:])


def _stack_arg(insns, before, register, depth=0):
    if register == 'sp':
        return 0
    if depth > 8:
        return None
    for j in range(before - 1, max(-1, before - 384), -1):
        ins = insns[j]
        if not any(_same_reg(ins.reg_name(r), register) for r in ins.regs_access()[1]):
            continue
        op = ins.operands
        if ins.mnemonic == 'mov' and len(op) == 2 and op[1].type == ARM64_OP_REG:
            return _stack_arg(insns, j, _reg(ins, op[1]), depth + 1)
        if ins.mnemonic == 'add' and len(op) == 3 and op[2].type == ARM64_OP_IMM:
            base = _stack_arg(insns, j, _reg(ins, op[1]), depth + 1)
            if base is not None:
                return base + op[2].imm
        return None
    return None


def _camera_string_refs(module, insns):
    constants = {}
    result = []
    lo, size = module.rodata
    for ins in insns:
        op = ins.operands
        value = None
        if ins.mnemonic in ('adrp', 'adr') and len(op) == 2 and op[1].type == ARM64_OP_IMM:
            value = op[1].imm
        elif ins.mnemonic == 'add' and len(op) == 3 and op[2].type == ARM64_OP_IMM:
            prior = constants.get(_reg(ins, op[1]))
            if prior is not None:
                value = prior + op[2].imm
        elif ins.mnemonic == 'mov' and len(op) == 2 and op[1].type == ARM64_OP_REG:
            value = constants.get(_reg(ins, op[1]))
        for register in ins.regs_access()[1]:
            constants.pop(ins.reg_name(register), None)
        if value is not None:
            constants[_reg(ins, op[0])] = value
            if lo <= value < lo + size:
                raw = bytes(module.image[value:min(value + 256, lo + size)]).split(b'\0', 1)[0]
                if raw.startswith(b'[violetmp][camera] search '):
                    result.append((ins.address, value, raw.decode('utf-8', 'replace')))
    return result


def _load(ins, stack_offset):
    op = ins.operands
    return ins.mnemonic == 'ldr' and len(op) == 2 and op[1].type == ARM64_OP_MEM and \
        ins.reg_name(op[1].mem.base) == 'sp' and op[1].mem.disp == stack_offset


def discover_camera(module, starts=None):
    lo, size = module.text
    if not 0 < size <= MAX_TEXT or size % 4 or lo + size > len(module.image):
        raise ValueError('Native executable text outside discovery bounds')
    words = struct.unpack_from('<' + str(size // 4) + 'I', module.image, lo)
    starts = _starts(module, words) if starts is None else starts
    md = _decoder()
    wrappers = set()
    # libnx QueryMemory ABI: preserve x1 pointer, svc6, recover pointer in x2,
    # store returned page info w1, return. Validate instruction operands too.
    for i, word in enumerate(words):
        if word != 0xd40000c1 or i < 1 or i + 4 > len(words):
            continue
        at = lo + i * 4 - 4
        ins = list(md.disasm(bytes(module.image[at:at + 20]), at))
        if [(x.mnemonic, x.op_str) for x in ins] == [
            ('str', 'x1, [sp, #-0x10]!'), ('svc', '#6'), ('ldr', 'x2, [sp], #0x10'),
            ('str', 'w1, [x2]'), ('ret', '')]:
            wrappers.add(at)
    callers = {}
    for i, word in enumerate(words):
        pc = lo + i * 4
        if word >> 26 == 0b100101 and _branch(word, pc) in wrappers:
            start = starts[bisect.bisect_right(starts, pc) - 1]
            callers.setdefault(start, []).append(pc)
    if not wrappers:
        if any(word == 0xd40000c1 for word in words) or any('querymemory' in symbol[0].lower() for symbol in module.syms):
            raise ValueError('QueryMemory exists with an unsupported wrapper/import ABI')
        return [], [[lo, bytes(module.image[lo:lo + 4]).hex()]], dict(returns=[], proof='Full text has no SVC6; no QueryMemory import')
    candidates = []
    for start, calls in callers.items():
        j = bisect.bisect_right(starts, start)
        end = starts[j] if j < len(starts) else lo + size
        if end - start > 0x10000:
            continue
        insns = list(md.disasm(bytes(module.image[start:end]), start))
        refs = _camera_string_refs(module, insns)
        if not refs:
            continue
        if not any(x.mnemonic == 'mov' and '#0x7fffffffff' in x.op_str for x in insns):
            raise ValueError('Camera search lacks the bounded39-bit address-map traversal')
        by_pc = {x.address: i for i, x in enumerate(insns)}
        selected = {}
        for call in calls:
            i = by_pc[call]
            mi = _stack_arg(insns, i, 'x0')
            pi = _stack_arg(insns, i, 'x1')
            if mi is None or pi is None or mi == pi:
                continue
            tail = [x for x in insns[i + 1:i + 14] if x.mnemonic != 'nop']
            if len(tail) < 6 or tail[0].mnemonic != 'cbnz' or tail[0].op_str.split(',')[0] != 'w0':
                continue
            if not _load(tail[1], mi + 8) or tail[2].mnemonic != 'cbz' or \
               _reg(tail[1], tail[1].operands[0]) != _reg(tail[2], tail[2].operands[0]):
                continue
            # MemoryInfo field dataflow distinguishes the whole-map DeviceBytes
            # and Scannable loops from point Readable/ScanHeap queries.
            device = _load(tail[3], mi + 20) and _load(tail[4], mi + 28) and _load(tail[5], mi)
            outer = _load(tail[3], mi + 24) and _load(tail[4], mi)
            if device:
                if not any(x.mnemonic == 'and' and x.operands[-1].type == ARM64_OP_IMM and x.operands[-1].imm == 4 for x in tail[6:10]):
                    continue
            elif outer:
                if not any(x.mnemonic == 'and' and x.operands[-1].type == ARM64_OP_IMM and (x.operands[-1].imm & 0xffffffffffffffff) in (3, 0xffffffff00000003) for x in tail[5:10]):
                    continue
            else:
                continue
            selected[call + 4] = (mi, pi, tail[1].address)
        # Optimizers can split the first iteration and backedge query. A second
        # call must use the SAME actual output cells and branch on success to
        # the already-validated MemoryInfo.size load.
        for call in calls:
            if call + 4 in selected:
                continue
            i = by_pc[call]
            tail = insns[i + 1]
            if tail.mnemonic != 'cbz' or tail.op_str.split(',')[0] != 'w0':
                continue
            mi, pi = _stack_arg(insns, i, 'x0'), _stack_arg(insns, i, 'x1')
            target = tail.operands[1].imm
            if any((mi, pi, target) == value for value in selected.values()):
                selected[call + 4] = (mi, pi, target)
        if not selected:
            raise ValueError('Camera search queries exist but their map-loop ABI is unsupported')
        candidates.append(dict(start=start, end=end, returns=sorted(selected), string_refs=refs))
    if len(candidates) != 1:
        raise ValueError('Expected exactly one structurally qualified primary camera search; found ' + str(len(candidates)))
    selected = candidates[0]
    if len(selected['returns']) > MAX_CAMERA:
        raise ValueError('Camera query return count exceeds runtime contract')
    witnesses = [[off, bytes(module.image[off:off + 20]).hex()] for off in sorted(wrappers)]
    witnesses += [[off - 4, bytes(module.image[off - 4:off + 4]).hex()] for off in selected['returns']]
    return selected['returns'], witnesses, selected


def discover_switches(module, path, starts=None):
    import gen
    import unicorn as uc
    from unicorn import arm64_const as A
    m = gen.Module('lumiose', str(path), 0, simd='c')
    # The caller's image is authoritative too (allows honest shifted-image
    # fixtures). Real use passes the same NSO parser instance and file bytes.
    m.nso = module
    m.lo, size = module.text
    m.hi = m.lo + size
    m.words = struct.unpack_from('<' + str(size // 4) + 'I', module.image, m.lo)
    m.cache = {}
    starts = _starts(module, m.words) if starts is None else starts
    recovered = []
    total_cases = 0
    original = m._emulate_table
    md = _decoder()
    def seed_constant_spills(mu, entry, stop):
        # Generator recovery already seeds ADR/ADRP/ADD registers. Also retain
        # qualified constant table pointers spilled to this PRIVATE frame;
        # printf dispatchers reload one through FP. No unknown input is read.
        frame = gen.SCRATCH_MEM + 0x80000
        mu.reg_write(A.UC_ARM64_REG_X29, frame)
        constants = {'sp': frame, 'x29': frame}
        spills = {}
        for ins in md.disasm(bytes(module.image[entry:stop]), entry):
            op = ins.operands
            value = None
            if ins.mnemonic in ('adrp', 'adr') and len(op) == 2:
                value = op[1].imm
            elif ins.mnemonic == 'add' and len(op) == 3 and op[2].type == ARM64_OP_IMM:
                if _reg(ins, op[1]) in constants:
                    value = constants[_reg(ins, op[1])] + op[2].imm
            elif ins.mnemonic == 'mov' and len(op) == 2:
                if op[1].type == ARM64_OP_REG:
                    value = constants.get(_reg(ins, op[1]))
                elif op[1].type == ARM64_OP_IMM:
                    value = op[1].imm
            if ins.mnemonic == 'str' and len(op) == 2 and op[1].type == ARM64_OP_MEM:
                base = constants.get(ins.reg_name(op[1].mem.base))
                if base is not None and frame <= base + op[1].mem.disp <= frame + 0x1000 - 8:
                    address = base + op[1].mem.disp
                    known = constants.get(_reg(ins, op[0]))
                    if known is None:
                        spills.pop(address, None)
                    elif 0 <= known < len(module.image):
                        spills[address] = known
            for register in ins.regs_access()[1]:
                name = ins.reg_name(register)
                if name not in ('sp', 'x29'):
                    constants.pop(name, None)
            if value is not None and op and _reg(ins, op[0]) not in ('sp', 'x29'):
                constants[_reg(ins, op[0])] = value
            if ins.mnemonic in ('bl', 'blr'):
                for reg in range(19):
                    constants.pop('x' + str(reg), None)
        for address, value in spills.items():
            mu.mem_write(address, struct.pack('<Q', value))
    def traced(br, entry, end, start, index, count, set_at):
        nonlocal total_cases
        if not 1 <= count <= MAX_CASES:
            return None
        total_cases += count
        if total_cases > 65536 or br - entry > 0x10000:
            raise ValueError('Bounded CFG recovery budget exceeded')
        mu = m.emu()
        # The original helper overwrites the bounded index AT the guard. Skip
        # dead pre-guard character/input computation that would only be replaced
        # by that same index; preserve all actual lookup instructions afterwards.
        if set_at > start:
            start = set_at
        seed_constant_spills(mu, entry, start)
        reads = {}
        def record(emulator, access, address, width, value, user):
            if width in (1, 2, 4) and 0 <= address <= len(module.image) - width:
                pc = emulator.reg_read(A.UC_ARM64_REG_PC)
                reads.setdefault((pc, width), set()).add(address)
        hook = mu.hook_add(uc.UC_HOOK_MEM_READ, record)
        try:
            targets = original(br, entry, end, start, index, count, set_at)
        finally:
            mu.hook_del(hook)
        if not targets:
            return targets
        rows = set()
        for (pc, width), addresses in reads.items():
            if len(addresses) != count:
                continue
            table = min(addresses)
            if addresses != set(range(table, table + width * count, width)):
                continue
            for fmt in {1: ('b', 'B'), 2: ('h', 'H'), 4: ('i', 'I')}[width]:
                values = struct.unpack_from('<' + str(count) + fmt, module.image, table)
                anchor = min(targets) - min(values) * 4
                if _text(module, anchor) and {anchor + v * 4 for v in values} == set(targets):
                    rows.add((table, count, fmt, anchor))
        if not rows:
            raise ValueError('Recovered switch targets but no exact bounded physical table at ' + hex(br))
        # Signed/unsigned encodings with all-positive cells are equivalent;
        # choose signed deterministically, retaining the actual target proof.
        row = sorted(rows, key=lambda r: (r[0], r[1], r[2].isupper(), r[3]))[0]
        recovered.append(dict(branch=br, table=list(row), targets=targets))
        return targets
    m._emulate_table = traced
    def guarded_fallthrough(br, entry, end):
        # Same guard/CMP decoder as gen._jump_table_fallthrough, using its shared
        # _emulate_table instead of the older duplicate pre-guard executor. The
        # checked index is injected at CMP, never obtained from synthetic input.
        guard = None
        at = br - 4
        while at >= entry and br - at <= 4 * 16:
            word = m.word(at)
            if word & 0xff000010 == 0x54000000 and word & 15 in (8, 2):
                guard = at
                break
            if m.lift(at).kind in ('b', 'bl', 'blr', 'br', 'ret', 'trap'):
                return None
            at -= 4
        if guard is None:
            return None
        at = guard - 4
        while at >= entry and guard - at <= 4 * 8:
            word = m.word(at)
            if word & 0x7f80001f == 0x7100001f:
                if word >> 22 & 1:
                    return None
                limit = word >> 10 & 0xfff
                count = limit + 1 if m.word(guard) & 15 == 8 else limit
                if not 1 <= count <= MAX_CASES:
                    return None
                return m._emulate_table(br, entry, end, at, word >> 5 & 31, count, at)
            if m.lift(at).kind != 'op':
                return None
            at -= 4
        return None
    m._jump_table_fallthrough = guarded_fallthrough
    unresolved = []
    for i, word in enumerate(m.words):
        if word & 0xfffffc1f != 0xd61f0000:
            continue
        pc = m.lo + i * 4
        entry = starts[bisect.bisect_right(starts, pc) - 1]
        if not m.computed_target(pc, entry):
            continue
        prior = list(md.disasm(bytes(module.image[max(entry, pc - 12):pc]), max(entry, pc - 12)))
        # ADD xTarget,xObject,xVtableSlot without an index scale is an indirect
        # method/tail dispatch, not a bounded relative jump table.
        if not any(x.mnemonic == 'add' and len(x.operands) == 3 and x.operands[2].type == ARM64_OP_REG and
                   x.operands[2].shift.value == 2 for x in prior):
            continue
        if not m.jump_table(pc, entry, m.hi):
            unresolved.append(pc)
        if len(recovered) > MAX_TABLES:
            raise ValueError('Switch discovery exceeds bounded table count')
    if unresolved:
        raise ValueError('Unsupported computed branch table(s): ' + ','.join(hex(x) for x in unresolved[:16]))
    tables = sorted({tuple(r['table']) for r in recovered})
    targets = sorted({target for record in recovered for target in record['targets']})
    witnesses = [[r['branch'] - 4, bytes(module.image[r['branch'] - 4:r['branch'] + 4]).hex()] for r in recovered]
    return [list(row) for row in tables], targets, witnesses, recovered


def _bootstrap_entries(module, starts):
    """Reachable direct targets in the NSO header stub before normal functions.

    gen starts from callable/unwind seeds; exception dispatch in the handwritten
    module header can precede its first such seed. Decode that tiny prefix too.
    """
    lo, size = module.text
    first = min((x for x in starts if x > lo), default=lo + size)
    if first - lo > 0x1000:
        first = lo + 0x1000
    word = struct.unpack_from('<I', module.image, lo)[0]
    if word & 0xfc000000 != 0x14000000:
        return [], []
    pending = [lo]
    visited = set()
    targets = set()
    witnesses = []
    decoder = _decoder()
    while pending:
        pc = pending.pop()
        if pc in visited:
            continue
        visited.add(pc)
        if len(visited) > 256:
            raise ValueError('Module bootstrap prefix exceeds bounded decode')
        if not _text(module, pc):
            raise ValueError('Module bootstrap branches outside executable text')
        if pc >= first:
            targets.add(pc)
            continue
        word = struct.unpack_from('<I', module.image, pc)[0]
        instruction = next(decoder.disasm(bytes(module.image[pc:pc + 4]), pc), None)
        if instruction is None or instruction.mnemonic in ('udf', 'ret', 'br'):
            continue
        branch = None
        unconditional = False
        if word & 0x7c000000 == 0x14000000:
            branch = _branch(word, pc)
            unconditional = word >> 26 == 0b000101
        elif word & 0xff000010 == 0x54000000 or word & 0x7e000000 == 0x34000000:
            value = word >> 5 & 0x7ffff
            branch = pc + (value - (1 << 19) if value & (1 << 18) else value) * 4
        elif word & 0x7e000000 == 0x36000000:
            value = word >> 5 & 0x3fff
            branch = pc + (value - (1 << 14) if value & (1 << 13) else value) * 4
        if branch is not None:
            if not _text(module, branch):
                raise ValueError('Module bootstrap direct target outside text')
            pending.append(branch)
            witnesses.append([pc, bytes(module.image[pc:pc + 4]).hex()])
        if not unconditional:
            pending.append(pc + 4)
    return sorted(targets), witnesses


def discover_profile(module, path, *, reference=None):
    # Reference accepted for orchestration compatibility, never ID/signature lookup.
    kind = classify_abi(module)
    cameras, witnesses, camera_report = discover_camera(module)
    tables, entries, table_witnesses, report = discover_switches(module, path)
    witnesses += table_witnesses
    words = struct.unpack_from('<' + str(module.text[1] // 4) + 'I', module.image, module.text[0])
    bootstrap, bootstrap_witnesses = _bootstrap_entries(module, _starts(module, words))
    entries = sorted(set(entries) | set(bootstrap))
    witnesses += bootstrap_witnesses
    return dict(module_kind=kind, camera_query_returns=cameras, switch_tables=tables,
                additional_function_entries=entries, witnesses=witnesses,
                name_preservation_verified=False,
                discovery=dict(method='raw-aarch64-query-abi-and-generator-cfg',
                    camera=camera_report, jump_tables=report, bootstrap_entries=bootstrap,
                    name_semantics='Native imports classified; independent name-preservation attestation NOT inferred'))
