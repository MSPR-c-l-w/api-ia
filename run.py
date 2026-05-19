from app.config import settings
from app.main import app

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=settings.port,
        debug=settings.environment == "development",
    )
