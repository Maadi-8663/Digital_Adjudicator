"""Flask application factory for Digital Adjudicator."""

from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect

from config import Config, DevelopmentConfig, ProductionConfig

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO(cors_allowed_origins="*")
csrf = CSRFProtect()


def create_app(config_name: str = "development"):
    app = Flask(__name__, instance_relative_config=True)

    if config_name == "production":
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Ensure instance directory exists
    import os
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, async_mode=app.config.get("SOCKETIO_ASYNC_MODE", "eventlet"))
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to enter the hall."
    login_manager.login_message_category = "error"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Blueprints
    from .auth import auth_bp
    from .admin import admin_bp
    from .judge import judge_bp
    from .participant import participant_bp
    from .public import public_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(judge_bp, url_prefix="/judge")
    app.register_blueprint(participant_bp, url_prefix="/participant")

    # 'index' name kept for backwards-compat in templates that link to it
    @app.route("/index")
    def index():
        return redirect(url_for("public.home"))

    # Create tables on first run
    with app.app_context():
        db.create_all()

    return app
