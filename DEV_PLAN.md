# RPA 缺失功能开发计划（P3-P5 全量）

> 制定日期：2026-08-16 ｜ 依据：MISSING_FEATURES.md 第五/六/七批分析结论
> 范围：**128 个原子**（P3×33 + P4×53 + P5×42）+ 若干增强项
> 配套文档：MISSING_FEATURES.md（断点清单）｜LESSONS_LEARNED.md（经验库）｜tools/sync_atom_sql.py + mount_atom_tree.py（SQL/挂载工具）

---

## 一、总体里程碑（按依赖与风险排序）

| 阶段 | 批次 | 原子数 | 组件 | 新依赖 | 风险 |
|---|---|---|---|---|---|
| M1 纯Python速赢 | P3-0 / P4-2 / P4-3 / P5-3 | 6+3+2+1=12 | dataprocess/system | 无 | 低 |
| M2 轻依赖 | P4-6 / P5-2 / P5-5 | 3+6+8=17 | image新/system | qrcode/pyzbar/python-barcode；win32print | 低-中 |
| M3 新组件image | P4-1 | 21 | **新组件 astronverse-image** | Pillow | 中 |
| M4 PDF扩充 | P4-4 | 13 | document | pypdf/camelot-py/pdfplumber/reportlab(水印) | 中（camelot重） |
| M5 视频新组件 | P4-5 | 11 | **新组件 astronverse-video** | imageio-ffmpeg(自带ffmpeg二进制) | 中 |
| M6 数据库扩展 | P5-6 | 6 | database | psycopg2-binary | 低 |
| M7 手机扩展 | P5-4 | 15+ClickType增强 | phone | 无（adbutils已有） | 中（真机验证） |
| M8 网络 | P5-1 | 2 | network | sshtunnel | 低 |
| M9 Web增强 | P3-1 | 18 | browser | 无（runJS） | 中 |
| M10 IFrame跨域 | P3-2 | 9 | browser+插件 | 插件CDP改造 | **高** |
| M11 前端配合 | P5-7 | 3 | dialog+web前端 | ws通道扩展 | 中（跨端） |
| M12 可选增强 | P5-8 | 0新原子 | database | 无 | 低（按需） |

排序原则：先易后难、先后端后前端、新依赖重的靠后、需要跨端联调的压轴。每阶段结束做一次全量验证（ruff format + py_compile + MySQL 导入校验），阶段成果即时可发版。

---

## 二、批次详细计划

### M1-A P3-0 字典操作 ×6（ids 973-978）
- **文件**：dataprocess/dict.py 追加 6 原子 + config.yaml 6 段 + meta 重生成
- **原子**：merge_dicts / clear_dict / strip_dict_keys / strip_dict_values / dict_key_exists / dict_to_text
- **要点**：strip 系列返回新字典（影刀语义：不修改原字典时输出副本）；dict_to_text 用 json.dumps ensure_ascii=False
- **冒烟**：merge 冲突键后者覆盖、strip 嵌套不递归（仅一级键）、key_exists 布尔输出
- **挂载**：data.Dict 组，锚点 get_values_from_dict 后

### M1-B P4-2 日期时间 ×3+1增强（ids 1006-1008 + 改行 format_datetime）
- **原子**：date_to_chinese（汉字日期）/ get_datetime_list（起止+间隔枚举）/ modify_datetime（替换域）
- **增强**：format_datetime 加 custom_format(str模板)+without_zeros(去零) 参数，向后兼容
- **注意**：modify_datetime 与 set_time（偏移）语义区分要在 tip 里写清；get_datetime_list 间隔单位枚举：秒/分/时/天/月/年，月年用 dateutil relativedelta 步进
- **冒烟**：汉字日期含"零"处理（一零月→十月）、月末步进不越界（1.31+1月=2.28）

### M1-C P4-3 URL编解码 ×2（ids 1009-1010）
- **文件**：system/encrypt_core.py 追加；挂 encrypt|加解密编解码 分组
- **原子**：url_encode(保留字符集参数 safe) / url_decode(编码类型 UTF-8/GBK)
- **冒烟**：中文/空格/%2B往返、GBK解码

### M1-D P5-3 json数据提取 ×1（id 1059）
- **文件**：dataprocess/dataconvert.py 追加 extract_json_key
- **要点**：递归遍历 dict/list，收集所有匹配键名的值；输入若为 str 先 json.loads 尝试；未匹配返回 []
- **冒烟**：嵌套3层、列表内dict、str输入、无匹配返回[]

