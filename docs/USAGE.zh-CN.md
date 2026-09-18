# BF2 服务端 RCON 命令使用说明

> 配套文件：`mod/spawn.py`（模组）、`mod/zzdoctor.py`（加载诊断）
> 适用：**原版 BF2 服务端 1.5.3153**（内嵌 Python **2.3.4**）

---

## ⚠️ 先读这一段：能用 vs 不能用

**这些命令全部在服务端有效**，但记住一条铁律：

| 能力 | 服务端 | 客户端 |
|---|---|---|
| 查询物件位置、数量、距离 | ✅ | — |
| 创建 / 移动 / 删除物件 | ✅ 世界真的变了 | ❌ **看不见** |
| 碰撞体 | ✅ | ✅ 会跟着服务端变（会造成"幽灵物件"） |
| 让玩家看见新建筑 | — | ❌ **架构上不可能** |

**服务端改的是"服务端自己的世界"，客户端渲染的是"它自己本地烘焙的地图"。**
两者是两个独立的东西 —— 详见 `CONCLUSION.md`。

**所以这些命令的实用价值在于：地图编辑辅助、坐标采集、调试诊断。**
不适合用来做"给玩家看新建筑"。

---

## 一、安装

### 1. 放置文件

```
<服务端目录>\Admin\standard_admin\spawn.py       ← mod\spawn.py
<服务端目录>\Admin\standard_admin\zzdoctor.py    ← mod\zzdoctor.py
```

### 2. 修改 `Admin\standard_admin\__init__.py`

原版内容：

```python
import autobalance
import tk_punish
import playerconnect

autobalance.init()
tk_punish.init()
playerconnect.init()
```

改成：

```python
import zzdoctor          # 必须第一个：加载诊断 + 语法预检

import autobalance
import tk_punish
import playerconnect

autobalance.init()
tk_punish.init()
playerconnect.init()

try:
    import spawn
    zzdoctor._wt('__init__: import spawn OK')
except:
    zzdoctor._fail('__init__: import spawn')

try:
    spawn.init()
    zzdoctor._wt('__init__: spawn.init() OK')
except:
    zzdoctor._fail('__init__: spawn.init()')

zzdoctor.init()
```

> `zzdoctor` 会**逐个 compile 检查**同级模块，任何语法错误都会带着行号写进 `doctor.log`。
> 这不是装饰 —— 一个模块的语法错误会让**整个 `standard_admin` 包**导入失败，
> 而且**没有任何提示**（`spawn.py` 最初就是这样死了好几轮）。

### 3. 配置 RCON 密码

**原版服务端默认没有这个文件**，不建就连不上 RCON。

新建 `Admin\default.cfg`：

```
port=4711
password=deepseek
```

> 密码位置是 `Admin/default.cfg`，**不是** `ServerSettings.con` 里的 `sv.rconPassword`
> （那个键在原版服务端里根本不存在）。

### 4. 启动服务端

启动时留意日志文件（模组会写）：

```
spawn.log     ← 模组加载、命令注册、命令输出
doctor.log    ← 加载诊断、语法预检
```

正常应看到：

```
bf2-spawn-test 0.4 loaded (commands: spl, spw, spwbump, spwdel, spwdiag,
                           spwdump, spwenv, spwfind, spwlist, spwmoveback,
                           spwmovetest, spwnet, spwpos, spwraw, spwrender,
                           spwstack, spwtest, spwwalls)
```

### 5. 游戏内登录

**必须进游戏、在游戏内控制台敲**（原因见下面"注意事项"）：

```
rcon login deepseek
```

成功后返回 `Authentication successful, rcon ready.`

---

## 二、命令参考

### 🌟 最实用的三条

#### `rcon spwpos` —— 查自己坐标

```
your position: -773.52 / 185.10 / -121.81
your rotation: 162.7 / 0.0 / 0.0
```

**用途**：改地图时采集坐标。这三数就是 `StaticObjects.con` / `GamePlayObjects.con` 的坐标格式（`X / Y / Z`，**Y 是高度**）。

---

#### `rcon spwfind <模板名>` —— 查某物件在世界里的位置

```
rcon spwfind coolingtower_01

=== spwfind: coolingtower_01 ===
live instances: 2
  [0] (-26.93, 188.04, -163.62)   746.1m from you
  [1] (-89.38, 188.04, -101.71)   684.0m from you
```

