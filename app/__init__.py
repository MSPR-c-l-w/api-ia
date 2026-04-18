from flask import Flask
from flask_cors import CORS # <--- Import à ajouter
from app.api import register_blueprints
from app.config import Config
from app.extensions import api

def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, resources={r"/*": {"origins": "*"}}) 

    api.init_app(app)
    register_blueprints(api)

    return app