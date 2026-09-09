from __future__ import annotations

import zlib

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.hashlib import crc32, djb2, fnv1, fnv1a, hash_names, polynomial, sdbm
from ember.interpreter import run_output, run_treewalk_output

QUOTE = chr(34)
ACCENTED = "caf" + chr(233)


def quoted(text: str) -> str:
    return QUOTE + text + QUOTE


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


SUBJECTS = ["", "a", "b", "abc", "hello world", "The quick brown fox", ACCENTED, "x" * 200]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "fnv1a" in hash_names()
        assert "crc32" in hash_names()

    def test_the_names_are_sorted(self):
        assert hash_names() == sorted(hash_names())

    def test_there_are_nine_of_them(self):
        assert len(hash_names()) == 9

    def test_nothing_here_is_named_as_secure(self):
        # the difference from a cryptographic hash is not a matter of degree
        assert not any("secure" in name.lower() for name in hash_names())


class TestPublishedValues:
    def test_fnv1a_of_nothing_is_the_offset(self):
        assert fnv1a(b"") == 0x811C9DC5

    def test_fnv1a_of_a_letter(self):
        assert fnv1a(b"a") == 0xE40C292C

    def test_fnv1a_of_a_word(self):
        assert fnv1a(b"foobar") == 0xBF9CF968

    def test_fnv1_of_nothing_is_also_the_offset(self):
        assert fnv1(b"") == 0x811C9DC5

    def test_the_two_fnv_orders_differ_on_real_input(self):
        # 1a mixes before multiplying, which is the whole difference
        assert fnv1a(b"a") != fnv1(b"a")

    def test_djb2_of_nothing_is_its_seed(self):
        assert djb2(b"") == 5381

    def test_the_polynomial_hash_matches_the_familiar_one(self):
        assert polynomial(b"abc") == 96354

    def test_the_polynomial_hash_of_nothing_is_zero(self):
        assert polynomial(b"") == 0

    def test_sdbm_of_nothing_is_zero(self):
        assert sdbm(b"") == 0


class TestAgainstTheHost:
    @pytest.mark.parametrize("text", SUBJECTS)
    def test_the_redundancy_check_matches_the_host(self, text):
        assert crc32(text.encode()) == zlib.crc32(text.encode())

    def test_the_check_of_nothing_is_zero(self):
        assert crc32(b"") == 0

    def test_a_single_bit_changes_the_check(self):
        assert crc32(b"a") != crc32(b"b")


class TestWithinThirtyTwoBits:
    @pytest.mark.parametrize("maker", [fnv1a, fnv1, djb2, sdbm, polynomial, crc32])
    @pytest.mark.parametrize("text", ["", "a", "hello", "x" * 500])
    def test_every_hash_stays_inside_the_word(self, maker, text):
        # this language's integers do not overflow, so the wrapping is written out
        assert 0 <= maker(text.encode()) <= 0xFFFFFFFF

    @pytest.mark.parametrize("maker", [fnv1a, djb2, crc32])
    def test_a_long_input_does_not_grow_without_bound(self, maker):
        assert maker(b"x" * 10000) <= 0xFFFFFFFF


class TestDeterminism:
    @pytest.mark.parametrize("name", ["fnv1a", "fnv1", "djb2", "sdbm", "crc32"])
    def test_the_same_text_hashes_the_same(self, name):
        source = f"{name}({quoted('hello')})"
        assert evaluate(source) == evaluate(source)

    @pytest.mark.parametrize("name", ["fnv1a", "djb2", "crc32"])
    def test_different_text_hashes_differently(self, name):
        assert evaluate(f"{name}({quoted('a')})") != evaluate(f"{name}({quoted('b')})")

    def test_text_outside_ascii_hashes_by_its_bytes(self):
        # so a hash here matches what another implementation computes for the text
        assert int(evaluate(f"crc32({quoted(ACCENTED)})")) == zlib.crc32(ACCENTED.encode())


