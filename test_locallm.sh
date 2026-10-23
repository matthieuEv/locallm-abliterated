#!/bin/bash
set -euo pipefail
repo=$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(mktemp -d "${TMPDIR:-/tmp}/locallm-tests.XXXXXX")
cleanup_tests() {
    local code=$? run log
    if (( code != 0 )); then
        for log in "${TEST_RECORD:-$root}"/*.log; do
            [[ ! -f "$log" ]] || { printf '%s\n' "$log" >&2; tail -n 20 "$log" >&2; }
        done
    fi
    for run in "$root"/case-*/home/.local/state/locallm-abliterated/run.json; do
        [[ ! -f "$run" ]] || /bin/bash -c 'source "$1/locallm"; state=$(dirname -- "$2"); stop_active' bash "$repo" "$run" || :
    done
    rm -rf -- "$root"
}
trap cleanup_tests EXIT
jq_dir=$(dirname -- "$(command -v jq)")
passed=0
setup_fixture() {
    export HOME="$root/case-$passed/home"
    export TEST_RECORD="$root/case-$passed/records"
    export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share"
    export XDG_STATE_HOME="$HOME/.local/state" XDG_CACHE_HOME="$HOME/.cache"
    export UV_TOOL_BIN_DIR="$HOME/.local/bin" HF_HOME="$HOME/.cache/huggingface"
    export HF_HUB_CACHE="$HF_HOME/hub" TMPDIR="$root/case-$passed/tmp"
    export TEST_MODEL='Youssofal/Qwen3.6-35B-A3B-Abliterated-Heretic-MLX-4bit'
    export PATH="$UV_TOOL_BIN_DIR:$jq_dir:/usr/bin:/bin:/usr/sbin:/sbin"
    export TEST_BUSY_PORT=0 TEST_LOW_DISK=0 TEST_LATEST=fail TEST_NO_V2=0 TEST_RAPID_FAIL=0 TEST_TUI_EXIT=0 TEST_TUI_HANG=0 TEST_RM_FAIL=0
    mkdir -p "$UV_TOOL_BIN_DIR" "$TEST_RECORD" "$TMPDIR" "$HOME/project with spaces"
    cat > "$UV_TOOL_BIN_DIR/curl" <<'MOCK'
#!/bin/bash
set -eu
url='' output=''
while (( $# )); do
 case "$1" in http*) url=$1;; -o) output=$2; shift;; esac
 shift
done
case "$url" in
 *update/api/latest*) [[ "$TEST_LATEST" != fail ]] || exit 22; printf '{"version":"3.0.0"}\n';;
 *registry.npmjs.org*)
  if [[ "$TEST_NO_V2" == 1 ]]; then printf '{"versions":{"2.11.0-beta":{},"3.0.0":{}}}\n';
  else printf '{"versions":{"2.9.0":{},"2.10.0":{},"2.11.0-beta":{},"3.0.0":{}}}\n'; fi;;
 *huggingface.co/api/models/*) printf '{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","siblings":[{"rfilename":"weights.safetensors","size":1000}]}\n';;
 *opencode.ai/v2/install) cp "$TEST_RECORD/install.stub" "$output";;
 */health/ready) [[ -f "$TEST_RECORD/rapid.alive" ]] || exit 7; printf '{}\n';;
 */v1/models) jq -n --arg id "$TEST_MODEL" '{data:[{id:$id}]}';;
 *) printf 'Unexpected URL: %s\n' "$url" >&2; exit 1;;
esac
MOCK
    cat > "$UV_TOOL_BIN_DIR/uv" <<'MOCK'
#!/bin/bash
set -eu
printf '%s\n' "$*" >> "$TEST_RECORD/uv.calls"
case "$*" in
 'tool list') [[ ! -f "$TEST_RECORD/uninstalled" ]] || exit 0; echo 'rapid-mlx v0.16.6';;
 'tool install '*) cp "$TEST_RECORD/rapid.stub" "$UV_TOOL_BIN_DIR/rapid-mlx"; chmod +x "$UV_TOOL_BIN_DIR/rapid-mlx";;
 'tool uninstall rapid-mlx') touch "$TEST_RECORD/uninstalled"; rm -f "$UV_TOOL_BIN_DIR/rapid-mlx";;
 *) exit 1;;
