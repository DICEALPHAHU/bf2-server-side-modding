# -*- coding: utf-8 -*-
"""
Does the BF2 CLIENT have a running python interpreter at all?

The client-side gpm_cq.py probe never fired, but that could mean either:
   (a) the client loads python but not that particular module at that moment, or
   (b) the client does not run python at all in normal play.

These are very different conclusions, so test the foundation:
instrument the client's OWN python/bf2/__init__.py, which is the module that
initialises the whole bf2 python layer. If that never fires, the client simply
has no python running and gpm_cq.py was never a candidate.

Also instruments python/bf2/GameLogic.py, because that is where
bf2.gameLogic.sendClientCommand lives -- if the client loads GameLogic, then the
client DOES have a python side.
"""
import os
import shutil

CLIENT = r'D:\BF2\Battlefield 2'
SERVER = r'D:\BF2ServerForDeepseek\Battlefield 2'

TARGETS = [
    ('python/bf2/__init__.py', 'pyprobe-client.log', 'pyprobe-server.log'),
    ('python/bf2/GameLogic.py', 'pyprobe-client.log', 'pyprobe-server.log'),
]

PROBE = u'''

# --- DSH probe -------------------------------------------------------------
def _dsh_p(msg):
    try:
        f = open('%(log)s', 'a')
        f.write('%(tag)s [%(file)s]: ' + msg + '\\n')
        f.close()
    except:
        pass

_dsh_p('module imported  __file__=' + str(__file__))
'''


def install(root, rel, logname, tag):
    path = os.path.join(root, rel.replace('/', os.sep))
    if not os.path.exists(path):
        print('  MISSING: %s' % path)
        return
    backup = path + '.dsh-orig'
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    else:
        shutil.copy2(backup, path)   # start clean each run

    with open(path, 'rb') as f:
        body = f.read().decode('latin-1')
    if '_dsh_p' in body:
        print('  already probed: %s' % path)
        return
    body += PROBE % {'log': logname, 'tag': tag, 'file': rel}
    with open(path, 'wb') as f:
        f.write(body.encode('latin-1'))
    print('  probed [%s]: %s' % (tag, path))


def show(root, logname):
    p = os.path.join(root, logname)
    if os.path.exists(p):
        print('  %s: %d bytes' % (p, os.path.getsize(p)))
        for line in open(p, 'rb').read().decode('latin-1').split('\n'):
            if line.strip():
                print('      %s' % line)
    else:
        print('  %s: not present' % p)


if __name__ == '__main__':
    for rel, clog, slog in TARGETS:
        print('=== client: %s ===' % rel)
        install(CLIENT, rel, clog, 'CLIENT')
        print('=== server: %s ===' % rel)
        install(SERVER, rel, slog, 'SERVER')
        print()
    print('=== existing logs ===')
    show(CLIENT, 'pyprobe-client.log')
    show(SERVER, 'pyprobe-server.log')
