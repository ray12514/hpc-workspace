"""Read the existing Inspector YAML in the image; never probe or activate software."""
import json
import sys

MAX_BYTES = 4 * 1024 * 1024


class ProfileError(ValueError):
    pass


# Only these documented facts cross into workspace configuration. Unknown fields
# are ignored; absent optional facts remain absent. A one-element list is an
# array schema, ("map", spec) is a named inventory, and ("nullable", spec) allows null.
NAMED_PREFIX = {"name": str, "version": str, "prefix": str}
COMPILER = dict(NAMED_PREFIX, provider_family=str, platform_family=str,
                languages=[str], modules=[str], compilers={"c": str, "cxx": str, "fortran": str})
MPI = dict(NAMED_PREFIX, provider_family=str, platform_family=str, modules=[str],
           compiler=str, compatibility={"compilers": [str]},
           flavors=("map", {"prefix": str, "modules": [str]}))
TOOLKIT = {"version": str, "module": str, "prefix": str,
           "spack_components": [{"package": str, "prefix": str}]}
GPU = {"vendor": str, "driver_version": str, "toolkit_ceiling": str,
       "arch_target": str, "cuda_compat_available": bool}
STAGE = {"path": str, "visibility": str, "writable": bool, "free_gb": int,
         "free_inodes": int, "mount_opts": [str], "throughput_class": str}
EXTERNAL = dict(NAMED_PREFIX, provider_family=str, variants=str, modules=[str],
                detection={"confidence": str, "source": str},
                capabilities={"mpi_launch": {"command": str, "plugins": [str],
                                             "development_interfaces": [str]}})
FACTS = {
    "system": {"name": str, "family": str, "description": str},
    "os": {"name": str, "major": int, "minor": int, "glibc": str},
    "fabric": {"type": str, "generation": str, "drivers": [NAMED_PREFIX], "userspace": [NAMED_PREFIX]},
    "modules_system": {"tool": str, "version": str},
    "compiler_providers": [COMPILER], "mpi_providers": [MPI],
    "gpu_toolkit_modules": {"rocm": [TOOLKIT], "cudatoolkit": [TOOLKIT], "nvhpc": [TOOLKIT]},
    "system_externals": [EXTERNAL],
    "filesystem": {"install_tree_candidates": [{"path": str, "type": str,
                    "locks_honored": bool, "free_gb": int}],
                   "source_cache_candidate": str, "buildcache_candidate": str},
    "node_types": ("map", {"role": str, "description": str,
                    "cpu": {"detected": str, "preferred": str, "alternates": [str]},
                    "gpu": ("nullable", GPU), "build_stage": [STAGE]}),
}


def project(value, spec, path="profile"):
    if isinstance(spec, tuple):
        if spec[0] == "nullable":
            return None if value is None else project(value, spec[1], path)
        if not isinstance(value, dict):
            raise ProfileError(path + " must be a mapping")
        return {project(key, str, path): project(item, spec[1], path + "." + key)
                for key, item in value.items()}
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            raise ProfileError(path + " must be a mapping")
        return {key: project(value[key], child, path + "." + key)
                for key, child in spec.items() if key in value}
    if isinstance(spec, list):
        if not isinstance(value, list):
            raise ProfileError(path + " must be a list")
        return [project(item, spec[0], path + "[]") for item in value]
    if type(value) is not spec:
        raise ProfileError(path + " must be " + spec.__name__)
    if spec is str and (len(value) > 16384 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ProfileError(path + " contains control characters or is too long")
    return value


def normalize(data):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ProfileError("Expected an Inspector profile with schema_version: 1")
    facts = project(data, FACTS)
    name = facts.get("system", {}).get("name", "")
    if not name.strip() or len(name) > 256:
        raise ProfileError("profile.system.name must be a nonempty name of at most 256 characters")
    candidates = sorted({entry["name"] for entry in facts.get("system_externals", [])
                         if entry.get("name") in ("pbs", "slurm")})
    return {"profile_schema_version": 1, "facts": facts, "scheduler_candidates": candidates}


def read_profile(path):
    import yaml  # Image dependency only; normal host startup does not import YAML.

    class Loader(yaml.SafeLoader):
        count = 0
        depth = 0

        def compose_node(self, parent, index):
            self.count += 1
            self.depth += 1
            try:
                if self.count > 50000 or self.depth > 48:
                    raise ProfileError("Profile is too large or deeply nested")
                return super().compose_node(parent, index)
            finally:
                self.depth -= 1

        def construct_mapping(self, node, deep=False):
            self.flatten_mapping(node)
            result = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str) or key in result:
                    raise ProfileError("Profile mapping keys must be unique strings")
                result[key] = self.construct_object(value_node, deep=deep)
            return result

    with open(path, "rb") as stream:
        contents = stream.read(MAX_BYTES + 1)
    if len(contents) > MAX_BYTES:
        raise ProfileError("Profile exceeds the 4 MiB import limit")
    try:
        data = yaml.load(contents.decode("utf-8-sig"), Loader=Loader)
        # Reject cycles/alias expansion before projecting even unused fields.
        budget = [50000, MAX_BYTES]

        def visit(item, ancestors, depth=0):
            budget[0] -= 1
            if isinstance(item, str):
                budget[1] -= len(item.encode("utf-8"))
            if budget[0] < 0 or budget[1] < 0 or depth > 48 or id(item) in ancestors:
                raise ProfileError("Profile contains recursive or excessive aliases")
            if isinstance(item, (dict, list)):
                children = item.values() if isinstance(item, dict) else item
                for child in children:
                    visit(child, ancestors | {id(item)}, depth + 1)
        visit(data, set())
        return normalize(data)
    except (yaml.YAMLError, UnicodeError, RecursionError) as exc:
        raise ProfileError("Cannot parse Inspector YAML: " + str(exc))


if __name__ == "__main__":
    try:
        print(json.dumps(read_profile(sys.argv[1])))
    except (ProfileError, OSError, IndexError) as exc:
        print("Inspector import: " + str(exc), file=sys.stderr)
        sys.exit(2)
