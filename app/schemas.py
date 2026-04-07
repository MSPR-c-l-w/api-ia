from marshmallow import Schema, fields


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


class RecommendationRequestSchema(Schema):
    objective = fields.String(required=True)
    level = fields.String(required=True)
    constraints = fields.List(fields.String(), required=False, load_default=list)
    equipment = fields.List(fields.String(), required=False, load_default=list)
    duration_minutes = fields.Integer(required=False, load_default=30)


class RecommendationResponseSchema(Schema):
    session_name = fields.String(required=True)
    exercises = fields.List(fields.Dict(), required=True)
    rationale = fields.List(fields.String(), required=True)
    storage = fields.Dict(required=True)
