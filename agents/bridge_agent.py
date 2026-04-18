"""
Bridge Agent - Permanent debt monitoring.

Tracks deals approaching stabilization and initiates permanent financing
conversations with bank partners 18 months before stabilization.
No external dependencies.
"""

from datetime import datetime, timedelta, timezone


class BridgeAgent:
    BANK_PARTNERS = [
        {
            "name": "Pacific Premier Bank",
            "max_ltv": 75,
            "min_dscr": 1.25,
            "typical_spread_bps": 200,
            "geographies": ["CA", "WA", "OR", "AZ", "NV"],
            "asset_types": ["multifamily", "mixed-use", "industrial"],
        },
        {
            "name": "Columbia Bank",
            "max_ltv": 70,
            "min_dscr": 1.30,
            "typical_spread_bps": 225,
            "geographies": ["WA", "OR", "ID"],
            "asset_types": ["multifamily", "office", "retail"],
        },
        {
            "name": "Banner Bank",
            "max_ltv": 72,
            "min_dscr": 1.25,
            "typical_spread_bps": 215,
            "geographies": ["WA", "OR", "CA", "ID", "UT"],
            "asset_types": ["multifamily", "industrial", "mixed-use"],
        },
    ]

    def __init__(self):
        self._monitoring: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Readiness assessment
    # ------------------------------------------------------------------

    def assess_perm_readiness(self, deal_data: dict) -> dict:
        """Evaluate whether a deal is ready for permanent financing.

        Expected deal_data keys (all optional with sensible defaults):
            occupancy (float 0-100), noi_trend (str: 'positive'|'flat'|'negative'),
            covenant_breach (bool), construction_complete (bool),
            stabilization_date (ISO str), current_ltv (float), current_dscr (float),
            asset_type (str), state (str).

        Returns dict with: ready, months_to_stabilization, readiness_score,
        blocking_items, recommended_action.
        """
        occupancy = deal_data.get("occupancy", 0)
        noi_trend = deal_data.get("noi_trend", "flat")
        covenant_breach = deal_data.get("covenant_breach", False)
        construction_complete = deal_data.get("construction_complete", False)
        stab_date_str = deal_data.get("stabilization_date")

        # Months to stabilization
        if stab_date_str:
            stab_date = datetime.fromisoformat(stab_date_str)
            if stab_date.tzinfo is None:
                stab_date = stab_date.replace(tzinfo=timezone.utc)
            months_to_stab = max(
                0,
                round(
                    (stab_date - datetime.now(timezone.utc)).days / 30.44
                ),
            )
        else:
            months_to_stab = None

        # Scoring (0-100)
        score = 0
        blocking: list[str] = []

        # Occupancy check (40 pts)
        if occupancy >= 90:
            score += 40
        elif occupancy >= 80:
            score += 25
        else:
            blocking.append(f"Occupancy too low ({occupancy}% < 80%)")

        # NOI trend (20 pts)
        if noi_trend == "positive":
            score += 20
        elif noi_trend == "flat":
            score += 10
        else:
            blocking.append("NOI trending negative")

        # Covenant compliance (20 pts)
        if not covenant_breach:
            score += 20
        else:
            blocking.append("Active covenant breach")

        # Construction status (20 pts)
        if construction_complete:
            score += 20
        else:
            blocking.append("Construction not yet complete")

        ready = score >= 70 and len(blocking) == 0

        # Recommended action
        if ready and months_to_stab is not None and months_to_stab <= 18:
            action = "Begin bank partner outreach immediately"
        elif ready:
            action = "Deal is ready; monitor stabilization timeline"
        elif score >= 50:
            action = "Address blocking items; target readiness within 6 months"
        else:
            action = "Not ready for permanent financing; continue stabilization"

        return {
            "ready": ready,
            "months_to_stabilization": months_to_stab,
            "readiness_score": score,
            "blocking_items": blocking,
            "recommended_action": action,
        }

    # ------------------------------------------------------------------
    # Bank matching
    # ------------------------------------------------------------------

    def match_bank_partners(self, deal_data: dict) -> list[dict]:
        """Return bank partners ranked by fit for this deal.

        deal_data keys used: current_ltv, current_dscr, state, asset_type.
        """
        current_ltv = deal_data.get("current_ltv", 0)
        current_dscr = deal_data.get("current_dscr", 0)
        state = deal_data.get("state", "").upper()
        asset_type = deal_data.get("asset_type", "").lower()

        scored: list[dict] = []
        for bank in self.BANK_PARTNERS:
            fit_score = 0
            reasons: list[str] = []
            disqualified = False

            # LTV fit (max 35 pts)
            ltv_headroom = bank["max_ltv"] - current_ltv
            if ltv_headroom >= 0:
                fit_score += min(35, int(ltv_headroom * 3.5))
                reasons.append(f"LTV headroom: {ltv_headroom:.0f}%")
            else:
                disqualified = True
                reasons.append(f"LTV exceeds bank max ({current_ltv}% > {bank['max_ltv']}%)")

            # DSCR fit (max 35 pts)
            dscr_margin = current_dscr - bank["min_dscr"]
            if dscr_margin >= 0:
                fit_score += min(35, int(dscr_margin * 100))
                reasons.append(f"DSCR margin: {dscr_margin:.2f}x")
            else:
                disqualified = True
                reasons.append(f"DSCR below minimum ({current_dscr:.2f}x < {bank['min_dscr']:.2f}x)")

            # Geography match (15 pts)
            if state in bank.get("geographies", []):
                fit_score += 15
                reasons.append("Geography match")
            else:
                reasons.append("Outside preferred geography")

            # Asset type match (15 pts)
            if asset_type in bank.get("asset_types", []):
                fit_score += 15
                reasons.append("Asset type match")
            else:
                reasons.append("Non-preferred asset type")

            scored.append({
                "bank": bank["name"],
                "fit_score": fit_score,
                "disqualified": disqualified,
                "reasons": reasons,
                "typical_spread_bps": bank["typical_spread_bps"],
            })

        # Sort: non-disqualified first, then by score descending
        scored.sort(key=lambda b: (not b["disqualified"], b["fit_score"]), reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Pre-qualification package
    # ------------------------------------------------------------------

    def generate_pre_qual_package(self, deal_data: dict, bank: dict) -> dict:
        """Build a pre-qualification package for a specific bank.

        Parameters
        ----------
        deal_data : dict
            Full deal information (property_name, address, units, asset_type,
            current_ltv, current_dscr, noi, appraised_value, occupancy,
            stabilization_date, loan_amount_requested).
        bank : dict
            Bank partner dict (from BANK_PARTNERS).

        Returns
        -------
        dict with deal_summary, key_metrics, timeline, and ask.
        """
        now = datetime.now(timezone.utc)
        stab_str = deal_data.get("stabilization_date", "TBD")

        return {
            "prepared_date": now.isoformat(),
            "bank_name": bank["name"],
            "deal_summary": {
                "property_name": deal_data.get("property_name", "N/A"),
                "address": deal_data.get("address", "N/A"),
                "units": deal_data.get("units", "N/A"),
                "asset_type": deal_data.get("asset_type", "N/A"),
            },
            "key_metrics": {
                "current_ltv": deal_data.get("current_ltv"),
                "current_dscr": deal_data.get("current_dscr"),
                "noi": deal_data.get("noi"),
                "appraised_value": deal_data.get("appraised_value"),
                "occupancy": deal_data.get("occupancy"),
            },
            "timeline": {
                "stabilization_date": stab_str,
                "target_close": (
                    (datetime.fromisoformat(stab_str) + timedelta(days=90)).isoformat()
                    if stab_str != "TBD"
                    else "TBD"
                ),
            },
            "ask": {
                "loan_amount": deal_data.get("loan_amount_requested"),
                "max_ltv": bank["max_ltv"],
                "min_dscr": bank["min_dscr"],
                "estimated_spread_bps": bank["typical_spread_bps"],
            },
        }

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    def start_monitoring(self, deal_id: str, deal_data: dict) -> dict:
        """Begin 18-month pre-stabilization monitoring for a deal."""
        now = datetime.now(timezone.utc)
        stab_str = deal_data.get("stabilization_date")

        if stab_str:
            stab_date = datetime.fromisoformat(stab_str)
            if stab_date.tzinfo is None:
                stab_date = stab_date.replace(tzinfo=timezone.utc)
            months_remaining = max(
                0, round((stab_date - now).days / 30.44)
            )
        else:
            months_remaining = None

        entry = {
            "deal_id": deal_id,
            "deal_data": deal_data,
            "started_at": now.isoformat(),
            "months_remaining": months_remaining,
            "check_history": [],
            "status": "active",
        }
        self._monitoring[deal_id] = entry

        return {
            "deal_id": deal_id,
            "status": "monitoring_started",
            "months_remaining": months_remaining,
            "message": (
                f"Monitoring started. {months_remaining} months to stabilization."
                if months_remaining is not None
                else "Monitoring started. Stabilization date not set."
            ),
        }

    def check_monitoring(self, deal_id: str) -> dict:
        """Return current monitoring status for a deal."""
        entry = self._monitoring.get(deal_id)
        if entry is None:
            return {"deal_id": deal_id, "status": "not_monitored"}

        deal_data = entry["deal_data"]
        readiness = self.assess_perm_readiness(deal_data)

        # Recalculate months remaining
        stab_str = deal_data.get("stabilization_date")
        now = datetime.now(timezone.utc)
        if stab_str:
            stab_date = datetime.fromisoformat(stab_str)
            if stab_date.tzinfo is None:
                stab_date = stab_date.replace(tzinfo=timezone.utc)
            months_remaining = max(0, round((stab_date - now).days / 30.44))
        else:
            months_remaining = None

        action_items: list[str] = []
        if readiness["ready"] and months_remaining is not None and months_remaining <= 18:
            action_items.append("Initiate bank partner conversations")
        if readiness["blocking_items"]:
            action_items.extend(
                [f"Resolve: {item}" for item in readiness["blocking_items"]]
            )
        if months_remaining is not None and months_remaining <= 6:
            action_items.append("Urgent: stabilization imminent, finalize perm terms")

        check_record = {
            "checked_at": now.isoformat(),
            "readiness": readiness,
            "months_remaining": months_remaining,
            "action_items": action_items,
        }
        entry["check_history"].append(check_record)
        entry["months_remaining"] = months_remaining

        return {
            "deal_id": deal_id,
            "status": entry["status"],
            "months_remaining": months_remaining,
            "readiness_score": readiness["readiness_score"],
            "ready_for_perm": readiness["ready"],
            "action_items": action_items,
            "checks_completed": len(entry["check_history"]),
        }

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------

    def run(self, deal_id: str, deal_data: dict | None = None) -> dict:
        """Full assessment: readiness check, bank matching, recommendation.

        If deal_data is None, attempts to use data from active monitoring.
        """
        if deal_data is None:
            entry = self._monitoring.get(deal_id)
            if entry is None:
                return {
                    "deal_id": deal_id,
                    "error": "No deal_data provided and deal is not being monitored.",
                }
            deal_data = entry["deal_data"]

        readiness = self.assess_perm_readiness(deal_data)
        bank_matches = self.match_bank_partners(deal_data)
        qualified_banks = [b for b in bank_matches if not b["disqualified"]]

        recommendation: dict = {
            "deal_id": deal_id,
            "readiness": readiness,
            "bank_matches": bank_matches,
            "top_bank": qualified_banks[0]["bank"] if qualified_banks else None,
            "qualified_count": len(qualified_banks),
        }

        if readiness["ready"] and qualified_banks:
            recommendation["next_step"] = (
                f"Send pre-qual package to {qualified_banks[0]['bank']}"
            )
            recommendation["pre_qual_package"] = self.generate_pre_qual_package(
                deal_data,
                next(
                    b
                    for b in self.BANK_PARTNERS
                    if b["name"] == qualified_banks[0]["bank"]
                ),
            )
        elif readiness["ready"]:
            recommendation["next_step"] = (
                "Deal is ready but no qualifying bank partners at current metrics. "
                "Review LTV/DSCR thresholds."
            )
        else:
            recommendation["next_step"] = readiness["recommended_action"]

        return recommendation


# Module-level singleton
bridge = BridgeAgent()
