from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.matrixlib import matrix_names


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


SQUARE = "[[1, 2], [3, 4]]"
SINGULAR = "[[1, 2], [2, 4]]"
WIDE = "[[1, 2, 3], [4, 5, 6]]"


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "determinant" in matrix_names()
        assert "matrixMultiply" in matrix_names()

    def test_the_names_are_sorted(self):
        assert matrix_names() == sorted(matrix_names())

    def test_there_are_eighteen_of_them(self):
        assert len(matrix_names()) == 18


class TestShapeChecking:
    def test_the_shape_is_reported(self):
        assert evaluate(f"shape({SQUARE})") == "[2, 2]"

    def test_a_wide_matrix_reports_its_shape(self):
        assert evaluate(f"shape({WIDE})") == "[2, 3]"

    def test_a_ragged_matrix_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print shape([[1, 2], [3]]);")
        assert "every row the same length" in str(caught.value)

    def test_the_refusal_names_both_lengths(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print shape([[1, 2], [3]]);")
        message = str(caught.value)
        assert "row 1 has 2" in message
        assert "row 2 has 1" in message

    def test_a_matrix_with_no_rows_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print shape([]);")
        assert "no rows" in str(caught.value)

    def test_rows_with_no_entries_are_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print shape([[]]);")
        assert "no entries" in str(caught.value)

    def test_a_row_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print shape([1, 2]);")
        assert "each row to be a list" in str(caught.value)

    def test_an_entry_that_is_not_a_number_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print shape([["a"]]);')
        assert "needs numbers" in str(caught.value)

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print shape(5);")


class TestBuilding:
    def test_an_identity_has_ones_down_the_diagonal(self):
        assert evaluate("identity(2)") == "[[1, 0], [0, 1]]"

    def test_a_larger_identity(self):
        assert evaluate("identity(3)") == "[[1, 0, 0], [0, 1, 0], [0, 0, 1]]"

    def test_an_identity_of_one_is_a_single_one(self):
        assert evaluate("identity(1)") == "[[1]]"

    def test_a_size_of_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print identity(0);")

    def test_a_size_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print identity(2.5);")

    def test_a_filled_matrix_has_the_shape_asked_for(self):
        assert evaluate("shape(filled(2, 3, 0))") == "[2, 3]"

    def test_every_entry_is_the_value_given(self):
        assert evaluate("filled(2, 2, 7)") == "[[7, 7], [7, 7]]"

    def test_a_width_of_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print filled(2, 0, 1);")


class TestTransposing:
    def test_rows_become_columns(self):
        assert evaluate(f"transposed({SQUARE})") == "[[1, 3], [2, 4]]"

    def test_a_wide_matrix_becomes_tall(self):
        assert evaluate(f"shape(transposed({WIDE}))") == "[3, 2]"

    def test_transposing_twice_returns_the_original(self):
        assert evaluate(f"transposed(transposed({WIDE}))") == WIDE

    def test_an_identity_transposes_to_itself(self):
        assert evaluate("transposed(identity(3))") == evaluate("identity(3)")


class TestAddingAndScaling:
    def test_adding_adds_entry_by_entry(self):
        assert evaluate(f"matrixAdd({SQUARE}, identity(2))") == "[[2, 2], [3, 5]]"

    def test_subtracting_subtracts_entry_by_entry(self):
        assert evaluate(f"matrixSubtract({SQUARE}, {SQUARE})") == "[[0, 0], [0, 0]]"

    def test_scaling_multiplies_every_entry(self):
        assert evaluate(f"scaled({SQUARE}, 2)") == "[[2, 4], [6, 8]]"

    def test_scaling_by_one_changes_nothing(self):
        assert evaluate(f"scaled({SQUARE}, 1)") == SQUARE

    def test_scaling_by_zero_empties_it(self):
        assert evaluate(f"scaled({SQUARE}, 0)") == "[[0, 0], [0, 0]]"

    def test_adding_matrices_of_different_shapes_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print matrixAdd({SQUARE}, {WIDE});")
        assert "the same shape" in str(caught.value)

    def test_the_refusal_names_both_shapes(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print matrixAdd({SQUARE}, {WIDE});")
        message = str(caught.value)
        assert "2 by 2" in message
        assert "2 by 3" in message

    def test_subtracting_different_shapes_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print matrixSubtract({SQUARE}, {WIDE});")


class TestMultiplying:
    def test_two_square_matrices_multiply(self):
        assert evaluate(f"matrixMultiply({SQUARE}, {SQUARE})") == "[[7, 10], [15, 22]]"

    def test_a_row_times_a_column_gives_one_entry(self):
        assert evaluate("matrixMultiply([[1, 2, 3]], [[1], [2], [3]])") == "[[14]]"

    def test_multiplying_by_the_identity_changes_nothing(self):
        assert evaluate(f"matrixMultiply({SQUARE}, identity(2))") == SQUARE

    def test_the_identity_on_the_left_changes_nothing_either(self):
        assert evaluate(f"matrixMultiply(identity(2), {SQUARE})") == SQUARE

    def test_the_result_has_the_outer_shape(self):
        assert evaluate(f"shape(matrixMultiply({WIDE}, transposed({WIDE})))") == "[2, 2]"

    def test_mismatched_shapes_are_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print matrixMultiply({WIDE}, {WIDE});")
        assert "width of the first" in str(caught.value)

    def test_the_refusal_names_both_shapes(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print matrixMultiply({WIDE}, {WIDE});")
        assert "2 by 3" in str(caught.value)

    def test_a_power_repeats_multiplication(self):
        assert evaluate(f"matrixPower({SQUARE}, 2)") == evaluate(
            f"matrixMultiply({SQUARE}, {SQUARE})"
        )

    def test_a_power_of_one_is_the_matrix(self):
        assert evaluate(f"matrixPower({SQUARE}, 1)") == SQUARE

    def test_a_power_of_zero_is_the_identity(self):
        assert evaluate(f"matrixPower({SQUARE}, 0)") == evaluate("identity(2)")

    def test_a_negative_power_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print matrixPower({SQUARE}, -1);")

    def test_a_power_of_a_non_square_matrix_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print matrixPower({WIDE}, 2);")
        assert "square" in str(caught.value)


class TestDeterminants:
    def test_a_two_by_two_determinant(self):
        assert float(evaluate(f"determinant({SQUARE})")) == pytest.approx(-2.0)

    def test_a_diagonal_determinant_is_the_product(self):
        source = "determinant([[2, 0, 0], [0, 3, 0], [0, 0, 4]])"
        assert float(evaluate(source)) == pytest.approx(24.0)

    def test_the_identity_has_a_determinant_of_one(self):
        assert float(evaluate("determinant(identity(4))")) == pytest.approx(1.0)

    def test_a_singular_matrix_has_a_determinant_of_zero(self):
        assert float(evaluate(f"determinant({SINGULAR})")) == pytest.approx(0.0)

    def test_a_non_square_determinant_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print determinant({WIDE});")
        assert "square" in str(caught.value)

    def test_the_refusal_names_the_shape(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print determinant({WIDE});")
        assert "2 rows and 3 columns" in str(caught.value)

    def test_swapping_two_rows_flips_the_sign(self):
        one = float(evaluate(f"determinant({SQUARE})"))
        other = float(evaluate("determinant([[3, 4], [1, 2]])"))
        assert one == pytest.approx(-other)

    def test_a_singular_matrix_is_recognised(self):
        assert evaluate(f"isSingular({SINGULAR})") == "true"

    def test_an_invertible_matrix_is_not_singular(self):
        assert evaluate(f"isSingular({SQUARE})") == "false"


class TestRank:
    def test_a_full_rank_matrix_reports_its_size(self):
        assert evaluate(f"matrixRank({SQUARE})") == "2"

    def test_a_singular_matrix_has_a_lower_rank(self):
        assert evaluate(f"matrixRank({SINGULAR})") == "1"

    def test_the_identity_has_full_rank(self):
        assert evaluate("matrixRank(identity(3))") == "3"

    def test_a_zero_matrix_has_no_rank(self):
        assert evaluate("matrixRank(filled(2, 2, 0))") == "0"

    def test_a_non_square_matrix_can_be_ranked(self):
        assert evaluate(f"matrixRank({WIDE})") == "2"


class TestInverting:
    def test_a_matrix_times_its_inverse_is_close_to_the_identity(self):
        # close rather than equal, because elimination divides
        source = f"matrixClose(matrixMultiply({SQUARE}, inverse({SQUARE})), identity(2))"
        assert evaluate(source) == "true"

    def test_the_inverse_on_the_left_works_too(self):
        source = f"matrixClose(matrixMultiply(inverse({SQUARE}), {SQUARE}), identity(2))"
        assert evaluate(source) == "true"

    def test_the_identity_inverts_to_itself(self):
        assert evaluate("matrixClose(inverse(identity(3)), identity(3))") == "true"

    def test_inverting_twice_returns_the_original(self):
        source = f"matrixClose(inverse(inverse({SQUARE})), {SQUARE})"
        assert evaluate(source) == "true"

    def test_a_singular_matrix_has_no_inverse(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print inverse({SINGULAR});")
        assert "no inverse" in str(caught.value)

    def test_the_refusal_explains_why_it_does_not_approximate(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print inverse({SINGULAR});")
        assert "look like an answer" in str(caught.value)

    def test_a_non_square_matrix_cannot_be_inverted(self):
        with pytest.raises(Arithmetic):
            run_output(f"print inverse({WIDE});")


class TestInspecting:
    def test_the_trace_is_the_diagonal_sum(self):
        assert evaluate(f"matrixTrace({SQUARE})") == "5"

    def test_the_trace_of_an_identity_is_its_size(self):
        assert evaluate("matrixTrace(identity(4))") == "4"

    def test_a_non_square_trace_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print matrixTrace({WIDE});")

    def test_a_row_can_be_taken(self):
        assert evaluate(f"matrixRow({SQUARE}, 1)") == "[3, 4]"

    def test_a_column_can_be_taken(self):
        assert evaluate(f"matrixColumn({SQUARE}, 0)") == "[1, 3]"

    def test_a_row_past_the_end_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print matrixRow({SQUARE}, 5);")

    def test_a_column_past_the_end_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print matrixColumn({SQUARE}, 5);")

    def test_a_negative_row_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print matrixRow({SQUARE}, -1);")

    def test_a_symmetric_matrix_is_recognised(self):
        assert evaluate("isSymmetric([[1, 2], [2, 1]])") == "true"

    def test_an_asymmetric_matrix_is_recognised(self):
        assert evaluate(f"isSymmetric({SQUARE})") == "false"

    def test_an_identity_is_symmetric(self):
        assert evaluate("isSymmetric(identity(3))") == "true"

    def test_two_identical_matrices_are_close(self):
        assert evaluate(f"matrixClose({SQUARE}, {SQUARE})") == "true"

    def test_two_different_matrices_are_not(self):
        assert evaluate(f"matrixClose({SQUARE}, identity(2))") == "false"

    def test_matrices_of_different_shapes_are_not_close(self):
        assert evaluate(f"matrixClose({SQUARE}, {WIDE})") == "false"

    def test_a_tiny_difference_still_counts_as_close(self):
        assert evaluate("matrixClose([[1]], [[1.0000000000001]])") == "true"

    def test_a_visible_difference_does_not(self):
        assert evaluate("matrixClose([[1]], [[1.01]])") == "false"


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            f"shape({SQUARE})",
            "identity(3)",
            "filled(2, 3, 5)",
            f"transposed({WIDE})",
            f"matrixAdd({SQUARE}, identity(2))",
            f"matrixSubtract({SQUARE}, identity(2))",
            f"scaled({SQUARE}, 3)",
            f"matrixMultiply({SQUARE}, {SQUARE})",
            f"matrixPower({SQUARE}, 3)",
            f"determinant({SQUARE})",
            f"matrixRank({WIDE})",
            f"isSingular({SINGULAR})",
            f"inverse({SQUARE})",
            f"matrixTrace({SQUARE})",
            f"matrixRow({SQUARE}, 0)",
            f"matrixColumn({SQUARE}, 1)",
            f"matrixClose({SQUARE}, {SQUARE})",
            "isSymmetric([[1, 2], [2, 1]])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
