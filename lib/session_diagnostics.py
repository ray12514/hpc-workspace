"""Read kernel metadata without entering containers or contacting tmux servers.

No process arguments, environments, file contents, or workspace configuration
are collected. Never dereference the executable, cwd, root, or fd symlinks.
The separate sampling process lets the native controller report a partial
result if even a kernel metadata read blocks. Python 3.6+; standard library only.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

INTERESTING = re.compile(r'tmux|squashfuse|fuse-overlay|apptainer|starter|cray|clang|cc1|'
                         r'make|ninja|codex|nvim|^python', re.I)
MAX_PROCESSES = 160
MAX_THREADS = 256
TRACE = False


def progress(value):
    if TRACE:
        print(json.dumps({'probe': value}), flush=True)


def unescape(value):
    return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)


def read(path, limit=131072):
    try:
        with Path(path).open(encoding='utf-8', errors='replace') as stream:
            value = stream.read(limit + 1)
        return value[:limit], 'truncated' if len(value) > limit else None
    except OSError as error:
        return '', error.strerror or type(error).__name__


def link(path):
    try:
        return os.readlink(str(path))
    except OSError:
        return None


def fields(text):
    return dict(line.split(':', 1) for line in text.splitlines() if ':' in line)


def stat(text):
    """comm may contain spaces and closing parentheses; the last ')' ends it."""
    before, after = text.rsplit(')', 1)
    values = after.split()
    return dict(pid=int(before.split('(', 1)[0]), name=before.split('(', 1)[1],
                state=values[0], ppid=int(values[1]), ticks=int(values[11]) + int(values[12]),
                start=values[19], threads=int(values[17]))


def mounts(text):
    result = []
    for line in text.splitlines():
        try:
            left, right = line.split(' - ', 1)
            left, right = left.split(), right.split()
            result.append(dict(device=left[2], root=unescape(left[3]), path=unescape(left[4]),
                               type=right[0], controllers=right[2].split(',')))
        except (ValueError, IndexError):
            continue
    return result


def cpu_directories(text, mount_rows):
    """Resolve CPU controller paths and every visible ancestor, including v1."""
    result = set()
    for line in text.splitlines():
        try:
            _, controllers, group = line.split(':', 2)
        except ValueError:
            continue
        version = 'cgroup2' if not controllers else 'cgroup'
        if controllers and 'cpu' not in controllers.split(','):
            continue
        for mount in mount_rows:
            if mount['type'] != version or (controllers and 'cpu' not in mount['controllers']):
                continue
            root, base = mount['root'].rstrip('/'), mount['path'].rstrip('/') or '/'
            if root and group != root and not group.startswith(root + '/'):
                continue
            relative = group[len(root):].lstrip('/')
            directory = os.path.normpath(os.path.join(base, relative))
            if directory != base and not directory.startswith(base.rstrip('/') + '/'):
                continue
            while True:
                result.add(directory)
                if directory == base:
                    break
                directory = os.path.dirname(directory)
    return sorted(result)


def cpu_records(directories):
    result = {}
    for directory in sorted(directories):
        row = {}
        for filename in ('cpu.max', 'cpu.cfs_quota_us', 'cpu.cfs_period_us', 'cpu.stat'):
            text, error = read(Path(directory) / filename, 4096)
            if not error:
                row[filename] = text.strip()
        if row:
            result[directory] = row
    return result


def own_processes(proc, uid):
    rows = []
    for directory in proc.iterdir():
        if not directory.name.isdigit():
            continue
        try:
            if directory.stat().st_uid != uid:
                continue
            progress('process metadata ' + directory.name)
            row = stat(read(directory / 'stat')[0])
            status = fields(read(directory / 'status')[0])
            if int(status.get('Uid', '-1').split()[1]) != uid:
                continue
            row['allowed_cpus'] = status.get('Cpus_allowed_list', '(unavailable)').strip()
            row['wchan'] = read(directory / 'wchan', 256)[0].strip() or '(unavailable)'
            row['cgroup'] = read(directory / 'cgroup', 16384)[0].strip()
            rows.append(row)
        except (OSError, ValueError, IndexError):
            continue  # Processes may finish during collection.
    return rows


def priority(row):
    return (0 if 'tmux' in row['name'].lower() else
            1 if row['state'] == 'D' else
            2 if 'fuse' in row['name'].lower() else 3, row['pid'])


def detail(proc, row):
    directory = proc / str(row['pid'])
    progress('process links and threads ' + str(row['pid']))
    result = dict(executable=link(directory / 'exe'), cwd=link(directory / 'cwd'),
                  mount_namespace=link(directory / 'ns/mnt'), blocked_threads=[])
    try:
        tasks = sorted((directory / 'task').iterdir(), key=lambda path: int(path.name))
    except OSError:
        tasks = []
    result['threads_truncated'] = len(tasks) > MAX_THREADS
    for task in tasks[:MAX_THREADS]:
        try:
            current = stat(read(task / 'stat')[0])
        except (ValueError, IndexError):
            continue
        if current['state'] == 'D':
            progress('blocked thread stack ' + str(task))
            stack, error = read(task / 'stack', 4096)
            result['blocked_threads'].append(dict(tid=current['pid'],
                wchan=read(task / 'wchan', 256)[0].strip(), stack=stack.strip(), stack_error=error))
    if row['state'] == 'D' or 'tmux' in row['name'].lower() or 'fuse' in row['name'].lower():
        progress('mount table ' + str(row['pid']))
        text, error = read(directory / 'mountinfo')
        result['mountinfo_error'] = error
        # No mount sources/options: those can contain credentials on some filesystems.
        result['mounts'] = [{key: mount[key] for key in ('device', 'root', 'path', 'type')}
                            for mount in mounts(text)
                            if mount['type'].startswith(('fuse', 'squash', 'lustre', 'nfs'))]
    if 'fuse' in row['name'].lower():
        progress('FUSE image descriptor links ' + str(row['pid']))
        result['image_fds'] = []
        try:
            descriptors = list((directory / 'fd').iterdir())[:128]
        except OSError:
            descriptors = []
        for descriptor in descriptors:
            target = link(descriptor)
            if target and (target == '/dev/fuse' or target.endswith(('.sif', '.sif (deleted)'))):
                result['image_fds'].append(dict(fd=descriptor.name, target=target))
    return result


def fuse_queues(sysfs, uid):
    """Only the caller's visible connections; never open the abort controls."""
    rows = {}
    try:
        entries = (sysfs / 'fs/fuse/connections').iterdir()
        for directory in entries:
            if not directory.name.isdigit() or directory.stat().st_uid != uid:
                continue
            values = {}
            for name in ('waiting', 'max_background', 'congestion_threshold'):
                text, error = read(directory / name, 128)
                if not error:
                    values[name] = text.strip()
            if values:
                rows[directory.name] = values
    except OSError:
        pass
    return rows


