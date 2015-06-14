#!/usr/bin/env python
'''
Makina-States Stage runner

It will setup the env, then launch & wrap the stage0 -> 3 dance
The stage scripts need:

    - rsync (opt but recommended
    - python > 2.6
    - acl (setfacl/getfacl)

'''
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import copy
import sys
import os
import pipes
import string
import random
import subprocess
import hashlib
import textwrap

try:
    from collections import OrderedDict
except ImportError:
    try:
        from orderedict import OrderedDict
    except ImportError:
        OrderedDict = dict


_CWD = os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))
RED = '\033[31;01m'
PURPLE = '\033[35;01m'
CYAN = '\033[36;01m'
YELLOW = '\033[33;01m'
GREEN = '\033[32;01m'
NORMAL = '\033[0m'
COLORS = {'red': RED,
          'purple': PURPLE,
          'cyan': CYAN,
          'yellow': YELLOW,
          'normal': NORMAL,
          'green': GREEN}


class StageError(Exception):
    '''.'''


def hashfile(afile, hasher=None, blocksize=65536):
    if not hasher:
        hasher = hashlib.md5()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    return hasher.digest()


def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def purple(msg, pipe=sys.stdout):
    pipe.write(PURPLE)
    pipe.write(msg)
    pipe.write(NORMAL)
    pipe.write('\n')


def red(msg, pipe=sys.stdout):
    pipe.write(RED)
    pipe.write(msg)
    pipe.write(NORMAL)
    pipe.write('\n')


def cyan(msg, pipe=sys.stdout):
    pipe.write(CYAN)
    pipe.write(msg)
    pipe.write(NORMAL)
    pipe.write('\n')


def yellow(msg, pipe=sys.stdout):
    pipe.write(YELLOW)
    pipe.write(msg)
    pipe.write(NORMAL)
    pipe.write('\n')


def green(msg, pipe=sys.stdout):
    pipe.write(GREEN)
    pipe.write(msg)
    pipe.write(NORMAL)
    pipe.write('\n')


def die(reason, pipe=sys.stderr):
    red(reason, pipe=pipe)
    raise StageError(reason)


def die_in_error(p, reason, pipe=sys.stderr):
    if p.returncode != 0:
        die(reason, pipe=pipe)


def warn_in_error(p, reason='', pipe=sys.stderr):
    if p.returncode != 0:
        yellow(reason, pipe=pipe)


def run_cmd(cmd,
            env=None,
            shell=True,
            output=True,
            pipe=sys.stdout,
            errpipe=sys.stderr):
    if not env:
        env = copy.deepcopy(os.environ)
    if not output:
        pipe = subprocess.PIPE
        errpipe = subprocess.PIPE
    p = subprocess.Popen(cmd,
                         shell=shell,
                         env=env,
                         stderr=errpipe,
                         stdout=pipe)
    p.wait()
    return p


def qrun_cmd(*args, **kwargs):
    kwargs['output'] = False
    return run_cmd(*args, **kwargs)


def v_run(cmd,
          env=None,
          shell=True,
          pipe=sys.stdout,
          errpipe=sys.stderr):
    green(cmd, pipe=pipe)
    return run_cmd(cmd, env=env, shell=shell, pipe=pipe, errpipe=errpipe)


def v_die_run(cmd,
              env=None,
              reason=None,
              shell=True,
              pipe=sys.stdout,
              errpipe=sys.stderr):
    if not reason:
        reason = 'command {0} failed'.format(cmd)
    p = v_run(cmd, env=env, shell=shell, pipe=pipe, errpipe=errpipe)
    die_in_error(p, reason, pipe=errpipe)
    return p


def q_die_run(cmd,
              env=None,
              reason=None,
              shell=True,
              pipe=sys.stdout,
              errpipe=sys.stderr):
    if not reason:
        reason = 'command {0} failed'.format(cmd)
    p = run_cmd(
        cmd, output=False, env=env, shell=shell, pipe=pipe, errpipe=errpipe)
    die_in_error(p, reason, pipe=errpipe)
    return p


