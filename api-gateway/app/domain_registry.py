"""Domain registry for document storage and Agent Search routing."""
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


DEFAULT_DOMAINS = [
    {
        "domain": "operations",
        "display_name": "Operations",
        "bucket": "aiops-gc-poc-pilot-operations-r8lp73",
        "prefix": "docs/",
        "data_store_id": "",
        "engine_id": "",
        "serving_config": "",
    },
    {
        "domain": "compliance",
        "display_name": "Compliance",
        "bucket": "aiops-gc-poc-pilot-compliance-hz2xah",
        "prefix": "docs/",
        "data_store_id": "",
        "engine_id": "",
        "serving_config": "",
    },
    {
        "domain": "finance",
        "display_name": "Finance",
        "bucket": "aiops-gc-poc-pilot-finance-cw2x1h",
        "prefix": "docs/",
        "data_store_id": "",
        "engine_id": "",
        "serving_config": "",
    },
]


def _default_registry() -> dict[str, Any]:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "aiops-gc-poc-pilot")
    location = os.getenv("DISCOVERY_ENGINE_LOCATION", "global")
    staging_bucket = os.getenv("GCS_BUCKET_NAME", "aiops-gc-poc-pilot-uploads-8aukzz")

    return {
        "project_id": project_id,
        "project_number": os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER", ""),
        "location": location,
        "staging": {
            "bucket": staging_bucket,
            "prefix": "docs/",
            "archive_prefix": "archive/",
        },
        "domains": DEFAULT_DOMAINS,
    }


def _load_registry_file() -> Optional[dict[str, Any]]:
    config_json = os.getenv("DOC_DOMAIN_REGISTRY_JSON")
    if config_json:
        return json.loads(config_json)

    config_path = os.getenv("DOC_DOMAIN_REGISTRY_PATH", "/run/secrets/domain-registry.json")
    path = Path(config_path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip("/")
    return f"{prefix}/" if prefix else ""


def _normalize_registry(registry: dict[str, Any]) -> dict[str, Any]:
    normalized = _default_registry()
    normalized.update({key: value for key, value in registry.items() if key != "domains"})

    staging = normalized.get("staging") or {}
    staging["prefix"] = _normalize_prefix(staging.get("prefix", "docs/"))
    staging["archive_prefix"] = _normalize_prefix(staging.get("archive_prefix", "archive/"))
    normalized["staging"] = staging

    domains = []
    for domain in registry.get("domains", normalized["domains"]):
        item = dict(domain)
        item["domain"] = item["domain"].lower()
        item["prefix"] = _normalize_prefix(item.get("prefix", "docs/"))
        if item.get("engine_id"):
            resource_project = normalized.get("project_number") or normalized["project_id"]
            location = normalized["location"]
            engine_id = item["engine_id"]
            item["serving_config"] = (
                f"projects/{resource_project}/locations/{location}/collections/"
                f"default_collection/engines/{engine_id}/servingConfigs/default_search"
            )
        domains.append(item)
    normalized["domains"] = domains
    return normalized


@lru_cache(maxsize=1)
def get_domain_registry() -> dict[str, Any]:
    """Load and cache the document domain registry."""
    registry = _load_registry_file() or _default_registry()
    return _normalize_registry(registry)


def list_domains() -> list[dict[str, Any]]:
    """Return configured document domains."""
    return get_domain_registry()["domains"]


def get_domain(domain: str) -> dict[str, Any]:
    """Resolve a configured domain by ID."""
    domain_key = domain.lower()
    for item in list_domains():
        if item["domain"] == domain_key:
            return item
    raise KeyError(f"Unknown document domain: {domain}")


def get_query_domains(domain: str) -> list[dict[str, Any]]:
    """Resolve one query domain or all queryable domains."""
    if domain.lower() == "all":
        return [
            item for item in list_domains()
            if item.get("serving_config") or item.get("engine_id")
        ]
    item = get_domain(domain)
    if not item.get("serving_config") and not item.get("engine_id"):
        return []
    return [item]
