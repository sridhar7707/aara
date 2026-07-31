"""Parses the frozen brand YAML contracts and checks cross-contract version
alignment.

Uses a duplicate-key-detecting loader (not yaml.safe_load) because plain
PyYAML silently keeps the last value on a key collision -- in a "frozen"
governance contract that would hide a real authoring mistake (e.g. a
copy-pasted component block never renamed) instead of failing loudly.
The loader still subclasses yaml.SafeLoader and adds no object-construction
tags, so it remains as safe as safe_load().
"""
import os

import yaml

from .types import ValidationResult

YAML_CONTRACTS = [
    "brand/BRAND_MANIFEST.yaml",
    "brand/VERSION_LOCK.yaml",
    "brand/STATE_MAPPING.yaml",
    "brand/METRIC_CONTRACT.yaml",
    "brand/design_system/COMPONENT_REGISTRY.yaml",
]


def _unique_key_loader():
    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"duplicate key '{key}'")
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return UniqueKeyLoader


def load_contracts():
    """Returns (parsed_contracts: dict[path, obj], ValidationResult).

    Parsing continues past a single bad contract so one broken file doesn't
    hide errors in the rest.
    """
    result = ValidationResult()
    parsed = {}
    for contract in YAML_CONTRACTS:
        if not os.path.exists(contract):
            result.add(contract, 0, "YAML_CONTRACT_MISSING",
                        f"Missing mandatory YAML contract: {contract}", "BLOCK")
            continue
        try:
            with open(contract, "r", encoding="utf-8") as f:
                parsed[contract] = yaml.load(f, Loader=_unique_key_loader())
        except Exception as e:
            result.add(contract, 0, "YAML_INVALID", f"Invalid YAML syntax or structure: {e}", "BLOCK")
    return parsed, result


# Maps each key in VERSION_LOCK.yaml's `contracts:` block to the file and
# version-field path that key is supposed to pin. VERSION_LOCK.yaml declares
# four contracts (manifest, state_mapping, metric_contract,
# component_registry) -- checking only one against the others would leave
# three of them free to drift with no validator catching it.
CONTRACT_VERSION_FIELDS = {
    "manifest": ("brand/BRAND_MANIFEST.yaml", ("brand", "version")),
    "state_mapping": ("brand/STATE_MAPPING.yaml", ("metadata", "version")),
    "metric_contract": ("brand/METRIC_CONTRACT.yaml", ("metadata", "version")),
    "component_registry": ("brand/design_system/COMPONENT_REGISTRY.yaml", ("metadata", "version")),
}


def _get_nested(data, path):
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def validate_version_lock(parsed_contracts):
    result = ValidationResult()
    lock_data = parsed_contracts.get("brand/VERSION_LOCK.yaml")
    if not lock_data:
        return result

    pinned = lock_data.get("contracts") or {}
    for contract_key, pinned_version in pinned.items():
        if contract_key not in CONTRACT_VERSION_FIELDS:
            continue
        file_path, field_path = CONTRACT_VERSION_FIELDS[contract_key]
        contract_data = parsed_contracts.get(file_path)
        if not contract_data:
            continue
        actual_version = _get_nested(contract_data, field_path)
        if actual_version != pinned_version:
            result.add(
                "brand/VERSION_LOCK.yaml", 0, "VERSION_MISMATCH",
                f"contracts.{contract_key} pins '{pinned_version}' but {file_path} "
                f"declares '{actual_version}'",
            )
    return result
