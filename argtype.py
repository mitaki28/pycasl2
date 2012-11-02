# ~*~ coding:utf-8 ~*~
from functools import wraps


def argtype(size=0):
    def _(f):
        @wraps(f)
        def __(machine, addr=None):
            if addr is None: addr = machine.PR
            return f(machine, addr)
        __.size = size
        return __
    return _


@argtype(size=1)
def noarg(machine, addr):
    return tuple()


@argtype(size=1)
def r(machine, addr):
    a = machine.memory[addr]
    return (0x00f0 & a) >> 4,


@argtype(size=1)
def r1r2(machine, addr):
    a = machine.memory[addr]
    r1 = ((0x00f0 & a) >> 4)
    r2 = (0x000f & a)
    return r1, r2


@argtype(size=2)
def adrx(machine, addr):
    a = machine.memory[addr]
    b = machine.memory[addr + 1]
    x = (0x000f & a)
    adr = b
    return adr, x


@argtype(size=2)
def radrx(machine, addr):
    a = machine.memory[addr]
    b = machine.memory[addr + 1]
    r = ((0x00f0 & a) >> 4)
    x = (0x000f & a)
    adr = b
    return r, adr, x


@argtype(size=3)
def strlen(machine, addr):
    s = machine.memory[addr + 1]
    l = machine.memory[addr + 2]
    return s, l
