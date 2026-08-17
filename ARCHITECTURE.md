# AstronRPA 项目架构解析

> 生成日期：2026-08-16 ｜ 基于当前 main 分支实际目录结构 + 近期批次开发实践
> 配套文档：DEV_PLAN.md（开发计划）｜MISSING_FEATURES.md（断点清单）｜LESSONS_LEARNED.md（经验库）

---

## 一、Monorepo 总览

```
astron-rpa/
├── backend/          # 混合栈微服务（3 Java Spring：robot-service/rpa-auth/resource-service + 2 Python FastAPI：ai-service/openapi-service）
├── engine/           # Python 引擎（uv 工作区）：执行内核 + 原子组件 + 常驻服务
│   ├── main.py / meta_json.py
│   ├── components/   # 27 个原子组件（独立 uv 项目，可独立安装）
│   ├── servers/      # 6 个常驻服务（executor/scheduler/trigger/picker/vision-picker/browser-bridge）
│   └── shared/       # 7 个共享库（actionlib/baseline/locator/websocket-client/websocket-server/workflowlib/browser-plugin）
├── frontend/         # pnpm monorepo（web-app/electron-app/browser-plugin/cli/components/shared/auth-app）
├── docker/           # docker-compose 编排 + 数据卷
├── makefiles/        # 构建 make 体系（go/java/python/typescript/common/git）
├── tools/            # 内部工具脚本（sync_atom_sql.py / mount_atom_tree.py）
├── resources/        # 打包资源（含内置 Appium server）
└── docs/             # 文档
```

**技术栈分层**：
| 层 | 技术 | 说明 |
|---|---|---|
| 编辑器 | TypeScript/Vue3（web-app） | 流程编排、原子表单渲染、分类树 |
| 桌面宿主 | Electron（electron-app） | 引擎拉起、内置 Appium、打包安装包 |
| 浏览器通道 | Chrome MV3 插件（browser-plugin） | CDP debugger + contentInject 双路径 |
| 引擎 | Python 3（uv 管理） | 原子执行、流程调度 |
| 服务端 | Java Spring ×3 + Python FastAPI ×2（backend） | 应用管理/鉴权/资源 + AI 网关/OpenAPI(含 MCP) |
| 数据 | MySQL（c_atom_meta_new 等表）+ Docker | 原子元数据、流程存储 |

### 1.1 全局架构图（端到端）

```
╔════════════════════ 桌面端·本地环（electron 分发，可离线） ════════════════════╗
║                                                                                ║
║  web-app (Vue3 编辑器，electron 窗口)                                           ║
║    │ HTTP /scheduler/*（执行控制/拾取/终端） + ws/sse（日志/进度/调试）           ║
║    ▼                                                                           ║
║  scheduler 本地网关 :13159（引擎根服务，electron spawn 拉起）                     ║
║    ├─ /scheduler/*      执行控制·trigger 的 gateway_client 也走此路由             ║
║    ├─ /browser_connector/*  浏览器指令转发（插件 ws 出口）                        ║
║    ├─ 子服务：executor（流程编译→Python+bdb 执行）/ trigger / picker             ║
║    │          / vision-picker / LSP / venv·pip / datatable                      ║
║    └─ browser-bridge（FastAPI，独立:19082 或挂 13159）                          ║
║         │ ws（rpa_websocket.js）                                                ║
║         ▼                                                                       ║
║  browser-plugin（Chrome CDP / Firefox content-script 双路径）──► 浏览器/iframe   ║
║                                                                                ║
║  executor 执行时 import 27 原子组件（uv 单 venv editable 全家桶）                ║
║    └─ browser 组件 → send_browser_extension → HTTP → /browser_connector/* ──┘   ║
╚════════════════════════════════════════════════════════════════════════════════╝
        │ 登录(casdoor) / 元数据同步 / 应用市场 / 云端调度下发（RobotExecute）
        ▼
╔════════════════════ 云端环（docker-compose 编排） ═══════════════════════════════╗
║  openresty :32742（lua auth_handler 前置鉴权）                                   ║
║    ├─ /api/robot/*          robot-service :8040（Java：c_atom_meta_new API 宿主 ║
║    │                         /RobotExecute 下发/市场/配额/MQ listener）          ║
║    ├─ /api/rpa-ai-service/* ai-service :8010（FastAPI：LLM 代理·OCR·打码·        ║
║    │                         智能组件·computer_use·积分计费）                     ║
║    ├─ /api/rpa-openapi/*    openapi-service :8020（FastAPI：REST+WS+MCP）        ║
║    ├─ /api/resource/*       resource-service :8030（Java：文件+MinIO）           ║
║    ├─ /api/rpa-auth/*       rpa-auth :10251（Java：SSO 四 IdP+RBAC）             ║
║    └─ /api/casdoor/*        casdoor :8000                                       ║
║  基础设施：mysql:8.4.6(+atlas 迁移) / redis / minio / rpa-opensource-network      ║
╚════════════════════════════════════════════════════════════════════════════════╝
```

细节图：执行管线见 3.1 ｜ 浏览器插件内部见 4.1 ｜ 部署拓扑详见 6.6 ｜ 元数据流水线见 2.4

---

## 二、架构核心：原子（Atomic）体系

整个产品的一切功能都归结为"**原子（指令）**"这一唯一抽象。核心链路：

