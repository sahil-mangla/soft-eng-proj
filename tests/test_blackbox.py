import pytest

from tests.blackbox_cases import CASES


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_blackbox_case(case):
    actual, passed = case.execute()
    assert passed, f"{case.id} ({case.description}): expected {case.expected!r}, got {actual!r}"
