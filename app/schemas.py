from marshmallow import Schema, fields, validate


class HealthResponseSchema(Schema):
    status = fields.String(required=True)
    service = fields.String(required=True)
    version = fields.String(required=True)


class NutritionAnalysisRequestSchema(Schema):
    image_url = fields.Url(required=False, allow_none=True)
    image_base64 = fields.String(required=False, allow_none=True)
    user_goal = fields.String(required=False, allow_none=True)


class NutritionAnalysisResponseSchema(Schema):
    detected_foods = fields.List(fields.Dict(), required=True)
    estimated_calories = fields.Integer(required=True)
    estimated_macros = fields.Dict(required=True)
    feedback = fields.List(fields.String(), required=True)
    model_status = fields.String(required=True)


# ---------------------------------------------------------------------------
# Biometric-based meal recommendation schemas
# ---------------------------------------------------------------------------

_MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]
_DIETARY_CONSTRAINTS = [
    "low_carb", "high_protein", "low_fat",
    "low_sodium", "low_sugar", "vegetarian", "vegan",
]


class RecommendationRequestSchema(Schema):
    """
    Lightweight request: the API fetches biometrics and the meals catalogue
    itself from the backend using the caller's JWT.
    """

    meal_type = fields.String(
        required=False,
        load_default="lunch",
        validate=validate.OneOf(_MEAL_TYPES),
        metadata={"example": "lunch"},
    )
    dietary_constraints = fields.List(
        fields.String(validate=validate.OneOf(_DIETARY_CONSTRAINTS)),
        required=False,
        load_default=list,
        metadata={"example": ["low_sodium"]},
    )
    top_n = fields.Integer(
        required=False,
        load_default=5,
        validate=validate.Range(min=1, max=20),
        metadata={"example": 5},
    )


class NutritionalTargetsSchema(Schema):
    target_calories = fields.Float()
    target_protein_g = fields.Float()
    target_carbs_g = fields.Float()
    target_fat_g = fields.Float()


class MealRecommendationSchema(Schema):
    id = fields.Integer(allow_none=True)
    name = fields.String(allow_none=True)
    category = fields.String(allow_none=True)
    calories_kcal = fields.Float(allow_none=True)
    protein_g = fields.Float(allow_none=True)
    carbohydrates_g = fields.Float(allow_none=True)
    fat_g = fields.Float(allow_none=True)
    fiber_g = fields.Float(allow_none=True)
    meal_type_name = fields.String(allow_none=True)
    picture_url = fields.String(allow_none=True)
    confidence_score = fields.Float()
    constraint_violations = fields.List(fields.String())


class RecommendationResponseSchema(Schema):
    status = fields.String()
    user = fields.Dict()
    nutritional_targets = fields.Nested(NutritionalTargetsSchema)
    recommendations = fields.List(fields.Nested(MealRecommendationSchema))
    model_info = fields.Dict()

