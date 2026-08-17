# -*- coding: utf-8 -*-
"""原子表 SQL 同步工具（模板，每批次复制修改 NEW_ROWS / UPDATE_ROWS / COMPONENTS / EXPECTED_LAST_ID）

用法（每批次）:
1. 组件重新生成 meta.json 后，改本文件顶部 COMPONENTS / NEW_ROWS(新原子 id->(组件,key)) / UPDATE_ROWS(改行 id->(组件,key)) / EXPECTED_LAST_ID
2. python3 tools/sync_atom_sql.py  （新行追加到 SQL 末尾，改行整行替换保留 sort/create_time）
3. 再跑 tools/mount_atom_tree.py 挂载树
4. MySQL 容器全量验证（schema.sql 先建库表再导 data.sql，JSON_VALID 全过 + 树挂载 JSON_SEARCH 命中）

转义规范(默认 sql_mode): ensure_ascii=False 裸中文 + 反斜杠双写 + 单引号双写。
历史版本: P0=/tmp/sync_p0_sql.py P1=本模板 P2=/tmp/sync_p2_sql.py（/tmp 易失，以本文件为准）。
"""
import json
import re
from datetime import datetime

SQL_PATH = "/Users/infinitelab/Desktop/astron-rpa/docker/volumes/mysql/init_c_atom_meta_new_data.sql"
COMP = "/Users/infinitelab/Desktop/astron-rpa/engine/components"
COMPONENTS = {
    "browser": f"{COMP}/astronverse-browser/meta.json",
    "database": f"{COMP}/astronverse-database/meta.json",
    "dataprocess": f"{COMP}/astronverse-dataprocess/meta.json",
    "dialog": f"{COMP}/astronverse-dialog/meta.json",
    "encrypt": f"{COMP}/astronverse-encrypt/meta.json",
    "image": f"{COMP}/astronverse-image/meta.json",
    "network": f"{COMP}/astronverse-network/meta.json",
    "pdf": f"{COMP}/astronverse-pdf/meta.json",
    "phone": f"{COMP}/astronverse-phone/meta.json",
    "system": f"{COMP}/astronverse-system/meta.json",
    "video": f"{COMP}/astronverse-video/meta.json",
}
metas = {name: json.load(open(p, encoding="utf-8")) for name, p in COMPONENTS.items()}

# id -> (组件, atom_key)  M11 P5-7 进度条×3（ids 1097-1099，dialog 组件）
NEW_ROWS = {
    1097: ("dialog", "Dialog.init_progress_bar"),
    1098: ("dialog", "Dialog.update_progress"),
    1099: ("dialog", "Dialog.set_progress_description"),
}

# 本批次无改行
UPDATE_ROWS = {}

missing = []
for id_, (comp, key) in {**NEW_ROWS, **UPDATE_ROWS}.items():
    if key not in metas[comp]:
        missing.append((id_, comp, key))
if missing:
    raise SystemExit(f"meta.json 缺少 key: {missing}")


def sql_escape_json(obj) -> str:
    text = json.dumps(obj, ensure_ascii=False)
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "''")
    return text


def make_line(id_, key, content_escaped, sort, create, update):
    return (
        "INSERT INTO `c_atom_meta_new` (`id`,`atom_key`,`atom_content`,`sort`,`create_time`,`update_time`)  "
        f"VALUES ('{id_}','{key}','{content_escaped}',{sort},'{create}','{update}');\n"
    )


now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
lines = open(SQL_PATH, encoding="utf-8").readlines()

# ---- 1. 改行(整行替换, 保留 sort/create_time) ----
update_pat = re.compile(
    r"^(INSERT INTO `c_atom_meta_new`[^V]*VALUES )\('(\d+)','([^']*)','(.*)',(NULL|'[^']*'),'([^']*)','([^']*)'\);\s*$"
)
updated = {}
for i, line in enumerate(lines):
    m = update_pat.match(line)
    if not m:
        continue
    rid = int(m.group(2))
    if rid in UPDATE_ROWS:
        comp, key = UPDATE_ROWS[rid]
        assert m.group(3) == key, f"id {rid} key 不匹配: {m.group(3)} != {key}"
        content = sql_escape_json(metas[comp][key])
        lines[i] = make_line(rid, key, content, m.group(5), m.group(6), now)
        updated[rid] = True
missing_upd = set(UPDATE_ROWS) - set(updated)
if missing_upd:
    raise SystemExit(f"改行未找到: {missing_upd}")

# ---- 2. 新行按 id 定位插入(不要求追加末尾, M3 id 1014-1034 < 已有末尾 1073) ----
existing_ids = set()
id_line_idx = []  # (id, 行号)
for i, line in enumerate(lines):
    m = update_pat.match(line)
    if m:
        existing_ids.add(int(m.group(2)))
        id_line_idx.append((int(m.group(2)), i))
clash = existing_ids & set(NEW_ROWS)
if clash:
    raise SystemExit(f"id 已存在: {sorted(clash)}")

if not lines[-1].endswith("\n"):
    lines[-1] += "\n"

inserted = 0
for id_ in sorted(NEW_ROWS):
    comp, key = NEW_ROWS[id_]
    content = sql_escape_json(metas[comp][key])
    new_line = make_line(id_, key, content, "NULL", now, now)
    # 找第一个大于 id_ 的行号，插到它前面
    pos = None
    for eid, i in id_line_idx:
        if eid > id_:
            pos = i
            break
    if pos is None:
        lines.append(new_line)
        id_line_idx.append((id_, len(lines) - 1))
    else:
        lines.insert(pos, new_line)
        id_line_idx = [(eid, (i + 1 if i >= pos else i)) for eid, i in id_line_idx]
        id_line_idx.append((id_, pos))
        id_line_idx.sort()
    inserted += 1

open(SQL_PATH, "w", encoding="utf-8").writelines(lines)
print(f"OK: {len(updated)} 行更新, {inserted} 行新增, 总行数 {len(lines)}")
