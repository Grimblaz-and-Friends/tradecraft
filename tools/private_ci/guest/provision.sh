#!/bin/bash
# Runs as root inside the tradecraft-ci distribution, called by setup.py (#929).
# Every subcommand is idempotent: re-running it over a finished step changes
# nothing. setup.py copies this file, wsl.conf and isolation_check.py in through
# stdin, since the distribution mounts no Windows drive.
#
#   base               account, /etc/wsl.conf, fstab, packages (rows 1, 5, 7)
#   unpack N VER SHA   download and verify the runner into /home/ci-runner/runner-N
#   register N URL     configure instance N; the token arrives on stdin (C10)
#   service N          systemd unit, NoNewPrivileges drop-in, per-instance .env
#   state              one JSON line describing both instances
#   workers            the number of Runner.Worker processes running now
set -euo pipefail

ACCOUNT=ci-runner
HOME_DIR=/home/$ACCOUNT
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
  local n=$1 version=$2 sha=$3 dir tarball
  dir=$(runner_dir "$n")
  if [ -x "$dir/config.sh" ] && [ "$(cat "$dir/.tradecraft-version" 2>/dev/null)" = "$version" ]; then
    say "runner-$n already unpacked at $version"
    return
  fi
  tarball=$(mktemp --suffix=.tar.gz)
  curl -fsSL -o "$tarball" \
    "https://github.com/actions/runner/releases/download/v$version/actions-runner-linux-x64-$version.tar.gz"
  echo "$sha  $tarball" | sha256sum --check --quiet
  install -d -o "$ACCOUNT" -g "$ACCOUNT" -m 0750 "$dir"
  chmod 0644 "$tarball"
  as_account tar -xzf "$tarball" -C "$dir"
  rm -f "$tarball"
  "$dir/bin/installdependencies.sh" >/dev/null
  printf '%s\n' "$version" | as_account tee "$dir/.tradecraft-version" >/dev/null
}

register() {
  local n=$1 url=$2 dir
  dir=$(runner_dir "$n")
  # C10: the token arrives on stdin and reaches config.sh as an environment
  # input (ACTIONS_RUNNER_INPUT_TOKEN, which runner 2.338.0's CommandSettings
  # reads when no token argument is given), never in an argv or a file.
  IFS= read -r ACTIONS_RUNNER_INPUT_TOKEN
  export ACTIONS_RUNNER_INPUT_TOKEN
  export HOME="$HOME_DIR"
  cd "$dir"
  as_account ./config.sh --unattended --url "$url" \
    --runnergroup private-ci --labels private-ci --no-default-labels \
    --name "$(runner_name "$n")" --work _work --replace
  unset ACTIONS_RUNNER_INPUT_TOKEN
}

service() {
  local n=$1 dir unit dropin
  dir=$(runner_dir "$n")
  unit=$(unit_name "$n")
  cd "$dir"
  if [ ! -f "/etc/systemd/system/$unit" ]; then
    ./svc.sh install "$ACCOUNT"
  fi
  dropin="/etc/systemd/system/$unit.d"
  install -d -m 0755 "$dropin"
  printf '[Service]\nNoNewPrivileges=true\n' > "$dropin/tradecraft.conf"
  chmod 0644 "$dropin/tradecraft.conf"

  # Tool installs that default to system paths land in this instance's own
  # space, so the two instances never race on one directory (§3.7, C11).
  install -d -o "$ACCOUNT" -g "$ACCOUNT" -m 0750 "$dir/_dotnet" "$dir/_tmp"
  touch "$dir/.env"
  sed -i -E '/^(DOTNET_INSTALL_DIR|TMPDIR)=/d' "$dir/.env"
  {
    printf 'DOTNET_INSTALL_DIR=%s/_dotnet\n' "$dir"
    # Verra's residue gate writes fixed names under the temp path; a per-instance
    # TMPDIR keeps two concurrent jobs from colliding there.
    printf 'TMPDIR=%s/_tmp\n' "$dir"
  } >> "$dir/.env"
  chown "$ACCOUNT:$ACCOUNT" "$dir/.env"

  systemctl daemon-reload
  systemctl enable "$unit" >/dev/null 2>&1
  systemctl restart "$unit"
}

state() {
  local first=1 n dir unit active nnp enter worker runner
  printf '{"instances": ['
  for n in 1 2; do
    dir=$(runner_dir "$n")
    unit=$(unit_name "$n")
    active=$(systemctl is-active "$unit" 2>/dev/null || true)
    nnp=$(systemctl show -p NoNewPrivileges --value "$unit" 2>/dev/null || true)
    enter=$(systemctl show -p ActiveEnterTimestamp --value "$unit" 2>/dev/null || true)
    enter=$( [ -n "$enter" ] && date -d "$enter" +%s 2>/dev/null || echo 0)
    worker=$(find "$dir/_diag" -maxdepth 1 -name 'Worker_*.log' -printf '%T@\n' 2>/dev/null \
      | sort -n | tail -n 1 | cut -d. -f1)
    runner=""
    if [ -f "$dir/.runner" ]; then
      runner=$(tr -d '\r\n' < "$dir/.runner" | sed 's/^\xEF\xBB\xBF//')
    fi
    [ "$first" = 1 ] || printf ', '
    first=0
    printf '{"n": %s, "unit": "%s", "unpacked": %s, "active": "%s", "no_new_privileges": "%s", ' \
      "$n" "$unit" "$( [ -x "$dir/config.sh" ] && echo true || echo false)" "$active" "$nnp"
    printf '"active_enter_epoch": %s, "last_worker_epoch": %s, "runner": %s}' \
      "${enter:-0}" "${worker:-0}" "${runner:-null}"
  done
  printf '], "now_epoch": %s}\n' "$(date +%s)"
}

workers() {
  pgrep -c -f 'Runner\.Worker' || true
}

case "${1:-}" in
  base) base ;;
  unpack) unpack "$2" "$3" "$4" ;;
  register) register "$2" "$3" ;;
  service) service "$2" ;;
  state) state ;;
  workers) workers ;;
  *) say "usage: provision.sh base|unpack N VER SHA|register N URL|service N|state|workers"; exit 2 ;;
esac
