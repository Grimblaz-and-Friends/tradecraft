#!/bin/bash
# Runs as root inside the tradecraft-ci distribution, called by setup.py (#929).
# Every subcommand is idempotent: re-running it over a finished step changes
# nothing. setup.py copies this file, wsl.conf and isolation_check.py in through
# stdin, since the distribution mounts no Windows drive.
#
# Root never follows a symlink into, writes, changes ownership in, reads from
# or executes a file from the runner account's tree, because every job runs as
# that account and can change anything in it (#929, holder reading 8).
#
#   base               account, /etc/wsl.conf, fstab, packages (rows 1, 5, 7)
#   unpack N VER SHA   download and verify the runner into /home/ci-runner/runner-N
#   quiesce            stop both units and end every process the account runs
#   fresh N VER SHA    empty runner-N and extract the verified release into it
#   register N URL     configure instance N; the token arrives on stdin (C10)
#   start              start both units
#   service N          systemd unit and its root-owned drop-in
#   state              one JSON line describing both instances
#   workers            the number of Runner.Worker processes running now
set -euo pipefail

ACCOUNT=ci-runner
# The runner account's home. Only the tests override it, to run `state` and
# `workers` against a fresh tree.
HOME_DIR=${TRADECRAFT_CI_RUNNER_HOME:-/home/$ACCOUNT}
LIB=/usr/local/lib/tradecraft-private-ci
ORG=Grimblaz-and-Friends

say() { printf '%s\n' "$*" >&2; }

runner_dir() { printf '%s/runner-%s' "$HOME_DIR" "$1"; }
runner_name() { printf 'blaz-top-wsl-%s' "$1"; }
unit_name() { printf 'actions.runner.%s.%s.service' "$ORG" "$(runner_name "$1")"; }

as_account() {
  # The account's uid and groups with no_new_privs, the way the unit runs it.
  setpriv --reuid="$ACCOUNT" --regid="$ACCOUNT" --init-groups --no-new-privs "$@"
}

base() {
  install -o root -g root -m 0644 "$LIB/wsl.conf" /etc/wsl.conf

  if ! id -u "$ACCOUNT" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "$HOME_DIR" --shell /bin/bash \
      --user-group "$ACCOUNT"
    say "created $ACCOUNT"
  fi
  # Its own group only: no sudo, docker, lxd, incus or any other root route.
  usermod --groups "" "$ACCOUNT"
  rm -f "/etc/sudoers.d/$ACCOUNT"
  # No cron or at jobs for the account: either could start a process while a
  # registration token is in the guest.
  for deny in /etc/cron.deny /etc/at.deny; do
    touch "$deny"
    grep -qx "$ACCOUNT" "$deny" || printf '%s\n' "$ACCOUNT" >> "$deny"
  done

  # Root's password stays locked (Ubuntu's default, asserted, never set here).
  field=$(awk -F: '$1 == "root" { print $2 }' /etc/shadow)
  case "$field" in
    '*' | '!'*) ;;
    *) passwd --lock root >/dev/null; say "locked root's password" ;;
  esac

  # fstab: root-owned, 0644, and no Windows-backed entry (mountFsTab=false too).
  touch /etc/fstab
  sed -i -E '/^[^#]*[[:space:]](9p|drvfs|virtiofs|cifs|smb3)[[:space:]]/d' /etc/fstab
  chown root:root /etc/fstab
  chmod 0644 /etc/fstab

  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  packages=(
    # The base tools actions and steps assume from the hosted image (§3.7).
    git curl ca-certificates tar xz-utils zstd unzip zip jq python3 wget
    # Playwright 1.57.0's `install-deps chromium` for ubuntu24.04-x64, its tools
    # list then its chromium list (packages/playwright-core/src/server/registry/
    # nativeDeps.ts at v1.57.0). Serves Verra's e2e.yml :30 `--with-deps` and
    # :33 `install-deps`, which its carrier drops.
    xvfb fonts-noto-color-emoji fonts-unifont libfontconfig1 libfreetype6
    xfonts-cyrillic xfonts-scalable fonts-liberation fonts-ipafont-gothic
    fonts-wqy-zenhei fonts-tlwg-loma-otf fonts-freefont-ttf
    libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 libcairo2
    libcups2t64 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0t64 libnspr4 libnss3
    libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6
    libxfixes3 libxkbcommon0 libxrandr2
    # .NET's native prerequisites on Ubuntu 24.04, for actions/setup-dotnet in
    # Daemon's ci.yml :26 (the SDK itself lands in DOTNET_INSTALL_DIR).
    libc6 libgcc-s1 libicu74 liblttng-ust1t64 libssl3t64 libstdc++6 libunwind8
    zlib1g tzdata
    # The rest of what the runner's bin/installdependencies.sh installs on Ubuntu
    # 24.04, which root no longer runs from the account's tree.
    libkrb5-3
  )
  apt-get install -y -q --no-install-recommends "${packages[@]}"

  # PowerShell from Microsoft's signed repository for Ubuntu 24.04. Serves
  # Countdown-Clash's `shell: pwsh` steps (ci.yml :32, :36, :40), Verra's
  # ci-ready.yml :143, and the npm scripts that call pwsh in Verra's
  # ci-ready.yml :66 and :98 and Windgust-Questbook's ci.yml :48.
  if ! command -v pwsh >/dev/null 2>&1; then
    deb=$(mktemp --suffix=.deb)
    curl -fsSL -o "$deb" https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb
    dpkg -i "$deb"
    rm -f "$deb"
    apt-get update -q
    apt-get install -y -q powershell
  fi
}

