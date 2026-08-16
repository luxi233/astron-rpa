---
name: "astron-rpa-release"
description: "AstronRPA 发布流程编排与版本一致性检查。用户要求发布、打tag、创建Release时调用；每次发版前/后进行QA、构建、发布、回滚指导。"
---

# AstronRPA Release Skill

本 skill 固化 Astron RPA 项目（仓库 `astron-rpa`）的发布流程、三道质量闸门、三条发布路径、服务端回滚操作，以及相关工作流文件的位置。

**Trigger Conditions（何时调用本 skill）：**
- 用户明确说「发布」「发版」「打 tag」「创建 Release」「发布 vX.Y.Z」
- 对话中出现版本号（如 `1.1.8-2`、`v1.1.9`），且意图是构建/发布
- 用户需要检查 tag 是否规范、package.json 是否与 tag 一致
- 用户需要回滚到上一个版本、或询问 release 后服务器如何升级

---

## 1. 工作流清单（5 个，均在 `.github/workflows/`）

| 文件名 | 触发方式 | 核心作用 |
|---|---|---|
| `tag-guardian.yml` | tag 推送 `v*` + 手动 | 推送 tag 时立即校验：格式 / 与 package.json 一致性 / 关键文件存在 |
| `build-windows-client.yml` | 手动 | 单独构建 Windows EXE（拆分发布用），产出 artifact `AstronRPA-windows-exe` |
| `release-full-pipeline.yml` | 手动（推荐） | **一键发布**：QA Gate → Build Client → Publish Release 三阶段串联 |
| `publish-release.yml` | 手动 / reusable workflow_call | 创建 GitHub Release，打包 EXE + WPS 脚本 + server-snapshot + SERVER-DEPLOY.txt 四类资产 |
| `build-push-backend.yml` | `release:published` 事件 + 手动 | 构建并推送 5 个后端 Docker 镜像至 ghcr.io（:tag + :latest） |

---

## 2. 三道质量闸门（Release Safety Gates）

### Gate 1：Tag Guardian
每次 `git push origin vX.Y.Z[-xxx]` 后自动运行（`tag-guardian.yml`）。

**检查项：**
1. **格式**：必须匹配 `^v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$`
   - ✅ 正确：`v1.1.8-2`、`v1.1.8`、`v2.0.0-rc1`
   - ❌ 错误：`1.1.8`（缺 v）、`v1.1.8.2`（4 段）、`v1.1.8-1-fix3`（多段预发布）
2. **版本一致**：去前缀后必须 `== frontend/packages/electron-app/package.json#version`
3. **关键源文件**：`engine/components/astronverse-kdocs/scripts/wps_read_sheet.js`、`docker/docker-compose.yml` 在该 tag 的 commit 上存在

**修复错误 tag 的标准指令（工作流失败时原样执行）：**
```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
# 修正 package.json 或 tag 后重新打
git tag vX.Y.Z <correct-commit>
git push origin vX.Y.Z
```

### Gate 2：QA Gate（内嵌在 release-full-pipeline 的第一阶段）
- Python：ruff format 检查 + Python 3.13 全量 `py_compile` engine 目录
- TypeScript：`frontend/packages/browser-plugin` 执行 `tsc --noEmit`
- 紧急发布可勾 `skip_qa=true`

### Gate 3：Asset Gate（publish-release 和 release-full-pipeline 的 publish 阶段）
四类资产必须同时存在，否则不执行 `gh release create`：
- 🪟 `*.exe`（Windows 安装包）
- 📄 `wps_read_sheet.js`（WPS AirScript）
- 📦 `server-snapshot-<tag>.tar.gz`（git archive，排除 `resources/`）
- 📋 `SERVER-DEPLOY.txt`（部署/升级/回滚指南，自动附带 tag / commit / run ID）

---

## 3. 标准发布 SOP（Astron RPA 推荐流程）

以版本 `1.1.8-2` 为例（semver 预发布格式：`MAJOR.MINOR.PATCH-<序号>`，对应 tag `v1.1.8-2`）。

