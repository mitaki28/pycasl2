# ~*~ coding:utf-8 ~*~

import sys
from functools import wraps

from utils import l2a, a2l, get_bit
from argtypes import noarg, r, r1r2, adrx, radrx, strlen


def get_effective_address(m, adr, x):
    ''' 実効アドレスを返す '''
    return adr if x == 0 else a2l(adr + m.GR[x])


def get_value_at_effective_address(m, adr, x):
    ''' 実効アドレス番地の値を返す '''
    return m.memory[adr] if x == 0 else m.memory[a2l(adr + m.GR[x])]


def flags(result, logical=False, ZF=None, SF=None, OF=None):
    '''
    計算結果に応じたフラグを返す
    論理演算の場合は第二引数をTrueにする
    '''
    if ZF is None: ZF = (result == 0)
    if SF is None: SF = (get_bit(result, 15) == 0)
    if OF is None:
        if logical is True:
            OF = (result < 0 or 0xffff < result)
        else:
            OF = (result < -32768 or 0x7fff < result)
    return map(int, (ZF, SF, OF))


class Jump(Exception):
    def __init__(self, addr, result=None):
        self.addr = addr
        self.result = result


def instruction(opcode, opname, argtype):
    def _(ir):
        @wraps(ir)
        def __(machine):
            try:
                result = ir(machine, *argtype(machine))
            except Jump as jump:
                machine.PR = jump.addr
                result = jump.result
            else:
                machine.PR += argtype.size
            if result is not None:
                machine.ZF = machine.ZF if result[0] is None else result[0]
                machine.SF = machine.SF if result[1] is None else result[1]
                machine.OF = machine.OF if result[2] is None else result[2]
        __.opcode = opcode
        __.opname = opname
        __.argtype = argtype
        return __
    return _


@instruction(0x00, 'NOP', noarg)
def nop(machine):
    pass


@instruction(0x10, 'LD', radrx)
def ld2(machine, r, adr, x):
    machine.GR[r] = get_value_at_effective_address(machine, adr, x)
    return flags(machine.GR[r], OF=0)


@instruction(0x11, 'ST', radrx)
def st(machine, r, adr, x):
    machine.memory[get_effective_address(machine, adr, x)] = machine.GR[r]


@instruction(0x12, 'LAD', radrx)
def lad(machine, r, adr, x):
    machine.GR[r] = get_effective_address(machine, adr, x)


@instruction(0x14, 'LD', r1r2)
def ld1(machine, r1, r2):
    machine.GR[r1] = machine.GR[r2]
    return flags(machine.GR[r1], OF=0)


@instruction(0x20, 'ADDA', radrx)
def adda2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    result = l2a(machine.GR[r]) + l2a(v)
    machine.GR[r] = a2l(result)
    return flags(result)


@instruction(0x21, 'SUBA', radrx)
def suba2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    result = l2a(machine.GR[r]) - l2a(v)
    machine.GR[r] = a2l(result)
    return flags(result)


@instruction(0x22, 'ADDL', radrx)
def addl2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    result = machine.GR[r] + v
    machine.GR[r] = result & 0xffff
    return flags(result, logical=True)


@instruction(0x23, 'SUBL', radrx)
def subl2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    result = machine.GR[r] - v
    machine.GR[r] = result & 0xffff
    return flags(result, logical=True)


@instruction(0x24, 'ADDA', r1r2)
def adda1(machine, r1, r2):
    result = l2a(machine.GR[r1]) + l2a(machine.GR[r2])
    machine.GR[r1] = a2l(result)
    return flags(result)


@instruction(0x25, 'SUBA', r1r2)
def suba1(machine, r1, r2):
    result = l2a(machine.GR[r1]) - l2a(machine.GR[r2])
    machine.GR[r1] = a2l(result)
    return flags(result)


@instruction(0x26, 'ADDL', r1r2)
def addl1(machine, r1, r2):
    result = machine.GR[r1] + machine.GR[r2]
    machine.GR[r1] = result & 0xffff
    return flags(result, logical=True)


@instruction(0x27, 'SUBL', r1r2)
def subl1(machine, r1, r2):
    result = machine.GR[r1] - machine.GR[r2]
    machine.GR[r1] = result & 0xffff
    return flags(result, logical=True)


@instruction(0x30, 'AND', radrx)
def and2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    machine.GR[r] = machine.GR[r] & v
    return flags(machine.GR[r], OF=0)


@instruction(0x31, 'OR', radrx)
def or2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    machine.GR[r] = machine.GR[r] | v
    return flags(machine.GR[r], OF=0)


@instruction(0x32, 'XOR', radrx)
def xor2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    machine.GR[r] = machine.GR[r] ^ v
    return flags(machine.GR[r], OF=0)


@instruction(0x34, 'AND', r1r2)
def and1(machine, r1, r2):
    machine.GR[r1] = machine.GR[r1] & machine.GR[r2]
    return flags(machine.GR[r1], OF=0)


@instruction(0x35, 'OR', r1r2)
def or1(machine, r1, r2):
    machine.GR[r1] = machine.GR[r1] | machine.GR[r2]
    return flags(machine.GR[r1], OF=0)


@instruction(0x36, 'XOR', r1r2)
def xor1(machine, r1, r2):
    machine.GR[r1] = machine.GR[r1] ^ machine.GR[r2]
    return flags(machine.GR[r1], OF=0)


@instruction(0x40, 'CPA', radrx)
def cpa2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    diff = l2a(machine.GR[r]) - l2a(v)
    return int(diff == 0), int(diff < 0), 0


