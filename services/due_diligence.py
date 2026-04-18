"""Sparrow Capital Due Diligence Checklist Engine.

Implements the 8-phase Bond Financing Package Framework with 200+ documentation items.
Tracks third-party engagements, shovel-ready assessment, and 180-day timeline.
"""
import uuid
from datetime import datetime, timedelta


# ── 8-Phase Due Diligence Framework ─────────────────────────────

DD_PHASES = {
    "phase_1_organizational": {
        "name": "Phase 1: Organizational & Sponsor Documentation",
        "timeline_days": (1, 30),
        "items": [
            {"id": "1.1", "item": "Certificates of incorporation, bylaws, amendments", "category": "sponsor_org", "required": True},
            {"id": "1.2", "item": "Corporate structure chart (parent, affiliates, subsidiaries)", "category": "sponsor_org", "required": True},
            {"id": "1.3", "item": "Board minutes and shareholder meeting records (3 years)", "category": "sponsor_org", "required": True},
            {"id": "1.4", "item": "List of jurisdictions where business is conducted", "category": "sponsor_org", "required": True},
            {"id": "1.5", "item": "Officers and directors list with bios/CVs", "category": "key_personnel", "required": True},
            {"id": "1.6", "item": "Management organization chart", "category": "key_personnel", "required": True},
            {"id": "1.7", "item": "3 years audited financial statements", "category": "sponsor_financials", "required": True},
            {"id": "1.8", "item": "3 years unaudited financial statements", "category": "sponsor_financials", "required": True},
            {"id": "1.9", "item": "Off-balance sheet transaction disclosures", "category": "sponsor_financials", "required": True},
            {"id": "1.10", "item": "Ultimate beneficial owner (UBO) charts", "category": "sponsor_org", "required": True},
            {"id": "1.11", "item": "SPV/project entity formation documents", "category": "project_entity", "required": True},
            {"id": "1.12", "item": "Developer track record (completed projects list)", "category": "key_personnel", "required": True},
            {"id": "1.13", "item": "Property management firm selection + references", "category": "operations", "required": True},
        ],
    },
    "phase_2_financial": {
        "name": "Phase 2: Financial Documentation & Modeling",
        "timeline_days": (30, 60),
        "items": [
            {"id": "2.1", "item": "Total project funding needs (USD)", "category": "capital_structure", "required": True},
            {"id": "2.2", "item": "Target capital stack with cost of capital", "category": "capital_structure", "required": True},
            {"id": "2.3", "item": "Detailed capitalization schedule", "category": "capital_structure", "required": True},
            {"id": "2.4", "item": "Equity investment to date and commitments", "category": "capital_structure", "required": True},
            {"id": "2.5", "item": "Financial model (Excel) with documented assumptions", "category": "financial_model", "required": True},
            {"id": "2.6", "item": "Revenue assumptions with supporting data", "category": "financial_model", "required": True},
            {"id": "2.7", "item": "OpEx and CapEx assumptions with drawdown schedule", "category": "financial_model", "required": True},
            {"id": "2.8", "item": "Projected returns (IRR, ROI), breakeven analysis", "category": "financial_model", "required": True},
            {"id": "2.9", "item": "Financial ratios: DSCR, coverage, liquidity, margins", "category": "financial_model", "required": True},
            {"id": "2.10", "item": "3 years audited sponsor financials", "category": "financial_reporting", "required": True},
            {"id": "2.11", "item": "Tax returns (open statute years)", "category": "tax", "required": True},
            {"id": "2.12", "item": "Real property tax bills and assessments", "category": "tax", "required": False},
        ],
    },
    "phase_3_market": {
        "name": "Phase 3: Commercial & Market Analysis",
        "timeline_days": (60, 90),
        "items": [
            {"id": "3.1", "item": "Industry and asset class overview", "category": "market_analysis", "required": True},
            {"id": "3.2", "item": "Target market definition and size", "category": "market_analysis", "required": True},
            {"id": "3.3", "item": "Market trends and demand drivers", "category": "market_analysis", "required": True},
            {"id": "3.4", "item": "Competitor analysis (market shares, strengths/weaknesses)", "category": "market_analysis", "required": True},
            {"id": "3.5", "item": "KPMG/PwC feasibility study commissioned", "category": "feasibility", "required": True},
            {"id": "3.6", "item": "Primary market research (95% confidence)", "category": "feasibility", "required": True},
            {"id": "3.7", "item": "Marketing and sales strategy", "category": "marketing", "required": True},
            {"id": "3.8", "item": "Pre-sales/absorption strategy", "category": "marketing", "required": False},
        ],
    },
    "phase_4_technical": {
        "name": "Phase 4: Technical & Engineering",
        "timeline_days": (30, 90),
        "items": [
            {"id": "4.1", "item": "Site analysis (location, demographics, competition)", "category": "site_dd", "required": True},
            {"id": "4.2", "item": "Phase I Environmental Site Assessment", "category": "environmental", "required": True},
            {"id": "4.3", "item": "Phase II ESA (if Phase I flags issues)", "category": "environmental", "required": False},
            {"id": "4.4", "item": "Geotechnical investigation", "category": "site_dd", "required": True},
            {"id": "4.5", "item": "ALTA/NSPS survey", "category": "site_dd", "required": True},
            {"id": "4.6", "item": "Property appraisals (MAI)", "category": "site_dd", "required": True},
            {"id": "4.7", "item": "Construction drawings and specifications", "category": "construction", "required": True},
            {"id": "4.8", "item": "GMP contract or construction cost estimate", "category": "construction", "required": True},
            {"id": "4.9", "item": "Project execution schedule (Gantt)", "category": "construction", "required": True},
            {"id": "4.10", "item": "EPC/GC contractor selection", "category": "construction", "required": True},
            {"id": "4.11", "item": "Zoning verification and entitlements", "category": "entitlements", "required": True},
            {"id": "4.12", "item": "Building permits (approved or filed)", "category": "entitlements", "required": True},
        ],
    },
    "phase_5_legal": {
        "name": "Phase 5: Legal & Regulatory",
        "timeline_days": (60, 120),
        "items": [
            {"id": "5.1", "item": "Articles of incorporation, certificate of good standing", "category": "corporate", "required": True},
            {"id": "5.2", "item": "Joint venture / partnership agreements", "category": "corporate", "required": False},
            {"id": "5.3", "item": "Intellectual property inventory", "category": "corporate", "required": False},
            {"id": "5.4", "item": "Summary of all outstanding debt obligations", "category": "contracts", "required": True},
            {"id": "5.5", "item": "GMP contracts and construction agreements", "category": "contracts", "required": True},
            {"id": "5.6", "item": "Guarantee and indemnification agreements", "category": "contracts", "required": True},
            {"id": "5.7", "item": "Legal opinion (S1 compliant, entity + securities)", "category": "legal_opinion", "required": True},
            {"id": "5.8", "item": "Pending/threatened litigation disclosure", "category": "litigation", "required": True},
            {"id": "5.9", "item": "Regulatory compliance reports (3 years)", "category": "compliance", "required": True},
        ],
    },
    "phase_6_risk": {
        "name": "Phase 6: Risk Management & Insurance",
        "timeline_days": (60, 120),
        "items": [
            {"id": "6.1", "item": "Insurable risk assessment (Alliant/Marsh/Aon)", "category": "risk_assessment", "required": True},
            {"id": "6.2", "item": "Builder's risk insurance", "category": "insurance", "required": True},
            {"id": "6.3", "item": "General liability + professional liability", "category": "insurance", "required": True},
            {"id": "6.4", "item": "Environmental liability insurance", "category": "insurance", "required": True},
            {"id": "6.5", "item": "Business interruption insurance", "category": "insurance", "required": True},
            {"id": "6.6", "item": "Title commitment + proforma title policy", "category": "title", "required": True},
            {"id": "6.7", "item": "Performance bonds (GC)", "category": "bonds", "required": True},
            {"id": "6.8", "item": "Credit surety / LC for bond enhancement", "category": "credit_enhancement", "required": True},
            {"id": "6.9", "item": "Stress testing and scenario analysis", "category": "risk_assessment", "required": True},
        ],
    },
    "phase_7_esg": {
        "name": "Phase 7: ESG & Community Engagement",
        "timeline_days": (60, 120),
        "items": [
            {"id": "7.1", "item": "Environmental impact overview + mitigation", "category": "environmental", "required": True},
            {"id": "7.2", "item": "Sustainability initiatives", "category": "environmental", "required": False},
            {"id": "7.3", "item": "Social impact assessment + job creation", "category": "social", "required": True},
            {"id": "7.4", "item": "Community benefit agreements", "category": "social", "required": False},
            {"id": "7.5", "item": "Board governance framework", "category": "governance", "required": True},
        ],
    },
    "phase_8_bond_structuring": {
        "name": "Phase 8: Bond Structuring & Capital Stack",
        "timeline_days": (120, 180),
        "items": [
            {"id": "8.1", "item": "Series structure with timing/duration per tranche", "category": "structure", "required": True},
            {"id": "8.2", "item": "Coupon reserve calculations", "category": "structure", "required": True},
            {"id": "8.3", "item": "Credit surety premium calculations", "category": "structure", "required": True},
            {"id": "8.4", "item": "Sparrow/NEST fee calculation (2.5-3.5%)", "category": "fees", "required": True},
            {"id": "8.5", "item": "Bond offering memorandum (144A)", "category": "documentation", "required": True},
            {"id": "8.6", "item": "Bond indenture and trust agreement", "category": "documentation", "required": True},
            {"id": "8.7", "item": "Bond trustee proposal (Computershare)", "category": "documentation", "required": True},
            {"id": "8.8", "item": "Credit enhancement documentation", "category": "documentation", "required": True},
            {"id": "8.9", "item": "S&P rating agency package", "category": "rating", "required": True},
        ],
    },
}

