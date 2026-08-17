# RPA 缺失功能实现清单（断点续传）

> 依据影刀文档 7 批 102 条链接对比生成。
> 状态：⬜ 待办 | 🔧 进行中 | ✅ 完成
> 规则：每完成一个子任务立即更新此文件。SQL 起始 id=912。
> 生成日期：2026-08-16

## P0 纯组件级（零引擎改动）

### P0-1 SQLite3 数据库 ×6（database 组件，class Sqlite，ids 912-917）✅ 2026-08-16
- [x] 912 Sqlite.connect 连接 Sqlite3 数据库（db_path，输出 sqlite 对象）
- [x] 913 Sqlite.execute_sql 执行 SQL 语句（增删改，输出影响行数）
- [x] 914 Sqlite.query_table 查询数据表（输出列名+数据二维列表）
- [x] 915 Sqlite.batch_insert 批量插入数据（表名+列名+二维数据，事务）
- [x] 916 Sqlite.export_to_csv 导出数据至 CSV（查询结果直写 csv，编码）
- [x] 917 Sqlite.close 关闭 Sqlite3 数据库
- 完成：sqlite.py 新建 + error.py 9条消息 + config.yaml 6原子+options + meta.py 注册 + meta.json(10原子) + 冒烟通过(内存库全链路+CSV导出+事务+缺连接报错)

### P0-2 断言 ×4（ids 918-921）✅ 2026-08-16
- [x] 918 Assert.assert_condition 条件断言（system 组件；两对象+运算符，失败抛异常+自定义错误信息）
- [x] 919 Assert.assert_empty 空值断言（system 组件；None/空串/空白勾选，失败抛异常）
- [x] 920 Assert.assert_file_folder 文件/文件夹断言（system 组件；存在性，失败抛异常）
- [x] 921 Assert.assert_element 元素断言（browser 组件；元素+等待时间，失败抛异常）
- 完成：system/assert_core.py(class Assert×3+枚举AssertOperator/AssertEmptyMode/AssertTargetType) + browser/browser_assert.py(class Assert×1复用wait_element) + config.yaml + meta.py + meta.json(system 57/browser 57) + 冒烟通过(条件8运算符正反例/空值空白模式/文件正反例/元素mock)

### P0-3 数学函数 ×13（dataprocess 组件 math.py，ids 922-934）✅ 2026-08-16
- [x] 922 MathProcess.get_ceil 大于取整 ceil
- [x] 923 MathProcess.get_floor 小于取整 floor
- [x] 924 MathProcess.get_trunc 舍去取整 trunc
- [x] 925 MathProcess.get_remainder 取余（可选浮点取余）
- [x] 926 MathProcess.get_floor_div 取整除 //
- [x] 927 MathProcess.get_gcd 公约数 gcd（两整数）
- [x] 928 MathProcess.get_log 对数（自定义底，默认自然对数）
- [x] 929 MathProcess.get_log10 log10
- [x] 930 MathProcess.get_power x 的 y 次方
- [x] 931 MathProcess.get_sqrt 平方根
- [x] 932 MathProcess.get_exp e 的 x 次方
- [x] 933 MathProcess.get_factorial 阶乘
- [x] 934 MathProcess.get_random_item 随机元素（列表/字符串）
- 完成：math.py 追加13原子+_to_number helper + config.yaml 13段 + meta.json(84原子, MathProcess 18) + 冒烟通过(正例+异常例含除0/负数开方/负阶乘/非整数gcd/空列表)

### P0-4 文件扩展 ×6（system 组件，ids 935-940）✅ 2026-08-16
- [x] 935 File.encode_base64 Base64 编码文件（可选输出 HTML img 标签）
- [x] 936 File.get_md5 计算文件 MD5
- [x] 937 Folder.is_empty_folder 是否为空文件夹
- [x] 938 File.expand_env_path 展开路径中的环境变量
- [x] 939 File.join_path 合成一个路径（最多4段）
- [x] 940 File.is_file_locked 检查文件是否被占用
- 完成：file.py 追加5原子 + folder.py 追加1原子 + error.py 4条消息 + config.yaml 6段 + meta.json(63原子) + 冒烟通过(base64/img标签/md5/expandvars/join/占用/空文件夹正反例)

### P0-5 文本扩展 ×13（dataprocess 组件，ids 941-953）✅ 2026-08-16
- [x] 941 StringProcess.generate_random_string 生成随机字符串（汉字/大小写/数字/特殊字符）
- [x] 942 StringProcess.convert_percent 转换数字和百分比（互转+小数位）
- [x] 943 StringProcess.split_address 切分省市区地址
- [x] 944 StringProcess.match_similar_text 相似文本匹配（样本列表+阈值，输出最相似+相似度）
- [x] 945 StringProcess.compare_text_similarity 两个文本比较（输出相似度%）
- [x] 946 StringProcess.full_to_half 中文全角转半角
- [x] 947 StringProcess.cn_symbol_to_en 中文符号转英文
- [x] 948 StringProcess.en_symbol_to_cn 英文符号转中文
- [x] 949 StringProcess.remove_blank_lines 去除空白行
- [x] 950 StringProcess.merge_lines_to_one 多行合并成一行（分隔符+去空行）
- [x] 951 StringProcess.chinese_to_number 汉字转阿拉伯数字
- [x] 952 StringProcess.number_to_chinese 阿拉伯数字转汉字（普通/大写金额）
- [x] 953 StringProcess.generate_uuid 生成 UUID（补充，影刀在随机字符串内）
- 完成：string.py 追加13原子 + __init__.py 加枚举(PercentConvertType/ChineseNumberType) + config.yaml 13段+2枚举options + meta.json(97原子, StringProcess 29) + 冒烟39/39通过(随机字符串多池/百分比互转/省市区含直辖市与自治区/相似匹配/全半角/符号互转/空白行/汉字数字双向含10→十与万亿级零位) + ruff format 通过
- 坑：enum 参数 param() 里不能写 types="Str"（update() 只填 None 字段，会阻止注解派生枚举类名 → options label 退化为 value）；helpManual 以英文冒号结尾必须加引号（YAML mapping values 错误）

### P0-6 小改 ×4（改现有原子，无新 id）✅ 2026-08-16
- [x] DataTable.import_data_table_from_file 加 csv_delimiter 参数
- [x] DataTable.export_data_table_to_file 加 csv_delimiter 参数
- [x] System.get_pid 支持空名称=返回全部进程（名称+PID）
- [x] File.file_info 加 size_unit 参数（B/KB/MB/GB）
- 完成：datatable.py 两原子加 csv_delimiter(支持\t字面量, 单字符校验, 传递底层delimiter) + process.py get_pid 空名称返回[[进程名,PID]...] + file.py file_info size_unit(枚举FileSizeUnitType, 非B单位round4位) + __init__.py 枚举 + 两组件 config.yaml + meta.json(datatable 46/system 63) + 冒烟通过(CSV 5/5: 分号导入/制表符导出/分号导出/非法分隔符/默认逗号; system 7/7: B/KB/MB/默认/get_pid空名称/fuzzy) + ruff format 通过
- SQL 改行：import_data_table_from_file(id=688)/export_data_table_to_file(id=682)/get_pid/file_info 需同步更新

### P0 收尾 ✅ 2026-08-16
- [x] 各组件 meta.json 重新生成（stub 脚本）：dataprocess 97 / system 63 / datatable 46 / browser 57 / database 10
- [x] SQL 行写入 init_c_atom_meta_new_data.sql（新 id 912-953 共42行 + 改行185/276/682/688，/tmp/sync_p0_sql.py）
- [x] atomCommon(id=19) atomicTree 挂载（/tmp/mount_p0_tree.py 纯字符串手术+括号深度感知）：data.Math+13 / data.String+13 / database+6(Sqlite) / os.file+5 / os.path+1 / process新建assert断言子分组+4
- [x] 冒烟测试全通过（P0-1~P0-6 各自冒烟均通过）
- [x] ruff format 检查（P0-5/P0-6 改动文件全过）
- [x] MySQL 8.4.6 容器全量导入验证：569行 JSON_VALID 全过，抽查新行中文title/改行参数/分类树挂载全部正确
- 注：atomicTree 挂载惯例=单原子key进分组atomics（data.Math等是嵌套子分组，条目格式 {"key","title","icon"}）

## P1 组件级（browser/win 元素能力）

### P1-1 等待任意元素 ×6（ids 954-959）✅ 2026-08-16（代码层完成，SQL/挂载待 P1 收尾）
- [x] 954 BrowserElement.wait_any_element 等待任意一个元素出现(web)（5元素槽位+各自名称，输出命中名+结果）
- [x] 955 WinEle.wait_any_element 等待任意一个元素出现(win)（同上桌面版）
- [x] 956 BrowserElement.wait_any_group 等待任意一组元素出现(web)（A/B两组各3元素，组内全出现命中，输出组名）
- [x] 957 WinEle.wait_any_group 等待任意一组元素出现(win)（同上桌面版）
- [x] 958 BrowserElement.combine_elements 组合多元素(web)（5选择器→元素列表+数量）
- [x] 959 WinEle.combine_elements 组合多元素(win)（同上桌面版）
- 完成：browser_element.py +3原子(_probe_element helper, elementIsReady探测/轮询0.3s) + winele.py +3原子(_probe_element helper, WinEleCore.find(wait_time=0)探测) + winelement/error.py 补 PARAMETER_INVALID_FORMAT + 两组件 config.yaml 各3段 + meta.json(browser 57→60, winelement 16→19) + 冒烟 web 9/9 + win 9/9 (/tmp/smoke_p11_web.py, /tmp/smoke_p11_win.py) + ruff format 通过
- 设计说明：原子框架不支持动态列表参数 → wait_any_element 用5个可选元素槽位+名称；wait_any_group 固定A/B两组各3槽位（影刀语义=组内全部出现该组命中）

