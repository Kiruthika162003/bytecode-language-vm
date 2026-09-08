"""Classes from the inside: where a field lives, where a method lives, and what super costs.

Object syntax hides three separate mechanisms behind one dot, and this example
separates them. A field lives on the instance and is looked for first. A method
lives on the class and is found only when no field has that name, which is what
lets an instance override behaviour by storing a value under the same name; the
example does exactly that and shows the answer change. A method reached through
an instance cannot be handed out as the bare function it compiled to, because it
would not know which instance it belonged to, so the runtime wraps it with its
receiver, and the example stores one and calls it later to show the receiver
came along. Inheritance is then shown to be method copying rather than a chain
walk: a subclass receives its superclass's methods and may replace any of them,
and super still reaches the original because the superclass is kept in a hidden
binding the methods capture. The example ends on the cost of the binding step,
which is an allocation every time a method is fetched, and on the fact that a
class here is a value like any other, which is convenient and also means a
program can shadow one by accident.
"""

from __future__ import annotations

from ember.interpreter import run

SHAPES = """
class Shape {
  init(name) { this.name = name; }
  describe() { return "a " + this.name; }
  sides() { return 0; }
}
class Square < Shape {
  init(side) { super.init("square"); this.side = side; }
  sides() { return 4; }
  area() { return this.side * this.side; }
  describe() { return super.describe() + " with " + str(this.sides()) + " sides"; }
}
let s = Square(3);
print s.describe();
print s.area();
print s.name;
print type(s);
"""


def main() -> None:
    print("a subclass that calls up into its superclass")
    machine = run(SHAPES)
    for line in machine.output:
        print(f"  {line}")
    print("  super.init set the field, and super.describe reused the sentence")

    print()
    print("a field is looked for before a method of the same name")
    shadow = run(
        'class S { name() { return "the method"; } }'
        ' let s = S(); print s.name(); s.name = "the field"; print s.name;'
    )
    print(f"  before assigning: {shadow.output[0]!r}")
    print(f"  after assigning:  {shadow.output[1]!r}")
    print("  the field wins, which is what lets data override behaviour")

    print()
    print("a method fetched from an instance keeps that instance")
    bound = run(
        "class D { init(k) { this.k = k; } scale(x) { return x * this.k; } }"
        " let tripler = D(3).scale; print tripler(5); print tripler(10);"
    )
    print(f"  stored away and called twice later: {bound.output}")
    print("  the receiver travelled with the method, or this.k would be unbound")

    print()
    print("inheritance copies methods rather than walking a chain")
    layers = run(
        "class A { m() { return 1; } }"
        " class B < A { m() { return super.m() + 1; } }"
        " class C < B { m() { return super.m() + 1; } }"
        " print A().m(); print B().m(); print C().m();"
    )
    print(f"  each level adds one: {layers.output}")
    print("  the count is the proof that no level was skipped or repeated")

    print()
    print("what this costs, and one thing to watch:")
    print("  fetching a method allocates a binding every time, which a runtime")
    print("  that fused the fetch with the call that follows would avoid")
    print("  and a class is an ordinary value, so a later declaration with the")
    print("  same name shadows it silently, exactly as a variable would")


if __name__ == "__main__":
    main()
