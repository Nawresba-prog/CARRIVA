from backend import accesscodes as ac

ROLES = {"candidate", "approver", "admin"}


def test_parse_valid_and_invalid_entries():
    codes, warn = ac.parse("Alpha-Secret-1:approver, Beta-Secret-22:candidate,court:admin,Gamma-Secret-3:root,Alpha-Secret-1:admin,,sanssep", ROLES)
    assert codes == {"Alpha-Secret-1": "approver", "Beta-Secret-22": "candidate"} and len(warn) == 4


def test_code_may_contain_colon():
    codes, _ = ac.parse("abc:def-ghi-jkl:admin", ROLES)
    assert codes == {"abc:def-ghi-jkl": "admin"}


def test_check_constant_behaviour():
    codes, _ = ac.parse("Alpha-Secret-1:approver,Beta-Secret-22:candidate", ROLES)
    sub, role = ac.check(codes, "Beta-Secret-22")
    assert role == "candidate" and sub.startswith("u-") and "Beta" not in sub and sub == ac.subject("Beta-Secret-22")
    assert ac.check(codes, "beta-secret-22") is None and ac.check(codes, "") is None and ac.check(codes, None) is None
    assert ac.check({}, "x" * 12) is None
    assert ac.subject("a" * 12) != ac.subject("b" * 12)