### Step 1：改版本号 + 提交
```bash
cd /path/to/astron-rpa
# 编辑 electron-app package.json 的 version
# 从旧版本 → 1.1.8-2
#   frontend/packages/electron-app/package.json
git add frontend/packages/electron-app/package.json
git commit -m "chore: bump version to 1.1.8-2"
git push origin main
```

### Step 2：打 tag + 推送 → Tag Guardian 自动校验
```bash
git tag v1.1.8-2
git push origin v1.1.8-2
```
等待 30 秒：**GitHub → Actions → Tag Guardian**，看到绿色 ✅ 才继续。
若变红：按失败日志的「修复建议」改 tag 或改 package.json 后重做 Step 1+2。

### Step 3：一键发布（推荐路径 A）
浏览器访问：
```
https://github.com/<org>/astron-rpa/actions/workflows/release-full-pipeline.yml
```
点击 **Run workflow**，填写：
- **tag**：`v1.1.8-2`（必填；已推送到 origin）
- **title**：留空 → 自动生成 `Astron RPA v1.1.8-2`
- **prerelease**：`auto`（含 `-` 自动判定预发布，无 `-` 为正式版）
- **notes**：留空 → 基于上一个 tag 的提交区间自动生成
- **skip_qa** / **skip_engine** / **skip_frontend** / **skip_version_check**：默认 false（紧急时再勾）

Run 后观察三阶段：
```
🧪 qa-gate (~3min) → 🪟 build-client (~40–80min) → 🚀 publish-release (~3min)
```

### Step 4：自动后续
Release 创建事件 `release:published` 会自动触发 `build-push-backend.yml`：
- 构建 5 个后端镜像：ai-service / openapi-service / resource-service / robot-service / rpa-auth
- 同时打两个 tag：`ghcr.io/<org>/<svc>:v1.1.8-2` 和 `ghcr.io/<org>/<svc>:latest`

### Step 5：手动润色 Release Notes（可选）
进入 Release 页面，Auto-generated notes 已附提交列表，可加产品文案、截图等。

---

## 4. 三条发布路径对比

| 路径 | 入口 | 适用场景 | 操作复杂度 |
|---|---|---|---|
| **A. Release Full Pipeline** ✨推荐 | Actions → Release Full Pipeline | 规范的正式/预发布；最省心 | 1 次触发，全自动 |
| **B. Build → Publish 拆分** | Build Windows Client → Publish Release | 需要先对 EXE 手动 QA，或前后端/构建分工 | 2 次触发，传 run_id |
| **C. 紧急发布（Bypass gates）** | 同上 + 勾选 `skip_qa` / `skip_version_check` | Hotfix 且已本地验过 | 同 A/B，但跳过 gate |

### 路径 B 拆分发布的操作细节
1. Actions → **Build Windows Client** → Run（如需调试可勾 `skip_engine` 或 `skip_frontend`）
2. 构建结束后复制 **Run ID**（例：`1234567890`）
3. Actions → **Publish Release** → Run：
   - `run_id` = 上一步的 Run ID
   - `tag` = `v1.1.8-2`
   - 其余同 A 路径默认

---

## 5. 发布产出物（4 类资产 + 5 个镜像）

### Release 页面能下载的 4 个资产
1. **`AstronRPA Setup <ver>.exe`**：Windows 客户端安装包
2. **`wps_read_sheet.js`**：WPS AirScript（用户在 KDocs 在线表格里挂载用）
3. **`server-snapshot-<tag>.tar.gz`**：
   - `git archive` 打包的完整源码快照（不含 `.git`，排除 `resources/` 客户端素材）
   - 运维部署时解压，补上 `docker/.env` 就能 `docker compose up -d`
4. **`SERVER-DEPLOY.txt`**：每次 Release 自动生成的部署说明，内含 tag/commit/run ID 审计信息