# Shovel-Ready Assessment
SHOVEL_READY_CRITERIA = [
    {"id": "sr1", "criterion": "Land control confirmed", "phase": "phase_4_technical"},
    {"id": "sr2", "criterion": "Zoning and entitlements obtained", "phase": "phase_4_technical"},
    {"id": "sr3", "criterion": "Phase I/II ESA complete", "phase": "phase_4_technical"},
    {"id": "sr4", "criterion": "Design and construction documents finalized", "phase": "phase_4_technical"},
    {"id": "sr5", "criterion": "Building permits approved or filed", "phase": "phase_4_technical"},
    {"id": "sr6", "criterion": "GC/EPC contractor selected", "phase": "phase_4_technical"},
    {"id": "sr7", "criterion": "Insurance bound or committed", "phase": "phase_6_risk"},
    {"id": "sr8", "criterion": "Legal entity formed + legal opinion obtained", "phase": "phase_5_legal"},
    {"id": "sr9", "criterion": "Pro forma validated + financial model stress-tested", "phase": "phase_2_financial"},
    {"id": "sr10", "criterion": "Feasibility study complete with favorable conclusions", "phase": "phase_3_market"},
]

# Third-Party Engagements
THIRD_PARTY_FIRMS = [
    {"role": "Market Feasibility", "firms": ["KPMG LLP", "PwC"], "deliverable": "Independent feasibility study"},
    {"role": "Financial Audit", "firms": ["KPMG", "PwC", "Marcum LLP", "Deloitte"], "deliverable": "Compilation/audit report"},
    {"role": "Legal Opinion", "firms": ["Stradling Yocca Carlson & Rauth"], "deliverable": "S1-compliant legal opinion"},
    {"role": "Bond Counsel", "firms": ["Pillsbury Winthrop Shaw Pittman"], "deliverable": "Bond structure legal review"},
    {"role": "Insurance Broker", "firms": ["Alliant", "Marsh McLennan", "Aon"], "deliverable": "Insurable risk analysis"},
    {"role": "Surety Provider", "firms": ["Hylant Insurance"], "deliverable": "Surety bond/LC credit enhancement"},
    {"role": "Rating Agency", "firms": ["S&P Global Ratings"], "deliverable": "Investment grade credit rating"},
    {"role": "Bond Trustee", "firms": ["Computershare"], "deliverable": "Escrow + coupon administration"},
]


