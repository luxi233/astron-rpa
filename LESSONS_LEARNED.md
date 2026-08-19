# 项目经验与教训总结（持续更新）

> 来源：影刀对比补齐批次（P0-P3）+ 此前 v1.1.x 各批次（WPS/数据库/手机/网络/系统/对话框/Excel等）踩坑记录。
> 用途：新批次开发前速查，避免重复踩坑。日期：2026-08-16 整理。

---

## 一、SQL / 数据库（原子表）

1. **init SQL 转义规范（最高频坑）**：生产 MySQL 是默认 sql_mode（反斜杠是转义字符）。
   - 正确写法：`json.dumps(obj, ensure_ascii=False)` 裸中文 + `\` 双写 + `'` 双写。
   - 错误写法：`ensure_ascii=True` —— 生成的 `\uXXXX` / `\"` 单反斜杠导入时被吃一层 → title 乱码（u521b 式）+ JSON 整行崩。
2. **验证 SQL 必须在库内做**：`JSON_VALID` / `JSON_EXTRACT`。`mysql -B` TSV 导出会给反斜杠再加转义层，拿回 python `loads` 是假性崩/字面串，别信。
3. **atomCommon 行（id=19）手术必须纯字符串操作**，不做 JSON 往返（行内 template 字段有四重反斜杠，解析必炸）。括号深度感知扫描器 + 倒序下标插入是安全模式。
4. **同步脚本三要素**：末尾 id 校验（防重跑）+ 改行整行替换（保留 sort/create_time）+ 新行追加（update_time=now）。
5. **容器验证顺序**：先 `schema.sql` 建库表，再导 `init_c_atom_meta_new_data.sql`（文件开头是 `TRUNCATE rpa.c_atom_meta_new`，不建表直接报错）。
6. **新分类必须同步改 atomCommon 行的 atomicTree**，只加原子行不改树 = 编辑器里看不见（Database 批次 880-883 踩过）。

## 二、原子开发（装饰器/参数/枚举）

7. **枚举 options 识别靠函数签名类型注解**：`atomicMg.param("x")` 不写 `types="Str"` + 签名 `x: MyEnum = MyEnum.A` → 前端 RADIO + options；裸参数无注解 → INPUT_VARIABLE_PYTHON 无 options。
8. **options 的 label 来自组件 config.yaml 顶层 `options:` 段**（按枚举类名 keyed），不来自枚举代码注释。
9. **参数名禁用 `key`**（与 `atomic_run(self, func, key, *args)` 位置参数冲突报 multiple values）；也避开 `args`。
10. **装饰器原子直接调用（冒烟）必须 kwargs 传参**：位置参数报"参数不支持"。
11. **原子内部比较 `param == Enum.member`**：传字符串不报错但静默不匹配任何分支 —— 冒烟必须传枚举成员（如 `WriteType.CELL` 不是 `'cell'`）。
12. **输出数量决定返回形态**：单输出原子直接调用返回值本身，多输出返回元组。
13. **业务 BaseException 无 message/code 属性**（元组式 args）—— 冒烟断言用 `str(e)` 内容匹配。
14. **TerminateAppSignal 必须显式继承 `builtins.BaseException`**：error.py 顶部 `BaseException = ...` 遮蔽内置名，业务基类父类是 Exception 会被流程 Try 吞掉。
15. **meta.json 重新生成**：用 stub 脚本（`/tmp/gen_meta_stub.py`）+ 组件自己的 venv（`cd <component> && uv run python /tmp/gen_meta_stub.py`）。pyautogui stub 是关键——没有它 mouseinfo 看到 faked Linux 平台、tkinter 缺失直接 `sys.exit`（SystemExit 不是 Exception），winele.py import 静默死、meta.json 留旧原子。重生成可能带出历史 label 漂移——手动保旧值控制 diff。
16. **macOS 冒烟 stub 清单**：browser 组件要 stub `astronverse.software.software`（平台检查在模块顶层）；printer_core 相关要 stub win32 全家桶（win32com/pythoncom/win32gui/win32print/win32clipboard/win32ui 等）。
17. **手机双连接**：`locate()` 必须传 `device=conn.device` 给 PhoneElement，否则双击/长按报"元素对象缺少设备引用"；selenium `create_pointer_down/up` 是 keyword-only 参数 `button=0`。
18. **纯色模板在 TM_CCOEFF_NORMED 下零方差处处匹配 1.0** —— CV 测试必须用随机纹理图。
19. **BaseException 构造必须两参 `(error_code, message)`**：单参 `raise BaseException(FORMAT.format(...))` 不在 raise 处报错，而是在 except 链中以 `TypeError: BaseException.__init__() missing 1 required positional argument: 'message'` 出现，极易误判为调用方问题（M4 `_open_plumber` 实例）。写 except 分支后必须配一个"错误路径"冒烟用例兜住。
20. **pdf 组件 macOS 生成 meta**（/tmp/gen_meta_pdf.py）：pdf.py 平台守卫 Darwin 直接 raise，core_unix 又是未实现抽象方法的占位类 → **不能改 `sys.platform="win32"`**（连累 stdlib：shutil→`_winapi` 崩，keyring 链引爆）。正确姿势：预载 `astronverse.pdf.core_win`（依赖全跨平台）顶替 `sys.modules['astronverse.pdf.core_unix']` + patch `platform.system()→"Linux"`。冒烟只测 PDFExt 时可直接 import pdf_ext（它不 import pdf.py，无平台守卫）。

## 三、YAML / config.yaml

