# bf2-spawn-test —— 服务端运行时生成 staticobject 的验证工具

**目的**：在活服务器上，用最短路径证明（或推翻）两件事：

- **A** 服务端能不能在运行时创建可被客户端渲染的对象
- **B** 引擎到底接受哪种命令写法、哪种模板名

这是**探针**，不是成品。它每一步的猜测都会打印出来，所以你能看见引擎实际接受了哪个变体。

---

## 为什么是这个方案

你朋友指的那个 `sendClientCommand` 是死的 —— 它的真实定义（bf2tech 原文）是：

> `bf2.gameLogic.sendClientCommand(playerId, command, args)`
> Appears to tell game engine to **prompt a player for input**; the player's
> response returns control to Python by generating a `ClientCommand` event;
> **command is typically a numeric value**, args can be anything, but is
> typically a tuple or list.

它是"给某个玩家弹一个交互提示、等回应、回调 Python"用的（指挥官确认框那类）。**客户端不执行命令、不执行 Python、不创建对象。**

真正的机制在引擎控制台命令里，全部有文档（`BF2_Console_Commands.txt`，签名逐条核对过）：

```
Object.create          IObjectTemplate* Vec3 Vec3  ->  IObject*      L2220
Object.delete / deleteAll / list / listObjectsOfTemplate
Object.info / printScript / forceStart / forceStop / setObjectToGround
Object.loadAll<std::string> / saveAll<std::string>

ObjectTemplate.create  <类型> <名字>  ->  IObjectTemplate*           L2912
ObjectTemplate.active / activeSafe<std::string>
objectTemplate.addTemplate<std::string>                              L2410
objectTemplate.setActiveTemplate<int>                                L4305
objectTemplate.getTemplate<int> -> std::string                       L3521
objectTemplate.networkableInfo<std::string>                          L3912
objectTemplate.setObjectTemplate<int> <std::string>                  L4336

GeometryTemplate.create <类型> <名字> -> IGeometryTemplate*          L1042
  └ 原文注释: "Creates a Geometry Mesh template from the geometry mesh
     name so it can be used in other files without creating a duplicate mesh"

object.absolutePosition <Vec3>     L2199     <- 大佬说的"坐标xyz"
object.rotation <Vec3>             L2313     <- 大佬说的"角度abr"
object.layer <int>                 L2295     <- 大佬说的"层数"
object.setTeam / setVisibleTeam / getVisibleTeam
```

执行入口是**有文档的**：`host.rcon_invoke(command)` —— *"Executes a server console command."*

**关键：为什么"下面三个得写在一起执行不然会炸"** —— `object.absolutePosition` / `object.rotation` / `object.layer` 操作的是**当前活动对象**。`Object.create` 之后必须立刻设完这三样，中间插入别的命令，活动指针就跑了。这就是那句"会炸"的真正含义。

---

## 安装

### 1. 放文件

```
<bf2server>\admin\standard_admin\spawn.py        <- 本目录 mod/spawn.py
<bf2server>\admin\standard_admin\__init__.py     <- 改这个文件（下一步）
```

> `<bf2server>` 形如 `C:\Battlefield 2 Server\`，`admin\standard_admin\` 是 BF2 自带的 Python 管理模块目录。

### 2. 修改 `__init__.py`

打开 `<bf2server>\admin\standard_admin\__init__.py`，它原本长这样：

```python
import autobalance
import tk_punish
autobalance.init()
tk_punish.init()
```

加两行，变成：

```python
import autobalance
import tk_punish
import spawn                      # <-- 加这行
autobalance.init()
tk_punish.init()
spawn.init()                      # <-- 加这行
```

**就这么简单。** 你朋友说的"放在 `admin` 目录中""在 `__init__.py` 里引用"——**这部分他是对的**。bf2tech 的 EvalPy 就是这么装的。

### 3. 确认 RCON 已配置

`<bf2server>\mods\bf2\settings\serversettings.con` 里要有：

```
sv.rconPassword "你的密码"
```

### 4. 启动服务端

看到服务器控制台出现这行就成功了：

```
[spawn] bf2-spawn-test 0.2 loaded; commands: spl, spw, spwdel, spwdelall, spwdump, spwlist, spwmove, spwraw
```

如果没出现 → 见下面「排错」。

---

## 重要前提：位置上下文

| 你从哪敲命令 | `ctx.player` | 能读到你自己的坐标吗 |
|---|---|---|
| **游戏内控制台** `rcon spw x` | 你的玩家索引 | ✅ 能 |
| **外部 RCON 客户端**（TCP） | `None` | ❌ 不能 |
| **服务器本地控制台** | `None` | ❌ 不能 |

依据是 bf2tech 的管理模块源码：

```
if type(playerid_or_socket) == types.IntType:
    ctx.player = playerid_or_socket        # 游戏内 rcon
    ...
else:
    ctx.socket = playerid_or_socket        # TCP rcon
