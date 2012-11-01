# -*- coding: euc-jp -*-

'''
PyCOMET2, COMET II emulator implemented in Python.
Copyright (c) 2009, Masahiko Nakamoto.
All rights reserved.

Based on a simple implementation of COMET II emulator.
Copyright (c) 2001-2008, Osamu Mizuno.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
'''

import sys
import string
import array
import logging
from functools import wraps
from optparse import OptionParser

# argtypeに与える引数の種類
noarg, r, r1r2, adrx, radrx, ds, dc, strlen = [0, 1, 2, 3, 4, 5, 6, 7]
# 機械語命令のバイト長
inst_size = {noarg: 1, r: 1, r1r2: 1, adrx: 2,
             radrx: 2, ds: -1, dc: -1, strlen: 3}
# スタックポインタの初期値
initSP = 0xff00


def l2a(x):
    ''' unsigned -> signed '''
    x &= 0xffff
    if 0x0000 <= x <= 0x7fff:
        a = x
    elif 0x8000 <= x <= 0xffff:
        a = x - 2 ** 16
    else:
        raise TypeError
    return a


def a2l(x):
    ''' signed -> unsigned '''
    x &= 0xffff
    if 0 <= x:
        return x
    return x + 2 ** 16


def get_bit(x, n):
    ''' xのnビット目の値を返す (最下位ビットがn = 0)'''
    if x & (0x01 << n) == 0:
        return 0
    else:
        return 1


def get_r(machine, addr=None):
    if addr is None: addr = machine.PR
    a = machine.memory[addr]
    return (0x00f0 & a) >> 4


def get_r1r2(machine, addr=None):
    if addr is None: addr = machine.PR
    a = machine.memory[addr]
    r1 = ((0x00f0 & a) >> 4)
    r2 = (0x000f & a)
    return r1, r2


def get_adrx(machine, addr=None):
    if addr is None: addr = machine.PR
    a = machine.memory[addr]
    b = machine.memory[addr + 1]
    x = (0x000f & a)
    adr = b
    return adr, x


def get_radrx(machine, addr=None):
    if addr is None: addr = machine.PR
    a = machine.memory[addr]
    b = machine.memory[addr + 1]
    r = ((0x00f0 & a) >> 4)
    x = (0x000f & a)
    adr = b
    return r, adr, x


def get_strlen(machine, addr=None):
    if addr is None:
        addr = machine.PR
    s = machine.memory[addr + 1]
    l = machine.memory[addr + 2]
    return s, l


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
            noarg, r, r1r2, adrx, radrx, ds, dc, strlen
            try:
                if argtype == noarg:
                    result = ir()
                elif argtype == r:
                    result = ir(machine, *get_r(machine))
                elif argtype == r1r2:
                    result = ir(machine, *get_r1r2(machine))
                elif argtype == adrx:
                    result = ir(machine, *get_adrx(machine))
                elif argtype == radrx:
                    result = ir(machine, *get_radrx(machine))
                elif argtype == strlen:
                    result = ir(machine, *get_strlen(machine))
                else:
                    raise Exception
            except Jump as jump:
                machine.PR = jump.addr
                result = jump.result
            else:
                machine.PR += inst_size[argtype]
            if result is not None:
                machine.ZF = result[0] or machine.ZF
                machine.SF = result[1] or machine.SF
                machine.OF = result[2] or machine.OF
        __.opcode = opcode
        __.opname = opname
        __.argtype = argtype
        return __
    return _


