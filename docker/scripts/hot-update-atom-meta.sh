#!/usr/bin/env bash
# ================================================================
# 热更新原子能力元数据表 c_atom_meta_new（生产安全）
#
# 原理：c_atom_meta_new 是纯参考数据表（由仓库
# volumes/mysql/init_c_atom_meta_new_data.sql 定义），用户数据
# （账号/机器人/流程）都在其他表。本脚本把该表在运行中的
# MySQL 里按仓库文件重建，不动数据卷、不清库、不停服务。
#
# 安全措施：执行前自动 mysqldump 全库备份，可随时回滚。
#
# 用法（部署目录的 docker 下）：
#   bash scripts/hot-update-atom-meta.sh
# ================================================================
set -euo pipefail

DOCKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DOCKER_DIR"

MYSQL_CONTAINER="${MYSQL_CONTAINER:-rpa-opensource-mysql}"
SQL_FILE="volumes/mysql/init_c_atom_meta_new_data.sql"

# --- 从 .env 读取数据库配置 ---
if [ ! -f .env ]; then
  echo "ERROR: $DOCKER_DIR/.env not found"
  exit 1
fi
DB_USER=$(grep -E '^DATABASE_USERNAME=' .env | head -1 | cut -d= -f2 | tr -d '"' | tr -d ' ')
DB_PASS=$(grep -E '^DATABASE_PASSWORD=' .env | head -1 | cut -d= -f2 | tr -d '"' | tr -d ' ')
DB_NAME=$(grep -E '^DATABASE_NAME=' .env | head -1 | cut -d= -f2 | tr -d '"' | tr -d ' ')
[ -z "$DB_USER" ] || [ -z "$DB_PASS" ] || [ -z "$DB_NAME" ] && { echo "ERROR: .env missing DATABASE_USERNAME/PASSWORD/NAME"; exit 1; }

if [ "$DB_NAME" != "rpa" ]; then
  echo "WARN: DATABASE_NAME=$DB_NAME, but init SQL hardcodes schema 'rpa' (TRUNCATE rpa.c_atom_meta_new)"
fi

echo "container=$MYSQL_CONTAINER  user=$DB_USER  db=$DB_NAME"

# --- 1/3 全库备份 ---
BACKUP_DIR="volumes/backup"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"
echo "[1/3] Backing up '$DB_NAME' -> $BACKUP_FILE"
docker exec -e MYSQL_PWD="$DB_PASS" "$MYSQL_CONTAINER" \
  mysqldump -u"$DB_USER" --databases "$DB_NAME" | gzip > "$BACKUP_FILE"
echo "      size: $(du -h "$BACKUP_FILE" | cut -f1)"

# --- 2/3 重建元数据表 ---
echo "[2/3] Re-seeding c_atom_meta_new from $SQL_FILE"
docker exec -i -e MYSQL_PWD="$DB_PASS" "$MYSQL_CONTAINER" \
  mysql -u"$DB_USER" "$DB_NAME" < "$SQL_FILE"

# --- 3/3 验证 ---
echo "[3/3] Verifying"
docker exec -e MYSQL_PWD="$DB_PASS" "$MYSQL_CONTAINER" \
  mysql -u"$DB_USER" "$DB_NAME" -N -e "
SELECT CONCAT('  total atom rows:  ', COUNT(*)) FROM c_atom_meta_new;
SELECT CONCAT('  WPS atom rows:    ', COUNT(*)) FROM c_atom_meta_new WHERE atom_key LIKE 'WPS.%';"

echo
echo "DONE. Refresh the web editor (Ctrl+F5) to see changes."
echo "Rollback (if ever needed):"
echo "  gunzip -c $BACKUP_FILE | docker exec -i -e MYSQL_PWD=\"\$DB_PASS\" $MYSQL_CONTAINER mysql -u\"\$DB_USER\""
