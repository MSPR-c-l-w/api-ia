"""Re-export from domain layer for backward compatibility.

The catalogue and level ordering are pure domain data and have been moved to
``app.contexts.workout.domain.data.exercises_catalog``. This module re-exports
them so that any existing code still referencing the infrastructure path keeps
working without modification.
"""

from app.contexts.workout.domain.data.exercises_catalog import (  # noqa: F401
    EXERCISE_CATALOG,
    LEVEL_ORDER,
)
