"""Private workspace defaults, independent of the optional Inspector source file."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from inspector import normalize, ProfileError


class ConfigurationError(ValueError):
    pass


def directory():
    if os.environ.get("WS_CONFIG_DIR"):
        return Path(os.environ["WS_CONFIG_DIR"]).expanduser().resolve()
    return (Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "hpc-workspace").resolve()


def site_key(name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name):
        raise ConfigurationError("Site keys must use 1–64 lowercase letters, digits, underscores or hyphens")
    return name


def key_for_name(name):
    value = name.lower()
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        return value
    return "system-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def read():
    path = directory() / "config.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        validate(data)
        return data
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ConfigurationError("Cannot read {}: {}".format(path, exc))


def validate(data):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ConfigurationError("Unsupported workspace configuration version")
    site_key(data.get("site"))
    site_key(data.get("state_site", data["site"]))
    overrides = data.get("overrides", {})
    if not isinstance(overrides, dict) or set(overrides) - {"scheduler", "binds", "scheduler_env"}:
        raise ConfigurationError("Configuration overrides support scheduler, binds, and scheduler_env")
    if "scheduler" in overrides and overrides["scheduler"] not in ("pbs", "slurm"):
        raise ConfigurationError("Scheduler must be pbs or slurm")
    imported = data.get("inspector")
    if imported is not None:
        if not isinstance(imported, dict) or type(imported.get("profile_schema_version")) is not int or imported["profile_schema_version"] != 1:
            raise ConfigurationError("Invalid saved Inspector import")
        facts = imported.get("facts")
        try:
            normalized = normalize(dict(facts, schema_version=1))
        except (ProfileError, TypeError, ValueError) as exc:
            raise ConfigurationError("Invalid imported facts: " + str(exc))
        if normalized["scheduler_candidates"] != imported.get("scheduler_candidates"):
            raise ConfigurationError("Saved scheduler candidates do not match imported facts")
        for key in ("source", "sha256", "imported_at"):
            if not isinstance(imported.get(key), str):
                raise ConfigurationError("Missing Inspector import metadata: " + key)
    return data


def write(data, previous):
    validate(data)
    folder = directory()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(folder / "config.lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if read() != previous:
            raise ConfigurationError("Workspace configuration changed during import; retry the operation")
        fd, temporary = tempfile.mkstemp(prefix="config-", dir=str(folder))
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(data, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, str(folder / "config.json"))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def resolve(root, site=None, saved=None):
    site = site_key(site or (saved or {}).get("site") or "local")
    path = root / "profiles" / (site + ".json")
    data = json.loads(path.read_text()) if path.exists() else {
        "schema_version": 1, "site": site, "scheduler": None, "binds": [],
        "mpi_status": "not configured; local integration and validation pending",
    }
    if data.get("schema_version") != 1 or data.get("site") != site:
        raise ConfigurationError("Invalid profile for " + site)
    if saved and saved["site"] == site:
        data["state_site"] = saved.get("state_site", site)
        imported = saved.get("inspector")
        if imported:
            candidates = imported["scheduler_candidates"]
            if candidates:
                data["scheduler"] = candidates[0] if len(candidates) == 1 else None
            data["inspector"] = imported
        data.update(saved.get("overrides", {}))
    override = root / "profiles" / (site + ".local.json")
    if override.exists():
        extra = json.loads(override.read_text())
        if not isinstance(extra, dict) or set(extra) - {"binds", "scheduler_env", "scheduler"}:
            raise ConfigurationError("Local profiles support binds, scheduler_env, and scheduler")
        data.update(extra)
    if data.get("scheduler") not in (None, "pbs", "slurm") or not isinstance(data.get("binds"), list):
        raise ConfigurationError("Invalid scheduler or binds configuration")
    return data


def changed_fields(before, after, prefix=""):
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            result.extend(changed_fields(before.get(key), after.get(key), prefix + ("." if prefix else "") + key))
        return result
    return [] if before == after else [prefix]
