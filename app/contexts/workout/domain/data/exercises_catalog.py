"""Exercise catalogue and level ordering — pure domain data.

These constants depend only on domain value objects (ExerciseDefinition) and
contain no infrastructure concerns. They belong in the domain layer so that
domain services and use cases can reference them without importing infrastructure.
"""

from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)

LEVEL_ORDER: list[str] = ["debutant", "intermediaire", "avance", "athlete"]

EXERCISE_CATALOG: list[ExerciseDefinition] = [
    ExerciseDefinition(
        id="marche-rapide",
        name="marche rapide",
        muscle_group="cardio",
        level="debutant",
        objectives=["perte_de_poids", "endurance", "maintien"],
        equipment=[],
        tags=["cardio", "sans materiel", "faible impact"],
        contraindications=[],
    ),
    ExerciseDefinition(
        id="pont-fessier",
        name="pont fessier",
        muscle_group="fessiers",
        level="debutant",
        objectives=["renforcement", "maintien"],
        equipment=[],
        tags=["renforcement", "faible impact", "sans materiel"],
        contraindications=[],
    ),
    ExerciseDefinition(
        id="gainage",
        name="gainage",
        muscle_group="core",
        level="debutant",
        objectives=["renforcement", "maintien", "performance"],
        equipment=[],
        tags=["core", "sans materiel"],
        contraindications=[],
    ),
    ExerciseDefinition(
        id="squat-pdc",
        name="squats poids du corps",
        muscle_group="jambes",
        level="intermediaire",
        objectives=["renforcement", "prise_de_masse", "performance"],
        equipment=[],
        tags=["jambes", "sans materiel"],
        contraindications=["genou"],
    ),
    ExerciseDefinition(
        id="fentes",
        name="fentes",
        muscle_group="jambes",
        level="intermediaire",
        objectives=["renforcement", "prise_de_masse"],
        equipment=[],
        tags=["jambes", "sans materiel"],
        contraindications=["genou"],
    ),
    ExerciseDefinition(
        id="developpe-couche-halteres",
        name="developpe couche halteres",
        muscle_group="pectoraux",
        level="intermediaire",
        objectives=["prise_de_masse", "renforcement", "performance"],
        equipment=["haltères", "banc"],
        tags=["pectoraux", "haltères"],
        contraindications=["epaule"],
    ),
    ExerciseDefinition(
        id="souleve-terre",
        name="souleve de terre",
        muscle_group="dos",
        level="avance",
        objectives=["prise_de_masse", "performance", "renforcement"],
        equipment=["barre", "haltères"],
        tags=["dos", "force"],
        contraindications=["dos", "genou"],
    ),
    ExerciseDefinition(
        id="burpees",
        name="burpees",
        muscle_group="cardio",
        level="avance",
        objectives=["perte_de_poids", "performance", "endurance"],
        equipment=[],
        tags=["cardio", "intensif", "sans materiel"],
        contraindications=["genou", "dos"],
    ),
    ExerciseDefinition(
        id="traction",
        name="tractions",
        muscle_group="dos",
        level="athlete",
        objectives=["performance", "prise_de_masse", "renforcement"],
        equipment=["barre de traction"],
        tags=["dos", "force"],
        contraindications=["epaule"],
    ),
    ExerciseDefinition(
        id="course-intervalles",
        name="course par intervalles",
        muscle_group="cardio",
        level="athlete",
        objectives=["performance", "endurance", "perte_de_poids"],
        equipment=[],
        tags=["cardio", "intensif"],
        contraindications=["genou"],
    ),
]
