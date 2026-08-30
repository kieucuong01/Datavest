"""Persistence for DataVest's permanently free, source-visible library."""

from __future__ import annotations

import json
from typing import Any

from app.services.community_kpis import fetch_market_asset_kpis, summarise_backtest_runs
from app.services.indicator_translator import pick_localized
from app.utils.db import get_db_connection


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _publication(row: dict[str, Any], language: str = "en-US") -> dict[str, Any]:
    item = dict(row)
    item["name"] = pick_localized(item.get("name"), item.get("name_i18n"), language)
    item["description"] = pick_localized(item.get("description"), item.get("description_i18n"), language)
    item["source_visible"] = True
    item["is_forked"] = bool(item.get("source_indicator_id"))
    return item


class CommunityLibrary:
    """Free publication, fork, review and discussion operations."""

    def publish_script_source(
        self,
        *,
        user_id: int,
        source_id: int,
        code: str,
        name: str,
        description: str,
        is_admin: bool = False,
        publication_id: int = 0,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Publish a script source with full source and immutable lineage."""
        status = "approved" if is_admin else "pending"
        with get_db_connection() as db:
            cur = db.cursor()
            if publication_id:
                cur.execute(
                    """
                    UPDATE qd_indicator_codes SET name = ?, description = ?, code = ?,
                        publish_to_community = 1, preview_image = '', asset_type = 'script_template',
                        source_script_source_id = ?, review_status = ?, review_note = '',
                        reviewed_at = CASE WHEN ? = 'approved' THEN NOW() ELSE NULL END,
                        reviewed_by = CASE WHEN ? = 'approved' THEN ? ELSE NULL END,
                        updated_at = NOW(), updatetime = EXTRACT(EPOCH FROM NOW())::BIGINT
                    WHERE id = ? AND user_id = ?
                    """,
                    (name, description, code, source_id, status, status, status, user_id, publication_id, user_id),
                )
                if not cur.rowcount:
                    cur.close()
                    return False, "publication_not_found", {}
            else:
                cur.execute(
                    """
                    INSERT INTO qd_indicator_codes
                        (user_id, is_buy, end_time, name, code, description, publish_to_community,
                         preview_image, asset_type, source_script_source_id, review_status,
                         reviewed_at, reviewed_by, createtime, updatetime, created_at, updated_at)
                    VALUES (?, 0, 1, ?, ?, ?, 1, '', 'script_template', ?, ?,
                            CASE WHEN ? = 'approved' THEN NOW() ELSE NULL END,
                            CASE WHEN ? = 'approved' THEN ? ELSE NULL END,
                            EXTRACT(EPOCH FROM NOW())::BIGINT, EXTRACT(EPOCH FROM NOW())::BIGINT, NOW(), NOW())
                    """,
                    (user_id, name, code, description, source_id, status, status, status, user_id),
                )
                publication_id = int(cur.lastrowid or 0)
            db.commit()
            cur.close()
        return True, "published", {"id": publication_id, "source_id": source_id, "review_status": status}

    def get_market_indicators(
        self,
        *,
        page: int = 1,
        page_size: int = 12,
        keyword: str | None = None,
        sort_by: str = "score",
        user_id: int | None = None,
        accept_language: str = "en-US",
        asset_type: str | None = None,
        **_ignored: Any,
    ) -> dict[str, Any]:
        where = ["i.publish_to_community = 1", "COALESCE(i.review_status, 'approved') = 'approved'"]
        params: list[Any] = []
        if keyword:
            where.append("(i.name ILIKE ? OR i.description ILIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if asset_type in {"indicator", "script_template"}:
            where.append("COALESCE(i.asset_type, 'indicator') = ?")
            params.append(asset_type)
        where_sql = " AND ".join(where)
        offset = (max(1, page) - 1) * page_size
        order = {
            "newest": "i.created_at DESC, i.id DESC",
            "hot": "i.view_count DESC, i.id DESC",
            "rating": "i.avg_rating DESC, i.rating_count DESC, i.id DESC",
        }.get(sort_by, "i.id DESC")
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(f"SELECT COUNT(*) AS count FROM qd_indicator_codes i WHERE {where_sql}", tuple(params))
            total = int((cur.fetchone() or {}).get("count") or 0)
            cur.execute(
                f"""
                SELECT i.id, i.user_id AS author_id, i.name, i.description, i.code,
                       i.preview_image, COALESCE(i.asset_type, 'indicator') AS asset_type,
                       i.source_indicator_id, i.source_script_source_id, i.source_strategy_id,
                       i.avg_rating, i.rating_count, i.view_count, i.created_at, i.updated_at,
                       i.name_i18n, i.description_i18n,
                       u.username AS author_username, u.nickname AS author_nickname, u.avatar AS author_avatar
                FROM qd_indicator_codes i
                LEFT JOIN qd_users u ON u.id = i.user_id
                WHERE {where_sql}
                ORDER BY {order}
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            )
            rows = [dict(row) for row in (cur.fetchall() or [])]
            if sort_by == "score" and rows:
                scores = fetch_market_asset_kpis(cur, rows)
                for row in rows:
                    row["performance"] = scores.get(int(row["id"]), summarise_backtest_runs([]))
                rows.sort(key=lambda row: (-(row["performance"].get("score") or 0), -int(row["id"])))
            cur.close()
        items = [_publication(row, accept_language) for row in rows]
        counts = {
            "indicator": sum(1 for item in items if item.get("asset_type") == "indicator"),
            "script_template": sum(1 for item in items if item.get("asset_type") == "script_template"),
        }
        return {
            "items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size, "asset_type_counts": counts,
        }

    def get_indicator_detail(self, indicator_id: int, *, user_id: int | None = None, accept_language: str = "en-US") -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT i.*, u.username AS author_username, u.nickname AS author_nickname, u.avatar AS author_avatar
                FROM qd_indicator_codes i LEFT JOIN qd_users u ON u.id = i.user_id
                WHERE i.id = ? AND i.publish_to_community = 1
                  AND COALESCE(i.review_status, 'approved') = 'approved'
                """,
                (indicator_id,),
            )
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE qd_indicator_codes SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?", (indicator_id,))
                db.commit()
            cur.close()
        return _publication(dict(row), accept_language) if row else None

    def fork_free_indicator(self, *, buyer_id: int, indicator_id: int) -> tuple[bool, str, dict[str, Any]]:
        original = self.get_indicator_detail(indicator_id, user_id=buyer_id)
        if not original:
            return False, "indicator_not_found", {}
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO qd_indicator_codes
                    (user_id, is_buy, end_time, name, code, description, publish_to_community,
                     preview_image, asset_type, source_indicator_id, source_script_source_id,
                     source_strategy_id, createtime, updatetime, created_at, updated_at)
                VALUES (?, 0, 1, ?, ?, ?, 0, ?, ?, ?, ?, ?, EXTRACT(EPOCH FROM NOW())::BIGINT,
                        EXTRACT(EPOCH FROM NOW())::BIGINT, NOW(), NOW())
                """,
                (
                    buyer_id, f"{original.get('name') or 'Indicator'} (Fork)", original.get("code") or "",
                    original.get("description") or "", original.get("preview_image") or "",
                    original.get("asset_type") or "indicator", indicator_id,
                    original.get("source_script_source_id"), original.get("source_strategy_id"),
                ),
            )
            local_id = int(cur.lastrowid or 0)
            cur.execute(
                """
                INSERT INTO qd_indicator_code_versions (indicator_id, user_id, version_no, name, description, code, created_at)
                VALUES (?, ?, 1, ?, ?, ?, NOW())
                """,
                (local_id, buyer_id, f"{original.get('name') or 'Indicator'} (Fork)", original.get("description") or "", original.get("code") or ""),
            )
            db.commit()
            cur.close()
        return True, "forked", {"local_copy_id": local_id, "source_indicator_id": indicator_id}

    def get_author_published(self, user_id: int, page: int = 1, page_size: int = 20, **_ignored: Any) -> dict[str, Any]:
        offset = (max(1, page) - 1) * page_size
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT COUNT(*) AS count FROM qd_indicator_codes WHERE user_id = ? AND publish_to_community = 1", (user_id,))
            total = int((cur.fetchone() or {}).get("count") or 0)
            cur.execute(
                """
                SELECT id, name, description, code, preview_image, asset_type, review_status,
                       review_note, avg_rating, rating_count, view_count, source_indicator_id,
                       source_script_source_id, source_strategy_id, created_at, updated_at
                FROM qd_indicator_codes WHERE user_id = ? AND publish_to_community = 1
                ORDER BY updated_at DESC LIMIT ? OFFSET ?
                """,
                (user_id, page_size, offset),
            )
            items = [_publication(dict(row)) for row in (cur.fetchall() or [])]
            cur.close()
        return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}

    def get_comments(self, indicator_id: int, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        offset = (max(1, page) - 1) * page_size
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT COUNT(*) AS count FROM qd_indicator_comments WHERE indicator_id = ? AND is_deleted = 0", (indicator_id,))
            total = int((cur.fetchone() or {}).get("count") or 0)
            cur.execute(
                """
                SELECT c.id, c.indicator_id, c.user_id, c.rating, c.content, c.parent_id,
                       c.created_at, c.updated_at, u.username, u.nickname, u.avatar
                FROM qd_indicator_comments c LEFT JOIN qd_users u ON u.id = c.user_id
                WHERE c.indicator_id = ? AND c.is_deleted = 0
                ORDER BY c.created_at DESC LIMIT ? OFFSET ?
                """,
                (indicator_id, page_size, offset),
            )
            items = [dict(row) for row in (cur.fetchall() or [])]
            cur.close()
        return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}

    def add_comment(self, *, user_id: int, indicator_id: int, rating: Any = 5, content: str = "", parent_id: Any = None) -> tuple[bool, str, dict[str, Any]]:
        try:
            score = min(5, max(1, int(rating)))
        except Exception:
            return False, "invalid_rating", {}
        if len(content) > 4000:
            return False, "content_too_long", {}
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT id FROM qd_indicator_codes WHERE id = ? AND publish_to_community = 1", (indicator_id,))
            if not cur.fetchone():
                cur.close()
                return False, "indicator_not_found", {}
            cur.execute(
                "INSERT INTO qd_indicator_comments (indicator_id, user_id, rating, content, parent_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, NOW(), NOW())",
                (indicator_id, user_id, score, content.strip(), parent_id),
            )
            comment_id = int(cur.lastrowid or 0)
            self._refresh_rating(cur, indicator_id)
            db.commit()
            cur.close()
        return True, "comment_saved", {"id": comment_id}

    def update_comment(self, *, user_id: int, comment_id: int, indicator_id: int, rating: Any = 5, content: str = "") -> tuple[bool, str]:
        try:
            score = min(5, max(1, int(rating)))
        except Exception:
            return False, "invalid_rating"
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                "UPDATE qd_indicator_comments SET rating = ?, content = ?, updated_at = NOW() WHERE id = ? AND indicator_id = ? AND user_id = ? AND is_deleted = 0",
                (score, content.strip()[:4000], comment_id, indicator_id, user_id),
            )
            changed = bool(cur.rowcount)
            if changed:
                self._refresh_rating(cur, indicator_id)
                db.commit()
            cur.close()
        return (True, "comment_saved") if changed else (False, "comment_not_found")

    def get_user_comment(self, user_id: int, indicator_id: int) -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                "SELECT id, indicator_id, user_id, rating, content, parent_id, created_at, updated_at FROM qd_indicator_comments WHERE user_id = ? AND indicator_id = ? AND is_deleted = 0 ORDER BY updated_at DESC LIMIT 1",
                (user_id, indicator_id),
            )
            row = cur.fetchone()
            cur.close()
        return dict(row) if row else None

    @staticmethod
    def _refresh_rating(cur, indicator_id: int) -> None:
        cur.execute(
            """
            UPDATE qd_indicator_codes SET
                avg_rating = COALESCE((SELECT AVG(rating) FROM qd_indicator_comments WHERE indicator_id = ? AND is_deleted = 0), 0),
                rating_count = (SELECT COUNT(*) FROM qd_indicator_comments WHERE indicator_id = ? AND is_deleted = 0),
                updated_at = NOW()
            WHERE id = ?
            """,
            (indicator_id, indicator_id, indicator_id),
        )

    def get_pending_indicators(self, page: int = 1, page_size: int = 20, keyword: str | None = None, review_status: str = "pending", **_ignored: Any) -> dict[str, Any]:
        status = review_status if review_status in {"pending", "approved", "rejected"} else "pending"
        where = ["i.publish_to_community = 1", "COALESCE(i.review_status, 'approved') = ?"]
        params: list[Any] = [status]
        if keyword:
            where.append("(i.name ILIKE ? OR i.description ILIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        where_sql = " AND ".join(where)
        offset = (max(1, page) - 1) * page_size
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(f"SELECT COUNT(*) AS count FROM qd_indicator_codes i WHERE {where_sql}", tuple(params))
            total = int((cur.fetchone() or {}).get("count") or 0)
            cur.execute(
                f"""
                SELECT i.id, i.user_id AS author_id, i.name, i.description, i.code, i.preview_image,
                       i.asset_type, i.review_status, i.review_note, i.reviewed_at, i.reviewed_by,
                       i.source_indicator_id, i.source_script_source_id, i.source_strategy_id,
                       i.created_at, u.username AS author_username, u.nickname AS author_nickname
                FROM qd_indicator_codes i LEFT JOIN qd_users u ON u.id = i.user_id
                WHERE {where_sql} ORDER BY i.created_at ASC LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            )
            items = [_publication(dict(row)) for row in (cur.fetchall() or [])]
            cur.close()
        return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}

    def review_indicator(self, *, admin_id: int, indicator_id: int, action: str, note: str = "") -> tuple[bool, str]:
        if action not in {"approve", "reject"}:
            return False, "invalid_review_action"
        status = "approved" if action == "approve" else "rejected"
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                "UPDATE qd_indicator_codes SET review_status = ?, review_note = ?, reviewed_at = NOW(), reviewed_by = ?, updated_at = NOW() WHERE id = ? AND publish_to_community = 1",
                (status, note, admin_id, indicator_id),
            )
            changed = bool(cur.rowcount)
            db.commit()
            cur.close()
        return (True, status) if changed else (False, "indicator_not_found")

    def unpublish_indicator(self, admin_id: int, indicator_id: int, note: str = "") -> tuple[bool, str]:
        return self._unpublish(indicator_id, note)

    def author_unpublish_asset(self, user_id: int, indicator_id: int, note: str = "") -> tuple[bool, str]:
        return self._unpublish(indicator_id, note, user_id=user_id)

    @staticmethod
    def _unpublish(indicator_id: int, note: str, user_id: int | None = None) -> tuple[bool, str]:
        where = "id = ?" + (" AND user_id = ?" if user_id is not None else "")
        params = [indicator_id] + ([user_id] if user_id is not None else [])
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                f"UPDATE qd_indicator_codes SET publish_to_community = 0, review_status = NULL, review_note = ?, reviewed_at = NOW(), updated_at = NOW() WHERE {where}",
                tuple([note, *params]),
            )
            changed = bool(cur.rowcount)
            db.commit()
            cur.close()
        return (True, "unpublished") if changed else (False, "indicator_not_found")

    def admin_delete_indicator(self, admin_id: int, indicator_id: int) -> tuple[bool, str]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("DELETE FROM qd_indicator_codes WHERE id = ?", (indicator_id,))
            changed = bool(cur.rowcount)
            db.commit()
            cur.close()
        return (True, "deleted") if changed else (False, "indicator_not_found")

    def get_review_stats(self) -> dict[str, int]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE review_status = 'pending') AS pending,
                       COUNT(*) FILTER (WHERE review_status = 'approved') AS approved,
                       COUNT(*) FILTER (WHERE review_status = 'rejected') AS rejected
                FROM qd_indicator_codes WHERE publish_to_community = 1
                """
            )
            row = cur.fetchone() or {}
            cur.close()
        return {key: int(row.get(key) or 0) for key in ("pending", "approved", "rejected")}

    def get_indicator_performance(self, indicator_id: int) -> dict[str, Any]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT id, asset_type, source_script_source_id, source_strategy_id FROM qd_indicator_codes WHERE id = ? AND publish_to_community = 1", (indicator_id,))
            row = cur.fetchone()
            if not row:
                cur.close()
                return {"indicator_id": indicator_id, **summarise_backtest_runs([])}
            result = fetch_market_asset_kpis(cur, [dict(row)]).get(indicator_id, summarise_backtest_runs([]))
            cur.close()
        return {"indicator_id": indicator_id, **result}


_library: CommunityLibrary | None = None


def get_community_library() -> CommunityLibrary:
    global _library
    if _library is None:
        _library = CommunityLibrary()
    return _library
