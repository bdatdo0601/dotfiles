# ---------------------------------------------------------------------------
# Shared helpers for the run_once_after_* setup scripts.
# Included with {{ "{{" }} template "setup-lib.sh" . {{ "}}" }}; expects SETUP_NAME and
# STEP_TOTAL to be set by the including script. Targets macOS bash 3.2.
# ---------------------------------------------------------------------------
set -u
set -o pipefail

# shellcheck disable=SC2034  # used by some including scripts
SOURCE_DIR="{{ .chezmoi.sourceDir }}"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y%m%d-%H%M%S)-${SETUP_NAME}.log"

# Decide on colour before stdout is redirected through tee.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then USE_COLOR=1; else USE_COLOR=0; fi

# Mirror all output to the log file, with ANSI colour codes stripped there.
exec > >(tee >(sed -E $'s/\x1b\\[[0-9;]*m//g' >> "$LOG_FILE")) 2>&1

_c() { [ "$USE_COLOR" = 1 ] && printf '\033[%sm' "$1"; return 0; }
BOLD=$(_c 1); DIM=$(_c 2); RED=$(_c 31); GREEN=$(_c 32); YELLOW=$(_c 33)
BLUE=$(_c 34); CYAN=$(_c 36); RESET=$(_c 0)

log_info() { printf '%s    • %s%s\n' "$DIM" "$*" "$RESET"; }
log_ok()   { printf '%s    ✔ %s%s\n' "$GREEN" "$*" "$RESET"; }
log_warn() { printf '%s    ⚠ %s%s\n' "$YELLOW" "$*" "$RESET"; }
log_err()  { printf '%s    ✖ %s%s\n' "$RED" "$*" "$RESET"; }

fmt_duration() {
  local s=$1
  if [ "$s" -ge 60 ]; then printf '%dm%02ds' $((s / 60)) $((s % 60)); else printf '%ds' "$s"; fi
}

SCRIPT_START=$(date +%s)
STEP_INDEX=0
RESULTS=()   # entries: status|name|duration|note
FAILURES=0
WARNINGS=0

header() {
  printf '\n%s%s━━━ %s ━━━%s\n' "$BOLD" "$BLUE" "$1" "$RESET"
  printf '%s    host: %s · macOS %s · %s · %s%s\n' "$DIM" \
    "$(scutil --get ComputerName 2>/dev/null || hostname)" \
    "$(sw_vers -productVersion 2>/dev/null || uname -r)" "$(uname -m)" "$(date '+%Y-%m-%d %H:%M')" "$RESET"
  printf '%s    log:  %s%s\n' "$DIM" "$LOG_FILE" "$RESET"
}

# A step function signals its outcome through its exit code:
#   0 = done, 2 = skipped (already in place), 3 = finished with warnings,
#   anything else = failed. STEP_NOTE may carry a one-line explanation.
STEP_NOTE=""
run_step() {
  local name=$1 fn=$2 start rc elapsed status
  STEP_INDEX=$((STEP_INDEX + 1))
  STEP_NOTE=""
  printf '\n%s[%d/%d] %s%s\n' "$BOLD$CYAN" "$STEP_INDEX" "$STEP_TOTAL" "$name" "$RESET"
  start=$(date +%s)
  "$fn"
  rc=$?
  elapsed=$(fmt_duration $(($(date +%s) - start)))
  case $rc in
    0) status=ok;   log_ok "Done in $elapsed${STEP_NOTE:+ — $STEP_NOTE}" ;;
    2) status=skip; log_ok "Already set up${STEP_NOTE:+ — $STEP_NOTE}" ;;
    3) status=warn; WARNINGS=$((WARNINGS + 1)); log_warn "Finished with warnings in $elapsed${STEP_NOTE:+ — $STEP_NOTE}" ;;
    *) status=fail; FAILURES=$((FAILURES + 1)); log_err "Failed (exit $rc) after $elapsed${STEP_NOTE:+ — $STEP_NOTE}" ;;
  esac
  RESULTS+=("$status|$name|$elapsed|$STEP_NOTE")
  return 0
}

# Prints the per-step table and exits non-zero if any step failed, so chezmoi
# keeps this run_once script pending and retries it on the next `chezmoi apply`.
finish() {
  local total entry status name dur note icon
  total=$(fmt_duration $(($(date +%s) - SCRIPT_START)))
  printf '\n%s━━━ %s summary (%s) ━━━%s\n' "$BOLD$BLUE" "$SETUP_NAME" "$total" "$RESET"
  for entry in ${RESULTS[@]+"${RESULTS[@]}"}; do
    IFS='|' read -r status name dur note <<EOF
$entry
EOF
    case $status in
      ok)   icon="${GREEN}✔ done   " ;;
      skip) icon="${DIM}○ present" ;;
      warn) icon="${YELLOW}⚠ warning" ;;
      fail) icon="${RED}✖ FAILED " ;;
    esac
    printf '  %s%s  %-34s %6s%s  %s\n' "$icon" "$RESET" "$name" "$dur" "$DIM" "$note$RESET"
  done
  printf '%s  Full log: %s%s\n' "$DIM" "$LOG_FILE" "$RESET"
  if [ "$FAILURES" -gt 0 ]; then
    printf '%s  %d step(s) failed. Fix the issue above, then re-run `chezmoi apply` — completed steps are skipped.%s\n' \
      "$RED" "$FAILURES" "$RESET"
    exit 1
  fi
  [ "$WARNINGS" -gt 0 ] && printf '%s  %d step(s) had warnings; see above.%s\n' "$YELLOW" "$WARNINGS" "$RESET"
  exit 0
}

# confirm "Question" [default y|n] — reads from the terminal; uses the default when there is none.
confirm() {
  local answer prompt default=${2:-y}
  [ "$default" = y ] && prompt="[Y/n]" || prompt="[y/N]"
  if [ -r /dev/tty ] && { : < /dev/tty; } 2>/dev/null; then
    printf '%s    ? %s %s %s' "$BOLD" "$1" "$prompt" "$RESET" > /dev/tty
    read -r answer < /dev/tty || answer=""
  else
    answer=""
  fi
  answer=${answer:-$default}
  case $answer in [Yy]*) return 0 ;; *) return 1 ;; esac
}

load_brew_env() {
  command -v brew >/dev/null 2>&1 && return 0
  local b
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
  done
  return 1
}

SUDO_KEEPALIVE_PID=""
keep_sudo_alive() {
  log_info "Requesting administrator access once for the whole run (prompts from sudo are otherwise hidden by brew)."
  sudo -v || return 1
  ( while true; do sudo -n true; sleep 50; kill -0 "$$" 2>/dev/null || exit; done ) 2>/dev/null &
  SUDO_KEEPALIVE_PID=$!
  trap '[ -n "$SUDO_KEEPALIVE_PID" ] && kill "$SUDO_KEEPALIVE_PID" 2>/dev/null' EXIT
}
