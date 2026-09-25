"""Explicit configuration forms for a working workspace; no startup questionnaire."""
import argparse
import copy
import json
from pathlib import Path
import sys

# Invoked with the image's isolated Python (-I), which omits the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_profiles
import configuration
from config_documents import Document, commit
import integration
from terminal_forms import Cancelled, Form


def workspace_form(form):
    document = Document(configuration.directory() / 'config.json')
    before = copy.deepcopy(document.data)
    document.data = document.data or {'schema_version': 1, 'site': 'local', 'overrides': {}}
    configuration.validate(document.data)
    form.note('Workspace configuration: ' + str(document.path))
    form.note('Automatic host mounts remain available. Add only an extra bind you need.')
    binds = document.data.setdefault('overrides', {}).setdefault('binds', [])
    if not isinstance(binds, list):
        raise ValueError('Saved binds must be a list')
    while True:
        action = form.choose('Workspace settings', ['Review and save', 'Add a bind', 'Remove a bind', 'Scheduler default'])
        if action == 'Review and save':
            break
        if action == 'Scheduler default':
            selected = form.choose('Optional scheduler default (native sbatch/qsub do not need this)', ['automatic', 'pbs', 'slurm'], document.data['overrides'].get('scheduler', 'automatic'))
            if selected == 'automatic':
                document.data['overrides'].pop('scheduler', None)
            else:
                document.data['overrides']['scheduler'] = selected
        elif action == 'Add a bind':
            def directory(value):
                if not Path(value).expanduser().is_dir():
                    raise ValueError('Choose an existing directory on this system')
                if any(c in value for c in (',', ':', '\n', '\r')):
                    raise ValueError('Bind paths cannot contain commas, colons or newlines')
            source = str(Path(form.text('Host directory', check=directory)).expanduser().resolve())
            def destination(value):
                integration.validate_extra({'source': source, 'destination': value})
                if any(c in value for c in (',', ':', '\n', '\r')):
                    raise ValueError('Bind paths cannot contain commas, colons or newlines')
            target = form.text('Path inside the workspace', source, destination)
            mode = form.choose('Access', ['ro', 'rw'], 'ro')
            binds.append({'source': source, 'destination': target, 'mode': mode})
        elif binds:
            choices = ['{}: {} -> {}'.format(i + 1, item['source'], item.get('destination', item['source'])) for i, item in enumerate(binds)]
            selected = form.choose('Remove which extra bind?', choices)
            del binds[choices.index(selected)]
        else:
            form.note('There are no extra binds.')
    configuration.validate(document.data)
    for item in binds:
        integration.validate_extra(item)
    form.note('Changed settings: ' + ', '.join(configuration.changed_fields(before, document.data)))
    preview = {key: document.data['overrides'][key] for key in ('binds', 'scheduler') if key in document.data['overrides']}
    form.note(json.dumps(preview, indent=2))
    if form.confirm('Save workspace settings? New workspace entries will use them.'):
        commit([document], configuration.directory())
        form.note('Saved. Inspector imports remain available through ws init/refresh on the host.')


def run(args):
    form = Form(args.plain)
    target = args.target or form.choose('Configure', ['workspace', 'codex', 'claude'])
    if target == 'workspace':
        workspace_form(form)
    else:
        agent_profiles.edit(form, target, args.name)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?', choices=('workspace', 'codex', 'claude'))
    parser.add_argument('name', nargs='?')
    parser.add_argument('--plain', action='store_true')
    args = parser.parse_args()
    try:
        return run(args)
    except (Cancelled, KeyboardInterrupt):
        print('Cancelled; configuration was not saved.', file=sys.stderr)
        return 130
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print('ws configure: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
