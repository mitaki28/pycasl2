============================================================
PyCASL2 & PyCOMET2(CASLII Assembler & Simulater)
============================================================

概要
==============================

PyCASL2, PyCOMET2 は  `CASLII<http://www.ipa.go.jp/english/humandev/data/Term_LangSpec.pdf>`_ の、アセンブラ及びシュミレータです。
このプログラムは、Masahiko Nakamoto 氏によって作成された、
`PyCASL2 & PyComet2<http://www.image.med.osaka-u.ac.jp/member/nakamoto/pycasl2/index.html>`_ を、改良して作られています。
基本的な仕様については、http://www.image.med.osaka-u.ac.jp/member/nakamoto/pycasl2/index.html を参照してください。

変更点
==============================
現段階で変更が施されている部分は、シュミレータのPyComet2のみです。

- コマンド入力の際に、ヒストリ補完やカーソルキーによる移動が可能になっています。
- コマンド入力の際に、不正な引数を与えると強制終了するバグを修正しています。
- コードを全体的にリファクタリングしています。
- ファイルを複数のモジュールに分割し、メンテナンス性を高めています。

TODO
==============================
- テストをほとんど行なっていないためバグが発生する可能性が高いです


ライセンス
==============================
このプログラムはGPL2ライセンスに従います:

    PyCOMET2, COMET II emulator implemented in Python.
    Copyright (c) 2012, Yasuaki Mitani.
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
