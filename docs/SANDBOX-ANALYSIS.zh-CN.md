# 沙盒模组（Sandbox 1.0.1）分析

> 分析对象：`D:\BF2\Battlefield 2\mods\sandbox\`（用户客户端上已安装的成品模组）
> 作者：Elton "Elxx" Muuga（sandboxmod.com），2009-09-04

---

## 为什么值得记

这是整个调查中**唯一一份"确实能让服务端生成建筑"的成品代码**。
它比我们所有自写实验都值钱 —— 而且它证明了那位技术员当年说的
"看 sandbox 模组，里面有很多语句"是**正确的方向**。

---

## 它是干什么的

`mod.desc` 原文：

> Sandbox is a mod that lets you use the BF2 engine to build structures, set up
> racetracks, ramps, and much much more. This is all done from an easy Command
> Rose interface in-game. … once you're done, you can save it and send it to your
> friends. **Multiplayer support is also included so many players can collaboratively
> construct buildings**

**即：原版 BF2 引擎上的多人协作建造模组。**

---

## 核心机制（`sbxCore.py` L578-597，逐字摘录）

```python
def createObject(self, oName, oPos, oRot = (0.0,0.0,0.0), team = 2):
    if not oName in self.spawnerTemplates:
        self.createSpawnerTemplate(oName)
    host.rcon_invoke("Object.create sbx_" + oName)
    # object is initially spawned underground to prevent conflicts that cause some vehicles to fail
    host.rcon_invoke("Object.absolutePosition " + str(oPos[0]) + "/" + str(-1000.0) + "/" + str(oPos[2]))
    host.rcon_invoke("Object.rotation " + str(oRot[0]) + "/" + str(oRot[1]) + "/" + str(oRot[2]))
    host.rcon_invoke("Object.team " + str(team))

def createSpawnerTemplate(self, oName):
    host.rcon_invoke("ObjectTemplate.create ObjectSpawner sbx_" + oName)
    host.rcon_invoke("ObjectTemplate.activeSafe ObjectSpawner sbx_" + oName)
    host.rcon_invoke("ObjectTemplate.hasMobilePhysics 0")
    host.rcon_invoke("ObjectTemplate.setObjectTemplate 1 " + oName)
    host.rcon_invoke("ObjectTemplate.setObjectTemplate 2 " + oName)
    host.rcon_invoke("ObjectTemplate.minSpawnDelay 700000")
    host.rcon_invoke("ObjectTemplate.maxSpawnDelay 900000")
```

### 关键点

| 点 | 说明 |
|---|---|
| **造的是 `ObjectSpawner`，不是静态物件** | 这是引擎会给**网络 ID** 的类型（载具靠它复制）。直接 `Object.create <静态物件模板>` 没有网络 ID，客户端看不见 —— 这正是本调查中 12 次实验失败的根因 |
| **`setObjectTemplate 1` / `2`** | 1 和 2 是**队伍号**。这就是那位技术员说的"不是1就是2" |
| **先埋到 -1000 地下** | 作者注释：*"to prevent conflicts that cause some vehicles to fail"* —— 它把生成物当**载具类**处理，并踩过 ID 冲突的坑 |
| **`minSpawnDelay 700000`** | 约 8 天，目的是**阻止自动生成**。生成时机由脚本自己控制 |
| **`Object.team`** | 设定所属队伍，客户端可见性相关 |

---

## 模组的存档与网络

- **存档**：`mods/sandbox/saved/` 下的 `.bf2sbg` / `.bf2sbx` 文件，
  格式为 `地图名,COREVERSION@` + 物件数据（`sbxGame_build.py` L829-855）
- **网络**：`sbxNetwork.py` 通过 HTTP POST 到作者服务器
  （`sbx.saveGroup.php` / `sbx.loadGroup.php`），**该服务器早已下线**

---

## 模组的文件构成（关键：客户端也带物件）

```
mods/sandbox/
├── clientarchives.con     挂载 packages/sbx/objects_client.zip 等
├── serverarchives.con     挂载 packages/sbx/objects_server.zip 等
├── packages/
│   ├── sbx/
│   │   ├── objects_client.zip        2.5 MB   ← 客户端有模型
│   │   ├── objects_server.zip        992 KB
│   │   ├── extra_objects_server.zip  1.6 MB
│   │   └── music_client.zip         12.7 MB
│   ├── bf2/  af/  ef/  xp/  dirtbike/
└── python/game/gamemodes/
    ├── sbxCore.py           24 KB   核心（物件管理 + 生成）
    ├── sbxGame_build.py     49 KB   建造界面与逻辑
    ├── sbxSettings.py       13 KB   物件清单、权限、地图限制
    ├── sbxPlayerManager.py   7 KB
    ├── sbxNetwork.py               HTTP 存档同步
    ├── sbxObjectManager.py         sbxObject 类
    ├── sbxMath.py / sbxErrorHandling.py
    ├── gpm_cq.py            14 KB   征服模式（与 bf2 mod 的同名文件不同）
    ├── addons/              clear, cookie, flip, heal, jump, kill,
    │                        log, mutiny, punish, teleport
    └── __init__.py                 自定义事件分发器 host.gpmevents
