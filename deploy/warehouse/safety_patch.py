#!/usr/bin/env python3
"""Guarded, source-only hardening for the external warehouse service.

The warehouse application is maintained outside this repository.  This module
therefore patches only two small, known source anchors instead of vendoring the
application:

* bind Express to loopback rather than all interfaces; and
* make Shopify product-content writes fail closed unless an explicit runtime
  flag enables them.

The default command is deliberately read-only (`check`).  `apply` creates a
dated, secret-free source backup and never restarts a service.  A source drift
or partial patch is an error, not a reason to guess.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from typing import Iterable


SERVER_RELATIVE = Path("src/server.js")
SHOPIFY_RELATIVE = Path("src/shopify.js")
ALLOWED_ROLLBACK_FILES = frozenset({SERVER_RELATIVE, SHOPIFY_RELATIVE})

LOOPBACK_OLD = "app.listen(PORT, () => console.log(`Warehouse on :${PORT}`));"
LOOPBACK_NEW = (
    "app.listen(PORT, '127.0.0.1', "
    "() => console.log(`Warehouse on 127.0.0.1:${PORT}`));"
)

CONTENT_WRITE_GUARD = """// Live-store content mutations are fail-closed. During testing this variable is
// intentionally absent/false, so even an authenticated API caller cannot
// change prices, product visibility, or barcodes. Enabling writes requires an
// explicit server configuration change followed by a service restart.
export const contentWritesEnabled = () =>
  /^(1|true|yes|on)$/i.test(String(process.env.SHOPIFY_CONTENT_WRITES_ENABLED || '').trim());
""".rstrip("\n")

CENTRAL_MUTATION_GUARD = """// Every GraphQL mutation is independently disabled at the final network
// boundary. This also covers future mutation callers and webhook-registration
// code outside this module. Read-only queries continue to work normally.
export const shopifyMutationsEnabled = () =>
  /^(1|true|yes|on)$/i.test(String(process.env.SHOPIFY_MUTATIONS_ENABLED || '').trim());