```

**所以：一定要先加入服务器，然后在游戏内控制台敲命令。** 本工具所有涉及坐标的命令都需要这个上下文。

---

## 测试流程（按顺序做，别跳）

### 第 0 步：确认命令装上了

游戏内控制台：

```
rcon spwlist
```

应回 `bf2-spawn-test 0.2 | session spawned: 0 | dialect: (unknown)`。

---

### 第 1 步：拿到真实的模板名 —— `spwdump`

```
rcon spwdump 150
```

这会走一遍活的对象图，把**你周围 150 米内所有带几何体的对象**列出来：

```
objects within 150m of you (geometry templates):
  d=12.4    geom=objects/staticobjects/.../foo.con         tpl=foo
  d=31.0    geom=objects/staticobjects/.../bar.con         tpl=bar
  ...
scanned 2413 object(s); nothing printed means radius too small.
```

**`geom=` 那一列就是你要的模板名。** 这就是"复制地图里已有物件"的取名字工具 —— 也是这套技术真正的起点。

> 如果输出为空，把半径加大：`rcon spwdump 400`
> 如果报 `getTemplateProperty` 相关错误，改用 `rcon spwraw` 看引擎原生输出格式。

---

### 第 2 步：先测「移动已有的」—— `spwmove`

**这一步最重要，因为它不会碰到客户端资源边界。**

```
rcon spwmove <上一步拿到的名字>
```

它会把地图上那个物件搬到你面前 10 米。然后**看你自己的游戏画面**：

| 你看到什么 | 结论 |
|---|---|
| **物件动了** | ✅ 服务端→客户端的对象变换同步是通的。基础机制成立。 |
| 没动 | 命令写法不对，或该对象受地形/光照烘焙约束。看控制台回显。 |
| 客户端崩溃/掉线 | 罕见；说明该对象类型不适合服务端操作，换一个再试。 |

**为什么先做这步**：它只改已有对象的坐标，客户端早就有这个几何体了，**不可能因为"客户端缺资源"而失败**。所以一旦这步通了，"服务端能改世界、客户端看得见"就被证实了 —— 剩下要证的只有"能不能创建**新实例**"。

参数：`rcon spwmove <名字> [前] [右] [上] [偏航角]`，默认 `10 0 0 0`。

---

### 第 3 步：测「创建新的」—— `spw`

```
rcon spw <上一步拿到的名字>
```

它会依次试三种命令方言（`active` / `create` / `get`），并报告**世界对象数有没有增长**：

```
spawn: template=foo  pos=(123.4, 567.8, 91.0)  rot=(0, 0, 0)
  manager knows it as: foo  (3 instance(s) on this map)
  [active] before=3 after=4 -> *** OBJECT COUNT GREW ***
      Object.info -> ...
  ==> WORKING DIALECT: active   (remembered for this session)
  ==> NOW LOOK AT YOUR GAME CLIENT. Did the object appear?
      appeared  -> spawn works, and the client HAS this template.
      invisible -> spawn works, client LACKS the geometry.
      crash/DC  -> client LACKS the geometry, badly.