unpack() {
  local n=$1 version=$2 sha=$3 force=${4:-} dir work tarball
  dir=$(runner_dir "$n")
  # Everything under the runner home belongs to the account every job runs as, so
  # a job can replace any path there with a symlink. Root never creates, reads,
  # writes, changes ownership in or executes from that tree: the account does the
  # account's work. Root keeps only the download and its SHA-256 check, in a
  # directory of its own, and hands the verified bytes over on stdin.
  if [ -z "$force" ] && as_account test -x "$dir/config.sh" \
      && [ "$(as_account cat "$dir/.tradecraft-version" 2>/dev/null || true)" = "$version" ]; then
    say "runner-$n already unpacked at $version"
    return
  fi
  work=$(mktemp -d)
  tarball="$work/runner.tar.gz"
  curl -fsSL -o "$tarball" \
    "https://github.com/actions/runner/releases/download/v$version/actions-runner-linux-x64-$version.tar.gz"
  echo "$sha  $tarball" | sha256sum --check --quiet
  as_account mkdir -p -m 0750 "$dir"
  as_account tar -xzf - -C "$dir" < "$tarball"
  rm -rf "$work"
  # The runner's bin/installdependencies.sh is not run: it is account-writable.
  # What it installs on Ubuntu 24.04 (libkrb5-3, zlib1g, liblttng-ust1t64,
  # libssl3t64, libicu74) is in base's package list.
  printf '%s\n' "$version" | as_account tee "$dir/.tradecraft-version" >/dev/null
}

quiesce() {
  # Before a registration token enters the guest, no process of the account may
  # run: a job's leftover process could read config.sh's environment, or replace
  # config.sh or bin/ under it. The units' KillMode=process lets such a process
  # outlive its job, so stopping the units isn't enough.
  local n tries
  for n in 1 2; do
    systemctl stop "$(unit_name "$n")" 2>/dev/null || true
  done
  crontab -r -u "$ACCOUNT" 2>/dev/null || true
  for tries in 1 2 3 4 5 6 7 8 9 10; do
    pkill -KILL -u "$ACCOUNT" 2>/dev/null || true
    pkill -KILL -U "$ACCOUNT" 2>/dev/null || true
    if ! pgrep -u "$ACCOUNT" >/dev/null 2>&1 && ! pgrep -U "$ACCOUNT" >/dev/null 2>&1; then
      say "no $ACCOUNT process runs"
      return 0
    fi
    sleep 1
  done
  say "processes of $ACCOUNT still run after 10 s:"
  pgrep -a -u "$ACCOUNT" >&2 || true
  return 1
}

fresh() {
  # The instance being registered gets the release's own config.sh and bin/: its
  # directory is emptied (by the account, in its own tree) and re-extracted from
  # the tarball whose SHA-256 root checked.
  local n=$1 version=$2 sha=$3
  as_account rm -rf "$(runner_dir "$n")"
  unpack "$n" "$version" "$sha" force
}

start() {
  local n
  for n in 1 2; do
    systemctl start "$(unit_name "$n")"
  done
}