function documentHasMutation(document) {
  const withoutCommentsOrStrings = String(document || '')
    .replace(/#[^\\r\\n]*/g, ' ')
    .replace(/\"\"\"[\\s\\S]*?\"\"\"/g, ' ')
    .replace(/\"(?:\\\\.|[^\"\\\\])*\"/g, ' ');
  return /\\bmutation\\b/i.test(withoutCommentsOrStrings);
}

function requireShopifyMutationApproval(document) {
  if (documentHasMutation(document) && !shopifyMutationsEnabled()) {
    throw new Error(
      'Shopify GraphQL mutations are disabled and were not sent. ' +
      'Set SHOPIFY_MUTATIONS_ENABLED=true only for a separately approved operation.'
    );
  }
}
""".rstrip("\n")

CONTENT_REQUIRE_GUARD = """function requireContentWrites(action) {
  if (!contentWritesEnabled()) {
    throw new Error(
      `Shopify content writes are disabled; ${action} was not sent. ` +
      'Set SHOPIFY_CONTENT_WRITES_ENABLED=true only after live-write approval.'
    );
  }
}
""".rstrip("\n")

WRITE_GUARD = "\n\n".join(
    (CONTENT_WRITE_GUARD, CENTRAL_MUTATION_GUARD, CONTENT_REQUIRE_GUARD)
)

GRAPHQL_FUNCTION_OLD = (
    "export async function shopifyGraphQL(query, variables = {}, attempt = 0) {\n"
    "  if (!shopConfigured()) {"
)
GRAPHQL_FUNCTION_NEW = (
    "export async function shopifyGraphQL(query, variables = {}, attempt = 0) {\n"
    "  requireShopifyMutationApproval(query);\n"
    "  if (!shopConfigured()) {"
)

PRICE_FUNCTION_OLD = (
    "export async function setVariantPrices(productId, variants) {\n"
    "  const data = await shopifyGraphQL(VARIANTS_UPDATE, {"
)
PRICE_FUNCTION_NEW = (
    "export async function setVariantPrices(productId, variants) {\n"
    "  requireContentWrites('variant price update');\n"
    "  const data = await shopifyGraphQL(VARIANTS_UPDATE, {"
)

STATUS_FUNCTION_OLD = (
    "export async function setProductStatus(productId, status) {\n"
    "  const want = String(status).toUpperCase();"
)
STATUS_FUNCTION_NEW = (
    "export async function setProductStatus(productId, status) {\n"
    "  requireContentWrites('product status update');\n"
    "  const want = String(status).toUpperCase();"
)

BARCODE_FUNCTION_OLD = (
    "export async function setVariantBarcodes(productId, variants) {\n"
    "  const data = await shopifyGraphQL(VARIANT_BARCODES, {"
)
BARCODE_FUNCTION_NEW = (
    "export async function setVariantBarcodes(productId, variants) {\n"
    "  requireContentWrites('variant barcode update');\n"
    "  const data = await shopifyGraphQL(VARIANT_BARCODES, {"
)

GUARD_CALLS = (
    "requireContentWrites('variant price update');",
    "requireContentWrites('product status update');",
    "requireContentWrites('variant barcode update');",
)


class SafetyPatchError(RuntimeError):
    """An unexpected source or unsafe filesystem state."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_file(path: Path) -> None:
    if path.is_symlink():
        raise SafetyPatchError(f"refusing symlink target: {path}")
    if not path.is_file():
        raise SafetyPatchError(f"missing regular file: {path}")


def read_source(path: Path) -> str:
    require_regular_file(path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SafetyPatchError(f"source is not UTF-8 text: {path}") from exc


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SafetyPatchError(
            f"expected exactly one {label} anchor, found {count}; source drifted"
        )
    return source.replace(old, new, 1)


def patch_server(source: str) -> str:
    if LOOPBACK_NEW in source:
        if LOOPBACK_OLD in source or source.count(LOOPBACK_NEW) != 1:
            raise SafetyPatchError("server.js has an ambiguous or partial listen patch")
        return source
    return replace_once(source, LOOPBACK_OLD, LOOPBACK_NEW, "server listen")


def patch_shopify(source: str) -> str:
    guard_present = "export const contentWritesEnabled = () =>" in source
    any_guard_artifact = "requireContentWrites(" in source or "SHOPIFY_CONTENT_WRITES_ENABLED" in source
    if guard_present or any_guard_artifact:
        # Upgrade the first write lock to the central mutation boundary without
        # weakening or duplicating its three content-specific guards.
        has_v1 = (
            source.count("export const contentWritesEnabled = () =>") == 1
            and source.count("function requireContentWrites(action) {") == 1
            and all(source.count(call) == 1 for call in GUARD_CALLS)
        )
        if not has_v1:
            raise SafetyPatchError("shopify.js contains a partial or unexpected write guard")
        if "SHOPIFY_MUTATIONS_ENABLED" not in source:
            insertion = "function requireContentWrites(action) {"
            source = replace_once(
                source,
                insertion,
                f"{CENTRAL_MUTATION_GUARD}\n\n{insertion}",
                "central mutation guard insertion",
            )
        if "requireShopifyMutationApproval(query);" not in source:
            source = replace_once(
                source,
                GRAPHQL_FUNCTION_OLD,
                GRAPHQL_FUNCTION_NEW,
                "central mutation boundary",
            )
        if not shopify_is_hardened(source):
            raise SafetyPatchError("shopify.js contains a partial or unexpected write guard")
        return source

    source = replace_once(
        source,
        "const VARIANTS_UPDATE = `",
        f"{WRITE_GUARD}\n\nconst VARIANTS_UPDATE = `",
        "write-guard insertion",
    )
    source = replace_once(source, PRICE_FUNCTION_OLD, PRICE_FUNCTION_NEW, "price guard")
    source = replace_once(source, STATUS_FUNCTION_OLD, STATUS_FUNCTION_NEW, "status guard")
    source = replace_once(source, BARCODE_FUNCTION_OLD, BARCODE_FUNCTION_NEW, "barcode guard")
    source = replace_once(
        source,
        GRAPHQL_FUNCTION_OLD,
        GRAPHQL_FUNCTION_NEW,
        "central mutation boundary",
    )
    return source


def server_is_hardened(source: str) -> bool:
    return source.count(LOOPBACK_NEW) == 1 and LOOPBACK_OLD not in source


def shopify_is_hardened(source: str) -> bool:
    if source.count("export const contentWritesEnabled = () =>") != 1:
        return False
    if source.count("function requireContentWrites(action) {") != 1:
        return False
    if source.count("SHOPIFY_CONTENT_WRITES_ENABLED || ''") != 1:
        return False
    if source.count("SHOPIFY_MUTATIONS_ENABLED || ''") != 1:
        return False
    if source.count("function requireShopifyMutationApproval(document) {") != 1:
        return False
    if source.count("requireShopifyMutationApproval(query);") != 1:
        return False
    if any(source.count(call) != 1 for call in GUARD_CALLS):
        return False
    if "export async function setVariantPrices" not in source:
        return False
    if "export async function setProductStatus" not in source:
        return False
    if "export async function setVariantBarcodes" not in source:
        return False
    graphql_start = source.index("export async function shopifyGraphQL")
    boundary_index = source.index("requireShopifyMutationApproval(query);", graphql_start)
    network_index = source.find("fetch(endpoint()", graphql_start)
    if network_index == -1 or boundary_index > network_index:
        return False

    for function_marker, guard_call in (
        ("export async function setVariantPrices", GUARD_CALLS[0]),
        ("export async function setProductStatus", GUARD_CALLS[1]),
        ("export async function setVariantBarcodes", GUARD_CALLS[2]),
    ):
        function_start = source.index(function_marker)
        guard_index = source.index(guard_call, function_start)
        network_index = source.find("shopifyGraphQL(", function_start)
        if network_index == -1 or guard_index > network_index:
            return False
    return True


def check_sources(root: Path, *, emit: bool = True) -> tuple[Path, Path]:
    server_path = root / SERVER_RELATIVE
    shopify_path = root / SHOPIFY_RELATIVE
    server = read_source(server_path)
    shopify = read_source(shopify_path)
    errors: list[str] = []
    if not server_is_hardened(server):
        errors.append(f"{server_path} is not loopback-hardened")
    if not shopify_is_hardened(shopify):
        errors.append(f"{shopify_path} is not fail-closed for content writes")
    if errors:
        raise SafetyPatchError("; ".join(errors))
    if emit:
        print(f"PASS: warehouse safety sources are hardened under {root}")
    return server_path, shopify_path


def _copy_metadata(source: Path, target: Path) -> None:
    source_stat = source.stat()
    os.chmod(target, stat.S_IMODE(source_stat.st_mode))
    try:
        os.chown(target, source_stat.st_uid, source_stat.st_gid)
    except PermissionError as exc:
        raise SafetyPatchError(
            f"cannot preserve owner for {target}; run with the source owner or root"
        ) from exc
    os.utime(target, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))


def _write_staged(path: Path, source: str) -> Path:
    source_stat = path.stat()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.codex-safety-", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(source, encoding="utf-8")
        _copy_metadata(path, temporary)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _copy_backup(path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path, follow_symlinks=False)
    _copy_metadata(path, backup_path)


def create_backup(root: Path, paths: Iterable[Path], reason: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = root / ".codex-safety-backups" / stamp
    suffix = 1
    while backup_root.exists():
        backup_root = root / ".codex-safety-backups" / f"{stamp}-{suffix}"
        suffix += 1
    backup_root.mkdir(parents=True, mode=0o700)
    manifest: dict[str, object] = {
        "schema": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "files": [],
    }
    entries: list[dict[str, object]] = []
    for path in paths:
        relative = path.relative_to(root)
        destination = backup_root / relative
        _copy_backup(path, destination)
        entries.append(
            {
                "path": str(relative),
                "sha256": sha256(path),
                "mode": oct(stat.S_IMODE(path.stat().st_mode)),
            }
        )
    manifest["files"] = entries
    manifest_path = backup_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.chmod(manifest_path, 0o600)
    return backup_root


def _restore_from_backup(root: Path, backup_root: Path, paths: Iterable[Path]) -> None:
    staged: list[tuple[Path, Path]] = []
    try:
        for target in paths:
            require_regular_file(target)
            backup_path = backup_root / target.relative_to(root)
            require_regular_file(backup_path)
            staged.append((target, _stage_copy(backup_path, target)))
        for target, temporary in staged:
            os.replace(temporary, target)
    finally:
        for _target, temporary in staged:
            temporary.unlink(missing_ok=True)


def _stage_copy(source: Path, target: Path) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.codex-restore-", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary, follow_symlinks=False)
        _copy_metadata(target, temporary)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _install_staged(staged: dict[Path, Path]) -> None:
    installed: list[Path] = []
    try:
        for target, temporary in staged.items():
            os.replace(temporary, target)
            installed.append(target)
    except Exception:
        for target, temporary in staged.items():
            temporary.unlink(missing_ok=True)
        raise
    finally:
        for target in installed:
            staged[target].unlink(missing_ok=True)


def apply_patch(root: Path, dry_run: bool) -> int:
    server_path = root / SERVER_RELATIVE
    shopify_path = root / SHOPIFY_RELATIVE
    original_server = read_source(server_path)
    original_shopify = read_source(shopify_path)
    original_hashes = {
        server_path: sha256(server_path),
        shopify_path: sha256(shopify_path),
    }

    patched_server = patch_server(original_server)
    patched_shopify = patch_shopify(original_shopify)
    changes: dict[Path, tuple[str, str]] = {}
    if patched_server != original_server:
        changes[server_path] = (original_server, patched_server)
    if patched_shopify != original_shopify:
        changes[shopify_path] = (original_shopify, patched_shopify)

    if not changes:
        check_sources(root)
        print("Already hardened; no files changed.")
        return 0
    if dry_run:
        for path in changes:
            print(f"DRY RUN: would patch {path}")
        return 0

    backup_root = create_backup(root, changes, reason="pre-warehouse-safety-patch")
    staged: dict[Path, Path] = {}
    try:
        for path, (_original, patched) in changes.items():
            if sha256(path) != original_hashes[path]:
                raise SafetyPatchError(f"source changed while staging: {path}")
            staged[path] = _write_staged(path, patched)
        _install_staged(staged)
        check_sources(root)
    except Exception:
        try:
            _restore_from_backup(root, backup_root, changes)
        except Exception as restore_exc:
            raise SafetyPatchError(
                f"patch failed and automatic restore also failed: {restore_exc}"
            ) from restore_exc
        raise

    print(f"Applied warehouse safety patch; backup preserved at {backup_root}")
    print("Service was not restarted. Review, then restart warehouse.service separately.")
    return 0


def rollback_patch(root: Path, backup_root: Path, acknowledged: bool) -> int:
    if not acknowledged:
        raise SafetyPatchError(
            "rollback can remove the fail-closed guard; pass "
            "--acknowledge-write-enable-risk explicitly"
        )
    backup_root = backup_root.resolve()
    backup_parent = (root / ".codex-safety-backups").resolve()
    try:
        backup_root.relative_to(backup_parent)
    except ValueError as exc:
        raise SafetyPatchError(
            f"rollback backup must be under {backup_parent}"
        ) from exc
    manifest_path = backup_root / "manifest.json"
    require_regular_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise SafetyPatchError("rollback manifest has no files")
    paths: list[Path] = []
    for entry in entries:
        if not isinstance(entry, dict) or "path" not in entry:
            raise SafetyPatchError("rollback manifest contains an invalid file entry")
        relative = Path(str(entry["path"]))
        if relative not in ALLOWED_ROLLBACK_FILES:
            raise SafetyPatchError(f"rollback manifest contains unexpected path: {relative}")
        paths.append(root / relative)
    for path, entry in zip(paths, entries):
        backup_path = backup_root / path.relative_to(root)
        require_regular_file(backup_path)
        if sha256(backup_path) != entry.get("sha256"):
            raise SafetyPatchError(f"rollback backup hash mismatch: {backup_path}")
    current_backup = create_backup(root, paths, reason="pre-warehouse-safety-rollback")
    _restore_from_backup(root, backup_root, paths)
    print(f"Restored warehouse sources from {backup_root}")
    print(f"Current pre-rollback sources are backed up at {current_backup}")
    print("WARNING: run the check command before any service restart; rollback may re-enable writes.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="read-only source safety check")
    check.add_argument("root", nargs="?", type=Path, default=Path("/opt/warehouse"))

    apply = commands.add_parser("apply", help="guarded patch with dated backup")
    apply.add_argument("root", nargs="?", type=Path, default=Path("/opt/warehouse"))
    apply.add_argument("--dry-run", action="store_true", help="stage checks without writing")

    rollback = commands.add_parser("rollback", help="explicitly restore a dated backup")
    rollback.add_argument("root", type=Path)
    rollback.add_argument("backup", type=Path)
    rollback.add_argument(
        "--acknowledge-write-enable-risk",
        action="store_true",
        help="confirm that the restored source may not be fail-closed",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "check":
            check_sources(args.root.resolve())
            return 0
        if args.command == "apply":
            return apply_patch(args.root.resolve(), args.dry_run)
        if args.command == "rollback":
            return rollback_patch(
                args.root.resolve(), args.backup, args.acknowledge_write_enable_risk
            )
        raise SafetyPatchError(f"unsupported command: {args.command}")
    except (OSError, SafetyPatchError, ValueError, json.JSONDecodeError) as exc:
        print(f"SAFETY PATCH ABORTED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
