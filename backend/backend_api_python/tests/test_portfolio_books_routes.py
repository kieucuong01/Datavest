from flask import Flask
from app.routes.portfolio_books import portfolio_books_blp
from tests.test_portfolio_ledger_repository import repository
from app.services.portfolio.books import BooksService
from datetime import datetime, timezone

def test_books_require_login():
    app = Flask(__name__)
    app.register_blueprint(portfolio_books_blp, url_prefix='/api/portfolio')
    client = app.test_client()
    assert client.get('/api/portfolio/books').status_code == 401
    assert client.post('/api/portfolio/books', json={'user_id': 1}).status_code == 401

def test_payload_owner_cannot_override_session(repository, monkeypatch):
    import app.utils.auth as auth
    import app.routes.portfolio_books as routes
    svc = BooksService(repository, clock=lambda: datetime(2026,10,6,tzinfo=timezone.utc))
    book = svc.create(1, {'name':'private', 'currency':'VND'})
    monkeypatch.setattr(auth, 'verify_token', lambda token: {'user_id':2, '_verified_user_role':'user', '_verified_username':'B'})
    monkeypatch.setattr(routes, 'service', lambda: svc)
    app = Flask(__name__); app.register_blueprint(portfolio_books_blp, url_prefix='/api/portfolio')
    client = app.test_client(); headers = {'Authorization':'Bearer fake'}
    assert client.get('/api/portfolio/books/' + book['id'] + '/state', headers=headers).status_code == 404
    assert client.post('/api/portfolio/books/' + book['id'] + '/entries', headers=headers, json={'user_id':1}).status_code == 404
    assert client.get('/api/portfolio/books', headers=headers).json['data'] == []
