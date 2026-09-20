from pydantic import BaseModel, Field


class PersonaRef(BaseModel):
    onboardingCompleted: bool
    personaVersion: int
    personaStoragePath: str


class Persona(BaseModel):
    version: int
    content: str
    storagePath: str


class PersonaUpdate(BaseModel):
    content: str = Field(min_length=1)
    expectedVersion: int = Field(ge=0)
