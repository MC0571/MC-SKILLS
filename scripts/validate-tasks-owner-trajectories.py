#!/usr/bin/env python3
"""校验 Unit Owner 的结果约束；不把 fixture 或字段自报当真实运行证据。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from tasks_owner_trajectory_replay import evaluate, readback_digest
from tasks_owner_trajectory_schema import RULES, schema_errors

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "skills/tasks-owner/evals/trajectory_cases.jsonl"


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: case must be an object")
        rows.append(value)
    return rows


def run(path: Path, readbacks: dict[str, Any] | None = None) -> list[str]:
    failures: list[str] = []
    ids: set[str] = set()
    coverage = {rule: set() for rule in RULES}
    for line, case in enumerate(load_cases(path), 1):
        errors = schema_errors(case)
        if errors:
            failures.append(f"line {line}: {'; '.join(errors)}")
            continue
        if case["id"] in ids:
            failures.append(f"line {line}: duplicate case id")
        ids.add(case["id"])
        expected = case["expected"]
        violations = evaluate(case, (readbacks or {}).get(case["id"]))
        verdict = "fail" if violations else "pass"
        coverage[expected["rule_id"]].add(expected["verdict"])
        if verdict != expected["verdict"] or verdict == "fail" and expected["rule_id"] not in violations:
            failures.append(f"line {line} {case['id']}: expected {expected}, got {sorted(violations)}")
    if path.resolve() == DEFAULT_CASES:
        for rule, outcomes in coverage.items():
            if outcomes != {"pass", "fail"}:
                failures.append(f"{rule}: requires positive and negative cases")
    return failures


def self_test(path: Path) -> list[str]:
    failures = run(path)
    cases = {case["id"]: case for case in load_cases(path)}

    def check(identity: str, mutate, rule: str | None) -> None:
        candidate = copy.deepcopy(cases[identity])
        mutate(candidate)
        violations = evaluate(candidate)
        if (rule is None and violations) or (rule is not None and rule not in violations):
            failures.append(f"mutation {identity}: expected {rule or 'pass'}, got {sorted(violations)}")

    def facts(case: dict[str, Any], kind: str, occurrence: int = 0) -> dict[str, Any]:
        return [event["facts"] for event in case["events"] if event["kind"] == kind][occurrence]

    # 这三个反例在 v1 中被当作未消费的附加字段，均曾错误通过。
    check("hierarchical-independent-subunits-pass", lambda c: facts(c, "admission")["execution_mode_selection"].update(independently_admissible_subunits=[], write_carrier_overlap="shared:one-file"), "planning")
    check("systemic-preflight-pass", lambda c: facts(c, "preflight").update(covered_surfaces=["default"]), "planning")
    check("systemic-preflight-pass", lambda c: facts(c, "preflight")["sibling_scan"].update(status="missing"), "planning")
    check("lost-direct-event-readback-unlocks-successor-pass", lambda c: c["events"].pop(2), "schema")
    check("lost-direct-event-readback-unlocks-successor-pass", lambda c: facts(c, "completion_consumed").update(revision=2), "event_recovery")
    check("local-delivery-pass", lambda c: c["initial"]["authority"]["actions"].remove("write"), "authorization")
    check("local-delivery-pass", lambda c: facts(c, "write").update(carriers=["repo:src/../private"]), "authorization")
    check("independent-writers-and-legal-wait-pass", lambda c: facts(c, "admission", 1).update(carriers=["repo:src/a.py"]), "writer_safety")
    check("independent-writers-and-legal-wait-pass", lambda c: facts(c, "admission", 1).update(monitor_locator="none"), "event_recovery")
    check("local-delivery-pass", lambda c: facts(c, "unit_state").update(host_status="running", write_authority="active"), "writer_safety")
    check("local-delivery-pass", lambda c: facts(c, "fresh_review").update(head="old-head"), "review_integrity")
    check("local-delivery-pass", lambda c: next(e for e in c["events"] if e["kind"] == "fresh_review").update(unit_id="owner-main"), "review_integrity")
    check("local-delivery-pass", lambda c: facts(c, "publish")["check_results"][1].update(status="failed"), "review_integrity")
    check("local-delivery-pass", lambda c: facts(c, "publish")["check_results"][1].update(head="old-head"), "review_integrity")
    check("specific-user-check-override-pass", lambda c: facts(c, "publish")["verification_authority"]["overrides"][0].update(authority_locator="none"), "review_integrity")
    check("second-necessary-fix-with-new-evidence-pass", lambda c: facts(c, "finding_disposition", 1).update(evidence_digest="evidence:v1"), "review_integrity")
    check("second-necessary-fix-with-new-evidence-pass", lambda c: facts(c, "finding_disposition", 1).update(boundary_expansion="permission"), "review_integrity")
    check("owner-local-cleanup-pass", lambda c: facts(c, "cleanup").update(target_oid="unreviewed-user-commit"), "cleanup_safety")
    check("owner-local-cleanup-pass", lambda c: c["initial"]["authority"]["actions"].remove("cleanup"), "authorization")
    check("local-delivery-pass", lambda c: facts(c, "preflight").update(unconsumed_fake_gate="ready"), "schema")
    def omit_publish(case: dict[str, Any]) -> None:
        case["events"] = [e for e in case["events"] if e["kind"] != "publish"]
        for seq, event in enumerate(case["events"], 1):
            event["seq"] = seq

    # 收口检查不能依赖发布事件恰好存在；本地无 PR 交付复用同一检查来源。
    check("issue-does-not-waive-repository-check-fail", omit_publish, "review_integrity")
    check("local-no-pr-delivery-pass", lambda c: facts(c, "closeout")["check_results"][1].update(status="failed"), "review_integrity")
    check("independent-writers-and-legal-wait-pass", lambda c: facts(c, "write", 1).update(base_head="a1"), "review_integrity")
    check("independent-batch-publishes-while-other-writes-pass", lambda c: facts(c, "preflight").update(batch_locator="batch:b"), "writer_safety")
    check("acceptance-change-refreshed-verification-pass", lambda c: facts(c, "preflight", 1)["evidence_key"].update(acceptance_digest="acceptance:v1"), "review_integrity")
    check("environment-change-refreshed-verification-pass", lambda c: facts(c, "fresh_review", 1)["evidence_key"].update(environment_class="environment:local"), "review_integrity")
    check("rethink-new-investigation-resumes-same-scope-pass", lambda c: facts(c, "reassessment").update(evidence_revision="evidence:v1"), "review_integrity")
    check("user-decision-restores-only-original-scope-pass", lambda c: facts(c, "reassessment").update(user_decision_locator="none"), "authorization")
    # 不再因实现身份、模型、消息往返数或第二次必要修复本身判失败。
    check("independent-writers-and-legal-wait-pass", lambda c: c["events"][0]["args"].update(model="host-default"), None)
    check("second-necessary-fix-with-new-evidence-pass", lambda c: facts(c, "fresh_review", 1).update(reviewer_locator="reviewer:another"), None)
    check("local-delivery-pass", lambda c: facts(c, "publish")["verification_authority"]["sources"]["branch_protection"].update(locator="protection:main", required_checks=["repository-contracts"]), None)

    # 独立传入 readback 并绑定全部事件；改一个 live 标签、伪造 digest 或投影事实均不足。
    candidate = copy.deepcopy(cases["local-delivery-pass"])
    readback = dict(host_id="fixture-host:binding-self-test", source_locator="fixture-tool-record:binding-self-test", events=copy.deepcopy(candidate["events"]))
    candidate["source_kind"] = "live_readback"
    candidate["evidence"] = dict(host_id=readback["host_id"], source_locator=readback["source_locator"], readback_sha256=readback_digest(readback))
    if "evidence_binding" not in evaluate(candidate):
        failures.append("self-declared live trace was accepted without independent records")
    if evaluate(candidate, readback):
        failures.append("matching readback binding was rejected")
    candidate["events"][0]["args"]["model"] = "forged-observed-model"
    if "evidence_binding" not in evaluate(candidate, readback):
        failures.append("tool argument tampering bypassed readback binding")
    candidate["events"] = copy.deepcopy(readback["events"])
    candidate["evidence"]["readback_sha256"] = "forged-digest"
    if "evidence_binding" not in evaluate(candidate, readback):
        failures.append("forged readback digest was accepted")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--readbacks", type=Path, help="独立收集、按 case id 索引的工具记录 JSON；不是 fixture 自报")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        readbacks = json.loads(args.readbacks.read_text()) if args.readbacks else None
        if readbacks is not None and not isinstance(readbacks, dict):
            raise ValueError("readbacks must be indexed by case id")
        failures = self_test(args.path) if args.self_test else run(args.path, readbacks)
    except (OSError, TypeError, ValueError, KeyError, StopIteration) as exc:
        failures = [str(exc)]
    for failure in failures:
        print(f"error: {failure}")
    if not failures:
        print("Tasks Owner trajectory self-test passed." if args.self_test else "Tasks Owner trajectory validation passed.")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
