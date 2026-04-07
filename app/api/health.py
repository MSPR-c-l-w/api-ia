from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas import HealthResponseSchema

blp = Blueprint("health", __name__, url_prefix="/api/health", description="Health checks")


@blp.route("/")
class HealthResource(MethodView):
    @blp.response(200, HealthResponseSchema)
    def get(self):
        return {
            "status": "ok",
            "service": "healthai-coach-api",
            "version": "0.1.0",
        }
