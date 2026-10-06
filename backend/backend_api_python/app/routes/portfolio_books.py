"""Authenticated portfolio books; user identity is never accepted in a payload."""
from functools import wraps
from flask import g, jsonify, request
from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.utils.auth import login_required
from app.utils.logger import get_logger
from app.services.portfolio.books import BooksService
from app.services.portfolio.ledger_repository import BookNotFound, BookConflict

portfolio_books_blp = Blueprint('portfolio_books', __name__)
logger = get_logger(__name__)
def service(): return BooksService()
def endpoint(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        try: return jsonify({'code': 1, 'data': fn(*args, **kwargs)})
        except BookNotFound: return jsonify({'code': 0, 'message': 'Book or event not found'}), 404
        except BookConflict as exc: return jsonify({'code': 0, 'message': str(exc)}), 409
        except (ValueError, TypeError) as exc: return jsonify({'code': 0, 'message': str(exc)}), 400
        except Exception:
            logger.exception('Portfolio book operation failed')
            return jsonify({'code': 0, 'message': 'Portfolio service unavailable'}), 503
    return login_required(run)
def body():
    if request.content_length and request.content_length > 1200000: raise ValueError('Request too large')
    data = request.get_json(silent=True)
    if not isinstance(data, dict): raise ValueError('JSON object required')
    return data

@portfolio_books_blp.route('/books', methods=['GET', 'POST'])
@endpoint
def books():
    svc = service()
    return svc.repo.list_owned(g.user_id) if request.method == 'GET' else svc.create(g.user_id, body())
@portfolio_books_blp.route('/books/<book_id>/state', methods=['GET'])
@endpoint
def state(book_id): return service().state(g.user_id, book_id)
@portfolio_books_blp.route('/books/<book_id>/entries', methods=['GET', 'POST'])
@endpoint
def entries(book_id):
    if request.method == 'POST': return service().append(g.user_id, book_id, body())
    book = service().state(g.user_id, book_id)
    offset = max(0, int(request.args.get('offset', 0))); limit = min(200, max(1, int(request.args.get('limit', 50))))
    rows = list(reversed(book['events']))
    return {'entries': rows[offset:offset+limit], 'total': len(rows), 'revision': book['revision']}
@portfolio_books_blp.route('/books/<book_id>/entries/<event_id>/revisions', methods=['GET', 'POST'])
@endpoint
def revisions(book_id, event_id):
    return service().repo.revisions(g.user_id, book_id, event_id) if request.method == 'GET' else service().revise(g.user_id, book_id, event_id, body())
@portfolio_books_blp.route('/books/<book_id>/import/<operation>', methods=['POST'])
@endpoint
def csv_import(book_id, operation):
    if operation not in {'preview', 'commit'}: raise ValueError('Invalid operation')
    return getattr(service(), 'csv_' + operation)(g.user_id, book_id, body())
@portfolio_books_blp.route('/books/<book_id>/opening/<operation>', methods=['POST'])
@endpoint
def opening(book_id, operation):
    if operation not in {'preview', 'commit'}: raise ValueError('Invalid operation')
    return getattr(service(), 'opening_' + operation)(g.user_id, book_id, body())

@portfolio_books_blp.route('/books/<book_id>/history', methods=['GET'])
@endpoint
def history(book_id):
    from app.services.portfolio.history import PortfolioHistoryService
    return PortfolioHistoryService().history(g.user_id,book_id,request.args.get('start'),request.args.get('end'),request.args.get('revision'))

@portfolio_books_blp.route('/books/<book_id>/history/refresh', methods=['POST'])
@endpoint
def refresh_history(book_id):
    from app.services.portfolio.history import PortfolioHistoryService
    payload = body()
    return PortfolioHistoryService().refresh(g.user_id,book_id,payload.get('start'),payload.get('end'))

@portfolio_books_blp.route('/books/<book_id>/benchmark', methods=['GET','PUT'])
@endpoint
def benchmark(book_id):
    from app.services.portfolio.benchmarks import BenchmarkService
    svc = BenchmarkService()
    if request.method == 'PUT': return svc.select(g.user_id,book_id,body().get('key'))
    return svc.compare(g.user_id,book_id,request.args.get('key'),request.args.get('start'),request.args.get('end'))
