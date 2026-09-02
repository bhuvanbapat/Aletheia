"""Directive section 90: the complete end-to-end incident simulation, atomic.

Fresh server + fresh DB. All 20 steps asserted in one run.
Run: restart server, then `python tests/e2e_directive90.py`
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "http://localhost:8010"
step_results: list[tuple[int, str, bool, str]] = []


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=120) as resp:
        return json.loads(resp.read())


def post(path: str, body=None):
    data = json.dumps(body).encode() if body is not None else b"{}"
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def step(n: int, name: str, fn):
    try:
        detail = fn()
        step_results.append((n, name, True, str(detail)[:100]))
        print(f"  [{n:2d}] PASS  {name}" + (f" - {detail}" if detail else ""))
    except Exception as exc:
        step_results.append((n, name, False, str(exc)[:200]))
        print(f"  [{n:2d}] FAIL  {name} - {exc}")
        raise SystemExit(1)


print("=== DIRECTIVE-90 END-TO-END: deployment -> DB exhaustion -> full lifecycle ===")

state: dict = {}


def s1():
    deps = get("/api/deployments")
    target = [d for d in deps if d["service"] == "payments-service" and d["version"] == "v2.4.1"]
    assert target, f"payments-service v2.4.1 deployment missing: {[d['service'] for d in deps]}"
    state["dep_time"] = target[0]["timestamp"]
    return f"deployment at {target[0]['timestamp']}"


def s2():
    m = get("/api/metrics?service=orders-db&metric=db_latency_ms&minutes=120")
    vals = [p["value"] for p in m["series"]]
    assert max(vals) > 1000, f"DB latency never degraded (max {max(vals):.0f})"
    return f"db_latency peaked at {max(vals):.0f} ms"


def s3():
    m = get("/api/metrics?service=payments-service&metric=p95_latency_ms&minutes=120")
    vals = [p["value"] for p in m["series"]]
    assert max(vals) > 700, f"payments latency never rose (max {max(vals):.0f})"
    return f"payments p95 peaked at {max(vals):.0f} ms"


def s4():
    m = get("/api/metrics?service=orders-service&metric=error_rate&minutes=120")
    vals = [p["value"] for p in m["series"]]
    assert max(vals) > 10, f"orders errors never rose (max {max(vals):.0f})"
    return f"orders error_rate peaked at {max(vals):.0f}%"


def s5():
    incs = get("/api/incidents")
    target = [i for i in incs if i["scenario_id"] == "db_connection_exhaustion"]
    assert target, "flagship incident not detected/created"
    state["inc"] = target[0]["id"]
    return state["inc"]


def s6():
    inc = get(f"/api/incidents/{state['inc']}")
    assert len(inc["affected_services"]) >= 3
    assert inc["category"] == "database_exhaustion"
    return f"category={inc['category']} correlated, {len(inc['affected_services'])} services"


def s7():
    tl = get(f"/api/incidents/{state['inc']}/timeline")
    assert len(tl) >= 5, f"timeline too thin ({len(tl)})"
    kinds = {t["kind"] for t in tl}
    assert "deployment" in kinds, f"deployment missing from timeline: {kinds}"
    return f"{len(tl)} entries, kinds={sorted(kinds)}"


def s8():
    impact = get("/api/topology/impact/orders-db")
    for svc in ("payments-service", "orders-service", "api-gateway"):
        assert svc in impact["affected_if_degraded"], f"{svc} missing from impact radius"
    return "downstream impact: payments, orders, gateway"


def s9():
    inv = post(f"/api/incidents/{state['inc']}/investigate")
    assert inv["status"] == "completed"
    state["run_id"] = inv["run_id"]
    return f"run {inv['run_id']}, {len(inv['tool_calls'])} tool calls, demo={inv['demo_mode']}"


def s10():
    ev = get(f"/api/incidents/{state['inc']}/evidence")
    assert len(ev) >= 5, f"only {len(ev)} evidence rows"
    kinds = {e["kind"] for e in ev}
    assert "metric" in kinds
    return f"{len(ev)} evidence rows, kinds={sorted(kinds)}"


def s11():
    hyps = get(f"/api/incidents/{state['inc']}/hypotheses")
    assert len(hyps) >= 2
    state["top_hyp"] = hyps[0]["statement"]
    return f"{len(hyps)} hypotheses, top: {hyps[0]['statement'][:60]}"


def s12():
    inv = post(f"/api/incidents/{state['inc']}/investigate")
    assert inv["root_cause"] and "connection pool" in inv["root_cause"].lower()
    assert inv["root_cause_confidence"] > 0.5
    return f"ranked #1: {inv['root_cause']} ({inv['root_cause_confidence']})"


def s13():
    rems = get(f"/api/incidents/{state['inc']}/remediations")
    assert rems, "no remediation proposed"
    state["rem"] = rems[-1]["id"]
    return f"{rems[-1]['action']} proposed (risk {rems[-1]['risk']})"


def s14():
    rems = get(f"/api/incidents/{state['inc']}/remediations")
    rem = [r for r in rems if r["id"] == state["rem"]][0]
    assert rem["approval_state"] == "pending", f"approval state is {rem['approval_state']}"
    return "approval state pending (gate active)"


def s15():
    blocked = post(f"/api/remediations/{state['rem']}/execute")
    assert blocked["executed"] is False and blocked["status"] == "blocked"
    return "execution correctly blocked before approval"


def s16():
    post(f"/api/remediations/{state['rem']}/approve", {"approved": True, "approver": "directive90"})
    ex = post(f"/api/remediations/{state['rem']}/execute")
    assert ex["executed"] is True
    return "simulated execution complete (recovery telemetry generated)"


def s17():
    ver = post(f"/api/incidents/{state['inc']}/verify")
    assert ver["outcome"] in ("recovered", "partial"), f"outcome {ver['outcome']}"
    assert len(ver["evidence"]) >= 3
    inc = get(f"/api/incidents/{state['inc']}")
    expected = "resolved" if ver["outcome"] == "recovered" else "mitigated"
    assert inc["status"] == expected, f"status {inc['status']} != {expected}"
    return f"outcome={ver['outcome']}, incident -> {inc['status']}"


def s18():
    pm = post(f"/api/incidents/{state['inc']}/postmortem")
    for section in ("## Summary", "## Timeline", "## Root Cause", "## Recovery"):
        assert section in pm["content_markdown"], f"missing {section}"
    assert state["top_hyp"][:30].lower() in pm["content_markdown"].lower() or "connection pool" in pm["content_markdown"].lower()
    return f"postmortem {len(pm['content_markdown'])} chars, all sections present"


def s19():
    trace = get(f"/api/agent/runs/{state['run_id']}/trace")
    assert len(trace) >= 20, f"trace too thin ({len(trace)})"
    statuses = [t["status"] for t in trace]
    assert all(s in ("ok", "error") for s in statuses)
    errs = statuses.count("error")
    return f"{len(trace)} tool calls ({errs} errors), durations recorded"


def s20():
    rep = post("/api/evaluations/run")
    agg = rep["aggregate"]
    assert agg["n_scenarios"] == 5
    cases = get("/api/evaluations")
    assert len(cases) >= 5
    return (f"recorded {len(cases)} eval cases; aggregate RC={agg['root_cause_accuracy']}, "
            f"remediation={agg['remediation_accuracy']}, recovery={agg['recovery_verification_rate']}")


for n, name, fn in [
    (1, "deployment event appears", s1),
    (2, "DB metrics degrade", s2),
    (3, "payments latency rises", s3),
    (4, "orders errors rise", s4),
    (5, "incident detected", s5),
    (6, "incident correlated", s6),
    (7, "timeline generated", s7),
    (8, "topology downstream impact", s8),
    (9, "AI investigates", s9),
    (10, "evidence collected", s10),
    (11, "hypotheses generated", s11),
    (12, "root cause ranked", s12),
    (13, "remediation recommended", s13),
    (14, "approval state shown", s14),
    (15, "remediation blocked pre-approval", s15),
    (16, "remediation simulated", s16),
    (17, "recovery measured + status transition", s17),
    (18, "postmortem generated", s18),
    (19, "agent trace available", s19),
    (20, "evaluation result recorded", s20),
]:
    step(n, name, fn)

print()
passed = sum(1 for _, _, ok, _ in step_results if ok)
print(f"DIRECTIVE-90 E2E: {passed}/{len(step_results)} steps PASSED")
sys.exit(0)
