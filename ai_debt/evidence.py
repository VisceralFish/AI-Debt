from __future__ import annotations

from typing import Any


REQUIRED_CANDIDATE_FIELDS = ("concept", "debt_dimension", "why_it_matters")


def evaluate_candidate(candidate: dict[str, Any], delegation_points: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for field in REQUIRED_CANDIDATE_FIELDS:
        if not str(candidate.get(field, "")).strip():
            reasons.append(f"missing {field}")

    point = _delegation_point(candidate, delegation_points)
    if point is None:
        reasons.append("missing delegation point")

    if not _has_traceable_evidence(candidate, point):
        reasons.append("missing event/diff/transcript evidence")

    return not reasons, reasons


def collect_evidence_refs(candidate: dict[str, Any], delegation_points: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for ref in candidate.get("evidence_refs", []):
        if isinstance(ref, dict) and ref.get("kind") and ref.get("ref"):
            refs.append({"kind": str(ref["kind"]), "ref": str(ref["ref"])})

    point = _delegation_point(candidate, delegation_points)
    if point:
        for event_ref in point.get("event_refs", []):
            refs.append({"kind": "event", "ref": str(event_ref)})
        for diff_ref in point.get("diff_refs", []):
            refs.append({"kind": "diff", "ref": str(diff_ref)})
        for transcript_ref in point.get("transcript_refs", []):
            refs.append({"kind": "transcript", "ref": str(transcript_ref)})

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        key = (ref["kind"], ref["ref"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _delegation_point(candidate: dict[str, Any], delegation_points: list[dict[str, Any]]) -> dict[str, Any] | None:
    point_id = candidate.get("delegation_point_id")
    if point_id:
        for point in delegation_points:
            if str(point.get("id")) == str(point_id):
                return point
    inline = candidate.get("delegation_point")
    if isinstance(inline, dict):
        return inline
    return None


def _has_traceable_evidence(candidate: dict[str, Any], point: dict[str, Any] | None) -> bool:
    refs = collect_evidence_refs(candidate, [point] if point else [])
    return any(ref["kind"] in {"event", "diff", "transcript"} and ref["ref"] for ref in refs)
