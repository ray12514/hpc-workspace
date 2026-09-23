"""Host-side workspace operations. Commands are argv lists, never shell input."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import posixpath
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile

from scheduler import Scheduler, SchedulerError, selected_environment
from job_bridge import HostJobs, call as call_host_jobs
import configuration
from inspector import MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]
FORWARD = (
    "TERM", "COLORTERM", "LANG", "LC_ALL", "TZ", "SSH_AUTH_SOCK",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
    "CUDA_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES",
    "GPU_DEVICE_ORDINAL", "SLURM_JOB_ID", "PBS_JOBID", "WS_INSTALL_SKILLS",
    "WS_COLOR", "NO_COLOR", "WS_GIT_PROMPT",
)


class WorkspaceError(Exception):
    pass


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (ValueError, OSError) as exc:
        raise WorkspaceError("Cannot read {}: {}".format(path, exc))


def profile(site):
    return configuration.resolve(ROOT, site, configuration.read())


def current_profile(args):
    return args.resolved_profile if hasattr(args, "resolved_profile") else profile(args.site)


def require_scheduler(data):
    if data.get("scheduler") not in ("pbs", "slurm"):
        raise WorkspaceError("No single scheduler is configured. Set it once with 'ws init --scheduler pbs' or '--scheduler slurm'.")
    return data


def import_profile(source, args):
    """Parse a fixed local snapshot with the image's YAML helper, not Inspector."""
    image = selected_image(args)
    source = Path(source).expanduser().resolve()
    with source.open("rb") as stream:
        contents = stream.read(MAX_BYTES + 1)
    if len(contents) > MAX_BYTES:
        raise WorkspaceError("Inspector profile exceeds the 4 MiB import limit")
    runtime = shutil.which("apptainer")
    if not runtime:
        raise WorkspaceError("Load Apptainer to import YAML. Ordinary startup uses the saved configuration without parsing YAML.")
    with tempfile.TemporaryDirectory(prefix="ws-profile-") as temporary:
        snapshot = Path(temporary) / "profile.yaml"
        snapshot.write_bytes(contents)
        snapshot.chmod(0o600)
        command = [runtime, "exec", "--cleanenv", "--no-eval", "--no-mount", "home,cwd,hostfs",
                   "--bind", bind_spec(snapshot, "/tmp/ws-profile.yaml", "ro"), "--pwd", "/tmp",
                   image["path"], "/usr/bin/python3", "-I", "/opt/workspace/lib/inspector.py", "/tmp/ws-profile.yaml"]
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("APPTAINER", "SINGULARITY"))}
        try:
            result = subprocess.run(command, env=environment, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise WorkspaceError("Inspector profile import timed out; saved configuration was not changed")
        if result.returncode:
            raise WorkspaceError("Profile import failed (use a workspace image with the import helper):\n" + result.stderr[-4000:])
        if len(result.stdout) > MAX_BYTES:
            raise WorkspaceError("Imported profile exceeds the 4 MiB configuration limit")
        imported = json.loads(result.stdout)
    if not isinstance(imported, dict):
        raise WorkspaceError("Invalid response from the profile import helper")
    imported.update(source=str(source), sha256=hashlib.sha256(contents).hexdigest(),
                    imported_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    return imported


def configuration_candidate(args, source=None):
    previous = args.saved_configuration
    same_site = previous and (not args.explicit_site or args.explicit_site == previous["site"])
    candidate = json.loads(json.dumps(previous)) if same_site else {
        "schema_version": 1, "site": args.site, "overrides": {}}
    if source:
        imported = import_profile(source, args)
        name = imported.get("facts", {}).get("system", {}).get("name")
        if not isinstance(name, str):
            raise WorkspaceError("Imported profile is missing system.name")
        prior = candidate.get("inspector")
        if prior and prior["facts"]["system"]["name"] != name:
            raise WorkspaceError("Profile system.name changed; configuration and state were preserved. Use 'ws init --site NEW_KEY --profile FILE' for a different system.")
        if not same_site and not args.explicit_site:
            candidate["site"] = configuration.key_for_name(name)
            # Preserve a workspace already used before a profile was available.
            # Prefer the target's existing state if that system was used before.
            prior_state = state_path(args)
            target_state = prior_state.parent / candidate["site"]
            if not args.state_dir and prior_state.exists() and not target_state.exists():
                candidate["state_site"] = args.site
        candidate["inspector"] = imported
    if getattr(args, "scheduler", None):
        candidate.setdefault("overrides", {})["scheduler"] = args.scheduler
    configuration.validate(candidate)
    return candidate


def configure(args):
    source = args.profile
    if args.action == "refresh":
        if not args.saved_configuration or not args.saved_configuration.get("inspector"):
            raise WorkspaceError("No imported profile to refresh. Use 'ws init --profile FILE --image FILE.sif' first.")
        if args.explicit_site and args.explicit_site != args.saved_configuration["site"]:
            raise WorkspaceError("Refresh must target the configured site")
        source = source or args.saved_configuration["inspector"]["source"]
    elif not source and not (args.saved_configuration or {}).get("inspector"):
        source = os.environ.get("WS_INSPECTOR_PROFILE")
    candidate = configuration_candidate(args, source)
    changes = configuration.changed_fields(args.saved_configuration or {}, candidate)
    data = configuration.resolve(ROOT, candidate["site"], candidate)
    report = {"site": candidate["site"], "scheduler": data["scheduler"], "changed_fields": changes,
              "configuration": str(configuration.directory() / "config.json"), "dry_run": args.dry_run}
    if not args.dry_run:
        configuration.write(candidate, args.saved_configuration)
    print(json.dumps(report, indent=2))
    return 0


def prepare(args):
    args.explicit_site = args.site
    if in_container():
        args.site = configuration.site_key(args.site or os.environ.get("WS_SITE") or "local")
        return
    args.saved_configuration = configuration.read()
    args.site = configuration.site_key(args.site or (args.saved_configuration or {}).get("site") or "local")
    args.resolved_profile = configuration.resolve(ROOT, args.site, args.saved_configuration)
    if args.action not in ("enter", "session"):
        return
    same_site = not args.saved_configuration or args.site == args.saved_configuration["site"]
    source = args.profile or (os.environ.get("WS_INSPECTOR_PROFILE") if same_site else None)
    imported = args.resolved_profile.get("inspector")
    if source and not imported:
        reader_image = selected_image(args)["path"]
        candidate = configuration_candidate(args, source)
        args.site = candidate["site"]
        args.resolved_profile = configuration.resolve(ROOT, args.site, candidate)
        # Keep the SIF found before the system name was imported for this entry.
        if not args.image:
            args.image = reader_image
        if not args.dry_run:
            configuration.write(candidate, args.saved_configuration)
        print("{} workspace settings for {} from Inspector YAML. Use 'ws refresh' to update them.".format(
              "Would import" if args.dry_run else "Imported", args.site), file=sys.stderr)
    elif args.profile and imported and str(Path(args.profile).expanduser().resolve()) != imported["source"]:
        raise WorkspaceError("A profile is already imported. Use 'ws refresh --profile FILE' to change its source.")


def state_path(args):
    if getattr(args, "state_dir", None):
        return Path(args.state_dir).expanduser().resolve()
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    site = getattr(args, "resolved_profile", {}).get("state_site", args.site)
    return (base / "hpc-workspace" / site).resolve()


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_record(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix != ".sif":
        raise WorkspaceError("Image must be an existing .sif file: " + str(path))
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def selected_image(args):
    if getattr(args, "image", None):
        return image_record(args.image)
    path = state_path(args) / "selection.json"
    if not path.exists():
        raise WorkspaceError("Select an image with 'ws use', or pass --image FILE.sif.")
    record = load_json(path)["current"]
    actual = image_record(record["path"])
    if any(actual[key] != record[key] for key in ("size", "mtime_ns")):
        raise WorkspaceError("Selected image changed. Revalidate it with 'ws use'.")
    return record


def allocation(data):
    if data.get("scheduler") not in ("pbs", "slurm"):
        jobs = [os.environ[key] for key in ("PBS_JOBID", "SLURM_JOB_ID") if os.environ.get(key)]
        return jobs[0] if len(jobs) == 1 else None
    key = "PBS_JOBID" if data["scheduler"] == "pbs" else "SLURM_JOB_ID"
    return os.environ.get(key) or None


def bind_spec(source, destination=None, mode="rw"):
    source = Path(source).expanduser().resolve()
    if not source.exists():
        raise WorkspaceError("Bind source does not exist: " + str(source))
    destination = str(destination or source)
    if not destination.startswith("/") or mode not in ("ro", "rw"):
        raise WorkspaceError("Bind destination must be absolute and mode ro or rw")
    if any(c in str(source) + destination for c in (",", ":", "\n", "\r")):
        raise WorkspaceError("Bind paths cannot contain commas, colons or newlines")
    return "{}:{}:{}".format(source, destination, mode)


def container_plan(args, create_state=False, job_directory=None):
    data = current_profile(args)
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise WorkspaceError("Project directory does not exist: " + str(project))
    image = selected_image(args)
    job = allocation(data)
    if args.compute and not job:
        raise WorkspaceError("Compute mode requires an existing {} allocation.".format(data["scheduler"] or "scheduler"))
    if args.gpu != "none" and not job:
        raise WorkspaceError("GPU access requires an existing allocation.")
    if args.host_jobs and (os.environ.get("SLURM_JOB_ID") or os.environ.get("PBS_JOBID")):
        raise WorkspaceError("Start --host-jobs on a login host, outside a compute allocation.")
    if args.host_jobs:
        require_scheduler(data)
    state = state_path(args)
    if create_state:
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
    runtime = shutil.which("apptainer") or "apptainer"
    home_mount = bind_spec(Path.home(), str(Path.home()))
    # An explicit bind alone does not set HOME: Apptainer otherwise uses the
    # account database even when the launching shell selected another home.
    command = [runtime, "exec", "--cleanenv", "--no-eval", "--no-mount", "home,cwd,hostfs",
               "--home", home_mount.rsplit(":", 1)[0]]
    mounts = [home_mount, bind_spec(project)]
    # A dry-run describes the state bind without creating directories.
    if not state.exists() and not create_state:
        if any(c in str(state) for c in (",", ":", "\n", "\r")):
            raise WorkspaceError("Unsupported character in state path")
        mounts.append(str(state) + ":/workspace-state:rw")
    else:
        mounts.append(bind_spec(state, "/workspace-state"))
    if args.work:
        mounts.append(bind_spec(args.work))
    for item in data["binds"]:
        if not isinstance(item, dict) or "source" not in item or set(item) - {"source", "destination", "mode"}:
            raise WorkspaceError("Invalid profile bind")
        destination = posixpath.normpath(item.get("destination", item["source"]))
        if destination in ("/", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/opt", "/opt/workspace", "/workspace-state", "/workspace-host") or destination.startswith(("/opt/workspace/", "/workspace-state/", "/workspace-host/")):
            raise WorkspaceError("Profile bind would replace a protected image path: " + destination)
        mounts.append(bind_spec(item["source"], destination, item.get("mode", "ro")))
    agent_socket = os.environ.get("SSH_AUTH_SOCK")
    if agent_socket and Path(agent_socket).exists():
        mounts.append(bind_spec(agent_socket, agent_socket))
    if job_directory is not None:
        mounts.append(bind_spec(job_directory, "/workspace-host"))
    for mount in dict.fromkeys(mounts):
        command += ["--bind", mount]
    if args.gpu != "none":
        command.append("--nv" if args.gpu == "cuda" else "--rocm")
    command += ["--pwd", str(project), image["path"], "/opt/workspace/bin/container-entry"]
    requested = list(args.command)
    if requested and requested[0] == "--":
        requested.pop(0)
    command += requested
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("APPTAINER_", "APPTAINERENV_", "SINGULARITY_", "SINGULARITYENV_"))}
    for key in FORWARD:
        if key in os.environ:
            environment["APPTAINERENV_" + key] = os.environ[key]
    environment.update({
        "APPTAINERENV_WS_SITE": args.site,
        "APPTAINERENV_WS_CONTEXT": "compute" if job else "login",
        "APPTAINERENV_WS_PROJECT": str(project),
        "APPTAINERENV_WS_HOSTNAME": socket.gethostname(),
        "APPTAINERENV_WS_GPU_MODE": args.gpu,
    })
    if job_directory is not None:
        environment["APPTAINERENV_WS_HOST_JOBS_SOCKET"] = "/workspace-host/scheduler.sock"
    return command, environment


def print_plan(command, environment=None):
    data = {"argv": command}
    if environment is not None:
        data["forwarded_environment_names"] = sorted(k[13:] for k in environment if k.startswith("APPTAINERENV_"))
    print(json.dumps(data, indent=2))


def execute(command, environment=None):
    if not shutil.which(command[0]):
        raise WorkspaceError("Command unavailable: {}. Load the site's module first.".format(command[0]))
    return subprocess.call(command, env=environment)


def enter(args):
    if not args.dry_run and platform.system() != "Linux":
        raise WorkspaceError("Apptainer entry runs on Linux. Use the Docker smoke test on this host.")
    command, environment = container_plan(args, create_state=not args.dry_run)
    if args.dry_run:
        print_plan(command, environment)
        if args.host_jobs:
            print("A temporary, same-user host scheduler socket will be bound at /workspace-host when started.", file=sys.stderr)
        return 0
    if args.host_jobs:
        roots = [args.project] + ([args.work] if args.work else [])
        scheduler = Scheduler(require_scheduler(current_profile(args)), os.environ, roots=roots)
        with HostJobs(scheduler) as bridge:
            command, environment = container_plan(args, create_state=True, job_directory=bridge.directory)
            return execute(command, environment)
    return execute(command, environment)


def in_container():
    return os.environ.get("WS_CONTAINER") == "1" or bool(os.environ.get("APPTAINER_CONTAINER"))


def scheduler_operation(args):
    request = {"operation": args.action, "site": args.site, "dry_run": args.dry_run}
    if args.action == "submit":
        request.update(script=str(Path(args.script).expanduser().resolve()),
                       cwd=str(Path(args.cwd).expanduser().resolve()),
                       environment=selected_environment(args.env))
    if in_container():
        connection = os.environ.get("WS_HOST_JOBS_SOCKET")
        if not connection:
            raise WorkspaceError("No host scheduler connection. Use the host window, or enter with --host-jobs on a login host.")
        result = call_host_jobs(connection, request)
    else:
        result = Scheduler(require_scheduler(current_profile(args)), os.environ).request(request)
    sys.stdout.write(result["stdout"])
    sys.stderr.write(result["stderr"])
    return result["returncode"]


def probe(command):
    if not shutil.which(command[0]):
        return {"available": False}
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=15)
        return {"available": True, "exit_code": result.returncode,
                "stdout": result.stdout[:16000].strip(), "stderr": result.stderr[:2000].strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "error": str(exc)}


def doctor(args):
    data = current_profile(args)
    result = {"schema_version": 1, "site": args.site, "hostname": socket.gethostname(),
              "platform": platform.system(), "architecture": platform.machine(),
              "kernel": platform.release(), "scheduler": data["scheduler"],
              "allocation": allocation(data), "modules": os.environ.get("LOADEDMODULES", "").split(":") if os.environ.get("LOADEDMODULES") else [],
              "mpi_status": data["mpi_status"], "project": str(Path(args.project).resolve()),
              "state_directory": str(state_path(args)), "checks": {}}
    result["configuration"] = {"path": str(configuration.directory() / "config.json"),
                               "inspector": data.get("inspector")}
    os_release = Path("/etc/os-release")
    if os_release.is_file():
        result["os_release"] = os_release.read_text()
    commands = {"apptainer": ["apptainer", "version"], "tmux": ["tmux", "-V"],
                "glibc": ["getconf", "GNU_LIBC_VERSION"], "python": ["python3", "--version"]}
    if data["scheduler"] == "slurm":
        commands["scheduler"] = ["srun", "--version"]
        commands["mpi_plugins"] = ["srun", "--mpi=list"]
    elif data["scheduler"] == "pbs":
        commands["scheduler"] = ["qstat", "--version"]
    if args.gpu_inventory:
        if not allocation(data):
            raise WorkspaceError("Run --gpu-inventory inside an allocated GPU job.")
        commands.update({
            "nvidia": ["nvidia-smi", "--query-gpu=name,driver_version,pci.bus_id", "--format=csv,noheader"],
            "amd_smi": ["amd-smi", "version"],
            "rocm_smi": ["rocm-smi", "--showproductname", "--showdriverversion"],
            "rocminfo": ["rocminfo"],
        })
    for name, command in commands.items():
        result["checks"][name] = probe(command)
    try:
        result["selected_image"] = selected_image(args)
    except (WorkspaceError, KeyError) as exc:
        result["selected_image"] = {"error": str(exc)}
    print(json.dumps(result, indent=2))
    return 0


def select_release(args):
    state = state_path(args)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = state / "selection.json"
    with (state / "selection.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prior = load_json(path) if path.exists() else {}
        if args.action == "rollback":
            record = prior.get("previous")
            if not record:
                raise WorkspaceError("No previous image selection is recorded.")
            actual = image_record(record["path"])
            if checksum(actual["path"]) != record["sha256"]:
                raise WorkspaceError("Previous image checksum no longer matches.")
            record.update(actual)
        else:
            record = image_record(args.image)
            if len(args.sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in args.sha256):
                raise WorkspaceError("--sha256 must contain 64 hexadecimal characters")
            record["sha256"] = checksum(record["path"])
            if record["sha256"] != args.sha256.lower():
                raise WorkspaceError("Image checksum mismatch; selection was not changed.")
        if prior.get("current") == record:
            print("Already selected: " + record["path"])
            return 0
        selection = {"schema_version": 1, "current": record, "previous": prior.get("current")}
        fd, temporary = tempfile.mkstemp(prefix="selection-", dir=str(state))
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(selection, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, str(path))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print("Selected: " + record["path"])
    return 0


def session(args):
    data = current_profile(args)
    if args.host_jobs:
        require_scheduler(data)
    if allocation(data) or os.environ.get("PBS_JOBID") or os.environ.get("SLURM_JOB_ID"):
        raise WorkspaceError("Start the persistent session on a login host, outside a compute allocation.")
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise WorkspaceError("Project directory does not exist: " + str(project))
    image = selected_image(args)
    name = "ws-{}-{}".format(args.site, hashlib.sha256(str(project).encode()).hexdigest()[:10])
    tmux = ["tmux", "-L", name, "-f", str(ROOT / "image/config/tmux/tmux.conf")]
    environment = dict(os.environ)
    environment["WS_ROOT"] = str(ROOT)
    environment["WS_SITE"] = args.site
    environment["WS_CONFIG_DIR"] = str(configuration.directory())
    environment["WS_SESSION_STATE"] = str(state_path(args) / "tmux" / socket.gethostname() / name)
    entry = [str(ROOT / "bin/ws"), "enter", "--site", args.site, "--project", str(project),
             "--image", image["path"], "--state-dir", str(state_path(args))]
    if args.work:
        entry += ["--work", args.work]
    if args.host_jobs:
        entry += ["--host-jobs"]
    editor = "exec " + " ".join(shlex.quote(x) for x in entry + ["--", "nvim"])
    launch = tmux + ["new-session", "-d", "-s", name, "-n", "editor", "-c", str(project), editor]
    if args.dry_run:
        print_plan(launch)
        return 0
    if platform.system() != "Linux":
        raise WorkspaceError("Persistent cluster sessions run on Linux login hosts.")
    if not shutil.which("tmux"):
        raise WorkspaceError("Host tmux is required. Load its site module before starting a session.")
    Path(environment["WS_SESSION_STATE"]).mkdir(parents=True, exist_ok=True, mode=0o700)
    found = subprocess.call(tmux + ["has-session", "-t", name], env=environment,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    if not found:
        subprocess.check_call(launch, env=environment)
        subprocess.check_call(tmux + ["set-option", "-t", name, "@workspace-image", image["path"]], env=environment)
        subprocess.check_call(tmux + ["new-window", "-t", name, "-n", "host", "-c", str(project)], env=environment)
        subprocess.check_call(tmux + ["new-window", "-t", name, "-n", "workspace", "-c", str(project),
                                      "exec " + " ".join(shlex.quote(x) for x in entry)], env=environment)
        subprocess.check_call(tmux + ["select-window", "-t", name + ":editor"], env=environment)
    current_image = subprocess.check_output(tmux + ["show-option", "-v", "-t", name, "@workspace-image"],
                                            env=environment, universal_newlines=True).strip()
    print("Session {} on {} (image {})".format(name, socket.gethostname(), current_image))
    if current_image != image["path"]:
        print("The existing session keeps its original image. New image selections apply to new sessions.")
    if args.detach:
        return 0
    return subprocess.call(tmux + ["attach-session", "-t", name], env=environment)


def parser():
    result = argparse.ArgumentParser(description="A consistent development workspace on HPC clusters.")
    sub = result.add_subparsers(dest="action")
    for name, handler in (("enter", enter), ("jobs", scheduler_operation), ("submit", scheduler_operation), ("doctor", doctor),
                          ("use", select_release), ("rollback", select_release), ("session", session),
                          ("init", configure), ("refresh", configure)):
        command = sub.add_parser(name)
        command.set_defaults(handler=handler)
        command.add_argument("--site", help="Override the configured system key for this command")
        if name not in ("jobs", "submit"):
            command.add_argument("--state-dir", help="Override this site's persistent workspace-state directory")
        if name in ("enter", "doctor", "session"):
            command.add_argument("--project", default=os.getcwd())
        if name in ("enter", "doctor", "session", "init", "refresh"):
            command.add_argument("--image", help="Explicit SIF; otherwise use the selected image")
        if name in ("enter", "jobs", "submit", "session", "init", "refresh"):
            command.add_argument("--dry-run", action="store_true", help="Preview without saving settings, entering the workspace, or submitting jobs; new YAML is parsed")
        if name in ("enter", "session", "init", "refresh"):
            command.add_argument("--profile", help="Existing local Inspector YAML (initial setup or explicit refresh)")
        if name in ("init", "refresh"):
            command.add_argument("--scheduler", choices=("pbs", "slurm"), help="Save an explicit scheduler default")
        if name in ("enter", "session"):
            command.add_argument("--work", help="Additional work directory mounted at its native path")
            command.add_argument("--host-jobs", action="store_true", help="Enable submit/jobs from this login-host container session")
        if name == "submit":
            command.add_argument("--cwd", default=os.getcwd(), help="Host submission working directory (default: current directory)")
            command.add_argument("--env", action="append", default=[], metavar="NAME", help="Explicitly pass a job environment variable; put resource settings in the script")
            command.add_argument("script", help="Existing PBS or Slurm batch script")
        if name == "enter":
            command.add_argument("--compute", action="store_true", help="Require an existing scheduler allocation")
            command.add_argument("--gpu", choices=("none", "cuda", "rocm"), default="none", help="Device passthrough; does not install a GPU toolkit")
            command.add_argument("command", nargs=argparse.REMAINDER)
        if name == "doctor":
            command.add_argument("--gpu-inventory", action="store_true")
        if name == "use":
            command.add_argument("image")
            command.add_argument("--sha256", required=True)
        if name == "session":
            command.add_argument("--detach", action="store_true")
    return result


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    if not getattr(args, "handler", None):
        arguments.print_help()
        return 0
    try:
        if in_container() and args.action not in ("jobs", "submit"):
            raise WorkspaceError("Run 'ws " + args.action + "' on the host. Inside the workspace use submit or jobs.")
        prepare(args)
        return args.handler(args)
    except (WorkspaceError, SchedulerError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print("ws: " + str(exc), file=sys.stderr)
        return 2
