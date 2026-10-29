"""Orchestration LangGraph de la candidature.

draft -> approval_gate (interrupt : le graphe est suspendu, état persisté par le checkpointer)
      -> send (seulement si approuvé, hash revérifié) -> END

Un thread = une candidature (thread_id = id d'approbation).
En production, remplacer MemorySaver par un checkpointer persistant (PostgresSaver).
"""
from __future__ import annotations

import logging
from typing import Callable, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class AppState(TypedDict, total=False):
    cv: dict
    job: dict
    draft: dict
    approved_hash: str
    status: str  # pending | rejected | sent | simulated | ready | failed
    result: dict
    error: str


log = logging.getLogger("career.agent")


def send_status(res: dict) -> str:
    """ready = lettre approuvée à envoyer via l'annonce ; simulated = mode test (DRY_RUN), rien n'est parti : ne jamais l'afficher comme « envoyé » ; sinon sent."""
    if res.get("manual"):
        return "ready"
    if res.get("dryRun"):
        return "simulated"
    return "sent"


def make_checkpointer(path: str | None = None):
    """Checkpointer SQLite persistant (les approbations en attente survivent à un redémarrage) si `langgraph-checkpoint-sqlite` est installé ;
    sinon MemorySaver (état perdu au redémarrage : à signaler à l'appelant via `persistent`). Retourne (checkpointer, persistent)."""
    if path:
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver
            return SqliteSaver(sqlite3.connect(path, check_same_thread=False)), True
        except Exception as exc:  # noqa: BLE001
            log.warning("checkpointer SQLite indisponible (%s) : état en mémoire, perdu au redémarrage", exc)
    return MemorySaver(), False


def build_graph(
    draft_fn: Callable[[dict, dict], dict],
    send_fn: Callable[[dict, dict], dict],
    hash_fn: Callable[[dict], str],
    checkpointer=None,
):
    def draft_node(state: AppState) -> AppState:
        if state.get("draft"):  # brouillon fourni (relance) : il passe quand même par l'Approval Gate
            return {"status": "pending"}
        return {"draft": draft_fn(state["cv"], state["job"]), "status": "pending"}

    def approval_gate(state: AppState) -> AppState:
        # Suspend l'exécution. Rien avant cet appel n'a d'effet externe (le noeud est rejoué à la reprise).
        answer = interrupt({"draft": state["draft"], "hash": hash_fn(state["draft"])})
        if answer.get("decision") != "approve":
            return {"status": "rejected"}
        draft = dict(state["draft"])
        if answer.get("body"):
            draft["body"] = answer["body"]  # l'édition de l'humain fait partie de ce qui est approuvé
        return {"draft": draft, "approved_hash": hash_fn(draft), "status": "approved"}

    def send_node(state: AppState) -> AppState:
        if hash_fn(state["draft"]) != state["approved_hash"]:  # anti-TOCTOU
            return {"status": "failed", "error": "content changed after approval"}
        try:
            res = send_fn(state["draft"], state["cv"])
            return {"result": res, "status": send_status(res)}
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "error": str(exc)}

    g = StateGraph(AppState)
    g.add_node("draft", draft_node)
    g.add_node("approval_gate", approval_gate)
    g.add_node("send", send_node)
    g.add_edge(START, "draft")
    g.add_edge("draft", "approval_gate")
    g.add_conditional_edges("approval_gate", lambda s: "send" if s.get("status") == "approved" else END, ["send", END])
    g.add_edge("send", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())
