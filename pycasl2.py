# -*- coding: euc-jp -*-

'''
PyCASL2, CASL II assembler implemented in Python.
Copyright (c) 2009, Masahiko Nakamoto.
All rights reserved.

Based on a simple implementation of CASL II assembler.
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

import warnings
warnings.simplefilter('ignore', DeprecationWarning)

import sys, os, string, array, re
from optparse import OptionParser, OptionValueError
from sets import Set


op_tokens = Set(['NOP', 'LD', 'ST', 'LAD', 'ADDA', 'SUBA', 'ADDL', 'SUBL',
              'AND', 'OR','XOR', 'CPA', 'CPL', 'SLA', 'SRA', 'SLL', 'SRL',
              'JMI', 'JNZ', 'JZE', 'JUMP', 'JPL', 'JOV', 'PUSH', 'POP',
              'CALL', 'RET', 'SVC', 'START', 'END', 'DC', 'DS',
              'IN', 'OUT', 'RPUSH', 'RPOP'])

noarg, r, r1r2, adrx, radrx, ds, dc, strlen, start = [0, 1, 2, 3, 4, 5, 6, 7, 8]

reg_str = {}
for i in range(0,9):
    reg_str['GR%1d' % i] = i

op_table = {'NOP':[0x00, noarg],
            'LD2':[0x10, radrx],
            'ST':[0x11, radrx],
            'LAD':[0x12, radrx],
            'LD1':[0x14, r1r2],
            'ADDA2':[0x20, radrx],
            'SUBA2':[0x21, radrx],
            'ADDL2':[0x22, radrx],
            'SUBL2':[0x23, radrx],
            'ADDA1':[0x24, r1r2],
            'SUBA1':[0x25, r1r2],
            'ADDL1':[0x26, r1r2],
            'SUBL1':[0x27, r1r2],
            'AND2':[0x30, radrx],
            'OR2':[0x31, radrx],
            'XOR2':[0x32, radrx],
            'AND1':[0x34, r1r2],
            'OR1':[0x35, r1r2],
            'XOR1':[0x36, r1r2],
            'CPA2':[0x40, radrx],
            'CPL2':[0x41, radrx],
            'CPA1':[0x44, r1r2],
            'CPL1':[0x45, r1r2],
            'SLA':[0x50, radrx],
            'SRA':[0x51, radrx],
            'SLL':[0x52, radrx],
            'SRL':[0x53, radrx],
            'JMI':[0x61, adrx],
            'JNZ':[0x62, adrx],
            'JZE':[0x63, adrx],
            'JUMP':[0x64, adrx],
            'JPL':[0x65, adrx],
            'JOV':[0x66, adrx],
            'PUSH':[0x70, adrx],
            'POP':[0x71, r],
            'CALL':[0x80, adrx],
            'RET':[0x81, noarg],
            'SVC':[0xf0, adrx],
            'IN':[0x90, strlen],
            'OUT':[0x91, strlen],
            'RPUSH':[0xa0, noarg],
            'RPOP':[0xa1, noarg],
            'LD': [-1, 0],
            'ADDA':[-2, 0],
            'SUBA':[-3, 0],
            'ADDL':[-4, 0],
            'SUBL':[-5, 0],
            'AND':[-6, 0],
            'OR':[-7, 0],
            'XOR':[-8, 0],
            'CPA':[-9, 0],
            'CPL':[-10, 0],
            'START':[-100, start],
            'END':[-101, 0],
            'DS':[0, ds],
            'DC':[0, dc]}


''' unsigned -> signed '''
def l2a(x):
    x &= 0xffff
    if 0x0000 <= x <= 0x7fff:
        a = x
    elif 0x8000 <= x <= 0xffff:
        a = x - 2**16
    else:
        raise TypeError
    return a

''' signed -> unsigned '''
def a2l(x):
    x &= 0xffff
    if 0 <= x:
        return x
    return x + 2**16


class CASL2:

    # ラベルの情報を保持する
    class Label:
        def __init__(self, label, lines=0, filename='', addr=0, goto=''):
            self.label = label
            self.lines = lines
            self.filename = filename
            self.addr = addr
            self.goto = goto

        def __str__(self):
            scope, label = self.label.split('.')
            if len(scope) == 0:
                s = '%s:%d\t%04x\t%s' % (self.filename, self.lines, self.addr, label)
            else:
                s = '%s:%d\t%04x\t%s (%s)' % (self.filename, self.lines, self.addr, label, scope)
            return s

    class Instruction:
        def __init__(self, label, op, args, line_number, src):
            self.label = label
            self.op = op
            self.args = args
            self.line_number = line_number
            self.src = src

        def __str__(self):
            return '%d: %s, %s, %s' % (self.line_number, self.label, self.op, self.args)

    class ByteCode:
        def __init__(self, code, addr, line_number, src):
            self.code = code
            self.addr = addr
            self.line_number = line_number
            self.src = src

        def __str__(self):
            try:
                s = '%04x\t%04x\t\t%d\t%s' % (self.addr, self.code[0], self.line_number, self.src)
            except IndexError:
                s = '%04x\t    \t\t%d\t%s' % (self.addr, self.line_number, self.src)
            if 1 < len(self.code):
                s += '\n'
                try:
                    s += '%04x\t%04x' % (self.addr+1, self.code[1])
                except TypeError:
                    s += '%04x\t%s' % (self.addr+1, self.code[1])
            if 2 < len(self.code):
                s += '\n'
                try:
                    s += '%04x\t%04x' % (self.addr+2, self.code[2])
                except TypeError:
                    s += '%04x\t%s' % (self.addr+2, self.code[2])
            return s

    class Error(BaseException):
        def __init__(self, line_num, src, message):
            self.line_num = line_num
            self.src = src
            self.message = message

        def report(self):
            print >> sys.stderr, "Error: %s\nLine %d: %s" % (self.message, self.line_num, self.src)


    def __init__(self, filename=""):
        self.symbols = {}
        self.gen_code_func = [self.gen_code_noarg, self.gen_code_r, self.gen_code_r1r2,
                              self.gen_code_adrx, self.gen_code_radrx,
                              self.gen_code_ds, self.gen_code_dc, self.gen_code_strlen,
                              self.gen_code_start]
        self.addr = 0
        self.label_count = 0
        self.additional_dc = []
        self.start_address = 0x0000
        self.start_found = False
        self.current_scope = ''

    def dump(self, a_code):
        addr = 0
        print 'Addr\tOp\t\tLine\tSource code'
        for c in a_code:
            if c.code != []:
                if c.code[0] == 0x4341:
                    continue
            print c
##             print '%04x\t%04x\t\t%d\t%s' % (c.addr, c.code[0], c.line_number, c.src)
##             if 1 < len(c.code):
##                 print '%04x\t%04x' % (c.addr+1, c.code[1])
##             if 2 < len(c.code):
##                 print '%04x\t%04x' % (c.addr+2, c.code[2])
##             addr += len(c.code)

        print '\nDefined labels'
        labels = self.symbols.values()
        labels.sort(lambda x, y: cmp(x.lines, y.lines))
        for i in labels:
            print i

    def assemble(self, filename):
        self.filename = filename
        self.addr = 0

        self.fp = file(filename, 'r')
        self.current_line_number = -1
        self.next_line = self.Instruction(None, "", None, -1, "")
        self.next_src = ""
        self.tmp_code = []

        try:
            self.get_line()
            self.is_valid_program()
        except self.Error, e:
            e.report()
            sys.exit()

        self.fp.close()

##         print >> sys.stderr, '-- First pass --'
##         for i in self.tmp_code:
##             print >> sys.stderr, i

        # ラベルをアドレスに置換。
        try:
            code_list = [self.replace_label(code) for code in self.tmp_code if code != None]
        except self.Error, e:
            e.report()
            sys.exit()

        # =記法のリテラル用コードを末尾に加える。
        code_list.extend(self.additional_dc)

##         print >> sys.stderr, '-- Second pass --'
##         for i in code_list:
##             print >> sys.stderr, i

        return code_list

    def is_valid_program(self):
        ''' 構文解析 '''
        while True:
            if not self.is_START():
                raise self.Error(self.current_line_number,
                                 self.current_src,
                                 "START is not found.")
            is_data_exist = False
            while not (self.next_line.op == "END" or self.next_line.op == "EOF"):
                i = self.get_line()
                if i.op == 'RET':
                    if is_data_exist:
                        raise self.Error(self.current_line_number,
                                         self.current_src,
                                         "Data definition in program")
                    is_data_exist = False
                if i.op == 'START':
                    raise self.Error(self.current_line_number,
                                     self.current_src,
                                     "Invalid operation is found.")
                if i.op in ('DC', 'DS'):
                    is_data_exist = True
                self.tmp_code.append(self.convert(i))
            if not self.is_END():
                raise self.Error(self.current_line_number,
                                 self.current_src,
                                 "END is not found.")
            if self.next_line.op == "EOF":
                break
        return True


    def get_line(self):
        # 一行先読みする
        # コメントのみの行は読み飛ばす
        current = self.next_line
        self.current_src = self.next_src

        while True:
            line = self.fp.readline().rstrip()
            self.current_line_number += 1
            self.next_src = line

            if len(line) == 0:
                self.next_line = self.Instruction(None, "EOF", None, self.current_line_number+1, "")
                return current
            #

            line = line.split(';')[0].rstrip()
            if len(line) > 0:
                break
            #
        #
        self.next_line = self.split_line(line, self.current_line_number+1)
        return current


    def is_START(self):
        i = self.get_line()
        if i.op != "START":
            return False

        self.tmp_code.append(self.convert(i))

        return True

    def is_RET(self):
        i = self.get_line()
        if i.op != "RET":
            return False

        self.tmp_code.append(self.convert(i))

        return True

    def is_END(self):
        i = self.get_line()
        if i.op != "END":
            return False

        self.tmp_code.append(self.convert(i))

        return True

    def is_DC_or_DS(self):
        # DC, DS以外はエラー
        i = self.get_line()
        if not (i.op == "DC" or i.op == "DS"):
            return False

        self.tmp_code.append(self.convert(i))

        return True

    def is_valid_instruction(self):
        # DC, DS, END, STARTはエラー
        i = self.get_line()
        if (i.op == "DC" or i.op == "DS" or i.op == "END" or i.op == "START"):
            return False

        self.tmp_code.append(self.convert(i))

        return True

    def replace_label(self, bcode):
        ''' ラベルをアドレスに置換 '''
        def conv(x, bcode):
            if type(x) == type('str'):
                if x[0] == '=':
                    return self.gen_additional_dc(x, bcode.line_number)
                #
                global_name = '.' + x.split('.')[1]
                if x in self.symbols.keys():
                    return self.symbols[x].addr
                #
                # スコープ内にないときは、スコープ名なしのラベルを探す
                elif global_name in self.symbols.keys():
                    if self.symbols[global_name].goto is '':
                        return self.symbols[global_name].addr
                    # サブルーチンの実行開始番地が指定されていた場合、gotoに書かれているラベルの番地にする
                    else:
                        label = self.symbols[global_name].goto
                        if label in self.symbols.keys():
                            return self.symbols[label].addr
                        else:
                            raise self.Error(bcode.line_number, bcode.src, 'Undefined label "%s" was found.' % x.split('.')[1])
                        #
                    #
                else:
                    raise self.Error(bcode.line_number, bcode.src, 'Undefined label "%s" was found.' % x.split('.')[1])
            else:
                return x

        return self.ByteCode([conv(i, bcode) for i in bcode.code], bcode.addr, bcode.line_number, bcode.src)

    def remove_comment(self, file):
        return [i for i in [(n+1, line[:-1].split(';')[0]) for n, line in enumerate(file)] if len(i[1]) > 0]


    def split_line(self, line, line_number):
        ''' 行からラベル、命令、オペランドを取り出す '''
        result = re.match('^\s*$', line)
        # check empty line
        if result != None:
            return (None, None, None)

        re_label = "(?P<label>[A-Za-z_][A-Za-z0-9_]*)?"
        re_op = "\s+(?P<op>[A-Z]+)"
        re_arg1 = "(?P<arg1>=?(([-#]?[A-Za-z0-9_]+)|(\'.*\')))"
        re_arg2 = "(?P<arg2>=?(([-#]?[A-Za-z0-9_]+)|(\'.*\')))"
        re_arg3 = "(?P<arg3>=?(([-#]?[A-Za-z0-9_]+)|(\'.*\')))"
        re_args = "(\s+%s(\s*,\s*%s(\s*,\s*%s)?)?)?" % (re_arg1, re_arg2, re_arg3)
        re_comment = "(\s*(;(?P<comment>.+)?)?)?"
        pattern = "(^" + re_label + re_op + re_args + ")?" + re_comment

        result = re.match(pattern, line)

        if result == None:
            print >> sys.stderr, 'Line %d: Invalid line was found.' % line_number
            print >> sys.stderr,  line
            sys.exit()

##        print result.group('label'), result.group('op'), result.group('arg1'), result.group('arg2'), result.group('arg3')
        label = result.group('label')
        op = result.group('op')
        args = None
        if result.group('arg1') != None:
            args = [result.group('arg1')]
            if result.group('arg2') != None:
                args.append(result.group('arg2'))
            if result.group('arg3') != None:
                args.append(result.group('arg3'))

        return self.Instruction(label, op, args, line_number, line)

    def register_label(self, inst):
        ''' ラベルをシンボルテーブルに登録する '''
        if inst.label != None:
            label_name = self.current_scope + '.' + inst.label
            if label_name in self.symbols.keys():
                print >> sys.stderr, 'Line %d: Label "%s" is already defined.' % (inst.line_number, inst.label)
                sys.exit()
            #
            self.symbols[label_name] = self.Label(label_name, inst.line_number, self.filename, self.addr)
        #
        return


    def conv_noarg(self, args):
        return (None,)

    def conv_r(self, args):
        return (reg_str[args[0]], )

    def conv_r1r2(self, args):
        return (reg_str[args[0]], reg_str[args[1]])

    def conv_adrx(self, args):
        addr = self.conv_adr(args[0])
        if len(args) == 1:
            return (addr, 0)
        return (addr, reg_str[args[1]])

    def conv_radrx(self, args):
        addr = self.conv_adr(args[1])
        if len(args) == 2:
            return (reg_str[args[0]], addr, 0)
        return (reg_str[args[0]], addr, reg_str[args[2]])

    def conv_adr(self, addr):
        if re.match('-?[0-9]+', addr) != None:
            a = a2l(int(addr))
        elif re.match('#[A-Za-z0-9]+', addr) != None:
            a = int(addr[1:], 16)
        elif re.match('[A-Za-z_][A-Za-z0-9_]*', addr) != None:
            a = self.current_scope + '.' + addr
        elif re.match('=.+', addr) != None:
            a = addr
        return a

    def gen_code_noarg(self, op, args):
        code = [0]
        code[0] = (op_table[op][0] << 8)
        return code

    def gen_code_r(self, op, args):
        code = [0]
        code[0] = ((op_table[op][0] << 8) | (self.conv_r(args)[0] << 4))
        return code

    def gen_code_r1r2(self, op, args):
        code = [0]
        r1, r2 = self.conv_r1r2(args)
        code[0] = ((op_table[op][0] << 8) | (r1 << 4) | r2)
        return code

    def gen_code_adrx(self, op, args):
        code = [0, None]
        addr, x = self.conv_adrx(args)
        code[0] = ((op_table[op][0] << 8) | (0 << 4) | x)
        code[1] = addr
        return code

    def gen_code_radrx(self, op, args):
        code = [0, None]
        r, addr, x = self.conv_radrx(args)
        code[0] = ((op_table[op][0] << 8) | (r << 4) | x)
        code[1] = addr
        return code

    def gen_code_ds(self, op, args):
        code = array.array('H', [0]*int(args[0]))
        return code

    def gen_code_dc(self, op, args):
        const = self.cast_literal(args[0])
        code = array.array('H', const)
        return code

    # IN,OUT用
    def gen_code_strlen(self, op, args):
        code = [0, None, None]
        code[0] = (op_table[op][0] << 8)
        code[1] = self.conv_adr(args[0])
        code[2] = self.conv_adr(args[1])
        return code

    # START用
    def gen_code_start(self, op, args):
        code = [0]*8
        code[0] = (ord('C') << 8) + ord('A')
        code[1] = (ord('S') << 8) + ord('L')
        if args != None:
            addr, x = self.conv_adrx(args)
            code[2] = addr
        return code

    def cast_literal(self, arg):
        if arg[0] == '#':
            value = [int(arg[1:], 16)]
        elif arg[0] == '\'':
            value = [ord(i) for i in arg[1:-1]]
        else:
            value = [a2l(int(arg))]
        return value

    # ラベルの文字列を生成する
    def gen_label(self):
        l = '_L' + '%04d' % self.label_count
        self.label_count += 1
        return l

    # =記法のリテラル用コードを生成する
    def gen_additional_dc(self, x, n):
        l = self.gen_label()
        label_name = '.' + l
        self.symbols[label_name] = self.Label(label_name, n, self.filename, self.addr)
        const = self.cast_literal(x[1:])
        code = array.array('H', const)
        self.addr += len(code)
        # self.additional_dc.append((code, n, '%s\tDC\t%s' % (l,x[1:])))
        self.additional_dc.append(self.ByteCode(code, self.symbols[label_name].addr, n, '%s\tDC\t%s' % (l,x[1:])))
        return self.symbols[label_name].addr


    # バイト列に変換
    def convert(self, inst):
        self.register_label(inst)

        try:
            if inst.op == None:
                return None
            #
            if -100 < op_table[inst.op][0] < 0:
                if self.is_arg_register(inst.args[1]):
                    inst.op += '1'
                else:
                    inst.op += '2'
            #
            if op_table[inst.op][0] == -100:
                if inst.label == None:
                    print >> sys.stderr, 'Line %d: Label should be defined for START.' % inst.line_number
                    sys.exit()
                self.current_scope = inst.label
                if self.start_found:
                    # サブルーチンの実行開始番地が指定されていた場合、gotoに実行開始番地をセットする
                    if inst.args != None:
                        self.symbols['.'+inst.label].goto = self.conv_adr(inst.args[0])
                    return None
                else:
                    self.start_found = True
                    return self.ByteCode(self.gen_code_start(inst.op, inst.args), self.addr, inst.line_number, inst.src)
            elif op_table[inst.op][0] == -101:
                self.current_scope = ''
                return None
            elif op_table[inst.op][0] < 0:
                return None

            bcode = self.ByteCode(self.gen_code_func[op_table[inst.op][1]](inst.op, inst.args), self.addr, inst.line_number, inst.src)
            self.addr += len(bcode.code)

            return bcode
        except KeyError:
            print >> sys.stderr, 'Line %d: Invalid instruction "%s" was found.' % (inst.line_number, inst.op)
            sys.exit()

    def is_arg_register(self, arg):
        if arg[0:2] == 'GR':
            return True
        else:
            return False

    def write(self, filename, code_list):
        codelist = []
        for bcode in code_list:
            for i in bcode.code:
                codelist.append(i)
        obj = array.array('H', codelist)
        obj.byteswap()
        obj.tofile(file(filename, 'wb'))


def main():
    usage = '%prog [options] input.cas [output.com]'
    parser = OptionParser(usage)
    parser.add_option('-a', None, action='store_true', dest='dump', default=False, help='turn on verbose listings')
    parser.add_option('-v', '--version', action='store_true', dest='version', default=False, help='display version and exit')
    options, args = parser.parse_args()

    if options.version:
        print 'PyCASL2 version 1.1.4'
        print '$Revision: 42606859abf2 $'
        print 'Copyright (c) 2009,2011, Masahiko Nakamoto.'
        print 'All rights reserved.'
        sys.exit()

    if len(args) < 1:
        parser.print_help()
        sys.exit()

    if len(args) < 2:
        com_name = os.path.splitext(args[0])[0] + '.com'
    else:
        com_name = args[1]

    casl2 = CASL2()
    x = casl2.assemble(args[0])
    if options.dump:
        casl2.dump(x)
    casl2.write(com_name, x)

if __name__ == '__main__':
    main()