```
Python 组件源码(@atomic装饰器)
  → meta.json（组件自描述）
  → SQL c_atom_meta_new 表（服务端元数据）
  → atomicTree/atomicTreeExtend（分类树挂载）
  → 编辑器指令面板（用户拖拽）
  → 引擎 executor 按流程逐行执行原子
```

### 2.1 actionlib——原子的定义框架（engine/shared/astronverse-actionlib）

关键机制：
- **`@atomicMg.atomic(group, inputList, outputList)` 装饰器**：把静态方法注册为原子；`group` 是逻辑分组（如 "Database"/"Phone"）
- **`atomicMg.param(key, types, formType, required)`**：参数元数据。**枚举 options 的识别依赖函数签名的类型注解**（裸 `param("x")` + 无注解 → 纯文本输入；`x: SomeEnum = ...` → RADIO+options 下拉）——这是最核心也最易错的机制
- **`AtomicFormType`**：表单控件类型枚举（INPUT_VARIABLE_PYTHON / TEXTAREAMODAL / PICK / RADIO...），决定编辑器渲染
- **types_manager / types**：跨组件对象类型注册（如 PhoneObject/PhoneElement/DocumentObject），供参数类型选择器引用
- **humansim**：拟人模拟区间（human_sim_start/end 激活，鼠标键盘自动加随机轨迹）

### 2.2 组件标准结构（27 个组件完全一致）

```
engine/components/astronverse-<name>/
├── pyproject.toml      # 独立 uv 项目，声明依赖（uv sync 自动建 .venv）
├── config.yaml         # 原子 UI 元数据：title/comment/icon/tip/helpManual + options 枚举label
├── meta.py             # 注册入口：register(Class) → meta() 生成 meta.json
├── meta.json           # 产物：原子全量元数据（同步 SQL 的唯一来源）
└── src/astronverse/<name>/
    ├── __init__.py     # 枚举定义（ClickType/FileType/...）
    ├── <功能>.py        # 原子实现（静态方法 + 装饰器）
    └── error.py        # ErrorCode 消息（baseline BizCode + i18n _()）
```

**config.yaml 与代码的分工**：代码定义参数结构（key/类型/formType），yaml 定义展示文案（title/tip/helpManual）和枚举中文 label（`options:` 段按枚举类名索引）。

### 2.3 组件清单（27 个，按能力域）

| 域 | 组件 | 代表能力 |
|---|---|---|
| 数据处理 | dataprocess / datatable / excel | 文本/列表/字典/时间/数学；Excel openpyxl+COM |
| 文档 | pdf / word / kdocs | PDF 7原子、Word、WPS AirScript（js 脚本随发版分发） |
| 自动化-桌面 | software / window / winelement / system / input | Win32/UIA 元素、系统操作、键鼠 |
| 自动化-Web | browser / network | 56 原子、SFTP/FTP/HTTP、curl 解析 |
| 自动化-移动 | phone | uiautomator2 直连 + Appium 双模式（24 操作 duck-typing 分发） |
| 视觉 | vision / verifycode / cua | 模板匹配/OCR/点击、验证码、ComputerUse |
| 交互 | dialog / input / report | 弹窗/输入框/报表 |
| 数据库 | database | pyodbc ODBC + SQLite3 |
| 集成 | email / encrypt / ai / openapi / enterprise / smart / script | 邮件、加解密、AI、开放接口、脚本 |

### 2.4 元数据流水线（新增原子的必经之路）

1. **meta.json 生成**：`cd <组件> && uv run python /tmp/gen_meta_stub.py`（stub 掉平台依赖模块；**pyautogui stub 缺失会导致静默失败保留旧 meta**）
2. **SQL 同步**：`tools/sync_atom_sql.py` —— 从 meta.json 生成 `c_atom_meta_new` 行。**转义铁律**：`ensure_ascii=False` 裸中文 + `\` 双写 + `'` 双写（生产 MySQL 默认 sql_mode，反斜杠是转义符）
3. **分类树挂载**：`tools/mount_atom_tree.py` —— 改 atomCommon 行(id=19) 的 atomicTree JSON。**必须纯字符串手术不做 JSON 往返**；同 key 原子出现在多分组时必须"分组边界定位+倒序插入"
4. **容器验证**：mysql:8.4 全量导入 → `JSON_VALID` 全过 + 中文 title 正确 + 挂载点命中（**必须用 SQL 内 JSON 函数验证，TSV 导出会假性崩**）

---

## 三、引擎执行架构

### 3.1 执行模型：流程编译成 Python + bdb 调试（最核心机制）

executor 不是解释器，而是**编译器**——把流程 JSON 编译成真正的 Python 源码再执行（engine/servers/astronverse-executor/src/astronverse/executor/flow/）：

```
storage.process_detail（流程行 JSON）
  → Lexer（行→Token）→ Parser（→AST：Program/Block/Atomic/If/Try/For/While 节点）
  → AST.display(svc)（各节点递归自生成 CodeLine{tab缩进, code, 流程行号}）
  → 产物：main.py / processN.py / moduleN.py / smartN.py
          + 同名 .map 文件（"py行号:流程行号" 逗号串）
          + package.py（tpl/package.tpl 模板：运行时辅助层）
          + package.json（AST 收集的全局信息序列化）
  → CustomBdb（debug/bdb.py）以调试器身份执行 main.py
```

