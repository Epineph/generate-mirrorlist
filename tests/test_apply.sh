#!/usr/bin/env bash
# Verify the actual preview/apply boundary using isolated local fixtures.

set -Eeuo pipefail
IFS=$'\n\t'

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
script="$project_dir/generate-mirrorlist"

cat >"$scratch/valid" <<'EOF'
# Valid fixture; these addresses are never contacted.
Server = https://a.example/archlinux/$repo/os/$arch
Server = https://b.example/$repo/os/$arch
Server = https://c.example/arch/$repo/os/$arch
EOF
printf 'original mirrorlist\n' >"$scratch/target"
cp -- "$scratch/target" "$scratch/original"

# Preview must leave the existing destination untouched.
"$script" --from "$scratch/valid" --target "$scratch/target" >/dev/null
cmp -- "$scratch/original" "$scratch/target"

# Applying publishes the list and preserves the original in one backup.
"$script" --from "$scratch/valid" --target "$scratch/target" --apply \
  >"$scratch/apply.log"
cmp -- "$scratch/valid" "$scratch/target"
backups=("$scratch"/target.bak.*)
[[ ${#backups[@]} -eq 1 ]]
cmp -- "$scratch/original" "${backups[0]}"
[[ $(stat -c '%a' "$scratch/target") == 644 ]]

# Broken lists must fail before touching the destination.
cat >"$scratch/invalid" <<'EOF'
Server = http://unsafe.example/$repo/os/$arch
EOF
if "$script" --from "$scratch/invalid" --target "$scratch/target" --apply \
  >"$scratch/invalid.log" 2>&1; then
  printf 'FAIL: accepted an invalid mirrorlist\n' >&2
  exit 1
fi
cmp -- "$scratch/valid" "$scratch/target"

# Duplicate URLs must not count as independent fallback mirrors.
cat "$scratch/valid" "$scratch/valid" >"$scratch/duplicates"
if "$script" --from "$scratch/duplicates" --apply \
  --target "$scratch/target" >"$scratch/duplicates.log" 2>&1; then
  printf 'FAIL: accepted duplicate mirrors\n' >&2
  exit 1
fi

# A symlink target must not redirect the write into another file.
ln -s -- "$scratch/target" "$scratch/link"
if "$script" --from "$scratch/valid" --target "$scratch/link" --apply \
  >"$scratch/symlink.log" 2>&1; then
  printf 'FAIL: accepted a symlink target\n' >&2
  exit 1
fi
[[ -L $scratch/link ]]
cmp -- "$scratch/valid" "$scratch/target"

# An existing lock symlink must never truncate its referent.
printf 'preserve lock referent\n' >"$scratch/sentinel"
cp -- "$scratch/sentinel" "$scratch/sentinel.original"
ln -s -- "$scratch/sentinel" "$scratch/locked.lock"
if "$script" --from "$scratch/valid" --target "$scratch/locked" --apply \
  >"$scratch/lock.log" 2>&1; then
  printf 'FAIL: accepted a symlink lock\n' >&2
  exit 1
fi
cmp -- "$scratch/sentinel.original" "$scratch/sentinel"
[[ ! -e $scratch/locked ]]

# A backup failure must preserve the target and remove the staged replacement.
mkdir -- "$scratch/failing-bin"
cat >"$scratch/failing-bin/cp" <<'EOF'
#!/usr/bin/env bash
printf 'fixture: simulated backup failure\n' >&2
exit 23
EOF
chmod +x -- "$scratch/failing-bin/cp"
if PATH="$scratch/failing-bin:$PATH" "$script" --from "$scratch/valid" \
  --target "$scratch/target" --apply >"$scratch/failure.log" 2>&1; then
  printf 'FAIL: ignored a backup failure\n' >&2
  exit 1
fi
cmp -- "$scratch/valid" "$scratch/target"
shopt -s nullglob
staged_files=("$scratch"/target.new.*)
[[ ${#staged_files[@]} -eq 0 ]]

printf 'PASS: preview, apply, backup, invalid input and symlink tests\n'
