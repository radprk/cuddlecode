from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from .rubric import RUBRIC
from .indexing import retrieve

class State(BaseModel):
    repo_url: str
    run_id: str
    files: list
    vector: Any
    summary: Optional[str] = None
    results: list = []

def summarize_node(state: State) -> Dict[str, Any]:
    # No external LLM yet; keep deterministic.
    paths = [f["path"] for f in state.files]
    summary = "Project files analyzed:\n- " + "\n- ".join(paths[:20])
    return {"summary": summary}

def grade_node(state: State) -> Dict[str, Any]:
    results = []
    for dim in RUBRIC:
        evidence = retrieve(state.vector, dim["prompt"], k=6)
        # Basic heuristic scoring for now; replace with LLM later
        score = 2
        if dim["id"] == "testing":
            has_tests = any("test" in e["path"].lower() for e in evidence)
            score = 3 if has_tests else 1
        results.append({
            "dimension": dim["id"],
            "score": score,
            "confidence": 0.4,
            "evidence": evidence[:3],
            "notes": "Heuristic baseline (replace with LLM grading)."
        })
    return {"results": results}

def feedback_node(state: State) -> Dict[str, Any]:
    strengths = [r["dimension"] for r in sorted(state.results, key=lambda x: -x["score"])[:2]]
    improvements = [r["dimension"] for r in sorted(state.results, key=lambda x: x["score"])[:2]]
    fb = {
        "strengths": strengths,
        "improvements": improvements,
        "next_assignment": "Add or improve automated tests and document how to run them."
    }
    return {"feedback": fb}

def build_graph():
    g = StateGraph(State)
    g.add_node("summarize", summarize_node)
    g.add_node("grade", grade_node)
    g.add_node("feedback", feedback_node)

    g.set_entry_point("summarize")
    g.add_edge("summarize", "grade")
    g.add_edge("grade", "feedback")
    g.add_edge("feedback", END)
    return g.compile()