### P1-2 软件(win)扩展 ×4（ids 960-963）✅ 2026-08-16（代码层完成，SQL/挂载待 P1 收尾）
- [x] 960 WinEle.get_all_attributes 获取元素全部属性（→字典；17个UIA属性白名单+BoundingRectangle+Value回退）
- [x] 961 WinEle.get_all_text 获取元素所有文本（递归子孙先序收集，分隔符合并+列表+数量）
- [x] 962 WinEle.batch_scrape 批量数据抓取(win)（相似元素=行模板，行内递归子孙文本→二维列表）
- [x] 963 WinEle.scroll_into_view 显示指定元素（ScrollItemPattern逐级向上，可选auto_click）
- 完成：winele.py 新增模块级 helpers(_UIA_ATTRIBUTE_SPECS/_collect_uia_attributes/_collect_descendant_texts reversed入栈保序) + class WinEleExtension(4原子, 装饰器key="WinEle") + meta.py register(WinEleExtension, group_key="WinEle") + config.yaml 4段 + meta.json(19→23) + 冒烟 9/9 (/tmp/smoke_p12_win.py) + ruff format 通过
- 坑：register() 默认 group_key=cls.__name__，与装饰器原子key("WinEle")不一致会 KeyError — 必须显式传 group_key；_collect_descendant_texts 用 stack LIFO 会反转兄弟顺序，children 需 reversed() 入栈

### P1-3 懒加载 ×2（ids 964-965）✅ 2026-08-16（代码层完成，SQL/挂载待 P1 收尾）
- [x] 964 BrowserElement.get_similar_lazy 获取相似元素列表-懒加载(web)（滚动+elementFromSelect轮询，连续stable轮不增停止，max_count上限）
- [x] 965 BrowserElement.get_similar_lazy_xpath 懒加载-xpath版（runJS+document.evaluate计数滚动，最后收集文本列表）
- 完成：browser_element.py +2原子 + import json + config.yaml 2段 + meta.json(60→63) + 冒烟(与P1-4合并 /tmp/smoke_p13_web.py)

### P1-4 翻页 ×1（id 966）✅ 2026-08-16（代码层完成，SQL/挂载待 P1 收尾）
- [x] 966 BrowserElement.paginator 翻页器(XPath)（迭代器原子：每页yield页码+条目文本，页体处理完后点击下一页FIRST_ORDERED_NODE，无下一页/达max_pages停止）
- 完成：browser_element.py +1原子(noAdvanced迭代器, 仿loop_similar) + config.yaml 1段 + meta.json(63) + 冒烟11/11 (/tmp/smoke_p13_web.py: 3页翻页/max_pages提前停/空xpath报错/lazy两版增长停止+max_count) + ruff format 通过
- 设计说明：paginator yield后才点击下一页（generator恢复时机=执行器处理完页体）；JS注入用json.dumps字面量不用str.format（花括号冲突）

### P1.5 数据库增强 ×3新原子+1改（ids 967-969）✅ 2026-08-16（代码层完成，SQL/挂载待 P1 收尾）
- [x] 967 Database.upsert 更新插入（主键冲突→UPDATE，每行先UPDATE后INSERT，整体事务）
- [x] 968 Database.execute_transaction 执行事务（begin/commit/rollback 三枚举）
- [x] 969 Database.run_procedure 运行存储过程（{CALL proc(?,?,...)}，pyodbc.Output输出参数+nextset消费多结果集）
- [x] 改 Database.execute_sql 加参数化查询（params 参数）+ return_format 选项（list二维/dicts字典）
- 完成：database.py +3原子+execute_sql增强 + 3枚举(SqlResultFormatFlag/TransactionActionFlag/ProcedureParamTypeFlag) + error.py 4条消息 + config.yaml 3段+execute_sql扩+3枚举options + meta.json(13原子) + 冒烟22/22 (/tmp/smoke_p15_db.py: mock pyodbc) + ruff format 通过
- 设计说明：upsert 按行先UPDATE（命中rowcount>0）后INSERT（跨库兼容，不用MySQL ON DUPLICATE/SQLServer MERGE方言）；run_procedure 输出参数类型枚举映射 pyodbc.SQL_INTEGER/SQL_VARCHAR/SQL_DOUBLE；output_types 是列表参数走 textarea（非单选RADIO）
- 坑：业务 BaseException 无 message/code 属性（元组式 args），冒烟断言用 str(e) 内容匹配

### P1 收尾 ✅ 2026-08-16
- [x] meta.json 重新生成：browser 63 / winelement 23 / database 13
- [x] SQL 行写入（/tmp/sync_p1_sql.py）：新 id 954-969 共16行 + 改行 881(Database.execute_sql 加params/return_format)，总590行(585数据行)
- [x] atomicTree 挂载（/tmp/mount_p1_tree.py 分组内锚点条目后插入）：web+6(wait_any_element/wait_any_group在wait_element后, lazy×2在similar后, paginator在web组loop_similar后, combine在get_relative_element后) / desktop+7(win版同位+batch_scrape在similar后+get_all_×2在get_element_info后+scroll_into_view在wait_element后) / database+3(upsert在execute_sql后, transaction/procedure在batch_insert后)
- [x] 坑：BrowserElement.loop_similar 在树中出现2次(code/for组+web组) — 挂载必须先定位分组边界再在分片内找锚点
- [x] MySQL 8.4.6 容器全量验证：schema.sql+data.sql 导入 585行 JSON_VALID 全过；新行中文title正确(翻页器-XPath（web）/更新插入数据/批量数据抓取（桌面))；改行881 inputList[3]=params；atomCommon树 JSON_VALID=1 且三个挂载点 JSON_SEARCH 命中
→ **P1 全部完成，断点：从 P2 开始**

## P2 引擎调度层

### P2 动态调用 ×3（ids 970-972）✅ 2026-08-16
- [x] 970 Script.run_process_dynamic 动态调用子流程（名称来自运行时变量，参数字典，输出=输出参数字典）
- [x] 971 Script.run_module_dynamic 动态调用Python模块（名称变量，v2 main(args)/v1 main(**kwargs) 双签名兼容）
- [x] 972 Script.run_command_dynamic 动态调用自定义指令（编码变量，裸c-id或c-id.main，过滤__参数）
- 完成：script.py +3原子(复用_get_auto_context/_call, 名称参数INPUT_VARIABLE_PYTHON, 参数字典TEXTAREAMODAL) + config.yaml 3段 + meta.json(6原子) + SQL 3新行(970-972)+挂载(process组Script.process后+1 / script组Script.module/Script.component后+2) + 冒烟9/9 (/tmp/smoke_p2_dynamic.py: 构造/tmp/p2_dyn工程包, v2输出回填/v1兼容/裸编码/编码.main/__参数过滤/7种错误分支) + ruff format 通过
- 设计说明：现有Script.process/module用SELECT拾取器(编译期固定选择)，动态版名称来自运行时变量，参数无法用PROCESSPARAM联动表单→用字典参数；输出统一为字典(module版返回main返回值)；组件名称映射在服务端，本地仅支持编码
- 坑：_get_auto_context 从 main 帧取 __package__（冒烟需在脚本顶层设 __package__ 模拟工程包）；裸编码 c-id 必须归一化为 c-id.main；YAML tip 含 {'k': v} 冒号必须整体加引号

---

# 第五批（2026-08-16 影刀文档 41 条对比）

> 41 条中 **已有/等价 8 条，缺失 33 条**。SQL 起始 id=973。
> 已有判定：滚动元素至可视区域(web)=BrowserElement.scroll_into_view；获取当前激活网页对象=get_current_obj；执行SQL/批量插入/SQLServer批量导入=Database组件(ODBC连接串等价表单式)；点击文本OCR(win元素/窗口)=CV.ocr_click区域参数近似；浏览器启动配置=browser_open.open_args。

## P3 纯组件级（零引擎改动）

### P3-0 字典操作 ×6（dataprocess 组件 dict.py 扩展，ids 973-978）⬜
> 挂载：data.Dict|字典操作 分组，锚点 get_values_from_dict 后追加 6 条
- [ ] 973 DictProcess.merge_dict 合并字典（被合并字典键值对更新到字典，就地修改）
- [ ] 974 DictProcess.clear_dict 清空字典（清空全部键值对）
- [ ] 975 DictProcess.strip_dict_keys 删除字典键两端空格（仅字符串键，就地重建）
- [ ] 976 DictProcess.strip_dict_values 删除字典值两端空格（仅字符串值就地strip）
- [ ] 977 DictProcess.dict_key_exist 指定键是否存在（输出布尔）
- [ ] 978 DictProcess.dict_to_text 格式成文本（项连接符+键值连接符拼接输出文本）

