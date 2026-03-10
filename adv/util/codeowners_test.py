from .codeowners import CodeOwners


def test_codeowners_basic():
    codeowners = CodeOwners("""
    *      ivartj
    /zoo/  alice
    """)
    assert "ivartj" in codeowners.assignees("foo.txt")
    assert "ivartj" in codeowners.assignees("foo/bar.txt")
    assert "ivartj" not in codeowners.assignees("zoo/bar.txt")
