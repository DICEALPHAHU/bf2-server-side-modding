# -*- coding: utf-8 -*-
"""
bf2-spawn-test  --  BF2 staticobject runtime spawn probe
================================================================================
Purpose
    Prove (or disprove) two things on a live Battlefield 2 server:

    A) Can the server create a STATICOBJECT at runtime that clients render?
    B) What names / syntax does the engine actually accept for that?

This is a PROBE, not a finished product. Every guess it makes is printed,
so you can see exactly which variant of the command the engine accepted.

Deployment
    <bf2server>/admin/standard_admin/spawn.py          <- this file
    <bf2server>/admin/standard_admin/__init__.py       <- add 2 lines (see README)

Python version: 2.4 / 2.5  (BF2's embedded interpreter -- NO f-strings, NO with)

RCON commands added
    spl                       list available object-template names
    spl <substring>           list template names matching substring
    spwdump [radius]          list world objects near you -> geometry template names
                              ^^^ run this FIRST: it gives you real template names
    spwraw                    dump raw Object.list / printScript replies (debug)
    spwmove <tpl> [fwd] [rgt] [up] [yaw]
                              ^^^ run this SECOND: move an existing map object.
                                  Cannot hit the client-asset boundary, so if this
                                  works, server->client object replication is proven.
    spw <template>            spawn at you, 0 rotation   <- run this THIRD
    spw <template> <zoff>
    spw <template> <h> <p> <r>          yaw/pitch/roll in degrees
    spw <template> <h> <p> <r> <layer> <team>
    spwtry <template>         same as spw with explicit dialect reporting
    spwdel <template>         delete every object of that template (UNDO)
    spwdelall                 delete everything we spawned this session
    spwlist                   show what we spawned this session
"""

import sys
import new
import default
import bf2
import host

from bf2 import g_debug

try:
    from math import sqrt
except ImportError:
    import math
    def sqrt(x):
        return math.sqrt(x)

# ---------------------------------------------------------------------------
# bookkeeping
# ---------------------------------------------------------------------------

VERSION = '0.2'
SPAWNED = []          # objects WE created (Python wrappers)
ACCEPTED = None       # once a dialect works, remember it and stop guessing


def log(msg):
    """Server console + log file."""
    try:
        host.rcon_invoke('echo "[spawn] %s"' % msg)
    except:
        pass


def rcon(cmd):
    """Run a server console command. Returns the engine's reply, or an ERR string.

    NOTE: a console command that throws does NOT kill the server, but a Python
    call on an object that is no longer valid DOES. So every rcon() is wrapped.
    """
    try:
        return host.rcon_invoke(cmd)
    except:
        return 'ERR:' + str(sys.exc_info()[1])


def me(playerId):
    """Return the PhysicalObject of the calling player, or None.

    player.getVehicle() returns the soldier body when not in a vehicle.
    """
    try:
        p = bf2.playerManager.getPlayerByIndex(playerId)
        if p is None:
            return None
        return p.getVehicle()
    except:
        return None


def caller(ctx):
    """Player index of whoever issued the rcon command, or None.

    From bf2tech's admin module (Scripts:ReserveSlots), the AdminServer builds a
    CommandContext per command:
        in-game rcon  -> ctx.player = <player index>,  ctx.socket = None
        TCP rcon      -> ctx.socket = <AdminConnection>, ctx.player = None
        local console -> both None
    So the local server console has NO position context -- use explicit xyz then.
    """
    return getattr(ctx, 'player', None)


def mypos(playerId):
    o = me(playerId)
    if o is None:
        return None
    try:
        return o.getPosition()
    except:
        return None


def objs_of(template):
    """All live world objects of a given template name."""
    if not template:
        return []
    try:
        return list(bf2.objectManager.getObjectsOfTemplate(template))
    except:
        return []


def find_by_template(template):
    """Locate a PhysicalObject for a template name. Supports both bare names and
    full paths ('objects/staticobjects/.../foo.con'), because bf2 is inconsistent
    about which one getObjectsOfTemplate() wants."""
    for cand in (template, template.lower(), template.replace('\\', '/')):
        found = objs_of(cand)
        if found:
            return found[0], cand
    # try tail-of-path form:  'objects/staticobjects/x/y/foo.con' -> 'foo'
    tail = template.replace('\\', '/').split('/')[-1]
    if tail.lower().endswith('.con'):
        tail = tail[:-4]
    found = objs_of(tail)
    if found:
        return found[0], tail
    return None, None


def raw_objs_of(template):
    """Same as objs_of but WITHOUT the dict lookup, for 'list raw'."""
    try:
        return list(bf2.objectManager.getObjectsOfTemplate(template))
    except:
        return []


# ---------------------------------------------------------------------------
# rcon helpers
# ---------------------------------------------------------------------------

def cap():
    """Capture 'Object.list' output, which has no return channel of its own.

    Object.list -> std::string, so host.rcon_invoke SHOULD hand the text back.
    If it doesn't on your build, spwdump is the fallback (it uses Python only).
    """
    try:
        out = host.rcon_invoke('Object.list')
        if out is None:
            return ''
        return str(out)
    except:
        return ''


def tag(prefix):
    """Return the tail of Object.list after the last occurrence of prefix.

    Using the LAST occurrence matters: Object.list echoes your own command line
    first, so search-from-front always finds the echoed command, never the result.
    """
    s = cap()
    if not s or prefix not in s:
        return s
    return s[s.rfind(prefix) + len(prefix):]


# ---------------------------------------------------------------------------
# template enumeration
# ---------------------------------------------------------------------------

def list_templates(ctx, filt=None):
    out = tag('Object.list')
    if not out:
        ctx.write('Object.list returned nothing usable.\n'
                  'Use  spwdump  instead (it enumerates via Python).\n')
        return
    names = []
    for line in out.split('\n'):
        line = line.strip()
        if not line:
            continue
        # engine usually prints "<name> : <something>"
        head = line.split(':')[0].strip()
        if head:
            names.append(head)
    names = sorted(set(names))
    if filt:
        f = filt.lower()
        names = [n for n in names if f in n.lower()]
    ctx.write('Object.list: %d template name(s)%s\n'
              % (len(names), filt and (' matching "%s"' % filt) or ''))
    for n in names:
        ctx.write('  %s\n' % n)
    if not names:
        ctx.write('  (nothing parsed -- Object.list format differs; try spwdump)\n')


def dump_nearby(ctx, playerId, radius):
    """THE IMPORTANT ONE.

    Walks the live object graph from the world root, reports every object whose
    geometry template is non-empty (i.e. a visible staticobject) within radius.
    The template names printed here are exactly what you feed to spw.
    """
    pos = mypos(playerId)
    if pos is None:
        ctx.write('cannot read your position.\n')
        return
    px, py, pz = pos[0], pos[1], pos[2]

    roots = []
    try:
        for t in ('dice.hfe.world.ObjectTemplate.ObjectSpawner',
                  'dice.hfe.world.ObjectTemplate.DestroyableObject',
                  'dice.hfe.world.ObjectTemplate.AnimatedBundle',
                  'dice.hfe.world.ObjectTemplate.Trigger',
                  'dice.hfe.world.ObjectTemplate.ControlPoint',
                  'dice.hfe.world.ObjectTemplate.PlayerControlObject'):
            try:
                roots.extend(list(bf2.objectManager.getObjectsOfType(t)))
            except:
                pass
    except:
        pass

    try:
        roots.extend(list(bf2.objectManager.getObjectsOfType('PhysicalObject')))
    except:
        pass

    seen = {}
    def walk(o, depth):
        if depth > 3 or o is None:
            return
        try:
            key = str(o.token)
        except:
            key = None
        if key is not None:
            if key in seen:
                return
            seen[key] = 1
        try:
            gt = str(o.getTemplateProperty('geometryTemplate'))
        except:
            gt = ''
        try:
            p = o.getPosition()
            d = sqrt((p[0]-px)**2 + (p[1]-py)**2 + (p[2]-pz)**2)
        except:
            p, d = None, 1e9
        if gt and gt not in ('', 'None', '0') and d <= radius:
            try:
                tn = o.templateName
            except:
                tn = '?'
            ctx.write('  d=%-6.1f  geom=%-42s  tpl=%s\n' % (d, gt[:42], tn))
        if depth < 3:
            try:
                for ch in o.getChildren():
                    walk(ch, depth + 1)
            except:
                pass

    for r in roots:
        try:
            walk(r, 0)
        except:
            pass
    ctx.write('scanned %d object(s); nothing printed means radius too small.\n'
              % len(seen))


# ---------------------------------------------------------------------------
# spawning
# ---------------------------------------------------------------------------

PROBE_TPL = '__bf2_spawn_probe'
SPAWNED_PROBE = [None]


def probe_name():
    """A template name that is guaranteed not to be a real map asset.

    Used only by the dialects that must construct an ObjectTemplate first, so a
    failed probe can never collide with, or corrupt, a genuine template.
    """
    if SPAWNED_PROBE[0] is None:
        SPAWNED_PROBE[0] = PROBE_TPL
    return SPAWNED_PROBE[0]


