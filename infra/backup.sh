#!/bin/sh
# Nightly database backup. Run from the repository root on the server, e.g. cron:
#   15 2 * * * cd /srv/nyumbani && ./infra/backup.sh >> /var/log/nyumbani-backup.log 2>&1
# Keeps 14 daily dumps locally. Copy them OFF the server too (e.g. rclone to a private R2 bucket):
#   BACKUP_REMOTE=r2:nyumbani-backups ./infra/backup.sh
set -eu
DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DIR"
docker compose -f docker-compose.prod.yml --env-file infra/production.env exec -T db \
  pg_dump -U postgres -d rental_marketplace --format=custom --no-owner > "$DIR/db-$STAMP.dump"
# Verification documents in local storage (only when no private R2 bucket is used).
docker compose -f docker-compose.prod.yml --env-file infra/production.env run --rm --no-deps -T backend \
  sh -c 'tar -C /app -czf - private_media' > "$DIR/private-media-$STAMP.tgz" 2>/dev/null || true
find "$DIR" -name 'db-*.dump' -mtime +14 -delete
find "$DIR" -name 'private-media-*.tgz' -mtime +14 -delete
if [ -n "${BACKUP_REMOTE:-}" ]; then rclone copy "$DIR" "$BACKUP_REMOTE" --include "*$STAMP*"; fi
echo "Backup $STAMP complete"
