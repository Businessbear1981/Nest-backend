from flask import Blueprint, current_app, jsonify, request, send_file

from services.auth import current_user, require_auth

documents_bp = Blueprint("documents", __name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


def _registry():
    return current_app.config["DOCS"]


@documents_bp.post("/upload")
@require_auth("admin", "client")
def upload():
    deal_id = request.form.get("deal_id") or request.args.get("deal_id")
    if not deal_id:
        return jsonify({"error": "deal_id required (form field or query param)"}), 400
    if "file" not in request.files:
        return jsonify({"error": "file part missing (multipart field 'file')"}), 400
    f = request.files["file"]
    data = f.read()
    if not data:
        return jsonify({"error": "empty file"}), 400
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({"error": f"file too large (>{MAX_UPLOAD_BYTES} bytes)"}), 413
    user = current_user()
    doc = _registry().upload(
        deal_id=deal_id,
        filename=f.filename or "unnamed",
        content_type=f.mimetype or "application/octet-stream",
        data=data,
        uploaded_by=user.email if user else None,
    )
    return jsonify(doc.public()), 201


@documents_bp.get("")
@require_auth()
def list_docs():
    deal_id = request.args.get("deal_id")
    reg = _registry()
    docs = reg.list_for_deal(deal_id) if deal_id else reg.list_all()
    user = current_user()
    if user and user.role == "client" and deal_id is None:
        # Clients without a deal_id filter shouldn't see the global list
        return jsonify([])
    return jsonify([d.public() for d in docs])


@documents_bp.get("/readiness")
@require_auth()
def readiness():
    deal_id = request.args.get("deal_id")
    if not deal_id:
        return jsonify({"error": "deal_id required"}), 400
    return jsonify(_registry().readiness(deal_id))


@documents_bp.get("/<doc_id>")
@require_auth()
def get_doc(doc_id: str):
    doc = _registry().get(doc_id)
    if doc is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(doc.public())


@documents_bp.get("/<doc_id>/download")
@require_auth()
def download_doc(doc_id: str):
    doc = _registry().get(doc_id)
    if doc is None:
        return jsonify({"error": "not_found"}), 404
    return send_file(doc.storage_path, as_attachment=True, download_name=doc.filename)


@documents_bp.delete("/<doc_id>")
@require_auth("admin")
def delete_doc(doc_id: str):
    ok = _registry().delete(doc_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"deleted": doc_id})
