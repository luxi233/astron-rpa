# 引擎与原子组件性能优化计划 (PERF_PLAN)

> 创建: 2026-08-18 | 来源: 全量性能审查(组件 + 引擎服务) | 仓库: astron-rpa
> 状态标记: [x] 已实施 [ ] 未实施(暂缓)
>
> ## 实施验证结果 (2026-08-18)

> - P1-P5 全部实施完成
> - datatable: 存量 pytest 47/47 + 新增 smoke_save_debounce 6/6
> - executor: smoke_logging_report 28/28 + smoke_logging 26/26 + smoke_logging_e2e 16/16
> - scheduler: 新增 smoke_excel_debounce 10/10 + smoke_logcenter_api 36/36(回归)
> - 全引擎 ruff format 522 文件全过; vision core.py py_compile 通过
> - P6 暂缓(见下), P7 为排除记录

## 第二轮 (2026-08-18 晚)

| 编号 | 位置 | 问题 | 影响 | 状态 |
|------|------|------|------|------|
| P8 | scheduler/utils/utils.py | emit_to_front 非 Windows 每次 fork echo 子进程 | 每条事件 ~10-20ms 同步阻塞 | [x] 统一 print+flush(Electron server.ts msgFilter 监听 stdout, 平台无关) |
| P9 | web-app 三处轮询 | 队列10s/机器人10s/消息20s 后台不暂停 | 后台持续打调度器, 耗电 | [x] 新增 hooks/useIntervalWhenVisible.ts(visibilitychange 暂停/恢复+回前台补一次), 三处接入 |
| P10 | datatable openpyxl wrapper | ① sheet.max_row/max_column 每次调用 O(n_cells) 扫描, 循环操作 O(n²) ② read_effective_area 嵌套 cell() 逐格取值 ③ write_row 每行 print ④ read_row/column/range/last_nonempty_row 逐格属性访问 | 大表格循环写/读明显变慢 | [x] 边界缓存(写增量维护+结构变更失效+切表失效+直写点手动失效), 读路径 values_only 批量取值, 删 print |

### P10 基准 (3000行×10列, 循环1000次读边界)
- 旧: sheet.max_row 直扫 1511.3ms → 新: 缓存命中 1.0ms (**~1500x**)
- 新增 smoke_bounds_cache.py 19/19(缓存正确性/失效重算/密集区域不物化/切表恢复)

### P10 备注
- iter_rows(values_only) 对边界内空隙仍物化 Cell(与旧实现一致, 非回归); 真正的收益来自
  边界缓存消除 O(n) 扫描 + 批量取值消除逐格属性访问
- 边界缓存失效点: delete_rows/cols, insert_cells, switch_sheet, delete_sheet后切active,
  fill_data_table_by_import_file 清空, import_from_csv, sort_data_table 直写区,
  共 8 处; 写方法(write_cell/row/column/append/range/copy_paste)增量维护不失效

## 第三轮 (2026-08-19): 数据处理组件专项审查 (P11)

审查范围: dataprocess 全模块(list/dict/string/data/dataconvert/math/time)、database(连接管理)、
datatable(已在前两轮优化)。dict/string/dataconvert/math/time 为单遍 O(n) 实现无热点;
database 由用户显式管理连接无逐查询重连问题。

| 编号 | 位置 | 问题 | 影响 | 状态 |
|------|------|------|------|------|
| P11-1 | dataprocess list.py filter_elements_from_list | `i not in list_data_2` 线性扫描 O(n×m) | 1万x1万列表过滤 ~340ms | [x] set 快路径 O(n+m) → 0.5ms(**~680x**); 含不可哈希项时 try/except TypeError 回退线性扫描, 语义一致(1==True 哈希与 in 相同) |
| P11-2 | list.py remove_columns_from_2d_list | 每行重建 remove_set(对全部 indexes 做 _norm_index) | 10万行×多列重复集合构建 | [x] 正索引集合提到循环外只算一次, 仅负索引(依赖行长度)逐行换算; 负索引/越界/非列表行行为不变 |
| P11-3 | list.py filter_empty_items | only_trim_trailing=True 时仍先做全量非空行扫描(结果被丢弃) | 全表白扫一遍 | [x] 移入分支, 尾部裁剪不再多扫 |