21. **tip / helpManual 含 `': '`（冒号+空格）必须整体单引号包裹**，内部字典写法改双引号（`tip: '参数字典，如 {"x": 1}'`）；helpManual 以英文冒号结尾同理（`:memory:` 案例）。
22. **追加配置块前先看文件尾部结构**：config.yaml 尾部是 `options: {}` 时，直接 `cat >>` 追加 `  Script.xxx:` 缩进块会挂到 options 下——必须插到 `atomic:` 内、`options:` 前。

## 四、浏览器 / JS 注入

23. **JS 模板不能用 str.format**（JS 花括号冲突）——用 `__PLACEHOLDER__` 显式 replace，或 `json.dumps` 生成 JS 字面量注入（XPath/URL/文本都这么干，顺带防注入）。
24. **跨域 iframe 页面内 JS 访问不了**——必须走 CDP（debugger Runtime.evaluate 按 frameId/contextId 路由），这是 P3-2 的前置改造。
25. **Univer workbook locale** 必须 `'zhCN' as SheetLocaleType`（裸字符串 tsc 报错，IWorkbookData.locale 是枚举）。

## 五、原子表挂载（atomicTree）

26. **同一原子 key 可在树中多个分组出现**（BrowserElement.loop_similar 在 code/for + web 两组；Script.module 在 process + script 两组）——挂载必须：先定位目标分组 atomics 数组边界（括号深度扫描）→ 分片内找锚点条目 → 收集插入点倒序执行。直接全文 find 第一个命中必挂错组。
27. **条目格式**：`{"key", "title", "icon"}`，separators=(", ", ": ")；icon 不存在时回退 atom-default（惯例可接受）。
25b. **固化工具**（/tmp 易失，已存项目内）：
   - `tools/sync_atom_sql.py` —— SQL 新行+改行同步模板（改 NEW_ROWS/UPDATE_ROWS/EXPECTED_LAST_ID）
   - `tools/mount_atom_tree.py` —— 树挂载模板（改 MOUNTS/GROUP_TITLES）
   - 流程：meta.json 重生成 → sync → mount → MySQL 容器全量验证

### atomicTree 分组结构全图（2026-08-16 快照，改树前先重新导出核对）

```
process|流程               （含 assert|断言 子组）
code|代码流程              （if|条件判断 / for|循环 / error|错误处理）
web|网页自动化             （web.cookie|Cookie / web.page|网页操作 / web.file|网页文件 / web.network|网络监听）
desktop|桌面自动化         （desktop.window|窗口操作 / SAP|SAP自动化）
phone|手机自动化
document|文档处理          （PDF / Word / Excel）
keyboard|鼠标键盘
data|数据处理              （data.Math / data.String / data.List / data.Dict / data.Time）
datatable|数据表格
database|数据库
os|操作系统                （os.file / os.path / os.zip / os.system / os.screenshot / os.clipboard / encrypt|加解密编解码 / os.printer）
network|网络               （email|邮件 / http|HTTP / ftp|FTP）
cv|CV图像
dialog|对话框
enterprise|控制台
script|自定义脚本          （BrowserScript.js_run / Script.module / Script.component）
```

常用挂载锚点（P1-P3 用过/计划）：
- web 组：wait_element、similar、loop_similar(web组内)、get_relative_element、set_select、element_text、element_visible、screenshot、element_operation
- desktop 组：wait_element、similar、get_element_info、get_relative_element、set_value
- database 组：execute_sql、batch_insert；data.Dict 组：get_values_from_dict
- process 组：Script.process；script 组：Script.module、Script.component

## 六、openpyxl / Excel / DataTable

28. **delete_rows 不缩 sheet.max_row**——排序/去重后必须用 `last_nonempty_row()` 兜底截断，否则空行被排到数据前。
29. **workbook.save('.csv') 直接报错**——CSV 导出走专用 csv.writer 路径（read_data 全区域 → writerows），别用 openpyxl 保存。
30. **ensure_xlsx_file 必须先 makedirs 父目录**（astron/）——模块级 `except: pass` 会吞 FileNotFoundError，留下 PyxlWrapper 未定义静默坏掉全组件。

## 七、工具链 / 流程纪律

31. **绝不能对同一文件并行 Edit**——互相覆盖丢改动（config.yaml 两条 tip 同时改，后一条吃掉前一条）。
32. **CI style gate 是 pinned ruff 的 `format --check`**：`uv run --project engine --dev ruff format ./engine --check`；ruff check 900+ 错误是预存噪音，只有 format 过不了会挂。
33. **发版纪律**：无代码变更不发版；tag 必须 `v<MAJOR>.<MINOR>.<PATCH>[-预发布]`（禁4段）；tag 与 electron package.json 完全一致；release 四资产（EXE/wps_read_sheet.js/server-snapshot/SERVER-DEPLOY.txt）；含 `-` 自动预发布。
34. **WPS AirScript 用 1.0 runtime**（2.0 改返回值机制不需要）；WPS 脚本更新四处同步：仓库 scripts/ + 本地 Downloads + config.yaml helpManual + SQL helpManual。
35. **AppleScript 大坑**：Finder `selection` 返回引用非列表，必须 `get selection as alias list`（空选中 -1728 要 try）；Finder 必须前台否则 selection 为空。
36. **网页读 URL 直接 WebFetch，不走浏览器代理**（成功率问题）。
37. **API 额度紧张时**：先存档后执行——把 URL/任务清单写进本地断点文件（MISSING_FEATURES.md 模式），每完成一段立即标记。