```

**注意**：`objects_client.zip` 里含沙盒**自有**的静态物件
（`staticobjects/sandbox/glassplane01`、`tracer`、以及 `fx_fire`/`fx_glow*`/
`fx_smoke`/`fx_waterfall` 等特效）。`sbx_` 前缀的生成器模板**不在任何包里** ——
确认它们是运行时由 Python 创建的。

---

## 实测：服务端复现沙盒流程

在纯原版 `bf2` mod（客户端零改动）的服务端上，逐字复制上述 10 行：

```
ObjectTemplate.create ObjectSpawner dsx_woodencrate_4m  ->  09E4B4C4    模板建成
ObjectTemplate.activeSafe ...                           ->  (接受)
ObjectTemplate.setObjectTemplate 1 woodencrate_4m       ->  (接受)
ObjectTemplate.setObjectTemplate 2 woodencrate_4m       ->  (接受)
Object.create dsx_woodencrate_4m                        ->  id36908     生成器建成
Object.absolutePosition .../-1000.0/...                 ->  (接受)
Object.team 2                                           ->  (接受)

dsx_woodencrate_4m 物件计数:  0 -> 1
object.template      -> 09E4B4C4
object.isVisible     -> 1
object.absolutePosition -> -770.043/186.102/-134.507
```

**服务端侧完全复现成功，但客户端仍然什么都看不见。**

### 结论

**沙盒的"服务端流程"本身不足以让原版客户端显示物件。**
还缺客户端侧的东西 —— 而沙盒的 `objects_client.zip`（2.5 MB）与它
20+ 个 Python 模块正是为此存在的。

**这恰好印证了本调查的总结论：客户端必须参与。**
沙盒的做法就是把"客户端要的东西"打包成模组发给玩家 —— 而不是靠运行时传输。

---

## 遗留问题（留给以后）

1. 客户端在**沙盒 mod** 下是否运行 Python？（本调查只在 `bf2` mod 下测过，结论是"不运行"）
2. 沙盒的建造物在**多人**下是否对其他玩家可见？
3. `setObjectTemplate` 生成的对象，是靠引擎自动复制还是靠客户端 Python 自己造？

**验证方式（未执行）**：直接跑沙盒联机，造东西，看另一个客户端能否看见。
但这需要把服务端切成 sandbox mod，且沙盒作为成品玩法，
更适合**直接使用**而不是拆解实验。

---

## 来源

- `mods/sandbox/python/game/gamemodes/sbxCore.py`（作者 Elxx，Missleboy）
- `mods/sandbox/readme.html`
- 作者致谢中提及技术来源为 **bf2tech.org**（已下线，镜像见本仓库 `archive/`）
