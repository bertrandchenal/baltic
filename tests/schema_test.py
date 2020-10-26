from numpy import asarray
from pandas import DataFrame

from lakota import Schema
from lakota.utils import strpt


def test_vlen_codecs():
    for codecs in ("", "vlen-utf8", "vlen-utf8 gzip"):
        schema = Schema(f"val str*  |{codecs}")

        arr = asarray(["ham", "spam"])
        buff = schema["val"].encode(arr)
        arr2 = schema["val"].decode(buff)

        assert all(arr == arr2)
        assert arr.dtype == arr2.dtype


def test_schema_from_frame():
    frm = {
        "timestamp": asarray(["2020-01-01", "2020-01-02"], dtype="M8[s]"),
        "float": asarray([1, 2], dtype="float"),
        "int": asarray([1, 2], dtype="int"),
        "str": asarray([1, 2], dtype="U"),
    }

    for use_df in (True, False):
        if use_df:
            frm = DataFrame(frm)
        schema = Schema.from_frame(frm, ["timestamp"])
        assert schema["str"].dt == "O"
        assert schema["timestamp"].dt == "M8[s]"
        assert schema["int"].dt == "int"
        assert schema["float"].dt == "float"


def test_serialize():
    schema = Schema(
        """
    timestamp timestamp*
    float f8
    int i8
    str str
    """
    )

    ts = strpt("2020-01-01")
    values = (ts, 1.1, 1, "one")
    expected = ("2020-01-01 00:00:00", "1.1", "1", "one")
    assert schema.serialize(values) == expected
    assert schema.deserialize(expected) == values
