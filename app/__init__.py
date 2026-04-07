from flask import Flask

from app.api import register_blueprints
from app.config import Config
from app.extensions import api


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    api.init_app(app)
    register_blueprints(api)

    return app
