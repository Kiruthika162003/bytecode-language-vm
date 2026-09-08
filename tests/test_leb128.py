from __future__ import annotations

import pytest

from ember.errors import Compile
from ember.leb128 import (
    decode_signed,
    decode_unsigned,
    encode_signed,
    encode_unsigned,
)


class TestUnsigned:
    def test_round_trip(self):
        for value in (0, 1, 127, 128, 255, 16383, 16384, 10**6, 2**64):
            data = encode_unsigned(value)
            decoded, offset = decode_unsigned(data)
            assert decoded == value
            assert offset == len(data)

    def test_small_values_cost_one_byte(self):
        assert len(encode_unsigned(0)) == 1
        assert len(encode_unsigned(127)) == 1

    def test_the_length_grows_with_magnitude(self):
        assert len(encode_unsigned(128)) == 2
        assert len(encode_unsigned(16383)) == 2
        assert len(encode_unsigned(16384)) == 3

    def test_a_negative_value_is_refused(self):
        with pytest.raises(Compile):
            encode_unsigned(-1)


class TestSigned:
    def test_round_trip(self):
        for value in (0, 1, -1, 63, 64, -64, -65, 127, -128, 10**9, -(10**9)):
            data = encode_signed(value)
            decoded, offset = decode_signed(data)
            assert decoded == value
            assert offset == len(data)

    def test_minus_one_stays_one_byte(self):
        # the whole point of the signed variant: no sign-extension blowup
        assert len(encode_signed(-1)) == 1


class TestSequential:
    def test_values_decode_one_after_another(self):
        buffer = b"".join(encode_unsigned(v) for v in (1, 300, 7))
        values = []
        offset = 0
        while offset < len(buffer):
            value, offset = decode_unsigned(buffer, offset)
            values.append(value)
        assert values == [1, 300, 7]

    def test_decoding_can_start_at_an_offset(self):
        buffer = b"\xff" + encode_unsigned(300)
        value, offset = decode_unsigned(buffer, 1)
        assert value == 300
        assert offset == len(buffer)


class TestTruncation:
    def test_an_unsigned_stream_ending_mid_value_is_refused(self):
        with pytest.raises(Compile):
            decode_unsigned(bytes([0x80]))

    def test_a_signed_stream_ending_mid_value_is_refused(self):
        with pytest.raises(Compile):
            decode_signed(bytes([0x80]))
