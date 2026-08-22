# -*- coding: utf-8 -*-
"""atomicTree 挂载工具（模板，每批次复制修改 MOUNTS / GROUP_TITLES）

用法（每批次）:
1. 改 MOUNTS = [(分组key, 锚点原子key, [(组件, 新原子key)...]), ...]；GROUP_TITLES 补齐目标分组 title
2. python3 tools/mount_atom_tree.py  （分组内锚点条目后插入，倒序下标防偏移）
3. 验证: MySQL 导入后 JSON_SEARCH 命中各新原子 key

关键点: 同一原子 key 可在树中多分组出现（如 BrowserElement.loop_similar 在 code/for + web 两组）
→ 必须先定位分组 atomics 数组边界(括号深度扫描) → 分片内找锚点 → 倒序插入；禁止全文 find 第一个命中。
分组结构全图见 LESSONS_LEARNED.md「五、原子表挂载」章节。
"""
import json

SQL_PATH = "/Users/infinitelab/Desktop/astron-rpa/docker/volumes/mysql/init_c_atom_meta_new_data.sql"
COMP = "/Users/infinitelab/Desktop/astron-rpa/engine/components"
METAS = {
    "browser": json.load(open(f"{COMP}/astronverse-browser/meta.json", encoding="utf-8")),
    "database": json.load(open(f"{COMP}/astronverse-database/meta.json", encoding="utf-8")),
    "dataprocess": json.load(open(f"{COMP}/astronverse-dataprocess/meta.json", encoding="utf-8")),
    "datatable": json.load(open(f"{COMP}/astronverse-datatable/meta.json", encoding="utf-8")),
    "dialog": json.load(open(f"{COMP}/astronverse-dialog/meta.json", encoding="utf-8")),
    "encrypt": json.load(open(f"{COMP}/astronverse-encrypt/meta.json", encoding="utf-8")),
    "image": json.load(open(f"{COMP}/astronverse-image/meta.json", encoding="utf-8")),
    "network": json.load(open(f"{COMP}/astronverse-network/meta.json", encoding="utf-8")),
    "pdf": json.load(open(f"{COMP}/astronverse-pdf/meta.json", encoding="utf-8")),
    "phone": json.load(open(f"{COMP}/astronverse-phone/meta.json", encoding="utf-8")),
    "system": json.load(open(f"{COMP}/astronverse-system/meta.json", encoding="utf-8")),
    "video": json.load(open(f"{COMP}/astronverse-video/meta.json", encoding="utf-8")),
}

# (分组key, 锚点原子key, [(组件, 新原子key)])
# M12: 数据表格删除空行/列 → datatable 分组 remove_duplicate_rows 后插入(字母序: remove_d < remove_e < rename)
MOUNTS = [
    (
        "datatable",
        "DataTable.remove_duplicate_rows",
        [
            ("datatable", "DataTable.remove_empty_rows_cols"),
        ],
    ),
]

# M11: 无新建顶级分组
NEW_GROUPS = []

# M11: 无新建子分组
SUBGROUPS = []

GROUP_TITLES = {
    "web": "网页自动化",
    "web.cookie": "Cookie",
    "web.page": "网页操作",
    "web.iframe": "IFrame跨域",
    "dialog": "对话框",
    "os.printer": "打印机",
    "os.system": "系统命令",
    "phone": "手机自动化",
    "document.PDF": "PDF",
    "video": "视频处理",
    "database": "数据库",
    "ftp": "FTP",
    "datatable": "数据表格",
}


def entry_text(comp, key):
    m = METAS[comp][key]
    title = m["title"]
    icon = m.get("icon") or "atom-default"
    return json.dumps({"key": key, "title": title, "icon": icon}, ensure_ascii=False, separators=(", ", ": "))


lines = open(SQL_PATH, encoding="utf-8").readlines()
line = lines[6]
assert "'19','atomCommon'" in line, "line 7 is not atomCommon"


def find_group_close(s, open_bracket_idx):
    """从 atomics 数组的 '[' 之后扫描, 返回该数组闭合 ']' 的下标"""
    depth = 1
    i = open_bracket_idx
    while i < len(s):
        c = s[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced")


def group_bounds(s, group_key):
    anchor = '{{"key": "{}", "title": "{}", "atomics": ['.format(group_key, GROUP_TITLES[group_key])
    idx = s.find(anchor)
    assert idx != -1, f"group not found: {group_key}"
    open_idx = idx + len(anchor) - 1
    close_idx = find_group_close(s, open_idx + 1)
    return open_idx + 1, close_idx


# 从后往前挂载(避免下标偏移): 先按分组出现顺序倒序处理同组内锚点也倒序
# 分组在行内的顺序: web < desktop < database; 组内锚点位置各异
# 策略: 收集全部插入点(绝对下标, 插入文本), 按下标降序执行
inserts = []
for group_key, anchor_key, items in MOUNTS:
    g_open, g_close = group_bounds(line, group_key)
    slice_ = line[g_open:g_close]
    a_idx = slice_.find('{{"key": "{}"'.format(anchor_key))
    assert a_idx != -1, f"anchor {anchor_key} not in group {group_key}"
    # 锚点条目结束: 从 a_idx 找下一个 '}' (条目内无嵌套)
    a_end = slice_.find("}", a_idx)
    assert a_end != -1
    abs_end = g_open + a_end + 1
    additions = ", ".join(entry_text(c, k) for c, k in items)
    inserts.append((abs_end, additions))

for pos, text in sorted(inserts, key=lambda x: -x[0]):
    line = line[:pos] + ", " + text + line[pos:]

# ---- 父组 atomics 末尾新建子分组 ----
for g in SUBGROUPS:
    assert line.count(f'{{"key": "{g["key"]}", "title": "{g["title"]}"') == 0, f"子分组已存在: {g['key']}"
    g_open, g_close = group_bounds(line, g["parent"])
    entries = ", ".join(entry_text(c, k) for c, k in g["items"])
    group_text = '{{"key": "{}", "title": "{}", "atomics": [{}]}}'.format(g["key"], g["title"], entries)
    # 插到父组 atomics 闭合 ']' 之前（最后一个元素之后）
    line = line[:g_close] + ", " + group_text + line[g_close:]

# ---- 新建顶级分组: 插到 before 分组对象之前 ----
for g in NEW_GROUPS:
    assert line.count(f'{{"key": "{g["key"]}", "title": "{g["title"]}"') == 0, f"分组已存在: {g['key']}"
    before = g["before"]
    anchor = '{{"key": "{}", "title": "{}", "atomics": ['.format(before, GROUP_TITLES[before])
    idx = line.find(anchor)
    assert idx != -1, f"before 分组未找到: {before}"
    entries = ", ".join(entry_text(c, k) for c, k in g["items"])
    group_text = '{{"key": "{}", "title": "{}", "atomics": [{}]}}'.format(g["key"], g["title"], entries)
    line = line[:idx] + group_text + ", " + line[idx:]

lines[6] = line
open(SQL_PATH, "w", encoding="utf-8").writelines(lines)
print(f"OK: MOUNTS {len(inserts)} 处追加, NEW_GROUPS {len(NEW_GROUPS)} 组新建, SUBGROUPS {len(SUBGROUPS)} 子组新建")
