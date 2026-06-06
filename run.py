"""Entry point for the Digital Adjudicator application."""

import os
from app import create_app, socketio

config_name = os.environ.get("FLASK_CONFIG", "development")
app = create_app(config_name)


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=app.config.get("DEBUG", False),
        allow_unsafe_werkzeug=True,
    )