def sample(proc=Path('/proc'), sysfs=Path('/sys'), uid=None):
    uid = os.getuid() if uid is None else uid
    all_rows = own_processes(proc, uid)
    wanted = sorted((row for row in all_rows if row['state'] == 'D' or INTERESTING.search(row['name'])),
                    key=priority)
    selected = wanted[:MAX_PROCESSES]
    mount_rows = mounts(read(proc / 'self/mountinfo')[0])
    directories = set()
    for row in selected:
        directories.update(cpu_directories(row['cgroup'], mount_rows))
        row['details'] = detail(proc, row)
        # Do not combine a process that exited with a reused PID's details.
        try:
            row['identity_verified'] = stat(read(proc / str(row['pid']) / 'stat')[0])['start'] == row['start']
        except (ValueError, IndexError):
            row['identity_verified'] = False
    progress('CPU controller counters')
    cpu = cpu_records(directories)
    progress('FUSE connection counters')
    queues = fuse_queues(sysfs, uid)
    return dict(monotonic=time.monotonic(), own_process_count=len(all_rows), processes=selected,
                processes_truncated=len(wanted) > MAX_PROCESSES,
                cpu=cpu, fuse=queues)


def worker(samples, interval):
    global TRACE
    TRACE = True
    for index in range(samples):
        if index:
            time.sleep(interval)
        print(json.dumps(sample(), ensure_ascii=True), flush=True)
    return 0


