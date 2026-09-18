# -*- coding: utf-8 -*-
"""
Test A: does game/gamemodes/gpm_cq.py run at MAP LOAD time, on both sides?

Why this is the right question:
    Vanilla BF2 will not load python out of a map package (proved: 8 probes in
    every plausible location never fired, even after joining the map). So a
    per-map python file must live in the MOD, not the map. The mod's game mode
    module -- mods/bf2/python/game/gamemodes/gpm_cq.py -- is imported by the
    engine and its init() is called when the game mode starts for a map. Both
    the server and the client have this file, and each runs its own copy.

    If that is true, then code placed there runs on BOTH sides at map load,
    which is exactly the "both sides generate it themselves, so no data needs to
    be sent" mechanism.

What this script does:
    Installs an identical probe into the CLIENT install and the SERVER install,
    each writing to a log file with its own tag, so we can see independently
    whether the server-side init ran and whether the client-side init ran.

    Nothing else is changed. Fully reversible via the .orig backups it makes.
"""
import os
import shutil

SERVER = r'D:\BF2ServerForDeepseek\Battlefield 2'
CLIENT = r'D:\BF2\Battlefield 2'

REL = os.path.join('mods', 'bf2', 'python', 'game', 'gamemodes', 'gpm_cq.py')

PROBE = u'''

# ---------------------------------------------------------------------------
# DSH test probe -- appended, harmless, writes only to a local log file
# ---------------------------------------------------------------------------
def _dsh_probe(msg):
    try:
        f = open('%(log)s', 'a')
        f.write('%(tag)s: ' + msg + '\\n')
        f.close()
    except:
        pass

_dsh_probe('module imported, __file__=' + str(__file__))

_dsh_orig_init = init
def init():
    _dsh_probe('init() CALLED')
    _dsh_orig_init()
    _dsh_probe('init() finished')

_dsh_probe('probe installed')
'''


def install(root, logname):
    path = os.path.join(root, REL)
    if not os.path.exists(path):
        print('  MISSING: %s' % path)
        return False

    backup = path + '.dsh-orig'
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print('  backed up -> %s' % os.path.basename(backup))
    else:
        # always start from the pristine copy so repeated runs are clean
        shutil.copy2(backup, path)

    with open(path, 'rb') as f:
        body = f.read().decode('latin-1')

    if '_dsh_probe' in body:
        print('  already has probe: %s' % path)
        return True

    tag = 'SERVER' if root == SERVER else 'CLIENT'
    body += PROBE % {'tag': tag, 'log': logname}
    with open(path, 'wb') as f:
        f.write(body.encode('latin-1'))
    print('  probe installed [%s]: %s' % (tag, path))
    return True


def report(root, logname):
    p = os.path.join(root, logname)
    print('  %s: %s' % (logname, 'EXISTS %d bytes' % os.path.getsize(p)
                        if os.path.exists(p) else 'not yet'))


if __name__ == '__main__':
    print('=== server side ===')
    install(SERVER, 'gpmprobe-server.log')
    print()
    print('=== client side ===')
    install(CLIENT, 'gpmprobe-client.log')
    print()
    print('=== current probe logs ===')
    report(SERVER, 'gpmprobe-server.log')
    report(CLIENT, 'gpmprobe-client.log')
    print()
    print('Original files are kept as gpm_cq.py.dsh-orig on both sides.')
