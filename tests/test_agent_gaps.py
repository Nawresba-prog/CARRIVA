import json
import os
import tempfile
from datetime import datetime, timezone

import sys
from unittest.mock import MagicMock

try:
    import langgraph  # noqa: F401
except ImportError:      # test sans installer langgraph : seules les fonctions pures de agent.py sont vérifiées
    for _n in ("langgraph", "langgraph.types", "langgraph.checkpoint", "langgraph.checkpoint.memory", "langgraph.graph"):
        sys.modules[_n] = MagicMock()

from backend import agent, replies, store


def test_store_roundtrip_datetime_and_atomic(tmp_path):
    d = str(tmp_path / "x")
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    assert store.save(d, "approvals", {"a": {"expires_at": now, "n": [1, 2], "s": {"b", "a"}}})
    got = store.load(d, "approvals", {})
    assert got["a"]["expires_at"] == now and got["a"]["n"] == [1, 2] and got["a"]["s"] == ["a", "b"]
    assert not [f for f in os.listdir(d) if f.endswith(".tmp")]
    assert store.load(d, "absent", "dflt") == "dflt" and store.load(None, "approvals", 7) == 7 and store.save("", "x", {}) is False


def test_store_survives_corrupt_file(tmp_path):
    (tmp_path / "approvals.json").write_text("{not json", encoding="utf-8")
    assert store.load(str(tmp_path), "approvals", {"ok": 1}) == {"ok": 1}


def test_insecure_defaults():
    assert store.insecure_defaults("prod", "j" * 32, "i" * 32) == []
    bad = " ".join(store.insecure_defaults("prod", "dev-only-change-me", "dev-internal-secret"))
    assert "JWT_SECRET" in bad and "INTERNAL_SECRET" in bad
    assert any("identiques" in x for x in store.insecure_defaults("prod", "s" * 20, "s" * 20))
    assert any("dev-token" in x for x in store.insecure_defaults("dev", "j" * 32, "i" * 32))
    assert any("trop court" in x for x in store.insecure_defaults("prod", "short", "i" * 32))


def test_dry_run_is_simulated_not_sent():
    assert agent.send_status({"dryRun": True, "to": "a@b.co"}) == "simulated"
    assert agent.send_status({"id": "m1", "to": "a@b.co"}) == "sent"
    assert agent.send_status({"manual": True}) == "ready"


def test_checkpointer_falls_back_to_memory_without_sqlite_package(tmp_path):
    cp, persistent = agent.make_checkpointer(str(tmp_path / "c.sqlite"))
    assert cp is not None and persistent in (True, False)
    assert agent.make_checkpointer(None)[1] is False


def test_replies_match_exact_recipient_only():
    ap = [{"id": "A", "status": "sent", "draft": {"to": "rh@acme.fr"}}, {"id": "B", "status": "pending", "draft": {"to": "rh@acme.fr"}},
          {"id": "C", "status": "sent", "kind": "followup", "draft": {"to": "rh@acme.fr"}}, {"id": "D", "status": "simulated", "draft": {"to": "rh@acme.fr"}}]
    msgs = [{"from_email": "RH@acme.fr", "subject": "Re: Candidature", "body": "Merci, nous revenons vers vous."},
            {"from_email": "autre@acme.fr", "subject": "Re", "body": "x"},
            {"from_email": "rh@acme.fr", "subject": "News", "body": "x", "auto": True}]
    assert replies.match(ap, msgs) == [{"approval_id": "A", "email": "rh@acme.fr", "optout": False}]


def test_replies_detect_stop_in_several_languages():
    ap = [{"id": "A", "status": "sent", "draft": {"to": "rh@acme.fr"}}]
    for body in ("STOP", "Merci de ne plus me contacter.", "Please unsubscribe me", "Bitte abmelden", "إلغاء الاشتراك"):
        r = replies.match(ap, [{"from_email": "rh@acme.fr", "subject": "", "body": body}])
        assert r and r[0]["optout"], body
    assert not replies.match(ap, [{"from_email": "rh@acme.fr", "subject": "", "body": "Nous avons bien reçu votre CV, bonne journée."}])[0]["optout"]