```

**然后看你自己的画面**，这是整个验证的核心判据：

| 客户端表现 | 含义 |
|---|---|
| **新物件出现了** | ✅✅ **成功。** 服务端能创建 staticobject，客户端能渲染，且客户端有此模板。五十年的问题到此结束。 |
| **看不见** | 服务端创建成功了（对象数增长），但**客户端没有这个几何体**。→ 换一个原版已有的模板再试，或者确认该物件是否真在原版 `objects/` 里。 |
| **崩溃/掉线** | 同上，但客户端处理不了未知模板。→ 说明此模板必须存在于客户端。 |

参数：`rcon spw <名字> [抬高] [偏航] [俯仰] [翻滚] [层] [队伍]`

---

### 第 4 步：测「边界」—— 用自制物件

这一步直接量出那条硬边界，**是整个工程的可行性判据**：

对同一个物件名，做两次第 3 步：

1. **原版物件**（`objects/staticobjects/...` 里的，比如某棵树、某个集装箱）→ 应该成功
2. **你自制 mod 里的新物件**（客户端没装）→ 应该**看不见**或**崩溃**

第 2 次的结果就是你未来所有设计的天花板：**客户端本地没有的模型，服务端怎么折腾都画不出来。**

---

### 第 5 步：撤掉 —— `spwdel` / `spwdelall`

```
rcon spwdel <名字>        # 删掉所有该模板的对象
rcon spwdelall            # 删掉本次会话中我们创建的
```

**注意**：地图静态物件带烘焙好的光照和阴影，删掉对象后**地上的阴影可能还留着**。这不是 bug，是烘焙贴图的本质。

> ⚠️ `spwdel <名字>` 删的是**全世界**该模板的对象 —— 包括地图原本就有的。做实验时别对着重要物件用。

---

## 出问题时（排错）

| 现象 | 原因 / 处理 |
|---|---|
| 启动时控制台没有 `[spawn] ... loaded` | `import spawn` 没加，或 `spawn.init()` 没调；或 `spawn.py` 没放对目录 |
| 控制台报 `SyntaxError` / `ImportError` | 检查 `spawn.py` 是不是被当文本保存了、编码是否变成非 ASCII（**必须是纯 ASCII 或 ASCII 兼容编码**，Python 2 对非 ASCII 源文件很敏感） |
| 游戏内敲 `rcon spw` 回 `unknown command` | 你还没 `rcon login <密码>`；或 `sv.rconPassword` 没配 |
| 回 `spawn: cannot read your position` | 你从 TCP rcon 或本地控制台敲的 —— **必须在游戏内敲** |
| `spwdump` 什么也没列 | 半径太小 → `rcon spwdump 400`；或 `getTemplateProperty` 不被支持 → 用 `rcon spwraw` 看原生输出 |
| `spw` 三种方言都说 no change | 模板名不对。用 `spwdump` 取一个**确实存在**的名字再来 |
| 服务器直接崩了 | 大概率是某个对象在你操作时已经失效（`isValid()` 为 0）。记录你敲到哪一条崩的，把那条命令去掉再试 |

崩溃是正常的探索成本，**但请在同一张图上、一次只改一件事**，这样才知道是哪条命令的问题。

---

## 配套：实时 Python REPL（强烈建议装）

bf2tech 的 EvalPy 是个通过 RCON 注入的**实时 Python 解释器**，装法和本工具完全一样，调试时省掉无数次重启：

`<bf2server>\admin\standard_admin\eval.py`（原作者 dackz，bf2tech 存档原文）：

```python
# script for eval()ing python code over rcon
import sys
import new
import default
import bf2
import host
import game
import standard_admin
from bf2 import g_debug

def write(self, text):
    self.write_original(str(text))

def rcmd_eval(self, ctx, cmd):
    try:
        eval(compile(cmd, '<string>', 'exec'))
    except:
        ctx.write(str(sys.exc_info()[0]).split('.')[-1] + ': ' + str(sys.exc_info()[1]) + '\n')

def init():
    if g_debug:
        print 'initialising eval script'
    default.CommandContext.write_original = default.CommandContext.write
    newMethod = new.instancemethod(write, None, default.CommandContext)
    default.CommandContext.write = newMethod
    newMethod = new.instancemethod(rcmd_eval, default.server, default.AdminServer)
    default.AdminServer.rcmd_eval = newMethod
    default.server.rcon_cmds['eval'] = default.AdminServer.rcmd_eval
    host.rcon_invoke('echo "eval.py loaded"')
```

在 `__init__.py` 里加 `import eval` / `eval.init()`，然后用**外部 RCON 客户端**（本地控制台不行）敲：

```
eval for i in dir(bf2.objectManager.getObjectsOfTemplate('c4_explosives')[0]): ctx.write(str(i) + '\n')
```

就能在运行中的服务器里随便试 API。**⚠️ 注意**：给 `ctx.write()` 传非字符串会让 RCON 连接死掉，永远用 `ctx.write(str(x))`。

---

## 这套东西的硬边界（先把话说死）

`GeometryTemplate.create` 的官方注释是 *"from the geometry mesh name"* —— **它必须已经有一个 mesh 才能建模板**。它能防止重复 mesh，但**不能凭空造 mesh，更不能把 mesh 推给客户端**。

所以：

- ✅ 用**客户端已有**的模板做：复制、批量生成、挪位置、改朝向、删掉 —— 全部可行，客户端一行不用改
- ❌ 让客户端显示**它没有的模型** —— 不可行

你十年前看到的那些服务器（旗杆挪位、建筑围基地、原版零件拼的炮塔），全部落在 ✅ 这一侧。

---

## 佐证文件

同工作区 `bf2tech-archive/` 内是本工具所有论断的原始快照（纯文本）：

| 文件 | 内容 |
|---|---|
| `BF2_Console_Commands.txt` | 引擎控制台命令全表（约 6500 行）—— `Object.*` / `ObjectTemplate.*` / `GeometryTemplate.*` |
| `Object_Reference.txt` | Python API 权威参考（`sendClientCommand` 真定义在 L338） |
| `Console_Script_Grammar.txt` | `.con` 脚本语法（`include` / `run` / 变量规则） |
| `Scripts-EvalPy.txt` | 上面的实时 REPL 原文 |
| `Scripts-ReserveSlots.txt` | 管理模块全文 —— `ctx.player` / `ctx.socket` 约定出处（L760-781） |
| `Scripts-Player_Position_Display.txt` | 官方式的坐标采集工具，输出格式同 `GamePlayObjects.con` |
| `Cookbook-Adding_New_RCon_Commands.txt` | `default.server.rcon_cmds[...]` 注册机制 |
