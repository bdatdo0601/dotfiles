#!/bin/bash
# dev-disk-cleanup.sh — reclaim disk from containers and inactive git worktrees.
#
#   dev-disk-cleanup.sh            dry run: show what would be removed
#   dev-disk-cleanup.sh --apply    do the cleanup (foreground)
#   dev-disk-cleanup.sh --auto     SessionStart hook mode: returns immediately; when the last
#                                  run is older than DEV_CLEANUP_COOLDOWN_HOURS (and, if
#                                  DEV_CLEANUP_MIN_FREE_GB > 0, free disk is below it), runs
#                                  --apply detached in the background.
#
# What --apply removes:
#   Docker/OrbStack   stopped containers (kind nodes kept), unused images, unused volumes,
#                     build cache (default builder + every buildx builder)
#   Apple Container   stopped containers, stopped builder, unused images, unused volumes
#   Git worktrees     clean worktrees with no process inside, untouched for
#                     DEV_CLEANUP_MIN_AGE_HOURS. Uses `git worktree remove` without
#                     --force, so git itself refuses any worktree with changes.
#                     Branches are kept; re-create with `git worktree add <path> <branch>`.
#
# Never touched: running containers and their volumes, worktrees with uncommitted or
# untracked changes, locked worktrees, detached worktrees whose HEAD is on no branch.
#
# Env overrides:
#   DEV_CLEANUP_REPOS            space-separated repo paths (default ~/workspace/iron-fillet)
#   DEV_CLEANUP_MIN_FREE_GB      --auto: only run below this many GB free (default 0 = always)
#   DEV_CLEANUP_COOLDOWN_HOURS   --auto minimum interval between runs (default 6)
#   DEV_CLEANUP_MIN_AGE_HOURS    worktree inactivity threshold (default 24)
#   DEV_CLEANUP_SKIP             space-separated subset of: docker container worktrees

set -u

REPOS=${DEV_CLEANUP_REPOS:-$HOME/workspace/iron-fillet}
MIN_FREE_GB=${DEV_CLEANUP_MIN_FREE_GB:-0}   # 0 = always clean, regardless of free space
COOLDOWN_HOURS=${DEV_CLEANUP_COOLDOWN_HOURS:-6}
MIN_AGE_HOURS=${DEV_CLEANUP_MIN_AGE_HOURS:-24}
SKIP=${DEV_CLEANUP_SKIP:-}
STATE_DIR=$HOME/.claude/state/dev-disk-cleanup
LOG=$STATE_DIR/cleanup.log
LOCK=$STATE_DIR/lock
STAMP=$STATE_DIR/last-run
SELF=$0

mkdir -p "$STATE_DIR"

free_gb() { df -g /System/Volumes/Data 2>/dev/null | awk 'NR==2{print $4}'; }
log() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }
skipped() { case " $SKIP " in *" $1 "*) return 0 ;; esac; return 1; }

# Internal: remove one worktree (used by the parallel xargs fan-out).
if [ "${1:-}" = "--_remove-one" ]; then
  git -C "$2" worktree remove "$3" 2>/dev/null && echo "removed $3" || echo "FAILED  $3"
  exit 0
fi

MODE=dry
case "${1:-}" in
  --apply) MODE=apply ;;
  --auto) MODE=auto ;;
  ""|--dry-run) MODE=dry ;;
  -h|--help) sed -n '2,32p' "$SELF"; exit 0 ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac

if [ "$MODE" = auto ]; then
  free=$(free_gb)
  if [ "$MIN_FREE_GB" -gt 0 ]; then
    [ -n "$free" ] || exit 0
    [ "$free" -lt "$MIN_FREE_GB" ] || exit 0
  fi
  if [ -f "$STAMP" ]; then
    age=$(( $(date +%s) - $(stat -f %m "$STAMP") ))
    [ "$age" -ge $(( COOLDOWN_HOURS * 3600 )) ] || exit 0
  fi
  if [ -d "$LOCK" ] && kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then exit 0; fi
  touch "$STAMP"   # claim the cooldown before backgrounding, so parallel session starts don't all fire
  nohup "$SELF" --apply >>"$LOG" 2>&1 </dev/null &
  printf '{"systemMessage":"Started background cleanup of containers and inactive worktrees (%s GB free). Log: %s"}\n' \
    "$free" "$LOG"
  exit 0
fi

if [ "$MODE" = apply ]; then
  if ! mkdir "$LOCK" 2>/dev/null; then
    if kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then
      log "another cleanup is running (pid $(cat "$LOCK/pid")); exiting"; exit 0
    fi
    rm -rf "$LOCK"; mkdir "$LOCK"
  fi
  echo $$ >"$LOCK/pid"
  trap 'rm -rf "$LOCK"' EXIT
  touch "$STAMP"
fi