**用途**：
- 验证你的地图改动**服务端是否生效**（改完 `StaticObjects.con` 后数量/坐标会变）
- 找某个物件离你多远，方便跑过去看
- **反向解算自己的坐标**：已知物件坐标 + 距离，能算出你在哪

---

#### `rcon spwdump [半径]` —— 列出周围物件

```
rcon spwdump 150

walking 240 root object(s), radius 150m
47 named object(s) within range:
  d=12.4    woodencrate_4m        at -765.2/185.1/-135.8
  d=31.0    container_cl_red      at -742.9/184.6/-118.2
  ...
distinct templates (name x count):
  container_cl_red                   x3
  woodencrate_4m                     x5
scanned 2413 object(s) total.
```

**用途**：**这是找模板名的工具** —— 想在某处放建筑，先看看附近有什么、叫什么名字。

---

### 创建 / 移动 / 删除（服务端有效，客户端看不见）

#### `rcon spwtest` —— 一键测试

在头顶 3 米生成一个木箱，并报告完整过程：

```
=== bf2-spawn-test 0.4 ===
your position: 775.14/163.07/20.60
chosen template: woodencrate_4m   (12 instance(s) already on this map)
--- executing the exact StaticObjects.con sequence ---
  Object.create woodencrate_4m
  Object.absolutePosition 775.139/163.074/23.596
  Object.rotation 0.000/0.000/0.000
  Object.layer 1
object count for woodencrate_4m:  12 -> 13   *** GREW ***
```

**用途**：快速确认"服务端能不能创建物件"。

---

#### `rcon spw <模板名> [模板名2] ...` —— 创建物件

```
rcon spw woodencrate_4m
rcon spw woodencrate_4m container_cl_red mi_sandbags_4m
```

在头顶 3 米创建，支持批量。

**引擎的真实语法**（从 `StaticObjects.con` 逐字核对，**907 个实例全部如此**）：

```
Object.create woodencrate_4m
Object.absolutePosition -59.987/176.238/-269.162
Object.rotation -66.6/0.0/0.0
Object.layer 1
```

**三个关键点**：
1. `Object.create` **只接一个参数**（模板名），**不带坐标**
2. 坐标用**斜杠分隔** `x/y/z`，不是空格
3. 这四行**必须紧连**（后三行配置的是 `Object.create` 刚创建的那个对象，中间插别的命令就跑了）

---

#### `rcon spwstack [模板名]` / `rcon spwmovetest` / `rcon spwbump`

把**已存在**的物件搬到你面前（不创建新的）：

| 命令 | 效果 |
|---|---|
| `spwstack` | 搬 5 个到你正前方排成一行 |
| `spwmovetest` | 搬最近的 1 个到你头顶 4 米 |
| `spwbump` | 搬 1 个到你正前方 2 米（测碰撞用） |

**用途**：测"服务端改坐标 → 客户端是否有反应"。

**用 `rcon spwmoveback` 还原**（会恢复到原始坐标）。

---

#### `rcon spwdel <模板名>` —— 删除

删除指定模板的**所有**物件。

> ⚠️ 包括地图原本就有的。做实验时别对着重要物件用。

---

### 诊断

| 命令 | 作用 |
|---|---|
| `rcon spwdiag` | 自检：版本、坐标、可枚举对象数、已知模板存活数 |
| `rcon spwlist` | 本次会话创建了什么 |
| `rcon spwraw` | 引擎原始回显（`Object.list` 等） |
| `rcon spl [关键字]` | 列出引擎的模板清单 |
| `rcon spwenv` | 地图名、世界尺寸、重力等 |

**遇到"命令没反应/报错"时，先跑 `spwdiag`**，它会把状态写进 `spawn.log`。

---

## 三、注意事项（都是踩过的坑）

### 1. 必须在**游戏内**控制台敲

| 来源 | `ctx.player` | 能读你自己坐标吗 |
|---|---|---|
| **游戏内** `rcon xxx` | 玩家索引 | ✅ **能** |
| 外部 TCP rcon 客户端 | `None` | ❌ 不能 |
| 服务端本地控制台 | `None` | ❌ 不能 |

所有涉及坐标的命令都需要游戏内上下文。