class Instruction:
    '''
    命令の基底クラス
    '''
    def __init__(self, machine, opcode=0x00, opname='None', argtype=noarg):
        self.m = machine
        self.opcode = opcode
        self.opname = opname
        self.argtype = argtype
        self.disassemble_functions = {noarg: self.disassemble_noarg,
                                      r: self.disassemble_r,
                                      r1r2: self.disassemble_r1r2,
                                      adrx: self.disassemble_adrx,
                                      radrx: self.disassemble_radrx,
                                      strlen: self.disassemble_strlen}

    def disassemble(self, address):
        return self.disassemble_functions[self.argtype](address)

    def disassemble_noarg(self, address):
        return '%--8s' % self.opname

    def disassemble_r(self, address):
        r = self.get_r(address)
        return '%-8sGR%1d' % (self.opname, r)

    def disassemble_r1r2(self, address):
        r1, r2 = self.get_r1r2(address)
        return '%-8sGR%1d, GR%1d' % (self.opname, r1, r2)

    def disassemble_adrx(self, address):
        adr, x = self.get_adrx(address)
        if x == 0:
            return '%-8s#%04x' % (self.opname, adr)
        else:
            return '%-8s#%04x, GR%1d' % (self.opname, adr, x)

    def disassemble_radrx(self, address):
        r, adr, x = self.get_radrx(address)
        if x == 0:
            return '%-8sGR%1d, #%04x' % (self.opname, r, adr)
        else:
            return '%-8sGR%1d, #%04x, GR%1d' % (self.opname, r, adr, x)

    def disassemble_strlen(self, address):
        s, l = self.get_strlen(address)
        return '%-8s#%04x, #%04x' % (self.opname, s, l)


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
    return flags(machine.GR[r], OF=0)


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
        return flags(machine.GR[r], locical=True,
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
    machine.setSP(machine.getSP() - 1)
    machine.memory[machine.getSP()] = get_effective_address(machine, adr, x)


@instruction(0x71, 'POP', r)
def pop(machine, r):
    machine.GR[r] = machine.memory[machine.getSP()]
    machine.setSP(machine.getSP() + 1)


@instruction(0x80, 'CALL', adrx)
def call(machine, adr, x):
    machine.setSP(machine.getSP() - 1)
    machine.memory[machine.getSP()] = machine.PR
    machine.call_level += 1
    raise Jump(get_effective_address(machine, adr, x))


@instruction(0x81, 'RET', noarg)
def ret(machine):
    if machine.call_level == 0:
        machine.step_count += 1
        machine.exit()
    machine.setSP(machine.getSP() + 1)
    machine.call_level -= 1
    raise Jump(machine.memory[machine.getSP()] + 2)


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
        machine.setSP(machine.getSP() - 1)
        machine.memory[machine.getSP()] = machine.GR[i]


@instruction(0xa1, 'RPOP', noarg)
def rpop(machine):
    for i in range(1, 9)[::-1]:
        machine.GR[i] = machine.memory[machine.getSP()]
        machine.setSP(machine.getSP() + 1)


class pyComet2:
    class InvalidOperation(BaseException):
        def __init__(self, address):
            self.address = address

        def __str__(self):
            return 'Invalid operation is found at #%04x.' % self.address

    class StatusMonitor:
        def __init__(self, machine):
            self.m = machine
            self.format = '%04d: '
            self.var_list = ['self.m.step_count']
            self.decimalFlag = False

        def __str__(self):
            variables = ""
            for v in self.var_list:
                variables += v + ","
            return eval("'%s' %% (%s)" % (self.format, variables))

        def append(self, s):
            if len(self.format) != 6:
                self.format += ", "

            try:
                if s == 'PR':
                    self.format += "PR=#%04x"
                    self.var_list.append('self.m.PR')
                elif s == 'OF':
                    self.format += "OF=%01d"
                    self.var_list.append('self.m.OF')
                elif s == 'SF':
                    self.format += "SF=%01d"
                    self.var_list.append('self.m.SF')
                elif s == 'ZF':
                    self.format += "ZF=%01d"
                    self.var_list.append('self.m.ZF')
                elif s[0:2] == 'GR':
                    if int(s[2]) < 0 or 8 < int(s[2]):
                        raise
                    if self.decimalFlag:
                        self.format += s[0:3] + "=%d"
                    else:
                        self.format += s[0:3] + "=#%04x"
                    self.var_list.append('self.m.GR[' + s[2] + ']')
                else:
                    adr = self.m.cast_int(s)
                    if adr < 0 or 0xffff < adr:
                        raise
                    if self.decimalFlag:
                        self.format += "#%04x" % adr + "=%d"
                    else:
                        self.format += "#%04x" % adr + "=#%04x"
                    self.var_list.append('self.m.memory[%d]' % adr )
            except:
                print >> sys.stderr, ("Warning: Invalid monitor "
                                      "target is found."
                                      " %s is ignored." % s)

    def __init__(self):
        self.inst_list = [nop, ld2, st, lad, ld1,
                          adda2, suba2, addl2, subl2,
                          adda1, suba1, addl1, subl1,
                          and2, or2, xor2, and1, or1, xor1,
                          cpa2, cpl2, cpa1, cpl1,
                          sla, sra, sll, srl,
                          jmi, jnz, jze, jump, jpl, jov,
                          push, pop, call, ret, svc,
                          in_, out, rpush, rpop]

        self.inst_table = {}
        for ir in self.inst_list:
            self.inst_table[ir.opcode] = ir

        self.isAutoDump = False
        self.break_points = []
        self.call_level = 0
        self.step_count = 0
        self.monitor = self.StatusMonitor(self)

        self.initialize()

    def initialize(self):
        # 主記憶 1 word = 2 byte unsigned short
        self.memory = array.array('H', [0] * 65536)
        # レジスタ unsigned short
        self.GR = array.array('H', [0] * 9)
        # スタックポインタ SP = GR[8]
        self.setSP(initSP)
        # プログラムレジスタ
        self.PR = 0
        # Overflow Flag
        self.OF = 0
        # Sign Flag
        self.SF = 0
        # Zero Flag
        self.ZF = 1
        logging.info('Initialize memory and registers.')

    def setSP(self, value):
        self.GR[8] = value

    def getSP(self):
        return self.GR[8]

    def print_status(self):
        try:
            code = self.getInstruction().disassemble(self.PR)
        except:
            code = '%04x' % self.memory[self.PR]
        sys.stderr.write('PR  #%04x [ %-30s ]  STEP %d\n'
                         % (self.PR, code, self.step_count) )
        sys.stderr.write('SP  #%04x(%7d) FR(OF, SF, ZF)  %03s  (%7d)\n'
                         % (self.getSP(), self.getSP(),
                            self.getFRasString(), self.getFR()))
        sys.stderr.write('GR0 #%04x(%7d) GR1 #%04x(%7d) '
                         ' GR2 #%04x(%7d) GR3: #%04x(%7d)\n'
                         % (self.GR[0], l2a(self.GR[0]),
                            self.GR[1], l2a(self.GR[1]),
                            self.GR[2], l2a(self.GR[2]),
                            self.GR[3], l2a(self.GR[3])))
        sys.stderr.write('GR4 #%04x(%7d) GR5 #%04x(%7d) '
                         'GR6 #%04x(%7d) GR7: #%04x(%7d)\n'
                         % (self.GR[4], l2a(self.GR[4]),
                            self.GR[5], l2a(self.GR[5]),
                            self.GR[6], l2a(self.GR[6]),
                            self.GR[7], l2a(self.GR[7])))

    def exit(self):
        if self.isCountStep:
            print 'Step count:', self.step_count

        if self.isAutoDump:
            print >> sys.stderr, "dump last status to last_state.txt"
            self.dump_to_file('last_state.txt')

        sys.exit()

    def set_auto_dump(self, flg):
        self.isAutoDump = flg

    def set_count_step(self, flg):
        self.isCountStep = flg

    def setLoggingLevel(self, lv):
        logging.basicConfig(level=lv)

    def getFR(self):
        return self.OF << 2 | self.SF << 1 | self.ZF

    def getFRasString(self):
        return str(self.OF) + str(self.SF) + str(self.ZF)

    # PRが指す命令を返す
    def getInstruction(self, adr=None):
        try:
            if adr is None: adr = self.PR
            return self.inst_table[(self.memory[adr] & 0xff00) >> 8]
        except KeyError:
            raise self.InvalidOperation(adr)

    # 命令を1つ実行
    def step(self):
        self.getInstruction()()
        self.step_count += 1

    def watch(self, variables, decimalFlag=False):
        self.monitor.decimalFlag = decimalFlag
        for v in variables.split(","):
            self.monitor.append(v)

        while (True):
            if self.PR in self.break_points:
                break
            else:
                try:
                    print self.monitor
                    sys.stdout.flush()
                    self.step()
                except self.InvalidOperation, e:
                    print >> sys.stderr, e
                    self.dump(e.address)
                    break

    def run(self):
        while (True):
            if self.PR in self.break_points:
                break
            else:
                try:
                    self.step()
                except self.InvalidOperation, e:
                    print >> sys.stderr, e
                    self.dump(e.address)
                    break

    # オブジェクトコードを主記憶に読み込む
    def load(self, filename, quiet=False):
        if not quiet:
            print >> sys.stderr, 'load %s ...' % filename,
        self.initialize()
        fp = file(filename, 'rb')
        try:
            tmp = array.array('H')
            tmp.fromfile(fp, 65536)
        except EOFError:
            pass
        fp.close()
        tmp.byteswap()
        self.PR = tmp[2]
        tmp = tmp[8:]
        for i in range(0, len(tmp)):
            self.memory[i] = tmp[i]
        if not quiet:
            print >> sys.stderr, 'done.'

    def dump_memory(self, start_addr=0x0000, lines=0xffff / 8):
        printable = (string.letters
                     + string.digits
                     + string.punctuation + ' ')

        def to_char(array):
            def chr2(i):
                c = 0x00ff & i
                return chr(c) if chr(c) in printable else '.'
            return ''.join([chr2(i) for i in array])

        def to_hex(array):
            return ' '.join(['%04x' % i for i in array])

        st = []
        for i in range(0, lines):
            addr = i * 8 + start_addr
            if 0xffff < addr: return st
            st.append('%04x: %-39s %-8s\n'
                      % (addr,
                         to_hex(self.memory[addr:addr + 8]),
                         to_char(self.memory[addr:addr + 8])))
        return ''.join(st)

    # 8 * 16 wordsダンプする
    def dump(self, start_addr=0x0000):
        print self.dump_memory(start_addr, 16),

    def dump_stack(self):
        print self.dump_memory(self.getSP(), 16),

    def dump_to_file(self, filename, lines=0xffff / 8):
        fp = file(filename, 'w')
        fp.write('Step count: %d\n' % self.step_count)
        fp.write('PR: #%04x\n' % self.PR)
        fp.write('SP: #%04x\n' % self.getSP())
        fp.write('OF: %1d\n' % self.OF)
        fp.write('SF: %1d\n' % self.SF)
        fp.write('ZF: %1d\n' % self.ZF)
        for i in range(0, 8):
            fp.write('GR%d: #%04x\n' % (i, self.GR[i]))
        fp.write('Memory:\n')
        fp.write(self.dump_memory(0, lines))
        fp.close()

    def disassemble(self, start_addr=0x0000):
        addr = start_addr
        for i in range(0, 16):
            try:
                inst = self.getInstruction(addr)
                if inst is not None:
                    print >> sys.stderr, ('#%04x\t#%04x\t%s'
                                          % (addr, self.memory[addr],
                                             inst.disassemble(addr)))
                    if 1 < inst_size[inst.argtype]:
                        print >> sys.stderr, ('#%04x\t#%04x'
                                              % (addr + 1,
                                                 self.memory[addr + 1]))
                    if 2 < inst_size[inst.argtype]:
                        print >> sys.stderr, ('#%04x\t#%04x'
                                              % (addr + 2,
                                                 self.memory[addr + 2]))
                    addr += inst_size[inst.argtype]
                else:
                    print >> sys.stderr, ('#%04x\t#%04x\t%s'
                                          % (addr,
                                             self.memory[addr],
                                             '%-8s#%04x'
                                             % ('DC',
                                                self.memory[addr])))
                    addr += 1
            except:
                print >> sys.stderr, ('#%04x\t#%04x\t%s'
                                      % (addr,
                                         self.memory[addr],
                                         '%-8s#%04x' % ('DC',
                                                        self.memory[addr])))
                addr += 1
            #
        #

    def cast_int(self, addr):
        if addr[0] == '#':
            return int(addr[1:], 16)
        else:
            return int(addr)

    def set_break_point(self, addr):
        if addr in self.break_points:
            print >> sys.stderr, '#%04x is already set.' % addr
        else:
            self.break_points.append(addr)

    def print_break_points(self):
        if len(self.break_points) == 0:
            print >> sys.stderr, 'No break points.'
        else:
            for i, addr in enumerate(self.break_points):
                print >> sys.stderr, '%d: #%04x' % (i, addr)

    def delete_break_points(self, n):
        if 0 <= n < len(self.break_points):
            print >> sys.stderr, '#%04x is removed.' % (self.break_points[n])
        else:
            print >> sys.stderr, 'Invalid number is specified.'

    def write_memory(self, addr, value):
        self.memory[addr] = value

    def jump(self, addr):
        self.PR = addr
        self.print_status()

    def wait_for_command(self):
        while True:
            sys.stderr.write('pycomet2> ')
            sys.stderr.flush()
            line = sys.stdin.readline()
            args = line.split()
            if line[0] == 'q':
                break
            elif line[0] == 'b':
                if 2 <= len(args):
                    self.set_break_point(self.cast_int(args[1]))
            elif line[0:2] == 'df':
                self.dump_to_file(args[1])
                print >> sys.stderr, 'dump to', filename
            elif line[0:2] == 'di':
                if len(args) == 1:
                    self.disassemble()
                else:
                    self.disassemble(self.cast_int(args[1]))
            elif line[0:2] == 'du':
                if len(args) == 1:
                    self.dump()
                else:
                    self.dump(self.cast_int(args[1]))
            elif line[0] == 'd':
                if 2 <= len(args):
                    self.delete_break_points(int(args[1]))
            elif line[0] == 'h':
                self.print_help()
            elif line[0] == 'i':
                self.print_break_points()
            elif line[0] == 'j':
                self.jump(self.cast_int(args[1]))
            elif line[0] == 'm':
                self.write_memory(self.cast_int(args[1]),
                                  self.cast_int(args[2]))
            elif line[0] == 'p':
                self.print_status()
            elif line[0] == 'r':
                self.run()
            elif line[0:2] == 'st':
                self.dump_stack()
            elif line[0] == 's':
                try:
                    self.step()
                except self.InvalidOperation, e:
                    print >> sys.stderr, e
                    self.dump(e.address)

                self.print_status()
            else:
                print >> sys.stderr, 'Invalid command.'

    def print_help(self):
        print >> sys.stderr, ('b ADDR        '
                              'Set a breakpoint at specified address.')
        print >> sys.stderr, 'd NUM         Delete breakpoints.'
        print >> sys.stderr, ('di ADDR       '
                              'Disassemble 32 words from specified address.')
        print >> sys.stderr, 'du ADDR       Dump 128 words of memory.'
        print >> sys.stderr, 'h             Print help.'
        print >> sys.stderr, 'i             Print breakpoints.'
        print >> sys.stderr, 'j ADDR        Set PR to ADDR.'
        print >> sys.stderr, 'm ADDR VAL    Change the memory at ADDR to VAL.'
        print >> sys.stderr, 'p             Print register status.'
        print >> sys.stderr, 'q             Quit.'
        print >> sys.stderr, 'r             Strat execution of program.'
        print >> sys.stderr, 's             Step execution.'
        print >> sys.stderr, 'st            Dump 128 words of stack image.'


def main():
    usage = 'usage: %prog [options] input.com'
    parser = OptionParser(usage)
    parser.add_option('-c', '--count-step', action='store_true',
                      dest='count_step', default=False, help='count step.')
    parser.add_option('-d', '--dump', action='store_true',
                      dest='dump', default=False,
                      help='dump last status to last_state.txt.')
    parser.add_option('-r', '--run', action='store_true',
                      dest='run', default=False, help='run')
    parser.add_option('-w', '--watch', type='string',
                      dest='watchVariables', default='',
                      help='run in watching mode. (ex. -w PR,GR0,GR8,#001f)')
    parser.add_option('-D', '--Decimal', action='store_true',
                      dest='decimalFlag', default=False,
                      help='watch GR[0-8] and specified address in decimal '
                           'notation. (Effective in watcing mode only)')
    parser.add_option('-v', '--version', action='store_true',
                      dest='version', default=False,
                      help='display version information.')
    options, args = parser.parse_args()

    if options.version:
        print 'PyCOMET2 version 1.2'
        print '$Revision: a31dbeeb4d1c $'
        print 'Copyright (c) 2009, Masahiko Nakamoto.'
        print 'All rights reserved.'
        sys.exit()

    if len(args) < 1:
        parser.print_help()
        sys.exit()

    comet2 = pyComet2()
    comet2.set_auto_dump(options.dump)
    comet2.set_count_step(options.count_step)
    if len(options.watchVariables) != 0:
        comet2.load(args[0], True)
        comet2.watch(options.watchVariables, options.decimalFlag)
    elif options.run:
        comet2.load(args[0], True)
        comet2.run()
    else:
        comet2.load(args[0])
        comet2.print_status()
        comet2.wait_for_command()

if __name__ == '__main__':
    main()
