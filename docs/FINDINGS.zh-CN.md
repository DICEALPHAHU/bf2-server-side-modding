# BF2 服务端动态生成建筑 —— 调查归档

**日期**：2026-09-18
**结论**：原版 BF2（客户端 + 服务端 1.5.3153）**架构上不支持**服务端在运行时或加载时改变客户端看到的建筑。

---

## 一句话总结

> **客户端的建筑几何体烘焙在本地 `client.zip\terraindata.raw` 里（44MB），
> 且原版 BF2 客户端在联机时根本不启动 Python 解释器。
> 因此服务端的任何改动都无法影响客户端渲染的建筑。**

---

## 核心实验证据

在 `Dalian_Plant`（纯原版图，客户端与服务端 `client.zip` 哈希完全一致）上做的实验：

| # | 实验 | 服务端结果 | 客户端结果 |
|---|---|---|---|
| 1 | 运行时 `Object.create woodencrate_4m` | ✅ `12→13`，返回 `id36117` | ❌ 什么都不显示 |
| 2 | 运行时移动已有物件 | ✅ readback 坐标确认 | ❌ 模型留在原位 |
| 3 | 运行时删除物件 | ✅ 计数下降 | ❌ 照样显示 |
| 4 | 可见性开关（`setActive`/`setIsVisibleRecursive`/`start`/`initGrid`） | ✅ 接受 | ❌ 全部无效 |
| 5 | 改 `StaticObjects.con` 挪厂房位置 | ✅ `spwfind` 报 `775/252/20` | ❌ 仍显示在 `-59/176/-269` |
| 6 | **从 `StaticObjects.con` 彻底删除厂房** | ✅ `907→906` | ❌ **照样显示** |
| 7 | 加载时增加 3 座冷却塔实例 | ✅ `907→910` | ❌ 不显示 |
| 8 | `DestroyableObject` 类（`c_NIGhostAlways`） | ✅ 创建成功 | ❌ 不显示 |
| 9 | `mountArchive` 挂载新物件 | — | 💥 客户端崩 `NetworkManager.cpp:233` |
| 10 | 地图包内放 Python（8 个位置探针） | ❌ 无一执行 | ❌ 无一执行 |
| 11 | **服务端 `python/bf2/*` + `gpm_cq.py`** | ✅ **全部加载，`init()` 执行** | ❌ **完全不加载** |
| 12 | 客户端联机时 Python 解释器 | — | ❌ **从未启动** |

**第 11、12 条是决定性的**：客户端在联机模式下不运行 Python。

---

## 关键机制发现

### 1. 渲染与碰撞分离

用户观察到的现象完美印证：

- 移动厂房后 → 客户端**模型留在原位，碰撞跟着服务端走**（"幽灵厂房"）
- 删除厂房后 → 客户端**仍显示模型，但没有碰撞**

```
客户端建筑模型  ←  client.zip\terraindata.raw（烘焙，服务端改不了）
服务端碰撞      ←  server.zip + Python（服务端说了算）
```

### 2. 客户端不跑 Python

```
服务端 python/bf2/__init__.py      ✅ 加载
服务端 python/bf2/GameLogic.py     ✅ 加载
服务端 mods/bf2/python/.../gpm_cq.py init()  ✅ 执行

客户端 以上全部                     ❌ 一个都没有
```

### 3. 静态物件没有网络 ID

`Object.create` 返回的 `id36117` 只是**服务端本地对象 ID**，不是网络 ID。
引擎只为**载具/装备/玩法对象**生成网络 ID 并同步给客户端。

---

## 真实可用的命令清单（服务端侧）

见 `mod/spawn.py`，共 18 个 RCON 命令：

| 命令 | 作用 |
|---|---|
| `spwpos` | 显示自己坐标 |
| `spwfind <模板>` | 某物件在世界里的位置、离你多远 |
| `spwdiag` | 模组自检 |
| `spwdump [半径]` | 列出周围的物件模板名 |
| `spwtest` | 在头顶生成一个木箱 |
| `spw <模板>` | 生成物件 |
| `spwstack` / `spwbump` | 把物件搬到你面前（测试碰撞/渲染） |
| `spwmovetest` / `spwmoveback` | 移动/还原物件 |
| `spwdel` / `spwlist` / `spwraw` / `spl` / `spwenv` / `spwnet` / `spwrender` | 诊断用 |

**这些命令在服务端全部有效**，只是客户端看不见效果。

---

## 踩过的坑（对以后有用）

| 坑 | 教训 |
|---|---|
| **Python 2.3.4** | 服务端内嵌 Python，**不支持三元表达式、`sorted()`、`set()`、装饰器、`with`** |
| **`os` 模块被阉割** | 没有 `getcwd`/`path`/`listdir` |
| **非 ASCII 会炸** | 源文件必须纯 ASCII |
| **`+modPath` 不存在** | `bf2_w32ded.exe` 里没有这个参数 |
| **路径不能加引号** | 引擎命令行不解析引号，带空格路径要用 `cd` 切换工作目录 |
| **`rcon` 密码位置** | 在 `Admin/default.cfg`（不是 `sv.rconPassword`） |
| **`ctx.player`** | 游戏内 rcon 才有；TCP rcon 和本地控制台没有 |
| **`sendClientCommand`** | 是 UI 事件通道（如 `100=tkpunish`），**不是命令执行** |

---

## 当年的谜团：最可能的解释

用户明确记得：**拿原版 daqing_oilfields，进某个服，看到了额外建筑，而且没下载过任何东西。**

基于以上全部证据，只剩两种可能：

1. **那个服跑的是模组**，模组有自己的建筑，共用了原版地图名 → 玩家直连即可进入，建筑"本来就在"客户端文件里
2. **客户端的文件被替换过**（启动器/整合包）→ 用户不知情

**注意**：用户客户端装有 7 个 mod：`bf2, sandbox, SPMF, Time_War, xpack, [CHB], [MEW]`，
其中 **`sandbox`** 正是当年那位技术员提到的模组。答案可能就在其中。

---

## 如果未来要做，唯一可行的路

**改地图包（`client.zip` + `server.zip` 同步），让玩家下载。**

- ✅ 完全可行，这就是用户已有那三张自定义地图的做法
  （`Camp_BMK`、`Dalian_2_v_2`、`daqing_2_v_2`）
- ⚠️ **两边必须严格同步**，否则产生"幽灵建筑"（模型与碰撞不一致）
- 工具建议：改一次 → 自动打进两个 zip → 逐字节校验

---

## 归档内容

```
bf2-archive/
├── CONCLUSION.md          本文档（结论与证据）
├── USAGE.md               ★ RCON 命令使用说明（安装 / 命令参考 / 注意事项）
├── mod/
│   ├── spawn.py           18 个 RCON 命令的完整模组（Python 2.3 兼容）
│   └── zzdoctor.py        加载诊断 + 语法预检
├── scripts/
│   ├── build_mount_test.py    mountArchive 测试构建器
│   ├── test_gpm_probe.py      gpm_cq.py 探针
│   ├── test_map_python.py     地图包 Python 探针
│   ├── test_python_engine.py  客户端/服务端 Python 引擎探针
│   ├── RUN-SERVER.bat         带日志的服务端启动脚本
│   └── README.md              测试模组使用手册
├── logs/                  实测日志（证据）
└── bf2tech-archive/       bf2tech wiki 存档 34 个文件
    ├── BF2_Console_Commands.txt   引擎控制台命令全表（6500 行）
    ├── Object_Reference.txt       Python API 权威参考
    └── ...
```

---

## 参考链接

- [BF2 引擎控制台命令（object / Object.create）](https://realitymod.gitlab.io/public/RealityDocs/technical/modding/console/objects/object.html)
- [Python API：BF2 Host（rcon_invoke）](https://realitymod.gitlab.io/public/RealityDocs/technical/python/reference/bf2host.html)
- [Python API：BF2 Objects](https://realitymod.gitlab.io/public/RealityDocs/technical/python/reference/bf2objects.html)
- [PR 论坛：[Coding] Server-side modding](https://forum.realitymod.org/viewtopic.php?t=134409)
- [Extending BF2 Python API](https://alontavor.github.io/ExtendingBF2Python/)
- bf2tech 原站已死，存档见 `bf2tech-archive/`
  （抓取方式：`http://web.archive.org/cdx/search/cdx?url=...` + `http://web.archive.org/web/<时间戳>id_/<URL>`）
