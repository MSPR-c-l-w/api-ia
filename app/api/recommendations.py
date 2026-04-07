from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas import RecommendationRequestSchema, RecommendationResponseSchema

blp = Blueprint(
    "recommendations",
    __name__,
    url_prefix="/api/recommendations",
    description="Sport recommendation engine",
)


@blp.route("/workout")
class WorkoutRecommendationResource(MethodView):
    @blp.arguments(RecommendationRequestSchema)
    @blp.response(200, RecommendationResponseSchema)
    def post(self, payload):
        objective = payload["objective"]
        level = payload["level"]
        constraints = payload.get("constraints", [])
        equipment = payload.get("equipment", [])
        duration = payload.get("duration_minutes", 30)

        knee_safe = "mal au genou" in [item.lower() for item in constraints]

        exercises = [
            {
                "name": "marche rapide",
                "duration_minutes": 10,
                "difficulty": level,
                "tags": ["cardio", "sans materiel", "faible impact"],
            },
            {
                "name": "pont fessier",
                "repetitions": "3 x 12",
                "difficulty": level,
                "tags": ["renforcement", "faible impact"],
            },
            {
                "name": "gainage",
                "repetitions": "3 x 30 sec",
                "difficulty": level,
                "tags": ["core", "sans materiel"],
            },
        ]

        if not knee_safe:
            exercises.append(
                {
                    "name": "squats poids du corps",
                    "repetitions": "3 x 10",
                    "difficulty": level,
                    "tags": ["jambes", "sans materiel"],
                }
            )

        return {
            "session_name": f"session_{objective}_{level}",
            "exercises": exercises,
            "rationale": [
                f"Programme genere pour un objectif de {objective}.",
                f"Duree cible: {duration} minutes.",
                f"Contraintes prises en compte: {', '.join(constraints) if constraints else 'aucune'}.",
                f"Materiel disponible: {', '.join(equipment) if equipment else 'aucun'}.",
            ],
            "storage": {
                "engine": "mongodb",
                "status": "not_connected_yet",
            },
        }
