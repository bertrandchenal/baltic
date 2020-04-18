from uuid import uuid4
from numpy import array

import pytest
import zarr

from baltic import Segment, Schema


@pytest.fixture
def frame():
    FACTOR = 100_000
    names = [str(uuid4()) for _ in range(5)]
    return {
        'value': array([1.1, 2.2, 3.3, 4.4, 5.5] * FACTOR),
        'category': array(names * FACTOR),
    }


@pytest.fixture
def sgm(frame):
    schema = Schema({
        'category': 'dim',
        'value': 'msr',
    })
    sgm = Segment(schema)
    sgm.write(frame)
    return sgm


def test_read_segment(sgm, frame):
    res = sgm.read('category', 'value')

    for col in res:
        assert (res[col][:] == frame[col]).all()


def test_copy_segment(sgm):
    group = zarr.group()

    for col in sgm.schema.columns:
        sgm.copy(col, group)
        assert (sgm[col][:] == group[col][:]).all()