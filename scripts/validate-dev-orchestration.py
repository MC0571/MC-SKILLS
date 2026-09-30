#!/usr/bin/env python3
"""校验 PMO 与 Tasks Owner 的共享合同和关键行为。"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from tasks_owner_trajectory_schema import (
    LOCATOR_SENTINELS,
    USER_DECISION_AUTHORITIES,
    USER_DECISION_FIELDS,
    user_decision_errors,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "skills/tasks-owner/references/dev-orchestration-contract.json"
PLATFORM = ROOT / "skills/tasks-owner/references/codex-app.md"
FEEDBACK_FORM = ROOT / ".github/ISSUE_TEMPLATE/skill-feedback.yml"
CYCLES = ROOT / "skills/pmo/evals/cycle_cases.jsonl"
INTEGRATION = ROOT / "skills/tasks-owner/evals/dev_orchestration_cases.jsonl"
OWNER_TRIGGERS = ROOT / "skills/tasks-owner/evals/trigger_cases.json"
PMO_TRIGGERS = ROOT / "skills/pmo/evals/trigger_cases.json"
CAPABILITIES = {
    "pmo_admission", "owner_sparse_delta", "single_scope_owner_execution",
    "scoped_finding_fix", "delivery_closeout", "bounded_execution_retrospective",
    "skill_feedback_candidate", "product_frontier_closure", "native_skill_feedback",
}
CAPABILITY_COMPATIBILITY_FIELDS = {
    "consumer_acceptance", "capability_locator", "selected_execution_surface",
    "next_actual_action_locator", "required_semantics", "observed_semantics",
    "existence_evidence", "probe_or_contract_check", "negative_or_unavailable_behavior",
    "status", "side_effect_attempted", "prior_equivalent_failure",
    "equivalent_failure_evidence", "probe_attempted",
}
ACTION_SCOPED_SEMANTICS = {
    "carrier_binding", "target_identity", "permission", "requested_runtime", "approval",
    "monitoring", "cancel", "readback",
}
PMO_ADMISSION_FIELDS = {
    "contract_id", "schema_version", "authority_origin", "scope_kind", "scope_locator",
    "planning_truth_locator", "product_goal", "expected_contribution", "acceptance_locator",
    "product_exit_locator", "governing_invariant_locator", "convergence_chain_locator",
    "ownership_boundary_locator", "allowed_scope", "excluded_scope", "carrier_locator",
    "target_head_locator", "decision_boundary_locator",
}
ACTION_ORDER = [
    "closeout_unit", "correct_drift", "recompute_product_frontier", "route_delta", "shape_work_item",
    "create_or_wake_owner", "request_user_decision", "record_evidenced_wait",
    "record_skill_feedback_candidate", "submit_or_update_skill_feedback",
]
FRONTIER_CLASSES = {
    "execution_ready", "admission_pending", "active_execution", "waiting_external",
    "waiting_user", "replan_or_reownership_pending", "closeout_pending",
}
OWNER_ACTIONABLE_CLASSES = {
    "execution_ready", "admission_pending", "replan_or_reownership_pending", "closeout_pending",
}
WAIT_CLASSES = {"active_execution", "waiting_external", "waiting_user"}
GAP_REQUIRED_FIELDS = {
    "gap_locator", "product_exit_locator", "classification", "owner_or_next_actor", "evidence_locator",
    "wake_condition", "invalidation_condition",
}
WAITING_PROOF_FIELDS = {
    "subject", "external_condition", "responsible_party", "evidence_locator",
    "observed_at", "freshness", "wake_condition", "invalidation_condition",
    "next_actor", "requires_user_judgment",
}
SPARSE_FORBIDDEN_KINDS = {
    "ack", "started", "execution_release", "proceed", "commit", "test_passed",
    "review_started", "review_fix", "ci", "pull_request", "branch", "head",
    "heartbeat", "thread_active",
}
RETROSPECTIVE_TRIGGERS = {
    "user_correction", "explicit_skill_correction", "repeated_failure", "post_repair_recurrence",
    "no_product_progress", "scope_dependency_ownership_drift", "source_of_truth_conflict",
    "repeated_platform_assumption_failure", "high_impact_incident",
}
RETROSPECTIVE_CANDIDATE_FIELDS = {
    "affected_skill", "trigger", "observed_behavior", "expected_behavior", "product_impact",
    "current_resolution", "generalizable_reason", "regression_proposal", "source_locator",
    "disclosure_status", "fingerprint_seed",
}
CORE_FEEDBACK_FIELDS = {
    "affected_skill", "retrospective_trigger", "observed_behavior", "expected_behavior",
    "product_impact", "current_resolution", "generalizable_root_cause", "proposed_regression",
    "redacted_evidence", "fingerprint_occurrence",
}
FINGERPRINT_FIELDS = {
    "affected_skill", "incident_root_cause_class", "governing_behavior_category", "platform_contract_major",
}
FEEDBACK_ACTIONS = {"search_issue", "read_issue", "create_issue", "add_comment"}
FEEDBACK_WRITE_ACTIONS = {"create_issue", "add_comment"}
FEEDBACK_SIDE_EFFECT_FIELDS = {
    "feedback_write_attempted", "feedback_write_succeeded", "feedback_write_action",
    "feedback_submission_locator", "feedback_readback_verified",
}
FEEDBACK_FORBIDDEN_ACTIONS = {
    "write_code", "create_branch", "create_pull_request", "merge_pull_request", "create_release",
    "close_issue", "delete_issue", "update_milestone", "update_labels", "update_assignees",
    "change_permissions", "install_skill", "update_skill", "reload_skill",
}
FEEDBACK_PRECONDITIONS = {
    "skill_identity_match", "canonical_repository_match", "github_feedback_capability_available",
    "dedupe_complete", "redaction_safe", "explicit_feedback_authority",
}
FEEDBACK_STATUSES = {"none", "candidate", "deduped", "submitted", "deferred_private"}
FEEDBACK_TARGETS = {"pmo", "tasks-owner", "platform", "none"}
SUBMISSION_FIELDS = {
    "feedback_write_action", "feedback_submission_locator", "feedback_readback_verified", "skill_digest_unchanged",
}
OCCURRENCE_FIELDS = {"source_locator", "product_impact", "current_resolution", "root_cause_delta", "regression_delta"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: 必须是对象")
        value["_line"] = number
        rows.append(value)
    return rows


def real_locator(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() not in LOCATOR_SENTINELS


def concrete_prefixed(value: Any, prefixes: list[str]) -> bool:
    return isinstance(value, str) and any(value.startswith(prefix) and real_locator(value[len(prefix):]) for prefix in prefixes)


def semver(value: Any) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", str(value))
    return tuple(map(int, match.groups())) if match else None


def version_is_compatible(actual: Any, compatibility: dict[str, Any]) -> bool:
    parsed = semver(actual)
    minimum = semver(compatibility.get("minimum_compatible_version"))
    return parsed is not None and minimum is not None and parsed >= minimum and compatibility.get("required_contract_schema_major") == 2


def feedback_fingerprint(facts: dict[str, Any], contract: dict[str, Any]) -> str:
    fields = contract["skill_feedback"]["fingerprint_fields"]
    return json.dumps([facts.get(field) for field in fields], ensure_ascii=False, separators=(",", ":"))


def feedback_api_body(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "affected_skill": candidate.get("affected_skill"),
        "retrospective_trigger": candidate.get("trigger"),
        "observed_behavior": candidate.get("observed_behavior"),
        "expected_behavior": candidate.get("expected_behavior"),
        "product_impact": candidate.get("product_impact"),
        "current_resolution": candidate.get("current_resolution"),
        "generalizable_root_cause": candidate.get("generalizable_reason"),
        "proposed_regression": candidate.get("regression_proposal"),
        "redacted_evidence": candidate.get("source_locator"),
        "fingerprint_occurrence": {
            "fingerprint": candidate.get("fingerprint_seed"),
            "occurrence": "first_occurrence",
        },
    }


def feedback_authorized(facts: dict[str, Any]) -> bool:
    """既有明确授权可复用；canonical 身份与工具访问都不生成授权。"""
    authority = facts.get("feedback_authority")
    action = facts.get("feedback_write_action") or (
        "add_comment" if facts.get("existing_feedback_issue") else "create_issue"
    )
    return (
        isinstance(authority, dict)
        and real_locator(authority.get("authority_locator"))
        and authority.get("repository") == "MC-and-his-Agents/MC-AGENT-KIT"
        and isinstance(authority.get("actions"), list)
        and all(real_locator(item) for item in authority["actions"])
        and action in FEEDBACK_WRITE_ACTIONS
        and action in authority["actions"]
    )


def feedback_side_effect_errors(facts: dict[str, Any]) -> list[str]:
    if not any(field in facts for field in FEEDBACK_SIDE_EFFECT_FIELDS):
        return []
    errors: list[str] = []
    if not feedback_authorized(facts):
        errors.append("反馈写入缺少覆盖目标与动作的明确授权")
    if facts.get("retrospective") not in RETROSPECTIVE_TRIGGERS:
        errors.append("反馈外部写入必须来自有效执行复盘")
    if facts.get("root_cause_target") not in {"skill", "platform"}:
        errors.append("项目或规划根因不能产生 Skill feedback 外部写入")
    if facts.get("current_delivery_action") or facts.get("product_actions_complete") is not True:
        errors.append("反馈外部写入必须后于当前产品恢复与纠偏")
    for field in (
        "skill_identity_match", "canonical_repository_match", "github_feedback_capability_available",
        "feedback_dedupe_complete", "feedback_redaction_safe",
    ):
        if facts.get(field) is not True:
            errors.append(f"反馈外部写入前置条件未满足：{field}")
    existing = facts.get("existing_feedback_issue")
    if not isinstance(existing, bool):
        errors.append("反馈外部写入必须携带显式 boolean dedupe 结果")
    action = facts.get("feedback_write_action")
    if action not in FEEDBACK_WRITE_ACTIONS:
        errors.append("反馈外部写入动作必须属于 write allowlist")
    elif isinstance(existing, bool) and action != ("add_comment" if existing else "create_issue"):
        errors.append("反馈外部写入动作与 dedupe 结果不一致")
    if facts.get("feedback_write_succeeded") is True:
        if facts.get("feedback_write_attempted") is not True:
            errors.append("反馈写入成功必须绑定真实尝试")
        if facts.get("skill_digest_unchanged") is not True:
            errors.append("反馈写入成功后当前 Skill digest 必须保持不变")
    if facts.get("feedback_readback_verified") is True and facts.get("feedback_write_succeeded") is not True:
        errors.append("反馈 readback 不能先于成功写入")
    if real_locator(facts.get("feedback_submission_locator")) and facts.get("feedback_write_succeeded") is not True:
        errors.append("反馈 submission locator 必须来自成功写入")
    return errors


def feedback_fact_errors(facts: dict[str, Any]) -> list[str]:
    side_effect_errors = feedback_side_effect_errors(facts)
    if not facts.get("retrospective"):
        return side_effect_errors
    root_cause = facts.get("root_cause_target")
    if root_cause not in {"project", "planning", "skill", "platform"}:
        return side_effect_errors + ["执行复盘 root_cause_target 无效"]
    if root_cause in {"project", "planning"}:
        return side_effect_errors
    if facts.get("current_delivery_action"):
        return side_effect_errors
    if facts.get("product_actions_complete") is not True:
        return side_effect_errors + ["Skill feedback 必须后于产品恢复与纠偏"]
    candidate = facts.get("feedback_candidate")
    if not isinstance(candidate, dict) or set(candidate) != RETROSPECTIVE_CANDIDATE_FIELDS:
        return side_effect_errors + ["Skill feedback candidate 字段不完整"]
    if any(not real_locator(candidate.get(field)) for field in RETROSPECTIVE_CANDIDATE_FIELDS - {"fingerprint_seed"}):
        return side_effect_errors + ["Skill feedback candidate 字段必须可回读"]
    fingerprint = candidate.get("fingerprint_seed")
    if not isinstance(fingerprint, dict) or set(fingerprint) != FINGERPRINT_FIELDS:
        return side_effect_errors + ["Skill feedback candidate fingerprint 必须只包含稳定字段"]
    affected_skill = candidate.get("affected_skill")
    if (
        fingerprint.get("affected_skill") != affected_skill
        or fingerprint.get("incident_root_cause_class") != root_cause
        or not real_locator(fingerprint.get("governing_behavior_category"))
        or fingerprint.get("platform_contract_major") != 2
    ):
        return side_effect_errors + ["Skill feedback candidate fingerprint 与复盘事实不一致"]
    if candidate.get("trigger") != facts.get("retrospective"):
        return side_effect_errors + ["Skill feedback candidate 的 trigger 或 affected_skill 无效"]
    if root_cause == "skill" and affected_skill not in {"pmo", "tasks-owner"}:
        return side_effect_errors + ["Skill 根因必须定位到 pmo 或 tasks-owner"]
    if root_cause == "platform" and affected_skill != "platform":
        return side_effect_errors + ["平台根因必须定位到 platform"]
    if facts.get("feedback_dedupe_complete") is True and not isinstance(facts.get("existing_feedback_issue"), bool):
        return side_effect_errors + ["Skill feedback dedupe 完成后必须显式记录是否已有 Issue"]
    if facts.get("feedback_write_action") == "create_issue":
        body = facts.get("feedback_api_body")
        if not isinstance(body, dict) or set(body) != CORE_FEEDBACK_FIELDS or body != feedback_api_body(candidate):
            return side_effect_errors + ["create_issue 必须显式投影完整且等价的 API body"]
    if facts.get("existing_feedback_issue") and facts.get("feedback_dedupe_complete") is True:
        occurrence = facts.get("feedback_occurrence")
        if not isinstance(occurrence, dict) or set(occurrence) != OCCURRENCE_FIELDS or any(
            not real_locator(occurrence.get(field)) for field in OCCURRENCE_FIELDS
        ):
            return side_effect_errors + ["同 fingerprint occurrence comment 字段不完整"]
    return side_effect_errors


def cycle_fact_errors(facts: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exits = facts.get("product_exit_locators")
    gaps = facts.get("gaps")
    if not isinstance(exits, list) or any(not real_locator(item) for item in exits) or len(exits) != len(set(exits)):
        errors.append("product_exit_locators 必须是无重复的真实 locator 列表")
    if facts.get("frontier_closure_status") not in {"complete", "incomplete"}:
        errors.append("frontier_closure_status 无效")
    if not isinstance(gaps, list):
        return errors + ["gaps 必须是列表"]
    locators: set[str] = set()
    linked_exits: set[str] = set()
    for gap in gaps:
        if not isinstance(gap, dict) or not GAP_REQUIRED_FIELDS <= set(gap):
            errors.append("gap 缺少机器合同字段")
            continue
        if any(not real_locator(gap.get(field)) for field in GAP_REQUIRED_FIELDS):
            errors.append("gap 字段必须可定位")
        locator = gap.get("gap_locator")
        if locator in locators:
            errors.append("gap_locator 重复")
        locators.add(locator)
        linked_exits.add(gap.get("product_exit_locator"))
        classification = gap.get("classification")
        if classification not in FRONTIER_CLASSES:
            errors.append("gap classification 无效")
        if classification == "waiting_external":
            proof = gap.get("waiting_proof")
            if not isinstance(proof, dict) or not WAITING_PROOF_FIELDS <= set(proof) or any(
                not real_locator(proof.get(field)) for field in WAITING_PROOF_FIELDS - {"requires_user_judgment"}
            ):
                errors.append("waiting_external 缺少完整且当前的 waiting proof")
            elif str(proof["freshness"]).strip().lower() in {"stale", "expired", "invalid"}:
                errors.append("waiting_external 使用了陈旧 waiting proof")
            else:
                actor = gap.get("owner_or_next_actor")
                responsible = proof.get("responsible_party")
                if proof.get("requires_user_judgment") is not False or proof.get("next_actor") != actor:
                    errors.append("waiting_external 的 actor 必须绑定无需用户判断的 waiting proof")
                elif actor != "user" and (
                    not concrete_prefixed(actor, ["external:"])
                    or actor != f"external:{responsible}"
                ):
                    errors.append("waiting_external 的责任方必须是 proof 对应的外部 actor")
        elif "waiting_proof" in gap:
            errors.append("只有 waiting_external 可以携带 waiting proof")
        if classification == "waiting_user":
            errors.extend(user_decision_errors(gap, facts.get("decision_boundary_locator")))
            if gap.get("owner_or_next_actor") != "user":
                errors.append("waiting_user 的 next actor 必须是 user")
    if facts.get("product_exit_complete") and (exits or gaps):
        errors.append("产品出口完成时不能仍有出口或差距")
    if facts.get("product_exit_complete") and facts.get("frontier_closure_status") != "complete":
        errors.append("产品出口完成必须绑定完整产品前沿闭包")
    if not facts.get("product_exit_complete") and not exits:
        errors.append("产品出口未完成时必须枚举出口")
    if facts.get("frontier_closure_status") == "complete" and not facts.get("product_exit_complete") and not gaps:
        errors.append("完整前沿必须枚举剩余差距")
    if (
        facts.get("frontier_closure_status") == "complete"
        and isinstance(exits, list)
        and linked_exits != set(exits)
    ):
        errors.append("完整前沿必须让每个产品出口至少关联一个已分类 gap，且不能引用未知出口")
    return errors


def derive_cycle(facts: dict[str, Any]) -> tuple[str, list[str]]:
    if cycle_fact_errors(facts):
        return "progressed", ["recompute_product_frontier"]
    actions: list[str] = []
    gaps = facts.get("gaps") if isinstance(facts.get("gaps"), list) else []
    classes = {gap.get("classification") for gap in gaps if isinstance(gap, dict)}
    if facts.get("merge_verified"):
        actions.append("closeout_unit")
    elif "closeout_pending" in classes:
        actions.append("closeout_unit")
    if facts.get("drift_detected"):
        actions.append("correct_drift")
    if facts.get("frontier_recomputed") is True or facts.get("frontier_closure_status") == "incomplete":
        actions.append("recompute_product_frontier")
    if facts.get("route_delta_ready"):
        actions.append("route_delta")
    if "replan_or_reownership_pending" in classes:
        actions.append("shape_work_item")
    if classes & {"execution_ready", "admission_pending"}:
        actions.append("create_or_wake_owner")
    if "waiting_user" in classes:
        actions.append("request_user_decision")
    if "waiting_external" in classes:
        actions.append("record_evidenced_wait")
    if facts.get("feedback_candidate"):
        actions.append("record_skill_feedback_candidate")
    if facts.get("feedback_submission_ready") and feedback_authorized(facts) and all(
        facts.get(key) is True
        for key in (
            "product_actions_complete", "skill_identity_match", "canonical_repository_match",
            "github_feedback_capability_available", "feedback_dedupe_complete", "feedback_redaction_safe",
        )
    ):
        actions.append("submit_or_update_skill_feedback")
    product = any(action in ACTION_ORDER[:6] for action in actions)
    blocked = bool(classes & {"waiting_user", "waiting_external", "active_execution"})
    if facts.get("product_exit_complete") and "recompute_product_frontier" not in actions:
        status = "completed"
    elif product and blocked:
        status = "partially_blocked"
    elif product:
        status = "progressed"
    elif facts.get("frontier_closure_status") == "complete" and classes <= WAIT_CLASSES:
        status = "waiting"
    else:
        status = "progressed"
    return status, actions


def derive_integration(facts: dict[str, Any]) -> str | None:
    if facts.get("systemic_invariant"):
        if mandate_errors(facts) or unit_identity_errors(facts):
            return None
        action = facts.get("requested_action")
        if action not in {"start_writer", "deliver"}:
            return None
        closure = facts.get("closure")
        if isinstance(closure, dict) and closure.get("governing_invariant_locator") != unit_identity_value(facts)["governing_invariant_locator"]:
            return None
        if action == "deliver":
            return "coverage_verified" if not closure_errors(closure, "deliver") else "hold_before_delivery"
        if capability_compatibility_errors(facts, require_compatible=False):
            return None
        ready = facts["capability_compatibility"]["status"] == "compatible"
        valid = ready and not closure_errors(closure)
        return "start_writer" if valid else "hold_before_writer"
    if facts.get("writer_admission_requested"):
        if facts.get("mandate_complete") and not mandate_errors(facts) and not unit_identity_errors(facts) and not capability_compatibility_errors(facts, require_compatible=False):
            status = facts["capability_compatibility"]["status"]
            return "admit_unit_writer" if status == "compatible" else "hold_before_writer"
        return None
    if facts.get("current_delivery_action") is True:
        return "continue_delivery"
    if facts.get("existing_unit"):
        return "new_unit" if facts.get("scope_change") else "same_unit"
    if facts.get("retrospective"):
        trigger = facts.get("retrospective")
        if trigger not in RETROSPECTIVE_TRIGGERS:
            return "continue_delivery"
        if facts.get("root_cause_target") in {"project", "planning"}:
            return "continue_delivery"
        if facts.get("root_cause_target") not in {"skill", "platform"}:
            return "continue_delivery"
        if facts.get("feedback_redaction_safe") is not True:
            return "deferred_private"
        if facts.get("skill_identity_match") is not True or facts.get("canonical_repository_match") is not True:
            return "deferred_private"
        requested_action = facts.get("feedback_requested_action")
        if requested_action is not None and requested_action not in FEEDBACK_ACTIONS:
            return "deferred_private"
        if facts.get("feedback_write_action") not in FEEDBACK_ACTIONS | {None}:
            return "deferred_private"
        if facts.get("feedback_dedupe_complete") is not True:
            return "candidate"
        if facts.get("github_feedback_capability_available") is not True:
            return "candidate"
        if not feedback_authorized(facts):
            return "candidate"
        if facts.get("existing_feedback_issue"):
            if not facts.get("feedback_write_succeeded"):
                return "comment_existing" if facts.get("github_feedback_capability_available") is True else "candidate"
        if facts.get("feedback_write_succeeded"):
            expected_action = "add_comment" if facts.get("existing_feedback_issue") else "create_issue"
            complete = (
                facts.get("feedback_write_action") == expected_action
                and real_locator(facts.get("feedback_submission_locator"))
                and facts.get("feedback_readback_verified") is True
                and facts.get("skill_digest_unchanged") is True
            )
            return "submitted" if complete else "candidate"
        if facts.get("feedback_write_attempted"):
            return "candidate"
        return "create_new_feedback_issue" if facts.get("github_feedback_capability_available") is True else "candidate"
    if facts.get("mandate_complete") and not mandate_errors(facts):
        return "activate_owner"
    return None


def skill_version(path: Path) -> str | None:
    match = re.search(r"^\s*version:\s*['\"]?([^'\"\s]+)", path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("contract_id") != "dev-orchestration" or contract.get("schema_version") != "2.0.0":
        errors.append("共享合同身份或版本错误")
    if contract.get("authority_source") != "tasks-owner":
        errors.append("共享合同权威来源错误")
    if set(contract.get("capabilities", [])) != CAPABILITIES:
        errors.append("共享合同能力集合不完整")
    if set(contract.get("owner_mandate", {}).get("required_fields", [])) != {
        "authority_origin", "scope_kind", "scope_locator", "global_tradeoff_authority"
    }:
        errors.append("Owner 委任字段不完整")
    cannot_reset = set(contract.get("unit_identity", {}).get("cannot_reset_by", []))
    if not {"file", "path", "pull_request", "branch", "head", "reviewer", "execution_generation", "owner"} <= cannot_reset:
        errors.append("Unit 身份仍可被实现载体错误重置")
    sparse = contract.get("owner_sparse_delta", {})
    if not SPARSE_FORBIDDEN_KINDS <= set(sparse.get("forbidden_kinds", [])):
        errors.append("稀疏增量仍允许日常工程噪声")
    if (
        sparse.get("normal_path_visible_events") != ["pmo_admission", "unit_completed"]
        or sparse.get("material_delta_event") != "owner_sparse_delta"
        or sparse.get("normal_path_human_messages") != 0
    ):
        errors.append("连续交付路径仍允许 PMO 控制面噪声")
    if set(contract.get("pmo_admission", {}).get("required_fields", [])) != PMO_ADMISSION_FIELDS:
        errors.append("PMO 准入字段不完整")
    unit_fields = set(contract.get("unit_identity", {}).get("required_fields", []))
    writer = contract.get("writer_admission", {})
    if set(writer.get("required_unit_identity_fields", [])) != unit_fields:
        errors.append("writer 准入没有复用唯一 Unit 身份")
    if (
        set(writer.get("capability_compatibility_required_fields", [])) != CAPABILITY_COMPATIBILITY_FIELDS
        or set(writer.get("action_scoped_semantics", [])) != ACTION_SCOPED_SEMANTICS
        or set(writer.get("execution_surfaces", [])) != {"local", "native_subagent", "app_task", "external"}
        or writer.get("surface_identity_prefix") != {
            "local": "thread:", "native_subagent": "native-subagent:",
            "app_task": "app-task:", "external": "external:",
        }
        or writer.get("surface_capability_locator_prefix") != {
            "local": ["tool:"], "native_subagent": ["host:native-"],
            "app_task": ["host:app-", "host:exact-task-"], "external": ["external:"],
        }
        or writer.get("surface_carrier_prefix") != {
            "local": ["git-common-dir:"], "native_subagent": ["git-common-dir:"],
            "app_task": ["git-common-dir:", "task:"], "external": ["external:"],
        }
        or writer.get("targeted_monitoring_prefix") != "targeted:"
        or set(writer.get("capability_status", [])) != {
            "compatible", "missing", "incompatible", "provided_by_current_batch", "not_applicable",
        }
        or set(writer.get("negative_behavior", [])) != {
            "replan_or_reownership_pending", "waiting_external", "not_applicable",
        }
        or writer.get("admitted_status") != "compatible"
        or writer.get("unchanged_evidence_action") != "hold_without_probe"
        or writer.get("default_execution_surface") != "local"
        or writer.get("delegation") != "single_complete_assignment"
    ):
        errors.append("writer action-scoped capability 合同不完整")
    verification = contract.get("verification_authority", {})
    if (
        set(verification.get("sources", [])) != {
            "user", "issue", "repository", "skill_default",
            "branch_protection", "security_contract", "release_contract",
        }
        or verification.get("resolution") != "union_of_applicable_requirements"
        or verification.get("source_fields") != ["locator", "required_checks"]
        or verification.get("override_fields") != ["source", "check", "authority_locator"]
        or verification.get("override_authority") != "explicit_user_source"
        or set(verification.get("non_waivable_sources", [])) != {"branch_protection", "security_contract"}
        or verification.get("readiness_layers") != ["product", "merge", "release"]
        or set(verification.get("hosted_required_when", [])) != {
            "effective_authority", "branch_protection", "release_contract", "security_contract",
        }
        or verification.get("evidence_reuse_key") != ["tree_digest", "acceptance_digest", "environment_class"]
        or set(verification.get("exact_head_freshness", [])) != {"independent_review", "required_checks", "pr_metadata"}
        or verification.get("unrelated_failure_action") != "backlog_without_product_rollback"
    ):
        errors.append("验证权威与 readiness 分层合同不完整")
    closure = contract.get("systemic_invariant_closure", {})
    if (
        not {"required_fields", "surface_required_fields", "surface_status", "closure_status", "required_ordering"} <= set(closure)
        or closure.get("required_ordering") != "predicate_before_first_observable_side_effect"
        or closure.get("admission_status") != ["planned", "verified"]
        or closure.get("delivery_status") != "verified"
    ):
        errors.append("系统性闭包机器 schema 不完整")
    for skill, compatibility in contract.get("compatible_skills", {}).items():
        if set(compatibility) != {"tested_artifact_version", "minimum_compatible_version", "required_contract_schema_major"}:
            errors.append(f"{skill} 的发布版本与兼容版本语义混淆")
            continue
        tested = semver(compatibility["tested_artifact_version"])
        minimum = semver(compatibility["minimum_compatible_version"])
        if tested is None or minimum is None or not version_is_compatible(compatibility["tested_artifact_version"], compatibility):
            errors.append(f"{skill} 的最低兼容版本无效")
        if compatibility["required_contract_schema_major"] != 2:
            errors.append(f"{skill} 的合同主版本不兼容")
    frontier = contract.get("product_frontier", {})
    if (
        set(frontier.get("required_fields", [])) != {"product_exit_locators", "gaps", "frontier_closure_status"}
        or
        set(frontier.get("classifications", [])) != FRONTIER_CLASSES
        or set(frontier.get("owner_actionable_classifications", [])) != OWNER_ACTIONABLE_CLASSES
        or set(frontier.get("gap_required_fields", [])) != GAP_REQUIRED_FIELDS
        or set(frontier.get("waiting_proof_required_fields", [])) != WAITING_PROOF_FIELDS
        or set(frontier.get("waiting_user_required_fields", [])) != USER_DECISION_FIELDS
        or set(frontier.get("user_reserved_authorities", [])) != USER_DECISION_AUTHORITIES
        or set(frontier.get("whole_cycle_wait_allowed_classifications", [])) != WAIT_CLASSES
        or set(frontier.get("closure_status", [])) != {"complete", "incomplete"}
        or frontier.get("completed_requires_complete_closure") is not True
        or frontier.get("recompute_forbids_completed") is not True
        or set(frontier.get("recompute_triggers", [])) != {
            "user_correction", "unit_merge_or_closeout", "dependency_resolution", "owner_terminal",
            "waiting_proof_invalidation", "stalled_progress_or_missing_exit", "deep_audit",
        }
    ):
        errors.append("产品前沿闭包合同不完整")
    retrospective = contract.get("execution_retrospective", {})
    if (
        set(retrospective.get("triggers", [])) != RETROSPECTIVE_TRIGGERS
        or set(retrospective.get("root_cause_targets", [])) != {"project", "planning", "skill", "platform"}
        or set(retrospective.get("candidate_required_fields", [])) != RETROSPECTIVE_CANDIDATE_FIELDS
        or retrospective.get("ordering") != [
            "current_product_recovery", "frontier_or_owner_correction", "retrospective",
            "root_cause_classification", "feedback_candidate",
        ]
        or retrospective.get("explicit_skill_correction_requires_repetition") is not False
        or retrospective.get("heartbeat_is_recovery_only") is not True
    ):
        errors.append("自主执行复盘合同不完整")
    feedback = contract.get("skill_feedback", {})
    required_feedback = {
        "canonical_repositories", "canonical_issue_form", "allowed_actions", "forbidden_actions",
        "write_actions", "requested_action_field", "side_effect_fact_fields",
        "side_effect_requires_submission_preconditions",
        "submission_preconditions", "core_semantic_fields", "fingerprint_fields", "fingerprint_forbidden_fields",
        "fingerprint_occurrence_required_fields", "new_issue_occurrence",
        "occurrence_comment_fields", "checkpoint_fields", "submission_required_fields", "authority_policy", "authority_fields",
        "failure_status",
        "api_body_must_be_explicit", "issue_is_only_long_term_retrospective_body",
        "does_not_change_product_semantic_revision", "does_not_change_current_skill_digest",
    }
    if not required_feedback <= set(feedback):
        errors.append("Skill 反馈合同不完整")
    elif set(feedback.get("allowed_actions", [])) != FEEDBACK_ACTIONS:
        errors.append("Skill 反馈动作 allowlist 错误")
    elif set(feedback.get("write_actions", [])) != FEEDBACK_WRITE_ACTIONS:
        errors.append("Skill 反馈写入动作集合错误")
    elif feedback.get("requested_action_field") != "feedback_requested_action":
        errors.append("Skill 反馈请求动作字段错误")
    elif set(feedback.get("side_effect_fact_fields", [])) != FEEDBACK_SIDE_EFFECT_FIELDS or feedback.get("side_effect_requires_submission_preconditions") is not True:
        errors.append("Skill 反馈副作用不变量错误")
    elif feedback.get("canonical_repositories") != {
        "pmo": "MC-and-his-Agents/MC-AGENT-KIT", "tasks-owner": "MC-and-his-Agents/MC-AGENT-KIT",
    }:
        errors.append("Skill 反馈 canonical repository 错误")
    elif set(feedback.get("forbidden_actions", [])) != FEEDBACK_FORBIDDEN_ACTIONS:
        errors.append("Skill 反馈 forbidden actions 不完整")
    elif set(feedback.get("submission_preconditions", [])) != FEEDBACK_PRECONDITIONS:
        errors.append("Skill 反馈提交前置条件不完整")
    elif set(feedback.get("core_semantic_fields", [])) != CORE_FEEDBACK_FIELDS:
        errors.append("Skill 反馈核心语义字段错误")
    elif set(feedback.get("fingerprint_fields", [])) != FINGERPRINT_FIELDS:
        errors.append("Skill 反馈稳定 fingerprint 字段错误")
    elif set(feedback.get("fingerprint_occurrence_required_fields", [])) != {"fingerprint", "occurrence"} or feedback.get("new_issue_occurrence") != "first_occurrence":
        errors.append("Skill 反馈首次 occurrence 合同错误")
    elif not {"branch", "pull_request", "head", "owner", "unit", "execution_generation", "heartbeat"} <= set(feedback.get("fingerprint_forbidden_fields", [])):
        errors.append("Skill 反馈 fingerprint 会受易变执行身份污染")
    elif set(feedback.get("occurrence_comment_fields", [])) != {"source_locator", "product_impact", "current_resolution", "root_cause_delta", "regression_delta"}:
        errors.append("Skill 反馈 occurrence 字段错误")
    elif set(feedback.get("checkpoint_fields", [])) != {"feedback_fingerprint", "feedback_issue_locator", "last_occurrence_locator", "feedback_status", "next_action"}:
        errors.append("Skill 反馈 checkpoint 复制了长期正文")
    elif set(feedback.get("feedback_status", [])) != FEEDBACK_STATUSES or set(feedback.get("feedback_target", [])) != FEEDBACK_TARGETS:
        errors.append("Skill 反馈状态或目标枚举不完整")
    elif set(feedback.get("submission_required_fields", [])) != SUBMISSION_FIELDS:
        errors.append("Skill 反馈 submitted readback 门不完整")
    elif feedback.get("failure_status") != {
        "candidate": ["dedupe_incomplete", "tool_unavailable", "write_failed", "readback_unavailable", "authority_missing"],
        "deferred_private": ["redaction_unsafe", "canonical_repository_mismatch", "skill_identity_mismatch", "action_not_allowed"],
    }:
        errors.append("Skill 反馈失败状态未 fail closed 或误把暂时失败归为隐私延期")
    elif (
        feedback.get("authority_policy") != "reuse_explicit_authority_within_scope; otherwise_candidate"
        or feedback.get("authority_fields") != ["authority_locator", "repository", "actions"]
    ):
        errors.append("反馈授权必须绑定已有目标/动作范围，无授权时保留候选")
    elif not all(feedback.get(field) is True for field in (
        "api_body_must_be_explicit", "issue_is_only_long_term_retrospective_body",
        "does_not_change_product_semantic_revision", "does_not_change_current_skill_digest",
    )):
        errors.append("Skill 反馈错误地改变产品或运行版本")
    return errors


def feedback_form_errors(contract: dict[str, Any], text: str) -> list[str]:
    feedback = contract["skill_feedback"]
    body = re.search(r"(?m)^body:\s*$", text)
    if not body:
        return ["Skill feedback Form 缺少 body"]
    body_text = text[body.end():]
    if re.search(r"(?m)^[a-zA-Z_][a-zA-Z0-9_-]*:\s*", body_text):
        return ["Skill feedback Form 控件逃逸到 body 之外"]
    blocks = re.split(r"(?m)(?=^  - type:)", body_text)
    controls: dict[str, str] = {}
    for block in blocks:
        kind = re.search(r"(?m)^  - type:\s*([a-z0-9_-]+)\s*$", block)
        if not kind or kind.group(1) == "markdown":
            continue
        identifier = re.search(r"(?m)^ {4}id:\s*([a-z0-9_-]+)\s*$", block)
        if not identifier or identifier.group(1) in controls:
            return ["Skill feedback Form 控件缺少唯一直接 id"]
        controls[identifier.group(1)] = block
    form_ids = list(controls)
    if len(form_ids) != len(set(form_ids)):
        return ["Skill feedback Form 存在重复字段"]
    if set(form_ids) != set(feedback["core_semantic_fields"]):
        return ["Skill feedback Form 与机器 schema 的核心语义字段漂移"]
    if any(not re.search(r"(?m)^ {4}validations:\s*\n {6}required:\s*true\s*$", block) for block in controls.values()):
        return ["Skill feedback Form 的核心语义字段必须全部必填"]
    trigger_options = set(re.findall(r"(?m)^ {8}-\s*(.+?)\s*$", controls.get("retrospective_trigger", "")))
    if trigger_options != set(contract["execution_retrospective"]["triggers"]):
        return ["Skill feedback Form 的 retrospective trigger 投影不完整"]
    affected_options = set(re.findall(r"(?m)^ {8}-\s*(.+?)\s*$", controls.get("affected_skill", "")))
    if affected_options != {"pmo", "tasks-owner", "platform / host"}:
        return ["Skill feedback Form 的 affected skill 投影不完整"]
    if feedback["canonical_issue_form"] != str(FEEDBACK_FORM.relative_to(ROOT)):
        return ["Skill feedback Form locator 与机器合同不一致"]
    if "dev-orchestration-contract.json" not in text:
        return ["Skill feedback Form 未声明机器 schema 权威"]
    return []


def validate_files(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for skill in ("pmo", "tasks-owner"):
        skill_dir = ROOT / f"skills/{skill}"
        manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
        expected = contract["compatible_skills"][skill]["tested_artifact_version"]
        if manifest.get("version") != expected or skill_version(skill_dir / "SKILL.md") != expected:
            errors.append(f"{skill} 的入口、manifest 与本次发布候选版本不一致")
    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
        "skills/pmo/SKILL.md", "skills/tasks-owner/SKILL.md",
        "skills/tasks-owner/references/governance.md",
    ))
    for locator in ("dev-orchestration-contract.json", "codex-app.md"):
        if locator not in combined:
            errors.append(f"入口无法发现 {locator}")
    if len(list((ROOT / "skills").glob("*/references/dev-orchestration-contract.json"))) != 1:
        errors.append("跨 Skill 合同必须只有一个权威文件")
    if len(list((ROOT / "skills").glob("*/references/codex-app.md"))) != 1:
        errors.append("Codex App 平台事实必须只有一个权威文件")
    forbidden = re.compile(r"gpt-5\.6|codex_app__|wait_agent|10_000|60_000|24 小时|\d+\s*分钟")
    for skill in ("pmo", "tasks-owner"):
        for path in (ROOT / f"skills/{skill}").rglob("*.md"):
            if path == PLATFORM or any(part in {"evals", "reports"} for part in path.parts):
                continue
            if forbidden.search(path.read_text(encoding="utf-8")):
                errors.append(f"平台参数必须只出现在 codex-app.md：{path.relative_to(ROOT)}")
    return errors


def closure_errors(closure: Any, stage: str = "start") -> list[str]:
    if not isinstance(closure, dict):
        return ["系统性闭包必须是对象"]
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))["systemic_invariant_closure"]
    required = set(schema["required_fields"])
    if not required <= set(closure):
        return ["系统性闭包缺少范围、顺序、失败规则、适用面或摘要"]
    if any(not real_locator(closure.get(key)) for key in required - {"surfaces"}):
        return ["系统性闭包的说明或摘要不能为空"]
    statuses = [schema["delivery_status"]] if stage == "deliver" else schema["admission_status"]
    if closure.get("status") not in statuses:
        return ["开始需要覆盖计划，交付需要已验证结果"]
    if closure.get("ordering") != schema["required_ordering"]:
        return ["系统性闭包必须证明 predicate 早于首次可观察副作用"]
    surfaces = closure.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        return ["系统性闭包没有适用面"]
    surface_fields = set(schema["surface_required_fields"])
    for surface in surfaces:
        if not isinstance(surface, dict) or not surface_fields <= set(surface):
            return ["系统性闭包的适用面证据不完整"]
        if surface.get("status") not in schema["surface_status"]:
            return ["系统性闭包的适用面状态无效"]
        if closure.get("status") == "verified" and surface.get("status") == "planned":
            return ["未执行的验证计划不能证明交付"]
        for field in surface_fields:
            if not real_locator(surface.get(field)):
                return ["系统性闭包的适用面证据不完整"]
    return []


def mandate_errors(facts: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if facts.get("authority_origin") not in {"user", "pmo"}:
        errors.append("Owner 授权来源无效")
    if facts.get("scope_kind") not in {"project_scope", "work_item"}:
        errors.append("Owner 范围类型无效")
    if not real_locator(facts.get("scope_locator")):
        errors.append("Owner 缺少范围定位")
    if facts.get("authority_origin") == "user" and (
        facts.get("global_tradeoff_authority") != "none" and not real_locator(facts.get("global_tradeoff_authority"))
    ):
        errors.append("Owner 缺少全局取舍授权边界")
    if facts.get("authority_origin") == "pmo" and facts.get("global_tradeoff_authority") != "none":
        errors.append("PMO 不得继承用户全局取舍授权")
    if facts.get("authority_origin") == "pmo":
        admission = facts.get("pmo_admission")
        if not isinstance(admission, dict) or not PMO_ADMISSION_FIELDS <= set(admission):
            errors.append("PMO 准入 envelope 不完整")
        else:
            if admission.get("contract_id") != "dev-orchestration" or admission.get("schema_version") != "2.0.0":
                errors.append("PMO 准入 envelope 使用了不兼容的共享合同")
            for field in PMO_ADMISSION_FIELDS:
                value = admission.get(field)
                if field in {"allowed_scope", "excluded_scope"}:
                    if not isinstance(value, list) or not value or any(not real_locator(item) for item in value):
                        errors.append(f"PMO 准入 {field} 不能为空")
                elif not real_locator(value):
                    errors.append(f"PMO 准入 {field} 不能为空")
    return errors


def continuous_lane_errors(facts: dict[str, Any]) -> list[str]:
    if "current_delivery_action" in facts and not isinstance(facts.get("current_delivery_action"), bool):
        return ["current_delivery_action 必须是 boolean"]
    if facts.get("current_delivery_action") is not True and "pmo_visible_events" not in facts:
        return []
    required = {"pmo_visible_events", "owner_internal_events", "owner_sparse_deltas", "pmo_human_message_count"}
    if not required <= set(facts):
        return ["当前普通交付动作缺少完整 continuous lane 事实"]
    visible = facts.get("pmo_visible_events")
    internal = facts.get("owner_internal_events")
    deltas = facts.get("owner_sparse_deltas")
    errors: list[str] = []
    if not isinstance(visible, list) or not visible or visible[0] != "pmo_admission" or any(
        event not in {"pmo_admission", "owner_sparse_delta", "unit_completed"}
        for event in visible
    ) or "pmo_admission" in visible[1:] or ("unit_completed" in visible and visible[-1] != "unit_completed"):
        errors.append("普通 Unit 的 PMO 可见路径必须只有准入、可选 material delta 与 terminal")
    elif any(event != "owner_sparse_delta" for event in visible[1:-1]):
        errors.append("普通工程事件不得升级为 PMO gate")
    if not isinstance(internal, list) or not internal or any(not real_locator(event) for event in internal):
        errors.append("连续交付 proceed-control 必须保留 Owner 私有工程轨迹")
    sparse = json.loads(CONTRACT.read_text(encoding="utf-8"))["owner_sparse_delta"]
    if not isinstance(deltas, list) or len(deltas) != (visible.count("owner_sparse_delta") if isinstance(visible, list) else -1):
        errors.append("每个 PMO-visible sparse delta 必须绑定一个机器事实")
    elif any(
        not isinstance(delta, dict)
        or not set(sparse["required_fields"]) <= set(delta)
        or delta.get("kind") not in sparse["allowed_kinds"]
        or delta.get("kind") in sparse["forbidden_kinds"]
        or any(not real_locator(delta.get(field)) for field in sparse["required_fields"])
        for delta in deltas
    ):
        errors.append("PMO-visible sparse delta 缺少 material 事实或 evidence locator")
    if facts.get("pmo_human_message_count") != 0:
        errors.append("普通 Unit 内部工程进展不得产生 PMO 人类消息")
    return errors


def unit_identity_value(facts: dict[str, Any]) -> Any:
    if facts.get("authority_origin") == "pmo" and isinstance(facts.get("pmo_admission"), dict):
        return facts["pmo_admission"]
    return facts.get("unit_identity")


def unit_identity_errors(facts: dict[str, Any]) -> list[str]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    fields = set(contract["writer_admission"]["required_unit_identity_fields"])
    identity = unit_identity_value(facts)
    if not isinstance(identity, dict):
        return ["writer 准入缺少 Unit 身份"]
    return [f"writer 准入缺少 {field}" for field in fields if not real_locator(identity.get(field))]


def capability_compatibility_errors(facts: dict[str, Any], require_compatible: bool = True) -> list[str]:
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))["writer_admission"]
    capability = facts.get("capability_compatibility")
    if not isinstance(capability, dict) or not CAPABILITY_COMPATIBILITY_FIELDS <= set(capability):
        return ["writer 准入缺少 action-scoped capability compatibility"]
    errors: list[str] = []
    for field in (
        "consumer_acceptance", "capability_locator", "next_actual_action_locator",
        "existence_evidence", "probe_or_contract_check",
    ):
        if not real_locator(capability.get(field)):
            errors.append(f"capability compatibility 缺少 {field}")
    surface = capability.get("selected_execution_surface")
    if surface not in schema["execution_surfaces"]:
        errors.append("capability compatibility 的执行 surface 无效")
    required = capability.get("required_semantics")
    observed = capability.get("observed_semantics")
    if (
        not isinstance(required, dict) or not {"carrier_binding", "target_identity"} <= set(required)
        or not set(required) <= ACTION_SCOPED_SEMANTICS
        or any(not real_locator(value) for value in required.values())
    ):
        errors.append("capability compatibility 的下一动作语义无效")
    if (
        not isinstance(observed, dict)
        or not set(observed) <= ACTION_SCOPED_SEMANTICS
        or any(not real_locator(value) for value in observed.values())
    ):
        errors.append("capability compatibility 的已观察语义无效")
    if isinstance(required, dict) and surface in schema["execution_surfaces"]:
        identity = required.get("target_identity")
        carrier = required.get("carrier_binding")
        locator = capability.get("capability_locator")
        if not concrete_prefixed(identity, [schema["surface_identity_prefix"][surface]]):
            errors.append("selected execution surface 与 target identity 不一致")
        if not concrete_prefixed(carrier, schema["surface_carrier_prefix"][surface]):
            errors.append("selected execution surface 与 cwd/carrier 不一致")
        if not concrete_prefixed(locator, schema["surface_capability_locator_prefix"][surface]):
            errors.append("selected execution surface 与 capability contract identity 不一致")
        if "monitoring" in required and (
            not concrete_prefixed(required["monitoring"], [schema["targeted_monitoring_prefix"]])
        ):
            errors.append("delegated monitoring 必须绑定 exact target")
    status = capability.get("status")
    if status not in schema["capability_status"]:
        errors.append("capability compatibility 状态无效")
    elif isinstance(required, dict) and isinstance(observed, dict):
        compatible = all(observed.get(key) == value for key, value in required.items())
        if (status == "compatible") != compatible:
            errors.append("capability compatibility 状态与 required/observed semantics 矛盾")
    if capability.get("negative_or_unavailable_behavior") not in schema["negative_behavior"]:
        errors.append("capability compatibility 缺少既有恢复状态")
    if capability.get("side_effect_attempted") is not False:
        errors.append("capability compatibility 必须在创建或相关副作用前完成")
    prior_failure = capability.get("prior_equivalent_failure")
    probe_attempted = capability.get("probe_attempted")
    expected_prior_evidence = f"{capability.get('probe_or_contract_check')}@same-schema-environment-authority"
    if not isinstance(prior_failure, bool) or not isinstance(probe_attempted, bool):
        errors.append("capability compatibility 缺少等价失败去重事实")
    elif prior_failure and (
        status == "compatible"
        or capability.get("equivalent_failure_evidence") != expected_prior_evidence
        or probe_attempted
    ):
        errors.append("相同 route/environment/authority 的失败不得重复 probe")
    elif not prior_failure and capability.get("equivalent_failure_evidence") != "not_applicable":
        errors.append("首次 capability 检查不得伪造等价失败证据")
    if require_compatible and status != schema["admitted_status"]:
        errors.append("下一实际动作所需 capability 尚未 compatible")
    return errors


def writer_admission_errors(facts: dict[str, Any]) -> list[str]:
    return unit_identity_errors(facts) + capability_compatibility_errors(facts)


def validate_cycles(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    for row in rows:
        line = row.pop("_line", "?")
        if set(row) != {"schema_version", "id", "facts", "expected"} or row.get("schema_version") != "pmo-cycle.v1":
            errors.append(f"cycle line {line}: 结构错误")
            continue
        if row["id"] in ids:
            errors.append(f"cycle line {line}: ID 重复")
        ids.add(row["id"])
        errors.extend(f"cycle line {line}: {error}" for error in cycle_fact_errors(row["facts"]))
        derived = derive_cycle(row["facts"])
        expected = row["expected"]
        if derived != (expected.get("cycle_status"), expected.get("actions")):
            errors.append(f"cycle line {line}: 期望与事实不一致")
        actions = expected.get("actions", [])
        if actions != sorted(actions, key=ACTION_ORDER.index):
            errors.append(f"cycle line {line}: 产品动作和治理动作顺序错误")
    if {row.get("expected", {}).get("cycle_status") for row in rows} != {"progressed", "partially_blocked", "waiting", "completed"}:
        errors.append("PMO 周期状态覆盖不完整")
    return errors


def validate_integration(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    outcomes: set[str] = set()
    for row in rows:
        line = row.pop("_line", "?")
        if set(row) != {"schema_version", "id", "facts", "expected"} or row.get("schema_version") != "dev-orchestration-case.v1":
            errors.append(f"integration line {line}: 结构错误")
            continue
        if row["id"] in ids:
            errors.append(f"integration line {line}: ID 重复")
        ids.add(row["id"])
        outcomes.add(row["expected"])
        errors.extend(f"integration line {line}: {error}" for error in feedback_fact_errors(row["facts"]))
        errors.extend(f"integration line {line}: {error}" for error in continuous_lane_errors(row["facts"]))
        if derive_integration(row["facts"]) != row["expected"]:
            errors.append(f"integration line {line}: 期望与事实不一致")
        if row["expected"] in {"activate_owner", "admit_unit_writer"}:
            errors.extend(f"integration line {line}: {error}" for error in mandate_errors(row["facts"]))
        if row["expected"] == "admit_unit_writer":
            errors.extend(f"integration line {line}: {error}" for error in writer_admission_errors(row["facts"]))
        if row["facts"].get("systemic_invariant") and row["expected"] in {"start_writer", "coverage_verified"}:
            stage = "deliver" if row["expected"] == "coverage_verified" else "start"
            errors.extend(f"integration line {line}: {error}" for error in closure_errors(row["facts"].get("closure"), stage))
    required = {
        "activate_owner", "admit_unit_writer", "same_unit", "new_unit", "hold_before_writer",
        "start_writer", "deferred_private", "candidate", "comment_existing",
        "create_new_feedback_issue", "submitted", "continue_delivery",
    }
    if not required <= outcomes:
        errors.append("跨 Skill 场景覆盖不完整")
    return errors


def validate_triggers() -> list[str]:
    errors: list[str] = []
    owner = json.loads(OWNER_TRIGGERS.read_text(encoding="utf-8"))
    pmo = json.loads(PMO_TRIGGERS.read_text(encoding="utf-8"))
    for name, document in (("tasks-owner", owner), ("pmo", pmo)):
        groups = [document.get(key, []) for key in ("should_trigger", "should_not_trigger", "near_neighbor")]
        if any(not isinstance(group, list) or not group for group in groups):
            errors.append(f"{name} 触发评测三类样本不完整")
            continue
        texts = [case.get("text") for group in groups for case in group]
        if any(not isinstance(text, str) or not text.strip() for text in texts) or len(texts) != len(set(texts)):
            errors.append(f"{name} 触发样本存在空值或重复")
    if "pmo_admission" not in {case.get("family") for case in owner.get("should_trigger", [])}:
        errors.append("Tasks Owner 缺少 PMO 准入触发样本")
    pmo_negative = {case.get("family") for case in pmo.get("should_not_trigger", [])}
    if not {"single_unit_owner", "one_off_implementation", "skill_maintenance"} <= pmo_negative:
        errors.append("PMO 对邻近任务的拒绝样本不完整")
    return errors


def run_existing(self_test: bool) -> list[str]:
    errors: list[str] = []
    suffix = ["--self-test"] if self_test else []
    for name in ("validate-pmo-trajectories.py", "validate-tasks-owner-trajectories.py"):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / name), *suffix], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            errors.append(result.stdout.strip())
    return errors


def validate() -> list[str]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return (
        validate_contract(contract) + validate_files(contract)
        + feedback_form_errors(contract, FEEDBACK_FORM.read_text(encoding="utf-8"))
        + validate_cycles(load_jsonl(CYCLES)) + validate_integration(load_jsonl(INTEGRATION))
        + validate_triggers()
        + run_existing(False)
    )


def self_test() -> list[str]:
    failures: list[str] = []
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    bad = copy.deepcopy(contract)
    bad["capabilities"].remove("owner_sparse_delta")
    if not validate_contract(bad):
        failures.append("缺失共享能力的变异未被拒绝")
    for label, mutate in (
        ("准入字段", lambda value: value["pmo_admission"].update(required_fields=[])),
        ("反馈合同", lambda value: value.update(skill_feedback={})),
        ("复盘 trigger", lambda value: value["execution_retrospective"]["triggers"].remove("explicit_skill_correction")),
        ("完成态闭包", lambda value: value["product_frontier"].update(completed_requires_complete_closure=False)),
        ("用户决策边界", lambda value: value["product_frontier"]["waiting_user_required_fields"].remove("decision_boundary_locator")),
        ("连续交付路径", lambda value: value["owner_sparse_delta"]["normal_path_visible_events"].insert(1, "started")),
        ("验证来源合并", lambda value: value["verification_authority"].update(resolution="first_source_wins")),
        ("Hosted 条件门禁", lambda value: value["verification_authority"]["hosted_required_when"].remove("effective_authority")),
        ("验证证据复用键", lambda value: value["verification_authority"]["evidence_reuse_key"].remove("environment_class")),
        ("action-scoped capability", lambda value: value["writer_admission"]["action_scoped_semantics"].remove("cancel")),
        ("execution surface identity", lambda value: value["writer_admission"]["surface_identity_prefix"].update(local="app-task:")),
        ("capability 不变证据策略", lambda value: value["writer_admission"].update(unchanged_evidence_action="retry_probe")),
        ("高风险副作用顺序", lambda value: value["systemic_invariant_closure"].update(required_ordering="first_observable_side_effect_before_predicate")),
        ("根因分类", lambda value: value["execution_retrospective"]["root_cause_targets"].remove("platform")),
        ("反馈 allowlist", lambda value: value["skill_feedback"]["allowed_actions"].append("create_pull_request")),
        ("反馈写入动作", lambda value: value["skill_feedback"]["write_actions"].append("read_issue")),
        ("反馈请求动作字段", lambda value: value["skill_feedback"].update(requested_action_field="feedback_write_action")),
        ("反馈副作用字段", lambda value: value["skill_feedback"]["side_effect_fact_fields"].remove("feedback_submission_locator")),
        ("反馈授权", lambda value: value["skill_feedback"]["submission_preconditions"].remove("explicit_feedback_authority")),
        ("canonical Skill 映射", lambda value: value["skill_feedback"]["canonical_repositories"].pop("pmo")),
        ("反馈状态", lambda value: value["skill_feedback"]["feedback_status"].remove("candidate")),
        ("fingerprint 字段", lambda value: value["skill_feedback"]["fingerprint_fields"].append("head")),
        ("首次 occurrence", lambda value: value["skill_feedback"].update(new_issue_occurrence="unknown")),
        ("反馈失败状态", lambda value: value["skill_feedback"]["failure_status"]["candidate"].remove("write_failed")),
        ("权威来源", lambda value: value.update(authority_source="pmo")),
        ("最低兼容版本", lambda value: value["compatible_skills"]["pmo"].update(minimum_compatible_version="0.14.0")),
    ):
        bad_contract = copy.deepcopy(contract)
        mutate(bad_contract)
        if not validate_contract(bad_contract):
            failures.append(f"破坏{label}的变异未被拒绝")
    pmo_compatibility = contract["compatible_skills"]["pmo"]
    if not version_is_compatible("0.12.1", pmo_compatibility):
        failures.append("高于最低版本的兼容补丁版本被错误拒绝")
    if version_is_compatible("0.11.9", pmo_compatibility):
        failures.append("低于最低版本的 Skill 被错误接受")
    cycles = load_jsonl(CYCLES)
    bad_cycles = copy.deepcopy(cycles)
    next(row for row in bad_cycles if row["id"] == "merge-drift-and-successor")["expected"]["actions"].reverse()
    if not validate_cycles(bad_cycles):
        failures.append("动作乱序变异未被拒绝")
    for label, mutate in (
        ("等待证明缺字段", lambda facts: facts["gaps"][0]["waiting_proof"].pop("external_condition")),
        ("等待证明缺 actor", lambda facts: facts["gaps"][0]["waiting_proof"].pop("next_actor")),
        ("等待证明伪装用户判断", lambda facts: facts["gaps"][0]["waiting_proof"].update(requires_user_judgment=True)),
        ("等待证明 actor 冲突", lambda facts: facts["gaps"][0].update(owner_or_next_actor="user")),
        ("外部责任方冲突", lambda facts: facts["gaps"][0]["waiting_proof"].update(responsible_party="other-provider")),
        ("陈旧等待证明", lambda facts: facts["gaps"][0]["waiting_proof"].update(freshness="stale")),
        ("前沿闭包不完整", lambda facts: facts.update(frontier_closure_status="incomplete")),
        ("重复差距", lambda facts: facts["gaps"].append(copy.deepcopy(facts["gaps"][0]))),
        ("等待伪装为无 Owner", lambda facts: facts["gaps"][0].update(waiting_proof=None)),
    ):
        bad_wait = copy.deepcopy(cycles)
        wait_case = next(row for row in bad_wait if row["id"] == "all-gaps-have-wait-proof")
        mutate(wait_case["facts"])
        if not validate_cycles(bad_wait):
            failures.append(f"{label}变异未被拒绝")
    for label, mutate in (
        ("缺少 authority locator", lambda gap: gap.pop("decision_boundary_locator")),
        ("职责内事项升级", lambda gap: gap.update(decision_authority="owner_actionable")),
        ("未完成有界调查", lambda gap: gap.update(existing_truth_exhausted=False)),
        ("调查状态失败", lambda gap: gap.update(bounded_investigation_status="failed")),
        ("存在安全可逆默认", lambda gap: gap.update(safe_reversible_default_available=True)),
        ("默认方案 locator 存在", lambda gap: gap.update(safe_reversible_default_locator="default:available")),
        ("机械动作伪装决策", lambda gap: gap.update(requires_user_judgment=False)),
        ("冻结无关前沿", lambda gap: gap.update(unaffected_work_continues=False)),
        ("责任方不是用户", lambda gap: gap.update(owner_or_next_actor="owner")),
        ("附加第二套等待证明", lambda gap: gap.update(waiting_proof={})),
    ):
        bad_decision = copy.deepcopy(cycles)
        decision = next(row for row in bad_decision if row["id"] == "user-decision-is-not-duplicated-wait")
        mutate(decision["facts"]["gaps"][0])
        if not validate_cycles(bad_decision):
            failures.append(f"waiting_user {label}变异未被拒绝")
    for field in ("decision_boundary_locator", "bounded_investigation_locator", "exact_decision_question", "blocked_action", "blocking_scope"):
        bad_decision = copy.deepcopy(cycles)
        decision = next(row for row in bad_decision if row["id"] == "user-decision-is-not-duplicated-wait")
        decision["facts"]["gaps"][0][field] = "none"
        if not validate_cycles(bad_decision):
            failures.append(f"waiting_user {field} sentinel 变异未被拒绝")
    bad_decision = copy.deepcopy(cycles)
    decision = next(row for row in bad_decision if row["id"] == "user-decision-is-not-duplicated-wait")
    decision["facts"]["decision_boundary_locator"] = "issue:other#authority"
    if not validate_cycles(bad_decision):
        failures.append("waiting_user admission authority mismatch 变异未被拒绝")
    missing_exit_gap = copy.deepcopy(cycles)
    multi_exit = next(row for row in missing_exit_gap if row["id"] == "multi-exit-closure")
    multi_exit["facts"]["gaps"].pop()
    if not validate_cycles(missing_exit_gap):
        failures.append("漏掉整个产品出口 gap 的闭包变异未被拒绝")
    incomplete_completed = copy.deepcopy(cycles)
    complete_case = next(row for row in incomplete_completed if row["id"] == "product-exit-complete")
    complete_case["facts"]["frontier_closure_status"] = "incomplete"
    status, actions = derive_cycle(complete_case["facts"])
    if status == "completed" or "recompute_product_frontier" not in actions or not validate_cycles(incomplete_completed):
        failures.append("产品出口完成与不完整前沿并存的变异未被拒绝")
    integration = load_jsonl(INTEGRATION)
    direct_none = copy.deepcopy(next(row["facts"] for row in integration if row["id"] == "direct-user-mandate"))
    direct_none["global_tradeoff_authority"] = "none"
    if mandate_errors(direct_none) or derive_integration(direct_none) != "activate_owner":
        failures.append("范围内 Owner 被错误要求全局取舍授权")
    planned = copy.deepcopy(next(row["facts"] for row in integration if row["id"] == "systemic-closure-complete"))
    if derive_integration(planned) != "start_writer":
        failures.append("高风险覆盖计划被实现后的结果证据倒置阻塞")
    planned["requested_action"] = "deliver"
    if derive_integration(planned) != "hold_before_delivery":
        failures.append("高风险计划被错误接受为交付结果")
    ungranted = copy.deepcopy(next(row["facts"] for row in integration if row["id"] == "new-feedback-submitted"))
    ungranted.pop("feedback_authority")
    if derive_integration(ungranted) != "candidate" or not feedback_side_effect_errors(ungranted):
        failures.append("canonical 访问错误地产生了外部写入授权")
    wrong_authority = copy.deepcopy(ungranted)
    wrong_authority["feedback_authority"] = {"authority_locator": "user:grant", "repository": "other/repo", "actions": ["create_issue"]}
    if feedback_authorized(wrong_authority):
        failures.append("反馈授权目标不匹配被错误接受")
    wrong_authority["feedback_authority"]["repository"] = "MC-and-his-Agents/MC-AGENT-KIT"
    wrong_authority["feedback_authority"]["actions"] = ["add_comment"]
    if feedback_authorized(wrong_authority):
        failures.append("反馈授权动作不匹配被错误接受")
    wrong_authority["feedback_authority"]["actions"] = ["search_issue", "read_issue", "create_issue"]
    if not feedback_authorized(wrong_authority):
        failures.append("已有反馈读写授权被错误要求重新授权")
    bad_integration = copy.deepcopy(integration)
    next(row for row in bad_integration if row["id"] == "head-change-keeps-unit")["expected"] = "new_unit"
    if not validate_integration(bad_integration):
        failures.append("实现载体重置 Unit 的变异未被拒绝")
    for field in ("scope_locator", "global_tradeoff_authority"):
        bad_mandate = copy.deepcopy(integration)
        direct = next(row for row in bad_mandate if row["id"] == "direct-user-mandate")
        direct["facts"].pop(field)
        if not validate_integration(bad_mandate):
            failures.append(f"缺少 {field} 的 Owner 准入变异未被拒绝")
    for case_id, identity_key in (("direct-user-writer-admission", "unit_identity"), ("pmo-unit-writer-admission", "pmo_admission")):
        for field in json.loads(CONTRACT.read_text(encoding="utf-8"))["writer_admission"]["required_unit_identity_fields"]:
            bad_identity = copy.deepcopy(integration)
            writer_case = next(row for row in bad_identity if row["id"] == case_id)
            writer_case["facts"][identity_key].pop(field)
            if not validate_integration(bad_identity):
                failures.append(f"{case_id} 缺少 {field} 的 writer 准入变异未被拒绝")
    capability_fields = json.loads(CONTRACT.read_text(encoding="utf-8"))["writer_admission"]["capability_compatibility_required_fields"]
    for field in capability_fields:
        bad_capability = copy.deepcopy(integration)
        writer_case = next(row for row in bad_capability if row["id"] == "direct-user-writer-admission")
        writer_case["facts"]["capability_compatibility"].pop(field)
        if not validate_integration(bad_capability):
            failures.append(f"缺少 {field} 的 action-scoped capability 变异未被拒绝")
    missing_required_semantic = copy.deepcopy(integration)
    capability = next(row for row in missing_required_semantic if row["id"] == "direct-user-writer-admission")["facts"]["capability_compatibility"]
    capability["observed_semantics"].pop("permission")
    if not validate_integration(missing_required_semantic):
        failures.append("下一动作缺少 required permission 的变异未被拒绝")
    for semantic in ("carrier_binding", "target_identity", "permission"):
        mismatched_semantic = copy.deepcopy(integration)
        capability = next(row for row in mismatched_semantic if row["id"] == "direct-user-writer-admission")["facts"]["capability_compatibility"]
        capability["observed_semantics"][semantic] = f"mismatch:{semantic}"
        if not validate_integration(mismatched_semantic):
            failures.append(f"required/observed {semantic} 精确值不一致的变异未被拒绝")
    for label, case_id, semantic, value in (
        ("local target identity", "direct-user-writer-admission", "target_identity", "app-task:delegated"),
        ("native target identity", "pmo-unit-writer-admission", "target_identity", "thread:current"),
        ("ambient cwd/carrier", "direct-user-writer-admission", "carrier_binding", "ambient:cwd"),
        ("non-targeted monitoring", "pmo-unit-writer-admission", "monitoring", "all-agents"),
    ):
        wrong_surface_binding = copy.deepcopy(integration)
        capability = next(row for row in wrong_surface_binding if row["id"] == case_id)["facts"]["capability_compatibility"]
        capability["required_semantics"][semantic] = value
        capability["observed_semantics"][semantic] = value
        if not validate_integration(wrong_surface_binding):
            failures.append(f"selected surface 接受错误 {label} 的变异未被拒绝")
    wrong_contract_identity = copy.deepcopy(integration)
    capability = next(row for row in wrong_contract_identity if row["id"] == "pmo-unit-writer-admission")["facts"]["capability_compatibility"]
    capability["capability_locator"] = "tool:local-shell"
    if not validate_integration(wrong_contract_identity):
        failures.append("selected surface 接受错误 capability contract identity 的变异未被拒绝")
    for label, case_id, field, value in (
        ("target identity", "direct-user-writer-admission", "target_identity", "thread:"),
        ("target identity sentinel", "direct-user-writer-admission", "target_identity", "thread:unknown"),
        ("target identity null sentinel", "direct-user-writer-admission", "target_identity", "thread:null"),
        ("cwd/carrier", "direct-user-writer-admission", "carrier_binding", "git-common-dir:"),
        ("cwd/carrier sentinel", "direct-user-writer-admission", "carrier_binding", "git-common-dir:none"),
        ("cwd/carrier n/a sentinel", "direct-user-writer-admission", "carrier_binding", "git-common-dir:n/a"),
        ("targeted monitoring", "pmo-unit-writer-admission", "monitoring", "targeted:"),
        ("targeted monitoring sentinel", "pmo-unit-writer-admission", "monitoring", "targeted:missing"),
        ("targeted monitoring na sentinel", "pmo-unit-writer-admission", "monitoring", "targeted:na"),
    ):
        empty_target = copy.deepcopy(integration)
        capability = next(row for row in empty_target if row["id"] == case_id)["facts"]["capability_compatibility"]
        capability["required_semantics"][field] = value
        capability["observed_semantics"][field] = value
        if not validate_integration(empty_target):
            failures.append(f"只有前缀而无实体的 {label} 变异未被拒绝")
    empty_contract_identity = copy.deepcopy(integration)
    capability = next(row for row in empty_contract_identity if row["id"] == "direct-user-writer-admission")["facts"]["capability_compatibility"]
    for value in ("tool:", "tool:none", "tool:tbd", "tool:null"):
        capability["capability_locator"] = value
        if not validate_integration(copy.deepcopy(empty_contract_identity)):
            failures.append("只有前缀或 sentinel 的 capability contract identity 变异未被拒绝")
    attempted_before_admission = copy.deepcopy(integration)
    capability = next(row for row in attempted_before_admission if row["id"] == "delegated-required-capability-missing")["facts"]["capability_compatibility"]
    capability["side_effect_attempted"] = True
    if not validate_integration(attempted_before_admission):
        failures.append("capability 不兼容却已创建或产生副作用的变异未被拒绝")
    forged_compatible = copy.deepcopy(integration)
    capability = next(row for row in forged_compatible if row["id"] == "delegated-required-capability-missing")["facts"]["capability_compatibility"]
    capability["status"] = "compatible"
    if not validate_integration(forged_compatible):
        failures.append("缺失 capability 被伪装为 compatible 的变异未被拒绝")
    escalated_to_user = copy.deepcopy(integration)
    capability = next(row for row in escalated_to_user if row["id"] == "delegated-required-capability-missing")["facts"]["capability_compatibility"]
    capability["negative_or_unavailable_behavior"] = "waiting_user"
    if not validate_integration(escalated_to_user):
        failures.append("runtime capability 缺失被转交用户的变异未被拒绝")
    cancel_without_readback = copy.deepcopy(integration)
    capability = next(row for row in cancel_without_readback if row["id"] == "approval-cancel-remains-owner-actionable")["facts"]["capability_compatibility"]
    capability["observed_semantics"].pop("readback")
    if not validate_integration(cancel_without_readback):
        failures.append("exact-task cancel 缺少 terminal/旧动作未执行回读的变异未被拒绝")
    repeated_probe = copy.deepcopy(integration)
    capability = next(row for row in repeated_probe if row["id"] == "unchanged-delegated-failure-does-not-reprobe")["facts"]["capability_compatibility"]
    capability["probe_attempted"] = True
    if not validate_integration(repeated_probe):
        failures.append("相同 route/environment/authority 失败的重复 probe 变异未被拒绝")
    reset_prior_failure = copy.deepcopy(integration)
    capability = next(row for row in reset_prior_failure if row["id"] == "unchanged-delegated-failure-does-not-reprobe")["facts"]["capability_compatibility"]
    capability["prior_equivalent_failure"] = False
    if not validate_integration(reset_prior_failure):
        failures.append("保留旧 evidence 却重置 prior failure 的变异未被拒绝")
    changed_prior_evidence = copy.deepcopy(integration)
    capability = next(row for row in changed_prior_evidence if row["id"] == "unchanged-delegated-failure-does-not-reprobe")["facts"]["capability_compatibility"]
    capability["equivalent_failure_evidence"] = "contract-check:other@same-schema-environment-authority"
    if not validate_integration(changed_prior_evidence):
        failures.append("等价失败 evidence 与当前 contract check 不一致的变异未被拒绝")
    bad_admission = copy.deepcopy(integration)
    pmo_case = next(row for row in bad_admission if row["id"] == "pmo-work-item-mandate")
    pmo_case["facts"]["pmo_admission"].pop("scope_locator")
    if not validate_integration(bad_admission):
        failures.append("缺少范围定位的 PMO 准入变异未被拒绝")
    bad_admission_version = copy.deepcopy(integration)
    next(row for row in bad_admission_version if row["id"] == "pmo-work-item-mandate")["facts"]["pmo_admission"]["schema_version"] = "1.0.0"
    if not validate_integration(bad_admission_version):
        failures.append("旧共享合同版本的 PMO 准入变异未被拒绝")
    for sentinel in ("none", "unknown", "null", "missing", "n/a", "na", "tbd"):
        direct_sentinel = copy.deepcopy(integration)
        next(row for row in direct_sentinel if row["id"] == "direct-user-mandate")["facts"]["scope_locator"] = sentinel
        if not validate_integration(direct_sentinel):
            failures.append(f"direct mandate scope sentinel {sentinel} 未被拒绝")
        for field in PMO_ADMISSION_FIELDS - {"allowed_scope", "excluded_scope"}:
            admission_sentinel = copy.deepcopy(integration)
            admission = next(row for row in admission_sentinel if row["id"] == "pmo-work-item-mandate")["facts"]["pmo_admission"]
            admission[field] = sentinel
            if not validate_integration(admission_sentinel):
                failures.append(f"PMO admission {field} sentinel {sentinel} 未被拒绝")
    for field in ("allowed_scope", "excluded_scope"):
        admission_sentinel = copy.deepcopy(integration)
        next(row for row in admission_sentinel if row["id"] == "pmo-work-item-mandate")["facts"]["pmo_admission"][field] = ["missing"]
        if not validate_integration(admission_sentinel):
            failures.append(f"PMO admission {field} sentinel 未被拒绝")
    noisy_lane = copy.deepcopy(integration)
    lane = next(row for row in noisy_lane if row["id"] == "ordinary-unit-continuous-lane")
    lane["facts"]["pmo_visible_events"].insert(1, "started")
    if not validate_integration(noisy_lane):
        failures.append("普通 Unit 的 PMO-visible STARTED 变异未被拒绝")
    missing_lane = copy.deepcopy(integration)
    lane = next(row for row in missing_lane if row["id"] == "ordinary-unit-continuous-lane")
    for field in ("pmo_visible_events", "owner_internal_events", "owner_sparse_deltas", "pmo_human_message_count"):
        lane["facts"].pop(field)
    if not validate_integration(missing_lane):
        failures.append("省略 continuous lane 事实的变异未被拒绝")
    fake_delta = copy.deepcopy(integration)
    lane = next(row for row in fake_delta if row["id"] == "ordinary-unit-continuous-lane")
    lane["facts"]["pmo_visible_events"].insert(1, "owner_sparse_delta")
    if not validate_integration(fake_delta):
        failures.append("无 material 事实的 sparse delta 变异未被拒绝")
    for malformed in ("true", 1):
        malformed_lane = copy.deepcopy(integration)
        lane = next(row for row in malformed_lane if row["id"] == "ordinary-unit-continuous-lane")
        lane["facts"]["current_delivery_action"] = malformed
        for field in ("pmo_visible_events", "owner_internal_events", "owner_sparse_deltas", "pmo_human_message_count"):
            lane["facts"].pop(field)
        if not validate_integration(malformed_lane):
            failures.append(f"malformed current_delivery_action={malformed!r} 变异未被拒绝")
    for case_id in ("delegated-required-capability-missing", "systemic-closure-missing"):
        disguised_gate = copy.deepcopy(integration)
        case = next(row for row in disguised_gate if row["id"] == case_id)
        case["facts"].update(
            current_delivery_action=True,
            pmo_visible_events=["pmo_admission", "unit_completed"],
            owner_internal_events=["implementation", "validation"],
            owner_sparse_deltas=[],
            pmo_human_message_count=0,
        )
        case["expected"] = "continue_delivery"
        if not validate_integration(disguised_gate):
            failures.append(f"{case_id} 被普通 continuous lane 掩盖的变异未被拒绝")
    closure_schema = json.loads(CONTRACT.read_text(encoding="utf-8"))["systemic_invariant_closure"]
    for field in closure_schema["required_fields"]:
        bad_closure = copy.deepcopy(integration)
        closure_case = next(row for row in bad_closure if row["id"] == "systemic-closure-complete")
        closure_case["facts"]["closure"].pop(field)
        if not validate_integration(bad_closure):
            failures.append(f"缺少 {field} 的闭包变异未被拒绝")
    for field in set(closure_schema["required_fields"]) - {"surfaces"}:
        bad_closure = copy.deepcopy(integration)
        next(row for row in bad_closure if row["id"] == "systemic-closure-complete")["facts"]["closure"][field] = "missing"
        if not validate_integration(bad_closure):
            failures.append(f"sentinel {field} 的闭包变异未被拒绝")
    for field in closure_schema["surface_required_fields"]:
        bad_closure = copy.deepcopy(integration)
        closure_case = next(row for row in bad_closure if row["id"] == "systemic-closure-complete")
        closure_case["facts"]["closure"]["surfaces"][0].pop(field)
        if not validate_integration(bad_closure):
            failures.append(f"缺少 {field} 的闭包适用面变异未被拒绝")
    late_predicate = copy.deepcopy(integration)
    closure_case = next(row for row in late_predicate if row["id"] == "systemic-closure-complete")
    closure_case["facts"]["closure"]["ordering"] = "first_observable_side_effect_before_predicate"
    if not validate_integration(late_predicate):
        failures.append("高风险 predicate 晚于首次可观察副作用的变异未被拒绝")
    bad_feedback = copy.deepcopy(cycles)
    feedback_case = next(row for row in bad_feedback if row["id"] == "delivery-before-skill-feedback")
    feedback_case["facts"]["canonical_repository_match"] = False
    if not validate_cycles(bad_feedback):
        failures.append("canonical 仓库不匹配的提交变异未被拒绝")
    for label, mutate in (
        ("反馈提交 locator", lambda facts: facts.pop("feedback_submission_locator")),
        ("反馈提交回读", lambda facts: facts.update(feedback_readback_verified=False)),
        ("Skill digest 保持", lambda facts: facts.update(skill_digest_unchanged=False)),
        ("反馈目标仓库", lambda facts: facts.update(canonical_repository_match=False)),
        ("反馈去重", lambda facts: facts.update(feedback_dedupe_complete=False)),
        ("GitHub feedback capability", lambda facts: facts.update(github_feedback_capability_available=False)),
    ):
        bad_submission = copy.deepcopy(integration)
        submission = next(row for row in bad_submission if row["id"] == "new-feedback-submitted")
        mutate(submission["facts"])
        if not validate_integration(bad_submission):
            failures.append(f"缺少{label}的反馈提交变异未被拒绝")
    submitted = next(row for row in integration if row["id"] == "new-feedback-submitted")
    for case_id, expected, mutate in (
        ("adversarial-project-write", "continue_delivery", lambda facts: facts.update(root_cause_target="project")),
        ("adversarial-delivery-write", "continue_delivery", lambda facts: facts.update(current_delivery_action=True)),
        ("adversarial-redaction-write", "deferred_private", lambda facts: facts.update(feedback_redaction_safe=False)),
        ("adversarial-identity-write", "deferred_private", lambda facts: facts.update(skill_identity_match=False)),
        ("adversarial-repository-write", "deferred_private", lambda facts: facts.update(canonical_repository_match=False)),
        ("adversarial-dedupe-write", "candidate", lambda facts: facts.update(feedback_dedupe_complete=False)),
        ("adversarial-capability-write", "candidate", lambda facts: facts.update(github_feedback_capability_available=False)),
        ("adversarial-digest-write", "candidate", lambda facts: facts.update(skill_digest_unchanged=False)),
    ):
        side_effect_case = copy.deepcopy(submitted)
        side_effect_case["id"] = case_id
        side_effect_case["expected"] = expected
        mutate(side_effect_case["facts"])
        if derive_integration(side_effect_case["facts"]) != expected:
            failures.append(f"{case_id} 未保持原负向控制状态")
        elif not validate_integration(copy.deepcopy(integration) + [side_effect_case]):
            failures.append(f"{case_id} 的矛盾反馈副作用未被独立拒绝")
    for label, mutate in (
        ("产品动作优先", lambda facts: facts.update(product_actions_complete=False)),
        ("根因枚举", lambda facts: facts.update(root_cause_target="unclassified")),
        ("candidate 字段", lambda facts: facts["feedback_candidate"].pop("product_impact")),
        ("API body 字段", lambda facts: facts["feedback_api_body"].pop("product_impact")),
        ("Skill 根因目标", lambda facts: facts["feedback_candidate"].update(affected_skill="platform")),
        ("fingerprint 易变字段", lambda facts: facts["feedback_candidate"]["fingerprint_seed"].update(head="abc")),
        ("fingerprint 根因", lambda facts: facts["feedback_candidate"]["fingerprint_seed"].update(incident_root_cause_class="platform")),
        ("首次 occurrence", lambda facts: facts["feedback_api_body"]["fingerprint_occurrence"].pop("occurrence")),
        ("dedupe 结果", lambda facts: facts.pop("existing_feedback_issue")),
    ):
        bad_payload = copy.deepcopy(integration)
        payload_case = next(row for row in bad_payload if row["id"] == "explicit-pmo-correction-standing-authority")
        mutate(payload_case["facts"])
        if not validate_integration(bad_payload):
            failures.append(f"破坏{label}的反馈变异未被拒绝")
    bad_occurrence = copy.deepcopy(integration)
    next(row for row in bad_occurrence if row["id"] == "existing-feedback-occurrence")["facts"]["feedback_occurrence"].pop("source_locator")
    if not validate_integration(bad_occurrence):
        failures.append("缺少 occurrence 字段的反馈变异未被拒绝")
    bad_platform_target = copy.deepcopy(integration)
    next(row for row in bad_platform_target if row["id"] == "redaction-failed")["facts"]["feedback_candidate"]["affected_skill"] = "pmo"
    if not validate_integration(bad_platform_target):
        failures.append("platform 根因错误定位到 pmo 的变异未被拒绝")
    form_text = FEEDBACK_FORM.read_text(encoding="utf-8")
    if not feedback_form_errors(contract, form_text.replace("id: product_impact", "id: product_value")):
        failures.append("Form 与机器 schema 漂移的变异未被拒绝")
    if not feedback_form_errors(contract, form_text.replace("required: true", "required: false", 1)):
        failures.append("Form 核心必填字段失效的变异未被拒绝")
    misplaced_required = form_text.replace("    validations:\n      required: true", "    attributes:\n      required: true", 1)
    if not feedback_form_errors(contract, misplaced_required):
        failures.append("Form required 脱离 validations 的变异未被拒绝")
    forged_form = re.sub(
        r"(?ms)^  - type: textarea\n    id: product_impact\n.*?(?=^  - type:|\Z)",
        "",
        form_text,
    ).replace("value: |\n", "value: |\n        id: product_impact\n        required: true\n", 1)
    if not feedback_form_errors(contract, forged_form):
        failures.append("藏在 markdown 中的伪 Form 字段绕过了结构校验")
    body_prefix, body_text = form_text.split("body:\n", 1)
    first_control = body_text.index("  - type: dropdown")
    escaped_controls = f"{body_prefix}body:\n{body_text[:first_control]}x_controls:\n{body_text[first_control:]}"
    if not feedback_form_errors(contract, escaped_controls):
        failures.append("逃逸到 body 外的 Form 控件绕过了结构校验")
    for case_id, wrong_action in (
        ("existing-feedback-occurrence", "create_issue"),
        ("explicit-pmo-correction-standing-authority", "add_comment"),
        ("existing-feedback-occurrence", "search_issue"),
        ("explicit-pmo-correction-standing-authority", "read_issue"),
    ):
        bad_action = copy.deepcopy(integration)
        next(row for row in bad_action if row["id"] == case_id)["facts"]["feedback_write_action"] = wrong_action
        if not validate_integration(bad_action):
            failures.append("与 dedupe 结果不一致的反馈动作未被拒绝")
    fingerprint_facts = {
        "affected_skill": "pmo", "incident_root_cause_class": "skill",
        "governing_behavior_category": "frontier-closure", "platform_contract_major": 2,
        "branch": "one", "head": "abc", "owner": "owner-a", "heartbeat": "first",
    }
    changed_identity = dict(fingerprint_facts, branch="two", head="def", owner="owner-b", heartbeat="second")
    if feedback_fingerprint(fingerprint_facts, contract) != feedback_fingerprint(changed_identity, contract):
        failures.append("稳定 fingerprint 被 branch/head/Owner/Heartbeat 污染")
    return failures + run_existing(True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        errors = self_test() if args.self_test else validate()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    for error in errors:
        print(f"error: {error}")
    if not errors:
        print("双层编排自检通过。" if args.self_test else "双层编排校验通过。")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