REPORT = textwrap.dedent('''\
{c[yellow]}CWD{c[normal]}:            {c[cyan]}{e[CWD]}{c[normal]}
{c[yellow]}OS{c[normal]}:             {c[cyan]}{e[MS_OS]}{c[normal]}
{c[yellow]}OS_RELEASE{c[normal]}:     {c[cyan]}{e[MS_OS_RELEASE]}{c[normal]}
{c[yellow]}DATADIR{c[normal]}:        {c[cyan]}{e[MS_DATA_DIR]}{c[normal]}
{c[yellow]}BASE{c[normal]}:           {c[cyan]}{e[MS_BASE]}{c[normal]}
{c[yellow]}BASEIMAGE{c[normal]}:      {c[cyan]}{e[MS_BASEIMAGE]}{c[normal]}
{c[yellow]}IMAGE{c[normal]}:          {c[cyan]}{e[MS_IMAGE]}{c[normal]}
{c[yellow]}IMAGE_DIR{c[normal]}:      {c[cyan]}{e[MS_IMAGE_DIR]}{c[normal]}
{c[yellow]}STAGE0 TAG{c[normal]}:     {c[cyan]}{e[MS_STAGE0_TAG]}{c[normal]}
{c[yellow]}STAGE1 TAG{c[normal]}:     {c[cyan]}{e[MS_STAGE1_NAME]}{c[normal]}
{c[yellow]}STAGE2 TAG{c[normal]}:     {c[cyan]}{e[MS_STAGE2_NAME]}{c[normal]}
{c[yellow]}STAGE2 TAG{c[normal]}:     {c[cyan]}{e[MS_STAGE2_NAME]}{c[normal]}
{c[yellow]}DOCKER ARGS{c[normal]}:    {c[cyan]}{e[MS_DOCKER_ARGS]}{c[normal]}

''')


def report(environ, pipe=sys.stdout):
    pipe.write(REPORT.format(c=COLORS, e=environ))


