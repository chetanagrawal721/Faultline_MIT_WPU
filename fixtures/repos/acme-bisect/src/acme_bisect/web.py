"""HTTP helpers. Flask 2.2.2 imports werkzeug.urls.url_quote when it is imported, and Werkzeug 3 removed it."""
from flask import Flask, jsonify


def make_app() -> Flask:
    app = Flask(__name__)

    @app.get("/ping")
    def ping():
        return jsonify({"ok": True})

    return app