## 八、视频 / ffmpeg（M5 astronverse-video）

38. **imageio-ffmpeg 只带 ffmpeg 不带 ffprobe**——元数据（时长/分辨率/有无音轨）解析用 `ffmpeg -i` 的 stderr：`Duration: HH:MM:SS.ss` 正则 + `Stream.*Video:.*?(\d+)x(\d+)` 分辨率 + `Audio:` 子串判音轨；无 ffprobe 可用是常态，别假设二进制存在。
39. **拼接必须 filter concat 再编码统一**（`-filter_complex [0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]` + libx264/aac）——concat demuxer 要求编码参数完全一致，异源视频必炸；拼接前 probe 预检分辨率一致并给明确报错。混合有无音轨的输入统一按无音轨拼接（`all(has_audio)`），避免流缺失。
40. **音频变速 atempo 单级 0.5-2.0**，超范围拆链式乘积（0.25=0.5×0.5、4.0=2.0×2.0）；视频轨对应 setpts=PTS/speed。冒烟时长断言给 ±0.3s 容差（重编码时间基漂移）。
41. **容器验证直接导 `rpa` 库**：schema.sql 的 `CREATE DATABASE ... rpa` / `USE rpa;` 是无反引号形式，`sed 's/`rpa`/`rpa_verify`/g'` 替换不到 → rpa_verify 库根本没建出来；验证容器是一次性的，schema 原样导入 rpa 库再导 data.sql（TRUNCATE 本来就指向 rpa）最省事，无需改名隔离。
42. **database 组件的 BaseException 是内置名**（M6 发现）：该组件 error.py 不像 video/system 那样定义业务 BaseException，`from error import *` 后裸 `BaseException` 仍是 builtins——`except BaseException: raise` 前置 + `except Exception` 后置的包装模式在此组件是**死代码**（内置 BaseException 先捕获一切普通异常直接 re-raise，友好中文错误分支永不执行），驱动错误原样抛出。既有 Database(pyodbc)/Sqlite 同样如此——保持一致性不修；新组件写法要学 video：error.py 显式定义业务 BaseException 类。组件间 `import *` 的名字遮蔽行为不统一，写 except 链前先确认本组件 BaseException 到底是谁。
43. **psycopg2 与 pyodbc/sqlite3 的占位符差异**：pyodbc/sqlite3 用 `?`，psycopg2 用 `%s`（executemany）和 `%(name)s`（字典绑定——insert_dict 直接把原字典作为 params 传给 execute，零转换）；DDL 的 rowcount 是 -1 不是 0（统一 `rowcount>0 else 0` 归一）；标识符防注入用双引号包裹+内部双引号双写（`"us""ers"`），值参数化交给占位符。

## 九、手机 / adb shell（M7 astronverse-phone）

44. **adb shell 的 URI 不能套路径引号助手**（M7 冒烟抓到）：`-d file://{}` 若复用 `_q(path)` 会产生 `file://"/sdcard/x.png"`（URI 内嵌引号，am broadcast 解析失败）——正确姿势是 URI 整体作为一个参数加引号 `-d "file:///sdcard/x.png"`（路径内的引号先剥掉）。引号助手只用于普通路径参数。
45. **长截屏重叠查找不能逐 k 全块比较**：2400 行屏幕对每个候选 k 做全块 array_equal 是 O(h²·w) 灾难；正确姿势三步——灰度量化（>>3 容忍渲染噪声）行 bytes 建哈希索引 → 只对"prev 某行 == new 首行"的候选 k 验证 → 5 个采样点（0/¼/½/¾/k-1）均值差 <3.0 判定。到底判停用"滑动后新屏与上屏 array_equal"；无限滚动模式必须带 hard_cap（50）兜底（时钟/动画内容永不相等会死循环）。冒烟用合成 1000 行唯一纹理长图（`(i*7+j*3)%256`）+ mock swipe 推进 scroll_pos 并 clamp 到底，拼接结果与原图**逐像素**断言。
46. **u2/appium 双模式 shell 分发**：`_adb_shell` 统一入口——u2 走 `device.shell(cmd)` 返回 str；appium 优先 `execute_script('mobile: shell', {command})`（需 driver 支持），失败回退 `adbutils.adb.device(conn.serial).shell()`（PhoneObject 持有 serial 是回退的关键，连接时务必存真 serial）。文件存在性判定用 `[ -f x ] && echo 1 || echo 0` 的 stdout 解析（`"1" in out.split()`），别用退出码（u2/appium 对非零退出的返回形态不一致）。`ls -1p` 尾斜杠区分文件/文件夹后，通配过滤和排序放 Python 侧（fnmatch+sorted），shell 侧不做。
47. **ruff 必须用项目 .ruff.toml 跑**（M7 收尾坑）：`--isolated` 会丢掉 line-length=120 按默认 88 误报 4 文件需重排；engine/.ruff.toml 的 ignore 里有 UP045（preview 规则），ruff 0.8.6 报 `Unknown rule selector` 直接拒跑——**cd engine 目录用 ruff ≥0.14** 才能正确加载配置（UP038 已移除的 warning 无害）。判定"是否新增 lint"用 statistics 输出对比存量清单即可。
48. **懒加载复用 swipe_screen 而非直发 touch**：lazy_load 循环 = `_xpath_exists`（不等待、异常吞为 False）命中即 `_locate_built_xpath` 取元素；未命中则 `swipe_screen(DIRECTION)` 复用既有的双模式滑动分发（Appium W3C/u2 swipe），避免重复实现滑动协议。元素版与 xpath 版共用 core，仅入口构建 xpath 不同（`_build_xpath(by,value)` 支持 selector JSON 多条件）。

