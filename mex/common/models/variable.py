from pydantic import Field

from mex.common.models.base import BaseModel
from mex.common.models.extracted_data import ExtractedData
from mex.common.models.merged_item import MergedItem
from mex.common.types import (
    ResourceID,
    Text,
    VariableGroupID,
    VariableID,
    VocabularyEnum,
)


class DataType(VocabularyEnum):
    """The type of the single piece of information within a datum."""

    __vocabulary__ = "data-type"


class BaseVariable(BaseModel):
    """A single piece of information within a resource."""

    stableTargetId: VariableID
    belongsTo: list[VariableGroupID] = []
    codingSystem: str | None = Field(
        None,
        examples=["SF-36 Version 1"],
    )
    dataType: DataType | None = Field(
        None,
        examples=["https://mex.rki.de/concept/data-type-1"],
    )
    description: list[Text] = []
    label: list[Text] = Field(
        ...,
        examples=[{"language": "de", "value": "Mehrere Treppenabsätze steigen"}],
        min_items=1,
    )
    usedIn: list[ResourceID] = Field(..., min_items=1)
    valueSet: list[str] = Field(
        [],
        examples=[
            "Ja, stark eingeschränkt",
            "Ja, etwas eingeschränkt",
            "Nein, überhaupt nicht eingeschränkt",
        ],
    )


class ExtractedVariable(BaseVariable, ExtractedData):
    """An automatically extracted metadata set describing a variable."""


class MergedVariable(BaseVariable, MergedItem):
    """The result of merging all extracted data and rules for a variable."""