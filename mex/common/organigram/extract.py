import json
from typing import Generator, Iterable

from mex.common.logging import watch
from mex.common.models import ExtractedOrganizationalUnit
from mex.common.organigram.models import OrganigramUnit
from mex.common.settings import BaseSettings
from mex.common.types import Identifier, Text


@watch
def extract_oranigram_units() -> Generator[OrganigramUnit, None, None]:
    """Extract organizational units from the organigram JSON file.

    Settings:
        organigram_path: Resolved path to the organigram file

    Returns:
        Generator for organigram units
    """
    settings = BaseSettings.get()
    with open(settings.organigram_path, "r") as fh:
        for raw in json.load(fh):
            yield OrganigramUnit.parse_obj(raw)


def get_synonyms(
    extracted_unit: ExtractedOrganizationalUnit,
) -> Generator[Text, None, None]:
    """Generate synonyms for a unit using its name fields.

    Args:
        extracted_unit: Extracted organizational unit

    Returns:
        Generator with (possibly duplicate) synonyms
    """
    yield from extracted_unit.name
    yield from extracted_unit.shortName
    yield from extracted_unit.alternativeName


def get_unit_merged_ids_by_synonyms(
    extracted_units: Iterable[ExtractedOrganizationalUnit],
) -> dict[str, Identifier]:
    """Return a mapping from unit alt_label and label to their merged IDs.

    There will be multiple entries per unit mapping to the same merged ID.

    Args:
        extracted_units: Iterable of extracted units

    Returns:
        Mapping from unit synonyms to stableTargetIds
    """
    return {
        synonym.value: extracted_unit.stableTargetId
        for extracted_unit in extracted_units
        for synonym in get_synonyms(extracted_unit)
    }


def get_unit_merged_ids_by_emails(
    extracted_units: Iterable[ExtractedOrganizationalUnit],
) -> dict[str, Identifier]:
    """Return a mapping from unit emails to their merged IDs.

    There may be multiple emails per unit mapping to the same merged ID.

    Args:
        extracted_units: Iterable of extracted units

    Returns:
        Mapping from lowercased `email` to stableTargetIds
    """
    return {
        email.lower(): extracted_unit.stableTargetId
        for extracted_unit in extracted_units
        for email in extracted_unit.email
    }