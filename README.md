# BF2 Server-Side Modding — Findings & Tools

Reverse-engineering notes, working tools, and hard evidence about **what a Battlefield 2
dedicated server can and cannot change**, verified experimentally on a stock
**BF2 1.5.3153** client + dedicated server.

Everything here was established by direct experiment, not by repeating forum folklore.
Where a widely-repeated claim turned out to be wrong, the evidence is included.

> **中文说明见 [`docs/README.zh-CN.md`](docs/README.zh-CN.md)**

---

## The headline result

**A stock BF2 server cannot make clients display a building that is not already in
their own local map files.** Not at runtime, not at map load, not via any Python API.

```
client building geometry  <-  client.zip\terraindata.raw   (44 MB, baked, server cannot touch)
server collision          <-  server.zip + Python           (server is authoritative)
```

These are **two independent things**. That is why moving a building server-side leaves a
"ghost": the client still draws it in the old place but has no collision there.

---

## Evidence summary

All tests on the stock map `Dalian_Plant`, with **byte-identical `client.zip` on client and
server** (MD5 verified). Results:

| # | Experiment | Server | Client |
|---|---|---|---|
| 1 | Runtime `Object.create woodencrate_4m` | ✅ count `12→13`, returned `id36117` | ❌ nothing rendered |
| 2 | Runtime move of an existing object | ✅ readback confirms new coords | ❌ model stays at old spot |
| 3 | Runtime delete of an existing object | ✅ count drops | ❌ still rendered |
| 4 | Visibility switches (`setActive`, `setIsVisibleRecursive`, `Object.start`, `initGrid`) | ✅ accepted | ❌ all ineffective |
| 5 | Move a building by editing server `StaticObjects.con` | ✅ `spwfind` reports new coords | ❌ renders at old coords |
| 6 | **Delete a building from server `StaticObjects.con`** | ✅ `907→906` | ❌ **still rendered** |
| 7 | Add 3 extra building instances at map load | ✅ `907→910` | ❌ nothing rendered |
| 8 | `DestroyableObject` class (`c_NIGhostAlways`) | ✅ created | ❌ nothing rendered |
| 9 | `mountArchive` injecting a new object | — | 💥 client aborts (`NetworkManager.cpp:233`) |
| 10 | Python packed inside the map (`server.zip`), 8 probe locations | ❌ never ran | ❌ never ran |
| 11 | Python at `python/bf2/*` and `mods/bf2/python/.../gpm_cq.py` | ✅ **all loaded, `init()` ran** | ❌ **never loaded** |
| 12 | Does the client run Python at all in multiplayer? | — | ❌ **no** |

**#11 and #12 are decisive.** The server runs Python happily; the client, in multiplayer,
never starts the interpreter. Every "server tells the client to do X" design therefore has
no destination to arrive at.

Full detail: [`docs/FINDINGS.zh-CN.md`](docs/FINDINGS.zh-CN.md)

---

## What actually works

The server **can** create, move and delete objects — it just can't show anyone.
So the useful applications are map editing, coordinate capture, and debugging.

Install the module and get **18 RCON commands**:

| Command | Purpose |
|---|---|
| `rcon spwpos` | **Show your coordinates** — in `X / Y / Z` form, ready to paste into a `.con` |
| `rcon spwfind <template>` | **Locate a template in the world** + distance from you |
| `rcon spwdump [radius]` | **List template names around you** — how you find out what a building is called |
| `rcon spwtest` | One-shot spawn test with full reporting |
| `rcon spw <template> ...` | Create object(s) at your position |
| `rcon spwstack` / `spwmovetest` / `spwbump` | Move existing objects for testing |
| `rcon spwmoveback` | Undo the above |
| `rcon spwdel <template>` | Delete objects |
| `rcon spwdiag` / `spwlist` / `spwraw` / `spwl` / `spwenv` | Diagnostics |

**Installation and full reference: [`docs/USAGE.zh-CN.md`](docs/USAGE.zh-CN.md)**

---

## What you actually have to do instead

To change what players *see*, you must **modify the map package and ship it to the client**:

