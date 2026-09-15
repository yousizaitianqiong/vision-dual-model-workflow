from scripts.check_public_surface import find_violations


def test_public_surface_is_clean():
    assert find_violations() == []
