# ~*~ coding:utf-8 ~*~


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


def i2bin(n, fill=None):
    if fill is None:
        return bin(n).split('b')[-1]
    else:
        return bin(n).split('b')[-1].zfill(fill)