## 十、错误框架 / 冒烟断言（M8 astronverse-network）

49. **`ErrorCode.format()` 原地污染模板**：error.py 的 `XXX_FORMAT.format(args)` 返回 self 且 `message` 被 format 结果覆写（占位符消失）——同一 FORMAT 对象第二次 format **静默返回首次插值文本**（M8 实证：两个错误分支报同一句"密钥连接未指定私钥文件路径"）。运行时抛错即终止流程无碍（全组件既有模式），但冒烟测试同一 FORMAT 连续触发多个错误分支时，只有第一个分支能断言完整文本，后续分支只能断言固定前缀/抛出类型；排错时若"错误信息张冠李戴"先想到这里。
50. **`atomic_run` 过滤 None 值 kwarg**（`base_kwargs = {k: v for ... if v is not None}`）：direct call 传 `x=None` 到不了函数体（报 missing argument）→ 业务里的 `if x is None` 友好提示分支不可达，冒烟要测该分支只能传"非 None 无效对象"（如字符串）走 except Exception 包装路径。
87. **组件未 `from xxx.error import *` 时 `raise BaseException` 用的是内建类 → 流程静默退出零报错**（WPS 双连接 bug 根因, v1.2.2 后仍复现）：引擎自定义 BaseException(Exception 子类, 含 .code/.message) 靠 import 星号导入遮蔽内建；组件若没建 error.py 没 import，`raise BaseException(str, str)` 抛的是**内建 BaseException**——不被 bdb 调试器的 `except Exception` 捕获、不被 start.py 的 `except BaseException`(已被遮蔽为自定义类)捕获 → 异常直达进程顶层, 前端零报错直接结束。actionlib/error.py TerminateAppSignal 注释早已记录遮蔽机制但只防了正向(想穿透), 没防反向(误穿透)。**新组件 checklist: 必须建 error.py + import * + ErrorCode 双参构造**；冒烟断言必须验证 `isinstance(e, Exception)` 且 `e.code.message` 可访问, 而非锁定 `len(e.args)>=2`（后者恰是内建类的 bug 行为）。
88. **`__validate__` 失配返回 None 会让坏绑定穿透到业务层**：强类型 `__validate__` 应对齐 actionlib.types 约定**抛 ParamException**；返回 None 时 atomic_run 不报错、业务函数收到 None（或经 None 过滤直接缺参）, 错误位置漂移且信息模糊。WpsHookClient 修复后, 绑定降级成字符串会在参数层报"参数 wps_client 的值转换成 WpsHookClient 失败，原始值: wps_client"（ParamModel 统一包装, 指引文案会被替换, 断言用参数名+类型名）。

## 十一、Web 增强 / runJS 冒烟（M9 astronverse-browser）

51. **长截图分段拼接重叠 bug（冒烟抓到）**：`element_long_screenshot` 滚动步长 step=视口高×0.8 时，相邻段视口区间重叠（段1覆盖 [y, y+vh]、段2覆盖 [y+step, y+step+vh]，step<vh）——若每段都裁"元素与视口交集"（`min(img.height, elem_bottom-scroll_y)`），重叠区被重复拼接导致总高超出元素实际高（1500px 元素拼出 1800px）。正确做法：每段只负责 `[y, y+min(step, 剩余高度, 视口高)]`，即 `seg_bottom = min(img.height, elem_top+elem_h-y, step)`，段间无缝无重叠，总高恒等于元素高。
52. **runJS 原子的 node 冒烟模式（M9 建立）**：FakeBrowser 拦截 `send_browser_extension(key="runJS")` → subprocess node 执行生成的 JS（fake DOM prelude + `(async function(){ code })()` 包裹，code 尾部本就是 `return main()` 顶层 return，包裹后语法合法）→ stdout JSON 回传断言。fake DOM 必须补齐 JS 代码里用到的**全部全局**：`XPathResult.FIRST_ORDERED_NODE_TYPE/ORDERED_NODE_SNAPSHOT_TYPE`、`NodeFilter.SHOW_TEXT`、`document.evaluate/createTreeWalker/querySelector(All)/createElement/head.appendChild`、`window.scrollX`（遗漏时 undefined 参与加法 → NaN → JSON.stringify 变 null → Python float(None) TypeError，报错位置在原子内部而非 JS 内，易误判成原子 bug）。sessionStorage/localStorage 用 `get length()` getter + key()/getItem() 模拟即可。
53. **f-string 混拼 JS 字符串的 `}}` 转义坑（冒烟环境自坑）**：多段字符串拼接 JS 时，f-string 段内 `{{`/`}}` 转义为大括号，但**无 f 前缀的普通字符串段 `}}` 原样两个大括号**——对象字面量闭合多出一个 `}` 导致注入 JS 语法错误（node SyntaxError: Unexpected token '}'）。原子源码按铁律用 `json.dumps` 字面量注入无此问题；构造测试 env / 动态拼 JS 时统一全段 f-string 或改用 json.dumps。
54. **atomic wrapper 对必填参数空字符串在框架层拦截**：inputList 里 `required=True` 的参数传 `""` 时，错误信息是框架的 `BaseException('参数异常: ')`（str(e) 只有错误码消息，业务关键词在 args[1]），到不了原子体内的"XPath不能为空"友好提示——冒烟断言异常文本要兼容两层：`str(e) + ' '.join(e.args)` 拼串匹配（同 #49 的教训延伸）。
55. **SQL 新行 id 映射以 MISSING_FEATURES 文档规划为准**：M9 初版 sync 脚本按"实现类分组"排 id（element 类在前 software 类在后），与文档规划的"功能领域"顺序（存储→文本→下拉→页面管理→JS库→样式→元素）不一致——**新批次开工前先抄文档 id 清单进 NEW_ROWS**，不要按实现顺序自排；发现不一致时行位置无需移动，一次性脚本重写 18 行的 (id, key, content) 即可（树挂载 entry 不含 id，无需返工）。

