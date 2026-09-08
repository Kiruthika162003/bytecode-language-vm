"""Dead code elimination: drop the statements that provably cannot run.

Once constant folding has turned computable conditions into literals, some
control flow becomes decidable while compiling. A branch whose condition
folded to a literal is not a branch at all, only one of its arms can ever
run, and emitting the test and the other arm wastes both space and time. A
loop whose condition folded to a falsehood never executes its body. And
anything written after a return in the same block is unreachable, because
the return leaves the function before control could arrive there. This
pass removes all three. The value is not only smaller output: dropping an
unreachable arm removes whatever it contained from consideration entirely,
so a large branch guarded by a compile-time falsehood costs nothing.
Two limits are drawn on purpose. The pass reasons only about conditions
that folding has already reduced to literals, and it makes no attempt to
track what a variable holds, so a condition that is obviously constant to
a reader but reaches the pass as a variable is left alone; proving that
would need dataflow analysis, which is a different and much larger
undertaking. And a declaration is never dropped even when it appears
unreachable, because a later stage may still resolve a name against it,
and removing a binding is a far riskier edit than removing a statement
that only computes. The pass runs after folding for exactly this reason:
on an unfolded tree it would find almost nothing to remove.
"""

from __future__ import annotations

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.valueops import is_truthy

_EMPTY = s.Block(())


def _literal_truth(node: e.Expr | None) -> bool | None:
    if isinstance(node, e.Literal):
        return is_truthy(node.value)
    return None


def prune_statement(node: s.Stmt) -> s.Stmt:
    if isinstance(node, s.Block):
        return s.Block(tuple(prune_body(node.statements)))
    if isinstance(node, s.IfStmt):
        return _prune_if(node)
    if isinstance(node, s.WhileStmt):
        if _literal_truth(node.condition) is False:
            return _EMPTY
        return s.WhileStmt(node.condition, prune_statement(node.body))
    if isinstance(node, s.ForStmt):
        return _prune_for(node)
    if isinstance(node, s.FunctionStmt):
        return s.FunctionStmt(node.name, node.parameters, tuple(prune_body(node.body)))
    if isinstance(node, s.ClassStmt):
        methods = tuple(
            s.FunctionStmt(m.name, m.parameters, tuple(prune_body(m.body)))
            for m in node.methods
        )
        return s.ClassStmt(node.name, node.superclass, methods)
    return node


def _prune_if(node: s.IfStmt) -> s.Stmt:
    truth = _literal_truth(node.condition)
    if truth is True:
        return prune_statement(node.then_branch)
    if truth is False:
        if node.else_branch is None:
            return _EMPTY
        return prune_statement(node.else_branch)
    return s.IfStmt(
        node.condition,
        prune_statement(node.then_branch),
        prune_statement(node.else_branch) if node.else_branch is not None else None,
    )


def _prune_for(node: s.ForStmt) -> s.Stmt:
    if _literal_truth(node.condition) is False:
        # the body never runs, but the initializer still declares and may still
        # be referred to, so it is kept and only the loop itself disappears
        if node.initializer is None:
            return _EMPTY
        return s.Block((prune_statement(node.initializer),))
    return s.ForStmt(
        prune_statement(node.initializer) if node.initializer is not None else None,
        node.condition,
        node.increment,
        prune_statement(node.body),
    )


def prune_body(statements: tuple[s.Stmt, ...]) -> list[s.Stmt]:
    kept: list[s.Stmt] = []
    for statement in statements:
        kept.append(prune_statement(statement))
        if isinstance(statement, (s.ReturnStmt, s.BreakStmt, s.ContinueStmt)):
            # each of these leaves the block unconditionally, so nothing written
            # after it in the same block can be reached
            break
    return kept


def prune_program(statements: list[s.Stmt]) -> list[s.Stmt]:
    return prune_body(tuple(statements))
