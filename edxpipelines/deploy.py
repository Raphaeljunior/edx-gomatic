"""
Tools for deploying gomatic-built pipelines.
"""

import logging
import os.path
import subprocess
import tempfile

from .canonicalize import canonicalize_file


def ensure_pipeline(script, dry_run=False, save_config_locally=False, **kwargs):
    script_args = []

    if dry_run:
        script_args.append('--dry-run')

    if save_config_locally:
        script_args.append('--save-config')

    for key, args in sorted(kwargs.items()):
        if not isinstance(args, list):
            args = [args]
        for arg in args:
            script_args.append('--{}'.format(key))
            if not isinstance(arg, list):
                arg = [arg]
            script_args.extend(arg)

    command = ['python', script] + script_args
    logging.debug("Executing script: {}".format(subprocess.list2cmdline(command)))
    result = subprocess.check_output(command, stderr=subprocess.STDOUT)
    if dry_run and save_config_locally:
        with tempfile.NamedTemporaryFile() as before_out, tempfile.NamedTemporaryFile() as after_out:
            canonicalize_file('config-before.xml', before_out)
            canonicalize_file('config-after.xml', after_out)
            subprocess.call([
                'git', '--no-pager',
                'diff', '--no-index', '--color-words',
                before_out.name, after_out.name
            ])
    return result