def main(argv=None,
         environ=None,
         pipe=sys.stdout,
         errpipe=sys.stderr):
    if not environ:
        environ = copy.deepcopy(os.environ)
    if argv is None:
        argv = sys.argv[:]
    yellow('-----------------------------------------------', pipe=pipe)
    yellow('-   makina-states docker build system         -', pipe=pipe)
    yellow('-----------------------------------------------', pipe=pipe)
    yellow('-   STAGE -1 - ASSEMBLING BUILD ENVIRONMENT   -', pipe=pipe)
    yellow('-----------------------------------------------', pipe=pipe)

    environ.setdefault('MS_OS', 'ubuntu')
    environ.setdefault(
        'MS_OS_MIRROR', 'http://mirror.ovh.net/ftp.ubuntu.com/')
    environ.setdefault('DEFAULT_RELEASE', '')
    environ.setdefault('MS_COMMAND', '/bin/systemd')
    DEFAULT_RELEASE = ''
    if environ['MS_OS'] == 'ubuntu':
        DEFAULT_RELEASE = 'vivid'
    environ.setdefault('MS_OS_RELEASE', DEFAULT_RELEASE)
    environ.setdefault('MS_DOCKER_ARGS', '')
    environ.setdefault('MS_BASE', 'scratch')
    MS_DATA_DIR = environ.setdefault(
        'MS_DATA_DIR', os.path.join(_CWD, 'data'))
    environ.setdefault(
        'MS_DOCKER_STAGE0',
        os.path.join(_CWD, 'docker/stage0.sh'))
    environ.setdefault(
        'MS_DOCKER_STAGE1',
        os.path.join(_CWD, 'docker/stage1.sh'))
    environ.setdefault(
        'MS_DOCKER_STAGE2',
        os.path.join(_CWD, 'docker/stage2.sh'))
    environ.setdefault(
        'MS_MAKINASTATES_BUILD_DISABLED', '0')
    environ.setdefault(
        'MS_DOCKER_STAGE3',
        os.path.join(_CWD, 'docker/stage3.sh'))
    environ.setdefault(
        'MS_DOCKERFILE_STAGE0',
        os.path.join(
            _CWD,
            'docker/Dockerfile.stage0'
            .format(environ)))
    environ.setdefault(
        'MS_STAGE0_TAG',
        'makinacorpus/'
        'makina-states-'
        '{0[MS_OS]}-{0[MS_OS_RELEASE]}-stage0:latest'.format(environ))
    environ.setdefault('MS_GIT_BRANCH', 'stable')
    environ.setdefault(
        'MS_GIT_URL',
        'https://github.com/makinacorpus/makina-states.git')
    MS_IMAGE = environ.setdefault(
        'MS_IMAGE',
        'makinacorpus/'
        'makina-states-{0[MS_OS]}-{0[MS_OS_RELEASE]}'.format(environ))
    environ.setdefault(
        'MS_IMAGE_CANDIDATE',
        MS_IMAGE.split(':')[0] + ':candidate')
    MS_IMAGE_DIR = environ.setdefault(
        'MS_IMAGE_DIR',
        os.path.join(environ['MS_DATA_DIR'],
                     environ['MS_IMAGE']))
    environ.setdefault(
        'MS_BASEIMAGE',
        'baseimage-{0[MS_OS]}-{0[MS_OS_RELEASE]}.tar.xz'
        .format(environ))
    id_ = id_generator()
    environ.setdefault(
        'MS_STAGE1_NAME',
        environ['MS_IMAGE'].replace('/', '') + '-stage1-' + id_)
    environ.setdefault(
        'MS_STAGE2_NAME',
        environ['MS_IMAGE'].replace('/', '') + '-stage2-' + id_)
    MS_INJECTED_DIR = environ['MS_INJECTED_DIR'] = os.path.join(
        environ['MS_IMAGE_DIR'], 'injected_volumes')
    MS_OVERRIDES = environ['MS_OVERRIDES'] = os.path.join(
        environ['MS_IMAGE_DIR'], 'overrides')
    MS_BOOTSTRAP_DIR = environ['MS_BOOTSTRAP_DIR'] = os.path.join(
        MS_INJECTED_DIR, 'bootstrap_scripts')
    environ['cwd'] = environ['CWD'] = _CWD
    report(environ, pipe=pipe)
    #
    cpcmd = 'rsync -aA'
    if qrun_cmd('which rsync').returncode != 0:
        raise StageError(
            'You must install rsync and place it in your path')
    # copy base boiler plate to the build directory
    breakl = False
    for i in [
        MS_DATA_DIR,
        MS_INJECTED_DIR,
        MS_BOOTSTRAP_DIR,
        MS_IMAGE_DIR
    ]:
        if not os.path.exists(i):
            try:
                cyan('{0}: creating {1}'.format(MS_IMAGE, i), pipe=pipe)
                os.makedirs(i)
            except OSError:
                die('{0}: ${1} HOST datadir cant be created'
                    .format(MS_IMAGE, i), pipe=pipe)
            breakl = True
    if breakl:
        pipe.write('\n')
    stage_files = OrderedDict()
    stage_files['lxc-cleanup.sh'] = os.path.join(
        _CWD,
        'files/sbin/lxc-cleanup.sh')
    stage_files['makinastates-snapshot.sh'] = os.path.join(
        _CWD,
        'files/sbin/makinastates-snapshot.sh')
    stage_files['Dockerfile.stage0'] = environ['MS_DOCKERFILE_STAGE0']
    stage_files['stage0.sh'] = environ['MS_DOCKER_STAGE0']
    stage_files['stage1.sh'] = environ['MS_DOCKER_STAGE1']
    stage_files['stage2.sh'] = environ['MS_DOCKER_STAGE2']
    stage_files['stage3.sh'] = environ['MS_DOCKER_STAGE3']
    for i in stage_files:
        j = os.path.join(MS_BOOTSTRAP_DIR, i)
        k = stage_files[i]
        d = os.path.dirname(j)
        if not os.path.exists(k):
            die('{0}: script {1} ({2})'
                ' does not exist'.format(MS_IMAGE, i, k), pipe=errpipe)
        if not os.path.exists(d):
            cyan('{0}: creating {1}'.format(MS_IMAGE, d), pipe=pipe)
            os.makedirs(d)
        docp = True
        if os.path.exists(j) and os.path.exists(k):
            docp = False
            with open(j) as jo:
                with open(k) as ko:
                    if hashfile(jo) != hashfile(ko):
                        docp = True

        if not docp:
            yellow('{0}: {1} already in place'.format(MS_IMAGE, i), pipe=pipe)
        else:
            q_die_run(
                '{0} {1} {2}'.format(cpcmd,
                                     pipes.quote(k),
                                     pipes.quote(j)),
                env=environ,
                pipe=pipe,
                errpipe=errpipe,
                reason=('{0}: script {1} ({2} -> {3})'
                        ' cant be copied'.format(
                            MS_IMAGE, i, k, j)))
            cyan('{0}: copied {1} -> {2}'.format(MS_IMAGE, k, j), pipe=pipe)
    pipe.write('\n')
    if os.path.exists(MS_OVERRIDES):
        q_die_run(
            '{0} {1}/ {2}/'.format(cpcmd,
                                   pipes.quote(MS_OVERRIDES),
                                   pipes.quote(MS_INJECTED_DIR)),
            env=environ,
            pipe=pipe,
            errpipe=errpipe,
            reason=('{0}: script ({1} -> {2})'
                    ' cant be overriden'.format(
                        MS_IMAGE, MS_OVERRIDES, MS_INJECTED_DIR)))
        cyan('{0}: overidden\n {1}\n  -> {2}\n'.format(
            MS_IMAGE, MS_OVERRIDES, MS_INJECTED_DIR), pipe=pipe)
    if argv[1:]:
        environ['MS_DOCKER_ARGS'] += ' {0}'.format(' '.join(argv[1:]))

    purple('--------------------', pipe=pipe)
    purple('- stage-1 complete -', pipe=pipe)
    purple('--------------------', pipe=pipe)
    pipe.write('\n')
    p = v_die_run(
        '{0}/injected_volumes/bootstrap_scripts/stage0.sh'
        ' {1}'.format(MS_IMAGE_DIR, ' '.join(argv)),
        env=environ,
        reason='{0}: build failed'.format(MS_IMAGE))
    return p, environ, pipe, errpipe


if __name__ == '__main__':
    main()
# vim:set et sts=4 ts=4 tw=80: