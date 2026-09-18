# -*- coding: utf-8 -*-
"""
Isolate the client crash.

Symptom: joining the server makes the CLIENT abort with
    NetworkManager.cpp(233): Networkable already added to network manager, netId=0

The previous attempt removed a duplicated GeometryTemplate and the error did not
change, so duplication is NOT the cause. Now separate the two remaining variables:

    A) the mount directive itself (ServerArchives.con + Objects.zip present)
    B) the woodencrate_dstest instances in StaticObjects.con

Modes:
    A  -> mount present, NO instances        (tests the mount alone)
    B  -> mount present, ONE instance        (tests a single instance)
    C  -> no mount, instances present        (tests instances alone; server only)
    D  -> full original map (clean baseline)

Usage:  python build_mount_test.py A
"""
import os
import shutil
import sys
import zipfile

BF = r'D:\BF2ServerForDeepseek\Battlefield 2'
LVL = os.path.join(BF, 'mods', 'bf2', 'Levels', 'Dalian_Plant')
BACKUP = os.path.join(LVL, 'server.zip.deepseek-backup')
OBJZIP = os.path.join(LVL, 'Objects.zip')
SERVERZIP = os.path.join(LVL, 'server.zip')

CON = (
    "ObjectTemplate.create SimpleObject woodencrate_dstest\r\n"
    "ObjectTemplate.saveInSeparateFile 1\r\n"
    "ObjectTemplate.collisionMesh woodencrate_4m\r\n"
    "ObjectTemplate.mapMaterial 0 Wood_solid 0\r\n"
    "ObjectTemplate.mapMaterial 1 Wood_thin 0\r\n"
    "ObjectTemplate.hasCollisionPhysics 1\r\n"
    "ObjectTemplate.physicsType 3\r\n"
    "ObjectTemplate.geometry woodencrate_4m\r\n"
    "ObjectTemplate.anchor 0/-1.3713/0\r\n"
)
TWEAK = (
    "ObjectTemplate.activeSafe SimpleObject woodencrate_dstest\r\n"
    "ObjectTemplate.saveInSeparateFile 1\r\n"
)
SPOTS = [(-772, 198, -141), (-762, 198, -131), (-782, 198, -151)]
MOUNT_LINE = 'fileManager.mountArchive Levels/Dalian_Plant/Objects.zip Objects\r\n'


def want(flag):
    return flag in sys.argv[1:]


def build(mode):
    use_mount = mode in ('A', 'B')
    n_inst = {'A': 0, 'B': 1, 'C': 3, 'D': 0}[mode]

    # --- Objects.zip ---
    if use_mount:
        if os.path.exists(OBJZIP):
            os.remove(OBJZIP)
        base = 'staticobjects/common/com_objects/crates/woodencrate_dstest/'
        with zipfile.ZipFile(OBJZIP, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr(base + 'woodencrate_dstest.con', CON)
            z.writestr(base + 'woodencrate_dstest.tweak', TWEAK)
        print('  Objects.zip: %d bytes' % os.path.getsize(OBJZIP))
    else:
        if os.path.exists(OBJZIP):
            os.remove(OBJZIP)
            print('  Objects.zip: removed')
        else:
            print('  Objects.zip: absent')

    # --- server.zip ---
    shutil.copy2(BACKUP, SERVERZIP)
    tmp = SERVERZIP + '.new'
    if os.path.exists(tmp):
        os.remove(tmp)

    added = 0
    with zipfile.ZipFile(SERVERZIP, 'r') as zin:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'StaticObjects.con' and n_inst > 0:
                    lines = data.decode('latin-1').replace('\r\n', '\n').split('\n')
                    out = []
                    done = False
                    i = 0
                    while i < len(lines):
                        out.append(lines[i])
                        if (not done) and ('Object.create coolingtower_01' in lines[i]):
                            j = i + 1
                            while j < len(lines) and any(
                                    lines[j].strip().startswith(p) for p in
                                    ('Object.absolutePosition', 'Object.rotation',
                                     'Object.layer', 'Object.setLightSourceMask')):
                                out.append(lines[j])
                                j += 1
                            i = j - 1
                            for sp in SPOTS[:n_inst]:
                                out.append('rem *** DSTEST ***')
                                out.append('Object.create woodencrate_dstest')
                                out.append('Object.absolutePosition %d.000/%d.000/%d.000' % sp)
                                out.append('Object.rotation 0.0/0.0/0.0')
                                out.append('Object.layer 1')
                                out.append('')
                                added += 1
                            done = True
                        i += 1
                    data = '\r\n'.join(out).encode('latin-1')
                zout.writestr(item, data)
            if use_mount:
                zout.writestr('ServerArchives.con', MOUNT_LINE)

    os.remove(SERVERZIP)
    os.rename(tmp, SERVERZIP)
    print('  server.zip: mount=%-5s instances=%d  (%d bytes)'
          % (use_mount, added, os.path.getsize(SERVERZIP)))


def verify():
    with zipfile.ZipFile(SERVERZIP) as z:
        names = z.namelist()
        print('  entries: %d' % len(names))
        print('  ServerArchives.con: %s' % ('ServerArchives.con' in names))
        so = z.read('StaticObjects.con').decode('latin-1')
        print('  woodencrate_dstest instances: %d'
              % so.count('Object.create woodencrate_dstest'))
        print('  total Object.create: %d'
              % sum(1 for l in so.split('\r\n') if l.strip().startswith('Object.create')))


if __name__ == '__main__':
    mode = 'A'
    for a in sys.argv[1:]:
        if a in ('A', 'B', 'C', 'D'):
            mode = a
    print('=== mode %s ===' % mode)
    if mode == 'D':
        shutil.copy2(BACKUP, SERVERZIP)
        if os.path.exists(OBJZIP):
            os.remove(OBJZIP)
        print('  restored pristine map, Objects.zip removed')
    else:
        build(mode)
    print()
    print('=== verify ===')
    verify()
    print()
    for f in ('spawn.log', 'doctor.log'):
        p = os.path.join(BF, f)
        if os.path.exists(p):
            try:
                os.remove(p)
                print('  removed %s' % f)
            except Exception as e:
                print('  could not remove %s: %s' % (f, e))