def collect(command, timeout):
    """Only our new diagnostic worker can be signaled, never a workspace PID."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True, start_new_session=True)
    incomplete, blocked_pid = False, None
    try:
        output, errors = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        incomplete = True
        output = getattr(error, 'output', '') or ''
        errors = getattr(error, 'stderr', '') or ''
        try:
            process.kill()
        except ProcessLookupError:
            pass
        try:
            output, errors = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            blocked_pid = process.pid
            # Do not wait forever for an uninterruptible metadata read.
    if isinstance(output, bytes):
        output = output.decode('utf-8', 'replace')
    if isinstance(errors, bytes):
        errors = errors.decode('utf-8', 'replace')
    samples, last_probe = [], None
    for line in output.splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict) and 'processes' in value:
                samples.append(value)
            elif isinstance(value, dict) and 'probe' in value:
                last_probe = value['probe']
        except ValueError:
            pass
    return dict(samples=samples, incomplete=incomplete or process.returncode != 0,
                worker_still_blocked=blocked_pid, worker_error=errors[-2000:], last_probe=last_probe)


def number(text, name):
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == name:
            return int(parts[1])
    return None


def summary(report):
    samples = report['samples']
    lines = ['Workspace host diagnostic: ' + ('INCOMPLETE' if report['incomplete'] else 'complete'),
             'Node: {} | samples: {} | UID: {}'.format(report['hostname'], len(samples), report['uid'])]
    if report['incomplete']:
        lines.append('Last probe: ' + json.dumps(report.get('last_probe')))
        if report['worker_still_blocked']:
            lines.append('Diagnostic worker {} remained blocked after timeout; avoid repeating this probe.'.format(
                report['worker_still_blocked']))
        if report['worker_error']:
            lines.append('Worker error: ' + json.dumps(report['worker_error']))
    if not samples:
        return '\n'.join(lines + ['No complete sample; see worker_error in the report.'])
    observed = {}
    for sample_row in samples:
        for row in sample_row['processes']:
            if row['identity_verified']:
                observed.setdefault((row['pid'], row['start']), []).append((sample_row['monotonic'], row))
    lines.append('PID / PPID  NAME  STATES  CPU% (one CPU=100)  WAIT')
    keys = sorted(observed, key=lambda key: priority(observed[key][-1][1]))
    for key in keys[:32]:
        history = observed[key]
        first_time, first = history[0]
        last_time, last = history[-1]
        cpu = '{:.1f}'.format(100 * (last['ticks'] - first['ticks']) / report['clock_ticks'] /
                            (last_time - first_time)) if last_time > first_time else '-'
        lines.append('{} / {}  {}  {}  {}  {}'.format(last['pid'], last['ppid'],
            json.dumps(last['name']), ''.join(row['state'] for _, row in history), cpu,
            json.dumps(last['wchan'])))
        for _, row in history:
            for task in row['details']['blocked_threads']:
                note = 'D thread {}: {}'.format(task['tid'], json.dumps(task['wchan']))
                if task['stack_error']:
                    note += ' (stack: {})'.format(task['stack_error'])
                elif task['stack']:
                    frames = [re.sub(r'^\[.*?\]\s*', '', frame) for frame in task['stack'].splitlines()[:6]]
                    note += ' stack=' + json.dumps(' <- '.join(frames))
                if note not in lines:
                    lines.append(note)
        if last['state'] == 'D' or 'tmux' in last['name'].lower() or 'fuse' in last['name'].lower():
            visible = sorted(set(mount['type'] for mount in last['details'].get('mounts', [])))
            if visible:
                lines.append('  Visible filesystem types: ' + ', '.join(visible))
            for descriptor in last['details'].get('image_fds', []):
                if descriptor['target'] != '/dev/fuse':
                    lines.append('  Open image: ' + json.dumps(descriptor['target']))
    if len(keys) > 32:
        lines.append('Additional processes are in the JSON report.')
    for directory, last in sorted(samples[-1]['cpu'].items()):
        first = samples[0]['cpu'].get(directory, {})
        start = number(first.get('cpu.stat', ''), 'nr_throttled')
        end = number(last.get('cpu.stat', ''), 'nr_throttled')
        limit = last.get('cpu.max', '{}/{}'.format(last.get('cpu.cfs_quota_us', '?'),
                                                  last.get('cpu.cfs_period_us', '?')))
        lines.append('CPU group {}: quota={} throttled_delta={}'.format(json.dumps(directory),
                     limit, end - start if start is not None and end is not None else 'unavailable'))
    if not samples[-1]['cpu']:
        lines.append('CPU controller counters unavailable; no conclusion about CPU limits.')
    connections = sorted(set(key for item in samples for key in item['fuse']))
    for connection in connections:
        waiting = [item['fuse'].get(connection, {}).get('waiting', '-') for item in samples]
        lines.append('FUSE connection {}: waiting={}'.format(connection, ','.join(waiting)))
    if not connections:
        lines.append('FUSE connection counters unavailable; this does not establish that queues are empty.')
    if any(item['processes_truncated'] or any(row['details']['threads_truncated']
            for row in item['processes']) for item in samples):
        lines.append('Process/thread sampling limit reached; report is partial for those lists.')
    lines.append('D is a kernel wait, not tmux detachment. Nonzero FUSE waiting alone is not a deadlock diagnosis.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='New private JSON report path; an existing file is never overwritten')
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--interval', type=float, default=3)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not sys.platform.startswith('linux'):
        parser.error('run from the native Linux login node that owns the workspace')
    if os.environ.get('WS_CONTAINER') == '1' or os.environ.get('WS_LAYOUT') == 'thin-v1':
        parser.error('run in a native SSH shell outside hpc-workspace')
    if not (2 <= args.samples <= 10 and 0.1 <= args.interval <= 10 and 1 <= args.timeout <= 60):
        parser.error('samples must be 2-10, interval 0.1-10, timeout 1-60 seconds')
    if (args.samples - 1) * args.interval >= args.timeout:
        parser.error('timeout must exceed the requested sampling interval total')
    if args.worker:
        return worker(args.samples, args.interval)
    output = None
    try:
        if args.output:
            descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            output = os.fdopen(descriptor, 'w', encoding='utf-8')
        print('Sampling existing processes from the host; no container or tmux command will run.', flush=True)
        command = [sys.executable, os.path.abspath(__file__), '--worker', '--samples', str(args.samples),
                   '--interval', str(args.interval), '--timeout', str(args.timeout)]
        report = collect(command, args.timeout)
        report.update(schema_version=1, hostname=socket.gethostname(), uid=os.getuid(),
                      clock_ticks=os.sysconf('SC_CLK_TCK'),
                      recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if output:
            json.dump(report, output, indent=2, ensure_ascii=True)
            output.write('\n')
            output.close()
            output = None
        print(summary(report))
        if args.output:
            print('Private detailed report: ' + json.dumps(args.output))
        return 2 if report['incomplete'] else 0
    except OSError as error:
        print('workspace diagnostic: ' + str(error), file=sys.stderr)
        return 2
    finally:
        if output:
            output.close()


if __name__ == '__main__':
    sys.exit(main())
