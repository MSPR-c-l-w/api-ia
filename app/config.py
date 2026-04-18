import os


class Config:
    API_TITLE = "HealthAI Coach API"
    API_VERSION = "0.1.0"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/docs"
    OPENAPI_SWAGGER_UI_PATH = "/swagger"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/healthai_coach")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # NestJS backend base URL (no trailing slash)
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")
    # Timeout in seconds for backend HTTP calls
    BACKEND_TIMEOUT = int(os.getenv("BACKEND_TIMEOUT", "10"))