关键设计：
- **Atomic 节点**生成 `src(args...)` 调用语句（src = meta 的模块.函数路径）并自动补 import；高级参数 `__skip_err__`（exit/retry/skip）在**生成期**包装出 try/except/while-retry 代码块；**debug 模式剥掉全部包装**（异常自由传播才命中断点）
- **.map 是断点调试的桥梁**：CustomBdb 继承标准库 `bdb.Bdb`，加载全部 .map 建立 py行↔流程行 双向映射——断点按流程行号下发，`_to_py_lines` 展开为多个 Python 行；`threading.Event` 实现暂停/继续，`_force_stop` 强停
- **package.py 运行时辅助层**：`element(id)` 经 HttpStorage（连 gateway_port）拉元素详情转 Pick 对象；`module()/component()/smart_component()` 做文件名解析；`gv` 全局变量字典；`complex_param_parser` 复杂参数求值
- main.py 骨架：`from .package import element, module, component, gv, ...` + `def main(args):`（参数解包 → try/finally，finally 回写输出参数到 args）
- `start.py`：flow_start 按版本号比对决定是否重新生成；debug_start 起 Ws（日志/toast 通道）+ 录制服务 + 右下角日志窗；`TerminateAppSignal`（继承 builtins.BaseException）穿透流程 Try 实现 CANCEL

### 3.2 atomic_run：原子的运行时包装（shared/astronverse-actionlib/atomic.py）

每个原子调用实际经过 `atomicMg.atomic_run`：
1. **无 `__info__` 直接透传**（手工/测试调用零开销）
2. 上报 `ReportCode.START`（process_id/line/key）；外部重试包装时以 `__in_external_retry__=True` 抑制重复上报
3. `ParamModel` 验证+类型转换（model_cache 缓存参数模型，超限整体 gc 重建）
4. `delay_before/after` 拟人延时、`__res_print__` 上报结果
5. 无 `**kwargs` 的原子按函数签名过滤多余参数（向后兼容）

### 3.3 六个常驻服务（servers/，职责以实测代码为准）

| 服务 | 职责 |
|---|---|
| scheduler | **引擎根入口**（engine/main.py 即启 scheduler；electron 拉起的也是它）。除定时调度外还含：core/setup（运行环境/venv/pip 管理）、core/lsp（编辑器 Python 补全的 LSP 客户端）、core/executor（执行器拉起 + virtual_desk 虚拟桌面）、core/datatable（excel_service + file_watcher）、picker 高亮（win/linux RPAHighlighter）。web-app 的 `/scheduler/*` HTTP API 全落在这 |
| executor | 3.1 的编译执行内核；debug/apis/ws 提供调试 ws 通道、debug/recording 执行录屏 |
| trigger | 触发器任务族：tasks/{scheduled,mail,hotkey,file}_task + server/gateway_client（与云端网关交互）+ core/queue_manager |
| picker | 元素拾取：strategy/（manager + uia/msaa/web/auto_desk/auto_web 多策略分发）+ engines/（uia/web/msaa/smart_component 各引擎）+ server/ws_server；编辑器选元素回填 WinPick/WebPick |
| vision-picker | 视觉拾取：core/{cv_match,cv_picker,core_win,core_unix}（模板匹配选点，跨平台两套实现） |
| browser-bridge | FastAPI(:19082)：`/browser_connector/browser/transition` 接引擎 HTTP 转发指令至浏览器插件（ws_route）；5001~5004 错误码契约（通信错/元素未找到/执行错/通用） |

### 3.4 shared 七库

| 库 | 职责 |
|---|---|
| actionlib | @atomic 装饰器 / atomic_run / param 元数据 / types_manager / humansim（见 2.1） |
| baseline | ErrorCode/BizCode/i18n/配置加载——所有组件的异常与文案基座 |
| locator | WinPick/WebPick 元素定位数据结构 |
| workflowlib | 流程运行时：params(ComplexParamParser 复杂参数) / storage(HttpStorage 连网关拉元素流程数据) / report / consequence(错误后果处理) / helper / config |
| websocket-client/server | 引擎↔编辑器 ws 通道封装（ws_service/ws_client） |
| browser-plugin | **插件安装器**：win/reg.py 注册表 + chrome/firefox/edge/360/360x/chromium 各浏览器插件的发现与启停（unix 分支 firefox/chromium） |

### 3.5 uv 工作区聚合

engine/pyproject.toml 用 `[tool.uv.sources]` 把 7 shared + 6 servers + 27 components 全部声明为 `path + editable`——**单一 .venv 共享全部模块**（根目录一次 `uv sync` 全局生效），服务/组件间互引就是普通 import；executor 的 .venv 里能看到全家族依赖即此缘故。

---

## 四、浏览器自动化链路（最复杂的跨端链路）

### 4.1 总体链路

```
web-app 编辑器（原子表单/元素拾取）
   ↕ HTTP /scheduler/*（engine.ts）+ ws/sse
electron-app（宿主：拉起 scheduler、内置 Appium）
   ↕
engine astronverse-browser 组件
   └── send_browser_extension(key, data)
        → HTTP POST http://127.0.0.1:{GATEWAY_PORT:-13159}/browser_connector/browser/transition
browser-bridge（FastAPI :19082，指令转发 + 5001~5004 错误码契约）
   ↕ ws（rpa_websocket.js）
browser-plugin（Chrome MV3 / Firefox MV2 双清单）
   ├── background：消息路由 + CDP debugger + frame 定位
   └── content：contentInject（frameId 标记 / Firefox JS 执行 / 高亮拾取）
```