def build(fmt, tpl, pos, rot, layer, team):
    x, y, z = pos[0], pos[1], pos[2]
    a, b, c = rot[0], rot[1], rot[2]
    if fmt == 'active':
        # Dialect 1 -- the one to bet on, and the ONLY one that needs no
        # ObjectTemplate.create at all. This mirrors how .con files work:
        # make a template active, then operate on it.
        return ['ObjectTemplate.activeSafe %s' % tpl,
                'Object.create %f %f %f %f %f %f' % (x, y, z, a, b, c),
                'object.absolutePosition %f %f %f' % (x, y, z),
                'object.rotation %f %f %f' % (a, b, c),
                'object.layer %d' % layer,
                'object.setTeam %d' % team,
                'Object.info Object.active']
    if fmt == 'create':
        # Dialect 2 -- build a fresh ObjectTemplate first, then pass its token.
        # Probe name is unique so we never collide with a real template, and so
        # a failed run cannot corrupt the engine's template table.
        return ['ObjectTemplate.create StaticObjects %s' % probe_name(),
                'ObjectTemplate.activeSafe %s' % probe_name(),
                'Object.create ObjectTemplate.active %f %f %f %f %f %f'
                % (x, y, z, a, b, c),
                'object.absolutePosition %f %f %f' % (x, y, z),
                'object.rotation %f %f %f' % (a, b, c),
                'object.layer %d' % layer,
                'Object.info Object.active']
    if fmt == 'get':
        # Dialect 3 -- fetch a token by index via getTemplate. Weakest guess
        # (getTemplate returns std::string, not a proxy), kept only for evidence.
        return ['ObjectTemplate.create StaticObjects %s' % probe_name(),
                'ObjectTemplate.getTemplate 0 -> v_tpl',
                'Object.create v_tpl %f %f %f %f %f %f' % (x, y, z, a, b, c),
                'object.absolutePosition %f %f %f' % (x, y, z),
                'object.rotation %f %f %f' % (a, b, c),
                'object.layer %d' % layer,
                'Object.info Object.active']
    return []


def try_dialects(ctx, tpl, pos, rot, layer, team):
    """Try each command dialect; report whether the world object count grew.

    Note we diff against NAME variants too: bf2.objectManager may address the
    same template by bare name or by full .con path depending on how it was
    registered, so we take the max count over all spellings on both sides.
    """
    global ACCEPTED
    results = []

    def count():
        best = 0
        for v in (tpl, tpl.lower(),
                  tpl.replace('\\', '/'),
                  tpl.replace('\\', '/').split('/')[-1].replace('.con', '')):
            best = max(best, len(raw_objs_of(v)))
        return best

    for fmt in ('active', 'create', 'get'):
        before = count()
        replies = []
        for cmd in build(fmt, tpl, pos, rot, layer, team):
            replies.append(rcon(cmd))
        after = count()
        grew = after > before
        obj = rcon('Object.info Object.active')
        results.append((fmt, before, after, grew, obj, replies))
        if grew:
            ACCEPTED = fmt
            break
    return results


def cmd_spawn(ctx, playerId, argv):
    global ACCEPTED
    if not argv:
        ctx.write('USAGE: spw <template> [zoff] [h] [p] [r] [layer] [team]\n'
                  '       spwdump   -- find the right <template> name\n')
        return

    tpl = argv[0]
    zoff = float(argv[1]) if len(argv) > 1 else 1.0
    rot = (float(argv[2]) if len(argv) > 2 else 0.0,
           float(argv[3]) if len(argv) > 3 else 0.0,
           float(argv[4]) if len(argv) > 4 else 0.0)
    layer = int(argv[5]) if len(argv) > 5 else 0
    team = int(argv[6]) if len(argv) > 6 else 0

    pos = mypos(playerId)
    if pos is None:
        ctx.write('spawn: cannot read your position.\n'
                  '  reason: no valid player context. The local server console and a\n'
                  '  TCP rcon client have ctx.player = None. Join the server and use\n'
                  '  the in-game console:  rcon spw <template>\n')
        return
    pos = (pos[0], pos[1], pos[2] + zoff)

    ctx.write('spawn: template=%s  pos=(%.1f, %.1f, %.1f)  rot=(%.0f, %.0f, %.0f)\n'
              % (tpl, pos[0], pos[1], pos[2], rot[0], rot[1], rot[2]))

    # sanity: is this template name known to the manager at all?
    known, realname = find_by_template(tpl)
    if known is None:
        ctx.write('  NOTE: bf2.objectManager does not currently know a template named\n'
                  '        "%s". That does NOT prove it is invalid (nothing of that\n'
                  '        template may be placed on this map yet) -- continue anyway.\n' % tpl)
    else:
        ctx.write('  manager knows it as: %s  (%d instance(s) on this map)\n'
                  % (realname, len(raw_objs_of(realname))))

    # NOTE: we deliberately do NOT touch existing objects here. This command
    # must answer exactly one question: does Object.create() grow the world?
    # Moving existing map objects is a separate, easier experiment -> spwmove.

    import time
    t0 = time.time()
    results = try_dialects(ctx, tpl, pos, rot, layer, team)

    for fmt, before, after, grew, obj, replies in results:
        ctx.write('  [%s] before=%s after=%s -> %s\n'
                  % (fmt, before, after, grew and '*** OBJECT COUNT GREW ***' or 'no change'))
        for r in replies:
            r = str(r).strip()
            if r:
                ctx.write('      %s\n' % r[:300])
        if obj:
            ctx.write('      Object.info -> %s\n' % str(obj)[:200])

    if ACCEPTED:
        log('ACCEPTED dialect = %s (template %s)' % (ACCEPTED, tpl))
        ctx.write('  ==> WORKING DIALECT: %s   (remembered for this session)\n' % ACCEPTED)
        ctx.write('  ==> NOW LOOK AT YOUR GAME CLIENT. Did the object appear?\n')
        ctx.write('      appeared  -> spawn works, and the client HAS this template.\n')
        ctx.write('      invisible -> spawn works, client LACKS the geometry.\n')
        ctx.write('      crash/DC  -> client LACKS the geometry, badly.\n')
    else:
        ctx.write('  ==> no dialect increased the object count.\n'
                  '      Next: run  spwdump  to get a template name that is\n'
                  '      definitely real, then retry with that.\n')


def cmd_del(ctx, playerId, argv):
    if not argv:
        ctx.write('USAGE: spwdel <template>   (or  spwdelall )\n')
        return
    tpl = argv[0]
    objs = objs_of(tpl)
    if not objs:
        ctx.write('spwdel: no live object of "%s".\n' % tpl)
        return
    n = 0
    for o in objs:
        try:
            rcon('Object.delete %s' % o.token)
            n += 1
        except:
            pass
    ctx.write('spwdel: issued %d delete(s); if 0, try:\n'
              '        rcon Object.delete <token>   with a token from Object.list\n' % n)


def cmd_delall(ctx, playerId, argv):
    n = 0
    while SPAWNED:
        o = SPAWNED.pop()
        try:
            rcon('Object.delete %s' % o.token)
            n += 1
        except:
            pass
    ctx.write('spwdelall: removed %d object(s).\n' % n)


def cmd_move(ctx, playerId, argv):
    """The EASY half of the trick, and the one to test FIRST.

    Moves / re-rotates an object that ALREADY EXISTS on the map. Because the
    client already has that geometry loaded, this cannot hit the asset boundary.
    If the object moves in your client, then server->client replication of
    object transforms is confirmed working on your build, and all that is left
    to prove is whether NEW instances can be created.
    """
    if not argv:
        ctx.write('USAGE: spwmove <template> [fwd] [right] [up] [yaw]\n'
                  '       Moves every live object of <template> to a spot near you.\n'
                  '       Get <template> from:  spwdump\n')
        return
    tpl = argv[0]
    fwd = float(argv[1]) if len(argv) > 1 else 10.0
    rgt = float(argv[2]) if len(argv) > 2 else 0.0
    up = float(argv[3]) if len(argv) > 3 else 0.0
    yaw = float(argv[4]) if len(argv) > 4 else 0.0

    obj, realname = find_by_template(tpl)
    if obj is None:
        ctx.write('spwmove: no live object of "%s" found.\n'
                  '         run  spwdump  and copy a name from the geom= column.\n' % tpl)
        return

    myo = me(playerId)
    if myo is None:
        ctx.write('spwmove: cannot read your position.\n')
        return
    try:
        p = myo.getPosition()
        r = myo.getRotation()
    except:
        ctx.write('spwmove: cannot read your transform.\n')
        return

    # bf2 rotation[0] is yaw in degrees; forward = (cos y, 0, sin y) with
    # a negated sine for the +y-forward convention. Cheap and good enough for
    # a probe -- refine once you can see the result.
    import math
    yawrad = r[0] * math.pi / 180.0
    fx = math.sin(yawrad)
    fy = math.cos(yawrad)
    # right-hand vector
    rx = math.cos(yawrad)
    ry = -math.sin(yawrad)

    tgt = (p[0] + fx * fwd + rx * rgt,
           p[1] + fy * fwd + ry * rgt,
           p[2] + up)
    rot = (r[0] + yaw, r[1], r[2])

    objs = objs_of(realname)
    n = 0
    for o in objs:
        try:
            o.setPosition(tgt)
            o.setRotation(rot)
            n += 1
        except:
            pass
    ctx.write('spwmove: moved %d object(s) of "%s"\n'
              '  from %s\n  to   (%.1f, %.1f, %.1f) rot=(%.0f, %.0f, %.0f)\n'
              '  LOOK AT YOUR CLIENT: did it move?\n'
              % (n, realname,
                 str(objs[0].getPosition()) if objs else '?',
                 tgt[0], tgt[1], tgt[2], rot[0], rot[1], rot[2]))


