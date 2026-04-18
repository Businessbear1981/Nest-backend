"""
Aria — NEST's inbound and follow-up agent. Classifies new leads, sequences
outreach, and drafts client proposals. Shares the Jimmy Lee voice with Morgan.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from services.jimmy_lee import JIMMY_LEE_SYSTEM_PROMPT, count_words, estimate_read_time
from agents._claude import complete, ClaudeUnavailable


FOLLOW_UP_PLAYBOOK = {
    1: {
        "label": "Attempt 1 — value proposition",
        "instruction": (
            "First follow-up to a lead who went quiet. Lead with deal economics: the "
            "cost delta from surety (~9%) to LC endgame (under 1%), and the 10–15 "
            "refi cycles. One screen tall. Subject line included."
        ),
    },
    2: {
        "label": "Attempt 2 — proof / case study",
        "instruction": (
            "Second follow-up. Use the Jacaranda Trace blueprint as proof: how the "
            "structure performed end-to-end. Short, specific, numeric. Subject line "
            "included."
        ),
    },
    3: {
        "label": "Attempt 3 — direct ask",
        "instruction": (
            "Third and final follow-up. Direct ask: 15 minutes this week or next to "
            "discuss their specific deal. Two sentences of context, one sentence ask. "
            "Subject line included."
        ),
    },
}


class AriaAgent:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._leads: dict[str, dict] = {}
        self._inbound: list[dict] = []
        self._seed()

    def _seed(self) -> None:
        self._leads["lead_001"] = {
            "id": "lead_001",
            "name": "Jacaranda Trace Partners",
            "contact": "dev@jacarandatrace.example",
            "stage": "warm",
            "deal_concept": {"size_usd": 42_000_000, "asset": "senior housing, FL"},
        }
        self._leads["lead_002"] = {
            "id": "lead_002",
            "name": "Bellwether Industrial",
            "contact": "cfo@bellwether.example",
            "stage": "cold",
            "deal_concept": {"size_usd": 18_500_000, "asset": "cold storage, PNW"},
        }

    # ---------- public ----------

    def classify_inbound(self, message: str, sender: Optional[str] = None) -> dict:
        text = (message or "").lower()
        if any(k in text for k in ["press", "reporter", "journalist", "bloomberg"]):
            kind = "press"
            priority = "high"
        elif any(k in text for k in ["invest", "lp ", "allocator", "family office", "ticket"]):
            kind = "investor_inquiry"
            priority = "high"
        elif any(k in text for k in ["urgent", "closing", "this week", "friday"]):
            kind = "hot_lead"
            priority = "high"
        elif any(k in text for k in ["deal", "bond", "project", "financing", "refi"]):
            kind = "warm_lead"
            priority = "medium"
        else:
            kind = "warm_lead"
            priority = "low"

        record = {
            "id": uuid.uuid4().hex[:12],
            "sender": sender,
            "message": message,
            "kind": kind,
            "priority": priority,
            "received_at": datetime.utcnow().isoformat() + "Z",
            "suggested_next": {
                "press": "Route to Sean; draft a one-paragraph on-the-record statement.",
                "investor_inquiry": "Hand to Sterling; match against open deal book.",
                "hot_lead": "Draft immediate reply; book intro call within 24h.",
                "warm_lead": "Sequence into 3-attempt follow-up cadence.",
            }[kind],
        }
        with self._lock:
            self._inbound.insert(0, record)
            self._inbound[:] = self._inbound[:200]
        return record

    def generate_follow_up(self, lead_id: str, attempt: int) -> dict:
        if attempt not in FOLLOW_UP_PLAYBOOK:
            raise ValueError(f"attempt must be 1, 2, or 3 (got {attempt})")
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(lead_id)
        spec = FOLLOW_UP_PLAYBOOK[attempt]
        user_prompt = (
            f"{spec['instruction']}\n\nLead:\n"
            f"- Name: {lead['name']}\n"
            f"- Contact: {lead['contact']}\n"
            f"- Stage: {lead['stage']}\n"
            f"- Deal concept: {lead.get('deal_concept')}\n\n"
            "Return the subject line as a markdown level-2 heading, then the body."
        )
        try:
            body = complete(JIMMY_LEE_SYSTEM_PROMPT, user_prompt, max_tokens=700)
            error = None
        except ClaudeUnavailable as e:
            body = f"_[generator offline: {e}]_"
            error = str(e)
        return {
            "lead_id": lead_id,
            "attempt": attempt,
            "label": spec["label"],
            "content": body,
            "word_count": count_words(body),
            "estimated_read_time": estimate_read_time(body),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "error": error,
        }

    def draft_proposal(self, lead_id: str, deal_concept: Optional[dict] = None) -> dict:
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(lead_id)
        concept = deal_concept or lead.get("deal_concept") or {}
        user_prompt = (
            "Draft a full client proposal. Sections: project overview, NEST structure, "
            "preliminary economics (surety cost-out, refi cycle fees, perpetual equity), "
            "why NEST vs. a traditional broker, next step. Markdown headings.\n\n"
            f"Lead: {lead['name']} <{lead['contact']}>\n"
            f"Deal concept: {concept}\n"
        )
        try:
            body = complete(JIMMY_LEE_SYSTEM_PROMPT, user_prompt, max_tokens=2500)
            error = None
        except ClaudeUnavailable as e:
            body = f"_[generator offline: {e}]_"
            error = str(e)
        return {
            "lead_id": lead_id,
            "content": body,
            "word_count": count_words(body),
            "estimated_read_time": estimate_read_time(body),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "error": error,
        }

    def leads(self) -> list[dict]:
        with self._lock:
            return list(self._leads.values())

    def inbound(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(self._inbound[:limit])

    # ---------- public intake ----------

    def intake(self, payload: dict) -> dict:
        """
        BD intake form handler. Creates a lead record, classifies it, and
        drafts Aria's immediate response. Single call for the public form.
        """
        name = str(payload.get("name", "")).strip()
        company = str(payload.get("company", "")).strip()
        project_type = str(payload.get("project_type", "")).strip()
        size = payload.get("size_usd") or payload.get("size") or 0
        timeline = str(payload.get("timeline", "")).strip()
        contact = str(payload.get("email") or payload.get("contact") or "").strip()
        missing = [k for k, v in {"name": name, "company": company, "project_type": project_type}.items() if not v]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

        lead_id = f"lead_{uuid.uuid4().hex[:8]}"
        synthetic = (
            f"New inbound from public form. {name} at {company}. "
            f"Project: {project_type}. Size: {size}. Timeline: {timeline}. "
            f"Contact: {contact}."
        )
        classification = self.classify_inbound(synthetic, sender=contact or name)

        with self._lock:
            self._leads[lead_id] = {
                "id": lead_id,
                "name": company or name,
                "contact": contact,
                "stage": "new",
                "source": "public_form",
                "deal_concept": {
                    "size_usd": size,
                    "asset": project_type,
                    "timeline": timeline,
                    "sponsor": name,
                },
                "created_at": datetime.utcnow().isoformat() + "Z",
            }

        user_prompt = (
            "Draft Aria's immediate response to a fresh BD intake from the NEST public "
            "site. Tone: Jimmy Lee — direct, decisive, zero hedging. Open with the "
            "person's first name. Acknowledge the project in one sentence. Offer two "
            "concrete 15-minute slots in the next three business days. Sign as Aria, "
            "NEST Advisors.\n\n"
            f"Name: {name}\nCompany: {company}\nProject type: {project_type}\n"
            f"Size: {size}\nTimeline: {timeline}\nContact: {contact}\n"
        )
        try:
            reply = complete(JIMMY_LEE_SYSTEM_PROMPT, user_prompt, max_tokens=500)
            error = None
        except ClaudeUnavailable as e:
            reply = (
                f"{name.split()[0] if name else 'Hello'} —\n\n"
                f"Got your note on {project_type or 'your project'}. "
                "Fifteen minutes this week. Reply with a time that works.\n\n"
                "— Aria, NEST Advisors"
            )
            error = str(e)

        return {
            "lead_id": lead_id,
            "classification": classification,
            "immediate_response": {
                "content": reply,
                "error": error,
            },
            "received_at": datetime.utcnow().isoformat() + "Z",
        }