**runJS 纪律**：JS 模板禁用 `str.format`（花括号冲突），一律 `__PLACEHOLDER__` 显式 replace + `json.dumps` 生成字面量注入。

### 4.2 browser-plugin 结构（frontend/packages/browser-plugin）

```
browser-plugin/
├── manifest.ts            # 构建期生成 manifest.json（Chrome/Firefox 双形态）
└── src/
    ├── background/        # service worker（核心逻辑全在这）
    │   ├── backgroundInject.ts  # 消息总路由：Handlers 字典分发引擎指令
    │   ├── debugger.ts    # CDP 核心：attach/frame 上下文/evaluate/网络监控
    │   ├── iframe.ts      # frame 定位：findTabAndFrame + 嵌套坐标计算
    │   ├── tab.ts         # tabs API 封装 + Chrome/Firefox 执行路径分发
    │   ├── network_monitor.ts  # 网络监控双实现（CDP Network / webRequest）
    │   ├── full_page_shot.ts   # CDP Emulation 全页/区域截图
    │   ├── cookie / dialog / data_table / similar / window / userScript / native
    │   └── constant.ts / utils.ts
    ├── content/contentInject.ts  # 内容脚本：frame 标记、Firefox eval 宿主、元素拾取
    ├── common/            # constant（ErrorMessage/StatusCode）/ utils（isFirefox）
    └── 3rd/               # rpa_websocket.js（与宿主的 ws 通信库）
```

**manifest.ts 双清单生成**：同一份基础 manifest，Firefox 分支降级为 MV2——剔除 `debugger` 权限、追加 `webRequest`/`webRequestBlocking`/`<all_urls>`、background 改 scripts 数组。**这是全插件"双模式适配"的根源：Firefox 无 CDP，一切 debugger 路径必须有 content script 替代**。

### 4.3 消息路由（backgroundInject.ts）

引擎/前端指令统一走 `Handlers` 字典（`tabsHandler`/`jsHandler`/`networkHandler`...）按 key 分发。元素类指令先经 `findTabAndFrame` 解析目标：

```
findTabAndFrame(params)
  ├─ isFrame=false → { tab, frameId: 0 }（主 frame 直通）
  └─ isFrame=true  → getAllFrames + frameFinder(tab, frames, params)
        ├─ checkType=visualization：iframePathDirs 逐级目录匹配
        └─ iframeXpath：按 '/$iframe$' 分隔符切段，沿 parentFrameId 链
           从根 frame(frameId=0) 逐层向下匹配
```

`jsHandler().runJS` 拿到 frameId 后交 `Tabs.runJS` 执行；失败统一 `Utils.fail` 包装。content script → background 方向另有 `contentMessageHandler`（element 拾取回填 / requestFrameId / keepBackgroundAlive）。

### 4.4 CDP 核心（debugger.ts）——frame 跨域执行的关键

**frame 执行上下文采集（frameContextIdMap 双通道）**：

| 通道 | 机制 | 采集来源 |
|---|---|---|
| 同域 frame | content script 注入后 `console.log('rpa_debugger_on:<frameId>')`，background 监听 `Runtime.consoleAPICalled` 反查 `executionContextId` | contentInject.ts |
| 跨域 frame | `Target.setAutoAttach(flatten)` → `Target.attachedToTarget` 事件 → 在子 target session 内 evaluate 读取 `document.documentElement.dataset.astronFrameId`（content script 预先打在 DOM 上的标记） | debugger.ts `handleAttachedTarget` |

同域通道存 `{target, contextId}`（可定向 evaluate）；跨域通道存 `{target: session, contextId: null}`（用 session 默认上下文执行）。

**evaluate 执行模型**：代码包一层 `(async function(){ ... })()` + `awaitPromise: true`（同步/异步统一）；对目标 frameId 的**所有**注册上下文 `Promise.all` 并发执行，取首个无 `exceptionDetails` 的结果——容忍部分上下文失效。前置链：`attachDebugger → Runtime.enable → setupAutoAttach`，单例状态（`attached`/`tabId`），detach 时全量重置 frameContextIdMap。

### 4.5 双浏览器执行路径（tab.ts）

```
runJS(tabId, frameId, params)
  ├─ Chrome ：Debugger.evaluate（CDP，见 4.4）
  └─ Firefox：sendTabFrameMessage → contentInject 的 window.handleSync
              → eval(message.data.code)（同步 eval，靠 MV2 CSP unsafe-eval）
```

其余能力同理成对：截图（CDP Page.captureScreenshot vs browser.tabs.captureTab+rect）、网络监控（CDP Network 域 vs webRequest.filterResponseData 流式截获响应体，Firefox 对 204/304/3xx 跳过 filter 避免 NS_ERROR_FAILURE）。

### 4.6 CDP 能力全景（除 evaluate 外）

| 能力 | CDP 命令 | 备注 |
|---|---|---|
| 网络监控 | Network.enable → requestWillBeSent/responseReceived/loadingFinished + getResponseBody | 过滤器 urlPattern/pathPattern/method 正则匹配 |
| 全页截图 | Page.getLayoutMetrics → Emulation.setDeviceMetricsOverride(撑满内容尺寸) → Page.captureScreenshot → clearDeviceMetricsOverride | 白底覆盖，attach/detach 一次性 |
| 区域截图 | 同上 + content script 取 devicePixelRatio 换算 CSS 像素 | |
| DOM 快照 | DOMSnapshot.captureSnapshot(includeDOMRects) | |
| 导出 PDF | Page.printToPDF | |

