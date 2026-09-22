"""Native scheduler operations with a deliberately selected host environment."""
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess


class SchedulerError(Exception):
    pass


# Native client configuration stays on the host. Neither the container's PATH
# nor the caller's complete environment is used for a submission.
HOST_ENV = (
    "HOME", "USER", "LOGNAME", "SHELL", "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "LD_LIBRARY_PATH", "SLURM_CONF", "SLURM_CONF_SERVER", "PBS_CONF_FILE",
    "PBS_SERVER", "PBS_DEFAULT", "PBS_EXEC", "KRB5CCNAME", "SSL_CERT_FILE", "SSL_CERT_DIR",
)
RESERVED = set(HOST_ENV) | {
    "LD_PRELOAD", "PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "CDPATH",
    "CUDA_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES",
}


def validate_environment(values):
    if not isinstance(values, dict) or len(values) > 64:
        raise SchedulerError("Job environment must contain at most 64 named values")
    for name, value in values.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
                or name in RESERVED or name.startswith(("WS_", "APPTAINER", "SINGULARITY", "SLURM_", "SBATCH_", "PBS_"))):
            raise SchedulerError("Environment name is reserved or invalid: " + str(name))
        if not isinstance(value, str) or "\0" in value or len(value) > 16384:
            raise SchedulerError("Invalid environment value for " + name)
    return values


def selected_environment(names):
    values = {}
    for name in names:
        if name not in os.environ:
            raise SchedulerError("Environment variable is not set: " + name)
        values[name] = os.environ[name]
    return validate_environment(values)


def validate_script(path, scheduler):
    if not path.is_file():
        raise SchedulerError("Submission script does not exist: " + str(path))
    with path.open("r", encoding="utf-8", errors="strict") as stream:
        for line in stream:
            stripped = line.strip()
            if "\0" in line:
                raise SchedulerError("Submission script must be text")
            if stripped and not stripped.startswith("#"):
                break  # Both schedulers stop scanning directives at the program.
            prefix = "#SBATCH" if scheduler == "slurm" else "#PBS"
            if not stripped.startswith(prefix):
                continue
            try:
                options = shlex.split(stripped[len(prefix):], comments=True)
            except ValueError as exc:
                raise SchedulerError("Invalid scheduler directive: " + str(exc))
            for option in options:
                if scheduler == "slurm" and (option.startswith(("--get-user-env", "--export-file", "--wrap"))
                                             or option in ("--wait", "-W")):
                    raise SchedulerError("Unsupported submission directive: " + option + "; use the native host client for this mode")
                if scheduler == "pbs" and (option.startswith(("-I", "-X", "-C")) or "block=true" in option.lower()):
                    raise SchedulerError("Interactive, blocking, and custom-prefix PBS submission require the native host client")


class Scheduler:
    """One interface used by the host CLI and its optional local connection."""

    def __init__(self, profile, environment, roots=None):
        self.site = profile["site"]
        self.kind = profile["scheduler"]
        self.environment = {key: environment[key] for key in HOST_ENV if key in environment}
        self.environment.setdefault("PATH", os.defpath)
        self.environment.setdefault("USER", getpass.getuser())
        self.environment.setdefault("LOGNAME", self.environment["USER"])
        extra = profile.get("scheduler_env", [])
        if not isinstance(extra, list) or not all(isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in extra):
            raise SchedulerError("Profile scheduler_env must be a list of environment variable names")
        for name in extra:
            if name.startswith(("APPTAINER", "SINGULARITY", "WS_", "SBATCH_")) or name in ("BASH_ENV", "ENV", "LD_PRELOAD", "PBS_DPREFIX"):
                raise SchedulerError("Reserved scheduler_env setting: " + name)
            if name in environment:
                self.environment[name] = environment[name]
        self.roots = [Path(path).expanduser().resolve() for path in roots] if roots is not None else None

    def _path(self, value):
        if not isinstance(value, str) or not value or "\0" in value:
            raise SchedulerError("Expected an absolute host path")
        path = Path(value)
        if not path.is_absolute():
            raise SchedulerError("Expected an absolute host path")
        path = path.resolve()
        if self.roots is not None and not any(path == root or root in path.parents for root in self.roots):
            raise SchedulerError("Submission paths must be inside this session's project or work directory")
        return path

    def request(self, request):
        if not isinstance(request, dict) or set(request) - {"operation", "site", "script", "cwd", "environment", "dry_run"}:
            raise SchedulerError("Invalid scheduler request")
        if request.get("site") != self.site:
            raise SchedulerError("Scheduler connection belongs to site " + self.site)
        operation = request.get("operation")
        if operation not in ("submit", "jobs"):
            raise SchedulerError("Only submit and jobs operations are supported")
        dry_run = request.get("dry_run", False)
        if not isinstance(dry_run, bool):
            raise SchedulerError("dry_run must be a boolean")
        environment = dict(self.environment)
        cwd = None
        if operation == "jobs":
            if set(request) - {"operation", "site", "dry_run"}:
                raise SchedulerError("Queue requests do not accept submission settings")
            user = self.environment["USER"]
            command = (["qstat", "-u", user] if self.kind == "pbs" else
                       ["squeue", "--user", user, "--format=%.18i %.12P %.28j %.10T %.12M %.6D %R"])
        else:
            cwd = self._path(request.get("cwd"))
            if not cwd.is_dir():
                raise SchedulerError("Submission directory does not exist: " + str(cwd))
            script = self._path(request.get("script"))
            validate_script(script, self.kind)
            environment.update(validate_environment(request.get("environment", {})))
            # ALL/-V refer to our selected host environment, never os.environ.
            command = (["qsub", "-V", str(script)] if self.kind == "pbs" else
                       ["sbatch", "--export=ALL", "--", str(script)])
        plan = {"argv": command, "cwd": str(cwd) if cwd else None,
                "environment_names": sorted(environment), "site": self.site}
        if dry_run:
            return {"returncode": 0, "stdout": json.dumps(plan, indent=2) + "\n", "stderr": ""}
        binary = shutil.which(command[0], path=self.environment["PATH"])
        if not binary:
            raise SchedulerError("Host command unavailable: " + command[0] + ". Load the site's scheduler module before starting the workspace.")
        command[0] = binary
        try:
            result = subprocess.run(command, cwd=str(cwd) if cwd else None, env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, timeout=45)
        except subprocess.TimeoutExpired:
            return {"returncode": 124, "stdout": "", "stderr":
                    "Scheduler command timed out. Submission outcome may be uncertain; check your queue before retrying. No automatic retry was made.\n"}
        return {"returncode": result.returncode, "stdout": result.stdout[:524288], "stderr": result.stderr[:524288]}