### M2-A P4-6 条码二维码 ×3（ids 1011-1013）
- **文件**：新 image 组件与 P4-1 同组件，barcode.py；依赖 qrcode / pyzbar / python-barcode（pyzbar 需系统 zbar 库：Windows 打包带 dll，macOS brew install zbar）
- **原子**：create_qrcode(内容/尺寸/容错/保存路径) / create_barcode(内容/类型ean13|code128/路径) / recognize_code(图片路径→多码结果列表)
- **风险**：pyzbar 系统依赖打包（nsis/electron-builder 需带上 zbar dll）→ 打包脚本要改
- **冒烟**：生成→识别往返断言

### M2-B P5-2 打印机 ×6（ids 1060-1065）
- **文件**：system/printer_core.py 扩展（win32print 懒加载，macOS stub 冒烟）
- **原子**：clear_print_queue / set_default_printer / get_printer_status(状态码+含义字典) / get_printer_list / get_print_jobs / get_default_printer
- **冒烟**：mock win32print 全接口；状态码表按影刀 Win32 值映射

### M2-C P5-5 系统 ×8（ids 1066-1073）
- **文件**：system 新建 screen_core.py（缩放/分辨率）+ misc 追加（IP/显示桌面/蜂鸣/回收站/计算机信息）
- **原子**：set_screen_scale(DPI%枚举) / get_screen_resolution / set_screen_resolution("宽*高") / get_ip_address(host+ip双输出) / show_desktop / play_sound(winsound.Beep 频率+ms) / empty_recycle_bin(SHEmptyRecycleBin) / get_computer_info(5输出)
- **平台**：屏幕类仅 Windows（macOS 拦截报错，同 IME 模式）；分辨率 get 跨平台
- **冒烟**：macOS 上 mock/stub 走通参数校验分支

### M3 P4-1 图片处理 ×21（ids 1014-1034）
- **新组件脚手架**：astronverse-image（仿 datatable 结构：pyproject/src/astronverse/image/{__init__,image.py,error.py}/config.yaml/meta.py），依赖 Pillow
- **meta.py 注册 + engine components 清单 + 服务端/编辑器分类树新增 image 分组**（挂 desktop 后，仿 phone 分类插入）
- **原子清单**（21）：get_image_dpi / set_image_dpi / get_image_size / resize_image_pixels / resize_image_scale / convert_image_format / split_image_size / split_image_ratio / crop_image / join_images / overlay_images / trim_image_border / add_image_watermark / add_text_watermark / image_similarity / save_clipboard_image / compress_image / set_image_opacity / correct_extension / image_to_sketch / replace_id_photo_bg
- **实现要点**：
  - 批量类（格式转换/水印）输入支持 单文件|文件夹|列表，统一 _iter_images() 帮助函数
  - image_similarity：同尺寸直方图相关性 + 不同尺寸先 resize 归一，输出 0-1
  - save_clipboard_image：win32clipboard DIB→PIL（Windows）/ NSPasteboard TIFF（macOS）
  - replace_id_photo_bg：容差色差替换（HSV 距离），输出新图
  - image_to_sketch：灰度→反色→高斯模糊→color_dodge 三步
  - correct_extension：PIL format 嗅探（JPEG/PNG/BMP/GIF/WEBP）改扩展名，覆盖开关
- **冒烟**：全部用 Pillow 现场生成随机纹理图测试（纯色图在相似度/模板类会假通过，教训见经验库）；批量类测文件夹遍历