### 4.7 引擎侧对接缺口（M10 结论）

插件已具备完整 frame 路由能力，**缺口在引擎**：astronverse-browser 组件原子（run_js 等）调 `send_browser_extension` 时未构造 `isFrame`/`iframeXpath`/`iframePathDirs` 参数 → bridge 原样透传 → 插件 `findTabAndFrame` 恒走主 frame 分支，跨域能力闲置。补参数传递即可激活，无需改插件与 bridge（data 字典整体透传，加字段零成本）。

---

## 五、前端结构（frontend/，pnpm monorepo "iflyrpa"）

### 5.1 工程体系

- pnpm>=9 + Node>=22（volta 锁 22.15）；workspace 含 `locales` 独立包 + `packages/*`
- **catalog: 协议**统一版本（pnpm-workspace.yaml）：vue 3.5 / vite 8beta / ant-design-vue 4.2 / tailwind 等
- 质量三件：@antfu/eslint-config（扁平 eslint.config.mjs）、vitest、@lobehub/i18n-cli（`pnpm i18n` 提取翻译，locales/en-US.json + zh-CN.json）
- 环境分身：web-app 的 `.env.saas/.env.enterprise/.env.opensource` + 根脚本 `set-env:*` 切换构建形态

### 5.2 web-app——主编辑器（**Vue 3**，非 React）

技术栈：Vue 3 + Vite + Pinia + ant-design-vue + vxe-table（流程表格）+ tiptap（富文本）+ tailwind + i18next + @module-federation/enhanced（微前端，对接市场/组件）+ Sentry。

```
src/
├── api/          # 按域分文件：atom/engine/executor/pick/project/robot... + http/sse/ws 三通道
├── ast/          # ASTNode + IncrementalASTParser（前端流程 AST：扁平行→树，脏队列+rAF 批量更新）
├── stores/       # 21 个 Pinia store：Flow/Elements/Variable/Running/Pick/CvPick/BatchPick/SmartCompPick/PythonPackage/Market...
├── views/        # Arrange（编排主页）/ Batch / Record / MultiChat / SmartCompPickMenu / UserForm / Log / Home
│   └── Arrange/components/：atomTree（原子分类树）/ atomForm（原子表单）/ flow（画布）
│                          / pick / variableManage / bottomTools / rightTab / triggerInsert...
├── platform/ corobot/ worker/ plugins/ router/ hooks/ utils/
```

关键机制：
- **前后端双 AST**：前端 IncrementalASTParser 负责编辑态结构化（容器/结束标记配对成树、增量更新）；引擎 Lexer/Parser 负责执行态（生成 Python）。两侧数据同源（流程行 JSON），职责不同
- **createUserFormItem.tsx**（views/Arrange/components/customDialog/hooks/）：按 meta.json 的 formType 映射 antd 控件——与 2.1 的 AtomicFormType 枚举一一对应，编辑器零代码适配新原子
- 引擎交互全走 HTTP `/scheduler/*`（api/engine.ts：picker 启停、terminal 调度模式、executor 控制、凭证管理）+ ws/sse 双实时通道
- 运行态：useRunningStore 对应引擎 ws 的 send_notification/日志流

### 5.3 electron-app——桌面宿主（包名 astron-rpa，版本即发版 tag 源）

Electron 25 + electron-vite + electron-builder（win/win32-ia32/mac/linux 四目标，`build:sdk` 用 tsdown 预打包 sdk）。

主进程 src/main/ 模块化：`server.ts`（**拉起引擎**：`spawn(pythonExe, ['-m', SCHEDULER_NAME, '--conf=...'])`；ps/tasklist 探活防重复启动；`--stop=True` 优雅关停；scheduler-event 向渲染层推启动进度）、`appium.ts`（**内置 Appium**：`spawn(process.execPath, [main.js], {ELECTRON_RUN_AS_NODE:'1'})` 复用 Electron 的 Node 跑 appium、GET /status 探活、4723 端口与 Python 端 Phone.connect 默认值对齐、tree-kill 清理）、`extension.ts`（插件注册）、`updater.ts`（electron-updater 自动更新）、`tray.ts / window.ts / file.ts(7z 解压) / event.ts(IPC)`。

### 5.4 其余包

| 包 | 职责 |
|---|---|
| browser-plugin | MV3/MV2 双清单插件（见第四节；tsc 严格门禁，预存 6 个 mock 测试失败为基线噪音） |
| cli | `rpa` 命令（cac + @clack/prompts）：dev/build 构建服务器 + **create 插件脚手架**（内置模板渲染）——面向插件/二次开发者，非发版工具 |
| components | 共享 UI 组件库：theme/useTheme 主题体系 + tokens（style-dictionary 构建）+ iconpark |
| shared | 类型与平台抽象（types/global、types/platform）——electron 与 web 共用的边界类型 |
| auth-app | 独立 Vue 3 登录应用（Vue Router + tailwind，配合 casdoor） |
| locales（frontend 根） | i18n 文案包（en-US/zh-CN），lobe-i18n 自动提取 |

---

## 六、服务端与部署

### 6.1 backend 五服务——**3 Java + 2 Python**（混合栈，非全 Java）

