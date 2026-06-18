#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from pathlib import Path
from textwrap import dedent

import pytest

from conftest import has_error_code
from l0_diagnostics import DIAGNOSTIC_CODE_FAMILIES
from l0_driver import L0Driver

# Codes that produce warnings, not errors.  Skip has_errors() assertion.
WARNING_CODES = {
    "PAR-0242",
    "RES-0020", "RES-0021", "RES-0022", "RES-0036",
    "TYP-0021", "TYP-0022", "TYP-0023", "TYP-0024", "TYP-0025",
    "TYP-0030", "TYP-0031", "TYP-0105",
}

# Codes emitted by `l0c` command paths (covered in CLI tests, not here).
CLI_ONLY_CODES = set(DIAGNOSTIC_CODE_FAMILIES["L0C"])

# Internal codes unreachable from user source.
INTERNAL_CODES = {
    # Parser precondition/guard code paths not reachable from source text.
    "PAR-0030", "PAR-0040", "PAR-0050", "PAR-0056", "PAR-0060",
    "PAR-0068", "PAR-0070", "PAR-0080", "PAR-0091", "PAR-0110",
    "PAR-0120", "PAR-0130", "PAR-0140",
    "PAR-0150", "PAR-0160", "PAR-0170", "PAR-0180", "PAR-0190",
    "PAR-0200", "PAR-0230", "PAR-0500",
    "PAR-0175", "PAR-0239",

    # Resolver "shouldn't happen" path for malformed compilation units.
    "RES-0029",

    "SIG-9029",
    "TYP-0001", "TYP-0002", "TYP-0103", "TYP-0139", "TYP-0149",
    "TYP-0109",
    "TYP-0153",  # UNKNOWN_MODULE unreachable: require_import fires MODULE_NOT_IMPORTED first
    "TYP-0182", "TYP-0190", "TYP-0200", "TYP-0260", "TYP-0282",
    "TYP-0300",  # same reason: UNKNOWN_MODULE path unreachable in sizeof
    "TYP-0319",  # default widening mismatch code; all current call sites pass a specific code
    "TYP-9209", "TYP-9288", "TYP-9289",
}


LEX_TRIGGERS = {
    "LEX-0010": '"unterminated',
    "LEX-0020": "'",
    "LEX-0021": "'a",
    "LEX-0030": "'\\u0100'",
    "LEX-0031": "'\\x0FFF'",
    "LEX-0040": "@",
    "LEX-0050": '"\\xGG"',
    "LEX-0051": '"\\u12"',
    "LEX-0052": '"\\U1234567"',
    "LEX-0053": '"\\777"',
    "LEX-0054": '"\\UDEADBEEF"',
    "LEX-0059": '"\\q"',
    "LEX-0060": "2147483648",
    "LEX-0061": "23423abc",
    "LEX-0070": "/* unterminated",
}