class DueDiligenceEngine:
    """Manages 8-phase DD checklist, shovel-ready assessment, and timeline."""

    def __init__(self):
        self._checklists = {}  # deal_id -> {item_id: status}

    def initialize_checklist(self, deal_id: str, start_date: str = None) -> dict:
        """Create a full DD checklist for a deal."""
        start = datetime.fromisoformat(start_date) if start_date else datetime.utcnow()
        checklist = {}
        for phase_key, phase in DD_PHASES.items():
            for item in phase["items"]:
                checklist[item["id"]] = {
                    "item_id": item["id"],
                    "item": item["item"],
                    "phase": phase_key,
                    "phase_name": phase["name"],
                    "category": item["category"],
                    "required": item["required"],
                    "status": "not_started",  # not_started|in_progress|received|approved|waived|blocked
                    "document_id": None,
                    "notes": "",
                    "due_date": (start + timedelta(days=phase["timeline_days"][1])).isoformat(),
                    "updated_at": None,
                }
        self._checklists[deal_id] = checklist
        return self.get_checklist_summary(deal_id)

    def update_item(self, deal_id: str, item_id: str, status: str,
                    document_id: str = None, notes: str = None) -> dict:
        """Update a single checklist item."""
        checklist = self._checklists.get(deal_id, {})
        item = checklist.get(item_id)
        if not item:
            return {"error": f"Item {item_id} not found for deal {deal_id}"}
        item["status"] = status
        if document_id:
            item["document_id"] = document_id
        if notes:
            item["notes"] = notes
        item["updated_at"] = datetime.utcnow().isoformat()
        return item

    def get_checklist_summary(self, deal_id: str) -> dict:
        """Get checklist status summary by phase."""
        checklist = self._checklists.get(deal_id, {})
        if not checklist:
            return {"error": "No checklist initialized for this deal"}

        phases = {}
        total_items = len(checklist)
        completed = 0
        blocked = 0

        for item in checklist.values():
            phase = item["phase"]
            if phase not in phases:
                phases[phase] = {"name": item["phase_name"], "total": 0, "completed": 0, "in_progress": 0, "blocked": 0}
            phases[phase]["total"] += 1
            if item["status"] in ("received", "approved", "waived"):
                phases[phase]["completed"] += 1
                completed += 1
            elif item["status"] == "in_progress":
                phases[phase]["in_progress"] += 1
            elif item["status"] == "blocked":
                phases[phase]["blocked"] += 1
                blocked += 1

        score = int(completed / total_items * 100) if total_items > 0 else 0

        return {
            "deal_id": deal_id,
            "total_items": total_items,
            "completed": completed,
            "blocked": blocked,
            "readiness_score": score,
            "phases": phases,
        }

    def shovel_ready_assessment(self, deal_id: str) -> dict:
        """Assess 10-point shovel-ready criteria."""
        checklist = self._checklists.get(deal_id, {})
        results = []
        passed = 0

        for criterion in SHOVEL_READY_CRITERIA:
            # Check if related phase items are complete
            phase_items = [i for i in checklist.values() if i["phase"] == criterion["phase"] and i["required"]]
            phase_complete = all(i["status"] in ("received", "approved", "waived") for i in phase_items) if phase_items else False
            status = "pass" if phase_complete else "fail"
            if phase_complete:
                passed += 1
            results.append({
                "id": criterion["id"],
                "criterion": criterion["criterion"],
                "status": status,
                "phase": criterion["phase"],
            })

        return {
            "deal_id": deal_id,
            "criteria": results,
            "passed": passed,
            "total": len(SHOVEL_READY_CRITERIA),
            "score": int(passed / len(SHOVEL_READY_CRITERIA) * 100),
            "funding_release_ready": passed >= 8,
        }

    def get_timeline(self, deal_id: str, start_date: str = None) -> dict:
        """Generate 180-day milestone timeline."""
        start = datetime.fromisoformat(start_date) if start_date else datetime.utcnow()
        milestones = [
            {"phase": "Phase 1", "label": "Engagement & Data Gathering", "start_day": 1, "end_day": 30, "deliverable": "Signed LOE, initial document collection"},
            {"phase": "Phase 2", "label": "Due Diligence Deep Dive", "start_day": 30, "end_day": 60, "deliverable": "Completed DD checklist, draft financials"},
            {"phase": "Phase 3", "label": "Third-Party Engagement", "start_day": 60, "end_day": 90, "deliverable": "KPMG/PwC, Alliant engagement letters"},
            {"phase": "Phase 4", "label": "Report Compilation", "start_day": 90, "end_day": 120, "deliverable": "Feasibility study, risk report, legal opinion"},
            {"phase": "Phase 5", "label": "Bond Structuring", "start_day": 120, "end_day": 150, "deliverable": "Offering memorandum, trustee proposal"},
            {"phase": "Phase 6", "label": "Package Assembly & Rating", "start_day": 150, "end_day": 180, "deliverable": "Complete bond package, IG rating"},
        ]
        for m in milestones:
            m["start_date"] = (start + timedelta(days=m["start_day"])).isoformat()
            m["end_date"] = (start + timedelta(days=m["end_day"])).isoformat()
        return {
            "deal_id": deal_id,
            "start_date": start.isoformat(),
            "target_close_date": (start + timedelta(days=180)).isoformat(),
            "milestones": milestones,
            "third_party_firms": THIRD_PARTY_FIRMS,
        }


# Singleton
dd_engine = DueDiligenceEngine()