## 十二、IFrame 跨域 / CDP 帧路由（M10 插件+astronverse-browser）

56. **类体装饰器内引用同类助手必 NameError**：`@atomicMg.atomic(inputList=[... BrowserIframe._frame_param() ...])` 在类体执行时 `BrowserIframe` 尚未绑定到模块命名空间——参数工厂（构造 atomicMg.param 列表片段的复用函数）一律放**模块级**，类内装饰器直接引用模块级函数名。
57. **CDP frameId 回退值 `||0` 会污染主文档上下文**：handleAttachedTarget 里未打标跨域帧 `dataset.astronFrameId || 0` 回退到 `0`，而主文档 frameId 也是 `0` → frameContextIdMap['0'] 被跨域会话覆盖，主文档执行被劫持到错误 target。修法：回退空串 + `frameId !== ''` 才写入映射（未打标帧不映射，留给 getFrameTree 显式路由）。
58. **同源/跨域帧识别双通道**：同源 iframe 内容脚本可注入，靠 `rpa_debugger_on` 标记打标 frameId；跨域 iframe 内容脚本进不去，必须 Target.setAutoAttach 挂子会话 + Runtime.evaluate 按 contextId 路由——引擎侧 runJS 只需带 `isFrame + iframeXpath`，路由复杂度全部收敛在插件层。
59. **macOS BSD sed 不认 GNU `\b` 词边界且静默失败**：`sed -E 's/\brpa\b/rpa_verify/g'` 在 macOS 上不报错也不替换（输出与输入相同）→ schema.sql 原样导入错库（该文件还是**裸库名** `USE rpa;` 无反引号，``s/`rpa`/.../`` 同样匹配不到）。容器验证改用：直接 DROP 重建 `rpa` 库原文导入（schema 自带 CREATE DATABASE+USE），或用 `perl -pe 's/\brpa\b/rpa_verify/g'`。

## 十三、进度条 / ws 消息 / 前端联调（M11 astronverse-dialog + web-app）

60. **新 ws 消息类型零改服务端**：`Ws.send_notification` 的 name 是 data 自由字段（`{"data": {"name": "notification"|"progress", "option": payload}}`）——新增前端消息类型只需引擎 payload 换 name + 前端 store 加 `msg.name === 'xxx'` 分支，executor ws.py 一行不改（DEV_PLAN 原计划"仿 send_notification 增加 progress 消息"实为不必要）。
61. **迭代器包装原子输出注册 List 即可接循环节点**：ProgressBar 实现 `__iter__/__next__`，meta 输出 `types="List"`，流程引擎对 List 直接 iter() → for 循环每次 next 自动推进度；`StopIteration` 前先推 close 再 raise。注意 `len()` 取不到（生成器）时 total=0 进"未知总数"模式（percent=None 由前端按 current/total 现算或不显示百分比）。
62. **函数签名注解不能写 UnionType**：`iterable: list | None = None` 会崩 meta 生成器 `gen_type → issubclass(UnionType)`（TypeError: arg 1 must be a class）——显式 Optional 联合类型不被支持，可空参数只能写 `: list = None`（implicit-optional lint 与存量 11 个同款并存）或干脆无注解。
63. **atomic wrapper 仅支持 kwargs 调用**：位置参数直接 `BaseException(PARAM_ARGS_NO_SUPPORT_FORMAT)`——冒烟/直调原子一律 `Dialog.update_progress(progress_bar=pb, percent=50)` 写法（M8 #44 的补充：不只 None kwarg 被过滤，args 整体不支持）。
64. **前端 notification.open + key 复用 = 进度条实时刷新**：antd `notification.open({ key: progress_id, duration: 0, description: h(Progress,...) })` 同 key 重复调用原地更新不重开弹窗；`percent` 传 null 时组件报错，需前端兜底（hasTotal 时按 current/total 现算，否则 Number(percent)||0）。流程结束用 activeProgressIds 数组在 reset() 统一 `notification.close` 清理，防泄漏常驻弹窗。
65. **vue-tsc 存量错误判定法**：web-app 全量 tsc 有 7 个存量错误（http/AtomForm/SettingCenterModal/components包）——验证新改动用 `grep -c "目标文件名"` 过滤错误行数为 0 即净，而非指望全量绿。

## 十四、测试收编 / 平台兼容（W2-W3 修复批次）

