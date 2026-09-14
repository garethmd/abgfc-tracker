def test_deliberately_failing():
    assert 1 == 2, "CI proof: this PR must be blocked"
