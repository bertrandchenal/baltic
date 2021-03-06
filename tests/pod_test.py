import pytest

from lakota import POD
from lakota.pod import FilePOD, MemPOD


def test_cd(pod):
    pod2 = pod / "ham"
    assert pod2.path.name == "ham"


def test_empty_ls():
    pod = POD.from_uri("file:///i-do-not-exists")
    with pytest.raises(FileNotFoundError):
        pod.ls()

    assert pod.ls(missing_ok=True) == []


def test_read_write(pod):
    data = bytes.fromhex("DEADBEEF")
    pod.write("key", data)
    assert pod.ls() == ["key"]
    res = pod.read("key")
    assert res == data


def test_multi_write(pod):
    data = bytes.fromhex("DEADBEEF")
    # First write
    res = pod.write("key", data)
    assert res == len(data)
    # second one
    res = pod.write("key", data)
    assert res is None


def test_write_delete(pod):
    data = bytes.fromhex("DEADBEEF")

    pod.write("key", data)
    pod.rm("key")
    assert pod.ls() == []


def test_write_delete_recursive(pod):
    data = bytes.fromhex("DEADBEEF")
    top_pod = pod.cd("top_dir")

    top_pod.write("sub_dir/key", data)
    if isinstance(pod, MemPOD):
        with pytest.raises(FileNotFoundError):
            top_pod.rm(".")
    elif isinstance(pod, FilePOD):
        with pytest.raises(OSError):
            top_pod.rm(".")
    # not test for S3, it seems that recurssion is implied

    top_pod.rm(".", recursive=True)
    assert pod.ls() == []


def test_write_clear(pod):
    assert pod.ls() == []
    data = bytes.fromhex("DEADBEEF")

    pod.write("key", data)
    pod.write("ham/key", data)
    pod.write("ham/spam/key", data)

    assert len(pod.ls()) == 2
    assert len(pod.ls("ham")) == 2
    assert len(pod.ls("ham/spam")) == 1
    pod.clear()
    assert (
        pod.ls(
            missing_ok=True  # moto_server delete the bucket when all keys are removed
        )
        == []
    )


def test_walk(pod):
    data = b""
    pod.write("ham/spam/foo", data)
    pod.write("bar/baz", data)
    pod.write("qux", data)

    assert sorted(pod.walk()) == ["bar/baz", "ham/spam/foo", "qux"]
    assert sorted(pod.walk(max_depth=10)) == ["bar/baz", "ham/spam/foo", "qux"]
    assert sorted(pod.walk(max_depth=3)) == ["bar/baz", "ham/spam/foo", "qux"]
    assert sorted(pod.walk(max_depth=2)) == ["bar/baz", "qux"]
    assert sorted(pod.walk(max_depth=1)) == ["qux"]
    assert sorted(pod.walk(max_depth=0)) == []