def cmd_raw(ctx, playerId, argv):
    """Dump the raw Object.list reply, markers included, so we can see the
    engine's actual formatting instead of guessing at it."""
    ctx.write('--- Object.list raw (markers shown as |) ---\n')
    try:
        out = host.rcon_invoke('Object.list')
    except:
        out = None
    if out is None:
        ctx.write('host.rcon_invoke returned None (no return channel).\n')
    else:
        s = str(out)
        ctx.write('len=%d\n' % len(s))
        for line in s.split('\n'):
            ctx.write('|%s\n' % line[:200])
    ctx.write('--- Object.printScript(Object.active) ---\n')
    r = rcon('Object.printScript Object.active')
    if r:
        ctx.write('%s\n' % str(r)[:800])
    ctx.write('--- probe: ObjectTemplate.getTemplate 0..3 ---\n')
    for i in range(4):
        r = rcon('ObjectTemplate.getTemplate %d' % i)
        ctx.write('  [%d] -> %s\n' % (i, str(r)[:200]))


def cmd_list(ctx, playerId, argv):
    ctx.write('bf2-spawn-test %s | session spawned: %d | dialect: %s\n'
              % (VERSION, len(SPAWNED), ACCEPTED or '(unknown)'))
    for o in SPAWNED:
        try:
            ctx.write('  %s  %s\n' % (o.templateName, str(o.getPosition())))
        except:
            pass


# ---------------------------------------------------------------------------
# rcon command registration (same mechanism bf2tech documents)
# ---------------------------------------------------------------------------

def rcmd_spl(self, ctx, cmd):
    argv = cmd.split()
    list_templates(ctx, argv[0] if argv else None)


def rcmd_spw(self, ctx, cmd):
    cmd_spawn(ctx, caller(ctx), cmd.split())


def rcmd_spwtry(self, ctx, cmd):
    cmd_spawn(ctx, caller(ctx), cmd.split())


def rcmd_spwdel(self, ctx, cmd):
    cmd_del(ctx, caller(ctx), cmd.split())


def rcmd_spwdelall(self, ctx, cmd):
    cmd_delall(ctx, caller(ctx), cmd.split())


def rcmd_spwlist(self, ctx, cmd):
    cmd_list(ctx, caller(ctx), cmd.split())


def rcmd_spwdump(self, ctx, cmd):
    argv = cmd.split()
    radius = float(argv[0]) if argv else 150.0
    ctx.write('objects within %.0fm of you (geometry templates):\n' % radius)
    if caller(ctx) is None:
        ctx.write('spwdump needs an in-game or in-game-rcon caller: there is no\n'
                  'position context from a TCP rcon client or the local console.\n'
                  'Join the server, then type:  rcon spwdump   in the game console.\n')
        return
    dump_nearby(ctx, caller(ctx), radius)


def rcmd_spwmove(self, ctx, cmd):
    cmd_move(ctx, caller(ctx), cmd.split())


def rcmd_spwraw(self, ctx, cmd):
    cmd_raw(ctx, caller(ctx), cmd.split())


CMDS = {
    'spl':      rcmd_spl,
    'spw':      rcmd_spw,
    'spwtry':   rcmd_spwtry,
    'spwdel':   rcmd_spwdel,
    'spwdelall': rcmd_spwdelall,
    'spwlist':  rcmd_spwlist,
    'spwdump':  rcmd_spwdump,
    'spwmove':  rcmd_spwmove,
    'spwraw':   rcmd_spwraw,
}


def init():
    if g_debug:
        print 'initialising bf2-spawn-test %s' % VERSION
    for name, fn in CMDS.items():
        m = new.instancemethod(fn, default.server, default.AdminServer)
        setattr(default.AdminServer, 'rcmd_' + name, m)
        default.server.rcon_cmds[name] = m
    log('bf2-spawn-test %s loaded; commands: %s'
        % (VERSION, ', '.join(sorted(CMDS.keys()))))
