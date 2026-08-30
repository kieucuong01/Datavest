"""
User Management API Routes

Provides endpoints for user CRUD operations, role management, etc.
Only accessible by admin users.
"""
import csv
import json
from io import StringIO
import re
from flask import Response, g, jsonify, request
from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.services.user_preferences import (
    change_user_password,
    delete_chart_template as delete_chart_template_service,
    ensure_chart_templates_column,
    get_notification_settings as get_notification_settings_service,
    list_chart_templates as list_chart_templates_service,
    save_chart_template as save_chart_template_service,
    send_test_notification,
    update_notification_settings as update_notification_settings_service,
)
from app.services.user_service import get_user_service
from app.utils.auth import login_required, admin_required
from app.utils.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)

_PROFILE_TIMEZONE_RE = re.compile(r'^[A-Za-z0-9_/+\-.]+$')


def _parse_positive_int(value) -> int:
    """Parse query-string int; return 0 when missing/invalid."""
    if value is None or value == '':
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ensure_chart_templates_column():
    """Back-compatible wrapper for older route-local callers."""
    ensure_chart_templates_column()

user_blp = Blueprint('user_manage', __name__)


@user_blp.route('/list', methods=['GET'])
@login_required
@admin_required
def list_users():
    """
    List all users (admin only).
    
    Query params:
        page: int (default 1)
        page_size: int (default 20, max 100)
        search: str (optional, search by username/email/nickname/id)
        user_id: int (optional, exact user id filter)
    """
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        search = request.args.get('search', '', type=str)
        user_id = _parse_positive_int(request.args.get('user_id'))
        if user_id <= 0:
            user_id = None
        page_size = min(100, max(1, page_size))
        
        result = get_user_service().list_users(
            page=page, page_size=page_size, search=search, user_id=user_id,
        )
        
        return jsonify({
            'code': 1,
            'msg': 'success',
            'data': result
        })
    except Exception as e:
        logger.error(f"list_users failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/export', methods=['GET'])
@login_required
@admin_required
def export_users():
    """Export all users as an Excel-friendly CSV file (admin only)."""
    try:
        search = request.args.get('search', '', type=str)
        user_id = _parse_positive_int(request.args.get('user_id'))
        if user_id <= 0:
            user_id = None
        users = get_user_service().list_all_users_for_export(search=search, user_id=user_id)

        output = StringIO()
        output.write('\ufeff')
        writer = csv.writer(output)
        writer.writerow([
            'ID', 'Username', 'Email', 'Nickname', 'Role', 'Status',
            'Timezone', 'Register IP',
            'Last Login At', 'Created At', 'Updated At'
        ])

        for user in users:
            writer.writerow([
                user.get('id') or '',
                user.get('username') or '',
                user.get('email') or '',
                user.get('nickname') or '',
                user.get('role') or '',
                user.get('status') or '',
                user.get('timezone') or '',
                user.get('register_ip') or '',
                user.get('last_login_at') or '',
                user.get('created_at') or '',
                user.get('updated_at') or '',
            ])

        filename = 'quantdinger_users_export.csv'
        return Response(
            output.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"export_users failed: {e}", exc_info=True)
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/detail', methods=['GET'])
@login_required
@admin_required
def get_user_detail():
    """Get user detail by ID (admin only)"""
    try:
        user_id = request.args.get('id', type=int)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Missing user id', 'data': None}), 400
        
        user = get_user_service().get_user_by_id(user_id)
        if not user:
            return jsonify({'code': 0, 'msg': 'User not found', 'data': None}), 404
        
        return jsonify({
            'code': 1,
            'msg': 'success',
            'data': user
        })
    except Exception as e:
        logger.error(f"get_user_detail failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    """
    Create a new user (admin only).
    
    Request body:
        username: str (required)
        password: str (required)
        email: str (optional)
        nickname: str (optional)
        role: str (optional, default 'user')
    """
    try:
        data = request.get_json() or {}
        
        user_id = get_user_service().create_user(data)
        
        return jsonify({
            'code': 1,
            'msg': 'User created successfully',
            'data': {'id': user_id}
        })
    except ValueError as e:
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 400
    except Exception as e:
        logger.error(f"create_user failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/update', methods=['PUT'])
@login_required
@admin_required
def update_user():
    """
    Update user information (admin only).
    
    Query params:
        id: int (required)
    
    Request body:
        email: str (optional)
        nickname: str (optional)
        role: str (optional)
        status: str (optional)
    """
    try:
        user_id = request.args.get('id', type=int)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Missing user id', 'data': None}), 400
        
        data = request.get_json() or {}
        
        success = get_user_service().update_user(user_id, data)
        
        if success:
            return jsonify({'code': 1, 'msg': 'User updated successfully', 'data': None})
        else:
            return jsonify({'code': 0, 'msg': 'Update failed', 'data': None}), 400
    except Exception as e:
        logger.error(f"update_user failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/delete', methods=['DELETE'])
@login_required
@admin_required
def delete_user():
    """Delete a user (admin only)"""
    try:
        user_id = request.args.get('id', type=int)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Missing user id', 'data': None}), 400
        
        # Prevent deleting self
        if hasattr(g, 'user_id') and g.user_id == user_id:
            return jsonify({'code': 0, 'msg': 'Cannot delete yourself', 'data': None}), 400
        
        success = get_user_service().delete_user(user_id)
        
        if success:
            return jsonify({'code': 1, 'msg': 'User deleted successfully', 'data': None})
        else:
            return jsonify({'code': 0, 'msg': 'Delete failed', 'data': None}), 400
    except Exception as e:
        logger.error(f"delete_user failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_user_password():
    """
    Reset a user's password (admin only).
    
    Request body:
        user_id: int (required)
        new_password: str (required)
    """
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        new_password = data.get('new_password', '')
        
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Missing user_id', 'data': None}), 400
        
        if len(new_password) < 6:
            return jsonify({'code': 0, 'msg': 'Password must be at least 6 characters', 'data': None}), 400
        
        success = get_user_service().reset_password(user_id, new_password)
        
        if success:
            return jsonify({'code': 1, 'msg': 'Password reset successfully', 'data': None})
        else:
            return jsonify({'code': 0, 'msg': 'Reset failed', 'data': None}), 400
    except ValueError as e:
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 400
    except Exception as e:
        logger.error(f"reset_user_password failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/roles', methods=['GET'])
@login_required
@admin_required
def get_roles():
    """Get available roles and their permissions"""
    service = get_user_service()
    
    roles = []
    for role in service.ROLES:
        roles.append({
            'id': role,
            'name': role.capitalize(),
            'permissions': service.get_user_permissions(role)
        })
    
    return jsonify({
        'code': 1,
        'msg': 'success',
        'data': {'roles': roles}
    })


@user_blp.route('/login-logs', methods=['GET'])
@login_required
def get_login_logs():
    """Paginated account login history (password / email code / OAuth)."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401

        page = int(request.args.get('page') or 1)
        page_size = int(request.args.get('page_size') or 20)

        from app.services.login_notify import list_login_logs

        data = list_login_logs(int(user_id), page=page, page_size=page_size)
        return jsonify({'code': 1, 'msg': 'success', 'data': data})
    except Exception as e:
        logger.error(f"get_login_logs failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """Get current user's profile and notification settings."""
    try:
        import json
        from app.utils.db import get_db_connection
        
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        
        user = get_user_service().get_user_by_id(user_id)
        if not user:
            return jsonify({'code': 0, 'msg': 'User not found', 'data': None}), 404
        
        # Add permissions
        user['permissions'] = get_user_service().get_user_permissions(user.get('role', 'user'))
        
        # Add notification settings
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT notification_settings FROM qd_users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            cur.close()
        
        settings_str = (row.get('notification_settings') if row else '') or ''
        notification_settings = {}
        if settings_str:
            try:
                notification_settings = json.loads(settings_str)
            except Exception:
                notification_settings = {}
        
        # Default values
        if 'default_channels' not in notification_settings:
            notification_settings['default_channels'] = ['browser']
        
        user['notification_settings'] = notification_settings
        
        return jsonify({
            'code': 1,
            'msg': 'success',
            'data': user
        })
    except Exception as e:
        logger.error(f"get_profile failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/profile/update', methods=['PUT'])
@login_required
def update_profile():
    """
    Update current user's profile (limited fields).
    
    Request body:
        nickname: str (optional)
        avatar: str (optional)
        timezone: str (optional, IANA id; empty = follow client)
    
    Note: Email cannot be changed after registration (for security).
          Only admin can change user email via User Management.
    """
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        
        data = request.get_json() or {}
        
        # Only allow updating certain fields for self-service
        # Email is NOT allowed to be changed (security: bound to account)
        allowed = {}
        for field in ['nickname', 'avatar']:
            if field in data:
                allowed[field] = data[field]
        
        if 'timezone' in data:
            tz = (data.get('timezone') or '').strip()
            if tz and (len(tz) > 64 or not _PROFILE_TIMEZONE_RE.match(tz)):
                return jsonify({
                    'code': 0,
                    'msg': 'Invalid timezone identifier',
                    'data': None
                }), 400
            allowed['timezone'] = tz
        
        if not allowed:
            return jsonify({'code': 0, 'msg': 'No valid fields to update', 'data': None}), 400
        
        success = get_user_service().update_user(user_id, allowed)
        
        if success:
            return jsonify({'code': 1, 'msg': 'Profile updated successfully', 'data': None})
        else:
            return jsonify({'code': 0, 'msg': 'Update failed', 'data': None}), 400
    except Exception as e:
        logger.error(f"update_profile failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/mfa/status', methods=['GET'])
@login_required
def get_mfa_status():
    """Get current user's authenticator-app MFA status."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        from app.services.mfa_service import get_mfa_service
        return jsonify({'code': 1, 'msg': 'success', 'data': get_mfa_service().get_status(int(user_id))})
    except Exception as e:
        logger.error(f"get_mfa_status failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/mfa/setup/start', methods=['POST'])
@login_required
def start_mfa_setup():
    """Start authenticator-app binding and return QR code data."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        user = get_user_service().get_user_by_id(int(user_id)) or {}
        label = user.get('email') or user.get('username') or f'user-{user_id}'
        from app.services.mfa_service import get_mfa_service
        data = get_mfa_service().start_setup(int(user_id), label)
        return jsonify({'code': 1, 'msg': 'Scan the QR code with your authenticator app', 'data': data})
    except ValueError as e:
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 400
    except Exception as e:
        logger.error(f"start_mfa_setup failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/mfa/setup/confirm', methods=['POST'])
@login_required
def confirm_mfa_setup():
    """Confirm authenticator-app binding with a 6-digit TOTP code."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        data = request.get_json() or {}
        code = data.get('code') or ''
        from app.services.mfa_service import get_mfa_service
        result = get_mfa_service().confirm_setup(int(user_id), code)
        return jsonify({'code': 1, 'msg': 'MFA enabled successfully', 'data': result})
    except ValueError as e:
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 400
    except Exception as e:
        logger.error(f"confirm_mfa_setup failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/mfa/disable', methods=['POST'])
@login_required
def disable_mfa():
    """Disable current user's authenticator-app MFA after code verification."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        data = request.get_json() or {}
        code = data.get('code') or ''
        from app.services.mfa_service import get_mfa_service
        get_mfa_service().disable(int(user_id), code)
        return jsonify({'code': 1, 'msg': 'MFA disabled successfully', 'data': None})
    except ValueError as e:
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 400
    except Exception as e:
        logger.error(f"disable_mfa failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


@user_blp.route('/notification-settings', methods=['GET'])
@login_required
def get_notification_settings():
    """Get current user's notification settings."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        settings = get_notification_settings_service(int(user_id))
        if settings is None:
            return jsonify({'code': 0, 'msg': 'User not found', 'data': None}), 404
        return jsonify({'code': 1, 'msg': 'success', 'data': settings})
    except Exception as e:
        logger.error(f"get_notification_settings failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
@user_blp.route('/notification-settings', methods=['PUT'])
@login_required
def update_notification_settings():
    """Update current user's notification settings."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        settings = update_notification_settings_service(int(user_id), request.get_json() or {})
        return jsonify({'code': 1, 'msg': 'Notification settings updated', 'data': settings})
    except Exception as e:
        logger.error(f"update_notification_settings failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
@user_blp.route('/chart-templates', methods=['GET'])
@login_required
def get_chart_templates():
    """Get current user's indicator chart templates."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        templates = list_chart_templates_service(int(user_id))
        return jsonify({'code': 1, 'msg': 'success', 'data': templates})
    except Exception as e:
        logger.error(f"get_chart_templates failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
@user_blp.route('/chart-templates', methods=['POST'])
@login_required
def save_chart_template():
    """Create or update a user's indicator chart template."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        ok, msg, saved = save_chart_template_service(int(user_id), request.get_json() or {})
        if not ok:
            return jsonify({'code': 0, 'msg': msg, 'data': None}), 400
        return jsonify({'code': 1, 'msg': msg, 'data': saved})
    except Exception as e:
        logger.error(f"save_chart_template failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
@user_blp.route('/chart-templates', methods=['DELETE'])
@login_required
def delete_chart_template():
    """Delete a user's chart template by id."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        ok, msg, data = delete_chart_template_service(int(user_id), request.args.get('template_id'))
        if not ok:
            return jsonify({'code': 0, 'msg': msg, 'data': None}), 400
        return jsonify({'code': 1, 'msg': msg, 'data': data})
    except Exception as e:
        logger.error(f"delete_chart_template failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
@user_blp.route('/notification-settings/test', methods=['POST'])
@login_required
def test_notification_settings():
    """Send a test notification using saved notification settings."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        accept = (request.headers.get('Accept-Language') or '') + ' ' + (request.headers.get('X-Locale') or '')
        ok, msg, data = send_test_notification(int(user_id), accept)
        return jsonify({'code': 1 if ok else 0, 'msg': msg, 'data': data})
    except Exception as e:
        logger.error(f"test_notification_settings failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
@user_blp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change current user's password."""
    try:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'code': 0, 'msg': 'Not authenticated', 'data': None}), 401
        data = request.get_json() or {}
        ok, msg, status = change_user_password(
            int(user_id),
            data.get('old_password', ''),
            data.get('new_password', ''),
        )
        return jsonify({'code': 1 if ok else 0, 'msg': msg, 'data': None}), status if not ok else 200
    except ValueError as e:
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 400
    except Exception as e:
        logger.error(f"change_password failed: {e}")
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
# ==================== Admin AI Analysis Stats ====================

@user_blp.route('/admin-ai-stats', methods=['GET'])
@login_required
@admin_required
def get_admin_ai_stats():
    """
    Get AI analysis usage statistics across the system (admin only).
    Does NOT expose analysis results, only aggregated counts/stats.

    Query params:
        page: int (default 1)
        page_size: int (default 20, max 100)
        search: str (optional, search by username)
    """
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        search = request.args.get('search', '', type=str).strip()
        page_size = min(100, max(1, page_size))
        offset = (page - 1) * page_size

        with get_db_connection() as db:
            cur = db.cursor()

            # --- Overall summary (from qd_analysis_tasks + qd_analysis_memory) ---
            cur.execute("""
                SELECT
                    COUNT(*) AS total_tasks,
                    COUNT(DISTINCT user_id) AS unique_users,
                    COUNT(DISTINCT symbol) AS unique_symbols,
                    COUNT(DISTINCT market) AS unique_markets
                FROM qd_analysis_tasks
            """)
            task_summary = cur.fetchone() or {}

            memory_summary = {}
            try:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total_memory,
                        COALESCE(SUM(CASE WHEN was_correct = true THEN 1 ELSE 0 END), 0) AS correct_count,
                        COALESCE(SUM(CASE WHEN was_correct = false THEN 1 ELSE 0 END), 0) AS incorrect_count,
                        COALESCE(SUM(CASE WHEN user_feedback = 'helpful' THEN 1 ELSE 0 END), 0) AS helpful_count,
                        COALESCE(SUM(CASE WHEN user_feedback = 'not_helpful' THEN 1 ELSE 0 END), 0) AS not_helpful_count
                    FROM qd_analysis_memory
                """)
                memory_summary = cur.fetchone() or {}
            except Exception as mem_err:
                logger.warning(f"qd_analysis_memory query failed (table/column may not exist): {mem_err}")
                db.rollback()
                cur = db.cursor()  # re-create cursor after rollback
                memory_summary = {}

            copilot_summary = {}
            try:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total_sessions,
                        COUNT(DISTINCT user_id) AS unique_chat_users
                    FROM qd_ai_copilot_sessions
                """)
                copilot_summary = cur.fetchone() or {}
                cur.execute("""
                    SELECT COUNT(*) AS total_messages
                    FROM qd_ai_copilot_messages
                """)
                copilot_message_summary = cur.fetchone() or {}
                copilot_summary['total_messages'] = int(copilot_message_summary.get('total_messages') or 0)
            except Exception as chat_err:
                logger.warning(f"qd_ai_copilot summary query failed (table may not exist): {chat_err}")
                db.rollback()
                cur = db.cursor()
                copilot_summary = {}

            # --- Per-user stats ---
            # Build WHERE clause for user search (applied after JOIN)
            user_where_clause = ""
            user_params = []
            if search:
                user_where_clause = "WHERE (u.username ILIKE ? OR u.nickname ILIKE ? OR u.email ILIKE ?)"
                like_val = f"%{search.strip()}%"
                user_params = [like_val, like_val, like_val]

            # Count distinct users who have analysis records (matching search criteria)
            count_sql = f"""
                SELECT COUNT(DISTINCT t.user_id) AS cnt
                FROM qd_analysis_tasks t
                LEFT JOIN qd_users u ON u.id = t.user_id
                {user_where_clause}
            """
            cur.execute(count_sql, tuple(user_params))
            count_result = cur.fetchone()
            user_total = count_result['cnt'] if count_result else 0

            # Get per-user aggregated stats
            # Important: Filter by user search criteria AFTER grouping, but we need to apply it in WHERE
            # Since we're grouping by user fields, we need to filter before GROUP BY
            stats_sql = f"""
                SELECT
                    t.user_id,
                    u.username,
                    u.nickname,
                    u.email,
                    COUNT(*) AS analysis_count,
                    COUNT(DISTINCT t.symbol) AS symbol_count,
                    COUNT(DISTINCT t.market) AS market_count,
                    MAX(t.created_at) AS last_analysis_at,
                    MIN(t.created_at) AS first_analysis_at
                FROM qd_analysis_tasks t
                LEFT JOIN qd_users u ON u.id = t.user_id
                {user_where_clause}
                GROUP BY t.user_id, u.username, u.nickname, u.email
                ORDER BY analysis_count DESC
                LIMIT ? OFFSET ?
            """
            cur.execute(stats_sql, tuple(user_params) + (page_size, offset))
            user_rows = cur.fetchall() or []

            # Get per-user analysis_memory stats (correct/helpful counts)
            user_ids = [r['user_id'] for r in user_rows if r.get('user_id')]
            memory_stats_map = {}
            copilot_stats_map = {}
            if user_ids:
                try:
                    placeholders = ','.join(['?'] * len(user_ids))
                    cur.execute(
                        f"""
                        SELECT
                            user_id,
                            COUNT(*) AS memory_count,
                            COALESCE(SUM(CASE WHEN was_correct = true THEN 1 ELSE 0 END), 0) AS correct,
                            COALESCE(SUM(CASE WHEN was_correct = false THEN 1 ELSE 0 END), 0) AS incorrect,
                            COALESCE(SUM(CASE WHEN user_feedback = 'helpful' THEN 1 ELSE 0 END), 0) AS helpful,
                            COALESCE(SUM(CASE WHEN user_feedback = 'not_helpful' THEN 1 ELSE 0 END), 0) AS not_helpful
                        FROM qd_analysis_memory
                        WHERE user_id IN ({placeholders})
                        GROUP BY user_id
                        """,
                        tuple(user_ids)
                    )
                    for row in (cur.fetchall() or []):
                        memory_stats_map[row['user_id']] = {
                            'memory_count': row['memory_count'],
                            'correct': row['correct'],
                            'incorrect': row['incorrect'],
                            'helpful': row['helpful'],
                            'not_helpful': row['not_helpful']
                        }
                except Exception as mem_err:
                    logger.warning(f"qd_analysis_memory per-user query failed: {mem_err}")
                    db.rollback()
                    cur = db.cursor()  # re-create cursor after rollback
                    memory_stats_map = {}
                try:
                    placeholders = ','.join(['?'] * len(user_ids))
                    cur.execute(
                        f"""
                        SELECT
                            s.user_id,
                            COUNT(DISTINCT s.id) AS chat_session_count,
                            COUNT(m.id) AS chat_message_count,
                            MAX(s.updated_at) AS last_chat_at
                        FROM qd_ai_copilot_sessions s
                        LEFT JOIN qd_ai_copilot_messages m ON m.session_id = s.id
                        WHERE s.user_id IN ({placeholders})
                        GROUP BY s.user_id
                        """,
                        tuple(user_ids)
                    )
                    for row in (cur.fetchall() or []):
                        copilot_stats_map[row['user_id']] = {
                            'chat_session_count': int(row.get('chat_session_count') or 0),
                            'chat_message_count': int(row.get('chat_message_count') or 0),
                            'last_chat_at': row.get('last_chat_at')
                        }
                except Exception as chat_err:
                    logger.warning(f"qd_ai_copilot per-user query failed: {chat_err}")
                    db.rollback()
                    cur = db.cursor()
                    copilot_stats_map = {}

            # Get recent analysis records (last 50)
            # Ensure we get user info even if user_id is NULL or user doesn't exist
            cur.execute(
                """
                SELECT
                    t.id,
                    t.user_id,
                    COALESCE(u.username, '') AS username,
                    COALESCE(u.nickname, '') AS nickname,
                    COALESCE(u.email, '') AS email,
                    t.market,
                    t.symbol,
                    t.model,
                    t.status,
                    t.created_at,
                    t.completed_at
                FROM qd_analysis_tasks t
                LEFT JOIN qd_users u ON u.id = t.user_id
                WHERE t.user_id IS NOT NULL
                ORDER BY t.created_at DESC
                LIMIT 50
                """
            )
            recent_rows = cur.fetchall() or []

            try:
                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.user_id,
                        COALESCE(u.username, '') AS username,
                        COALESCE(u.nickname, '') AS nickname,
                        COALESCE(u.email, '') AS email,
                        s.title,
                        s.context_market,
                        s.context_symbol,
                        s.created_at,
                        s.updated_at,
                        COUNT(m.id) AS message_count
                    FROM qd_ai_copilot_sessions s
                    LEFT JOIN qd_users u ON u.id = s.user_id
                    LEFT JOIN qd_ai_copilot_messages m ON m.session_id = s.id
                    WHERE s.user_id IS NOT NULL
                    GROUP BY s.id, s.user_id, u.username, u.nickname, u.email,
                             s.title, s.context_market, s.context_symbol,
                             s.created_at, s.updated_at
                    ORDER BY s.updated_at DESC
                    LIMIT 50
                    """
                )
                recent_copilot_rows = cur.fetchall() or []
            except Exception as chat_err:
                logger.warning(f"qd_ai_copilot recent query failed: {chat_err}")
                db.rollback()
                cur = db.cursor()
                recent_copilot_rows = []

            cur.close()

        # Build per-user items
        from app.utils.timeutil import to_utc_iso

        user_items = []
        for row in user_rows:
            uid = row.get('user_id')
            if not uid:  # Skip rows with NULL user_id
                continue

            ms = memory_stats_map.get(uid, {})
            cs = copilot_stats_map.get(uid, {})
            # Server stores naive TIMESTAMP in container TZ; emit UTC ISO so the
            # browser can render it in the user's locale correctly.
            last_at = to_utc_iso(row.get('last_analysis_at'))
            first_at = to_utc_iso(row.get('first_analysis_at'))

            user_items.append({
                'user_id': int(uid),
                'username': str(row.get('username') or ''),
                'nickname': str(row.get('nickname') or ''),
                'email': str(row.get('email') or ''),
                'analysis_count': int(row.get('analysis_count') or 0),
                'symbol_count': int(row.get('symbol_count') or 0),
                'market_count': int(row.get('market_count') or 0),
                'correct': int(ms.get('correct', 0)),
                'incorrect': int(ms.get('incorrect', 0)),
                'helpful': int(ms.get('helpful', 0)),
                'not_helpful': int(ms.get('not_helpful', 0)),
                'last_analysis_at': last_at,
                'first_analysis_at': first_at,
                'chat_session_count': int(cs.get('chat_session_count', 0)),
                'chat_message_count': int(cs.get('chat_message_count', 0)),
                'last_chat_at': to_utc_iso(cs.get('last_chat_at'))
            })

        # Build recent records
        recent_items = []
        for row in recent_rows:
            user_id = row.get('user_id')
            if not user_id:  # Skip rows with NULL user_id
                continue

            created_at = to_utc_iso(row.get('created_at'))
            completed_at = to_utc_iso(row.get('completed_at'))

            recent_items.append({
                'id': int(row.get('id') or 0),
                'user_id': int(user_id),
                'username': str(row.get('username') or ''),
                'nickname': str(row.get('nickname') or ''),
                'email': str(row.get('email') or ''),
                'market': str(row.get('market') or ''),
                'symbol': str(row.get('symbol') or ''),
                'model': str(row.get('model') or ''),
                'status': str(row.get('status') or ''),
                'created_at': created_at,
                'completed_at': completed_at
            })

        recent_copilot_items = []
        for row in recent_copilot_rows:
            user_id = row.get('user_id')
            if not user_id:
                continue
            recent_copilot_items.append({
                'id': int(row.get('id') or 0),
                'user_id': int(user_id),
                'username': str(row.get('username') or ''),
                'nickname': str(row.get('nickname') or ''),
                'email': str(row.get('email') or ''),
                'title': str(row.get('title') or ''),
                'market': str(row.get('context_market') or ''),
                'symbol': str(row.get('context_symbol') or ''),
                'message_count': int(row.get('message_count') or 0),
                'created_at': to_utc_iso(row.get('created_at')),
                'updated_at': to_utc_iso(row.get('updated_at'))
            })

        return jsonify({
            'code': 1,
            'msg': 'success',
            'data': {
                'user_stats': user_items,
                'user_total': user_total,
                'page': page,
                'page_size': page_size,
                'recent': recent_items,
                'recent_copilot': recent_copilot_items,
                'summary': {
                    'total_analyses': int(task_summary.get('total_tasks') or 0),
                    'unique_users': int(task_summary.get('unique_users') or 0),
                    'unique_symbols': int(task_summary.get('unique_symbols') or 0),
                    'unique_markets': int(task_summary.get('unique_markets') or 0),
                    'total_memory': int(memory_summary.get('total_memory') or 0),
                    'correct_count': int(memory_summary.get('correct_count') or 0),
                    'incorrect_count': int(memory_summary.get('incorrect_count') or 0),
                    'helpful_count': int(memory_summary.get('helpful_count') or 0),
                    'not_helpful_count': int(memory_summary.get('not_helpful_count') or 0),
                    'total_copilot_sessions': int(copilot_summary.get('total_sessions') or 0),
                    'total_copilot_messages': int(copilot_summary.get('total_messages') or 0),
                    'unique_chat_users': int(copilot_summary.get('unique_chat_users') or 0)
                }
            }
        })
    except Exception as e:
        logger.error(f"get_admin_ai_stats failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500


# ==================== Admin User Dashboard Stats ====================

@user_blp.route('/admin/stats', methods=['GET'])
@login_required
@admin_required
def get_admin_user_stats():
    """KPI dashboard data for the User Management tab (admin only).

    Returns a single envelope with `summary`, `growth`, `activity`.
    See `app.services.user_stats_service` for the schema of each section.
    """
    try:
        from app.services.user_stats_service import get_user_admin_stats

        data = get_user_admin_stats()
        return jsonify({'code': 1, 'msg': 'success', 'data': data})
    except Exception as e:
        logger.error(f"get_admin_user_stats failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'code': 0, 'msg': str(e), 'data': None}), 500
# openapi-compat: legacy import name
user_bp = user_blp
