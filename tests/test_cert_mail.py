import base64

from backend import cert_mail as M


def test_message_is_localized_fixed_and_attaches_pdf():
    for lang in M.TEXTS:
        m = M.build_message("a@b.fr", lang, "Sara Haddad", "Python", "https://x/verify/1", b"%PDF-1.4 x", "abc")
        assert m["to"] == "a@b.fr" and "Sara Haddad" in m["body"] and "https://x/verify/1" in m["body"] and "{" not in m["body"] + m["subject"]
        assert base64.b64decode(m["attachment"]["data_b64"]).startswith(b"%PDF") and m["attachment"]["filename"] == "attestation_abc.pdf"
    assert M.build_message("a@b.fr", "zz", "S", "T", "u", b"x", "c")["subject"] == M.TEXTS["en"][0]


def test_header_injection_is_neutralised():
    m = M.build_message("a@b.fr", "fr", "Sara\r\nBcc: evil@x.org", "Cours\nX", "u", b"x", "c")
    assert "\r" not in m["body"].split("\n\n")[0] and "\n" not in m["subject"] and "Cours X" in m["body"]


def test_limiter_window_and_keys():
    t = [0.0]
    lim = M.Limiter(2, 10, clock=lambda: t[0])
    assert lim.allow("u") and lim.allow("u") and not lim.allow("u") and lim.allow("other")
    t[0] = 11.0
    assert lim.allow("u")
