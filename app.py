"""E-Commerce Business Intelligence Dashboard - Flask application entry point."""
from __future__ import annotations

import logging

from flask import Flask, jsonify

from config import Config
from db import Database
from routes import ApiError, bp
from seed_data import seed

log = logging.getLogger(__name__)


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    db = Database.from_config(app.config)
    try:
        db.init_schema()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not set up the '{app.config['DB_ENGINE']}' database: {exc}\n"
            "Check your .env file (host, user, password, database name) and that the "
            "MySQL server is running. For a zero-setup demo use DB_ENGINE=sqlite."
        ) from exc
    if app.config["AUTO_SEED"] and db.scalar("SELECT COUNT(*) FROM orders") == 0:
        counts = seed(db)
        log.warning("Empty database detected - loaded sample data: %s", counts)
    app.extensions["db"] = db
    app.register_blueprint(bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return jsonify(error=err.message), err.status

    @app.errorhandler(404)
    def handle_404(_err):
        return jsonify(error="Resource not found."), 404

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("Unhandled error")
        return jsonify(error="Internal server error. Check the server log for details."), 500

    return app


if __name__ == "__main__":
    import os

    application = create_app()
    # HOST=0.0.0.0 is set automatically inside GitHub Codespaces / containers
    application.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
                    debug=application.config["DEBUG"])