class TestSpreading:
    def test_a_value_falls_into_one_of_the_buckets(self):
        for text in SUBJECTS:
            assert 0 <= int(evaluate(f"bucketOf({quoted(text)}, 8)")) < 8

    def test_one_bucket_takes_everything(self):
        assert evaluate(f"bucketOf({quoted('anything')}, 1)") == "0"

    def test_a_bucket_count_of_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print bucketOf({quoted('a')}, 0);")
        assert "at least one bucket" in str(caught.value)

    def test_a_bucket_count_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(f"print bucketOf({quoted('a')}, 2.5);")

    def test_the_spread_has_one_entry_per_bucket(self):
        listed = "[" + quoted("a") + "]"
        assert len(evaluate(f"spreadOf({listed}, 4)")[1:-1].split(", ")) == 4

    def test_a_good_hash_spreads_reasonably_evenly(self):
        # the keys are built in a loop rather than written out: a chunk holds at most
        # 256 constants, so four hundred string literals will not compile
        source = "let keys = [];" + chr(10)
        source += "for (let i = 0; i < 400; i = i + 1) { keys = push(keys, "
        source += quoted("key") + " + str(i)); }" + chr(10)
        source += "print spreadOf(keys, 8);"
        printed = run_output(source)[0]
        counts = [int(piece) for piece in printed[1:-1].split(", ")]
        assert sum(counts) == 400
        # fifty per bucket on average, so a spread far wider than that is a bad hash
        assert max(counts) - min(counts) < 40

    def test_the_spread_counts_many_values(self):
        source = "let keys = [];" + chr(10)
        source += "for (let i = 0; i < 40; i = i + 1) { keys = push(keys, str(i)); }"
        source += chr(10) + "print spreadOf(keys, 8);"
        printed = run_output(source)[0]
        assert sum(int(piece) for piece in printed[1:-1].split(", ")) == 40

    def test_spreading_nothing_gives_empty_buckets(self):
        assert evaluate("spreadOf([], 3)") == "[0, 0, 0]"

    def test_a_spread_of_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(f"print spreadOf({quoted('a')}, 3);")


class TestChecksums:
    def test_a_matching_checksum_is_recognised(self):
        source = f"let c = crc32({quoted('hello')});"
        source += f" print checksumMatches({quoted('hello')}, c);"
        assert run_output(source) == ["true"]

    def test_a_mismatched_checksum_is_recognised(self):
        source = f"let c = crc32({quoted('hello')});"
        source += f" print checksumMatches({quoted('world')}, c);"
        assert run_output(source) == ["false"]

    def test_a_checksum_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(f"print checksumMatches({quoted('a')}, 1.5);")

    def test_a_single_character_change_is_noticed(self):
        # which is what a redundancy check exists to do
        source = f"let c = crc32({quoted('abcdef')});"
        source += f" print checksumMatches({quoted('abcdeg')}, c);"
        assert run_output(source) == ["false"]


class TestRefusals:
    @pytest.mark.parametrize(
        "name", ["fnv1a", "fnv1", "djb2", "sdbm", "polynomialHash", "crc32"]
    )
    def test_something_that_is_not_a_string_is_refused(self, name):
        with pytest.raises(TypeMismatch):
            run_output(f"print {name}(5);")

    def test_the_message_names_the_function(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print fnv1a(5);")
        assert "fnv1a needs a string" in str(caught.value)


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            f"fnv1a({quoted('hello')})",
            f"fnv1({quoted('hello')})",
            f"djb2({quoted('hello')})",
            f"sdbm({quoted('hello')})",
            f"polynomialHash({quoted('hello')})",
            f"crc32({quoted('hello')})",
            f"bucketOf({quoted('hello')}, 16)",
            f"checksumMatches({quoted('hello')}, 907060870)",
            "spreadOf([" + quoted("a") + ", " + quoted("b") + "], 4)",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
