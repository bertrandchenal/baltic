from bisect import bisect_left, bisect_right

import numexpr
from numpy import array_equal, concatenate

from .utils import hashed_path

# TODO Frame does to much stuff, it should be splitted in two (one
# that act like a db cursor and one container). MetaFrame, ShallowFrame, ResultSet, Collection?


class Frame:
    """
    DataFrame-like object
    """

    def __init__(self, schema, columns):
        self.schema = schema
        self.columns = columns

    @classmethod
    def from_segments(cls, schema, *segments, limit=None):
        cols = {}
        for name in schema.columns:
            arrays = []
            slim = limit
            for sgm in segments:
                arr = sgm.read(name, limit)
                if slim is not None:
                    arr = arr[:slim]
                    slim -= len(sgm)
                arrays.append(arr)
            cols[name] = concatenate(arrays)
        return Frame(schema, cols)

    def df(self, *columns):
        from pandas import DataFrame

        return DataFrame({c: self[c] for c in self.schema.columns})

    def mask(self, mask_ar):
        cols = {name: self.data[name][mask_ar] for name in self.data}
        return Frame(self.schema, cols)

    def eval(self, expr):
        res = numexpr.evaluate(expr, local_dict=self)
        return res

    @property
    def empty(self):
        return len(self) == 0

    def rowdict(self, *idx):
        pos = self.index(*self.schema.deserialize(idx))
        values = self.schema.row(pos, full=True)
        return dict(zip(self.schema.columns, values))

    def index_slice(self, start=None, stop=None, closed="left"):
        """
        Slice between two index value. `closed` can be "left" (default),
        "right" or "both". If end is None, the code will use `start`
        as value and enforce "both" as value for `closed`
        """
        idx_start = idx_stop = None
        if start:
            idx_start = self.index(start, right=closed == "right")
        if stop:
            idx_stop = self.index(stop, right=closed in ("both", "right"))
        return self.slice(idx_start, idx_stop)

    def index(self, values, right=False):
        if not values:
            return None
        lo = 0
        hi = len(self)
        for name, val in zip(self.schema.idx, values):
            arr = self.columns[name]
            lo = bisect_left(arr, val, lo=lo, hi=hi)
            hi = bisect_right(arr, val, lo=lo, hi=hi)

        if right:
            return hi
        return lo

    def slice(self, start=None, stop=None):
        """
        Slice between both position start and end
        """
        # Replace None by actual values
        slc = slice(*(slice(start, stop).indices(len(self))))
        # Build new frame
        cols = {}
        for name in self.schema.columns:
            cols[name] = self.columns[name][slc]
        return Frame(self.schema, cols)

    def __eq__(self, other):
        return all(array_equal(self[c], other[c]) for c in self.schema.columns)

    def __len__(self):
        if not self.columns:
            return 0
        name = next(iter(self.schema.columns))
        return len(self.columns[name])

    def keys(self):
        return self.schema.columns

    def write(self, df, reverse_idx=False):
        # FIXME Frame.write Frame.from_df and Frame.save should be extracted. and hexdigets (called by save) can be put on schema
        for name in self.schema.columns:
            arr = df[name]
            if hasattr(arr, "values"):
                arr = arr.values
            self[name] = arr

    def __setitem__(self, name, arr):
        # Make sure we have a numpy array
        arr = self.schema[name].cast(arr)
        if len(arr) != len(self):
            raise ValueError("Lenght mismatch")
        self.columns[name] = arr

    def __getitem__(self, by):
        # By slice -> return a frame
        if isinstance(by, slice):
            start = by.start and self.schema.deserialize(by.start)
            stop = by.stop and self.schema.deserialize(by.stop)
            return self.index_slice(start, stop)

        # By column name -> return an array
        return self.columns[by]


class ShallowSegment:
    def __init__(self, schema, pod, digests, start, stop, length, closed="left"):
        self.schema = schema
        self.pod = pod
        self.start = start
        self.stop = stop
        self.length = length
        self.digest = dict(zip(schema, digests))

    def slice(self, start, stop, closed="left"):
        assert stop >= start
        # empty_test contains any condition that would result in an empty segment
        empty_test = [
            start > self.stop,
            stop < self.start,
            start == self.stop and closed not in ("both", "left"),
            stop == self.start and closed not in ("both", "right"),
        ]
        if any(empty_test):
            return EmptySegment(start, stop, self.schema)

        # skip_tests list contains all the tests that have to be true to
        # _not_ do the slice and return self
        skip_tests = (
            [start <= self.start]
            if closed in ("both", "left")
            else [start < self.start]
        )
        skip_tests.append(
            stop >= self.stop if closed in ("both", "righ") else stop > self.stop
        )
        if all(skip_tests):
            return self
        else:
            print("slice!")
            # Materialize arrays
            frm = Frame(self.schema, {name: self.read(name) for name in self.schema})
            # Compute slice and apply it
            frm = frm.index_slice(start, stop, closed=closed)
            return Segment(start, stop, frm)

    def __len__(self):
        return self.length

    def read(self, name, limit=None):
        folder, filename = hashed_path(self.digest[name])
        data = self.pod.cd(folder).read(filename)
        arr = self.schema[name].decode(data)
        return arr[:limit]

    @property
    def empty(self):
        return self.length == 0


class Segment:
    def __init__(self, start, stop, frm):
        self.start = start
        self.stop = stop
        self.frm = frm

    def read(self, name, limit=None):
        return self.frm[name][:limit]


class EmptySegment:
    def __init__(self, start, stop, schema):
        self.start = start
        self.stop = stop
        self.schema = schema

    def __len__(self):
        return 0

    def read(self, name, limit=None):
        return self.schema[name].cast([])

    @property
    def empty(self):
        return True