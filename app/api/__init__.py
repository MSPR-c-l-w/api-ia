from flask_smorest import Api

from app.api.health import blp as health_blueprint
from app.api.nutrition import blp as nutrition_blueprint
from app.api.recommendations import blp as recommendations_blueprint


def register_blueprints(api: Api) -> None:
    api.register_blueprint(health_blueprint)
    api.register_blueprint(nutrition_blueprint)
    api.register_blueprint(recommendations_blueprint)
