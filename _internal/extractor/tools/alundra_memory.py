#!/usr/bin/env python3
"""Read-only address helpers based on the archived Alundra research.

No emulator connection or game-revision verification is performed. All flag/item
translations are arithmetic hypotheses until validated against the correct game.
Uses only the Python standard library; requires Python 3.10+.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

RAM_SIZE = 0x200000
FLAG_BASE = 0x801DD334
ITEM_BASE = 0x801DD830
ITEM_COUNT = 0x5A
HEADER_SIZE = 0x800

def number(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use decimal or 0x-prefixed hexadecimal.') from exc

def physical(address: int) -> int:
    """Accept only first-2-MiB physical RAM, KSEG0 or KSEG1 aliases."""
    if 0 <= address < RAM_SIZE:
        return address
    for base in (0x80000000, 0xA0000000):
        if base <= address < base + RAM_SIZE:
            return address - base
    raise ValueError('Address is outside the supported 2 MiB RAM aliases.')

def decode_flag(code: int) -> dict:
    if not 0 <= code <= 0xFFFF:
        raise ValueError('Event code must be an unsigned 16-bit value.')
    address = FLAG_BASE + code // 8
    return {
        'event_code': f'0x{code:04X}', 'runtime_kseg0': f'0x{address:08X}',
        'physical_offset': f'0x{physical(address):08X}', 'bit': code & 7,
        'mask': f'0x{1 << (code & 7):02X}',
        'status': 'arithmetic only; does not prove that this operand is an event flag',
    }

def encode_flag(address: int, bit: int) -> int:
    if not 0 <= bit <= 7:
        raise ValueError('Bit index must be 0..7; non-normalized bit-8 aliases are rejected.')
    delta = physical(address) - physical(FLAG_BASE)
    code = delta * 8 + bit
    if not 0 <= code <= 0xFFFF:
        raise ValueError('Address is outside the arithmetic range of this 16-bit flag encoding.')
    return code

def item_address(item_id: int) -> dict:
    if not 0 <= item_id < ITEM_COUNT:
        raise ValueError('Item ID must be 0x00..0x59.')
    a = ITEM_BASE + 4 * item_id
    return {
        'item_id': f'0x{item_id:02X}', 'nominal_runtime_slot': f'0x{a:08X}',
        'nominal_physical_offset': f'0x{physical(a):08X}',
        'item_info8': f'0x{0x800C7DE4 + 8 * item_id:08X}',
        'slot_tier_info10': f'0x{0x800BBE50 + 10 * item_id:08X}',
        'status': 'nominal arithmetic addresses; effect pickups may use other authoritative counters',
    }

def parse_exe(data: bytes) -> dict:
    if len(data) < HEADER_SIZE or data[:8] != b'PS-X EXE':
        raise ValueError('Expected a PS-X EXE with a complete 0x800-byte header.')
    entry, gp, load, size = struct.unpack_from('<4I', data, 0x10)
    if size == 0:
        raise ValueError('Header reports an empty payload.')
    if size > len(data) - HEADER_SIZE:
        raise ValueError('Header load size exceeds the available file payload.')
    if load + size > 0x100000000:
        raise ValueError('Header payload wraps the 32-bit address space.')
    return {'entry_pc': entry, 'initial_gp': gp, 'load_address': load,
            'load_size': size, 'file_size': len(data), 'payload_file_offset': HEADER_SIZE}

def offset_to_runtime(info: dict, offset: int) -> int:
    relative = offset - HEADER_SIZE
    if not 0 <= relative < info['load_size']:
        raise ValueError('File offset is outside the header-declared load payload.')
    return info['load_address'] + relative

def runtime_to_offset(info: dict, address: int) -> int:
    relative = address - info['load_address']
    if not 0 <= relative < info['load_size']:
        raise ValueError('Runtime address is outside this EXE payload; no cross-module translation attempted.')
    return HEADER_SIZE + relative

def diff_ram(before: bytes, after: bytes, start: int, end: int, limit: int = 256) -> dict:
    if len(before) != RAM_SIZE or len(after) != RAM_SIZE:
        raise ValueError('Both inputs must be raw 2 MiB RAM images, not savestates or memory-card saves.')
    if not 0 <= start <= end <= RAM_SIZE:
        raise ValueError('Range must be physical offsets within 0..0x200000; end is exclusive.')
    if limit < 1:
        raise ValueError('Limit must be positive.')
    changes=[]
    total=0
    for offset in range(start, end):
        a,b=before[offset],after[offset]
        if a == b:
            continue
        total += 1
        if len(changes) < limit:
            changes.append({'physical_offset': f'0x{offset:08X}',
                'runtime_kseg0': f'0x{0x80000000+offset:08X}', 'before': f'0x{a:02X}',
                'after': f'0x{b:02X}', 'changed_mask': f'0x{a^b:02X}',
                'set_mask': f'0x{(~a & b) & 0xFF:02X}', 'cleared_mask': f'0x{(a & ~b) & 0xFF:02X}'})
    return {'changed_byte_count': total, 'returned_count': len(changes),
            'truncated': total > len(changes), 'changes': changes,
            'status': 'byte differences only; no chest identity or persistence inferred'}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p=sub.add_parser('flag-decode');p.add_argument('code',type=number)
    p=sub.add_parser('flag-encode');p.add_argument('address',type=number);p.add_argument('bit',type=number)
    p=sub.add_parser('item-address');p.add_argument('item_id',type=number)
    for name in ('exe-info','exe-offset','exe-address'):
        p=sub.add_parser(name);p.add_argument('file',type=Path)
        if name != 'exe-info':p.add_argument('value',type=number)
    p=sub.add_parser('ram-diff');p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    p.add_argument('--start',type=number,default=0x1DD334)
    p.add_argument('--end',type=number,default=0x1DD448,help='Exclusive physical end offset')
    p.add_argument('--limit',type=int,default=256)
    args=parser.parse_args(argv)
    try:
        if args.command=='flag-decode':result=decode_flag(args.code)
        elif args.command=='flag-encode':result=decode_flag(encode_flag(args.address,args.bit))
        elif args.command=='item-address':result=item_address(args.item_id)
        elif args.command.startswith('exe-'):
            raw=args.file.read_bytes();info=parse_exe(raw)
            result={'file':str(args.file),'sha256':hashlib.sha256(raw).hexdigest(),
                'header':{k:f'0x{v:08X}' for k,v in info.items()},
                'revision_status':'not identified; a valid PS-X EXE header is not a US v1.1 fingerprint'}
            if args.command=='exe-offset':result['runtime_kseg0_or_header_address']=f'0x{offset_to_runtime(info,args.value):08X}'
            elif args.command=='exe-address':result['file_offset']=f'0x{runtime_to_offset(info,args.value):08X}'
        else:result=diff_ram(args.before.read_bytes(),args.after.read_bytes(),args.start,args.end,args.limit)
        print(json.dumps(result,indent=2));return 0
    except (OSError, ValueError) as exc:
        print(f'error: {exc}',file=sys.stderr);return 2

if __name__=='__main__':
    raise SystemExit(main())
