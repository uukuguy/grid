#!/usr/bin/env bash
# scripts/eaasp-install-opa.sh — download official OPA binary for L3 sidecar (v3.11.0).
#
# Per ADR-V2-034, L3 governance runs OPA as a sidecar on 127.0.0.1:18181.
# This script downloads the official release binary, verifies its SHA256 against
# the official checksums file, and installs it to third_party/opac/opa.
#
# No Docker. No external service account. Network access required only at
# install time. Re-runnable: existing binary is overwritten after a fresh
# checksum verification.
#
# Per ADR-V2-028 (Strict-by-default Config Validation), this script:
#   - Fails closed if the target OS/arch is unsupported.
#   - Fails closed if the official checksums file cannot be fetched.
#   - Fails closed if the binary's SHA256 does not match the official manifest.
#
# Environment overrides:
#   OPA_VERSION  — pin a specific OPA version (default: latest stable)
#   OPA_DIR       — install directory           (default: third_party/opac)

set -euo pipefail

OPA_VERSION="${OPA_VERSION:-latest}"
OPA_DIR="${OPA_DIR:-third_party/opac}"
OPA_BIN="${OPA_DIR}/opa"

# --- Detect target OS/arch ------------------------------------------------
detect_target() {
    local os arch
    case "$(uname -s)" in
        Linux)   os="linux" ;;
        Darwin)  os="darwin" ;;
        *)       echo "ERROR: unsupported OS $(uname -s) for OPA sidecar (ADR-V2-034). Use Linux or macOS." >&2; exit 1 ;;
    esac
    case "$(uname -m)" in
        x86_64|amd64) arch="amd64" ;;
        arm64|aarch64) arch="arm64" ;;
        *)             echo "ERROR: unsupported arch $(uname -m) for OPA sidecar (ADR-V2-034)." >&2; exit 1 ;;
    esac
    echo "${os}_${arch}"
}

# --- Resolve version (only when OPA_VERSION=latest) -------------------------
TARGET="$(detect_target)"

if [[ "${OPA_VERSION}" == "latest" ]]; then
    echo "Resolving latest OPA release..."
    # github API returns the latest release tag; grep for the first semver-only tag.
    OPA_VERSION="$(curl -fsSL https://api.github.com/repos/open-policy-agent/opa/releases/latest \
        | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
    if [[ -z "${OPA_VERSION}" ]]; then
        echo "ERROR: failed to resolve latest OPA version from GitHub API." >&2
        exit 1
    fi
fi

# Normalize: accept both "v0.68.0" and "0.68.0" forms.
OPA_VERSION="${OPA_VERSION#v}"

VERSION_TAG="v${OPA_VERSION}"
BASE_URL="https://github.com/open-policy-agent/opa/releases/download/${VERSION_TAG}"
ARCHIVE="opa_${OPA_VERSION}_${TARGET}.tar.gz"
CHECKSUMS="sha256sums.txt"

echo "OPA target: ${TARGET}"
echo "OPA version: ${VERSION_TAG}"
echo "Downloading ${ARCHIVE}..."

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

curl -fsSL "${BASE_URL}/${ARCHIVE}" -o "${TMPDIR}/${ARCHIVE}"
curl -fsSL "${BASE_URL}/${CHECKSUMS}" -o "${TMPDIR}/${CHECKSUMS}"

# --- Verify checksum (fail-closed) ----------------------------------------
EXPECTED="$(grep -E "[[:space:]]${ARCHIVE}\$" "${TMPDIR}/${CHECKSUMS}" | awk '{print \$1}')"
if [[ -z "${EXPECTED}" ]]; then
    echo "ERROR: ${ARCHIVE} not found in ${CHECKSUMS}; cannot verify integrity." >&2
    exit 1
fi

ACTUAL="$(shasum -a 256 "${TMPDIR}/${ARCHIVE}" | awk '{print \$1}')"
if [[ "${EXPECTED}" != "${ACTUAL}" ]]; then
    echo "ERROR: OPA binary checksum mismatch." >&2
    echo "  expected: ${EXPECTED}" >&2
    echo "  actual:   ${ACTUAL}" >&2
    exit 1
fi

# --- Extract and install --------------------------------------------------
tar -xzf "${TMPDIR}/${ARCHIVE}" -C "${TMPDIR}" "${TARGET}/opa" 2>/dev/null \
    || tar -xzf "${TMPDIR}/${ARCHIVE}" -C "${TMPDIR}"
EXTRACTED="$(find "${TMPDIR}" -type f -name opa -perm -u+x | head -n1)"
if [[ -z "${EXTRACTED}" ]]; then
    echo "ERROR: failed to extract opa binary from ${ARCHIVE}." >&2
    exit 1
fi

mkdir -p "${OPA_DIR}"
mv "${EXTRACTED}" "${OPA_BIN}"
chmod +x "${OPA_BIN}"

# --- Sanity check ---------------------------------------------------------
"${OPA_BIN}" version

cat <<EOF

✓ OPA ${VERSION_TAG} installed to ${OPA_BIN}

Next steps:
  1. Set L3_OPA_URL=http://127.0.0.1:18181 in your environment (or use the dev default).
  2. Start L3 governance; it will bind to 127.0.0.1:18181 as a sidecar.
  3. Verify health: curl -fsS \${L3_OPA_URL}/health
  4. (Optional) Run 'make opa-clean' to remove the binary.
EOF
