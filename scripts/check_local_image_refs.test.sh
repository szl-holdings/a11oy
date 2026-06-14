#!/usr/bin/env bash
# Offline negative-fixture self-test for scripts/check_local_image_refs.py.
#
# Each fixture builds a throwaway git repo that mimics the docs/site layout
# (a VitePress site under docs/site/docs/ with a public/ dir, plus the mirror
# READMEs that live OUTSIDE srcDir), then asserts the guard PASSES on an honest
# tree and FAILS the moment a locally-referenced image stops resolving to a
# committed file. The broken cases mirror the real #719 bug: a navbar logo, a
# hero image, a markdown footer avatar, or an inline <img> pointing at an asset
# that was never committed.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
CHECKER="$HERE/check_local_image_refs.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

# make_site <root>  — committed honest baseline (no broken refs).
make_site() {
  local R="$1"
  mkdir -p "$R/docs/site/docs/.vitepress" \
           "$R/docs/site/docs/public/img" \
           "$R/docs/site/cookbook/assets/genius" \
           "$R/docs/site/investor"
  git -C "$R" init -q
  git -C "$R" config user.email t@t.t
  git -C "$R" config user.name t

  # committed assets
  printf '<svg/>' > "$R/docs/site/docs/public/img/szl-mark.svg"
  printf '<svg/>' > "$R/docs/site/cookbook/assets/genius/cookbook_card.svg"

  # VitePress config: navbar logo via /-absolute -> public dir
  cat > "$R/docs/site/docs/.vitepress/config.mjs" <<'EOF'
export default {
  themeConfig: {
    // Navbar logo: committed static szl-mark.svg at /img/szl-mark.svg.
    // (historical: szl-avatar-animated.gif was removed)
    logo: '/img/szl-mark.svg',
  },
}
EOF

  # home page hero image via /-absolute -> public dir
  cat > "$R/docs/site/docs/index.md" <<'EOF'
---
layout: home
hero:
  name: SZL Holdings
  image:
    src: /img/szl-mark.svg
    alt: SZL Holdings
---
EOF

  # mirror README OUTSIDE srcDir: markdown ref relative to file
  cat > "$R/docs/site/README.md" <<'EOF'
# SZL
![SZL Holdings](./docs/public/img/szl-mark.svg)
A remote badge is fine: ![badge](https://img.shields.io/badge/x-y.svg)
EOF

  # cookbook README: markdown (../) + inline <img>
  cat > "$R/docs/site/cookbook/README.md" <<'EOF'
# Cookbook
<img src="assets/genius/cookbook_card.svg" alt="card" />
![SZL Holdings](../docs/public/img/szl-mark.svg)
EOF

  # investor README: markdown (../)
  cat > "$R/docs/site/investor/README.md" <<'EOF'
# Investor
![SZL Holdings](../docs/public/img/szl-mark.svg)
EOF

  git -C "$R" add -A
  git -C "$R" commit -qm baseline
}

run_guard() { python3 "$CHECKER" --root "$1" --scan docs/site --quiet; }

expect_pass() {
  local desc="$1" root="$2"
  if run_guard "$root" >/dev/null 2>&1; then
    echo "PASS (ok): $desc"; PASS=$((PASS+1))
  else
    echo "FAIL (expected pass, got fail): $desc"; FAIL=$((FAIL+1))
    run_guard "$root" 2>&1 | sed 's/^/    /'
  fi
}

expect_fail() {
  local desc="$1" root="$2"
  if run_guard "$root" >/dev/null 2>&1; then
    echo "FAIL (expected fail, got pass): $desc"; FAIL=$((FAIL+1))
  else
    echo "PASS (caught): $desc"; PASS=$((PASS+1))
  fi
}

commit_all() { git -C "$1" add -A >/dev/null 2>&1; git -C "$1" commit -qm x >/dev/null 2>&1 || true; }

# --------------------------------------------------------------------------
# A: honest committed tree -> PASS
# --------------------------------------------------------------------------
A="$TMP/A"; make_site "$A"
expect_pass "honest tree (logo + hero + mirror READMEs + inline img all committed)" "$A"

# --------------------------------------------------------------------------
# B: navbar logo points at a file that was never committed (the #719 class)
# --------------------------------------------------------------------------
B="$TMP/B"; make_site "$B"
sed -i "s|/img/szl-mark.svg|/img/szl-avatar-animated.gif|" \
  "$B/docs/site/docs/.vitepress/config.mjs"
commit_all "$B"
expect_fail "navbar logo references an uncommitted asset" "$B"

# --------------------------------------------------------------------------
# C: hero image src points at a missing file
# --------------------------------------------------------------------------
C="$TMP/C"; make_site "$C"
sed -i "s|src: /img/szl-mark.svg|src: /img/missing-hero.png|" \
  "$C/docs/site/docs/index.md"
commit_all "$C"
expect_fail "hero image.src references a missing file" "$C"

# --------------------------------------------------------------------------
# D: markdown ![]() in a mirror README points at a missing file
# --------------------------------------------------------------------------
D="$TMP/D"; make_site "$D"
printf '\n![gone](./docs/public/img/never-here.svg)\n' >> "$D/docs/site/README.md"
commit_all "$D"
expect_fail "markdown image ref to a missing file" "$D"

# --------------------------------------------------------------------------
# E: inline <img src> points at a missing file
# --------------------------------------------------------------------------
E="$TMP/E"; make_site "$E"
printf '\n<img src="assets/genius/cookbook_cast.svg" />\n' \
  >> "$E/docs/site/cookbook/README.md"
commit_all "$E"
expect_fail "inline <img> ref to a missing file" "$E"

# --------------------------------------------------------------------------
# F: the asset exists ON DISK but was never committed -> still FAIL
# --------------------------------------------------------------------------
F="$TMP/F"; make_site "$F"
printf '<svg/>' > "$F/docs/site/docs/public/img/uncommitted.svg"   # NOT git add-ed
sed -i "s|/img/szl-mark.svg|/img/uncommitted.svg|" \
  "$F/docs/site/docs/.vitepress/config.mjs"
git -C "$F" add "docs/site/docs/.vitepress/config.mjs" >/dev/null 2>&1
git -C "$F" commit -qm onlyconfig >/dev/null 2>&1
expect_fail "referenced image exists on disk but is uncommitted" "$F"

# --------------------------------------------------------------------------
# G: remote https image ref is ignored (no local file) -> PASS
# --------------------------------------------------------------------------
G="$TMP/G"; make_site "$G"
printf '\n![remote](https://example.com/x/some.svg)\n' >> "$G/docs/site/README.md"
commit_all "$G"
expect_pass "remote https image ref is ignored" "$G"

# --------------------------------------------------------------------------
# H: relative ../ ref that DOES resolve into the public dir -> PASS
# --------------------------------------------------------------------------
H="$TMP/H"; make_site "$H"
printf '\n![ok](../docs/public/img/szl-mark.svg)\n' >> "$H/docs/site/cookbook/README.md"
commit_all "$H"
expect_pass "relative ../ ref that resolves to a committed file" "$H"

echo ""
echo "self-test results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
