import pytest

from twin.common.payload import PayloadError, decode_payload, encode_payload


def test_roundtrip_with_unit():
    raw = encode_payload(1_700_000_000.1234, 23.5, "inlet_temp")
    assert b'"unit":"C"' in raw
    ts, value = decode_payload(raw)
    assert ts == pytest.approx(1_700_000_000.123)
    assert value == 23.5


@pytest.mark.parametrize("raw", [b"not json", b"{}", b'{"ts": 1}', b'{"ts": "x", "value": 1}', b'{"ts": 1, "value": NaN}'])
def test_decode_rejects_garbage(raw):
    with pytest.raises(PayloadError):
        decode_payload(raw)