### M4 P4-4 PDF ×13（ids 1035-1047）
- **文件**：document 组件 pdf 相关模块扩展；依赖 pypdf / pdfplumber（表格+文本区域）/ reportlab+Pillow（生成水印PDF）；camelot 仅"线策略"表格用，装不上时降级 pdfplumber
- **原子**（13）：extract_table_spacing(#28) / extract_table_lines(#37合并设计) / get_pdf_table(#30页码选择) / extract_region_text(#31) / get_typed_regions(#32) / encrypt_pdf(#29) / rotate_pdf / get_page_size / split_pdf / delete_pdf_pages / add_pdf_watermark(#40叠加) / create_watermark_pdf(第七批#29生成) / images_to_pdf
- **页码语法统一**：'1,3,5-7'，负数倒数，写公共 parse_page_ranges() 
- **冒烟**：用 reportlab 现场造带表格/多页 PDF 测全链路；加密后 pypdf 解密验证

### M5 P4-5 视频 ×11（ids 1048-1058）
- **新组件 astronverse-video**，依赖 imageio-ffmpeg（PyPI 自带 ffmpeg 静态二进制，免系统安装）
- **原子**（11）：check_video_valid / get_video_duration / cut_video / remove_audio / extract_audio / video_to_gif / set_video_speed / batch_prepend / batch_append / concat_videos / add_video_watermark
- **实现**：统一 _ffmpeg() 返回 imageio-ffmpeg 路径，subprocess 封装 + 返回码/ stderr 检查；拼接先 probe 分辨率一致性，不一致报错提示
- **冒烟**：ffmpeg 现场生成 testsrc 短视频跑全部原子（macOS 本机可跑，无需真机）

### M6 P5-6 PostgreSQL ×6（ids 1074-1079）
- **文件**：database 组件新 postgresql.py，class Postgres；依赖 psycopg2-binary
- **原子**：connect(host/port/user/password/dbname) / execute(sql非查询→受影响行数) / query(表名+字段列表+where→行式列表) / insert_dict(字典INSERT) / batch_insert(字段列表+二维列表+单次上限) / close
- **meta.py 注册 Postgres**；分类树挂 database 分组（Sqlite 后）
- **冒烟**：mock psycopg2 连接/游标全接口（仿 pyodbc mock 模式）；如本机有 docker postgres 可选真连验证

### M7 P5-4 手机 ×15 + ClickType增强（ids 1080-1094）
- **文件**：phone 组件 phone.py/phone_core.py 扩展
- **ClickType 增强**：加 DOWN/UP 两成员（按下/抬起，配合 swipe 拼自定义拖拽轨迹）；双模式分发（u2: touch.down/up；appium: W3C ActionChains pointerDown/Up）
- **原子**（15）：run_adb_command(udid可空) / lazy_load(元素版) / lazy_load_xpath / scroll_screenshot(滚动+CV2拼接,次数空=无限) / install_apk / delete_file / delete_folder / create_folder / rename_file / rename_folder / file_exists / folder_exists / get_file_list(通配+排序) / get_folder_list(通配+排序) / refresh_file(MEDIA_SCANNER广播)
- **文件系类统一走 `_adb_shell(conn, cmd)` 帮助函数**（u2: conn.device.shell；appium: adb 命令），列表类用 `ls -p` 区分文件/文件夹 + Python 侧 fnmatch+sorted
- **冒烟**：mock adbutils Device.shell 返回样本；长截屏 mock 截图序列测拼接算法（Pillow np 相似度找重叠行）
- **风险**：真机回归放最后（用户手头设备），冒烟以 mock 为准

### M8 P5-1 SSH隧道 ×2（ids 1095-1096）
- **文件**：network 组件新 ssh_tunnel.py；依赖 sshtunnel（paramiko 已有）
- **原子**：open_ssh_tunnel(跳板 host/port/user/密码或密钥 + 目标 host/port + 本地端口可空自动分配 → 隧道对象+实际本地端口) / close_ssh_tunnel(隧道对象)
- **挂载**：network 分组 sftp 附近
- **冒烟**：mock SSHTunnelForwarder 验证参数映射与错误分支

### M9 P3-1 Web增强 ×18（ids 979-996）
- **文件**：browser 组件 browser_element.py / browser_software.py 扩展，全部走既有 runJS 通道
- **原子**：
  - 存储2：get/set_storage(session|local 双模式, key/value)
  - 文本1：get_text_nodes(XPath text() 拼接)
  - 下拉1：set_dropdown_generic(非select标签: input+模拟键盘/自定义div选项点击)
  - 页面管理4：disable_html_zoom / close_other_tabs / force_close_tab / get_browser_obj_type
  - JS库2：import_js_library(url)/import_common_lib(jQuery等常用)
  - 样式4：set_font_color / set_bg_color / set_bg_image / add_border（均 inject style）
  - 元素4：show_element / hide_element / remove_element / element_long_screenshot（滚动分段截+Pillow拼接）
- **JS 注入纪律**：模板一律 `__PLACEHOLDER__` replace + json.dumps 字面量（经验库铁律）
- **挂载**：element_operation/element_visible/screenshot/set_select 等对应分组，逐条锚点见 MISSING_FEATURES P3-1
- **冒烟**：FakeBrowser runJS handler 模式（仿 paginator 测试），逐原子断言生成 JS 语法（node --check）

### M10 P3-2 IFrame跨域 ×9（ids 997-1005）⚠️ 最高风险
- **前置改造**：浏览器插件 debugger.ts evaluate 支持 frame 上下文——CDP Runtime.evaluate 无 frameId 参数，需改用 **Page.createIsolatedWorld / Runtime.evaluate in contextId** 或 **DOM.performSearch + frameId**；插件增加 getFrameTree 能力，消息协议加 frameSelector 字段
- **原子**：init_iframe(index|name|xpath 定位→frame 标识) / switch_iframe(切主文档/指定frame) + XPath 跨域7件套（get_element/click/input/get_similar_list/wait/attribute/info，全部带 frame 标识路由）
- **Browser 对象扩展**：Browser.frame 属性（当前活动 frame 上下文），element 原子发 runJS 时携带 frameSelector
- **兼容**：插件旧版本无 frame 支持→ 降级报"请更新浏览器插件"
- **步骤**：先改插件(background.debugger)+单测（插件测试基线 6 个预存失败注意区分）→ 再引擎侧 → 真浏览器手工验证跨域页面（如 typora 嵌码云）
- **冒烟**：mock websocket 通道验证消息协议与 frame 路由逻辑

### M11 P5-7 Dialog进度条 ×3（ids 1097-1099）
- **链路**：executor ws.py 仿 send_notification 增加 progress 消息（msg.name='progress', 带 progress_id/percent/description）→ web-app useRunningStore 处理并渲染进度条组件（前端新增组件 ProgressToast）
- **原子**：init_progress_bar(可迭代对象+标题/任务名→进度条对象[包装迭代器, 每次 yield 推送 ws]) / update_progress(对象+数字) / set_progress_description(对象+文本)
- **注意**：init 返回的迭代器包装对象在 atomic 输出注册为 List（兼容循环节点）；ws 断连不阻断流程（try/except 吞推送错误）
- **验证**：需前端联调（pnpm tsc + 手动跑流程看进度条渲染）

### M12 P5-8 可选增强（无新原子，按需）
- format_datetime 已含在 M1-B；其余：upsert 支持字典3格式 / MySQL 表单式四件套 / Database.connect 分字段表单+简单池 —— **默认不做**，用户点名再做

---

## 三、每批次标准交付流程（七步曲）

1. **代码**：组件内实现 + error.py 消息 + __init__ 导出
2. **config.yaml**：原子 title/comment/tip/helpManual + options 枚举 label（枚举 options 靠签名类型注解，铁律）
3. **meta.json 重生成**：`cd <组件> && uv run python /tmp/gen_meta_stub.py`（注意各组件 stub 清单差异，见经验库）
4. **冒烟**：/tmp/smoke_*.py mock 测试全通过（新原子逐个断言，含错误分支）
5. **SQL**：tools/sync_atom_sql.py 改配置生成新行+改行（ensure_ascii=False 裸中文+反斜杠双写+单引号双写）
6. **挂载**：tools/mount_atom_tree.py 改 MOUNT 映射（同 key 多分组必须分组边界+倒序插入）
7. **验证**：mysql:8.4 容器全量导入 → JSON_VALID 全过 + 中文 title 正确 + 挂载点命中；ruff format --check + py_compile

每步完成即更新 MISSING_FEATURES.md 对应条目 ✅（断点续传标记）。

---

## 四、风险登记册

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | pyzbar 系统库(zbar) 打包遗漏 | M2 识别功能装机不可用 | Windows 带 dll 进 resources；安装包脚本同步改；文档写明 |
| R2 | camelot 安装重/依赖冲突 | M4 表格线策略 | 首选 pdfplumber 全覆盖；camelot 作为可选增强，装不上自动降级 |
| R3 | imageio-ffmpeg 二进制体积(~25MB) | M5 安装包变大 | 接受；或后续做"首次用时下载" |
| R4 | 插件 CDP frame 改造伤及现有 evaluate | M10 全部浏览器原子 | 插件改动加协议版本字段，旧消息路径零改动；全量跑插件测试基线对比 |
| R5 | 手机真机差异(国产ROM权限) | M7 文件系原子 | 冒烟 mock 为准；真机问题记录进经验库，文档写排查步骤 |
| R6 | 新分类树改动破坏现有挂载 | M3/M5 全编辑器 | 只做"插入新分组"不做重排；导入后全量核对 19 分组快照（经验库第五章） |
| R7 | 进度条前端联调阻塞 | M11 | 放最后；ws 协议先定稿评审再动手 |
| R8 | SQL id 冲突/断档 | 全部 | 每批次开工前 grep 最大 id；本表 id 为预算，实际以顺序分配为准并回写 |

---

## 五、发版策略

- M1+M2 完成可发 **v1.2.0**（纯后端速赢包）
- M3+M4+M6 完成可发 **v1.3.0**（图片/PDF/PG）
- M5+M7+M8 完成可发 **v1.4.0**（视频/手机/隧道）
- M9+M10 完成可发 **v1.5.0**（Web/IFrame，含插件升级）
- M11 完成可发 **v1.6.0**（进度条，前端同版本要求）
- 每次发版四资产齐全（EXE/wps_read_sheet.js/server-snapshot/SERVER-DEPLOY.txt），tag 与 electron package.json 严格一致
- 用户未确认前不主动发版（既有约定）

---

## 六、挂起的输入

- 第七批 #13 无效链接 → 待用户提供正确 URL 后补分析（可能追加 1 原子到对应批次）