PAR_TRIGGERS = {
    "PAR-0010": dedent(
        """
        module main;

        func main() -> int {
            let __dea__future__keyword__: int = 0;
            return 0;
        }
        """
    ),
    "PAR-0011": dedent(
        """
        module main;

        func main() -> int {
            let int: int = 0;
            return 0;
        }
        """
    ),
    "PAR-0020": "module main; +;",
    "PAR-0042": "module main; func foo -> int { return 0; }",
    "PAR-0043": "module main; func foo(: int) -> int { return 0; }",
    "PAR-0044": "module main; func foo(a int) -> int { return 0; }",
    "PAR-0041": "module main; func () -> int { return 0; }",
    "PAR-0045": "module main; func foo(a: int -> int { return a; }",
    "PAR-0046": "module main; extern func foo() -> int",
    "PAR-0051": "module main; struct { x: int; }",
    "PAR-0052": "module main; struct Point x: int; }",
    "PAR-0053": "module main; struct Point { : int; }",
    "PAR-0054": "module main; struct Point { x int; }",
    "PAR-0055": "module main; struct Point { x: int }",
    "PAR-0061": "module main; enum { None; }",
    "PAR-0062": "module main; enum Option None; }",
    "PAR-0063": "module main; enum Option { ; }",
    "PAR-0064": "module main; enum Option { Some(: int); }",
    "PAR-0065": "module main; enum Option { Some(v int); }",
    "PAR-0066": "module main; enum Option { Some(v: int; }",
    "PAR-0067": "module main; enum Option { None }",
    "PAR-0071": "module main; type = int;",
    "PAR-0072": "module main; type Alias int;",
    "PAR-0073": "module main; type Alias = int",
    "PAR-0081": "module main; let : int = 1;",
    "PAR-0082": "module main; let x: int 1;",
    "PAR-0083": "module main; let x: int = 1",
    "PAR-0090": "module main; func main() -> int return 0; }",
    "PAR-0100": dedent(
        """
        module main;

        func main() -> int {
            let x: int = 0
            return x;
        }
        """
    ),
    "PAR-0111": "module main; func main() -> int { let : int = 0; return 0; }",
    "PAR-0112": "module main; func main() -> int { let x: int 0; return 0; }",
    "PAR-0121": "module main; func main() -> int { if true { return 1; } return 0; }",
    "PAR-0122": "module main; func main() -> int { if (true { return 1; } }",
    "PAR-0123": "module main; func main() -> int { else return 0; }",
    "PAR-0131": "module main; func main() -> int { while true { return 1; } return 0; }",
    "PAR-0132": "module main; func main() -> int { while (true { return 1; } }",
    "PAR-0141": "module main; func main() -> int { for let i: int = 0; i < 3; i = i + 1 { return 0; } }",
    "PAR-0142": "module main; func main() -> int { for (let i: int = 0 i < 3; i = i + 1) { return 0; } }",
    "PAR-0143": "module main; func main() -> int { for (let i: int = 0; i < 3 i = i + 1) { return 0; } }",
    "PAR-0144": "module main; func main() -> int { for (let i: int = 0; i < 3; i = i + 1 { return 0; } }",
    "PAR-0161": "module main; func main() -> int { drop ; return 0; }",
    "PAR-0171": "module main; enum Option { None; } func main(opt: Option) -> int { match opt { None => { return 0; } } }",
    "PAR-0172": "module main; enum Option { None; } func main(opt: Option) -> int { match (opt { None => { return 0; } } }",
    "PAR-0173": "module main; enum Option { None; } func main(opt: Option) -> int { match (opt) None => { return 0; } }",
    "PAR-0174": "module main; enum Option { None; } func main(opt: Option) -> int { match (opt) { None { return 0; } } }",
    "PAR-0176": "module main; enum Option { None; } func main(opt: Option) -> int { match (opt) { None => { return 0; } None => { return 1; } } }",
    "PAR-0177": "module main; enum Option { None; } func main(opt: Option) -> int { match (opt) { } }",
    "PAR-0181": "module main; enum Option { Some(v: int); } func main(opt: Option) -> int { match (opt) { Some(x => { return 0; } } }",
    "PAR-0182": "module main; enum Option { None; } func main(opt: Option) -> int { match (opt) { 123 => { return 0; } } }",
    "PAR-0210": "module main; func add(a: int, b: int) -> int { return a + b; } func main() -> int { return add(1, 2; }",
    "PAR-0211": "module main; func main() -> int { let v: int = arr[0; return v; }",
    "PAR-0212": "module main; func main() -> int { let v: int = arr.; return v; }",
    "PAR-0223": "module main; struct S { x: int; } func main() -> int { let p: S* = new S(1; return 0; }",
    "PAR-0224": "module main; func main() -> int { let x: int = (1 + 2; return x; }",
    "PAR-0225": "module main; func main() -> int { let x: int = ; return 0; }",
    "PAR-0226": "module main; func main() -> int { let x: int = 1 & 2; return x; }",
    "PAR-0231": "module main; func main() -> int { case 42 { } return 0; }",
    "PAR-0232": "module main; func main() -> int { case (42 { } return 0; }",
    "PAR-0233": "module main; func main() -> int { case (42) 1 => { return 1; } return 0; }",
    "PAR-0234": "module main; func main() -> int { case (42) { else { return 0; } 1 => { return 1; } } }",
    "PAR-0235": "module main; func main() -> int { case (42) { 1 { return 1; } } }",
    "PAR-0236": "module main; func main() -> int { case (42) { else { return 0; } else { return 1; } } }",
    "PAR-0237": "module main; func main() -> int { case (42) { else => return 0; } }",
    "PAR-0240": "module main; func main() -> int { case (42) { } return 0; }",
    "PAR-0241": "module main; func main() -> int { case (42) { x => { return 0; } } }",
    "PAR-0242": "module main; func main() -> int { case (42) { 1 => { return 1; } else { return 0; } } }",
    "PAR-0243": "module main; func main() -> int { case (42) { 1 => if (true) return 1; else return 0; } }",
    "PAR-0300": "module main.; func main() -> int { return 0; }",
    "PAR-0310": "import std.io;",
    "PAR-0311": "module ;",
    "PAR-0312": "module main\nfunc main() -> int { return 0; }",
    "PAR-0320": "module main; import ;",
    "PAR-0321": "module main; import std.io",
    "PAR-0400": "module main; type Alias = ;",
    "PAR-0401": "module main; func foo(x: main::) -> int { return 0; }",
    "PAR-9401": "module main; func main() -> int { let x: int[] = 0; return x; }",
    "PAR-0501": "module main; func main() -> int { with let x: int = 1 => x = 0 { return 0; } return 0; }",
    "PAR-0502": "module main; func main() -> int { with (let x: int = 1 => x = 0 { return 0; } return 0; }",
    "PAR-0503": dedent("""\
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        func main() -> int {
            with (let f: int = open("a") => close(f),
                  let g: int = open("b")) {
                return f;
            }
        }
    """),
    "PAR-0504": dedent("""\
        module main;
        extern func open(name: string) -> int;
        extern func close(f: int);
        func main() -> int {
            with (let f: int = open("a") => close(f)) {
                return f;
            } cleanup {
                close(f);
            }
        }
    """),
    "PAR-0505": dedent("""\
        module main;
        extern func open(name: string) -> int;
        func main() -> int {
            with (let f: int = open("a")) {
                return f;
            }
        }
    """),
    "PAR-0506": "module main; func main() -> int { cleanup return 0; }",
}

