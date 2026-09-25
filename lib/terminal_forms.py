"""Gum forms with an explicit basic terminal fallback. No shell evaluation."""
import getpass
import os
import shutil
import subprocess
import sys


class Cancelled(Exception):
    pass


class Form:
    def __init__(self, plain=False):
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise ValueError('Configuration forms need a terminal. Use --help for noninteractive options.')
        self.gum = None if plain or os.environ.get('TERM') == 'dumb' else shutil.which('gum')

    def note(self, message):
        print(message, file=sys.stderr)

    def _gum(self, *args):
        # Gum's fixed gray labels/help can disappear on dark PuTTY palettes.
        # Inherit the terminal's normal contrast while retaining the interactive
        # controls and reverse-video cursor. Scope this to the form process so
        # shell/editor colors and the user's standalone Gum theme stay intact.
        environment = dict(os.environ, NO_COLOR='1')
        environment.pop('CLICOLOR_FORCE', None)
        environment.pop('FORCE_COLOR', None)
        result = subprocess.run([self.gum] + list(args), stdout=subprocess.PIPE,
                                universal_newlines=True, env=environment)
        if result.returncode in (1, 130, -2):
            raise Cancelled()
        if result.returncode:
            raise ValueError('Gum could not display this form. Retry with --plain.')
        return result.stdout.rstrip('\n')

    def text(self, title, value='', check=None, secret=False):
        while True:
            try:
                if self.gum:
                    args = ['input', '--header', title, '--prompt', '> ', '--char-limit', '0']
                    args += ['--password'] if secret else ['--value', str(value)]
                    answer = self._gum(*args)
                elif secret:
                    answer = getpass.getpass(title + ': ', stream=sys.stderr)
                else:
                    self.note(title + (' [' + str(value) + ']' if value else '') + ':')
                    answer = input() or str(value)
                if check:
                    check(answer)
                return answer
            except (EOFError, KeyboardInterrupt):
                raise Cancelled()
            except ValueError as exc:
                self.note(str(exc))

    def choose(self, title, options, default=None):
        self.note(title)
        if self.gum:
            args = ['choose', '--cursor', '> ', '--selected-prefix', '[x] ', '--unselected-prefix', '[ ] ']
            if default in options:
                args += ['--selected', default]
            return self._gum(*(args + list(options)))
        for index, option in enumerate(options, 1):
            self.note('  {}. {}'.format(index, option))
        default_number = str(options.index(default) + 1) if default in options else '1'
        while True:
            answer = self.text('Choose a number', default_number)
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]
            self.note('Choose one of the listed numbers.')

    def confirm(self, title):
        return self.choose(title, ['Cancel', 'Save'], 'Cancel') == 'Save'