esac
MOCK
    cat > "$TEST_RECORD/install.stub" <<'MOCK'
#!/bin/bash
set -eu
mkdir -p "$HOME/.opencode/bin"
cp "$TEST_RECORD/opencode.stub" "$HOME/.opencode/bin/opencode"
chmod +x "$HOME/.opencode/bin/opencode"
touch "$TEST_RECORD/installed"
MOCK
    cat > "$TEST_RECORD/opencode.stub" <<'MOCK'
#!/bin/bash
set -eu
case "$*" in
 --version) echo 'opencode v2.10.0';;
 'service stop') exit 0;;
 *)
  printf '%s\n' "$@" > "$TEST_RECORD/tui.args"
  touch "$TEST_RECORD/tui.started"
  trap 'exit 130' TERM INT
  while [[ "$TEST_TUI_HANG" == 1 ]]; do sleep 0.1; done
  exit "$TEST_TUI_EXIT";;
esac
MOCK
    cat > "$TEST_RECORD/rapid.stub" <<'MOCK'
#!/bin/bash
set -eu
printf '%s\n' "$*" >> "$TEST_RECORD/rapid.calls"
case "$1" in
 pull)
  path="$HF_HUB_CACHE/models--${TEST_MODEL//\//--}/snapshots/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  mkdir -p "$path"; touch "$path/weights.safetensors";;
 serve)
  [[ "$TEST_RAPID_FAIL" == 0 ]] || exit 9
  touch "$TEST_RECORD/rapid.alive"
  trap 'rm -f "$TEST_RECORD/rapid.alive"; touch "$TEST_RECORD/rapid.stopped"; exit 0' TERM INT
  while :; do sleep 0.1; done;;
 rm)
  [[ "$TEST_RM_FAIL" == 0 ]] || exit 7
  rm -rf "$HF_HUB_CACHE/models--${TEST_MODEL//\//--}";;
 *) exit 1;;
esac
MOCK
    cat > "$UV_TOOL_BIN_DIR/lsof" <<'MOCK'
#!/bin/bash
[[ "$TEST_BUSY_PORT" == 1 ]]
MOCK
    cat > "$UV_TOOL_BIN_DIR/df" <<'MOCK'