### 自动构建并推送的 5 个 Docker 镜像
```
ghcr.io/<org>/ai-service:<tag>     :latest
ghcr.io/<org>/openapi-service:<tag>:latest
ghcr.io/<org>/resource-service:<tag>:latest
ghcr.io/<org>/robot-service:<tag>:latest
ghcr.io/<org>/rpa-auth:<tag>:latest
```

---

## 6. 服务端 Fresh Deploy / Upgrade / Rollback

Release 附带的 `SERVER-DEPLOY.txt` 已经内嵌以下说明，这里保留一份给 agent 执行时参考。

### 6.1 Fresh Deploy（全新部署）
```bash
# 1. 解压 snapshot
tar -xzf server-snapshot-<tag>.tar.gz -C /opt/astron-rpa
cd /opt/astron-rpa

# 2. 初始化配置（第一次部署）
cp docker/.env.example docker/.env
# 编辑 docker/.env，填入 MySQL/Redis/Casdoor/MinIO 等 secret

# 3. 启动
cd docker && docker compose up -d

# 4. 验证
#   浏览器访问前端 80/443，后端健康检查端口（openapi-service /healthcheck）
```

### 6.2 Upgrade Deploy（常规升级）
```bash
# 1. 覆盖新 snapshot（保留 .env、data、logs、backup）
tar -xzf server-snapshot-<new-tag>.tar.gz -C /opt/astron-rpa
# docker/.env 保持原样不动；docker/volumes/** 下数据也不动

# 2. 热更新原子元数据（必跑；升级前端原子能力都靠它）
cd /opt/astron-rpa/docker
bash scripts/hot-update-atom-meta.sh

# 3. 如果后端代码变更则重启
docker compose restart
```

### 6.3 Rollback（回滚到任意历史 tag）
```bash
# 1. 从目标 Release 页下载回滚版本的 server-snapshot-<old-tag>.tar.gz
# 2. 解压覆盖（保留 .env / data / logs / docker/volumes/backup）
tar -xzf server-snapshot-<old-tag>.tar.gz -C /opt/astron-rpa

# 3. 同样热更新元数据
cd /opt/astron-rpa/docker
bash scripts/hot-update-atom-meta.sh

# 4. 如原子元数据仍异常 → 恢复 MySQL 自动备份
BACKUP=$(ls -t docker/volumes/backup/*.sql.gz | head -n1)
echo "Using backup: $BACKUP"
gunzip -c "$BACKUP" | docker exec -i rpa-opensource-mysql \
  mysql -u<MYSQL_USER> -p<MYSQL_PASSWORD> rpa

# 5. 回滚 Docker 镜像（可选）
#   每个服务的 :<old-tag> 镜像仍在 ghcr.io，编辑 docker-compose 指定 tag 或
#   docker compose pull + docker compose up -d
```

---

## 7. 版本号约定（SemVer 预发布格式）

AstronRPA 采用如下版本格式（**禁止再用 4 段点式**如 `1.1.8.2`）：

| 场景 | 格式 | 例子 | 是否预发布 |
|---|---|---|---|
| 正式发布版 | `vMAJOR.MINOR.PATCH` | `v1.1.8` | 否（pre-release=false） |
| Patch 构建 / 热更新 | `vMAJOR.MINOR.PATCH-<序号>` | `v1.1.8-2` | 是（pre-release=true） |
| 发布候选 RC | `vMAJOR.MINOR.PATCH-rc<N>` | `v2.0.0-rc1` | 是 |
| Beta | `vMAJOR.MINOR.PATCH-beta<N>` | `v2.0.0-beta.3` | 是 |

**判断逻辑（自动化层已实现）：** 只要 tag 包含 `-` → 预发布；否则 → 正式。

---

## 8. 常见事故 & 修复速查

### 事故 1：打了错误格式 tag 并推送到远程（如 `v1.1.8.2`）
```bash
git tag -d v1.1.8.2
git push origin :refs/tags/v1.1.8.2
git tag v1.1.8-2 <正确的 commit sha>
git push origin v1.1.8-2
# 随后 Tag Guardian 自动重跑；✅ 后再发布
```