### P11 验证
- 新增 tests/smoke/smoke_list_perf.py 16/16(过滤等价5组+不可哈希回退+大表一致+提速断言+删列正/负/混合/越界/非列表行+空值裁剪语义)
- 存量 pytest 213 passed 5 skipped; ruff 14 文件无变更

### P11 附带发现(未改, 记录)
- actionlib atomic 装饰器要求关键字传参, 位置传参抛 BaseException 且 SimpleReport.error
  会把完整参数 repr 打到 stdout——大数据直接调用时错误日志可能巨量; 生产链路(executor
  kwargs 调用)不受影响, 仅影响直调冒烟调试体验
- get_unique_list 用 list(set()) 不保序(原有语义, 未动)

## 0. 审查结论摘要

| 编号 | 位置 | 问题 | 影响 | 状态 |
|------|------|------|------|------|
| P1 | executor/start.py | ws 等待超时后无 return, 疑似死循环 | 进程挂死 | [x] |
| P2 | vision/core.py | 每次匹配 2 次无效磁盘写 + 模板重复 base64 解码 | 找图/等待类原子每轮多耗 50-150ms | [x] |
| P3 | datatable 组件 auto_save | 每次写操作全量序列化落盘 | 循环写 N 行 = N 次全量保存 | [x] |
| P4 | executor/debug/report.py | 每条日志同步 flush + 队列无限阻塞 put | 万步流程万次刷盘; ws 消费慢时流程卡死 | [x] |
| P5 | scheduler/excel_service.py | 每次单元格变更 load+save 全量重写 xlsx | 编辑器快速输入时高频全量 IO | [x] |
| P6 | executor 冷启动 | 每次运行新进程 + 组件包重依赖顶层导入 | 启动延迟秒级 | [ ] 暂缓 |

## P1 executor ws 等待死循环修复 [x]

- 位置: `engine/servers/astronverse-executor/src/astronverse/executor/start.py` L89-96
- 问题: `while not ws.check_ws_link()` 超时调用 `svc.end(CANCEL)` 后无 `return`, 循环继续, ws 永不连接时进程无限循环反复 end。
- 方案: 超时分支加 `return`。
- 风险: 无(纯 bug 修复)。
- 验收: 代码审查 + 存量冒烟回归。

## P2 vision 匹配链路去无效 IO + 模板缓存 [x]

- 位置: `engine/components/astronverse-vision/src/astronverse/vision/core.py`
- 问题:
  1. L44 `match_img.save("desktop_filepath_match.png")` 全屏截图 PNG 落盘, 保存后无人读取(后续用内存 np.array), 每次浪费 50-150ms。全仓库 grep 确认无消费方(拾取器 vision-picker 是独立服务, 有自己的截图逻辑且该行已注释)。
  2. L63 `cv2.imwrite("desktop.png", out_img)` 标注结果图落盘, 无消费方。
  3. `base64_to_image` 每轮重新解码模板图; `wait_image/click_image` 0.5s 轮询循环中模板不变, 重复解码+imdecode。
- 方案: 删除两处落盘及无用常量; `base64_to_image` 加 `functools.lru_cache(maxsize=64)`(同一 input_data dict 在循环中复用, 字符串相同命中缓存)。
- 风险: 低。若未来调试需要标注图, 恢复一行即可。lru_cache 返回 np 数组, 调用方只读(cvtColor/matchTemplate 均产生新数组)。
- 验收: py_compile + 存量测试回归(vision 组件 test_cv.py 全类 skip, 不受影响)。

## P3 datatable 组件 auto_save 防抖合并保存 [x]

- 位置: `engine/components/astronverse-datatable/src/astronverse/datatable/datatable.py` L85-94
- 问题: 20 个写原子挂 `@auto_save`, 每次写单元格/行 = openpyxl 全工作簿序列化+写盘。万行表单次 save 约 0.5-2s, 循环写 1000 行 = 1000 次全量保存, 90% 时间在保存。
- 方案(单线程模型, 无锁):
  - 模块级 `_save_state = {last_save, pending}`; 防抖窗口 0.5s。
  - 写操作后: 距上次落盘 >= 0.5s → 立即 save; 否则仅置 pending(内存 wrapper 已更新, 读原子走内存不受影响)。
  - `atexit.register(flush_save)` 兜底: 进程退出(=流程结束)前落盘 pending(executor 无 os._exit, atexit 可靠, 已验证)。
  - 暴露 `flush_save()` 供测试/外部显式落盘。
