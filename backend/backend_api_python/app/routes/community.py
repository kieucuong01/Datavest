"""Free, source-visible community library APIs."""

from __future__ import annotations

from flask import g, jsonify, request

from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.services.community_library import get_community_library
from app.utils.auth import login_required


community_blp = Blueprint("community", __name__)


def get_community_service():
    """Compatibility seam for route tests; returns the free library only."""
    return get_community_library()


def _page(default_size: int = 20) -> tuple[int, int]:
    page = max(1, request.args.get("page", 1, type=int))
    size = min(50, max(1, request.args.get("page_size", default_size, type=int)))
    return page, size


def _language() -> str:
    return request.headers.get("X-App-Lang") or request.headers.get("Accept-Language", "en-US").split(",")[0]


def _admin() -> bool:
    return str(getattr(g, "user_role", "") or "").lower() == "admin"


@community_blp.route("/indicators", methods=["GET"])
@login_required
def list_publications():
    page, size = _page(12)
    result = get_community_service().get_market_indicators(
        page=page,
        page_size=size,
        keyword=(request.args.get("keyword") or "").strip() or None,
        sort_by=(request.args.get("sort_by") or "score").strip(),
        user_id=int(g.user_id),
        accept_language=_language(),
        asset_type=(request.args.get("asset_type") or "").strip() or None,
    )
    return jsonify({"code": 1, "msg": "success", "data": result})


@community_blp.route("/indicators/<int:indicator_id>", methods=["GET"])
@login_required
def publication_detail(indicator_id: int):
    result = get_community_service().get_indicator_detail(indicator_id, user_id=int(g.user_id), accept_language=_language())
    if not result:
        return jsonify({"code": 0, "msg": "indicator_not_found", "data": None}), 404
    return jsonify({"code": 1, "msg": "success", "data": result})


@community_blp.route("/indicators/<int:indicator_id>/fork", methods=["POST"])
@login_required
def fork_publication(indicator_id: int):
    ok, message, data = get_community_service().fork_free_indicator(buyer_id=int(g.user_id), indicator_id=indicator_id)
    status = 200 if ok else (404 if message == "indicator_not_found" else 400)
    return jsonify({"code": 1 if ok else 0, "msg": message, "data": data}), status


@community_blp.route("/author/published", methods=["GET"])
@login_required
def author_publications():
    page, size = _page()
    result = get_community_service().get_author_published(user_id=int(g.user_id), page=page, page_size=size)
    return jsonify({"code": 1, "msg": "success", "data": result})


@community_blp.route("/author/indicators/<int:indicator_id>/unpublish", methods=["POST"])
@login_required
def author_unpublish(indicator_id: int):
    note = str((request.get_json(silent=True) or {}).get("note") or "")[:500]
    ok, message = get_community_service().author_unpublish_asset(int(g.user_id), indicator_id, note)
    return jsonify({"code": 1 if ok else 0, "msg": message, "data": None}), 200 if ok else 404


@community_blp.route("/indicators/<int:indicator_id>/comments", methods=["GET"])
@login_required
def comments(indicator_id: int):
    page, size = _page()
    return jsonify({"code": 1, "msg": "success", "data": get_community_service().get_comments(indicator_id, page, size)})


@community_blp.route("/indicators/<int:indicator_id>/comments", methods=["POST"])
@login_required
def add_comment(indicator_id: int):
    payload = request.get_json(silent=True) or {}
    ok, message, data = get_community_service().add_comment(
        user_id=int(g.user_id), indicator_id=indicator_id, rating=payload.get("rating", 5),
        content=str(payload.get("content") or ""), parent_id=payload.get("parent_id"),
    )
    return jsonify({"code": 1 if ok else 0, "msg": message, "data": data}), 200 if ok else 400


@community_blp.route("/indicators/<int:indicator_id>/comments/<int:comment_id>", methods=["PUT"])
@login_required
def update_comment(indicator_id: int, comment_id: int):
    payload = request.get_json(silent=True) or {}
    ok, message = get_community_service().update_comment(
        user_id=int(g.user_id), comment_id=comment_id, indicator_id=indicator_id,
        rating=payload.get("rating", 5), content=str(payload.get("content") or ""),
    )
    return jsonify({"code": 1 if ok else 0, "msg": message, "data": None}), 200 if ok else 400


@community_blp.route("/indicators/<int:indicator_id>/my-comment", methods=["GET"])
@login_required
def my_comment(indicator_id: int):
    item = get_community_service().get_user_comment(int(g.user_id), indicator_id)
    return jsonify({"code": 1, "msg": "success", "data": item})


@community_blp.route("/indicators/<int:indicator_id>/performance", methods=["GET"])
@login_required
def performance(indicator_id: int):
    return jsonify({"code": 1, "msg": "success", "data": get_community_service().get_indicator_performance(indicator_id)})


@community_blp.route("/admin/pending-indicators", methods=["GET"])
@login_required
def pending_publications():
    if not _admin():
        return jsonify({"code": 0, "msg": "admin_required", "data": None}), 403
    page, size = _page()
    result = get_community_service().get_pending_indicators(
        page=page, page_size=size, keyword=(request.args.get("keyword") or "").strip() or None,
        review_status=(request.args.get("review_status") or "pending").strip(),
    )
    return jsonify({"code": 1, "msg": "success", "data": result})


@community_blp.route("/admin/review-stats", methods=["GET"])
@login_required
def review_stats():
    if not _admin():
        return jsonify({"code": 0, "msg": "admin_required", "data": None}), 403
    return jsonify({"code": 1, "msg": "success", "data": get_community_service().get_review_stats()})


@community_blp.route("/admin/indicators/<int:indicator_id>/review", methods=["POST"])
@login_required
def review_publication(indicator_id: int):
    if not _admin():
        return jsonify({"code": 0, "msg": "admin_required", "data": None}), 403
    payload = request.get_json(silent=True) or {}
    ok, message = get_community_service().review_indicator(
        admin_id=int(g.user_id), indicator_id=indicator_id, action=str(payload.get("action") or "").strip(),
        note=str(payload.get("note") or "")[:500],
    )
    return jsonify({"code": 1 if ok else 0, "msg": message, "data": None}), 200 if ok else 400


@community_blp.route("/admin/indicators/<int:indicator_id>/unpublish", methods=["POST"])
@login_required
def admin_unpublish(indicator_id: int):
    if not _admin():
        return jsonify({"code": 0, "msg": "admin_required", "data": None}), 403
    note = str((request.get_json(silent=True) or {}).get("note") or "")[:500]
    ok, message = get_community_service().unpublish_indicator(int(g.user_id), indicator_id, note)
    return jsonify({"code": 1 if ok else 0, "msg": message, "data": None}), 200 if ok else 404


@community_blp.route("/admin/indicators/<int:indicator_id>", methods=["DELETE"])
@login_required
def admin_delete(indicator_id: int):
    if not _admin():
        return jsonify({"code": 0, "msg": "admin_required", "data": None}), 403
    ok, message = get_community_service().admin_delete_indicator(int(g.user_id), indicator_id)
    return jsonify({"code": 1 if ok else 0, "msg": message, "data": None}), 200 if ok else 404