#!/bin/bash
echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'
if [[ "$TEST_LOW_DISK" == 1 ]]; then echo 'test 1000 999 1 99% /'; else echo 'test 999999999 1 999999998 0% /'; fi
MOCK
    chmod +x "$UV_TOOL_BIN_DIR/"* "$TEST_RECORD/"*.stub
}
run_case() {
    passed=$((passed + 1))
    setup_fixture
    "$@"
    printf 'ok %s - %s\n' "$passed" "$1"
}
start_fake() { "$repo/locallm" start "$HOME/project with spaces" -s ses_fixture > "$TEST_RECORD/start.log" 2>&1; }
expect_fail() { if "$@"; then echo 'Expected failure' >&2; return 1; fi; }
wait_file() {
    local i
    for ((i=0;i<150;i++)); do [[ ! -f "$1" ]] || return 0; sleep 0.1; done
    cat "$TEST_RECORD/start.log" >&2
    return 1
}
case_start_and_exit() {
    start_fake || { cat "$TEST_RECORD/start.log"; return 1; }
    [[ -f "$TEST_RECORD/rapid.stopped" && ! -f "$TEST_RECORD/rapid.alive" ]]
    [[ ! -f "$XDG_STATE_HOME/locallm-abliterated/run.json" ]]
    grep -Fx "$(/bin/realpath "$HOME/project with spaces")" "$TEST_RECORD/tui.args" >/dev/null
    grep -Fx ses_fixture "$TEST_RECORD/tui.args" >/dev/null
    grep -F -- '--context-length 49152' "$TEST_RECORD/rapid.calls" >/dev/null
    jq -e --arg model "$TEST_MODEL" '.providers["rapid-mlx"].models[$model].limit == {context:49152,input:40960,output:8192}' "$XDG_CONFIG_HOME/opencode/opencode.json" >/dev/null
}
case_tui_failure_cleanup() {
    export TEST_TUI_EXIT=7
    expect_fail start_fake
    [[ -f "$TEST_RECORD/rapid.stopped" && ! -f "$TEST_RECORD/rapid.alive" ]]
}
case_server_failure_cleanup() {
    export TEST_RAPID_FAIL=1
    expect_fail start_fake
    [[ ! -f "$TEST_RECORD/tui.started" && ! -f "$XDG_STATE_HOME/locallm-abliterated/run.json" ]]
}
case_busy_port() {
    export TEST_BUSY_PORT=1
    expect_fail start_fake
    [[ ! -f "$TEST_RECORD/installed" && ! -d "$XDG_CONFIG_HOME/opencode" ]]
}
case_low_disk() {
    export TEST_LOW_DISK=1
    expect_fail start_fake
    [[ ! -f "$TEST_RECORD/installed" ]]
}
case_no_stable_v2() {
    export TEST_NO_V2=1
    expect_fail start_fake
    [[ ! -f "$TEST_RECORD/installed" ]]
}
case_budget_mismatch() {
    jq '.flags as $flags | .flags[($flags | index("--max-tokens")) + 1] = "4096"' "$repo/config/rapid-mlx.json" > "$TEST_RECORD/rapid-bad.json"
    expect_fail /bin/bash -c 'source "$1/locallm"; init_paths; rapid_config=$TEST_RECORD/rapid-bad.json; validate_config' bash "$repo" > "$TEST_RECORD/budget.log" 2>&1
}
case_config_symlinks() {
    mkdir -p "$XDG_CONFIG_HOME/opencode"
    echo keep > "$HOME/keep.txt"
    ln -s "$HOME/keep.txt" "$XDG_CONFIG_HOME/opencode/opencode.json"
    mkdir -p "$HOME/kept-dir"; echo keep > "$HOME/kept-dir/data"
    ln -s "$HOME/kept-dir" "$XDG_CONFIG_HOME/opencode/local-context.md"
    echo old > "$XDG_CONFIG_HOME/opencode/opencode.jsonc"
    echo credentials > "$XDG_CONFIG_HOME/opencode/auth.json"
    start_fake || { cat "$TEST_RECORD/start.log"; return 1; }
    [[ "$(cat "$HOME/keep.txt")" == keep ]]
    [[ "$(cat "$XDG_CONFIG_HOME/opencode/auth.json")" == credentials ]]
    [[ ! -L "$XDG_CONFIG_HOME/opencode/opencode.json" && ! -e "$XDG_CONFIG_HOME/opencode/opencode.jsonc" ]]
    [[ -f "$HOME/kept-dir/data" && ! -L "$XDG_CONFIG_HOME/opencode/local-context.md" ]]
}
case_destroy_preserves_projects() {
    start_fake || { cat "$TEST_RECORD/start.log"; return 1; }
    mkdir -p "$HF_HUB_CACHE/models--other--model" "$XDG_DATA_HOME/opencode"
    echo keep > "$HOME/project with spaces/WORKLOG.md"
    echo delete > "$XDG_DATA_HOME/opencode/session"
    "$repo/locallm" destroy > "$TEST_RECORD/destroy.log" 2>&1 || { cat "$TEST_RECORD/destroy.log"; return 1; }
    [[ ! -d "$XDG_CONFIG_HOME/opencode" && ! -d "$XDG_DATA_HOME/opencode" ]]
    [[ ! -d "$HF_HUB_CACHE/models--${TEST_MODEL//\//--}" && ! -d "$HOME/.opencode" ]]
    [[ -d "$HF_HUB_CACHE/models--other--model" && "$(cat "$HOME/project with spaces/WORKLOG.md")" == keep ]]
    [[ ! -d "$XDG_STATE_HOME/locallm-abliterated" ]]
    "$repo/locallm" destroy > "$TEST_RECORD/destroy-again.log" 2>&1
}
case_destroy_cleanup_failure() {
    start_fake || { cat "$TEST_RECORD/start.log"; return 1; }
    export TEST_RM_FAIL=1
    expect_fail "$repo/locallm" destroy > "$TEST_RECORD/destroy.log" 2>&1
    [[ -f "$XDG_CONFIG_HOME/opencode/opencode.json" && ! -f "$TEST_RECORD/uninstalled" ]]
}
case_unsafe_destroy() {
    export HOME="$root/case-$passed/opencode"
    mkdir -p "$HOME"
    export XDG_CONFIG_HOME="$HOME/.."
    # The selected opencode directory is HOME: reject before stopping or uninstalling.
    expect_fail "$repo/locallm" destroy > "$TEST_RECORD/destroy.log" 2>&1
    [[ ! -f "$TEST_RECORD/uv.calls" ]]
}
case_pid_identity() {
    /bin/bash -c 'source "$1/locallm"; init_paths; kill() { touch "$TEST_RECORD/signalled"; }; stop_record "{\"pid\":$$,\"identity\":\"different birth\"}"' bash "$repo"
    [[ ! -f "$TEST_RECORD/signalled" ]]
}
case_process_exits_during_stop() {
    /bin/bash -c 'source "$1/locallm"; init_paths; identity() { echo recorded; }; kill() { touch "$TEST_RECORD/signalled"; }; stop_record "{\"pid\":2147483647,\"identity\":\"recorded\"}" true' bash "$repo"
    [[ ! -f "$TEST_RECORD/signalled" ]]
}
case_safe_symlink_unlink() {
    mkdir -p "$HOME/kept"; echo keep > "$HOME/kept/data"
    ln -s "$HOME/kept" "$HOME/link"
    /bin/bash -c 'source "$1/locallm"; init_paths; remove_path "$HOME/link"' bash "$repo"
    [[ ! -L "$HOME/link" && -f "$HOME/kept/data" ]]
}
case_repo_protection() {
    ln -s "$repo" "$HOME/repo-link"
    expect_fail /bin/bash -c 'source "$1/locallm"; init_paths; remove_path "$HOME/repo-link/config"' bash "$repo" > "$TEST_RECORD/refusal.log" 2>&1
    [[ -f "$repo/config/opencode.json" ]]
}
case_concurrent_start_and_destroy() {
    export TEST_TUI_HANG=1
    start_fake & local owner=$!
    wait_file "$TEST_RECORD/tui.started"
    expect_fail "$repo/locallm" start "$HOME/project with spaces" > "$TEST_RECORD/second.log" 2>&1
    "$repo/locallm" destroy > "$TEST_RECORD/destroy.log" 2>&1 || { cat "$TEST_RECORD/destroy.log"; kill "$owner" 2>/dev/null || :; return 1; }
    wait "$owner" || :
    [[ ! -f "$TEST_RECORD/rapid.alive" && ! -d "$XDG_STATE_HOME/locallm-abliterated" ]]
}
case_signal_cleanup() {
    export TEST_TUI_HANG=1
    start_fake & local owner=$!
    wait_file "$TEST_RECORD/tui.started"
    kill -TERM "$(jq -r .owner.pid "$XDG_STATE_HOME/locallm-abliterated/run.json")"
    wait "$owner" || :
    [[ -f "$TEST_RECORD/rapid.stopped" && ! -f "$TEST_RECORD/rapid.alive" ]]
    [[ ! -f "$XDG_STATE_HOME/locallm-abliterated/run.json" && -d "$HOME/.opencode" ]]
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    run_case case_start_and_exit
    run_case case_tui_failure_cleanup
    run_case case_server_failure_cleanup
    run_case case_busy_port
    run_case case_low_disk
    run_case case_no_stable_v2
    run_case case_budget_mismatch
    run_case case_config_symlinks
    run_case case_destroy_preserves_projects
    run_case case_destroy_cleanup_failure
    run_case case_unsafe_destroy
    run_case case_pid_identity
    run_case case_process_exits_during_stop
    run_case case_safe_symlink_unlink
    run_case case_repo_protection
    run_case case_concurrent_start_and_destroy
    run_case case_signal_cleanup
    printf '%s tests réussis ; aucune installation réelle modifiée.\n' "$passed"
fi