| 服务 | 技术栈 | 端口/context | 职责 |
|---|---|---|---|
| robot-service | Java Spring（bootstrap.yml=Spring Cloud，服务名 robot） | :8040 `/api/robot` | 核心业务中台（见 6.2） |
| rpa-auth | Java Spring | :10251 `/api/rpa-auth` | SSO 鉴权 + RBAC（见 6.3） |
| resource-service | Java Spring | :8030 `/api/resource` | 文件资源服务（file 包：上传/管理，配 MinIO） |
| ai-service | **Python FastAPI**（uv 管理，app/ 分层） | :8010 `/api/rpa-ai-service` | AI 能力网关（见 6.4） |
| openapi-service | **Python FastAPI** | :8020 `/api/rpa-openapi` | 对外开放 API 三形态：REST + WebSocket + **MCP**（见 6.5） |

Java 三件套走 Maven + checkstyle/pmd/spotbugs 门禁；Python 双服务自带 pytest（tests/）+ RequestTracingMiddleware。

### 6.2 robot-service（com.iflytek.rpa，40 个 Controller 按域分包）

- **base/——元数据核心**：`CAtomMetaNewController`（**c_atom_meta_new 表的 API 宿主**，2.4 流水线的服务端落点）+ CAtom/CProcess/CElement/CGlobalVar/CModule/CParam/CSmartComponent——流程/元素/变量/模块全元数据 CRUD；ClientVersionUpdateController 管客户端强升
- **robot/**：RobotDesign（设计态）/RobotExecute（执行下发）/RobotExecuteRecord/RobotVersion/SharedFile/SharedVar
- **调度族**：task/（ScheduleTask 定时三件套）+ triggerTask/（TriggerTask + TaskMail）+ dispatch/（DispatchTask + **listener 包=MQ 监听**）
- **market/**：应用市场六件套（App/Classification/Invite/Resource/Team/User）
- 其他：quota（配额）、notify（通知发送）、feedback、terminal（终端管理）、monitor（无 Controller，dao 供内部）、agent + astronAgent（**两代 AI Agent 入口**）、component/（组件市场：版本/使用统计/屏蔽）

### 6.3 rpa-auth——多 IdP SSO + RBAC

- **idp/ 四身份提供者适配**：casdoorIdentity（开源默认）/ iflytekIdentity（内部）/ uapIdentity / enterpriseIdentity——企业版可插拔换身份源
- **sp/casdoor/**：casdoor 服务代理（登录 DTO/过滤器/DAO），docker 编排内置 casdoor v2.67.0 :8000
- **core/controller**：Auth/UserManage/Role/Resource/DataAuth——RBAC + 数据权限
- 辅助：auditRecord（审计留痕）、blacklist（令牌黑名单）、dataPreheater（预热）

### 6.4 ai-service（app/ 标准分层：routers/schemas/services/models/utils）

六路由：ocr（OCR 识别）、chat + models（**OpenAI 兼容 /v1**，代理多家 LLM）、jfbym（打码平台对接）、smart_component（智能组件生成/执行）、computer_use（ComputerUse 视觉操作）、admin。models/ 含 **point.py 积分计费** + smart_component.py——AI 用量计量闭环。

### 6.5 openapi-service——"RPA OpenAPI" v1.2.0

routers：workflows / executions / api_keys（API Key 签发）/ user / healthcheck / websocket（**WsManagerService 单例**，多 worker 进程间会话管理）。`app.mount("/mcp", handle_streamable_http)`——**StreamableHTTP MCP Server**（session_manager 会话管理 + tools_config 动态工具连接），AI Agent 可经 MCP 直接编排 RPA 流程；nginx 对 `/api/rpa-openapi/mcp`（带/不带斜杠）与 `/ws` 有专用 location。

### 6.6 部署拓扑——本地环 / 云端环双网关

```
本地环（桌面）：web-app(electron) → HTTP → scheduler 本地网关(:13159)
              /scheduler/*（执行控制）+ /browser_connector/*（插件转发）
              scheduler 拉起 executor/trigger/picker/browser-bridge 子服务
云端环（docker）：openresty(:32742→80) ─┬→ /api/robot/*       robot-service:8040
                                        ├→ /api/rpa-ai-service ai-service:8010
                                        ├→ /api/rpa-openapi/* openapi-service:8020（含 MCP/ws 专用路由）
                                        ├→ /api/resource/*    resource-service:8030
                                        ├→ /api/rpa-auth/*    rpa-auth:10251
                                        └→ /api/casdoor/*     casdoor:8000
基础设施：mysql:8.4.6 + atlas（schema 迁移）+ redis + minio（对象存储）+ casdoor
```

- **gateway_port 的双重含义**：引擎组件的 `GATEWAY_PORT` 在桌面形态=本地 scheduler:13159（trigger 的 gateway_client 也走它调 `/scheduler/executor/*`）；云端形态由下发执行的 project_info 注入指向云端网关
- nginx lua：auth_handler.lua（鉴权前置）+ resty/http 工具链
- **MySQL**：`c_atom_meta_new` 为核心表（当前 588 数据行，id 至 972 已用，973 起待分配）；初始化 SQL 转义规范见 2.4
- **docker/**：全栈编排（细节见 6.7）
- **CI/CD**：`release-full-pipeline.yml`（QA 门禁→Build→Publish）；prerelease 由 tag 含 `-` 自动判定；**发版四资产**：Windows EXE、wps_read_sheet.js、server-snapshot-<tag>.tar.gz、SERVER-DEPLOY.txt

### 6.7 docker/ 编排细节

```
docker/
├── docker-compose.yml      # 全栈编排（11 服务）
├── .env.example / QUICK_START.md
├── scripts/hot-update-atom-meta.sh   # 原子表热更新
└── volumes/
    ├── mysql/    # schema.sql + init 四数据集（c_atom_meta_new/app_market_dict/his_data_enum/sample_template）+ my.cnf
    ├── atlas/    # atlas.hcl + schema.hcl（声明式 schema 期望态）
    ├── casdoor/  # init_data_dump.json（预置组织/应用）
    └── nginx/    # default.conf + lua/auth_handler.lua + resty/http 工具链
```

关键机制：
- **镜像策略**：统一 `ghcr.io/iflytek/astron-rpa/*`（build 段注释保留——默认拉远端镜像，改本地构建即取消注释）；env_file 用 YAML anchor（`*env_file`）一处定义全服务复用
- **健康检查门控**：业务服务 `depends_on` mysql/redis `service_healthy` + casdoor `service_started`——DB 未就绪不启服务；对外仅 nginx 32742 暴露，其余端口全注释、服务间走 `rpa-opensource-network` 内网互访；日志按 `./logs/<svc>` 落盘
- **atlas 声明式迁移**：atlas.hcl 的 `dev = "docker://mysql/8/dev"` 起沙箱库比对 schema.hcl 期望态与实际差异生成迁移（migrations 目录），替代手写 DDL
- **OpenResty lua 鉴权**（auth_handler.lua）：Authorization Bearer 直接放行交后端校验；SESSION/JSESSIONID cookie 则由 lua 用 resty.http 子请求调鉴权服务换票——会话态在网关层前置收敛
- **hot-update-atom-meta.sh**：利用"c_atom_meta_new 是纯参考数据表（用户数据不在此表）"的性质——先 mysqldump 全库备份，再按仓库 init SQL 在运行库重建该表，**不动数据卷、不清库、不停服务**

### 6.8 makefiles/ 多语言工具链（根 Makefile include 七个子件）

| 文件 | 目标族 |
|---|---|
| common.mk | 颜色/工具探测/project-status（自动识别已装语言栈） |
| go.mk | gofmt/staticcheck/gocyclo/golangci-lint（模板自带，本仓库暂无 Go 代码） |
| typescript.mk | eslint / tsc 类型检查（对应 frontend） |
| java.mk | checkstyle / pmd / spotbugs（对应 backend 三 Java 服务） |
| python.mk | **ruff format/check 管 engine + openapi-service 两个 uv 项目**（`uv run --project <dir> --dev ruff ...`） |
| git.mk（默认启用） | 分支规范：new-feature/new-fix（type/name 格式）、check-branch、safe-push、clean-branches |
| git-pr.mk（注释可选） | PR 管理：pr-list/pr-status/push-and-pr（需仓库写权限） |

- **hooks 族**：hooks-install（pre-commit 全量检查 + commit-msg 信息校验 + pre-push 分支名校验）/ hooks-install-basic（轻量）/ hooks-uninstall——本地提交门禁与 CI 同规则
- `make help` 由 grep `##` 注释自动生成目标清单；dev-setup 一键装全语言工具
- 质量门禁与 7.6 呼应：`make fmt-check`/`make check` 是全栈统一入口

---

## 七、开发风格与工程约定（从实践中沉淀）

1. **七步曲交付**：代码 → config.yaml → meta.json → mock 冒烟 → SQL → 树挂载 → 容器验证；每步完成即更新 MISSING_FEATURES.md 断点标记
2. **冒烟先行**：所有新原子写 `/tmp/smoke_*.py` mock 测试（paramiko 式 duck-typing mock；真 appium 包 patch webdriver.Remote 模式）；**测试必须传枚举成员而非字符串**（字符串静默不匹配分支）；**模板匹配测试禁用纯色图**（TM_CCOEFF_NORMED 零方差处处 1.0）
3. **平台隔离**：Windows 专用模块函数体内懒加载（win32com/win32print 等）；macOS 冒烟用 stub 清单（见经验库）；平台检查在模块顶层的组件冒烟时 stub 整个平台模块
4. **参数命名红线**：原子参数名禁用 `key`（与 atomic_run 位置参数冲突）；`press_key` 用 `key_name`
5. **迭代器原子**：翻页器/循环类返回 generator（`noAdvanced=True`），执行器恢复时机=页体处理完成
6. **质量门禁**：`make fmt-check`/`make check` 全栈入口（见 6.8）；Python 侧 `uv run --project engine --dev ruff format ./engine --check`（pinned ruff；check 的 900+ 错误是预存噪音；python.mk 同管 openapi-service）；web-app `pnpm tsc` 有 4 个预存错误
7. **SQL/树手术纪律**：见 2.4；atomCommon 行 sort='1' 非 NULL 是预存噪音勿"修"
8. **发版纪律**：无代码变更不发版；tag 三段式且与 electron package.json 严格一致

---

## 八、关键文件地图（改哪儿找哪儿）

| 目的 | 文件/目录 |
|---|---|
| 加新原子 | engine/components/astronverse-*/src/astronverse/*/*.py + config.yaml |
| 原子装饰器/参数机制 | engine/shared/astronverse-actionlib/src/astronverse/actionlib/atomic.py（atomic_run 见 3.2） |
| 异常/文案基座 | engine/shared/astronverse-baseline/src/astronverse/baseline/error/ |
| 执行入口/终止信号 | engine/servers/astronverse-executor/src/astronverse/executor/start.py、actionlib/error.py(TerminateAppSignal) |
| 流程编译器 | executor/flow/{flow.py, syntax/{lexer,parser,ast}.py, tpl/package.tpl}、debug/bdb.py（.map 行号映射） |
| 引擎根服务/宿主拉起 | engine/main.py（=scheduler）、frontend electron-app src/main/{server,appium}.ts |
| 本地网关（:13159） | scheduler core/servers/（/scheduler/* 执行控制 + /browser_connector/* 插件转发）+ trigger/server/gateway_client.py |
| 浏览器指令链 | engine components/astronverse-browser browser.py(send_browser_extension) → browser-bridge start.py/apis/ws_route.py → 插件 background |
| 原子元数据 API（服务端） | backend robot-service base/CAtomMetaNewController.java（c_atom_meta_new 表宿主） |
| 云端调度下发 | robot-service robot/RobotExecute*、task/、triggerTask/、dispatch/listener（MQ） |
| 对外开放 API / MCP | backend openapi-service app/main.py（/mcp StreamableHTTP mount）、routers/ |
| AI 能力/积分计费 | backend ai-service app/routers/{chat,models,ocr,jfbym,smart_component,computer_use}.py、models/point.py |
| SSO/身份源 | backend rpa-auth idp/（四 IdP）+ sp/casdoor/ + core/controller（RBAC） |
| SQL 同步/树挂载 | tools/sync_atom_sql.py、tools/mount_atom_tree.py |
| 初始化 SQL / 热更新 | docker/volumes/mysql/init-*.sql（当前 588 行）、docker/scripts/hot-update-atom-meta.sh |
| 编辑器表单渲染 | frontend/packages/web-app src/views/Arrange/components/customDialog/hooks/createUserFormItem.tsx |
| 前端流程 AST / 画布 | web-app src/ast/{ASTNode,IncrementalASTParser}.ts、src/views/Arrange/ |
| 插件 CDP 通道 | frontend/packages/browser-plugin src/background/{debugger.ts,iframe.ts}、content/contentInject.ts |
| 内置 Appium | resources/appium + electron 主进程拉起逻辑（ELECTRON_RUN_AS_NODE，:4723） |
| make 工具链 | 根 Makefile + makefiles/*.mk（`make help` 列全部目标） |
| 进度断点/计划/经验 | MISSING_FEATURES.md、DEV_PLAN.md、LESSONS_LEARNED.md |

---

## 九、架构评价（优势与债务）

**优势**：
- **编译式执行内核**（最亮眼设计）：流程编译成真 Python 源码 + `.map` 行号映射 + 标准库 bdb——用语言原生调试器白嫖断点/单步能力，执行性能即原生 Python；skip_err 在生成期包装，错误处理零运行时开销
- **策略分发已成家族模式**：phone（u2/appium duck-typing）、插件（Chrome CDP / Firefox content-script）、picker（uia/msaa/web 多策略 manager）——新目标端只需增加策略实现，原子层不动
- 原子抽象统一：27 组件一套装饰器/配置/元数据规范，新增能力边际成本低
- 元数据驱动前端：编辑器零代码适配新原子（表单/枚举全自动，createUserFormItem 按 formType 映射）
- **双网关拓扑解耦桌面与云端**：本地环（scheduler:13159 一站式：执行控制+插件转发+LSP+venv 管理）自洽可离线；云端环（openresty 六 upstream）可独立升级——同一引擎两种部署形态
- **双 workspace 聚合**：uv（engine 全家 editable 单 venv）+ pnpm（catalog 版本统一）——一处 sync 全局生效，跨包重构低成本
- **AI 三面布局**：OpenAI 兼容 LLM 代理（ai-service）+ 积分计费闭环 + MCP 对外开放（openapi-service）——RPA 能力既被 AI 增强、也可被外部 Agent 编排
- mock 冒烟文化使跨平台开发（macOS 开发→Windows 运行）可持续

**债务/注意**：
- c_atom_meta_new 行内 JSON 手术脆弱（无 schema 校验，靠容器验证兜底）
- 插件协议无版本协商；M10 IFrame 缺口已定位在引擎侧（原子未传 frame 参数，插件能力闲置，见 4.7）
- **双 AST 实现漂移风险**：前端 IncrementalASTParser（TS）与引擎 Lexer/Parser（Python）是两份独立语法实现，控制流语义（Try/For/While 容器配对规则）需人工保持一致——改动控制流结构时两侧必须同改
- **debug/运行行为差异**：debug 模式生成期剥离 skip_err 重试/跳过包装——"调试通过 ≠ 正式运行一致"，重试路径是调试盲区
- 两代 AI Agent 入口并存（robot-service agent/ 与 astronAgent/）待收敛
- 端口双约定：13159（网关挂载）与 19082（browser-bridge 独立部署）并存，行为取决于 GATEWAY_PORT 注入——排障先确认部署形态
- 单 venv 全家桶：27 组件全量 editable，磁盘与安装代价大，按需裁剪是潜在优化点
- 部分组件图标缺失回退 atom-default（惯例可接受）；go.mk 为多语言模板冗余（本仓库无 Go）
- meta 生成依赖 /tmp 脚本 + stub 清单，未沉淀为组件内工具（建议后续移入 tools/）