DRV_TRIGGERS = {
    "DRV-0010": "missing-file",
    "DRV-0020": "module-mismatch",
    "DRV-0030": "import-cycle",
    "DRV-0040": "bad-encoding",
}

RES_TRIGGERS = {
    "RES-0010": dedent("""\
        module main;
        func foo() -> int { return 1; }
        func foo() -> int { return 2; }
    """),
}

SIG_TRIGGERS = {
    "SIG-0010": "module main; func foo() -> int { return 0; } func bar(x: foo) -> int { return 0; }",
    "SIG-0011": "module main; func foo(x: void?) -> int { return 0; }",
    "SIG-0018": dedent("""\
        module main;
        enum Color { Red(); }
        func foo(x: main::Color::Red) -> int { return 0; }
    """),
    "SIG-0019": "module main; func foo(x: NoSuchType) -> int { return 0; }",
    "SIG-0020": "module main; type A = B; type B = A; func foo(x: A) -> int { return 0; }",
    "SIG-0030": "module main; let x = foo();",
    "SIG-0040": dedent("""\
        module main;
        struct A { b: B; }
        struct B { a: A; }
        func foo() -> int { return 0; }
    """),
}

TYP_TRIGGERS = {
    "TYP-0010": dedent("""\
        module main;
        func foo() -> int { if (true) { return 1; } }
    """),
    "TYP-0020": dedent("""\
        module main;
        func foo() -> int { let x: int = 1; let x: int = 2; return x; }
    """),
    "TYP-0021": dedent("""\
        module main;
        func foo() -> int {
            let x: int = 1;
            if (true) { let x: int = 2; return x; }
            return x;
        }
    """),
    "TYP-0022": dedent("""\
        module main;
        enum E { Red(); }
        func foo() -> int { let Red: int = 1; return Red; }
    """),
    "TYP-0025": dedent("""\
        module main;
        func bar() -> int { return 0; }
        func foo() -> int { let bar: int = 1; return bar; }
    """),
    "TYP-0030": dedent("""\
        module main;
        func foo() -> int {
            while (true) { break; let x: int = 0; }
            return 0;
        }
    """),
    "TYP-0031": dedent("""\
        module main;
        func foo() -> int { return 1; let x: int = 0; }
    """),
    "TYP-0040": dedent("""\
        module main;
        func foo() -> int { let x: Unknown = 0; return 0; }
    """),
    "TYP-0050": dedent("""\
        module main;
        func foo() -> int { let x: void = 0; return 0; }
    """),
    "TYP-0051": dedent("""\
        module main;
        func foo() -> int { let x = unknown_func(); return 0; }
    """),
    "TYP-0052": dedent("""\
        module main;
        func foo() -> int { let x = null; return 0; }
    """),
    "TYP-0053": dedent("""\
        module main;
        func v() -> void {}
        func foo() -> int { let x = v(); return 0; }
    """),
    "TYP-0060": dedent("""\
        module main;
        func foo() -> int { drop unknown; return 0; }
    """),
    "TYP-0061": dedent("""\
        module main;
        func foo() -> int { let x: int = 1; drop x; return 0; }
    """),
    "TYP-0062": dedent("""\
        module main;
        struct S { v: int; }
        func foo() -> int { let p: S* = new S(1); drop p; drop p; return 0; }
    """),
    "TYP-0063": dedent("""\
        module main;
        struct S { v: int; }
        let gp: S*? = null;
        func foo() -> int { drop gp; return 0; }
    """),
    "TYP-0070": dedent("""\
        module main;
        func foo() -> int { if (1) { return 1; } return 0; }
    """),
    "TYP-0080": dedent("""\
        module main;
        func foo() -> int { while (1) { return 1; } return 0; }
    """),
    "TYP-0090": dedent("""\
        module main;
        func foo() -> int { for (let i: int = 0; 1; i = i + 1) { return 0; } return 0; }
    """),
    "TYP-0100": dedent("""\
        module main;
        func foo() -> int {
            let x: int = 1;
            match (x) { _ => { return 0; } }
        }
    """),
    "TYP-0101": dedent("""\
        module main;
        enum E { Some(v: int); }
        func foo(e: E) -> int {
            match (e) { Some(a, b) => { return 0; } }
        }
    """),
    "TYP-0102": dedent("""\
        module main;
        enum E { Some(v: int); }
        func foo(e: E) -> int {
            match (e) { Unknown => { return 0; } }
        }
    """),
    "TYP-0104": dedent("""\
        module main;
        enum E { A(); B(); }
        func foo(e: E) -> int {
            match (e) { A => { return 0; } }
        }
    """),
    "TYP-0105": dedent("""\
        module main;
        enum E { A(); B(); }
        func foo(e: E) -> int {
            match (e) { A => { return 0; } B => { return 1; } _ => { return 2; } }
        }
    """),
    "TYP-0106": dedent("""\
        module main;
        struct Point { x: int; y: int; }
        func foo() -> int {
            let p: Point = Point(1, 2);
            case (p) {
                else { return 0; }
            }
        }
    """),
    "TYP-0107": dedent("""\
        module main;
        func foo() -> int {
            let x: int = 1;
            case (x) {
                "hello" => { return 1; }
                else { return 0; }
            }
        }
    """),
    "TYP-0108": dedent("""\
        module main;
        func foo() -> int {
            let x: int = 1;
            case (x) {
                1 => { return 1; }
                1 => { return 2; }
                else { return 0; }
            }
        }
    """),
    "TYP-0110": dedent("""\
        module main;
        func foo() -> int { break; return 0; }
    """),
    "TYP-0120": dedent("""\
        module main;
        func foo() -> int { continue; return 0; }
    """),
    "TYP-0150": dedent("""\
        module main;
        struct S { v: int; }
        func foo() -> int {
            let p: S* = new S(1);
            drop p;
            let q: S* = p;
            return 0;
        }
    """),
    "TYP-0151": dedent("""\
        module main;
        struct S { v: int; }
        func foo() -> int { let x: int = S; return 0; }
    """),
    "TYP-0152": dedent("""\
        module main;
        enum E { Some(v: int); }
        func foo() -> int { let x: int = Some; return 0; }
    """),
    "TYP-0156": dedent("""\
        module main;
        import std.io;
        func ok() -> int? { return 1 as int?; }
        func fail() -> int? { return null; }
        func foo() -> int? {
            with (let q: int = ok()?,
                  let p: int = fail()?) {
            } cleanup {
                printl_si("q", q);
                printl_si("p", p);
            }
            return 0 as int?;
        }
        func main() -> int { return 0; }
    """),
    "TYP-0158": dedent("""\
        module main;
        enum Color { Red(); }
        func foo() -> int { let x: int = Color::Red::x; return 0; }
    """),
    "TYP-0159": dedent("""\
        module main;
        func foo() -> int { let x: int = unknown; return 0; }
    """),
    "TYP-0160": dedent("""\
        module main;
        func foo() -> int { let x: int = -true; return 0; }
    """),
    "TYP-0161": dedent("""\
        module main;
        func foo() -> int { let x: bool = !1; return false; }
    """),
    "TYP-0162": dedent("""\
        module main;
        func foo() -> int { let x: int = *1; return 0; }
    """),
    "TYP-0170": dedent("""\
        module main;
        func foo() -> int { let x: int = true + 1; return 0; }
    """),
    "TYP-0171": dedent("""\
        module main;
        func foo() -> bool { let x: bool = 1 && 2; return x; }
    """),
    "TYP-0172": dedent("""\
        module main;
        func foo() -> bool { let x: bool = 1 == true; return x; }
    """),
    "TYP-0173": dedent("""\
        module main;
        struct S { v: int; }
        func foo(a: S, b: S) -> bool { return a == b; }
    """),
    "TYP-0180": dedent("""\
        module main;
        func foo() -> int { return (1 + 2)(3); }
    """),
    "TYP-0181": dedent("""\
        module main;
        enum E { A(); }
        func foo() -> int { let x: int = E(1); return 0; }
    """),
    "TYP-0183": dedent("""\
        module main;
        func bar(x: int) -> int { return x; }
        func foo() -> int { return bar(1, 2); }
    """),
    "TYP-0189": dedent("""\
        module main;
        func foo() -> int { return unknown(1); }
    """),
    "TYP-0191": dedent("""\
        module main;
        struct S { a: int; b: int; }
        func foo() -> int { let s: S = S(1); return 0; }
    """),
    "TYP-0201": dedent("""\
        module main;
        enum E { Some(v: int); }
        func foo(e: E) -> int { let e: E = Some(1, 2); return 0; }
    """),
    "TYP-0210": dedent("""\
        module main;
        func foo(arr: int*) -> int { return arr[true]; }
    """),
    "TYP-0211": dedent("""\
        module main;
        extern func maybe_buf() -> int*?;
        func foo(i: int) -> int {
            let buf: int*? = maybe_buf();
            return buf[i];
        }
    """),
    "TYP-0212": dedent("""\
        module main;
        func foo() -> int { let x: int = 1; return x[0]; }
    """),
    "TYP-0220": dedent("""\
        module main;
        struct S { v: int; }
        func foo(p: S?) -> int { return p.v; }
    """),
    "TYP-0221": dedent("""\
        module main;
        struct S { x: int; }
        func foo(s: S) -> int { return s.y; }
    """),
    "TYP-0222": dedent("""\
        module main;
        func foo() -> int { let x: int = 1; return x.field; }
    """),
    "TYP-0230": dedent("""\
        module main;
        func foo() -> int { let s: string = "hello"; let x: int = s as int; return x; }
    """),
    "TYP-0240": dedent("""\
        module main;
        func foo() -> int { return sizeof(void); }
    """),
    "TYP-0241": dedent("""\
        module main;
        func foo() -> int { return sizeof(int, bool); }
    """),
    "TYP-0242": dedent("""\
        module main;
        func foo() -> int { return ord(1, 2); }
    """),
    "TYP-0243": dedent("""\
        module main;
        func foo() -> int { return ord(42); }
    """),
    "TYP-0250": dedent("""\
        module main;
        func bar() -> int { return 1; }
        func foo() -> int? { return bar()?; }
    """),
    "TYP-0251": dedent("""\
        module main;
        func bar() -> int? { return null; }
        func foo() -> int { return bar()?; }
    """),
    "TYP-0270": dedent("""\
        module main;
        type A = B;
        type B = A;
        func foo() -> int { let x: int = 1 as A; return x; }
    """),
    "TYP-0271": dedent("""\
        module main;
        func bar() -> int { return 0; }
        func foo() -> int { return 1 as bar; }
    """),
    "TYP-0278": dedent("""\
        module main;
        func foo() -> int { let x: void? = null; return 0; }
    """),
    "TYP-0280": dedent("""\
        module main;
        func foo() -> int { let p: int* = new Unknown(1); return 0; }
    """),
    "TYP-0281": dedent("""\
        module main;
        enum Color { Red(); Green(); }
        func foo() -> int { let p: Color* = new Color(); return 0; }
    """),
    "TYP-0283": dedent("""\
        module main;
        struct S { a: int; b: int; }
        func foo() -> int { let p: S* = new S(1); return 0; }
    """),
    "TYP-0285": dedent("""\
        module main;
        func foo() -> int { let p: int* = new int(1, 2); return 0; }
    """),
    "TYP-0286": dedent("""\
        module main;
        func foo() -> int { let p: int* = new int(true); return 0; }
    """),
    "TYP-0290": dedent("""\
        module main;
        func bar(x: int) -> int { return x; }
        func foo() -> int { return bar(int); }
    """),
    "TYP-0310": dedent("""\
        module main;
        func foo() -> int { let x: int = true; return 0; }
    """),
    "TYP-0311": dedent("""\
        module main;
        func foo() -> int { let x: int = 0; x = true; return x; }
    """),
    "TYP-0312": dedent("""\
        module main;
        func bar(x: int) -> int { return x; }
        func foo() -> int { return bar(true); }
    """),
    "TYP-0313": dedent("""\
        module main;
        struct S { v: int; }
        func foo() -> int { let s: S = S(true); return 0; }
    """),
    "TYP-0314": dedent("""\
        module main;
        enum E { Some(v: int); }
        func foo() -> int { let e: E = Some(true); return 0; }
    """),
    "TYP-0315": dedent("""\
        module main;
        func foo() -> int { return true; }
    """),
    "TYP-0316": dedent("""\
        module main;
        struct S { v: int; }
        func foo() -> int { let p: S* = new S(true); return 0; }
    """),
    "TYP-0700": dedent("""\
        module main;
        func foo() -> byte { return 300 as byte; }
    """),
    "TYP-0701": dedent("""\
        module main;
        func foo() -> int* { return (null as int*?) as int*; }
    """),
}

