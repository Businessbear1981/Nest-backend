"""Auditor — Project Audit Agent.

Runs a comprehensive audit of any deal in the NEST pipeline.
Checks completeness, identifies gaps, scores readiness across all dimensions.
"""
from datetime import datetime

try:
    from agents._claude import complete, ClaudeUnavailable
    from services.jimmy_lee import JIMMY_LEE_SYSTEM_PROMPT
except ImportError:
    complete = None
    JIMMY_LEE_SYSTEM_PROMPT = ""
    ClaudeUnavailable = Exception


AUDIT_DIMENSIONS = {
    "documentation": {
        "weight": 0.15,
        "checks": [
            "Sponsor financials (3yr audited)",
            "Corporate structure chart + UBO",
            "Officer/director bios",
            "SPV formation documents",
        ],
    },
    "financial_model": {
        "weight": 0.20,
        "checks": [
            "Proforma model with documented assumptions",
            "Revenue assumptions benchmarked",
            "Expense assumptions within range",
            "DSCR >1.5x at stabilization",
            "IRR/ROI projections reasonable",
            "Sensitivity analysis completed",
        ],
    },
    "credit_quality": {
        "weight": 0.20,
        "checks": [
            "DSCR meets JP Morgan A-grade (>2.0x) or BBB- (>1.5x)",
            "LTV within target (<55% A, <70% BBB-)",
            "Debt/EBITDA within range (<4.5x A, <6.5x BBB-)",
            "Interest coverage adequate (>3.5x A, >2.25x BBB-)",
            "LGD acceptable with surety structure",
        ],
    },
    "market_feasibility": {
        "weight": 0.10,
        "checks": [
            "Market feasibility study ordered or complete",
            "Demand analysis supports unit count",
            "Supply pipeline analyzed",
            "Absorption rate realistic",
        ],
    },
    "construction_readiness": {
        "weight": 0.15,
        "checks": [
            "Phase I ESA complete",
            "Geotechnical investigation done",
            "GMP contract executed or near-final",
            "GC/EPC contractor selected",
            "Permits filed or approved",
            "Construction schedule (Gantt) provided",
        ],
    },
    "legal_regulatory": {
        "weight": 0.10,
        "checks": [
            "Legal opinion obtained or engaged",
            "Bond counsel engaged",
            "Litigation disclosed and assessed",
            "Zoning verified",
            "Licenses (AHCA etc.) in process",
        ],
    },
    "insurance_surety": {
        "weight": 0.10,
        "checks": [
            "Hylant surety submission ready",
            "Builder's risk insurance quoted",
            "General liability coverage planned",
            "Title commitment obtained",
            "Credit enhancement structure defined",
        ],
    },
}