### P3-1 Web 元素/页面增强 ×18（browser 组件，ids 979-996）✅ 2026-08-17
> 实际挂载（调整）：web组 element_text 后 get_text_nodes / set_select 后 universal_set_select / combine_elements 后样式4+元素4；web.cookie 子组末尾存储2；web.page 子组末尾页面管理4+JS库2
**存储/文本（BrowserSoftware）**
- [x] 979 BrowserSoftware.get_session_storage 获取会话存储（sessionStorage全量字典，runJS通道）✅
- [x] 980 BrowserSoftware.get_local_storage 获取本地存储（localStorage全量字典）✅
- [x] 981 BrowserElement.get_text_nodes 获取文本节点内容（XPath//text()节点列表，runJS document.evaluate）✅
**下拉框（BrowserElement）**
- [x] 982 BrowserElement.universal_set_select 通用设置下拉框（触发元素点击+点击选项文本，非select标签下拉）✅
**页面管理（BrowserSoftware）**
- [x] 983 BrowserSoftware.cancel_html_zoom 取消HTML缩放（恢复document.documentElement zoom/transform）✅
- [x] 984 BrowserSoftware.close_other_tabs 关闭其他网页（保留指定网页关同实例其他标签）✅
- [x] 985 BrowserSoftware.force_close_web 强制关闭网页（忽略对话框提示直接关）✅
- [x] 986 BrowserSoftware.get_browser_type 获取网页对象类型（输出chrome/edge/firefox）✅
**JS库（BrowserSoftware）**
- [x] 987 BrowserSoftware.import_js_library 导入JS库（URL/文本来源注入script标签）✅
- [x] 988 BrowserSoftware.import_common_js_library 导入常用JS库（jquery/lodash/dayjs/axios/html2canvas枚举）✅
**样式（BrowserElement）**
- [x] 989 BrowserElement.get_font_color 获取元素字体颜色（computedStyle color）✅
- [x] 990 BrowserElement.get_background_color 获取元素背景颜色（computedStyle backgroundColor）✅
- [x] 991 BrowserElement.get_background_image 获取元素背景图片（backgroundImage url提取）✅
- [x] 992 BrowserElement.element_add_border 元素增加边框（粗细/样式/颜色，outline实现调试辅助）✅
**元素操作（BrowserElement）**
- [x] 993 BrowserElement.element_show 显示元素（style.display恢复）✅
- [x] 994 BrowserElement.element_hide 隐藏元素（style.display:none）✅
- [x] 995 BrowserElement.element_remove 删除元素（remove()，不可恢复）✅
- [x] 996 BrowserElement.element_long_screenshot 元素长截图（滚动拼接全元素截图）✅

### P3-2 IFrame 跨域系列 ×9（browser 组件+插件改造，ids 997-1005）✅
> 挂载：新增 web.iframe|IFrame跨域 子分组（web 组 atomics 末尾，web.network 后），9 原子全组进该子分组 ✅
> 依赖：插件 debugger evaluate 需扩展 frame 上下文执行（Runtime.evaluate 按 frameId/contextId 路由）；跨域 iframe 无法用页面内 JS 访问，必须走 CDP。✅（getFrameTree + frameContextIdMap 同源标记注入）
> 实现调整：9 原子统一收敛到新类 BrowserIframe（browser_iframe.py），非原计划的 BrowserSoftware×2+BrowserElement×7 分拆；997/998 输出/消费 frame 标识字典（Dict），999-1005 走 runJS+isFrame/iframeXpath 路由。
- [x] 997 BrowserIframe.init_iframe 初始化IFrame（序号/名称/XPath 定位，输出frame标识）✅
- [x] 998 BrowserIframe.switch_iframe 切换IFrame（支持 frame 标识数组多层切换）✅
- [x] 999 BrowserIframe.iframe_get_element_text 获取元素文本-XPath跨域 ✅
- [x] 1000 BrowserIframe.iframe_click_element 点击元素-XPath跨域 ✅
- [x] 1001 BrowserIframe.iframe_input_text 填写输入框-XPath跨域 ✅
- [x] 1002 BrowserIframe.iframe_get_similar_list 获取相似元素列表-XPath跨域 ✅
- [x] 1003 BrowserIframe.iframe_wait_element 等待元素-XPath跨域（出现/消失）✅
- [x] 1004 BrowserIframe.iframe_get_attribute 获取元素属性-XPath跨域 ✅
- [x] 1005 BrowserIframe.iframe_get_element_info 获取元素信息-XPath跨域（text/value/html）✅

---

# 第六批（2026-08-16 收到 55 条链接，已全部分析完毕）

> **状态：✅ 分析完毕**（2026-08-16 逐条 WebFetch 完成，判定依据=各组件 meta.json 全量原子清单）
> **结论**：已有 2 / 部分等价 1 / **缺失 52 新原子+1 增强** → 并入 P4 批次（P4-1 ~ P4-6），SQL id 从 1006 起。