- edit `client.zip` **and** `server.zip` **together**
- both sides must match exactly, or you get ghost geometry (visible but intangible)
- this is the standard approach, and how every custom BF2 map already works

BF2 mods also commonly ship the same map *name* with different content. That is the most
likely explanation for the "impossible server" stories — the client was running the mod's
files all along, not receiving anything at runtime.

---

## Gotchas worth knowing (all cost real time)

| Trap | Detail |
|---|---|
| **Embedded Python is 2.3.4** | No ternary `x if c else y`, no `sorted()`, no `set()`, no decorators, no `with`, no `except X as e` |
| **`os` module is crippled** | `os.getcwd`, `os.path`, `os.listdir` do not exist. Use `__file__` string surgery |
| **Non-ASCII kills it** | Source files must be pure ASCII — a stray Chinese comment in a docstring is a SyntaxError |
| **A SyntaxError is silent** | One bad module makes the whole `standard_admin` package fail to import, with **no** visible error. Hence `zzdoctor.py`, which compile-checks every sibling and logs the reason |
| **`+modPath` does not exist** | The string is not in `bf2_w32ded.exe` |
| **Command line does not parse quotes** | Paths with spaces must be handled by `cd`-ing to the install root |
| **RCON password lives in `Admin\default.cfg`** | Not `sv.rconPassword`. File is absent by default, so RCON is unusable until you create it |
| **`ctx.player` only for in-game rcon** | TCP rcon and the local console have no player context, so position-dependent commands fail |
| **`sendClientCommand` is a UI event channel** | `command` is a number (e.g. `100` = tkpunish dialog), not a command string. It cannot execute anything on the client |

---

## Historical archive

The community wiki **bf2tech** (the best BF2 server-side reference that ever existed) went
offline. Its pages are mirrored in [`archive/`](archive/), recovered via the Wayback Machine
CDX index:

- **`BF2_Console_Commands.txt`** — the complete engine console command table (~6500 lines)
- **`Object_Reference.txt`** — the authoritative BF2 Python API reference
- **`Scripts-EvalPy.txt`** — a live Python REPL you can inject over RCON
- plus `.con` grammar, coordinate system, and a dozen period server scripts

Retrieval method, if more pages are ever needed:

```
http://web.archive.org/cdx/search/cdx?url=bf2tech.uturista.pt*&output=text&fl=timestamp,original
http://web.archive.org/web/<timestamp>id_/<original-url>
```

*(HTTPS to archive.org failed from this machine; plain HTTP worked.)*

---

## Repository layout

```
mod/        spawn.py (18 RCON commands), zzdoctor.py (load diagnostics)
docs/       findings, usage guide, Chinese README
scripts/    test harnesses for each experiment + a logging server launcher
logs/       raw output from the experiments cited above
archive/    bf2tech wiki mirror
```

---

## Scope and honesty

This documents **one specific engine build** (BF2 1.5.3153). It is possible that earlier
patches behaved differently, or that a total-conversion mod changes the picture.

It is also possible that a mechanism exists which these twelve experiments failed to hit.
If you know of one, **an issue with a reproduction is very welcome** — especially if it
includes a client-side screenshot of an object created by the server at runtime.

What this repository does *not* claim: that the technique never existed. It claims that on
a stock 1.5 client, with unmodified client files, the server cannot inject visible geometry —
and it shows the experiments that establish that.

---

## License

**MIT** — see [LICENSE](LICENSE).

The original intention was **GPL-3.0**, to guarantee that anything built on this work stays
open. It was changed to MIT deliberately, for one practical reason:

> **copyleft gets in the way of the people who would actually use this.**

BF2 modding is a small, non-commercial, mostly-volunteer scene. A total-conversion mod that
wants to borrow the `spwfind` coordinate helper, or a server admin who wants to fold a few
of these commands into a private admin script, should not have to reason about licence
compatibility or publish their whole project to do it.

So: **use it, change it, ship it, close it, sell it — no permission needed, no obligations
beyond keeping the copyright notice.** The point of publishing this was to stop the
knowledge from dying with the people who found it, not to put conditions on it.
