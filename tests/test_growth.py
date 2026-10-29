import httpx

from backend import growth as G


class R:
    def __init__(self, code, text="ok"):
        self.status_code, self._t = code, text
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")
    def json(self):
        return {"content": [{"type": "text", "text": self._t}]}


def seq(*items):
    calls = []
    def post(**kw):
        calls.append(kw)
        it = items[min(len(calls) - 1, len(items) - 1)]
        if isinstance(it, Exception):
            raise it
        return it
    post.calls = calls
    return post


def test_system_prompt_has_quality_date_memory_and_service():
    for n in G.SERVICES:
        s = G.build_system(n, "en", {"name": "Acme", "sector": "Bakery"}, today="25/10/2026")
        assert "STANDARD DE QUALITÉ" in s and "25/10/2026" in s and "Acme" in s and "English" in s and G.SERVICES[n][:20] in s
    assert "Strategy, ESG" in G.build_system(6, "fr", {}) and "Facebook" not in G.build_system(6, "fr", {}).split("SERVICE 6")[0]


def test_memory_is_data_not_instructions():
    s = G.build_system(1, "fr", {"name": "x" * 1000})
    assert "x" * 301 not in s


def test_trim_history_keeps_recent_and_starts_with_user():
    msgs = []
    for i in range(10):
        msgs += [{"role": "user", "content": f"q{i} " + "a" * 3000}, {"role": "assistant", "content": f"r{i} " + "b" * 3000}]
    msgs.append({"role": "user", "content": "dernier"})
    out = G.trim_history(msgs, 14000)
    assert out[-1]["content"] == "dernier" and out[0]["role"] == "user" and sum(len(m["content"]) for m in out) <= 14000 + 3010 and len(out) < len(msgs)
    assert G.trim_history([{"role": "user", "content": "z" * 50000}], 100) == [{"role": "user", "content": "z" * 50000}]   # le dernier message n'est jamais perdu


def test_retry_on_rate_limit_then_success():
    G.os.environ["ANTHROPIC_API_KEY"] = "k"
    post, waits = seq(R(429), R(503), R(200, "bonjour")), []
    out = G.chat(1, "fr", {}, [{"role": "user", "content": "salut"}], post=post, sleep=waits.append)
    assert out == "bonjour" and len(post.calls) == 3 and waits == [1.5, 3.0]


def test_no_retry_on_client_error_and_gives_up_after_three():
    G.os.environ["ANTHROPIC_API_KEY"] = "k"
    post = seq(R(400))
    try:
        G.chat(1, "fr", {}, [{"role": "user", "content": "x"}], post=post, sleep=lambda s: None); assert False
    except httpx.HTTPError:
        assert len(post.calls) == 1
    post = seq(httpx.TimeoutException("t"), httpx.TransportError("c"), httpx.TimeoutException("t"))
    try:
        G.chat(1, "fr", {}, [{"role": "user", "content": "x"}], post=post, sleep=lambda s: None); assert False
    except httpx.TimeoutException:
        assert len(post.calls) == 3
    post = seq(R(503))
    try:
        G.chat(1, "fr", {}, [{"role": "user", "content": "x"}], post=post, sleep=lambda s: None); assert False
    except httpx.HTTPError:
        assert len(post.calls) == 3


def test_payload_uses_prompt_cache_and_requires_key():
    G.os.environ["ANTHROPIC_API_KEY"] = "k"
    post = seq(R(200))
    G.chat(2, "fr", {"name": "Acme"}, [{"role": "user", "content": "x"}], post=post)
    j = post.calls[0]["json"]
    assert j["system"][0]["cache_control"] == {"type": "ephemeral"} and "Acme" in j["system"][0]["text"] and j["messages"][-1]["content"] == "x"
    assert post.calls[0]["headers"]["x-api-key"] == "k"
    del G.os.environ["ANTHROPIC_API_KEY"]
    try:
        G.chat(1, "fr", {}, [{"role": "user", "content": "x"}], post=post); assert False
    except RuntimeError as e:
        assert str(e) == "no_key"