# Codes requiring multi-module setups.  The value is a mode string
# handled by _analyze_with_driver.
MULTI_MODULE_TRIGGERS = {
    "RES-0020": "extern-shadow",
    "RES-0021": "import-shadow",
    "RES-0022": "ambiguous-import",
    "RES-0036": "duplicate-import",
    "TYP-0023": "shadow-imported-variant",
    "TYP-0024": "shadow-ambiguous",
    "TYP-0154": "not-imported-varref",
    "TYP-0155": "ambiguous-varref",
    "TYP-0279": "ambiguous-type-body",
    "TYP-0301": "not-imported-sizeof",
    "TYP-0303": "ambiguous-sizeof",
}


def _all_codes() -> list[str]:
    codes: list[str] = []
    for family in DIAGNOSTIC_CODE_FAMILIES.values():
        codes.extend(family)
    return codes


def _analyze_with_driver(tmp_path: Path, mode: str):
    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)

    if mode == "missing-file":
        return driver.analyze("missing")

    if mode == "module-mismatch":
        (tmp_path / "foo.l0").write_text("module bar;\n")
        return driver.analyze("foo")

    if mode == "import-cycle":
        (tmp_path / "a.l0").write_text("module a;\nimport b;\n")
        (tmp_path / "b.l0").write_text("module b;\nimport a;\n")
        return driver.analyze("a")

    if mode == "bad-encoding":
        (tmp_path / "main.l0").write_bytes(b"module main;\nfunc main() -> int { return 0; }\n\xff")
        return driver.analyze("main")

    if mode == "extern-shadow":
        (tmp_path / "helper.l0").write_text(dedent("""\
            module helper;
            extern func ext_fn(x: int) -> int;
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import helper;
            extern func ext_fn(x: int) -> int;
            func foo() -> int { return ext_fn(1); }
        """))
        return driver.analyze("main")

    if mode == "import-shadow":
        (tmp_path / "helper.l0").write_text(dedent("""\
            module helper;
            func foo() -> int { return 1; }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import helper;
            func foo() -> int { return 2; }
        """))
        return driver.analyze("main")

    if mode == "duplicate-import":
        (tmp_path / "helper.l0").write_text(dedent("""\
            module helper;
            func foo() -> int { return 1; }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import helper;
            import helper;
            func bar() -> int { return foo(); }
        """))
        return driver.analyze("main")

    if mode == "ambiguous-import":
        (tmp_path / "a.l0").write_text(dedent("""\
            module a;
            func foo() -> int { return 1; }
        """))
        (tmp_path / "b.l0").write_text(dedent("""\
            module b;
            func foo() -> int { return 2; }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import a;
            import b;
            func bar() -> int { return 0; }
        """))
        return driver.analyze("main")

    if mode == "shadow-imported-variant":
        (tmp_path / "colors.l0").write_text(dedent("""\
            module colors;
            enum Color { Red(); Green(); }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import colors;
            func foo() -> int { let Red: int = 1; return Red; }
        """))
        return driver.analyze("main")

    if mode == "shadow-ambiguous":
        (tmp_path / "a.l0").write_text(dedent("""\
            module a;
            enum E1 { Red(); }
        """))
        (tmp_path / "b.l0").write_text(dedent("""\
            module b;
            enum E2 { Red(); }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import a;
            import b;
            func foo() -> int { let Red: int = 1; return Red; }
        """))
        return driver.analyze("main")

    if mode == "not-imported-varref":
        (tmp_path / "other.l0").write_text(dedent("""\
            module other;
            let bar: int = 1;
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            func foo() -> int { let x: int = other::bar; return x; }
        """))
        return driver.analyze("main")

    if mode == "ambiguous-varref":
        (tmp_path / "a.l0").write_text(dedent("""\
            module a;
            let foo: int = 1;
        """))
        (tmp_path / "b.l0").write_text(dedent("""\
            module b;
            let foo: int = 2;
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import a;
            import b;
            func bar() -> int { let x: int = foo; return x; }
        """))
        return driver.analyze("main")

    if mode == "ambiguous-type-body":
        (tmp_path / "a.l0").write_text(dedent("""\
            module a;
            struct T { v: int; }
        """))
        (tmp_path / "b.l0").write_text(dedent("""\
            module b;
            struct T { v: int; }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import a;
            import b;
            func foo() -> int { let x: T = 0; return 0; }
        """))
        return driver.analyze("main")

    if mode == "not-imported-sizeof":
        (tmp_path / "other.l0").write_text(dedent("""\
            module other;
            struct T { v: int; }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            func foo() -> int { return sizeof(other::T); }
        """))
        return driver.analyze("main")

    if mode == "ambiguous-sizeof":
        (tmp_path / "a.l0").write_text(dedent("""\
            module a;
            struct T { v: int; }
        """))
        (tmp_path / "b.l0").write_text(dedent("""\
            module b;
            struct T { v: int; }
        """))
        (tmp_path / "main.l0").write_text(dedent("""\
            module main;
            import a;
            import b;
            func foo() -> int { return sizeof(T); }
        """))
        return driver.analyze("main")

    raise ValueError(f"unknown driver trigger mode: {mode}")


