#!/usr/bin/env python3
"""Replay recorded PMO policy fixtures; this is not a scheduler or live-tool test.

Each cycle supplies source observations and simulated tool results. The replay
computes actions without reading expected prose, then compares the resulting
states. Missing observations, failed verification and uncertain creation remain
pending instead of silently becoming successful delivery.
"""

from __future__ import annotations

import argparse
import copy
import json
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "skills/pmo/evals/trajectory_cases.jsonl"
SCHEMA_VERSION = "pmo-trajectory.v2"
TERMINAL = {"completed", "cancelled", "superseded"}
EVENTS = {"unchanged", "progress", "merged", "completed", "cancelled", "superseded", "outcome_verified", "blocked", "ready"}
STATES = {"ready", "active", "waiting", "planning", "completed", "dispatch_pending"}


def locator(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value not in {"none", "missing", "unknown"}


def overlaps(left: list[str], right: list[str]) -> bool:
    return any(a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/") for a in left for b in right)


def holds_carrier(unit: dict[str, Any]) -> bool:
    return unit["status"] == "dispatch_pending" or (unit["status"] in {"active", "waiting"} and locator(unit.get("owner")))


def current_sources(units: dict[str, dict[str, Any]]) -> set[str]:
    return {unit["owner"] for unit in units.values() if unit["status"] in {"active", "waiting"} and locator(unit.get("owner"))} | {
        unit["waiting"]["source"] for unit in units.values() if unit["status"] == "waiting"
    }


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def waiting_valid(value: Any) -> bool:
    return isinstance(value, dict) and all(locator(value.get(key)) for key in ("source", "condition", "responsible_party", "evidence_locator", "wake_condition"))


def replay(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Project policy actions from ordered observations; never execute tools."""
    if facts.get("evidence_mode") != "recorded_fixture":
        raise ValueError("offline replay only accepts recorded_fixture; live claims require actual tool artifacts")
    cycles = facts.get("cycles")
    if not isinstance(cycles, list) or not cycles:
        raise ValueError("cycles must be a non-empty list")
    mandate = facts["mandate"]
    if not all(locator(mandate.get(key)) for key in ("scope_locator", "authority_locator", "repo_locator")):
        raise ValueError("mandate needs scope, authority and repository locators")
    outcomes = facts["outcomes"]
    if not isinstance(outcomes, list) or not outcomes or len(set(outcomes)) != len(outcomes) or not all(locator(item) for item in outcomes):
        raise ValueError("outcomes must identify the complete, unique product acceptance set")
    units = {unit["id"]: copy.deepcopy(unit) for unit in facts["units"]}
    if len(units) != len(facts["units"]) or len({unit["scope_locator"] for unit in units.values()}) != len(units):
        raise ValueError("duplicate unit or scope identity")
    for unit in units.values():
        if unit.get("status") not in STATES or not locator(unit.get("scope_locator")):
            raise ValueError("unit needs an explicit status and scope")
        if not isinstance(unit.get("carriers"), list) or not unit["carriers"] or not all(locator(item) for item in unit["carriers"]):
            raise ValueError("unit needs concrete write carriers")
        if not set(unit.get("outcomes", [])) <= set(outcomes) or not unit.get("outcomes"):
            raise ValueError("unit outcome must belong to the mandate")
        if any(dep not in units or dep == unit["id"] for dep in unit.get("depends_on", [])):
            raise ValueError("dependency must identify another unit")
        if unit["status"] == "active" and not all(locator(unit.get(key)) for key in ("owner", "recovery_locator")):
            raise ValueError("active unit needs an owner and a usable recovery locator")
        if unit["status"] == "waiting" and not waiting_valid(unit.get("waiting")):
            raise ValueError("waiting unit needs an external condition and recovery facts")
    revisions: dict[str, int] = {}
    seen_events: set[tuple] = set()
    pending_sources: set[str] = set()
    pending_poll_sources: set[str] = set()
    pending_evidence: set[str] = set()
    verified_outcomes: set[str] = set()
    result: list[dict[str, Any]] = []
    for cycle in cycles:
        actions: list[str] = []
        product_actions: list[str] = []

        def act(value: str, *, product: bool = False) -> None:
            if value not in actions:
                actions.append(value)
            if product:
                product_actions.append(value)

        trigger = cycle.get("trigger")
        if trigger not in {"heartbeat", "event", "wait"}:
            raise ValueError("cycle trigger must be heartbeat, event or wait")
        poll_sources = set(cycle.get("poll_sources", [])) | pending_poll_sources
        required_sources = poll_sources | pending_sources
        if trigger == "heartbeat":
            required_sources |= current_sources(units)
        observations = cycle.get("observations", [])
        read_sources: set[str] = set()
        for observation in observations:
            source, revision, kind = observation.get("source"), observation.get("revision"), observation.get("kind")
            if not locator(source) or not isinstance(revision, int) or isinstance(revision, bool) or revision < 0 or kind not in EVENTS:
                raise ValueError("observation needs a source revision and known event kind")
            if not locator(observation.get("evidence_locator")):
                raise ValueError("observation requires source evidence")
            unit_id = observation.get("unit")
            unit = units.get(unit_id)
            if unit_id is not None and unit is None:
                raise ValueError("observation refers to an unknown unit")
            if revision < revisions.get(source, -1):
                continue
            read_sources.add(source)
            outcome_keys = {f"product_outcome:{outcome}" for outcome in observation.get("outcomes", [])}
            event_key = (source, revision, kind, unit_id, tuple(sorted(outcome_keys)))
            product_pending = bool(outcome_keys & pending_evidence)
            if event_key in seen_events and unit_id not in pending_evidence and not product_pending:
                continue
            seen_events.add(event_key)
            revisions[source] = revision
            if kind == "outcome_verified":
                if source != mandate["repo_locator"]:
                    raise ValueError("product evidence must come from the mandated repository")
                claimed = set(observation.get("outcomes", []))
                if not claimed or not claimed <= set(outcomes):
                    raise ValueError("outcome evidence must match the product mandate")
                if observation.get("acceptance_verified") is not True:
                    pending_evidence.update(outcome_keys)
                    act("verify_product_outcome")
                    continue
                pending_evidence.difference_update(outcome_keys)
                verified_outcomes |= claimed
                act("accept_product_outcome", product=True)
                continue
            if kind in {"unchanged", "progress"}:
                continue
            if unit is None:
                raise ValueError("unit event requires a unit identity")
            allowed_sources = {unit.get("owner"), mandate["repo_locator"], unit.get("waiting", {}).get("source")}
            if source not in allowed_sources:
                raise ValueError("unit result must match its owner or authoritative source")
            if kind == "merged":
                act(f"route_affected_change:{unit_id}", product=True)
                continue
            if kind in TERMINAL:
                if unit["status"] == "completed":
                    continue
                if observation.get("writers_stopped") is not True or (kind == "completed" and observation.get("acceptance_verified") is not True):
                    pending_evidence.add(unit_id)
                    act(f"verify_result:{unit_id}")
                    continue
                pending_evidence.discard(unit_id)
                unit["owner"] = None
                unit["status"] = "completed" if kind == "completed" else "planning"
                act(f"complete_unit:{unit_id}" if kind == "completed" else f"replan_unit:{unit_id}", product=True)
            elif kind == "blocked":
                if not waiting_valid(observation.get("waiting")):
                    act(f"investigate_blocker:{unit_id}")
                else:
                    unit.update(status="waiting", waiting=observation["waiting"])
            elif kind == "ready":
                if unit["status"] not in {"planning", "waiting", "ready"}:
                    raise ValueError("readiness cannot restart an active or completed unit")
                unit.update(status="ready", ready=True)
        pending_poll_sources = poll_sources - read_sources
        pending_sources = ((required_sources - read_sources) & current_sources(units)) | pending_poll_sources
        for source in sorted(pending_sources):
            act(f"read_source:{source}")
        writers = [unit for unit in units.values() if holds_carrier(unit)]
        for index, left in enumerate(writers):
            for right in writers[index + 1:]:
                if overlaps(left["carriers"], right["carriers"]):
                    act(f"resolve_writer_conflict:{left['id']}:{right['id']}")
        try:
            TopologicalSorter({key: [dep for dep in unit.get("depends_on", []) if units[dep]["status"] != "completed"] for key, unit in units.items() if unit["status"] != "completed"}).prepare()
        except CycleError:
            act("resolve_unowned_or_cyclic_work")
        for unit in units.values():
            unit_id, status = unit["id"], unit["status"]
            if status == "dispatch_pending":
                recovered = cycle.get("recovered_owners", {}).get(unit_id)
                if locator(recovered):
                    unit.update(status="active", owner=recovered, recovery_locator=recovered)
                else:
                    act(f"locate_dispatch:{unit_id}")
                continue
            if status == "planning" or (status == "ready" and unit.get("ready") is not True):
                act(f"shape_unit:{unit_id}")
                continue
            if status != "ready" or any(units[dep]["status"] != "completed" for dep in unit.get("depends_on", [])):
                continue
            other_writers = [other for other in units.values() if other["id"] != unit_id and holds_carrier(other)]
            if any(overlaps(unit["carriers"], other["carriers"]) for other in other_writers):
                continue
            if mandate.get("allow_owner_creation") is not True:
                act(f"request_creation_authority:{unit_id}")
                continue
            if mandate.get("tasks_owner_contract_major") != 2:
                act(f"resolve_skill_dependency:{unit_id}")
                continue
            runtime = unit.get("runtime", {})
            if runtime.get("requested") and (runtime.get("observed") != runtime["requested"] or not locator(runtime.get("evidence_locator"))):
                act(f"resolve_requested_runtime:{unit_id}")
                continue
            act(f"delegate_unit:{unit_id}", product=True)
            dispatch = cycle.get("dispatch_results", {}).get(unit_id)
            if locator(dispatch):
                unit.update(status="active", owner=dispatch, recovery_locator=dispatch)
            else:
                unit.update(status="dispatch_pending", owner=None)
                act(f"locate_dispatch:{unit_id}")
        remaining = set(outcomes) - verified_outcomes
        carried = set().union(*(set(unit["outcomes"]) for unit in units.values() if unit["status"] != "completed"))
        for outcome in sorted(remaining - carried):
            act(f"verify_or_shape_outcome:{outcome}")
        unfinished = [unit for unit in units.values() if unit["status"] != "completed"]
        if not remaining and not unfinished and not pending_sources and not pending_evidence:
            status = "completed"
        elif product_actions:
            status = "progressed"
        elif actions or pending_evidence:
            status = "needs_action"
        else:
            # Ready units may wait only for a real active dependency or writer.
            waiting_units = {unit["id"] for unit in unfinished if unit["status"] in {"active", "waiting"}}
            changed = True
            while changed:
                changed = False
                for unit in unfinished:
                    if unit["id"] in waiting_units or unit["status"] != "ready":
                        continue
                    if any(dep in waiting_units for dep in unit.get("depends_on", [])) or any(
                        overlaps(unit["carriers"], other["carriers"]) for other in unfinished if holds_carrier(other)
                    ):
                        waiting_units.add(unit["id"])
                        changed = True
            status = "waiting" if unfinished and all(unit["id"] in waiting_units for unit in unfinished) else "needs_action"
            if status == "needs_action":
                act("resolve_unowned_or_cyclic_work")
        result.append({
            "actions": actions,
            "status": status,
            "unit_status": {key: unit["status"] for key, unit in units.items()},
            "pending_sources": sorted(pending_sources),
            "pending_evidence": sorted(pending_evidence),
            "remaining_outcomes": sorted(remaining),
        })
    return result


def validate_case(case: dict[str, Any]) -> list[str]:
    if set(case) != {"schema_version", "id", "facts", "expected"} or case.get("schema_version") != SCHEMA_VERSION or not locator(case.get("id")):
        return ["invalid case schema"]
    try:
        actual = replay(case["facts"])
    except (KeyError, TypeError, ValueError) as exc:
        return [str(exc)]
    return [] if actual == case["expected"] else [f"recorded actions/state differ from replay: {actual}"]


def validate_document(cases: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()
    for case in cases:
        case_id = case.get("id", "missing")
        if case_id in seen:
            failures.append(f"{case_id}: duplicate case id")
        seen.add(case_id)
        failures.extend(f"{case_id}: {error}" for error in validate_case(case))
    if not cases:
        failures.append("no trajectory cases")
    return failures


def self_test(path: Path) -> list[str]:
    cases = load_cases(path)
    failures = validate_document(cases)
    if failures:
        return failures
    by_id = {case["id"]: case for case in cases}

    def rejects(case_id: str, label: str, mutate) -> None:
        candidate = copy.deepcopy(by_id[case_id])
        mutate(candidate["facts"])
        if not validate_case(candidate):
            failures.append(f"negative mutation not rejected: {label}")

    rejects("missed-completion-starts-successor", "unverified acceptance cannot release successor", lambda f: f["cycles"][0]["observations"][0].update(acceptance_verified=False))
    rejects("missed-completion-starts-successor", "active writer cannot release successor", lambda f: f["cycles"][0]["observations"][0].update(writers_stopped=False))
    rejects("missed-completion-starts-successor", "new terminal cannot be treated as no change", lambda f: f["cycles"][0]["observations"][0].update(kind="unchanged"))
    rejects("multi-target-first-return", "first return does not cover other sources", lambda f: f["cycles"][0].update(observations=[]))
    rejects("independent-writes-start-together", "shared carrier cannot have two writers", lambda f: f["units"][1].update(carriers=f["units"][0]["carriers"]))
    rejects("ordinary-unit-needs-one-delegation", "creation requires authority", lambda f: f["mandate"].update(allow_owner_creation=False))
    rejects("ordinary-unit-needs-one-delegation", "incompatible skill cannot create owner", lambda f: f["mandate"].update(tasks_owner_contract_major=1))
    rejects("ordinary-unit-needs-one-delegation", "explicit runtime requirement must be respected", lambda f: f["units"][0].update(runtime={"requested":"user-model", "observed":"other-model", "evidence_locator":"tool:runtime"}))
    rejects("fifty-no-change-observations", "checkpoint alone cannot prove no change", lambda f: f["cycles"][20].update(observations=[]))
    rejects("all-product-evidence-completes", "child completion cannot replace parent evidence", lambda f: f["cycles"][0]["observations"].pop())
    rejects("uncertain-creation-is-not-repeated", "recovery must locate the existing owner", lambda f: f["cycles"][1].update(recovered_owners={}))
    rejects("waiting-with-real-owner", "active task requires recovery path", lambda f: f["units"][0].update(recovery_locator=None))
    rejects("waiting-for-external-condition", "external wait requires real condition", lambda f: f["units"][0]["waiting"].pop("condition"))
    rejects("missing-runtime-does-not-block-observation", "live mode cannot be self-certified", lambda f: f.update(evidence_mode="live_readback"))
    rejects("all-product-evidence-completes", "product evidence cannot cross repository", lambda f: f["cycles"][0]["observations"][-1].update(source="github:other/repo"))
    rejects("missed-completion-starts-successor", "unit evidence cannot use another owner", lambda f: f["cycles"][0]["observations"][0].update(source="thread:other"))
    rejects("same-source-revision-keeps-distinct-results", "distinct units cannot share a completion identity", lambda f: f["cycles"][0]["observations"][1].update(unit="a"))
    rejects("same-source-revision-keeps-distinct-results", "older source revision must not roll state back", lambda f: f["cycles"][2]["observations"][0].update(revision=6))
    rejects("same-source-revision-keeps-pending-outcomes", "distinct outcomes must retain separate evidence", lambda f: f["cycles"][0]["observations"][3].update(outcomes=["exit:a"]))
    rejects("terminal-clears-obsolete-wait-source", "only terminal evidence invalidates the old wait", lambda f: f["cycles"][0]["observations"][0].update(kind="progress"))
    rejects("shared-wait-source-remains-pending", "shared pending source must follow the remaining wait", lambda f: f["units"][1]["waiting"].update(source="external:other-runner"))
    rejects("explicit-poll-survives-unit-terminal", "explicit poll must retain its own pending requirement", lambda f: f["cycles"][0].pop("poll_sources"))
    rejects("explicit-poll-survives-unit-terminal", "explicit poll completes only after a source read", lambda f: f["cycles"][3].update(observations=[]))
    empty = copy.deepcopy(cases[0])
    empty["facts"]["cycles"] = []
    empty["expected"] = []
    if not any("non-empty" in error for error in validate_case(empty)):
        failures.append("empty replay must fail even when expected is empty")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        failures = self_test(args.path) if args.self_test else validate_document(load_cases(args.path))
    except (OSError, TypeError, ValueError, KeyError) as exc:
        failures = [str(exc)]
    for failure in failures:
        print(f"error: {failure}")
    if not failures:
        print("PMO recorded trajectory self-test passed." if args.self_test else "PMO recorded trajectory validation passed.")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