66. **stub win32 模块必须设 `module.__path__ = []`**：meta_path finder stub 出的模块不是包，`import win32com.client` 时 Python 先查父模块有无 `__path__`（不走 finder），直接报 `'win32com' is not a package`——exec_module 里补 `module.__path__ = []` 才能通过子模块 import（system/tests/conftest.py 模式）。
67. **subprocess.run 的 input 与 stdin 互斥**：同时传 `input=...` 与 `stdin=subprocess.DEVNULL` 抛 `ValueError: stdin and input arguments may not both be used.`（clipboard_core_linux.py copy_file_clip 真 bug，12 个 clipboard 用例全挂的根因）——传 input 就删 stdin。
68. **跨组件冒烟脚本归位原则**：脚本跟随"被测原子所在组件"归位，不得依赖其他组件 venv 的第三方包——dataprocess/smoke_m1 的 URL 段依赖 encrypt 的 pycryptodome，迁出为 encrypt/tests/smoke/smoke_m1_url.py 才能在各自 venv 跑通；跨组件重复段（p06 的 system 部分）直接删并指向覆盖方。
69. **冒烟脚本路径禁止依赖 cwd**：`sys.path.insert(0, "src")` 在 /tmp 直跑时靠 cwd 兜底碰巧通过，收编后从任意目录跑必挂——统一 `os.path.join(os.path.dirname(__file__), "..", "..", "src")` 绝对定位；winelement 等被测依赖在独立组件时还要补对应组件 src 路径。
70. **Windows-only 测试用 skipIf 而非放任失败**：xclip/test.exe/scrot/进程名(exe后缀) 等 macOS 必挂用例加 `@unittest.skipIf(sys.platform != "win32", ...)`（34 个）——macOS 全绿基线 + Windows CI 真实执行两不误；demo 类手动脚本（真实开浏览器）用 `pytest.skip(..., allow_module_level=True)` 模块级跳过。
71. **过时 API 测试删除重写优于缝补**：script 旧 `__env__=` 注入式 9 用例对当前签名全 TypeError（API 已改 auto-context），且 conftest fixtures 为空文件——按当前 `_module_call` 签名重写 4 用例（mock import_module）覆盖 v1/v2/错误分支，比逐个改参数名可靠。
72. **zsh 循环不做 word-splitting**：`for pair in "a b"; do set -- $pair` 在 zsh 里 `$pair` 不分词（bash 才分）——批量脚本包 `bash -c '...'` 执行；同理 macOS 无 `timeout` 命令（exit 127），要么 brew coreutils 的 gtimeout 要么不用。

## 十五、后端服务测试（openapi/ai-service，全量测试批次）

73. **patch httpx.AsyncClient 类方法会拦截测试客户端自身**：conftest 的 AsyncClient(ASGITransport) 发请求同样走 `httpx.AsyncClient.post`——mock 上游 API 时必须按目标 URL 判定（假上游 host 才返回 fake，其余透传原实现），否则流式用例拿到的是 fake 响应对象（content-type=application/json）而非真实 ASGI 响应，表现为"假失败"。且 patch 到类上的 fake 函数**必须带 self 形参**（漏掉即 TypeError 被服务层 except 吞掉，难定位）。
74. **service 层 commit 会击穿 conftest 事务回滚隔离**：`session.begin()` + teardown `rollback()` 的隔离模式下，被测 service 内部调用 `db.commit()`/`flush+commit` 后事务关闭，teardown 抛 `ResourceClosedError: This transaction is closed`——rollback 前必须加 `if transaction.is_active:` 守卫；隔离兜底靠 function 级 drop_all/create_all。
75. **FastAPI Query 默认值不得违反自身约束**：`Query(100, ge=1, le=50)` 裸调用（不带参数）直接 422——默认值必须在约束区间内；此类"默认值自相矛盾"路由测试裸调用即可暴露。
76. **测试路径必须对照真实路由而非想当然 RESTful**：本项目路由风格是动词式（`/api-keys/get|create|remove`、`/workflows/upsert|execute-async`），且统一 `StandardResponse{code,msg,data}` 包装（ResCode 字符串枚举 SUCCESS="0000"/ERR="5001"，不存在的资源返回 200+ERR 而非 404）——写测试前先 `rg "@router\\.(get|post)"` 核对路由表和响应模型。
77. **模块级 create_async_engine 导入即需环境变量**：database.py 顶层建 engine（虽惰性连接），conftest `from app.main import app` 链路上 config 必填字段（DATABASE_URL 等）缺失即 ValidationError——跑测试须预置环境变量（值可指向不可达地址，测试中 get_db 已被 override）；LOG_DIR 默认 /var/log 同理要覆盖。
78. **service 返回值与直觉不符时以签名/实现为准**：`ApiKeyService.create_api_key` 返回明文 key 字符串（flush 后仅前缀入库），不返回 ORM 对象——conftest 辅助函数要拿 id 只能按 prefix 反查；同理模型字段名是 `api_key` 不是 `key`。

## 十六、发版流水线（v1.2.0 全量批次）

79. **本地 pnpm 版本必须与 CI 对齐（pnpm 9）**：CI 全线 `pnpm/action-setup@v4 version: 9`，本地 pnpm 10 会往 pnpm-lock.yaml 写入 `packageExtensionsChecksum`（pnpm 10 专属），CI 9 的 frozen install 直接 `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH` 失败且报错不直观（先跑 ruff 的还以为是 Python 问题）——lockfile 变更后用 `npx pnpm@9.15.9 install --no-frozen-lockfile` 重生成并以 `--frozen-lockfile` 复验；本地默认 pnpm 10.33 装新依赖前先想 CI。
80. **发版 tag 移动的安全窗口**：release 流水线挂在 tag 上、release 未发布前，发现 QA gate 问题可以 `git push origin :refs/tags/vX.Y.Z` 删远程 tag → 修复 commit → 重打 tag → 重新 dispatch 流水线（v1.2.0 实际迭代了 3 轮：ruff format 29 个测试文件 → pnpm lockfile → 全绿）；一旦 GitHub Release 已创建就绝不能移 tag，只能走 vX.Y.Z-1 修订版。
81. **QA gate 是全量检查不是增量**：本地开发只 format 改动过的文件，但 CI `ruff format ./engine --check` 是仓库全量——批量收编冒烟脚本/新组件后必须在仓库根跑一遍 CI 同款命令（含 browser-plugin `pnpm exec tsc --noEmit`），别等 push tag 后才发现 29 个文件要重排。

