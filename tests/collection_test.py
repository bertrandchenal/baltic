import pytest

from lakota.repo import Repo, Schema

schema = Schema(["timestamp timestamp*", "value float"])
frame = {"timestamp": [1, 2, 3], "value": [11, 12, 13]}


def test_create():
    frame = {"timestamp": [1, 2, 3], "value": [11, 12, 13]}
    # Create repo / collection / series
    repo = Repo()
    temperature = repo.create_collection(schema, "temperature")
    temp_bru = temperature / "Brussels"
    temp_bru.write(frame)

    # Read it back
    temperature = repo / "temperature"
    temp_bru = temperature / "Brussels"
    assert temp_bru.frame() == frame

    assert list(repo.ls()) == ["temperature"]
    assert list(temperature.ls()) == ["Brussels"]

    # Test double creation
    repo.create_collection(schema, "temperature")
    assert sorted(repo.ls()) == ["temperature"]
    assert len(list(repo.collection_series.changelog)) == 1
    repo.create_collection(schema, "temperature", "wind")
    assert sorted(repo.ls()) == ["temperature", "wind"]


def test_multi():
    repo = Repo()
    temperature = repo.create_collection(schema, "temperature")
    temp_bru = temperature / "Brussels"
    temp_bru.write(frame)

    frame_ory = frame.copy()
    frame_ory["value"] = [21, 22, 23]
    temp_ory = temperature / "Paris"
    temp_ory.write(frame_ory)

    assert temp_bru.frame() == frame
    assert temp_ory.frame() == frame_ory

    assert len(list(repo.revisions())) == 1
    assert len(list(temperature.revisions())) == 2
    assert len(list(temp_bru.revisions())) == 1

    assert list(temperature) == ["Brussels", "Paris"]


@pytest.mark.parametrize("archive", [False, True])
def test_squash(archive):
    repo = Repo()
    other_frame = frame.copy()
    other_frame["value"] = [1, 2, 3]
    temperature = repo.create_collection(schema, "temperature")
    assert temperature.squash(archive=archive) is None

    temp_bru = temperature / "Brussels"
    temp_bru.write(other_frame)

    # Capture changelog state
    prev_commits = list(temperature.changelog)
    assert len(prev_commits) == 1

    # Squash
    new_commit = temperature.squash(archive=archive)
    # New commit should have the same key (timestamp may change)
    old_key = prev_commits[0].rsplit("-", 1)[1]
    new_key = new_commit.child.rsplit("-", 1)[1]
    assert old_key == new_key
    assert len(list(temperature.changelog)) == 1

    temp_bru.write(frame)
    temp_ory = temperature / "Paris"
    temp_ory.write(frame)

    # Squash collection
    temperature.squash(archive=archive)
    assert len(list(temperature.changelog)) == 1

    # Read data back
    assert list(temperature) == ["Brussels", "Paris"]
    for label in ("Brussels", "Paris"):
        series = temperature / label
        assert len(list(series.revisions())) == 1


def test_pack():
    repo = Repo()
    other_frame = frame.copy()
    other_frame["value"] = [1, 2, 3]
    temperature = repo.create_collection(schema, "temperature")
    assert temperature.pack() is None

    temp_bru = temperature / "Brussels"
    temp_bru.write(other_frame)
    assert temperature.pack() is None
    temp_ory = temperature / "Paris"
    temp_ory.write(frame)
    assert temperature.pack() is not None