- 权衡: 强杀(SIGKILL)时 <0.5s 窗口内的写丢失(与任何崩溃场景一致); 编辑器 SSE watcher 靠 mtime 感知, 实时性损失 <0.5s。
- 验收: 存量 47 测试(全部内存断言, 已确认无文件持久化断言) + 新增 smoke_save_debounce.py。

## P4 report.py 日志缓冲写 + 队列防阻塞 [x]

- 位置: `engine/servers/astronverse-executor/src/astronverse/executor/debug/report.py`
- 问题:
  1. L97 每条日志 `flush()` 强制 syscall, 万步流程万次刷盘。
  2. L84 `queue.put(block=True, timeout=None)`: ws 消费慢/断开时队列满(1000)后流程线程永久阻塞。
- 方案:
  - flush 改为时间窗: 距上次 flush >= 2s 才刷(首条立即刷, 保证流程启动消息即时可见); `close()`/进程退出自动 flush。
  - 暴露 `flush()` 公有方法。
  - `queue.put(timeout=5)`, 超时 `queue.Full` 丢弃该条并继续(日志可丢, 流程不可卡)。
- 语义变化: "每条立即可读" → "首条即时 + 2s 窗口 + close/退出全量落盘", 冒烟测试同步适配(读文件前 flush)。
- 验收: smoke_logging_report.py 适配后全过 + smoke_logging.py + smoke_logging_e2e.py 回归。

## P5 excel_service 单元格更新合并防抖 [x]

- 位置: `engine/servers/astronverse-scheduler/src/astronverse/scheduler/core/datatable/excel_service.py` L238-280
- 问题: `/update-cells` 每次请求 `load_workbook` 全量加载 + `save` 全量重写。前端 Univer 快速输入时每个按键变更都触发全量 IO(文件大时数百 ms)。
- 方案(不缓存 workbook, 规避外部写导致脏缓存):
  - 类级共享状态(实例按请求创建, 已验证 get_excel_service 每次 new): `_pending_updates: {abs_path: [updates]}` + 锁 + 200ms 定时器。
  - `update_cells`: 校验文件存在后入队, 200ms 静默期后由定时器一次性 load+apply+save(合并同一文件的多批更新)。
  - `read_file/read_file_stream/write_file/delete_file` 入口先 `flush_pending()`, 保证读一致性。
  - 定时器线程内 per-file try/except, 失败(如文件被删)记日志丢弃, 不影响其他文件。
- 权衡: 编辑器 mtime watcher 收到变更通知延迟 <=200ms; 前端读接口因读前 flush 看到的一定是最新。
- 验收: 新增 smoke_excel_debounce.py(合并/读前flush/异常容错) + smoke_logcenter_api.py 回归。

## P6 executor 冷启动优化(暂缓, 架构级) [ ]

- 现状: 每次流程运行启动新 Python 进程; bdb.py L141 整包 import, cv2/uiautomation/openpyxl/win32 等重依赖随组件包顶层导入, 启动秒级延迟。
- 方向A(低成本): 组件包内重依赖改函数级懒导入 — 需逐组件梳理, 收益 0.5-2s。
- 方向B(高成本): executor 常驻进程池 + 版本化代码热更新 — 影响调度/隔离/崩溃恢复全链路, 需独立设计评审。
- 决策: 本轮不实施, 待 Windows 实机部署验证启动耗时数据后再立项。

## P7 已审查排除项(记录备查) [x]

- SSE 逐行推送: connector/datatable.py 已注释改走 /open 一次性返回, 无问题。
- input 重试 sleep(0.01) / vision 轮询 0.5s / get_settings 重试 5 次: 间隔合理。
- read_file 尾部空行列裁剪 O(rows×cols): 常规规模可接受。
- logcenter 启动清理/baseline logger: 仅启动时一次, 无运行时开销。

## 回归清单(全部实施后执行)

1. datatable: pytest 47 存量 + smoke_save_debounce.py
2. executor: smoke_logging_report / smoke_logging / smoke_logging_e2e
3. scheduler: smoke_excel_debounce.py + smoke_logcenter_api.py(36)
4. 全引擎 ruff format check(520 文件)
5. vision/其余改动文件 py_compile