## 十七、WPS 静默失败与对象参数强类型（v1.2.1 修复批次）

82. **types="Any" 的对象参数是静默失败温床（WPS 白屏级 bug 根因）**：连接类原子的输出/下游参数若声明 `types="Any"`（或签名是普通类被 gen_type 归为 Any），前端变量绑定可能存成 `{"type":"str"/"other"}`，executor `_param_to_eval` 对 str/other 一律 `repr()` 成**字符串字面量**——生成 `wps_client='连接A'` 而非变量引用；运行时 `str.send_request` → AttributeError；若指令开了"错误时跳过"，异常被 except 吃掉只报 SKIP 警告，**输出变量从未赋值，后续引用连环 NameError 也被吞，流程"无报错直接结束"**。修复三件套：①对象类加 `@classmethod __validate__`（对齐 browser.py 的 Browser，gen_type 走 RPABASE 分支保留类名）；②meta param 显式 `types="WpsHookClient"`（输出+全部输入）；③原子入口 `_client(wps_client)` isinstance 兜底，str/None 抛**带修复指引的 WpsHookError**（指引用户用变量选择器绑定而非手输）。复现脚本模式：mock webhook 6 种响应结构 + skip 包装生成代码 exec 实跑（`/tmp/wps_skip_sim.py` 思路，已收编 kdocs 冒烟）。
83. **新组件发布前必查"对象流"原子的 types 链**：create/connect 类原子输出对象 → 下游 N 个原子引用——检查 meta.json 里这条链两端 types 是否一致且非 Any（`jq '.["X.create"].outputList[0].types'` 对照下游 inputList）；Browser/BrowserObj 是正确范本。WPS 26 原子无任何测试（收编冒烟时是空白），对象链 bug 正是从这个盲区溜进 v1.2.0 的——新组件交付清单必须含"对象链 types 一致性 + 冒烟"两项。
84. **executor 的 skip 模式会吞 NameError**：`_display_with_skip` 生成的 `try/except Exception` 结构里，输出变量赋值失败后**该变量在后续指令中不存在**，而后续指令若也开 skip，其 NameError 同样只报 SKIP——两层叠加后用户看到的是"流程正常跑完但什么都没发生"。排查此类"静默结束"先看流程日志里有无黄色 SKIP 条目（report.warning），而不是只盯红色 ERROR。
85. **workflow_dispatch 的 notes 参数禁止携带反引号**（v1.2.1 发版踩坑）：release-full-pipeline 的 "Compose release notes" 步骤把 notes 拼进 bash 脚本，markdown 代码标记 `` `__validate__` `` 被解释为**命令替换**，runner 报 `__validate__: command not found` 退出 127，QA/Build 全绿也会死在 Publish——notes 里写纯文本（去反引号）或用单引号代替；失败重跑直接重新 dispatch 即可（tag 不动，无需删 tag，参见 #80 的安全窗口）。
86. **新对象类型必须注册进 atomCommon(id=19) 的 types 表，否则前端流变量面板全崩**（v1.2.1 回归）：把原子参数 types 改成类名（如 WpsHookClient）只是"声明"，前端 `globalVarTypeList = atomMeta.types` 来自 atomCommon 行 types 段（v1.2.1 时 23 个：Any/Str/.../Browser/ExcelObj/PhoneObject 等）——未注册类型的输出变量会让 ProcessVarPane.vue 的 `globalVarTypeList[record.types].desc` 和 useAtomVarPopover.ts `generateValTree` 的解构直接 TypeError，**渲染树崩掉→变量面板/变量选择器全空白**。完整注册三件套：①组件 meta.py 加 `typesMg.register_types(类, version=..., channel="global", template="...")` + config_type.yaml 写 desc，生成 meta_type.json 入库（browser/excel/word 范本）；②SQL atomCommon 行 types 段末尾纯字符串手术插入同构条目（花括号深度扫描定位末键对象闭合，值内 `()` 不影响 `{}` 计数）；③前端消费点一律 `?.`/`??` 兜底（本次已加，防未来再犯）。另注意：原子行 meta.json 只改 types 不等于类型注册，两者数据链路独立。

## 十八、数据表格显示不稳定（v1.5.x 修复批次）

