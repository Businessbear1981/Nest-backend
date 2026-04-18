"""
Document registry + extraction stub.

Real extraction (PDF parsing, OCR, LLM field extraction) belongs in a worker
later. For now we capture the upload, store bytes on disk, mark a fake
extraction record per file, and compute a per-deal readiness score against
a required-doc checklist.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


# Required document checklist per deal — drives the readiness score
REQUIRED_DOCS: dict[str, dict] = {
    "rent_roll":          {"label": "Rent roll",                    "weight": 20},
    "operating_statement":{"label": "T-12 operating statement",     "weight": 20},
    "appraisal":          {"label": "Appraisal",                    "weight": 15},
    "title":              {"label": "Title commitment",             "weight": 10},
    "insurance":          {"label": "Insurance binder",             "weight": 10},
    "purchase_sale":      {"label": "Purchase and sale agreement",  "weight": 10},
    "sponsor_bio":        {"label": "Sponsor bio / track record",   "weight": 10},
    "environmental":      {"label": "Phase I environmental",        "weight":  5,},
}


def classify_document(filename: str) -> str:
    """Heuristic kind detection from filename. Cheap stand-in for real classification."""
    n = filename.lower()
    rules = [
        ("rent_roll",          ["rent roll", "rent_roll", "rentroll"]),
        ("operating_statement",["t-12", "t12", "operating", "p&l", "income statement"]),
        ("appraisal",          ["appraisal"]),
        ("title",              ["title"]),
        ("insurance",          ["insurance", "binder", "coi"]),
        ("purchase_sale",      ["psa", "purchase", "sale agreement"]),
        ("sponsor_bio",        ["bio", "track record", "sponsor"]),
        ("environmental",      ["phase i", "phase 1", "environmental", "esa"]),
    ]
    for kind, needles in rules:
        if any(n.find(re.sub(r"\s+", "", x)) >= 0 or n.find(x) >= 0 for x in needles):
            return kind
    return "other"


@dataclass
class Document:
    id: str
    deal_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    kind: str
    storage_path: str
    uploaded_by: Optional[str]
    uploaded_at: str
    extracted_fields: dict = field(default_factory=dict)
    extraction_status: str = "pending"  # pending | done | failed

    def public(self) -> dict:
        d = asdict(self)
        d.pop("storage_path", None)
        return d


class DocumentRegistry:
    def __init__(self, storage_root: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        self._docs: dict[str, Document] = {}
        self._by_deal: dict[str, list[str]] = {}
        self._storage_root = storage_root or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"
        )
        os.makedirs(self._storage_root, exist_ok=True)

    # ---------- writes ----------

    def upload(self, *, deal_id: str, filename: str, content_type: str, data: bytes, uploaded_by: Optional[str] = None) -> Document:
        if not deal_id:
            raise ValueError("deal_id required")
        if not filename:
            raise ValueError("filename required")
        digest = hashlib.sha256(data).hexdigest()
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        deal_dir = os.path.join(self._storage_root, deal_id)
        os.makedirs(deal_dir, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
        storage_path = os.path.join(deal_dir, f"{doc_id}__{safe_name}")
        with open(storage_path, "wb") as f:
            f.write(data)
        kind = classify_document(filename)
        doc = Document(
            id=doc_id,
            deal_id=deal_id,
            filename=filename,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(data),
            sha256=digest,
            kind=kind,
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
        )
        # Stub extraction — real version goes through OCR + Claude later.
        doc.extracted_fields = self._stub_extract(kind, filename, len(data))
        doc.extraction_status = "done"
        with self._lock:
            self._docs[doc.id] = doc
            self._by_deal.setdefault(deal_id, []).append(doc.id)
        return doc

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            doc = self._docs.pop(doc_id, None)
            if doc is None:
                return False
            self._by_deal.get(doc.deal_id, []).remove(doc.id) if doc.id in self._by_deal.get(doc.deal_id, []) else None
        try:
            os.remove(doc.storage_path)
        except OSError:
            pass
        return True

    # ---------- reads ----------

    def get(self, doc_id: str) -> Optional[Document]:
        with self._lock:
            return self._docs.get(doc_id)

    def list_for_deal(self, deal_id: str) -> list[Document]:
        with self._lock:
            ids = list(self._by_deal.get(deal_id, []))
            return [self._docs[i] for i in ids if i in self._docs]

    def list_all(self) -> list[Document]:
        with self._lock:
            return list(self._docs.values())

    # ---------- readiness ----------

    def readiness(self, deal_id: str) -> dict:
        docs = self.list_for_deal(deal_id)
        present_kinds = {d.kind for d in docs}
        score = 0
        present, missing = [], []
        for kind, meta in REQUIRED_DOCS.items():
            entry = {"kind": kind, "label": meta["label"], "weight": meta["weight"]}
            if kind in present_kinds:
                score += meta["weight"]
                present.append(entry)
            else:
                missing.append(entry)
        return {
            "deal_id": deal_id,
            "score": min(100, score),
            "present": present,
            "missing": missing,
            "doc_count": len(docs),
            "blocking_count": len(missing),
        }

    # ---------- internals ----------

    def _stub_extract(self, kind: str, filename: str, size: int) -> dict:
        base = {"source_filename": filename, "size_bytes": size, "extractor": "stub_v1"}
        if kind == "rent_roll":
            return {**base, "unit_count": 142, "occupancy_pct": 94.4, "noi_annualized_usd": 1_870_000}
        if kind == "operating_statement":
            return {**base, "period": "T-12", "egi_usd": 3_120_000, "opex_usd": 1_250_000, "noi_usd": 1_870_000}
        if kind == "appraisal":
            return {**base, "as_is_value_usd": 32_500_000, "cap_rate_pct": 5.75, "appraiser": "Cushman & Wakefield"}
        if kind == "title":
            return {**base, "title_company": "First American", "exceptions_count": 3}
        if kind == "insurance":
            return {**base, "carrier": "Chubb", "limit_usd": 50_000_000, "deductible_usd": 25_000}
        if kind == "purchase_sale":
            return {**base, "purchase_price_usd": 31_750_000, "earnest_money_usd": 750_000, "close_date": "2026-05-15"}
        if kind == "sponsor_bio":
            return {**base, "principals": 2, "deals_completed": 14, "afm_track_record_yrs": 17}
        if kind == "environmental":
            return {**base, "phase": "I", "rec_count": 0, "consultant": "Terracon"}
        return base