class AuditorAgent:
    """Runs comprehensive project audits."""

    def audit_deal(self, deal: dict, bond: dict = None, checklist: dict = None,
                   credit_metrics: dict = None) -> dict:
        """Full project audit across all dimensions.

        Returns scored audit with findings, recommendations, and readiness grade.
        """
        findings = []
        dimension_results = {}

        for dim_name, dim_config in AUDIT_DIMENSIONS.items():
            dim_findings = self._audit_dimension(dim_name, dim_config, deal, bond, checklist, credit_metrics)
            passed = sum(1 for f in dim_findings if f["status"] == "pass")
            total = len(dim_findings)
            score = (passed / total * 100) if total > 0 else 0

            dimension_results[dim_name] = {
                "score": round(score, 1),
                "weight": dim_config["weight"],
                "passed": passed,
                "total": total,
                "findings": dim_findings,
            }
            findings.extend(dim_findings)

        # Weighted composite score
        composite = sum(
            d["score"] * d["weight"] for d in dimension_results.values()
        )

        # Critical blockers
        blockers = [f for f in findings if f["status"] == "fail" and f.get("blocking", False)]

        # Grade
        if composite >= 85 and not blockers:
            grade = "A"
            recommendation = "PROCEED TO STRUCTURING — deal meets all criteria"
        elif composite >= 70 and len(blockers) <= 2:
            grade = "B"
            recommendation = "PROCEED WITH CONDITIONS — address blockers before closing"
        elif composite >= 55:
            grade = "C"
            recommendation = "CONDITIONAL — significant gaps require resolution"
        else:
            grade = "D"
            recommendation = "NOT READY — major items outstanding"

        return {
            "deal_id": deal.get("id", "unknown"),
            "deal_name": deal.get("name", "Unknown"),
            "audit_date": datetime.utcnow().isoformat(),
            "composite_score": round(composite, 1),
            "grade": grade,
            "recommendation": recommendation,
            "dimension_results": dimension_results,
            "total_checks": len(findings),
            "passed": sum(1 for f in findings if f["status"] == "pass"),
            "failed": sum(1 for f in findings if f["status"] == "fail"),
            "warnings": sum(1 for f in findings if f["status"] == "warn"),
            "blockers": blockers,
            "blocker_count": len(blockers),
        }

    def _audit_dimension(self, dim_name, dim_config, deal, bond, checklist, metrics):
        """Audit a single dimension."""
        findings = []
        project = deal.get("project", {})
        sponsor = deal.get("sponsor", {})
        cl = checklist or deal.get("readiness_checklist", {})

        for check_text in dim_config["checks"]:
            result = self._evaluate_check(dim_name, check_text, deal, bond, cl, metrics, project, sponsor)
            findings.append(result)

        return findings

    def _evaluate_check(self, dim, check, deal, bond, cl, metrics, project, sponsor):
        """Evaluate a single audit check."""
        # Documentation checks
        if dim == "documentation":
            if "financials" in check.lower():
                has = sponsor.get("audited_financials_received", False)
                return {"check": check, "status": "pass" if has else "fail", "blocking": True, "note": "" if has else "3yr audited financials required for bond issuance"}
            if "SPV" in check or "formation" in check.lower():
                has = cl.get("bond_counsel_engaged", False)
                return {"check": check, "status": "pass" if has else "warn", "blocking": False, "note": ""}
            return {"check": check, "status": "warn", "blocking": False, "note": "Manual verification needed"}

        # Financial model checks
        if dim == "financial_model":
            if "DSCR" in check:
                dscr = (metrics or {}).get("dscr", 0)
                passed = dscr >= 1.5
                return {"check": check, "status": "pass" if passed else "fail", "blocking": True, "note": f"DSCR={dscr:.2f}x" if dscr else "No DSCR computed"}
            return {"check": check, "status": "warn", "blocking": False, "note": "Verify against proforma"}

        # Credit quality checks
        if dim == "credit_quality":
            m = metrics or {}
            if "DSCR" in check:
                dscr = m.get("dscr", 0)
                return {"check": check, "status": "pass" if dscr >= 1.5 else "fail", "blocking": True, "note": f"DSCR={dscr:.2f}x"}
            if "LTV" in check:
                ltv = m.get("ltv", 100)
                return {"check": check, "status": "pass" if ltv <= 70 else "fail", "blocking": True, "note": f"LTV={ltv:.1f}%"}
            if "LGD" in check:
                lgd = m.get("lgd_bank_conduit", 60)
                return {"check": check, "status": "pass" if lgd <= 20 else "warn", "blocking": False, "note": f"LGD={lgd:.1f}%"}
            return {"check": check, "status": "warn", "blocking": False, "note": "Verify against benchmarks"}

        # Construction checks
        if dim == "construction_readiness":
            if "Phase I" in check:
                st = cl.get("phase_i_environmental", "not_started")
                return {"check": check, "status": "pass" if st in ("received", "approved") else "fail" if st == "not_started" else "warn", "blocking": True, "note": f"Status: {st}"}
            if "GMP" in check:
                st = cl.get("gmp_contract", "not_started")
                return {"check": check, "status": "pass" if st == "executed" else "warn", "blocking": True, "note": f"Status: {st}"}
            return {"check": check, "status": "warn", "blocking": False, "note": "Verify with project team"}

        # Insurance checks
        if dim == "insurance_surety":
            if "Hylant" in check:
                ready = cl.get("hylant_submission_ready", False)
                return {"check": check, "status": "pass" if ready else "fail", "blocking": True, "note": "Hylant submission required for surety"}
            return {"check": check, "status": "warn", "blocking": False, "note": "Insurance package in progress"}

        # Default
        return {"check": check, "status": "warn", "blocking": False, "note": "Manual verification needed"}

    def generate_audit_report(self, audit_result: dict) -> str:
        """Generate a formatted audit report via Claude API."""
        prompt = (
            f"Generate a project audit report for {audit_result['deal_name']}.\n"
            f"Grade: {audit_result['grade']} ({audit_result['composite_score']}/100)\n"
            f"Passed: {audit_result['passed']}/{audit_result['total_checks']}\n"
            f"Blockers: {audit_result['blocker_count']}\n"
            f"Recommendation: {audit_result['recommendation']}\n\n"
            f"Write a 1-page audit summary. Jimmy Lee tone — direct, no hedging.\n"
            f"Lead with the grade and recommendation. List each blocker with specific fix.\n"
            f"Close with timeline to resolve and proceed."
        )
        try:
            return complete(JIMMY_LEE_SYSTEM_PROMPT, prompt, max_tokens=1500)
        except (ClaudeUnavailable, Exception):
            return f"# Audit Report — {audit_result['deal_name']}\n\nGrade: {audit_result['grade']}\nScore: {audit_result['composite_score']}/100\n\n{audit_result['recommendation']}"


# Singleton
auditor = AuditorAgent()