87. **xlsx 非原子写 + 并发读 = BadZipFile 灾难**：执行器 `PyxlWrapper.save` 与 scheduler `_apply_updates` 原来都是 `workbook.save(path)` 直接覆盖写——写大表期间（数百 ms）前端 fetchDataTable 并发 `load_workbook` 读到写一半的 zip，实测压测 6 秒 **1311 次读失败（99.9%）**，这就是"数据表格始终不能稳定显示"的主根因（拉取失败→前端回退旧数据）。修复：所有写路径原子化——先写同目录 tmp（带 pid+uuid 防多进程冲突）再 `os.replace`；读侧加 3×0.1s 重试兜底。修复后同型压测零失败。**教训：凡"一个进程写文件 + 另一进程/前端轮询读"的展示链路，写必须原子（tmp+rename），否则损坏读只是概率问题。**
88. **边界缓存首次写被写死成小行号 → 清空数据表格残留旧数据**：openpyxl.py 的 `max_row/max_col` 增量缓存用 `max(cache or 0, row)` 模式——缓存初始 None，首次写 row=1 时 `None or 0=0`，缓存被**写死成 1**，完全忽略文件里上次运行残留的 N 行；`clear_data_table` 拿 `get_max_row()=1` 只删 1 行。是否复现取决于"清空前写过什么行号"，所以用户感知是"**经常**没清空"而非总是。修复：`_ensure_bounds_cached()` 先按 sheet 真实边界初始化，再参与 max（9 处统一修）。**教训：增量缓存必须先初始化基线再做增量，`None or 0` 是把"未初始化"当"零"的经典坑。**
89. **防抖落盘 pending 必须有 Timer 兜底**：写原子 0.5s 防抖窗口内的变更只标 pending 不落盘，若流程随即结束（典型：写入→清空→结束），落盘被推迟到 atexit——**此时前端 SSE 监听已随流程结束关闭，file_changed 事件丢失，表格残留旧数据**。修复：pending 时起 `threading.Timer`（daemon）在窗口结束后自动落盘，写内存与落盘用锁互斥（openpyxl 非线程安全）。**教训：所有"延迟落盘"设计都要回答"兜底触发者是谁"——不能依赖"下一次写"（可能永不来）或"进程退出"（下游监听可能已关）。**
90. **watchdog 6.0.0 + macOS 26 的 FSEvents 零事件（import 正常但回调永不触发）**：scheduler file_watcher 原用 `watchdog.observers.Observer`（macOS 映射 FSEventsObserver），在 macOS 26 + Python 3.13 + watchdog 6.0.0 实测**完全不触发任何回调**——数据表格文件变了前端永远收不到 file_changed，表格死活不刷新（原生 Observer 压测零事件，PollingObserver 同场景 created/modified/deleted 全部正常）。修复：统一改 `PollingObserver(timeout=0.5)`——单文件轮询 stat 开销可忽略，0.5s 延迟被事件防抖自然吸收，且跨平台行为一致。**教训：文件监听类功能必须在目标平台实测事件流（创建/修改/删除各验一遍），import 成功≠运行时回调触发；PollingObserver 是保底可靠项。**
91. **watchdog 回调线程操作 asyncio 设施必须 `call_soon_threadsafe`**：Observer 的 emitter 是独立线程，`on_modified` 里直接 `event_loop.create_task()` 是线程不安全的——不会唤醒阻塞中的循环（select/epoll 无感），事件最多延迟一个心跳才被处理，极端时序下丢事件。修复：`call_soon_threadsafe(_schedule)` 调度到循环线程；`on_deleted` 的 `queue.put_nowait` 同理。**教训：watchdog 回调一律视为"外部线程"，凡触碰 asyncio 对象（create_task/Queue/call_soon）都走 *_threadsafe 变体。**
92. **openpyxl 空表语义：max_row==1 而非 0**：空 worksheet 的 `max_row` 返回 1（dimension 默认 A1），断言"清空后边界"要写 `<=1` 而非 `==0`；同理 `delete_rows` 后 max_row 也不收缩（幻影行，已有 last_nonempty_row 兜底）。另：`ws.cell(value=None)` 不落值，要清空已用区域单元格须 `ws.cell(...).value = None`。
93. **数据表格稳定性的完整验证矩阵**（本次新建四套测试共 60 例）：组件侧 `smoke_datatable_stability.py`（29 例：边界缓存 A1-A12/防抖 Timer B1-B8/清空端到端 C1-C4/原子写并发压测 D1-D5），scheduler 侧 `smoke_datatable_read_side.py`（14 例：读裁剪/防抖一致性/并发写读/原子写压测/watcher 线程安全 F1-F3），**跨进程端到端** `smoke_datatable_e2e.py`（13 例：组件 venv 子进程真实写→scheduler 真实 watcher+read_file，一致性逐格校验 G1-G5 + 实时性量化 H（实测写→事件延迟 0.16~0.97s，上限断言 4s）+ 终态磁盘 I），**前端 vitest** `src/__tests__/useRunningStore.dataTable.test.ts`（4 例：SSE file_changed→fetchDataTable→active sheet 更新/file_deleted 置空/reset 兜底拉取+abort/updateDataTableCell 乐观更新与边界收敛）。**并发场景必须用真实压测验证**（修复前 99.9% 读失败这种问题，单线程单例测试永远发现不了）；**跨进程链路必须真起子进程验证**（两个 venv 各 import 各侧代码，mock 拼不出防抖+原子写+轮询+事件防抖的叠加时序）。前端 store 测试要点：Socket mock 必须带 create/bindOpen/bindClose/isConnect/OPTIONS（缺 create 会抛异常走 catch 分支，_startDataTableListener 永不执行且测试静默失败在"listener 未调用"）。

## 三条元经验

- **断点文件是命**：MISSING_FEATURES.md 的"每完成一项立即标记 + 坑位记录 + 下一个可用 id"让多次上下文丢失后都能无损续接。
- **冒烟先行**：每个批次 mock 冒烟（paramiko式/pyodbc式/FakeBrowser式）比真环境快且能覆盖错误分支；错误分支断言用 str(e) 内容匹配而非异常属性。
- **等价判定要写明依据**：对比影刀时"已有/等价"结论必须写对应原子名（如 scroll_into_view/get_current_obj/open_args），避免下批重复排查。