### 2. 密码是 `Admin\default.cfg`

不是 `sv.rconPassword`（原版没这个键）。

### 3. 服务端内嵌 Python 是 **2.3.4**（2005 年）

写模组时**禁止**：

```python
x if c else y        # 三元表达式（2.5+）
sorted()             # 2.4+
set() / frozenset()  # 2.4+
(x for x in y)       # 生成器表达式（2.4+）
@decorator           # 2.4+
with ...             # 2.5+
except X as e        # 2.6+
```

**源文件必须纯 ASCII**（非 ASCII 会让 Python 2.3 直接语法错误）。这也是为什么 `spawn.py` 里全是英文注释。

### 4. `os` 模块被阉割

这个环境里没有：

```
os.getcwd()    ✗
os.path        ✗
os.listdir()   ✗
```

定位自身目录只能用 `__file__` 字符串切分。

### 5. 改地图后必须**重启服务端**

地图文件只在启动时读一次。

### 6. 启动服务端的命令行

```
bf2_w32ded.exe +config mods/bf2/Settings/ServerSettings.con +mapList mods/bf2/Settings/maplist.con
```

- **不要加** `+modPath` —— `bf2_w32ded.exe` 里没这个参数
- **路径不要加引号** —— 引擎命令行不解析引号；带空格的路径靠 `cd` 切工作目录解决
- 工作目录必须是安装根目录（`Admin/default.py` 用相对路径打开 `admin/default.cfg`）

### 7. `rcon exec` —— 原版自带的万能命令

任何服务端控制台命令都能通过它执行，不需要额外模组：

```
rcon exec Object.list
rcon exec sv.serverName
```

`default.py` 里 `exec` 的实现就是 `ctx.write(host.rcon_invoke(cmd))`。

---

## 四、服务端 Python 的加载点（供参考）

实测确认的加载链：

```
服务端启动
  └── sv.adminScript "default"          (ServerSettings.con)
        └── Admin/default.py            被导入
              ├── parseConfig()         读 Admin/default.cfg
              ├── server = AdminServer()  注册 rcon_cmds {login, users, exec}
              └── init()
                    └── import standard_admin
                          └── Admin/standard_admin/__init__.py
                                └── spawn.init()  ← 注册自定义命令
```

**地图加载时**还会执行：

```
mods/bf2/python/bf2/__init__.py         ✅ 实测加载
mods/bf2/python/game/gamemodes/gpm_cq.py → init()   ✅ 实测执行
```

**但客户端在联机模式下这些全都不加载**（实测：一个都没触发）。

---

## 五、限制（重要）

**这些命令不能让你"给玩家加建筑"。** 原因：

1. **BF2 客户端联机时不运行 Python**（实测验证）
2. 建筑几何体烘焙在客户端 `client.zip\terraindata.raw`（44 MB）
3. 静态物件**没有网络 ID**，引擎不会把它们同步给客户端

**客户端能看见的只有**：载具、装备、玩法对象、玩家 —— 这些有网络 ID。

**要改玩家看到的建筑，只有一条路**：改地图包（`client.zip` + `server.zip` 同步），让玩家下载。

---

## 六、扩展阅读

归档内 `bf2tech-archive/`：

| 文件 | 内容 |
|---|---|
| `BF2_Console_Commands.txt` | **引擎控制台命令全表**（6500 行）—— 最值钱的一份 |
| `Object_Reference.txt` | Python API 权威参考 |
| `Console_Script_Grammar.txt` | `.con` 脚本语法（`run` / `include` / 变量） |
| `Scripts-EvalPy.txt` | **通过 RCON 注入的实时 Python REPL** |
| `Scripts-ReserveSlots.txt` | 管理模块全文（`ctx.player` 约定出处） |
| `Scripts-Player_Position_Display.txt` | 坐标采集工具 |
| `Scripts-ConParser.txt` | `.con` 文件读写库 |

**EvalPy 特别推荐** —— 装好后可以在运行中的服务器里直接试 API，不用反复重启：

```
rcon eval for i in dir(bf2.objectManager.getObjectsOfTemplate('c4_explosives')[0]): ctx.write(str(i) + '\n')
```

⚠️ 给 `ctx.write()` 传非字符串会让 RCON 连接死掉，永远用 `ctx.write(str(x))`。
