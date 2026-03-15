from .codeowners import CodeOwners


def test_codeowners_basic():
    codeowners = CodeOwners("""
    *      ivartj
    /zoo/  alice
    """)
    assert "ivartj" in codeowners("foo.txt")
    assert "ivartj" in codeowners("foo/bar.txt")
    assert "ivartj" not in codeowners("zoo/bar.txt")
