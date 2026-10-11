"""The site's machine-readable feed.

Everything the site shows that can change -- build state, hypotheses, the holdout summary, the
leaderboard snapshot, source health -- is assembled here, so the published page is a rendering of
the repository rather than something a human retyped. Non-competition sources may be health-probed;
DrivenData leaderboard snapshots are manual only and this module never requests that host.

Score discipline: an owner-reported number is stored with ``"kind": "owner_report"`` and is never
rendered next to a verified number without that label; a leaderboard row is a dated public-page
observation, not a project score or file attribution.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_PROBE = ("drivendata.org",)      # standing brief: never automate access to the competition host


def _read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def sha256(path: Path, limit: int | None = None) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def build(root: Path = ROOT) -> dict:
    reg, docs = root / "registry", root / "docs"
    feed: dict = {"schema": 1, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    src = _read_json(reg / "sources.json", {"sources": []})
    feed["sources"] = src["sources"]
    feed["source_count"] = len(src["sources"])

    rows = []
    lb_path = reg / "leaderboard_history.jsonl"
    if lb_path.exists():
        for line in lb_path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    feed["leaderboard"] = rows[-1]["rows"] if rows else []
    feed["leaderboard_observed_utc"] = rows[-1].get("observed_utc") if rows else None
    feed["leaderboard_verified"] = bool(rows and rows[-1].get("verified"))
    feed["leaderboard_snapshots"] = len(rows)
    feed["leaderboard_retrieval_policy"] = "manual rendered-page snapshots only; no automated competition-host request"
    # Current operating status is intentionally separate from registry/submission_build.json:
    # a historic primary must not override a later preregistered stop verdict.
    active_status = _read_json(reg / "current_site_status.json")
    if active_status:
        feed["active_site_status"] = active_status

    # A dated audit supersedes historical positive cards without erasing their evidence.
    stop_audit = _read_json(docs / "h68-runcard.json")
    if stop_audit:
        feed["current_lane_decision"] = {
            "verdict": stop_audit["verdict"],
            "submit_to_competition": stop_audit["okay_to_submit"],
            "new_tiff_generated": stop_audit["new_tiff_generated"],
            "research_raster_sha256": stop_audit["existing_research_raster_sha256"],
            "report": stop_audit["report"],
            "note": "Snapshot of this repository; NOT a live DrivenData score feed.",
        }
    h73 = _read_json(root / "evidence" / "h73_runcard.json")
    if h73:
        # Newer negative run supersedes the dated H68 status in the feed without
        # erasing H68's historical evidence or inventing a portal approval.
        feed["current_lane_decision"] = {
            "run": h73["run"], "verdict": h73["verdict"],
            "submit_to_competition": h73["submit_to_competition"],
            "new_tiff_generated": True, "download_ok": h73["download_ok"],
            "research_raster_sha256": h73["raster_sha256"],
            "holdout_dti": h73["holdout_dti"],
            "report": "docs/research/h73-result-and-h33-analysis.md",
            "note": h73["selector_decision"],
        }

    hyp = _read_json(reg / "hypotheses.json", {"hypotheses": []})
    feed["hypotheses"] = hyp["hypotheses"]

    claims = _read_json(reg / "claims.json", {"claims": []})
    feed["claims"] = claims["claims"]

    sub = _read_json(reg / "submission_build.json")
    if sub:
        f = sub.get("file", {})
        fp = root / f.get("path", "")
        f["sha256"] = f.get("sha256") or (sha256(fp) if fp.is_file() else None)
        f["bytes"] = f.get("bytes") or (fp.stat().st_size if fp.is_file() else None)
        if active_status and active_status.get("status") == "STOP" and not active_status.get("recommended_competition_submission"):
            feed["submission"] = None
            feed["historical_registry_submission_build"] = sub
        else:
            feed["submission"] = sub
    hold = _read_json(root / "evidence" / "holdout_run1.json")
    if hold:
        def _arms(f):
            a = f.get("arms", {})
            if isinstance(a, dict):
                return {k: {"dti": v.get("dti"), "n_px": v.get("n_px")} for k, v in a.items()}
            return {v["name"]: {"dti": v.get("dti"), "n_px": v.get("n_px")} for v in a}
        feed["holdout"] = {"preregistration": hold["preregistration"]["id"],
                           "summary": hold["summary"], "generated_utc": hold.get("generated_utc"),
                           "folds": [{"block": f.get("block"), "auc": f.get("auc"),
                                      "n_truth": f.get("n_truth", 0), "arms": _arms(f)}
                                     for f in hold["folds"]]}
    for name in ("h60_2_catalogue_difference.json", "truth_model_mc.json",
                 "emission_models_mc.json", "shipped_vs_incumbent_mc.json"):
        ev = _read_json(root / "evidence" / name)
        if ev:
            feed.setdefault("evidence", {})[name] = ev
    feed["irregularities"] = _read_json(reg / "irregularities.json", {"items": []})["items"]
    (docs / "data").mkdir(parents=True, exist_ok=True)
    (docs / "data" / "feed.json").write_text(json.dumps(feed, indent=1) + "\n")
    return feed


def refresh_sources(root: Path = ROOT, timeout: float = 15.0) -> dict:
    """Probe every *non-competition* source once and record the observed status.

    Sources on ``SKIP_PROBE`` (the competition host) are recorded as ``not_probed``: the standing
    brief is explicit that access to the competition site is never automated.
    """
    import urllib.request
    results = []
    src = _read_json(root / "registry" / "sources.json", {"sources": []})
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for s in src["sources"]:
        url = s["url"]
        rec = {"id": s["id"], "url": url, "checked_utc": now}
        if any(h in url for h in SKIP_PROBE):
            rec.update(status="not_probed", note="competition host: never probed automatically")
            results.append(rec)
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GEMSDOE32-feed/1.0 (+research)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                rec.update(http_status=int(r.status), content_type=r.headers.get("Content-Type", ""))
        except Exception as exc:                      # noqa: BLE001 - recorded, never raised
            rec.update(http_status=None, error=f"{type(exc).__name__}: {exc}")
        results.append(rec)
    out = {"checked_utc": now, "results": results,
           "policy": "drivendata.org is never requested by this repository"}
    (root / "docs" / "data").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "data" / "source_health.json").write_text(json.dumps(out, indent=1) + "\n")
    return out
