import json
import re
from copy import deepcopy
from importlib.resources import files
from itertools import zip_longest
from typing import Any, Callable

import pytest

from mex.common.models import EXTRACTED_MODEL_CLASSES_BY_NAME
from mex.common.transform import dromedary_to_kebab
from mex.common.types.identifier import MEX_ID_PATTERN
from mex.common.types.timestamp import TIMESTAMP_REGEX

SPECIFIED_SCHEMA_PATH = files("mex.model").joinpath("entities")

GENERATED_SCHEMAS = dict(
    sorted(
        {
            name.removeprefix("Extracted"): model.model_json_schema(
                ref_template="/schema/fields/{model}"
            )
            for name, model in EXTRACTED_MODEL_CLASSES_BY_NAME.items()
        }.items()
    )
)
SPECIFIED_SCHEMAS = dict(
    sorted(
        {
            schema["title"].replace(" ", ""): schema
            for file_name in SPECIFIED_SCHEMA_PATH.glob("*.json")
            if (schema := json.load(open(file_name, encoding="utf-8")))
            and not schema["title"].startswith("Concept")
        }.items()
    )
)
ENTITY_TYPES_AND_FIELD_NAMES_BY_FQN = {
    f"{entity_type}.{field_name}": (entity_type, field_name)
    for entity_type, schema in SPECIFIED_SCHEMAS.items()
    for field_name in schema["properties"]
}


def test_entity_types_match_spec() -> None:
    assert list(GENERATED_SCHEMAS) == list(SPECIFIED_SCHEMAS)


@pytest.mark.parametrize(
    ("generated", "specified"),
    zip_longest(GENERATED_SCHEMAS.values(), SPECIFIED_SCHEMAS.values()),
    ids=GENERATED_SCHEMAS,
)
def test_field_names_match_spec(
    generated: dict[str, Any], specified: dict[str, Any]
) -> None:
    generated = {
        k: v for k, v in generated["properties"].items() if k != "$type"
    }  # only in generated models
    assert set(generated) == set(specified["properties"])


@pytest.mark.parametrize(
    ("generated", "specified"),
    zip_longest(GENERATED_SCHEMAS.values(), SPECIFIED_SCHEMAS.values()),
    ids=GENERATED_SCHEMAS,
)
def test_entity_type_matches_class_name(
    generated: dict[str, Any], specified: dict[str, Any]
) -> None:
    assert generated["title"] == generated["properties"]["$type"]["const"]
    assert (
        specified["title"].replace(" ", "") in generated["properties"]["$type"]["const"]
    )


@pytest.mark.parametrize(
    ("generated", "specified"),
    zip_longest(GENERATED_SCHEMAS.values(), SPECIFIED_SCHEMAS.values()),
    ids=GENERATED_SCHEMAS,
)
def test_required_fields_match_spec(
    generated: dict[str, Any], specified: dict[str, Any]
) -> None:
    assert set(generated["required"]) == set(specified["required"])


def deduplicate_dicts(dct: dict[str, Any], key: str) -> None:
    # take a set of dicts and deduplicate them by dumping/loading to json
    dct[key] = [json.loads(s) for s in dict.fromkeys(json.dumps(d) for d in dct[key])]


def dissolve_single_item_lists(dct: dict[str, Any], key: str) -> None:
    # if a list in a dict value has just one item, dissolve it into the parent dict
    if len(dct[key]) == 1 and isinstance(dct[key][0], dict):
        dct.update(dct.pop(key)[0])


def sub_only_text(repl: Callable[[str], str], string: str) -> str:
    # substitute only the textual parts of a string, e.g. leave slashes alone
    return re.sub(r"([a-zA-Z_-]+)", lambda m: repl(m.group(0)), string)


def prepare_field(field: str, obj: list[Any] | dict[str, Any]) -> None:
    # prepare each item in a list (in-place)
    if isinstance(obj, list):
        for item in obj:
            prepare_field(field, item)
        obj[:] = [item for item in obj if item]
        return

    # discard annotations that we can safely ignore
    # (these have no use-case and no implementation plans yet)
    obj.pop("sameAs", None)  # only in spec
    obj.pop("subPropertyOf", None)  # only in spec
    obj.pop("description", None)  # only in model (mostly implementation hints)

    # pop annotations that we don't compare directly but use for other comparisons
    title = obj.pop("title", "")  # only in model (autogenerated by pydantic)
    use_scheme = obj.pop("useScheme", "")  # only in spec (needed to select vocabulary)
    vocabulary = use_scheme.removeprefix("https://mex.rki.de/item/")  # vocabulary name

    # ignore differences between dates and datetimes
    # (we only have `Timestamp` as a date-time implementation, but no type for `date`,
    # but we might/should add that in the future)
    if (
        obj.get("format") in ("date", "date-time")
        or obj.get("pattern") == TIMESTAMP_REGEX
    ):
        obj.pop("examples", None)
        obj.pop("pattern", None)
        obj["format"] = "date-time"

    # align reference paths
    # (the paths to referenced vocabularies and types differ between the models
    # and the specification, so we need to make sure they match before comparing)
    if obj.get("pattern") == MEX_ID_PATTERN:
        obj.pop("pattern")
        obj.pop("type")
        if field in ("identifier", "stableTargetId"):
            obj["$ref"] = "/schema/fields/identifier"
        else:
            obj["$ref"] = "/schema/entities/{}#/identifier".format(
                title.removesuffix("Identifier")
                .removeprefix("Merged")
                .removeprefix("Extracted")
            )

    # align concept/enum annotations
    # (spec uses `useScheme` to specify vocabularies and models use enums)
    if obj.get("$ref") == "/schema/entities/concept#/identifier":
        obj["$ref"] = f"/schema/fields/{vocabulary}"

    # make sure all refs have paths in kebab-case
    # (the models use the class names, whereas the spec uses kebab-case URLs)
    if "$ref" in obj:
        obj["$ref"] = sub_only_text(dromedary_to_kebab, obj["$ref"])

    # recurse into the field definitions for array items
    if obj.get("type") == "array":
        prepare_field(field, obj["items"])

    for quantifier in {"anyOf", "allOf"} & set(obj):
        # prepare choices
        prepare_field(field, obj[quantifier])
        # deduplicate items, used for date/times
        deduplicate_dicts(obj, quantifier)
        # collapse non-choices
        dissolve_single_item_lists(obj, quantifier)


@pytest.mark.parametrize(
    ("entity_type", "field_name"),
    ENTITY_TYPES_AND_FIELD_NAMES_BY_FQN.values(),
    ids=ENTITY_TYPES_AND_FIELD_NAMES_BY_FQN.keys(),
)
def test_field_defs_match_spec(entity_type: str, field_name: str) -> None:
    specified_properties = SPECIFIED_SCHEMAS[entity_type]["properties"]
    generated_properties = GENERATED_SCHEMAS[entity_type]["properties"]
    specified = deepcopy(specified_properties[field_name])
    generated = deepcopy(generated_properties[field_name])

    prepare_field(field_name, specified)
    prepare_field(field_name, generated)

    assert (
        generated == specified
    ), f"""
{entity_type}.{field_name}

specified:
{json.dumps(specified_properties[field_name], indent=4, sort_keys=True)}

generated:
{json.dumps(generated_properties[field_name], indent=4, sort_keys=True)}
"""