run() { if [ "$MODE" = apply ]; then "$@"; else echo "  would run: $*"; fi; }

log "=== dev-disk-cleanup ($MODE) — free: $(free_gb) GB"

# ---------- Docker / OrbStack ----------
if ! skipped docker && command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  log "--- docker"
  docker system df 2>/dev/null
  # Keep kind node containers even when stopped, so local clusters survive.
  run docker container prune -f --filter 'label!=io.x-k8s.kind.cluster'
  run docker image prune -af
  run docker volume prune -af
  run docker builder prune -af
  # Only running builders: pruning a stopped docker-container builder boots it first.
  for b in $(docker buildx ls --format '{{.Name}}' 2>/dev/null | sed 's/\*$//' | sort -u); do
    docker buildx inspect "$b" 2>/dev/null | grep -q 'Status: *running' || continue
    run docker buildx prune -af --builder "$b"
  done
  [ "$MODE" = apply ] && docker system df 2>/dev/null
else
  log "--- docker: skipped (disabled or daemon not running)"
fi

# ---------- Apple Container ----------
if ! skipped container && command -v container >/dev/null; then
  log "--- apple container"
  started=0
  if ! container ls -a >/dev/null 2>&1; then
    if [ "$MODE" = apply ]; then
      container system start >/dev/null 2>&1 && started=1
    else
      echo "  service not running (would start it, clean, then stop it)"
    fi
  fi
  if container ls -a >/dev/null 2>&1; then
    stopped=$(container ls -a 2>/dev/null | awk 'NR>1 && $5=="stopped" && $1!="buildkit"{print $1}')
    [ -n "$stopped" ] && run container rm $stopped
    if container builder status 2>/dev/null | awk 'NR>1{print $4}' | grep -qx stopped; then
      run container builder delete --force
    fi
    run container image prune --all
    run container volume prune
  fi
  [ "$started" = 1 ] && container system stop >/dev/null 2>&1
else
  log "--- apple container: skipped"
fi

# ---------- Git worktrees ----------
if ! skipped worktrees; then
  cwds=$(lsof -a -d cwd 2>/dev/null | awk 'NR>1{print $NF}' | sort -u)
  now=$(date +%s)
  for repo in $REPOS; do
    [ -d "$repo" ] || continue
    log "--- worktrees: $repo"
    main=$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's#/\.git$##')
    remove_list=$(mktemp)
    kept=0
    # porcelain: "worktree <path>" / "branch <ref>" | "detached" / "locked" ...
    git -C "$repo" worktree list --porcelain | awk '
      /^worktree /{w=substr($0,10); b=""; l=0}
      /^branch /{b=substr($0,8)}
      /^detached/{b="(detached)"}
      /^locked/{l=1}
      /^$/{if(w!="")print w "\t" b "\t" l; w=""}
      END{if(w!="")print w "\t" b "\t" l}' |
    while IFS="$(printf '\t')" read -r w b locked; do
      [ "$w" = "$main" ] && continue
      [ -d "$w" ] || continue
      reason=""
      [ "$locked" = 1 ] && reason="locked"
      if [ -z "$reason" ] && printf '%s\n' "$cwds" | grep -q -e "^$w\$" -e "^$w/"; then reason="process running"; fi
      if [ -z "$reason" ]; then
        gd=$(git -C "$w" rev-parse --git-dir 2>/dev/null)
        last=$(git -C "$w" log -1 --format=%ct HEAD 2>/dev/null || echo 0)
        rl=$(stat -f %m "$gd/logs/HEAD" 2>/dev/null || echo 0)
        m=$(( last > rl ? last : rl )); hrs=$(( (now - m) / 3600 ))
        [ "$hrs" -lt "$MIN_AGE_HOURS" ] && reason="active ${hrs}h ago"
      fi
      if [ -z "$reason" ]; then
        n=$(git -C "$w" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
        [ "$n" != 0 ] && reason="uncommitted changes ($n)"
      fi
      if [ -z "$reason" ] && [ "$b" = "(detached)" ]; then
        git -C "$w" branch -a --contains HEAD 2>/dev/null | grep -q . || reason="detached HEAD on no branch"
      fi
      if [ -n "$reason" ]; then
        echo "  keep    $w  [$reason]"
      else
        echo "$w" >>"$remove_list"
      fi
    done
    count=$(wc -l <"$remove_list" | tr -d ' ')
    log "  $count worktree(s) to remove"
    if [ "$count" -gt 0 ]; then
      if [ "$MODE" = apply ]; then
        xargs -P4 -n1 "$SELF" --_remove-one "$repo" <"$remove_list"
        git -C "$repo" worktree prune
      else
        sed 's/^/  remove  /' "$remove_list"
      fi
    fi
    rm -f "$remove_list"
  done
fi

log "=== done — free: $(free_gb) GB"
