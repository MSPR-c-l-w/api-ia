from flask import Flask

from app.routers.health import health_bp
from app.routers.nutrition import nutrition_bp, nutrition_legacy_bp
from app.routers.recommendations import recommendations_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(nutrition_bp)
    app.register_blueprint(nutrition_legacy_bp)
    app.register_blueprint(recommendations_bp)
