# -*- coding: utf-8 -*-
"""
Does the engine load Python that is packed inside a MAP's server.zip?

I claimed it does not, based only on the observation that vanilla maps contain
no .py files. That is weak evidence: vanilla maps having none does not prove the
engine refuses them.

The user recalls that the server they studied needed a DIFFERENT py file per map.
That is exactly what you would do if the engine loads a per-map python module.

So test it directly. Put a one-line probe in every plausible location inside the
map package, and see which one (if any) actually executes.

A probe writes to a log file next to the server executable, because stdout is
block-buffered into server-console.log and may never appear.
"""
import os
import shutil
import zipfile

BF = r'D:\BF2ServerForDeepseek\Battlefield 2'
LVL = os.path.join(BF, 'mods', 'bf2', 'Levels', 'Dalian_Plant')
BACKUP = os.path.join(LVL, 'server.zip.deepseek-backup')
SERVERZIP = os.path.join(LVL, 'server.zip')


def probe_source(tag):
    """A module that reports the moment it is imported or initialised."""
    return (
        "import sys\r\n"
        "\r\n"
        "def _probe(msg):\r\n"
        "    try:\r\n"
        "        f = open('mappython.log', 'a')\r\n"
        "        f.write('%s: ' % '" + tag + "' + msg + '\\n')\r\n"
        "        f.close()\r\n"
        "    except:\r\n"
        "        pass\r\n"
        "\r\n"
        "_probe('MODULE IMPORTED (__file__=%s)' % __file__)\r\n"
        "\r\n"
        "def init():\r\n"
        "    _probe('init() CALLED')\r\n"
        "\r\n"
        "try:\r\n"
        "    init()\r\n"
        "    _probe('auto-init done')\r\n"
        "except:\r\n"
        "    pass\r\n"
    )


# every plausible place a map could carry python that the engine might import
PLACEMENTS = [
    '__init__.py',
    'python/__init__.py',
    'python/mapscript.py',
    'GameModes/gpm_cq/64/__init__.py',
    'maptest.py',
]

# CANDIDATES for the "official" map python entry point; we try each name and
# see which one fires. If none fires, the engine does not load map python.
ENTRY_NAMES = ['__init__.py', 'init.py', 'mapinit.py', 'map.py']


def build():
    shutil.copy2(BACKUP, SERVERZIP)
    tmp = SERVERZIP + '.new'
    if os.path.exists(tmp):
        os.remove(tmp)

    with zipfile.ZipFile(SERVERZIP, 'r') as zin:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            # place a probe bearing its own tag so we can tell them apart
            for name in PLACEMENTS:
                tag = name
                zout.writestr(name, probe_source(tag))
            # also try running one explicitly from Init.con, to cover the
            # "the map's own script does `run foo.py`" idea
            for name in ENTRY_NAMES:
                if name not in PLACEMENTS:
                    zout.writestr(name, probe_source(name))
    os.remove(SERVERZIP)
    os.rename(tmp, SERVERZIP)
    print('  probes installed:')
    for n in PLACEMENTS + [n for n in ENTRY_NAMES if n not in PLACEMENTS]:
        print('    %s' % n)


def add_run_to_init():
    """Also make Init.con explicitly 'run' one of them, in the game branch."""
    tmp = SERVERZIP + '.new2'
    if os.path.exists(tmp):
        os.remove(tmp)
    changed = False
    with zipfile.ZipFile(SERVERZIP, 'r') as zin:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'Init.con':
                    text = data.decode('latin-1')
                    if 'run mapinit.py' not in text:
                        text = text.replace(
                            'run tmp.con v_arg1',
                            'run tmp.con v_arg1\r\nrun mapinit.py', 1)
                        changed = True
                    data = text.encode('latin-1')
                zout.writestr(item, data)
    os.remove(SERVERZIP)
    os.rename(tmp, SERVERZIP)
    print('  Init.con patched with "run mapinit.py": %s' % changed)


def verify():
    with zipfile.ZipFile(SERVERZIP) as z:
        print('  entries: %d' % len(z.namelist()))
        for n in z.namelist():
            if n.endswith('.py'):
                print('    %s  %d bytes' % (n, z.getinfo(n).file_size))
        so = z.read('Init.con').decode('latin-1')
        for line in so.split('\r\n'):
            if 'run' in line and '.py' in line:
                print('    Init.con: %s' % line)


if __name__ == '__main__':
    for f in ('spawn.log', 'doctor.log', 'mappython.log'):
        p = os.path.join(BF, f)
        if os.path.exists(p):
            try:
                os.remove(p)
                print('  removed old %s' % f)
            except Exception as e:
                print('  could not remove %s: %s' % (f, e))
    print('=== install probes ===')
    build()
    print('=== patch Init.con ===')
    add_run_to_init()
    print('=== verify ===')
    verify()