### 事故 2：tag 版本 ≠ package.json 版本（发布流程的 Version Gate 报错）
**二选一修复：**
- **A（tag 打错）**：删 tag → 按 package.json 的真实版本重新打 tag（`v${pkg_ver}`）
- **B（package.json 没改）**：修改 package.json → commit → push → 删旧 tag → 对新 commit 重打 tag → 推送 tag

### 事故 3：发布后发现 EXE 有 bug，想撤销 GitHub Release
1. Release 页 → Edit → **Delete release**（只删 release，不删 tag）
2. 修复代码 + bump package.json 版本（例如 `1.1.8-2` → `1.1.8-3`）
3. commit → push → 打 `v1.1.8-3` → 走发布流程
4. （可选）清掉旧 tag：`git tag -d v1.1.8-2 && git push origin :refs/tags/v1.1.8-2`

### 事故 4：Tag Guardian 绿了，但 release-full-pipeline 报 asset missing
通常是「tag 推的分支里有文件，但实际发布时 checkout 出的 commit 没有」。用：
```bash
git ls-tree v1.1.8-2 engine/components/astronverse-kdocs/scripts/wps_read_sheet.js
# 如果不存在：把 tag 移到正确的 commit
```

---

## 9. Agent 执行 Checklist（每次按此顺序工作）

当用户说「发布」时，按以下 123 顺序执行：

1. **确认版本号**：
   - 询问用户要发布的版本（例：`1.1.8-2`），如果用户没说，读 `frontend/packages/electron-app/package.json#version` 推断并确认
   - 把版本转成 tag 格式：加 `v` 前缀 → `v1.1.8-2`
   - 校验 tag 是否符合 semver 正则（见 Gate 1），不符合直接报错提醒改
2. **版本一致性预检**：
   - 如果用户已经打了 tag：检查 `package.json` 的 version 与去前缀的 tag 是否一致，不一致先让用户选 A / B 修复
3. **引导到工作流**：
   - 优先推荐路径 A（Release Full Pipeline），给出入口 URL + 参数建议
   - 若用户明确要拆分 → 路径 B
   - 若用户要紧急 hotfix → 提醒可勾选哪些 skip，并告知 skip 的风险
4. **发布后**：
   - 提醒用户 build-push-backend.yml 会自动跑（5 镜像）
   - 如果还需部署到服务器：按 §6.2 Upgrade Deploy 执行；需要回滚：§6.3
5. **生成 Release Notes 摘要**（可选）：当用户嫌自动 notes 太糙时，帮忙整理分模块（功能/Bug/兼容性）文案

---

## 10. 版本号变更代码定位

发布前需要改的唯一版本号文件：

- **客户端（EXE 版本 + Release 版本基准）**：[frontend/packages/electron-app/package.json](file:///Users/infinitelab/Desktop/astron-rpa/frontend/packages/electron-app/package.json)
  - 修改 `"version": "X.Y.Z[-N]"` 后 commit + push，然后才打 tag

其它模块（Python 后端、Java 后端、browser-plugin）暂不在 Release 产物里显式打版本号，都靠外层 git tag 对齐。

---

## 11. 工作流文件快速索引

- [tag-guardian.yml](file:///Users/infinitelab/Desktop/astron-rpa/.github/workflows/tag-guardian.yml)
- [release-full-pipeline.yml](file:///Users/infinitelab/Desktop/astron-rpa/.github/workflows/release-full-pipeline.yml)
- [publish-release.yml](file:///Users/infinitelab/Desktop/astron-rpa/.github/workflows/publish-release.yml)
- [build-windows-client.yml](file:///Users/infinitelab/Desktop/astron-rpa/.github/workflows/build-windows-client.yml)
- [build-push-backend.yml](file:///Users/infinitelab/Desktop/astron-rpa/.github/workflows/build-push-backend.yml)
