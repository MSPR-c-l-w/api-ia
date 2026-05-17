from pydantic import BaseModel, Field


class ExerciseDefinition(BaseModel):
    """Exercice du catalogue utilisé par le moteur de scoring."""

    id: str
    name: str
    muscle_group: str
    level: str = Field(
        description="debutant | intermediaire | avance | athlete",
    )
    objectives: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(
        default_factory=list,
        description="Matériel requis ; vide = sans matériel",
    )
    tags: list[str] = Field(default_factory=list)
    contraindications: list[str] = Field(
        default_factory=list,
        description="Ex. genou, dos, epaule",
    )