register() {
  local n=$1 url=$2 dir
  dir=$(runner_dir "$n")
  # C10: the token arrives on stdin and reaches config.sh as an environment
  # input (ACTIONS_RUNNER_INPUT_TOKEN, which runner 2.338.0's CommandSettings
  # reads when no token argument is given), never in an argv or a file.
  # read answers 1 at end of input with no newline; the token is still read.
  IFS= read -r ACTIONS_RUNNER_INPUT_TOKEN || [ -n "$ACTIONS_RUNNER_INPUT_TOKEN" ]
  export ACTIONS_RUNNER_INPUT_TOKEN
  export HOME="$HOME_DIR"
  # The account enters its own directory; root never does.
  as_account bash -c 'cd "$1" && shift && exec ./config.sh "$@"' _ "$dir" \
    --unattended --url "$url" \
    --runnergroup private-ci --labels private-ci --no-default-labels \
    --name "$(runner_name "$n")" --work _work --replace
  unset ACTIONS_RUNNER_INPUT_TOKEN
}

service() {
  local n=$1 dir unit dropin
  dir=$(runner_dir "$n")
  unit=$(unit_name "$n")

  # The account lays out its own side: the service launcher svc.sh would copy,
  # the per-instance tool and temp directories, and (on an install made before
  # this setup wrote them into the drop-in) its old .env lines removed.
  as_account bash -c '
    set -euo pipefail
    cd "$1"
    install -m 0755 bin/runsvc.sh runsvc.sh
    mkdir -p -m 0750 _dotnet _tmp
    if [ -f .env ]; then sed -i -E "/^(DOTNET_INSTALL_DIR|TMPDIR)=/d" .env; fi
  ' _ "$dir"

  # Root writes the unit itself from the runner's own template
  # (src/Misc/layoutbin/actions.runner.service.template at v2.338.0), rather
  # than running the account-writable svc.sh. The unit runs as the account.
  printf '%s\n' \
    '[Unit]' \
    "Description=GitHub Actions Runner ($ORG.$(runner_name "$n"))" \
    'After=network-online.target' \
    '' \
    '[Service]' \
    "ExecStart=$dir/runsvc.sh" \
    "User=$ACCOUNT" \
    "WorkingDirectory=$dir" \
    'KillMode=process' \
    'KillSignal=SIGTERM' \
    'TimeoutStopSec=5min' \
    '' \
    '[Install]' \
    'WantedBy=multi-user.target' > "/etc/systemd/system/$unit"
  chmod 0644 "/etc/systemd/system/$unit"

  # Everything root decides about the instance lives in this root-owned drop-in:
  # no setuid route, the GPU paravirtualization device and WSLg's directory
  # hidden from jobs, and the install locations that keep the two instances from
  # racing on one directory (§3.7, C11) as Environment= lines, not lines in the
  # account's .env.
  dropin="/etc/systemd/system/$unit.d"
  install -d -m 0755 "$dropin"
  printf '%s\n' \
    '[Service]' \
    'NoNewPrivileges=true' \
    'InaccessiblePaths=-/dev/dxg -/usr/lib/wsl -/mnt/wslg' \
    "Environment=DOTNET_INSTALL_DIR=$dir/_dotnet" \
    "Environment=TMPDIR=$dir/_tmp" > "$dropin/tradecraft.conf"
  chmod 0644 "$dropin/tradecraft.conf"

  systemctl daemon-reload
  systemctl enable "$unit" >/dev/null 2>&1
  systemctl restart "$unit"
}

state() {
  # Root reads the account's tree only through state.py, which opens nothing
  # through a symlink and treats what it reads there as untrusted text.
  exec python3 "$(dirname "$0")/state.py"
}

workers() {
  pgrep -c -f 'Runner\.Worker' || true
}

case "${1:-}" in
  base) base ;;
  unpack) unpack "$2" "$3" "$4" ;;
  quiesce) quiesce ;;
  fresh) fresh "$2" "$3" "$4" ;;
  register) register "$2" "$3" ;;
  start) start ;;
  service) service "$2" ;;
  state) state ;;
  workers) workers ;;
  *) say "usage: provision.sh base|unpack N VER SHA|quiesce|fresh N VER SHA|register N URL|service N|start|state|workers"; exit 2 ;;
esac