## 待分析 URL 清单（55条，按发送顺序，✅=已分析）
1. ✅获取图片DPI → **缺失**(P4图片处理: Pillow info dpi，无DPI报错) | https://www.yingdao.com/yddoc/rpa/zh-CN/719082839649193984
2. ✅调整图片大小(按像素) → **缺失**(P4: resize宽高) | https://www.yingdao.com/yddoc/rpa/zh-CN/711982713095217152
3. ✅调整图片大小(按比例) → **缺失**(P4: 比例小数resize) | https://www.yingdao.com/yddoc/rpa/zh-CN/711982077058019328
4. ✅获取图片尺寸 → **缺失**(P4: 宽高像素) | https://www.yingdao.com/yddoc/rpa/zh-CN/711981460749762560
5. ✅转换图片格式 → **缺失**(P4: jpg/png/jpeg/bmp，支持文件夹/列表/单文件批量) | https://www.yingdao.com/yddoc/rpa/zh-CN/711980825006522368
6. ✅切割图片(按尺寸) → **缺失**(P4: 横/纵向固定像素切割,前缀_001命名,输出路径列表) | https://www.yingdao.com/yddoc/rpa/zh-CN/711980134629699584
7. ✅图片裁剪 → **缺失**(P4: left/top支持负数,宽高矩形裁剪) | https://www.yingdao.com/yddoc/rpa/zh-CN/711979444266811392
8. ✅图片拼接 → **缺失**(P4: 列表/文件夹,横/纵向拼接,覆盖/不保存) | https://www.yingdao.com/yddoc/rpa/zh-CN/711977928176910336
9. ✅图层叠加 → **缺失**(P4: png透明叠加/jpg覆盖,列表或文件夹) | https://www.yingdao.com/yddoc/rpa/zh-CN/711976493625700352
10. ✅切割图片(按比例) → **缺失**(P4: 等宽/高等分N份) | https://www.yingdao.com/yddoc/rpa/zh-CN/711975702182412288
11. ✅去除图片边框 → **缺失**(P4: 四边裁掉N像素) | https://www.yingdao.com/yddoc/rpa/zh-CN/711975102123339776
12. ✅添加图片水印 → **缺失**(P4: 水印图+x/y负数定位,批量) | https://www.yingdao.com/yddoc/rpa/zh-CN/711973794063499264
13. ✅添加文字水印 → **缺失**(P4: 文字+字体/字号/颜色/加粗/自定义字体) | https://www.yingdao.com/yddoc/rpa/zh-CN/711972415717765120
14. ✅调整图片DPI → **缺失**(P4: save带dpi参数) | https://www.yingdao.com/yddoc/rpa/zh-CN/711971663235432448
15. ✅图片相似度 → **缺失**(P4: 两图文件对比,直方图/结构相似;注意CV.is_image_exist是屏幕模板匹配≠本指令) | https://www.yingdao.com/yddoc/rpa/zh-CN/711971220144963584
16. ✅保存剪贴板图片 → **缺失**(P4: 剪贴板DIB/TIFF→文件; 现有paste_clip仅MSG/FILE/FOLDER无图片) | https://www.yingdao.com/yddoc/rpa/zh-CN/711970352514527232
17. ✅压缩图片 → **缺失**(P4: 质量参数默认85,仅png/jpg保持原格式) | https://www.yingdao.com/yddoc/rpa/zh-CN/711968772074192896
18. ✅调整图片透明度 → **缺失**(P4: 0-1浮点alpha) | https://www.yingdao.com/yddoc/rpa/zh-CN/711967476669923328
19. ✅更正扩展名 → **缺失**(P4: 嗅探真实格式改名,覆盖开关) | https://www.yingdao.com/yddoc/rpa/zh-CN/711966608559915008
20. ✅彩图转线稿 → **缺失**(P4: 反色+高斯模糊+颜色减淡三步法) | https://www.yingdao.com/yddoc/rpa/zh-CN/712875061470351360
21. ✅证件照换底色 → **缺失**(P4: 背景色替换+色差容差10~50) | https://www.yingdao.com/yddoc/rpa/zh-CN/712875106246516736
22. ✅汉字表示日期 → **缺失**(P4低优: 数字日期→"二零二三年五月一日"; 可用数字汉字转换组合但专用原子更直接) | https://www.yingdao.com/yddoc/rpa/zh-CN/716459254892777472
23. ✅常用日期 → **部分等价**(TimeProcess.format_datetime 是枚举格式; 缺自定义模板字符串+去零without_zeros → P4增强format_datetime加custom_format/without_zeros参数) | https://www.yingdao.com/yddoc/rpa/zh-CN/711915079137910784
24. ✅获取日期时间列表 → **缺失**(P4: 起止+间隔秒/分/时/天/月/年, 文本/datetime, 去零, 倒序) | https://www.yingdao.com/yddoc/rpa/zh-CN/711914092427538432
25. ✅修改日期时间 → **缺失**(P4: 替换年/月/日/时/分/秒域; 注意set_time是增减偏移≠替换) | https://www.yingdao.com/yddoc/rpa/zh-CN/711913189630971904
26. ✅URL编码 → **缺失**(P4: quote+保留字符集参数, 放encrypt加解密编解码分组或text) | https://www.yingdao.com/yddoc/rpa/zh-CN/711911423715741696
27. ✅URL解码 → **缺失**(P4: unquote+编码类型UTF-8/GBK) | https://www.yingdao.com/yddoc/rpa/zh-CN/711910567800901632
28. ✅提取表格内容(基于文本间距) → **缺失**(P4-PDF: 文本间距启发式表格,4个间距参数) | https://www.yingdao.com/yddoc/rpa/zh-CN/929718787993903104
29. ✅加密PDF → **缺失**(P4-PDF: 打开密码,输出新文件路径) | https://www.yingdao.com/yddoc/rpa/zh-CN/887272105643360256
30. ✅获取PDF表格 → **缺失**(P4-PDF: 全部/指定页'1,3,5-7'+密码+横竖线依据,输出表格list) | https://www.yingdao.com/yddoc/rpa/zh-CN/887270160383885312
31. ✅提取PDF指定区域文字 → **缺失**(P4-PDF: xy坐标区域取文本, 配合#32区域坐标) | https://www.yingdao.com/yddoc/rpa/zh-CN/765869326742605824
32. ✅获取指定类型的区域 → **缺失**(P4-PDF: 文本块/图片/表格三类区域坐标, 输出bbox列表+内容位置字典) | https://www.yingdao.com/yddoc/rpa/zh-CN/765869267699388416
33. ✅旋转PDF → **缺失**(P4-PDF: 指定页+方向+角度) | https://www.yingdao.com/yddoc/rpa/zh-CN/724076663588495360
34. ✅获取页面的高和宽 → **缺失**(P4-PDF: 指定页宽高) | https://www.yingdao.com/yddoc/rpa/zh-CN/724075143136518144
35. ✅分割PDF → **缺失**(P4-PDF: 按页分割成单页/指定位置分两半, 输出路径列表) | https://www.yingdao.com/yddoc/rpa/zh-CN/711909583481417728
36. ✅获取PDF页数 → **已有**(PDF.get_pages_num) | https://www.yingdao.com/yddoc/rpa/zh-CN/711908728924221440
37. ✅提取表格信息 → **缺失**(P4-PDF: 全文档表格→二维列表列表, auto/lines/text策略+横线距离/文本距离, 输出错误页码列表; 与#28/#30合并设计成3个表格原子) | https://www.yingdao.com/yddoc/rpa/zh-CN/711907570266914816
38. ✅提取所有图片 → **已有**(PDF.get_pdf_images) | https://www.yingdao.com/yddoc/rpa/zh-CN/711906699757694976
39. ✅删除PDF页 → **缺失**(P4-PDF: 删指定页存新文件,负数倒数) | https://www.yingdao.com/yddoc/rpa/zh-CN/711905687729061888
40. ✅添加水印(PDF) → **缺失**(P4-PDF: 水印pdf叠加+页码范围'1,5'/单页/默认全部) | https://www.yingdao.com/yddoc/rpa/zh-CN/711904383974715392
41. ✅图片转换为PDF → **缺失**(P4-PDF: img2pdf, 页面尺寸选项) | https://www.yingdao.com/yddoc/rpa/zh-CN/711903400101134336
42. ✅检测视频是否损坏 → **缺失**(P4-视频新分类: ffmpeg探测,损坏抛异常) | https://www.yingdao.com/yddoc/rpa/zh-CN/901802872987086848
43. ✅视频加图片水印 → **缺失**(P4-视频: moviepy/ffmpeg overlay+透明度+四边距) | https://www.yingdao.com/yddoc/rpa/zh-CN/712475595202052096
44. ✅获取视频时长 → **缺失**(P4-视频: ffprobe秒数) | https://www.yingdao.com/yddoc/rpa/zh-CN/711902630288764928
45. ✅切分视频 → **缺失**(P4-视频: 开始/结束时间剪辑,ffmpeg -ss -to) | https://www.yingdao.com/yddoc/rpa/zh-CN/711901705778204672
46. ✅去除视频原声 → **缺失**(P4-视频: ffmpeg -an copy) | https://www.yingdao.com/yddoc/rpa/zh-CN/711900864188497920
47. ✅视频提取音频 → **缺失**(P4-视频: 提取音轨存MP3) | https://www.yingdao.com/yddoc/rpa/zh-CN/711900021961129984
48. ✅视频转GIF → **缺失**(P4-视频: 时间段→gif) | https://www.yingdao.com/yddoc/rpa/zh-CN/711899150078914560
49. ✅调整视频速度 → **缺失**(P4-视频: setpts+atempo, rate{倍速}后缀) | https://www.yingdao.com/yddoc/rpa/zh-CN/711897974012510208
50. ✅批量加片尾 → **缺失**(P4-视频: 片尾拼接,列表批量) | https://www.yingdao.com/yddoc/rpa/zh-CN/711896937762598912
51. ✅批量加片头 → **缺失**(P4-视频: 片头拼接,列表批量) | https://www.yingdao.com/yddoc/rpa/zh-CN/711895900676919296
52. ✅拼接视频 → **缺失**(P4-视频: 两视频/批量列表JSON合并concat) | https://www.yingdao.com/yddoc/rpa/zh-CN/711894878072324096
53. ✅生成条形码 → **缺失**(P4-条码: python-barcode, ean13/code128) | https://www.yingdao.com/yddoc/rpa/zh-CN/712280150439161856
54. ✅识别二维码/条形码 → **缺失**(P4-条码: pyzbar/zxing解码,多码列表输出) | https://www.yingdao.com/yddoc/rpa/zh-CN/711923269344595968
55. ✅生成二维码 → **缺失**(P4-条码: qrcode库) | https://www.yingdao.com/yddoc/rpa/zh-CN/711922234867576832

### 第六批分析结论（55条全部分析完毕 2026-08-16）
- **已有 2**：#36 PDF.get_pages_num、#38 PDF.get_pdf_images
- **部分等价 1**：#23 format_datetime（增强：自定义模板+去零）
- **缺失 52 新原子 + 1 增强**，按子批次：
  - **P4-1 图片处理 ×21**（#1-21）：新分类 image（Pillow 一把梭）——DPI获取/调整、尺寸、resize像素/比例、格式转换、切割尺寸/比例、裁剪、拼接、图层叠加、去边框、图片水印、文字水印、相似度、剪贴板保存、压缩、透明度、扩展名更正、彩图转线稿、证件照换底色
  - **P4-2 日期时间 ×3+1增强**（#22-25）：汉字日期、日期时间列表、修改日期域 + format_datetime 增强
  - **P4-3 URL编解码 ×2**（#26-27）
  - **P4-4 PDF ×12**（#28-35,37,39-41）：表格×3（间距/线策略/区域）、区域文字+区域坐标、加密、旋转、页面宽高、分割、删页、水印、图片转PDF
  - **P4-5 视频 ×11**（#42-52）：新分类 video（ffmpeg/imageio-ffmpeg）——检测损坏、图片水印、时长、切分、去原声、提取音频、转GIF、变速、批量片头/片尾、拼接
  - **P4-6 条码二维码 ×3**（#53-55）：生成条形码/二维码、识别
- **SQL id 分配**：P4-1 起 1006（P3 用 973-1005），预计至 ~1060
- **新分类挂载**：image、video 两个新分组（atomCommon 树同步加），PDF 扩充挂 document 分组，URL编解码挂 encrypt 分组，条码挂 image 分组

---

# 第七批（2026-08-16 收到 53 条链接，已全部分析完毕）

> **状态：✅ 分析完毕**（#39 重复链接已由用户更正为 889695284131282944）
> **结论**：已有 2 / 无效链接 1 / 部分等价 8 / **缺失 42 新原子** → P5-1~P5-8，SQL id 从 1061 起

## 第七批 URL 清单（53条，✅=已分析）
1. ✅开启SSH隧道 → **缺失**(P5-网络: sshtunnel库, paramiko已引入; 输出隧道对象+本地端口) | https://www.yingdao.com/yddoc/rpa/zh-CN/712470512327782400
2. ✅关闭SSH隧道 → **缺失**(P5-网络: 关隧道对象) | https://www.yingdao.com/yddoc/rpa/zh-CN/712470731631161344
3. ✅清空打印机队列 → **缺失**(P5-系统: 打印机队列清空) | https://www.yingdao.com/yddoc/rpa/zh-CN/910712291156439040
4. ✅设置默认打印机 → **缺失**(P5-系统: win32print SetDefaultPrinter) | https://www.yingdao.com/yddoc/rpa/zh-CN/712965032793845760
5. ✅打印图片 → **已有**(System.printer file_type=PICTURE) | https://www.yingdao.com/yddoc/rpa/zh-CN/712964998521737216
6. ✅打印PDF/EXCEL/WORD/TXT文件 → **已有**(System.printer FileType PDF/WORD/EXCEL) | https://www.yingdao.com/yddoc/rpa/zh-CN/712964953968549888
7. ✅获取打印机状态 → **缺失**(P5-打印机: win32print GetPrinter状态码表) | https://www.yingdao.com/yddoc/rpa/zh-CN/712964902638424064
8. ✅获取所有打印机列表 → **缺失**(P5-打印机: EnumPrinters) | https://www.yingdao.com/yddoc/rpa/zh-CN/712964860281671680
9. ✅获取打印机工作队列 → **缺失**(P5-打印机: EnumJobs作业列表) | https://www.yingdao.com/yddoc/rpa/zh-CN/712964772665331712
10. ✅获取默认打印机 → **缺失**(P5-打印机: GetDefaultPrinter) | https://www.yingdao.com/yddoc/rpa/zh-CN/712964731688955904
11. ✅json数据提取 → **缺失**(P5-数据: 递归提取嵌套dict/list中指定键名全部值, 搭配网络监听; json_convertor仅JSON↔str≠本指令) | https://www.yingdao.com/yddoc/rpa/zh-CN/716550345677529088
12. ✅运行ADB命令 → **缺失**(P5-手机: adbutils shell, udid单设备可空) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699778070708224
13. ⚠️无效链接(页面空仅"问题没有解决", 待用户提供正确URL) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699786364305408
14. ✅手机懒加载_xpath → **缺失**(P5-手机: 滑动方向/速度/遮挡元素, XPath版) | https://www.yingdao.com/yddoc/rpa/zh-CN/853258474133286912
15. ✅手机懒加载 → **缺失**(P5-手机: 元素版, 仿browser get_similar_lazy) | https://www.yingdao.com/yddoc/rpa/zh-CN/853257935492378624
16. ✅点击(手机坐标) → **部分等价**(Phone.click_screen 有单击/双击/长按; 缺按下/抬起动作→P5增强ClickType加DOWN/UP, 用于自定义拖拽轨迹) | https://www.yingdao.com/yddoc/rpa/zh-CN/750601366195355648
17. ✅手机滚动长截屏 → **缺失**(P5-手机: 滚动截图+CV2像素拼接, 次数空=无限滚) | https://www.yingdao.com/yddoc/rpa/zh-CN/720447751096573952
18. ✅安装APK(手机) → **缺失**(P5-手机: adb install, 已装跳过) | https://www.yingdao.com/yddoc/rpa/zh-CN/765775780114898944
19. ✅删除文件夹(手机) → **缺失**(P5-手机: adb shell rm) | https://www.yingdao.com/yddoc/rpa/zh-CN/751981229114150912
20. ✅创建文件夹(手机) → **缺失**(P5-手机: adb shell mkdir, 输出新路径) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699767138910208
21. ✅删除文件(手机) → **缺失**(P5-手机: adb shell rm 文件) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699757550731264
22. ✅文件夹重命名(手机) → **缺失**(P5-手机: adb shell mv, 输出新路径) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699748611375104
23. ✅文件重命名(手机) → **缺失**(P5-手机: adb shell mv, 输出新路径) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699740115009536
24. ✅文件夹是否存在(手机) → **缺失**(P5-手机: adb shell test -d) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699730782683136
25. ✅文件是否存在(手机) → **缺失**(P5-手机: adb shell test -f) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699719834255360
26. ✅获取文件夹列表(手机) → **缺失**(P5-手机: 子文件夹列表+通配匹配+字母/时间/大小排序) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699710520000512
27. ✅刷新文件(手机) → **缺失**(P5-手机: 媒体库扫描广播MEDIA_SCANNER_SCAN_FILE) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699691212324864
28. ✅获取文件列表(手机) → **缺失**(P5-手机: 文件列表+匹配+排序) | https://www.yingdao.com/yddoc/rpa/zh-CN/889699700423016448
29. ✅生成PDF水印文件 → **缺失**(P4-4配套: 生成水印PDF(平铺/单个+透明度/灰度/旋转/字体), 与第四批#40添加水印配合使用) | https://www.yingdao.com/yddoc/rpa/zh-CN/958521267041116160
30. ✅设置屏幕缩放 → **缺失**(P5-系统: DPI缩放100%-500%, win32) | https://www.yingdao.com/yddoc/rpa/zh-CN/894511601450475520
31. ✅获取本地计算机的IP地址 → **缺失**(P5-系统: socket.gethostbyname+hostname双输出) | https://www.yingdao.com/yddoc/rpa/zh-CN/765541561665847296
32. ✅显示桌面 → **缺失**(P5-系统: Win+D/Shell MinimizeAll) | https://www.yingdao.com/yddoc/rpa/zh-CN/889083937300676608
33. ✅播放声音 → **缺失**(P5-系统: 频率Hz+时长ms蜂鸣, winsound.Beep) | https://www.yingdao.com/yddoc/rpa/zh-CN/889083927402119168
34. ✅清空回收站 → **缺失**(P5-系统: SHEmptyRecycleBin) | https://www.yingdao.com/yddoc/rpa/zh-CN/889083916681478144
35. ✅获取屏幕分辨率 → **缺失**(P5-系统: 宽/高双输出(除缩放比), 与#30缩放同组) | https://www.yingdao.com/yddoc/rpa/zh-CN/889083899296088064
36. ✅设置屏幕分辨率 → **缺失**(P5-系统: "宽*高"或宽高参数+颜色分辨率+拉伸, ChangeDisplaySettings) | https://www.yingdao.com/yddoc/rpa/zh-CN/889083885555548160
37. ✅获取计算机信息 → **缺失**(P5-系统: 名称/OS版本/处理器/系统目录/位数5输出, platform) | https://www.yingdao.com/yddoc/rpa/zh-CN/889083871187038208
38. ✅建立连接(PostgreSQL) → **缺失**(P5-PostgreSQL系列: psycopg2 地址/端口/账号/密码/库名) | https://www.yingdao.com/yddoc/rpa/zh-CN/889695301097242624
39. ✅执行sql语句(PostgreSQL) → **缺失**(P5-PG: 非查询语句, 输出受影响行数) | https://www.yingdao.com/yddoc/rpa/zh-CN/889695284131282944
40. ✅添加数据记录(PostgreSQL) → **缺失**(P5-PG: 字典方式INSERT) | https://www.yingdao.com/yddoc/rpa/zh-CN/889695259254865920
41. ✅批量添加记录(PostgreSQL) → **缺失**(P5-PG: 二维列表批量插入+单次上限) | https://www.yingdao.com/yddoc/rpa/zh-CN/889695245015203840
42. ✅执行sql查询(PostgreSQL) → **缺失**(P5-PG: 表名+字段列表+where条件式查询) | https://www.yingdao.com/yddoc/rpa/zh-CN/889695229924098048
43. ✅关闭数据库(PostgreSQL) → **缺失**(P5-PG: 关连接) | https://www.yingdao.com/yddoc/rpa/zh-CN/889695216464576512
44. ✅更新进度条进度 → ✅已实现(Dialog.update_progress id1098: 进度条对象+0-100数字, 越界clamp) | https://www.yingdao.com/yddoc/rpa/zh-CN/889697963979509760
45. ✅设置任务描述 → ✅已实现(Dialog.set_progress_description id1099: 进度条对象+描述文本) | https://www.yingdao.com/yddoc/rpa/zh-CN/889697952390647808
46. ✅初始化进度条 → ✅已实现(Dialog.init_progress_bar id1097: 可迭代对象+标题/任务名, 迭代器包装输出进度条对象接循环节点自动推进) | https://www.yingdao.com/yddoc/rpa/zh-CN/889697919830265856
47. ✅更新插入数据(MySQL) → **部分等价**(Database.upsert已实现(表名+列+键列+二维列表); 影刀版数据字典3格式(单条/行式/列式)+唯一键列表 → P5低优增强upsert支持字典格式) | https://www.yingdao.com/yddoc/rpa/zh-CN/899980509349044224
48. ✅更新数据(MySQL) → **部分等价**(execute_sql可执行UPDATE; 缺表单式原子(表名+数据字典+where) → P5低优MySQL表单三件套) | https://www.yingdao.com/yddoc/rpa/zh-CN/899980426170773504
49. ✅查询数据(MySQL) → **部分等价**(execute_sql可SELECT; 缺表单式(表名+字段列表+where含ORDER/LIMIT) → P5低优) | https://www.yingdao.com/yddoc/rpa/zh-CN/899980283019177984
50. ✅插入数据(MySQL) → **部分等价**(batch_insert占位符插入已实现; 缺数据字典3格式封装 → P5低优) | https://www.yingdao.com/yddoc/rpa/zh-CN/899980168079499264
51. ✅删除数据(MySQL) → **部分等价**(execute_sql可DELETE; 缺表单式(表名+where) → P5低优MySQL表单四件套) | https://www.yingdao.com/yddoc/rpa/zh-CN/899980064828317696
52. ✅关闭数据库连接(MySQL) → **部分等价**(Database.close已实现; 影刀为连接池概念, 我们单连接能力等价) | https://www.yingdao.com/yddoc/rpa/zh-CN/899979963602984960
53. ✅连接数据库(MySQL池) → **部分等价**(Database.connect用ODBC连接串能力等价; 缺分字段表单(host/port/账号/密码/库名+字符集/超时/连接池) → P5低优) | https://www.yingdao.com/yddoc/rpa/zh-CN/899979785974210560

### 第七批分析结论（53条全部分析完毕 2026-08-16）
- **已有 2**：#5 打印图片、#6 打印文档（System.printer）
- **无效链接 1**：#13（空页，待用户补正确URL）
- **部分等价 8**：#16 手机点击(缺按下/抬起)、#47-53 MySQL表单式系列(execute_sql/upsert/batch_insert/close能力已覆盖, 缺字典式表单封装+连接池)
- **缺失 42 新原子 + 若干增强**，按子批次：
  - **P5-1 网络SSH隧道 ×2**（#1-2）：sshtunnel 开/关
  - **P5-2 打印机 ×6**（#3-4,7-10）：清空队列/设默认/状态/列表/队列/默认
  - **P5-3 数据 ×1**（#11）：json数据提取（递归键提取）
  - ~~**P5-4 手机 ×15**（#12,14-15,17-28）：ADB命令、懒加载×2、长截屏、装APK、文件/文件夹 增删改名存在列表×10、刷新文件；+ClickType DOWN/UP增强(#16)~~ ✅ M7
  - **P5-5 系统 ×8**（#30-37）：屏幕缩放/分辨率get/set、IP、显示桌面、播放声音、清空回收站、计算机信息
  - **P5-6 PostgreSQL ×6**（#38-43）：连接/执行/查询/字典插入/批量插入/关闭（psycopg2）
  - **P5-7 Dialog进度条 ×3**（#44-46）：初始化/更新进度/任务描述（需ws前端配合）
  - **P4-4配套 ×1**（#29）：生成PDF水印文件（并入PDF批次）
  - **P5-8 低优增强**：MySQL表单式四件套+字典格式upsert+分字段连接（#47-53可选）
- **SQL id**：P4 用至 ~1060，P5 从 1061 起预计至 ~1105

## 待办总账（按此顺序执行）

> **开发计划已制定**：[DEV_PLAN.md](file:///Users/infinitelab/Desktop/astron-rpa/DEV_PLAN.md)（M1-M12 里程碑/批次详设/七步曲交付流程/风险登记册/发版策略）。本清单是进度断点，DEV_PLAN 是工程方案，两者配合使用。
1. ~~**P3-0 字典×6**（ids 973-978，dataprocess，纯Python零依赖，最快）~~ ✅ M1
2. ~~**P3-1 Web增强×18**（ids 979-996，browser，大部分走runJS通道）~~ ✅ M9
3. ~~**P3-2 IFrame跨域×9**（ids 997-1005，需插件debugger evaluate扩展frame上下文）~~ ✅ M10
4. ~~**P4-2 日期时间×3+1增强**（ids 1006-1008+改行，dataprocess，纯Python）~~ ✅ M1
5. ~~**P4-3 URL编解码×2**（ids 1009-1010，system encrypt分组）~~ ✅ M1（实际放encrypt组件）
6. ~~**P4-6 条码二维码×3**（ids 1011-1013，image分类）~~ ✅ M2-A
7. ~~**P4-1 图片处理×21**（ids 1014-1034，新组件 image，Pillow）~~ ✅ M3
8. ~~**P4-4 PDF×13**（ids 1035-1047，document组件扩充，pypdf/camelot/pdfplumber；含第七批#29生成水印PDF）~~ ✅ M4
9. ~~**P4-5 视频×11**（ids 1048-1058，新组件 video，ffmpeg依赖）~~ ✅ M5
10. ~~**P5-3 json数据提取×1**（id 1059，dataprocess，递归键提取）~~ ✅ M1
11. ~~**P5-2 打印机×6**（ids 1060-1065，system，win32print）~~ ✅ M2-B
12. ~~**P5-5 系统×8**（ids 1066-1073，system：屏幕/声音/回收站/IP/计算机信息）~~ ✅ M2-C
13. ~~**P5-6 PostgreSQL×6**（ids 1074-1079，database组件，psycopg2）~~ ✅ M6
14. ~~**P5-4 手机×15+ClickType增强**（ids 1080-1094，phone组件，adb shell系列+懒加载+长截屏）~~ ✅ M7
15. ~~**P5-1 SSH隧道×2**（ids 1095-1096，network组件，sshtunnel）~~ ✅ M8
16. ~~**P5-7 Dialog进度条×3**（ids 1097-1099，需ws前端配合，最后做）~~ ✅ M11
17. **P5-8 低优增强**（可选：MySQL表单式四件套+upsert字典格式+分字段连接）
> 顺序逻辑：纯Python优先 → 轻依赖 → 新组件（image）→ 重依赖（camelot/ffmpeg）→ 系统win32 → 手机 → 前端配合。id 分配实现时按实际微调，以本表为准记录。

## 进度日志
- 2026-08-16 清单创建，P0 开工
- 2026-08-16 P0-1~P0-4 完成（SQLite3×6/断言×4/数学×13/文件×6）
- 2026-08-16 P0-5 完成（文本×13，修 enum types 坑+汉字数字零位bug+直辖市地址）
- 2026-08-16 P0-6 完成（CSV分隔符×2/get_pid空名称/file_info单位）
- 2026-08-16 P0 收尾完成（SQL 42新行+4改行、atomCommon 挂载、MySQL 容器验证 569 行全过）→ **P0 全部完成，断点：从 P1-1 开始**
- 2026-08-16 P1-1 完成（等待任意元素×6：web/win 各 wait_any_element+wait_any_group+combine_elements，代码+config+meta+冒烟18/18）→ 断点：从 P1-2 开始
- 2026-08-16 P1-2~P1.5 完成（win扩展×4/懒加载×2/翻页×1/数据库增强×3+参数化，冒烟 9+9+11+22 全过）
- 2026-08-16 P1 收尾完成（SQL 16新行+改行881、树挂载 web+6/desktop+7/database+3、MySQL 585行全过）→ **P1 全部完成**
- 2026-08-16 P2 完成（动态调用×3：run_process_dynamic/run_module_dynamic/run_command_dynamic，冒烟9/9，SQL 970-972+挂载，MySQL 588行全过）
- 2026-08-16 最终全量验证完成（ruff format 235文件全过、py_compile 全过、dataprocess重排版文件功能复核）
- 2026-08-16 第五批41条影刀文档对比完成：已有8/缺失33，P3批次入清单（字典×6/Web增强×18/IFrame跨域×9），SQL 起始 id=973
- 2026-08-16 第六批55条链接收到（API额度不足未分析），URL 全量存档至本清单"第六批"章节，额度恢复后从 P3-0 开始实现，再回头分析第六批
- 2026-08-16 第六批55条全部分析完毕（逐条抓取+对照meta.json）：已有2(#36/#38)/部分等价1(#23)/缺失52新原子+1增强 → P4-1~P4-6 六个子批次入待办总账（图片21/日期3+1/URL2/PDF12/视频11/条码3），id 1006起
- 2026-08-16 第七批53条全部分析完毕（#39重复由用户更正）：已有2/无效1(#13待补URL)/部分等价8/缺失42新原子 → P5-1~P5-8（SSH隧道2/打印机6/json1/手机15/系统8/PG6/进度条3），待办总账更新为17步，id 至 ~1099
- 2026-08-16 **M1 纯Python速赢完成**（P3-0字典×6 ids973-978 + P4-2日期×3+1增强 ids1006-1008+改行285 + P4-3 URL×2 ids1009-1010（放encrypt组件）+ P5-3 json×1 id1059）：冒烟47/47；月步进改为按倍数锚定修复漂移（1.31→2.28→3.31）；SQL 12新行+1改行总600行全JSON_VALID；挂载 data.Dict+6/data.Time+3/data.String+1/encrypt+2 全命中；ruff+py_compile 全过 → **断点：从待办#6 P4-6条码开始（需先建 astronverse-image 组件骨架）**
- 2026-08-16 **M2-A 条码二维码×3 完成**（P4-6 ids1011-1013，新建 astronverse-image 组件：Pillow/python-barcode/pyzbar/qrcode）：冒烟21/21（生成QR尺寸/容错+CODE128+EAN13 12位补码+识别回读+一图多码+异常路径×5）；macOS arm64 pyzbar 需 brew install zbar 且 find_library 失败→代码内 monkey-patch 回退 /opt/homebrew 路径（含 sys.modules 清缓存）；SQL 3新行总603 INSERTs 全JSON_VALID；挂载 cv组+3（indices 7-9）命中；ruff+format+py_compile 全过 → **断点：从待办#11 M2-B 打印机×6 开始（ids 1060-1065）**
- 2026-08-16 **M2-B 打印机×6 完成**（P5-2 ids1060-1065，system 组件新增 printer.py Printer类 + printer_core.py 扩展管理方法）：冒烟20/20（macOS守卫×2 + fake win32print 逻辑验证：列表/默认取设/状态位掩码中文映射/作业队列字段/PURGE=3 清队列/异常×3）；原子 key 前缀取装饰器 group_key → 与 config.yaml 必须一致（"Printer."）；comment 模板不支持 `@{k||v}` 语法（引号与裸值都不行）→ **断点：M2-C 系统×8**
- 2026-08-16 **M2-C 系统×8 完成**（P5-5 ids1066-1073，system 组件新增 screen.py Screen类×3 + device.py Device类×5）：冒烟24/24（IP/计算机信息 macOS 真实执行 + Win专有×6 平台守卫 + 参数校验×6 全平台生效 + 缩放档位表）；Win 专有逻辑用 ctypes 惰性导入（分辨率 EnumDisplaySettingsW/ChangeDisplaySettingsW、缩放注册表 LogPixels、回收站 SHEmptyRecycleBinW、桌面 Shell.Application、蜂鸣 winsound.Beep）
- 2026-08-16 **M2 收尾完成**：SQL 14新行总617 INSERTs 全 JSON_VALID；挂载 os.printer+6 / os.system+8 全命中；ruff format + py_compile 全过（system 组件 F403/F405 star-import 为存量风格未清理）→ **断点：从待办#7 P4-1 图片处理×21 开始（ids 1014-1034，astronverse-image 组件扩充）**
- 2026-08-16 **M3 图片处理×21 完成**（P4-1 ids1014-1034，image 组件新增 image.py ImageProcess类×21 + 枚举4 + numpy依赖）：冒烟39/39（随机纹理图防假通过；剪贴板 macOS 真机往返 osascript PNGf；批量类文件夹/列表/单文件三态；水印负值定位；相似度改逐像素相关——直方图法对均匀噪声假通过0.99；透明度去双重衰减paste坑；DPI PNG px/m 换算±0.01误差断言容差）；**相似度教训**：均匀随机噪声两图直方图几乎相同（都均匀分布），直方图相关系数0.99假通过 → 改灰度逐像素 Pearson 相关（同图=1/噪声对≈0.003）
- 2026-08-16 **M3 收尾完成**：SQL 21新行总638 INSERTs 全 JSON_VALID（1014-1034 按 id 插入 1013 后而非末尾追加——sync 工具改为定位插入模式）；**新建顶级分组 image"图片处理"**（挂 desktop 后 phone 前，21图片+3条码入组，cv 组条码保留多分组共存）；MySQL 容器 rpa_verify 全量验证过（638行/JSON_VALID=0错/树命中抽查4/4）；ruff+format+py_compile+YAML(24段/6枚举) 全过 → **断点：从待办#8 P4-4 PDF×13 开始（ids 1035-1047，document 组件扩充，pypdf/pdfplumber/reportlab）**
- 2026-08-16 **M4 PDF×13 完成**（P4-4 ids1035-1047，pdf 组件新增 pdf_ext.py PDFExt类×13 + 枚举4 + reportlab依赖）：表格×3（lines/text双策略+auto回退，camelot 未引入——pdfplumber 全覆盖，R2 风险消除）、区域×2（bbox 左上原点换算 pdfplumber 左下原点；词按行聚类）、加密/旋转/页面尺寸/分割/删页（页码语法统一 parse_page_ranges：'1,3,5-7' 负数倒数 翻转区间 越界段忽略）、图片合并PDF（EXIF方向自动纠正）、水印×2（生成 reportlab CID中文字体 STSong-Light + 叠加 merge_page）；冒烟39/39（reportlab 现场造线框表格+无线表格+3页PDF；加密后 pypdf 解密验证；旋转断言 page.rotation）；**冒烟抓到 bug**：_open_plumber 异常分支 BaseException 单参 raise → TypeError（签名需 (error_code, message) 两参）
- 2026-08-16 **M4 收尾完成**：SQL 13新行总651 INSERTs 全 JSON_VALID（1035-1047 定位插入）；挂载 document.PDF 子分组（锚点 convert_img_to_pdf 后13原子，边界校验过）；MySQL 容器 rpa_verify 全量验证过（651行/JSON_VALID=0错/PDFExt 13行落位1035-1047/树JSON_SEARCH命中/id 1014-1047 连续34行无断档）；ruff --fix 6处+手动2处全过；**meta生成新坑**：pdf.py 平台守卫 Darwin 直接抛错且 core_unix 是未实现抽象方法的占位类 → 改 sys.platform="win32" 会连累 stdlib（shutil→_winapi 崩）→ 正确姿势：预载 core_win 顶替 sys.modules['astronverse.pdf.core_unix'] + patch platform.system()→"Linux"（/tmp/gen_meta_pdf.py）→ **断点：从待办#9 P4-5 视频×11 开始（ids 1048-1058，新组件 astronverse-video，imageio-ffmpeg）**
- 2026-08-17 **M5 视频×11 完成**（P4-5 ids1048-1058，新建 astronverse-video 组件：imageio-ffmpeg 自带静态 ffmpeg 二进制免系统安装）：Video类×11——check_video_valid（ffprobe 校验不抛错）/ get_video_duration（秒，保留3位小数）/ cut_video（起止秒，-ss 前 -to 后） / remove_audio（-an 保留视频轨）/ extract_audio（mp3/wav/aac 三格式 -vn -acodec）/ video_to_gif（fps+宽度等比缩放 lanczos 单程直出）/ set_video_speed（atempo 链式适配 0.25-4.0 音频变速极限）/ batch_prepend+batch_append（批量片头片尾，filter concat 再编码统一）/ concat_videos（多视频拼接，probe 预检分辨率不一致报错提示）/ add_video_watermark（九宫格定位+透明度 overlay 全程显示）；枚举2（AudioFormatType/WatermarkPositionType）；冒烟27/27（ffmpeg 现场造 testsrc2+随机纹理视频+正弦音频，全链路时长断言±0.3s容差/水印输出 ffprobe 验证/损坏文件校验False/分辨率不一致拼接报错）
- 2026-08-17 **M5 收尾完成**：SQL 11新行总662 INSERTs 全 JSON_VALID（1048-1058 定位插入 1047 后）；**新建顶级分组 video"视频处理"**（挂 image 后 phone 前，11原子入组）；MySQL 容器全量验证过（662行/JSON_VALID=0错/Video 11行落位1048-1058/树JSON_SEARCH命中4/4/顶层18组顺序 image→video→phone 正确/组内末位 add_video_watermark）；ruff+py_compile 全过 → **断点：从待办#13 M6 P5-6 PostgreSQL×6 开始（ids 1074-1079，database 组件，psycopg2）**
- 2026-08-17 **M6 PostgreSQL×6 完成**（P5-6 ids1074-1079，database 组件新增 postgresql.py Postgres类×6 + psycopg2-binary 2.9.12 依赖）：connect（host/port/user/password/dbname 五参 + connect_timeout=30 + 端口空默认5432字符串转int）/ execute_sql（非查询→受影响行数，DDL rowcount=-1 归0）/ query_table（表名+字段列表+where 条件式拼接，空字段→*，标识符双引号转义防注入 `"us""ers"`）/ insert_dict（字典参数化 `%(col)s` 风格直接绑字典，失败回滚）/ batch_insert（二维列表+单次执行上限分批 executemany 每批一 commit，中途失败回滚）/ close；冒烟35/35（mock psycopg2 全接口 FakeConnection/FakeCursor：kwargs透传/SQL拼接断言/分批2/2/1/每批提交×3/行转元组/回滚×2/参数校验×4）；**重要发现**：database 组件 error.py 未定义业务 BaseException（不同于 video/system 组件），postgresql.py 内 BaseException 是内置名 → `except BaseException: raise` 前置使 `except Exception` 包装分支成死代码，驱动错误原样抛出——与既有 Database(pyodbc)/Sqlite 行为一致，保持不动，冒烟按真实行为断言
- 2026-08-17 **M6 收尾完成**：meta.json 13→19原子（既有13原子对比SQL现值零漂移）；SQL 6新行总668 INSERTs 全 JSON_VALID（1074-1079 追加末尾=定位插入1058后自然落位）；挂载 database 分组 Sqlite.close 后（Database×7→Sqlite×6→Postgres×6 共19条目，纯字符串括号深度扫描断言顺序——atomCommon 行禁 JSON 往返经验#3）；MySQL 容器全量验证过（668行/JSON_VALID=0错/Postgres 6行落位/树JSON_SEARCH命中2/2）；ruff format 9文件+py_compile+YAML(19原子/4枚举) 全过 → **断点：从待办#14 M7 P5-4 手机×15+ClickType增强 开始（ids 1080-1094，phone 组件，adb shell 系列+懒加载+长截屏）**
- 2026-08-17 **M7 手机×15+ClickType增强 完成**（P5-4 ids1080-1094，phone 组件 phone.py/phone_core.py 扩展）：run_adb_command（独立 adbutils 直连，udid 空=自动选择）/ lazy_load+lazy_load_xpath（反复滑动直至 xpath 命中，_xpath_exists 不等待探测+_locate_built_xpath 命中后取元素）/ scroll_screenshot（逐屏截图+滑动+重叠行拼接；重叠查找=量化行哈希(灰度>>3)建索引→候选k→5采样点均值差<3.0 验证；到底判停=新屏与上屏 array_equal；次数0=无限带 hard_cap=50 兜底；仅支持上/下方向）/ install_apk（u2: app_install；appium: mobile: installApp→adbutils install 回退）/ 文件系×10（rm -f/rm -rf/mkdir -p/mv×2/[ -f ]&[ -d ] echo 1|0/ls -1p 尾斜杠分文件目录+fnmatch 通配+升降序/MEDIA_SCANNER 广播）统一走 _adb_shell（u2: device.shell；appium: mobile: shell→adbutils 按 serial 回退）；ClickType 加 DOWN/UP（u2: touch.down/up；appium: W3C ActionChains pointerDown/Up 拼自定义拖拽轨迹）+ 新枚举 ListSortType；adbutils 显式入 pyproject 依赖；冒烟20/20（u2 全接口含合成1000行唯一纹理长图逐像素断言拼接+mock shell 命令串断言+appium mobile: shell/installApp/lazy/w3c）+ 回归47/47
- 2026-08-17 **M7 收尾完成**：meta.json 25→40原子（+15，改2：click_element/click_screen ClickType options，零标签漂移）；SQL 15新行+2改行(887/888)总683 INSERTs 全 JSON_VALID；挂载 phone 分组 get_ui_tree 后15原子（LOCATE 顺序 get_ui_tree<run_adb_command<refresh_file 验证过）；MySQL 容器全量验证过（683行/JSON_VALID=0错/ids 1080-1094 落位/树JSON_SEARCH命中/887+888 含 down+up options）；ruff format 5文件+py_compile 全过（14条 lint 全为存量未新增）→ **断点：从待办#15 M8 P5-1 SSH隧道×2 开始（ids 1095-1096，network 组件，sshtunnel）**
- 2026-08-17 **M8 SSH隧道×2 完成**（P5-1 ids1095-1096，network 组件新增 ssh_tunnel.py SshTunnel类 + sshtunnel 0.4.0 依赖）：open_ssh_tunnel（跳板机 host/port/user + SshLoginMode 密码/密钥双认证——密钥时 password 作 ssh_private_key_password 私钥口令；remote_bind_address 转发目标；local_port 空/0 → local_bind_address ("127.0.0.1",0) 自动分配；ssh_config_file=None 防本机 ~/.ssh/config 干扰；双输出 隧道对象+tunnel.local_bind_port 实际端口）/ close_ssh_tunnel（stop() 幂等，None/无效对象错误包装）；校验链：remote_host 空→remote_port≤0→KEY 缺 key_path→私钥文件存在性；冒烟22/22（MockForwarder 参数映射密码/密钥/端口默认 + 7 错误分支 + 真实 127.0.0.1:1 连接拒绝包装验证）；**新坑**：ErrorCode.format() 原地污染模板（message 被 format 结果覆写，第二次 format 静默返回首次文本）→ 冒烟同一 FORMAT 多分支只有第一个能断言全文；atomic_run 过滤 None 值 kwarg → None 校验分支 direct call 不可达（改传无效对象测）
- 2026-08-17 **M8 收尾完成**：meta.json 12→14原子（零丢失零漂移）；SQL 2新行总685 INSERTs 全 JSON_VALID；挂载 network「网络」→ftp「FTP」子分组末尾 ftp_delete 后（SFTP 附近，DEV_PLAN 要求位置）；MySQL 容器全量验证过（685行/JSON_VALID=0错/ids 1095-1096 落位 title 正确/树JSON_SEARCH 命中2/2/login_mode RADIO+default password+密码连接密钥连接/双输出 local_bind_port）；ruff format+I001 fix+py_compile 全过 → **断点：从待办#16 M11 P5-7 Dialog进度条×3 开始（ids 1097-1099，需 ws 前端配合）或 P3-1/P3-2 Web×27（ids 979-1005）**
- 2026-08-17 **M9 Web增强×18 完成**（P3-1 ids979-996，browser 组件 browser_element.py×10+browser_software.py×8，全走 runJS 通道 send_browser_extension）：存储2（sessionStorage/localStorage 全量字典）/文本1（get_text_nodes TreeWalker 遍历文本节点）/下拉1（universal_set_select 触发点击+300ms轮询精确→包含匹配，兼容 li/[role=option]/组件库类名）/页面管理4（cancel_html_zoom zoom+transform+viewport 三清 / close_other_tabs getAllTabs 遍历 closeTab / force_close_web 扩展通道失败回退 window.close / get_browser_type）/JS库2（URL/文本注入 script 标签 + 5常用库 jsdelivr CDN 枚举）/样式4（computedStyle 颜色×2+backgroundImage url 正则提取+outline 边框）/元素4（show/hide/remove + element_long_screenshot 滚动分段截屏拼接）；新枚举3（JsImportType/CommonJsLibType/BorderStyleType）；冒烟31/31（**FakeBrowser+node fake DOM 执行生成 JS 全链路验证**：sessionStorage 键遍历/异步下拉命中与超时/url() 正则提取/长截图 PIL 断言拼接尺寸700×1500+滚动恢复；**冒烟抓到 bug**：长截图 step<视口高时段间重叠导致总高超元素实际高 → 段高改 min(step,剩余高度,视口高) 修复）
- 2026-08-17 **M9 收尾完成**：meta.json 63→81原子（零丢失零漂移，枚举 options RADIO/SELECT 正确）；SQL 18新行总703 INSERTs 全 JSON_VALID（**id 映射按本清单文档规划修正**——初版按类分组排序与文档不一致，一次性脚本重排）；挂载 web组3锚点+web.cookie 末尾+web.page 末尾共5处（锚点顺序 element_text→get_text_nodes/set_select→universal_set_select/combine_elements→8原子/cookie 尾/page 尾验证过）；MySQL 容器全量验证过（703行/JSON_VALID=0错/ids 979-996 落位正确/树JSON_SEARCH命中/枚举 options 落库抽查）；ruff format+I001 fix+py_compile 全过 → **断点：M10 P3-2 IFrame跨域×9（ids 997-1005，最高风险：插件CDP frame改造）或 M11 P5-7 进度条×3（ids 1097-1099，前端ws联调）**
- 2026-08-17 **M10 IFrame跨域×9 完成**（P3-2 ids997-1005）：**插件改造**（debugger.ts）：新增 getFrameTree（Page.getFrameTree 取帧树）；handleAttachedTarget 修复 `||0` frameId 回退污染主文档上下文（改空串回退+未打标帧不映射）；attachDebugger/enableRuntime/detachDebugger 补返回值；同源帧靠内容脚本注入 `rpa_debugger_on` 标记识别，跨域帧走 CDP Target.setAutoAttach+frameContextIdMap 路由。**引擎侧**：browser_iframe.py 新类 BrowserIframe（init_iframe 序号/名称/XPath+父frame 定位输出frame标识 / switch_iframe 数组多层切换 / 元素7原子 text/click/input/similar_list/wait/attribute/info 全走 runJS+isFrame/iframeXpath）；Browser 加 frame 属性记录当前帧；新枚举 FrameLocateType/FrameWaitStatusTypeFlag。冒烟51/51（FakeBrowser+node 多文档 fake DOM 路由：主文档/同源子iframe/嵌套iframe 查找链 + 参数校验/错误分支）
- 2026-08-17 **M10 收尾完成**：meta.json 81→90原子（零丢失零漂移）；SQL 9新行总712 INSERTs 全 JSON_VALID；挂载 web 组 atomics 末尾新建子分组 web.iframe|IFrame跨域（web.cookie→web.page→web.file→web.network→web.iframe 顺序验证过，9原子全组进该子分组）；MySQL 容器全量验证过（712行/JSON_VALID=0错/ids 997-1005 落位/树JSON_SEARCH 命中组键+首尾原子+title/枚举 options 落库：997含"序号"1003含"等待消失"）；ruff format（browser_iframe.py 格式化后冒烟51/51复跑无回归）+py_compile 全过 → **断点：M11 P5-7 进度条×3（ids 1097-1099，前端ws联调）或 M12 可选增强（#17 P5-8 低优）**
- 2026-08-17 **M11 进度条×3 完成**（P5-7 ids1097-1099，dialog 组件 dialog.py +ProgressBar 类×3 原子）：init_progress_bar（可迭代对象+标题/任务名→进度条对象，**迭代器包装**：每次 __next__ 推 update+percent 自动算 round(current*100/total)，StopIteration 推 close 100；无 len 对象（生成器）total=0 进"未知总数"模式 percent=None 前端只显示计数不显示百分比）/ update_progress（手动 0-100，越界 clamp 非数字归0）/ set_progress_description（描述更新+当前进度重推）；消息协议 **name='progress' 完全复用 send_notification 通道零改 ws.py**（payload: operate open/update/close + progress_id(uuid4) + title/task_name/percent/current/total）；输出 types="List" 兼容循环节点（ProgressBar 有 __iter__/__next__）；ws 推送 try/except 全吞（断连不阻断流程）；对象参数无注解（M8 惯例）。**前端**：useRunningStore handleProgress（antd Progress VNode h() 渲染 bottomRight/duration 0 不自动关/key=progress_id 复用更新/percent None 时按 current/total 现算）+ activeProgressIds 跟踪 + reset() 统一 close 清理。冒烟35/35（FakeWs 断言消息序列 open+3update+close/percent 33-67-100/progress_id 全程一致/生成器未知总数/越界收敛/描述更新/无效对象 ValueError×2/ws 抛异常迭代照常/无 ws 不崩）
- 2026-08-17 **M11 收尾完成**：meta.json 8→11原子（零丢失零漂移）；SQL 3新行总715 INSERTs 全 JSON_VALID；挂载 dialog 分组 message_notification 后3原子（LOCATE 顺序验证过）；MySQL 容器 rpa 库重建全量验证过（715行/JSON_VALID=0错/ids 1097-1099 落位 title 对/树3命中/顺序对）；ruff format+py_compile 过，lint 净增1（implicit-optional `iterable: list = None`——组件存量同款风格 11 个，且 `list | None` UnionType 注解会崩 gen_type issubclass 只能保留）；vue-tsc useRunningStore 零错误（7 个存量错误在未改动文件 http/AtomForm/SettingCenterModal/components包）→ **M1-M11 全部完成，v1.6.0（进度条，前端同版本要求）可发版；剩 M12 可选增强（用户点名再做）**

## 总结
- **前四批已全部完成**：P0(42新原子+4改) + P1(17新原子+1改) + P2(3新原子) = **62个新原子 + 5个增强改原子**，SQL id 912-972（61新行）+ 改行185/276/682/688/881，总588数据行
- **M1 已完成**（2026-08-16）：12新原子+1增强（ids 973-978/1006-1010/1059 + 改行285），总600数据行
- **M2 已完成**（2026-08-16）：**M2 全部完成**：条码×3（1011-1013，新组件 astronverse-image）+ 打印机×6（1060-1065）+ 系统×8（1066-1073），冒烟 21+20+24=65/65，总617数据行
- **M3 已完成**（2026-08-16）：图片处理×21（1014-1034，ImageProcess类），冒烟 39/39，新顶级分组 image（图片处理），总638数据行
- **M4 已完成**（2026-08-16）：PDF×13（1035-1047，PDFExt类，camelot降级为pdfplumber双策略），冒烟 39/39，挂载 document.PDF 子分组，总651数据行
- **M5 已完成**（2026-08-17）：视频×11（1048-1058，新组件 astronverse-video/Video类，imageio-ffmpeg），冒烟 27/27，新顶级分组 video（视频处理），总662数据行
- **M6 已完成**（2026-08-17）：PostgreSQL×6（1074-1079，database组件/Postgres类，psycopg2-binary），冒烟 35/35（mock），挂载 database 分组 Sqlite 后，总668数据行
- **M7 已完成**（2026-08-17）：手机×15+ClickType增强（1080-1094+改行887/888，phone组件，adb shell系列+懒加载+长截屏），冒烟 20/20+回归47/47，挂载 phone 分组末尾，总683数据行
- **M8 已完成**（2026-08-17）：SSH隧道×2（1095-1096，network组件/SshTunnel类，sshtunnel），冒烟 22/22，挂载 network→ftp 子分组末尾（SFTP附近），总685数据行 → **M5+M7+M8 齐活，v1.4.0（视频/手机/隧道）可发版**
- **M9 已完成**（2026-08-17）：Web增强×18（979-996，browser组件，runJS通道），冒烟 31/31（FakeBrowser+node fake DOM），挂载 web组/web.cookie/web.page 5处，总703数据行
- **M10 已完成**（2026-08-17）：IFrame跨域×9（997-1005，browser组件 BrowserIframe类+插件CDP frame改造），冒烟 51/51（FakeBrowser+node 多文档 fake DOM），新建 web.iframe 子分组，总712数据行 → **v1.5.0（Web增强+IFrame）可发版**
- **M11 已完成**（2026-08-17）：进度条×3（1097-1099，dialog组件 ProgressBar迭代器包装+前端useRunningStore handleProgress渲染，ws零改动复用send_notification通道），冒烟 35/35，挂载 dialog 分组末尾，总715数据行 → **v1.6.0（进度条，前端同版本要求）可发版；M1-M11 全部完成**
- **待办**：仅剩 M12 可选增强（P5-8 低优，用户点名再做）
- **挂起**：#13 无效链接待用户提供正确 URL
- 未做发版：代码变更待用户确认后按需 commit/release（本清单仅记录实现）
- 下一个可用 c_atom_meta_new id：**1100**（973-1099 全部用完）
