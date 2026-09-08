from __future__ import annotations

import pytest

from ember.errors import EmberError
from ember.interpreter import run_output, run_treewalk_output

# Running each program through the bytecode VM and the tree-walker and
# demanding identical output is a strong check that neither implementation has
# drifted from the language. Closures are included now that the bytecode
# backend captures upvalues, so the two share that semantics too.
SHARED_PROGRAMS = [
    "print 1 + 2 * 3 - 4 / 2;",
    "print (1 + 2) * (3 + 4);",
    "print 17 % 5;",
    "print -(-5);",
    'print "a" + "b" + "c";',
    "print true and false; print true or false; print not true;",
    "print 1 < 2; print 2 <= 2; print 3 > 4; print 5 >= 5;",
    "print 1 == 1; print 1 != 2; print nil == nil;",
    'if (3 > 2) print "big"; else print "small";',
    "let s = 0; for (let i = 0; i < 10; i = i + 1) s = s + i; print s;",
    "let n = 5; let f = 1; while (n > 1) { f = f * n; n = n - 1; } print f;",
    "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(15);",
    "fn add(a, b) { return a + b; } fn sq(x) { return x * x; } print sq(add(2, 3));",
    "let a = [1, 2, 3]; a[1] = 20; a[0] += 5; print a; print a[2];",
    'let m = {"x": 1, "y": 2}; m["z"] = 3; print keys(m); print m["y"];',
    "print len([1, 2, 3, 4]); print min([9, 3, 7]); print max([9, 3, 7]);",
    "print abs(-8); print floor(3.9); print ceil(3.1); print sqrt(81);",
    (
        "let total = 0; let a = [10, 20, 30];"
        " for (let i = 0; i < len(a); i = i + 1) total = total + a[i]; print total;"
    ),
    "print range(5); print contains([1, 2, 3], 2);",
    "fn fact(n) { if (n <= 1) return 1; return n * fact(n - 1); } print fact(6);",
    'print upper("hello"); print split("a,b,c", ","); print join(["x", "y"], "-");',
    "print sorted([5, 3, 8, 1]); print reversed([1, 2, 3]); print sum([1, 2, 3, 4]);",
    "print pow(2, 8); print gcd(24, 18); print factorial(6); print clamp(20, 0, 9);",
    'print substring("abcdef", 2, 5); print index_of("abcdef", "cd");',
    "print unique([1, 2, 2, 3, 3, 3]); print concat([1], [2, 3]);",
    (
        "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
        " let f = make(); print f(); print f(); let g = make(); print g();"
    ),
    (
        "fn adder(n) { fn add(x) { return x + n; } return add; }"
        " let a2 = adder(2); let a10 = adder(10); print a2(1); print a10(1);"
    ),
    (
        "fn pair() { let n = 0; fn up() { n = n + 1; return n; }"
        " fn get() { return n; } up(); up(); up(); return get(); } print pair();"
    ),
    (
        "fn outer() { let x = 7; fn mid() { fn inner() { return x; }"
        " return inner(); } return mid(); } print outer();"
    ),
]


@pytest.mark.parametrize("source", SHARED_PROGRAMS)
def test_both_backends_agree(source: str):
    assert run_output(source) == run_treewalk_output(source)


class TestErrorsAgree:
    @pytest.mark.parametrize(
        "source",
        [
            "print 1 / 0;",
            'print 1 + "x";',
            "print missing;",
            "fn f(x) { return x; } f();",
            "const k = 1; k = 2;",
            "let a = [1]; print a[9];",
        ],
    )
    def test_both_backends_reject_the_same_programs(self, source: str):
        vm_error = None
        tw_error = None
        try:
            run_output(source)
        except EmberError as exc:
            vm_error = type(exc)
        try:
            run_treewalk_output(source)
        except EmberError as exc:
            tw_error = type(exc)
        assert vm_error is not None
        assert tw_error is not None