@pytest.mark.parametrize("code", _all_codes())
def test_diagnostic_code_triggers(code, analyze_single, tmp_path):
    if code in CLI_ONLY_CODES:
        return

    if code in INTERNAL_CODES:
        return

    if code in DRV_TRIGGERS or code in MULTI_MODULE_TRIGGERS:
        mode = DRV_TRIGGERS.get(code) or MULTI_MODULE_TRIGGERS[code]
        result = _analyze_with_driver(tmp_path, mode)
        if code not in WARNING_CODES:
            assert result.has_errors(), f"expected errors for {code}, got: {[d.message for d in result.diagnostics]}"
        assert has_error_code(result.diagnostics, code), \
            f"expected [{code}] in diagnostics: {[d.message for d in result.diagnostics]}"
        return

    trigger = (LEX_TRIGGERS.get(code) or PAR_TRIGGERS.get(code) or
               RES_TRIGGERS.get(code) or SIG_TRIGGERS.get(code) or
               TYP_TRIGGERS.get(code))
    if trigger is not None:
        result = analyze_single("main", trigger)
        if code not in WARNING_CODES:
            assert result.has_errors(), f"expected errors for {code}, got: {[d.message for d in result.diagnostics]}"
        assert has_error_code(result.diagnostics, code), \
            f"expected [{code}] in diagnostics: {[d.message for d in result.diagnostics]}"
        return

    pytest.fail(
        f"missing trigger/classification for diagnostic code {code}; "
        "add to *_TRIGGERS, DRV/MULTI_MODULE triggers, or classification sets"
    )
