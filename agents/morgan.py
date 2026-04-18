"""
Morgan — NEST's content agent. Jimmy Lee tone, 12 content types, single
entry point per call (`generate`) and a batch helper that builds a full
deal marketing package in one shot.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from services.jimmy_lee import (
    JIMMY_LEE_SYSTEM_PROMPT,
    build_user_prompt,
    count_words,
    estimate_read_time,
)
from agents._claude import complete, ClaudeUnavailable


CONTENT_TYPES: dict[str, dict] = {
    "credit_memo": {
        "label": "Credit memo (institutional, ~25 pages)",
        "instruction": (
            "Draft a full institutional credit memo for the deal. Cover: "
            "transaction summary, sponsor quality, collateral, structure (A/B tranche, "
            "LC endgame replacing surety), cashflow waterfall, downside scenarios, "
            "covenants, and recommendation. Long form but every section earns its place."
        ),
        "max_tokens": 6000,
    },
    "executive_summary": {
        "label": "Executive summary (3 paragraphs)",
        "instruction": (
            "Write a three-paragraph executive summary. Paragraph 1: the deal in one "
            "breath. Paragraph 2: why the structure wins. Paragraph 3: the ask and the "
            "close. No bullet points."
        ),
        "max_tokens": 900,
    },
    "investor_teaser": {
        "label": "Investor teaser (1 page)",
        "instruction": (
            "One-page investor teaser. Lead with the yield and the structural edge. "
            "Name the sponsor, the collateral, the target close, and the minimum "
            "commitment. Blind the borrower if context.blind is true."
        ),
        "max_tokens": 1200,
    },
    "client_proposal": {
        "label": "Client proposal (new developer / sponsor)",
        "instruction": (
            "Proposal to a new developer considering NEST vs. a traditional broker. "
            "Show the cost delta (surety at ~9% vs. LC endgame under 1%), the 10–15 "
            "refi cycle economics, and the perpetual equity stake. Close with next step."
        ),
        "max_tokens": 2000,
    },
    "bd_outreach": {
        "label": "BD outreach email (cold or warm)",
        "instruction": (
            "Outreach email. One screen tall on a phone. Subject line first, then body. "
            "Open with a specific observation about the recipient's project. Make the "
            "ask binary: a 15-minute call this week or next."
        ),
        "max_tokens": 700,
    },
    "deal_update": {
        "label": "Deal update (periodic, to existing client)",
        "instruction": (
            "Periodic update to a client already in the bond. Progress since last "
            "update, yield vs. target, Vector status, the next expected event with a "
            "date. Brief. Signed Morgan, NEST Advisors."
        ),
        "max_tokens": 800,
    },
    "refi_notice": {
        "label": "Refi / call execution notice",
        "instruction": (
            "Notification that NEST is executing a call and refi cycle on the bond. "
            "State the call date, the new coupon, the arrangement fee captured, and the "
            "impact on client position. Matter-of-fact."
        ),
        "max_tokens": 700,
    },
    "term_sheet_cover": {
        "label": "Term sheet cover letter",
        "instruction": (
            "Cover letter that precedes an investor term sheet. Two short paragraphs. "
            "Why this deal, why now. Sign off directing them to the term sheet attached."
        ),
        "max_tokens": 600,
    },
    "fund_prospectus": {
        "label": "Fund prospectus section (AEC token fund)",
        "instruction": (
            "A single section of the AEC token fund prospectus. Write as if dropped "
            "into the larger document — no repeated front matter. Compliance-aware "
            "but still Jimmy Lee."
        ),
        "max_tokens": 2500,
    },
    "press_release": {
        "label": "Press release (deal close)",
        "instruction": (
            "Press release announcing a deal close. Standard PR format with dateline, "
            "lead paragraph, key deal metrics, sponsor and NEST quotes, and boilerplate. "
            "No hype. Let the numbers do it."
        ),
        "max_tokens": 1200,
    },
    "linkedin_post": {
        "label": "LinkedIn post (BD social)",
        "instruction": (
            "LinkedIn post. Three to six short lines. First line stops the scroll. "
            "One concrete number. One concrete claim. End with a specific CTA, not "
            "'DM me.' No hashtag carpet-bombing — two, maximum."
        ),
        "max_tokens": 400,
    },
    "investor_deck_slide": {
        "label": "Investor deck — single slide content",
        "instruction": (
            "Content for a single investor deck slide. Return: a slide title, a "
            "one-line subtitle, and 3–5 tight bullets. Nothing else. The design "
            "team will handle the layout."
        ),
        "max_tokens": 500,
    },
    "hylant_submission": {
        "label": "Hylant surety submission cover letter + summary",
        "instruction": (
            "Write a Hylant Insurance surety submission cover letter and deal summary. "
            "Reference all submitted documents (Phase I ESA, appraisal, GMP contract, "
            "operating agreement, financial statements). Flag any missing items. "
            "Include: deal name, bond face, LTV, DSCR, surety type requested, "
            "premium estimate, and timeline to bind. Formal tone with Jimmy Lee precision."
        ),
        "max_tokens": 1500,
    },
    "refi_cycle_update": {
        "label": "Refi cycle execution memo",
        "instruction": (
            "Write a short refi cycle execution memo. Cover: current rate environment, "
            "rate savings achieved this cycle (bps), new coupon rate, client annual savings, "
            "cumulative savings since origination, next cycle timing estimate, "
            "and investor communication summary. Direct, numbers-first."
        ),
        "max_tokens": 800,
    },
    "full_credit_memo": {
        "label": "Full credit memorandum (Jacaranda Trace template)",
        "instruction": (
            "Write a complete credit memorandum following the Jacaranda Trace PLOM template. "
            "10 sections: (1) Executive Summary — 3 paragraphs, Jimmy Lee voice, lead with recommendation. "
            "(2) Obligor & Project Description. (3) Sources & Uses / Capital Stack. "
            "(4) Credit Analysis — DSCR, LTV, leverage, LGD, obligor grade. "
            "(5) Market Feasibility Summary. (6) Surety Structure — Hylant / LC. "
            "(7) Risk Factors & Mitigants. (8) Covenant Framework. "
            "(9) Stress Test Results — Base / Downside / Stress. "
            "(10) Investment Recommendation — never hedge. "
            "Cite JP Morgan commercial credit benchmarks throughout. "
            "Reference the Hylant surety structure. Lead with YES or NO."
        ),
        "max_tokens": 6000,
    },
    "investor_term_sheet": {
        "label": "Investor term sheet (draft)",
        "instruction": (
            "Draft a bond investor term sheet. Include: Issuer, Series designation, "
            "Face amount, Coupon rate, Duration, Call schedule, Put provisions, "
            "Surety provider, Rating target, Minimum investment, Settlement mechanics, "
            "Tax treatment, Governing law. Format as a clean term sheet with "
            "two-column layout (term: value). No narrative — just terms."
        ),
        "max_tokens": 1200,
    },
}

BATCH_RECIPE = [
    "executive_summary",
    "investor_teaser",
    "term_sheet_cover",
    "investor_deck_slide",
]


class MorganAgent:
    content_types = list(CONTENT_TYPES.keys())

    def __init__(self) -> None:
        self._history: list[dict] = []
        self._lock = threading.RLock()

    # ---------- core ----------

    def generate(self, content_type: str, context: Optional[dict] = None) -> dict:
        if content_type not in CONTENT_TYPES:
            raise ValueError(f"unknown content_type: {content_type}")
        spec = CONTENT_TYPES[content_type]
        ctx = dict(context or {})
        user_prompt = build_user_prompt(content_type, ctx, spec["instruction"])

        try:
            content = complete(
                JIMMY_LEE_SYSTEM_PROMPT,
                user_prompt,
                max_tokens=spec.get("max_tokens"),
            )
            error: Optional[str] = None
        except ClaudeUnavailable as e:
            content = f"_[generator offline: {e}]_"
            error = str(e)
        except Exception as e:  # noqa: BLE001 — surface any SDK failure as data
            content = f"_[generator error: {e}]_"
            error = str(e)

        record = {
            "id": uuid.uuid4().hex[:12],
            "content_type": content_type,
            "content_type_label": spec["label"],
            "content": content,
            "word_count": count_words(content),
            "estimated_read_time": estimate_read_time(content),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "context": ctx,
            "error": error,
        }
        with self._lock:
            self._history.insert(0, record)
            self._history[:] = self._history[:200]
        return record

    def generate_batch(self, deal_id: str, context: Optional[dict] = None) -> dict:
        ctx = dict(context or {})
        ctx.setdefault("deal_id", deal_id)
        materials: dict[str, dict] = {}
        for ctype in BATCH_RECIPE:
            materials[ctype] = self.generate(ctype, ctx)
        return {
            "deal_id": deal_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "materials": materials,
        }

    def history(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(self._history[:limit])

    def get(self, gen_id: str) -> Optional[dict]:
        with self._lock:
            for item in self._history:
                if item["id"] == gen_id:
                    return item
        return None
