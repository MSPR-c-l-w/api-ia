"""
Biometric-based meal recommendation endpoint.

Flow:
  1. Extract the caller's JWT from the Authorization header.
  2. Call the NestJS backend to fetch:
       - /auth/me          → User (date_of_birth, gender, height)
       - /health-profile/me → HealthProfile (weight, bmi, activity_level, calories_target)
       - /nutrition        → full meals catalogue (all pages)
  3. Feed real biometrics into the ML model → predicted nutritional targets.
  4. Score and rank meals from the catalogue.
  5. Return top-N recommendations.

POST /api/recommendations/predict  (Bearer token required)
POST /api/recommendations/train    (re-train model on demand)
"""

from flask import current_app, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from app.ml.predictor import predict_nutritional_targets, reload_model, score_and_rank_meals
from app.ml.train import MEAL_CALORIE_RATIOS, MODEL_PATH, train_and_save_model
from app.schemas import (
    RecommendationRequestSchema,
    RecommendationResponseSchema,
)
from app.services.backend_client import (
    BackendError,
    compute_age,
    fetch_health_profile,
    fetch_nutrition_catalogue,
    fetch_user_profile,
    normalise_activity_level,
    normalise_gender,
)

blp = Blueprint(
    "recommendations",
    __name__,
    url_prefix="/api/recommendations",
    description="Biometric-based meal recommendation engine",
)

_DEFAULT_ACTIVITY = "moderately_active"


def _extract_jwt() -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(401, message="Missing or malformed Authorization header (Bearer token required)")
    return auth_header[len("Bearer "):]


@blp.route("/predict")
class Predict(MethodView):
    @blp.arguments(RecommendationRequestSchema)
    @blp.response(200, RecommendationResponseSchema)
    def post(self, payload):
        """
        Return ranked meal recommendations for the authenticated user.

        The endpoint fetches the user's real biometrics and the full nutrition
        catalogue from the NestJS backend, then uses a trained Random Forest
        model (Mifflin-St Jeor) to compute per-meal nutritional targets and
        rank the catalogue accordingly.

        Requires a valid **Bearer JWT** (same token used with the backend).
        """
        if current_app.config.get("ENVIRONMENT") == "offline":
            return {
                "status": "offline",
                "user": {},
                "nutritional_targets": {},
                "recommendations": [],
                "model_info": {"mode": "degraded", "reason": "offline mode"},
            }

        jwt_token = _extract_jwt()

        # ------------------------------------------------------------------
        # 1. Fetch real data from the NestJS backend
        # ------------------------------------------------------------------
        try:
            user = fetch_user_profile(jwt_token)
            health = fetch_health_profile(jwt_token)
            meals_catalogue = fetch_nutrition_catalogue(jwt_token)
        except BackendError as exc:
            abort(exc.status_code, message=str(exc))

        if not meals_catalogue:
            abort(422, message="Nutrition catalogue is empty — seed the backend first")

        # ------------------------------------------------------------------
        # 2. Extract and validate biometrics
        # ------------------------------------------------------------------
        age = compute_age(user.get("date_of_birth"))
        gender = normalise_gender(user.get("gender"))
        height_cm = user.get("height")
        weight_kg = health.get("weight")
        bmi = health.get("bmi")
        activity_level = normalise_activity_level(health.get("physical_activity_level"))
        daily_calories_target = health.get("daily_calories_target")
        meal_type = payload["meal_type"]

        missing = []
        if age is None:
            missing.append("date_of_birth (user profile)")
        if weight_kg is None:
            missing.append("weight (health profile)")
        if height_cm is None:
            missing.append("height (user profile)")
        if missing:
            abort(
                422,
                message=(
                    f"Incomplete biometrics — please complete your profile. "
                    f"Missing: {', '.join(missing)}"
                ),
            )

        # ------------------------------------------------------------------
        # 3. Predict optimal nutritional targets via ML model
        # ------------------------------------------------------------------
        targets = predict_nutritional_targets(
            age=age,
            weight_kg=float(weight_kg),
            height_cm=float(height_cm),
            gender=gender,
            physical_activity_level=activity_level,
            meal_type=meal_type,
            bmi=float(bmi) if bmi else None,
        )

        # Override calorie target if the user set one manually in their profile
        if daily_calories_target:
            meal_ratio = MEAL_CALORIE_RATIOS.get(meal_type, 0.35)
            targets["target_calories"] = round(float(daily_calories_target) * meal_ratio, 1)

        # ------------------------------------------------------------------
        # 4. Score and rank meals
        # ------------------------------------------------------------------
        recommendations = score_and_rank_meals(
            meals=meals_catalogue,
            targets=targets,
            dietary_constraints=payload.get("dietary_constraints", []),
            top_n=payload["top_n"],
        )

        return {
            "status": "success",
            "user": {
                "age": age,
                "gender": gender,
                "weight_kg": weight_kg,
                "height_cm": height_cm,
                "bmi": bmi,
                "physical_activity_level": activity_level,
                "daily_calories_target": daily_calories_target,
            },
            "nutritional_targets": targets,
            "recommendations": recommendations,
            "model_info": {
                "algorithm": "RandomForestRegressor + weighted Euclidean scoring",
                "training_data": "Mifflin-St Jeor synthetic dataset (6 000 samples)",
                "model_path": MODEL_PATH,
            },
        }


@blp.route("/train")
class Train(MethodView):
    @blp.response(200)
    def post(self):
        """Re-train the biometric model and reload it into memory."""
        train_and_save_model(MODEL_PATH)
        reload_model()
        return {"status": "success", "message": "Model retrained and reloaded"}