@instruction(0x41, 'CPL', radrx)
def cpl2(machine, r, adr, x):
    v = get_value_at_effective_address(machine, adr, x)
    diff = machine.GR[r] - v
    return int(diff == 0), int(diff < 0), 0


@instruction(0x44, 'CPA', r1r2)
def cpa1(machine, r1, r2):
    diff = l2a(machine.GR[r1]) - l2a(machine.GR[r2])
    return int(diff == 0), int(diff < 0), 0


@instruction(0x45, 'CPL', r1r2)
def cpl1(machine, r1, r2):
    diff = machine.GR[r1] - machine.GR[r2]
    return int(diff == 0), int(diff < 0), 0


@instruction(0x50, 'SLA', radrx)
def sla(machine, r, adr, x):
    v = get_effective_address(machine, adr, x)
    p = l2a(machine.GR[r])
    prev_p = p
    sign = get_bit(machine.GR[r], 15)
    ans = (p << v) & 0x7fff
    if sign == 0:
        ans = ans & 0x7fff
    else:
        ans = ans | 0x8000
    machine.GR[r] = ans
    if 0 < v:
        return flags(machine.GR[r], OF=get_bit(prev_p, 15 - v))
    else:
        return flags(machine.GR[r])


@instruction(0x51, 'SRA', radrx)
def sra(machine, r, adr, x):
    v = get_effective_address(machine, adr, x)
    p = l2a(machine.GR[r])
    prev_p = p
    sign = get_bit(machine.GR[r], 15)
    ans = (p >> v) & 0x7fff
    if sign == 0:
        ans = ans & 0x7fff
    else:
        ans = ans | 0x8000
    machine.GR[r] = ans
    if 0 < v:
        return flags(machine.GR[r], OF=get_bit(prev_p, v - 1))
    else:
        return flags(machine.GR[r])


@instruction(0x52, 'SLL', radrx)
def sll(machine, r, adr, x):
    v = get_effective_address(machine, adr, x)
    p = machine.GR[r]
    prev_p = p
    ans = p << v
    ans = ans & 0xffff
    machine.GR[r] = ans
    if 0 < v:
        return flags(machine.GR[r], logical=True,
                     OF=get_bit(prev_p, 15 - (v - 1)))
    else:
        return flags(machine.GR[r], logical=True)


@instruction(0x53, 'SRL', radrx)
def srl(machine, r, adr, x):
    v = get_effective_address(machine, adr, x)
    p = machine.GR[r]
    prev_p = p
    ans = machine.GR[r] >> v
    ans = ans & 0xffff
    machine.GR[r] = ans
    if 0 < v:
        return flags(machine.GR[r], OF=get_bit(prev_p, (v - 1)))
    else:
        return flags(machine.GR[r])


@instruction(0x61, 'JMI', adrx)
def jmi(machine, adr, x):
    if machine.SF == 1:
        raise Jump(get_effective_address(machine, adr, x))


@instruction(0x62, 'JNZ', adrx)
def jnz(machine, adr, x):
    if machine.ZF == 0:
        raise Jump(get_effective_address(machine, adr, x))


@instruction(0x63, 'JZE', adrx)
def jze(machine, adr, x):
    if machine.ZF == 1:
        raise Jump(get_effective_address(machine, adr, x))


@instruction(0x64, 'JUMP', adrx)
def jump(machine, adr, x):
    raise Jump(get_effective_address(machine, adr, x))


@instruction(0x65, 'JPL', adrx)
def jpl(machine, adr, x):
    if machine.ZF == 0 and machine.SF == 0:
        raise Jump(get_effective_address(machine, adr, x))


@instruction(0x66, 'JOV', adrx)
def jov(machine, adr, x):
    if machine.OF == 0:
        raise Jump(get_effective_address(machine, adr, x))


@instruction(0x70, 'PUSH', adrx)
def push(machine, adr, x):
    machine.SP -= 1
    machine.memory[machine.SP] = get_effective_address(machine, adr, x)


@instruction(0x71, 'POP', r)
def pop(machine, r):
    machine.GR[r] = machine.memory[machine.SP]
    machine.SP += 1


@instruction(0x80, 'CALL', adrx)
def call(machine, adr, x):
    machine.SP -= 1
    machine.memory[machine.SP] = machine.PR
    machine.call_level += 1
    raise Jump(get_effective_address(machine, adr, x))


@instruction(0x81, 'RET', noarg)
def ret(machine):
    if machine.call_level == 0:
        machine.step_count += 1
        machine.exit()
    adr = machine.memory[machine.SP]
    machine.SP += 1
    machine.call_level -= 1
    raise Jump(adr + 2)


@instruction(0xf0, 'SVC', adrx)
def svc(machine, adr, x):
    raise Jump(machine.PR)


@instruction(0x90, 'IN', strlen)
def in_(machine, s, l):
    sys.stderr.write('-> ')
    sys.stderr.flush()
    line = sys.stdin.readline()
    line = line[:-1]
    if 256 < len(line):
        line = line[0:256]
    machine.memory[l] = len(line)
    for i, ch in enumerate(line):
        machine.memory[s + i] = ord(ch)


@instruction(0x91, 'OUT', strlen)
def out(machine, s, l):
    length = machine.memory[l]
    ch = ''
    for i in range(s, s + length):
        ch += chr(machine.memory[i])
    print ch


@instruction(0xa0, 'RPUSH', noarg)
def rpush(machine):
    for i in range(1, 9):
        machine.SP -= 1
        machine.memory[machine.SP] = machine.GR[i]


@instruction(0xa1, 'RPOP', noarg)
def rpop(machine):
    for i in range(1, 9)[::-1]:
        machine.GR[i] = machine.memory[machine.SP]
        machine.SP += 1
