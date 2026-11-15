#!/usr/bin/env python3
"""DIY helper and consistency checker for ToolShear (based on CluvexStudio/Strata).

Subcommands:
  info              Show configured package, namespace, native library, and cert summary.
  cert-info FILES   Inspect DER/PEM certs or APK Signing Block v2 certificates.
  verify-namespace  Verify namespace, JNI symbols, AIDL, Manifest, and ProGuard alignment.
  check [--apk ...] Full consistency, leak-guard, CI, and optional APK verification.
  migrate           One-shot deterministic migration from upstream Strata to ToolShear.
  set-package       Update applicationId in app/build.gradle.kts.
  set-namespace     Update namespace across Gradle, AIDL, Manifest, ProGuard, Java/Kotlin, Rust.
  set-cert          Verify or inspect public diy/manager-cert.pem against expected pin.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

APP_NAME = "ToolShear"
PR_APP_NAME = "ToolShear PR"
APK_PREFIX = "ToolShear_"

DEFAULT_PACKAGE = "com.kxwphnruvde.tqymsfobg"
DEFAULT_PR_PACKAGE = "com.kxwphnruvde.tqymsfobg.pr"
DEFAULT_NAMESPACE = "io.vngkzxq.mprt"

OFFICIAL_PACKAGE = "dev.cluvex.strata"
OFFICIAL_NAMESPACE = "dev.cluvex.strata"

JNI_LIB_NAME = "hvzqck"
JNI_LIB = f"lib{JNI_LIB_NAME}.so"

EXPECTED_CERT_SIZE = 0x0317  # 791 bytes
EXPECTED_CERT_SHA256 = "94dc8bf3d10ca39999b9bcdf688642705edc8ea2aeb47e6feef33d6ca65afc6c"

APP_DIR = ROOT / "app"
APP_GRADLE = APP_DIR / "build.gradle.kts"
GRADLE_PROPERTIES = ROOT / "gradle.properties"
SETTINGS_GRADLE = ROOT / "settings.gradle.kts"
PROGUARD = APP_DIR / "proguard-rules.pro"
PROGUARD_MIN = APP_DIR / "proguard-minified-test.pro"
MANIFEST = APP_DIR / "src" / "main" / "AndroidManifest.xml"
JAVA_ROOT = APP_DIR / "src" / "main" / "java"
AIDL_ROOT = APP_DIR / "src" / "main" / "aidl"
RES_ROOT = APP_DIR / "src" / "main" / "res"
RESOURCES_ROOT = APP_DIR / "src" / "main" / "resources"

NATIVE_DIR = ROOT / "native"
CARGO_TOML = NATIVE_DIR / "Cargo.toml"
CARGO_LOCK = NATIVE_DIR / "Cargo.lock"
NATIVE_BUILD_SH = NATIVE_DIR / "build.sh"
NATIVE_LIB_RS = NATIVE_DIR / "src" / "lib.rs"
NATIVE_PDFIUM_RS = NATIVE_DIR / "src" / "pdfium.rs"
NATIVE_HEXIO_RS = NATIVE_DIR / "src" / "hexio.rs"
NATIVE_RAR_RS = NATIVE_DIR / "src" / "rar.rs"

WF_BUILD = ROOT / ".github" / "workflows" / "build.yml"
GITIGNORE = ROOT / ".gitignore"
PRE_COMMIT = ROOT / ".githooks" / "pre-commit"
CERT_FILE = ROOT / "diy" / "manager-cert.pem"
README_FILE = ROOT / "README.md"

APK_SIG_BLOCK_MAGIC = b"APK Sig Block 42"
V2_BLOCK_ID = 0x7109871A
VERITY_PADDING_ID = 0x42726577
KNOWN_BLOCK_IDS = {
    0xF05368C0: "APK v3 signing block",
    0x1B93AD61: "APK v3.1 signing block",
    0x4692772C: "APK v4 source stamp",
    0x6DFF800D: "SourceStamp v1",
    0x9D6303F7: "SourceStamp v2",
}

PKG_GRADLE_RE = re.compile(r'(\bapplicationId\s*=\s*")([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)(")')
NS_GRADLE_RE = re.compile(r'(\bnamespace\s*=\s*")([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)(")')
JNI_FN_RE = re.compile(r'\bJava_([a-zA-Z0-9_]+?)_core_(?:nativebridge_NativeBridge|pdf_view_Pdfium)_')

OTHER_DIY_LEAK_TOKENS = (
    "com.cioputlxxcc",
    "com.shdmmztfcqk",
    "io.qzxnbqm",
    "io.bpaqxkj",
    "libfshqpk",
    "libnseqsv",
    "libdsorft",
    "libmbksab",
    "20-kernelSU-diy",
    "16-kernelSU-Next",
)

UPSTREAM_FORBIDDEN_TOKENS = (
    "dev.cluvex.strata",
    "dev/cluvex/strata",
    "dev_cluvex_strata",
    "Lcom/cluvex/",
    "Ldev/cluvex/",
    "libstrata_native",
    "strata_native",
    "strata-native",
    "CluvexStudio",
    "cluvex",
    "strata",
    "Strata",
    "STRATA",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def load_cert(path: Path) -> bytes:
    data = path.read_bytes()
    if b"-----BEGIN CERTIFICATE-----" in data:
        pem = data.split(b"-----BEGIN CERTIFICATE-----", 1)[1].split(b"-----END CERTIFICATE-----", 1)[0]
        return base64.b64decode(b"".join(pem.split()))
    return data


def describe_cert(der: bytes) -> tuple[int, str]:
    return len(der), hashlib.sha256(der).hexdigest()


class ApkError(Exception):
    pass


def parse_v2_block(data: bytes, pos: int, end: int) -> bytes:
    def length_prefixed(p: int, limit: int) -> tuple[int, int]:
        if p + 4 > limit:
            raise ApkError("truncated v2 block")
        length = struct.unpack_from("<I", data, p)[0]
        if length > limit - p - 4:
            raise ApkError("truncated v2 block")
        return p + 4, p + 4 + length

    pos, signers_end = length_prefixed(pos, end)
    pos, _ = length_prefixed(pos, signers_end)
    pos, signed_data_end = length_prefixed(pos, signers_end)
    _, digests_end = length_prefixed(pos, signed_data_end)
    pos, certs_end = length_prefixed(digests_end, signed_data_end)
    pos, cert_end = length_prefixed(pos, certs_end)
    return data[pos:cert_end]


def read_apk_cert(path: Path) -> tuple[bytes, list[str]]:
    """Return (certificate DER, list of signing block warnings/problems)."""
    data = path.read_bytes()
    size = len(data)

    def u16(off: int) -> int:
        return struct.unpack_from("<H", data, off)[0]

    def u32(off: int) -> int:
        return struct.unpack_from("<I", data, off)[0]

    def u64(off: int) -> int:
        return struct.unpack_from("<Q", data, off)[0]

    eocd = None
    for i in range(0x10000):
        pos = size - i - 2
        if pos - 20 < 0:
            break
        if u16(pos) == i and u32(pos - 20) == 0x06054B50:
            eocd = pos - 20
            break
    if eocd is None:
        raise ApkError("cannot find ZIP end of central directory")
    if eocd >= 20 and u32(eocd - 20) == 0x07064B50:
        raise ApkError("ZIP64 APKs are not supported")

    cd_size, cd_offset = u32(eocd + 12), u32(eocd + 16)
    if cd_offset > eocd or cd_size != eocd - cd_offset or cd_offset < 0x20:
        raise ApkError("malformed central directory")

    pairs_end = cd_offset - 0x18
    block_size = u64(pairs_end)
    if data[pairs_end + 8 : pairs_end + 24] != APK_SIG_BLOCK_MAGIC:
        raise ApkError("no APK Signing Block (v1-only or unsigned APK)")
    if block_size < 0x18 or block_size > cd_offset - 8:
        raise ApkError("malformed APK Signing Block size")
    pos = cd_offset - block_size - 8
    if u64(pos) != block_size:
        raise ApkError("APK Signing Block size mismatch")
    pos += 8

    problems: list[str] = []
    certs: list[bytes] = []
    while pos < pairs_end:
        pair_size = u64(pos)
        pos += 8
        if pair_size < 4 or pair_size > pairs_end - pos:
            raise ApkError("malformed signing block pair")
        pair_end = pos + pair_size
        block_id = u32(pos)
        if block_id == V2_BLOCK_ID:
            certs.append(parse_v2_block(data, pos + 4, pair_end))
        elif block_id != VERITY_PADDING_ID:
            name = KNOWN_BLOCK_IDS.get(block_id, "unknown block")
            problems.append(f"contains {name} (0x{block_id:08x}); sign with v2 only")
        pos = pair_end

    if len(certs) != 1:
        raise ApkError(f"expected exactly one v2 signature block, found {len(certs)}")
    return certs[0], problems


def read_one_safe(path: Path, regex: re.Pattern[str], group: int, what: str, errors: list[str]) -> str | None:
    if not path.is_file():
        errors.append(f"missing {rel(path)}")
        return None
    matches = list(regex.finditer(read_text(path)))
    if len(matches) != 1:
        errors.append(f"expected one {what} match in {rel(path)}, found {len(matches)}")
        return None
    return matches[0].group(group)


def read_unique_safe(path: Path, regex: re.Pattern[str], group: int, what: str, errors: list[str]) -> str | None:
    if not path.is_file():
        errors.append(f"missing {rel(path)}")
        return None
    values = {m.group(group) for m in regex.finditer(read_text(path))}
    if len(values) != 1:
        errors.append(f"expected one unique {what} value in {rel(path)}, found {sorted(values)}")
        return None
    return next(iter(values))


def require_tokens(path: Path, tokens: tuple[str, ...], errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing {rel(path)}")
        return
    text = read_text(path)
    for token in tokens:
        if token not in text:
            errors.append(f"{rel(path)} is missing {token!r}")


def forbid_tokens(path: Path, tokens: tuple[str, ...], errors: list[str]) -> None:
    if not path.is_file():
        return
    text = read_text(path)
    for token in tokens:
        if token in text:
            errors.append(f"{rel(path)} still contains forbidden {token!r}")


def remove_empty_parents(path: Path, stop_at: Path) -> None:
    cur = path
    while cur != stop_at and cur.is_dir():
        try:
            cur.rmdir()
        except OSError:
            break
        cur = cur.parent


def is_valid_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", value))


def cmd_migrate(_args: argparse.Namespace) -> int:
    """Perform one-shot deterministic rebranding migration from Strata to ToolShear."""
    ns = DEFAULT_NAMESPACE
    ns_slash = ns.replace(".", "/")
    ns_under = ns.replace(".", "_")

    old_java = JAVA_ROOT.joinpath(*OFFICIAL_NAMESPACE.split("."))
    new_java = JAVA_ROOT.joinpath(*ns.split("."))
    if old_java.exists():
        if new_java.exists():
            raise SystemExit(f"error: both {rel(old_java)} and {rel(new_java)} exist")
        new_java.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_java), str(new_java))
        remove_empty_parents(old_java.parent, JAVA_ROOT)
        print(f"moved {rel(old_java)} -> {rel(new_java)}")

    old_aidl = AIDL_ROOT.joinpath(*OFFICIAL_NAMESPACE.split("."))
    new_aidl = AIDL_ROOT.joinpath(*ns.split("."))
    if old_aidl.exists():
        if new_aidl.exists():
            raise SystemExit(f"error: both {rel(old_aidl)} and {rel(new_aidl)} exist")
        new_aidl.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_aidl), str(new_aidl))
        remove_empty_parents(old_aidl.parent, AIDL_ROOT)
        print(f"moved {rel(old_aidl)} -> {rel(new_aidl)}")

    old_web = RESOURCES_ROOT / "strata-web"
    new_web = RESOURCES_ROOT / "toolshear-web"
    if old_web.exists():
        if new_web.exists():
            raise SystemExit(f"error: both {rel(old_web)} and {rel(new_web)} exist")
        shutil.move(str(old_web), str(new_web))
        print(f"moved {rel(old_web)} -> {rel(new_web)}")

    file_renames = [
        (new_java / "StrataApp.kt", new_java / "ToolShearApp.kt"),
        (new_java / "core" / "root" / "StrataRootService.kt", new_java / "core" / "root" / "AppRootService.kt"),
        (new_java / "ui" / "drawer" / "StrataDrawer.kt", new_java / "ui" / "drawer" / "AppDrawer.kt"),
        (
            JAVA_ROOT / "org" / "apache" / "commons" / "compress" / "archivers" / "sevenz" / "StrataAesDecoder.java",
            JAVA_ROOT / "org" / "apache" / "commons" / "compress" / "archivers" / "sevenz" / "AppAesDecoder.java",
        ),
    ]
    for src, dst in file_renames:
        if src.exists():
            if dst.exists():
                raise SystemExit(f"error: destination already exists: {rel(dst)}")
            shutil.move(str(src), str(dst))
            print(f"renamed {rel(src)} -> {rel(dst)}")

    ordered_replacements = [
        ("Java_dev_cluvex_strata_", f"Java_{ns_under}_"),
        ("dev.cluvex.strata", ns),
        ("dev/cluvex/strata", ns_slash),
        ("org.apache.commons.compress.archivers.sevenz.StrataAesDecoder", "org.apache.commons.compress.archivers.sevenz.AppAesDecoder"),
        ("StrataAesDecoder", "AppAesDecoder"),
        ("StrataRootService", "AppRootService"),
        ("StrataDrawerContent", "AppDrawerContent"),
        ("StrataDrawer", "AppDrawer"),
        ("StrataMark", "AppMark"),
        ("StorageStrata", "StorageCard"),
        ("StrataGauge", "StorageGauge"),
        ("drawStrata", "drawGauge"),
        ("StrataApp", "ToolShearApp"),
        ("StrataTheme", "ToolShearTheme"),
        ("StrataColors", "AppColors"),
        ("StrataShapes", "AppShapes"),
        ("strataShapes", "appShapes"),
        ("StrataTypography", "AppTypography"),
        ("StrataColorScheme", "AppColorScheme"),
        ("StrataSettings", "AppSettings"),
        ("Theme.Strata.Splash", "Theme.ToolShear.Splash"),
        ("Theme.Strata", "Theme.ToolShear"),
        ("ThemeSeeds.STRATA", "ThemeSeeds.PRIMARY"),
        ("strata_seed", "toolshear_seed"),
        ("strata_window_background", "toolshear_window_background"),
        ("model_seed_strata", "model_seed_toolshear"),
        ("settings_backup_not_strata", "settings_backup_invalid_format"),
        ("libstrata_native.so", JNI_LIB),
        ("libstrata_native", f"lib{JNI_LIB_NAME}"),
        ("strata_native_test_", f"{JNI_LIB_NAME}_test_"),
        ("strata_native", JNI_LIB_NAME),
        ("strata.pdfium", "toolshear.pdfium"),
        ("strata-native", "toolshear-native"),
        ("strata_hexio_", f"{JNI_LIB_NAME}_hexio_"),
        ("strata-not-a-rar.rar", "toolshear-not-a-rar.rar"),
        ("strata_clone_icon", "toolshear_clone_icon"),
        ("strata_bookmarks", "toolshear_bookmarks"),
        ("strata_settings", "toolshear_settings"),
        ("strata_remotes", "toolshear_remotes"),
        ("strata_locale", "toolshear_locale"),
        ("strata_vault", "toolshear_vault"),
        ("strata-settings", "toolshear-settings"),
        ("strata-staged", "toolshear-staged"),
        ("strata-install-", "toolshear-install-"),
        (".strata-rename-", ".toolshear-rename-"),
        ("strata-drawer", "toolshear-drawer"),
        ("strata:share", "toolshear:share"),
        ("/strata-web/index.html", "/toolshear-web/index.html"),
        ("X-Strata", "X-ToolShear"),
        (".strata/recycle", ".toolshear/recycle"),
        ("strata-vault-key-v1", "toolshear-vault-key-v1"),
        ("strata-code-editor", "toolshear-code-editor"),
        ("Strata/APKs", "ToolShear/APKs"),
        ("Strata/Remote", "ToolShear/Remote"),
        ("Strata.apk", "ToolShear.apk"),
        ("STRATA_CMD", "APP_CMD"),
        ("__strata_line", "__app_line"),
        ("strata-run", "app-run"),
        ("strata-cargo", "app-cargo"),
        ("strata-zig-out", "app-zig-out"),
        ("strata-nim", "app-nim"),
        ('"strata: "', '"toolshear: "'),
        ('arguments = listOf("-c", script, "strata")', 'arguments = listOf("-c", script, "toolshear")'),
        ('val username: String = "strata"', 'val username: String = "toolshear"'),
        ('mutableStateOf("strata")', 'mutableStateOf("toolshear")'),
        ('"Strata"', f'"{APP_NAME}"'),
        ("strata.versionName", "toolshear.versionName"),
        ("strata.versionCode", "toolshear.versionCode"),
        ("strata.testBuildType", "toolshear.testBuildType"),
        ("strata.splitApks", "toolshear.splitApks"),
    ]

    candidate_dirs = [
        APP_DIR / "src" / "main" / "java",
        APP_DIR / "src" / "main" / "aidl",
        APP_DIR / "src" / "main" / "res",
        APP_DIR / "src" / "main" / "resources",
        NATIVE_DIR / "src",
    ]
    candidate_files = [
        MANIFEST,
        PROGUARD,
        PROGUARD_MIN,
        GRADLE_PROPERTIES,
        SETTINGS_GRADLE,
        CARGO_TOML,
        CARGO_LOCK,
        NATIVE_BUILD_SH,
        ROOT / "LICENSE",
    ]

    all_files: list[Path] = []
    for d in candidate_dirs:
        if d.is_dir():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    all_files.append(p)
    for f in candidate_files:
        if f.is_file():
            all_files.append(f)

    seen: set[Path] = set()
    updated = 0
    for path in all_files:
        if path in seen or path.suffix.lower() in {".png", ".webp", ".jpg", ".so", ".jar", ".ttf", ".otf"}:
            continue
        seen.add(path)
        try:
            text = original = read_text(path)
        except UnicodeDecodeError:
            continue

        for old, new in ordered_replacements:
            text = text.replace(old, new)

        if path.name == "Appearance.kt":
            text = text.replace("const val STRATA = 0xFF2D6A4F.toInt()", "const val PRIMARY = 0xFF2D6A4F.toInt()")
            text = text.replace(", STRATA),", ", PRIMARY),")

        if path.name == "Cargo.toml":
            text = text.replace(
                "Strata native core — small, fast file utilities written in Rust and exposed to the app over JNI.",
                f"{APP_NAME} native core — small, fast file utilities written in Rust and exposed to the app over JNI.",
            )

        is_res_strings = path.parent.name.startswith("values") and path.name.startswith("strings") and path.suffix == ".xml"
        is_web_html = path.name == "index.html" and path.parent.name == "toolshear-web"
        if is_res_strings or is_web_html:
            text = re.sub(r"\bStrata\b", APP_NAME, text)
            text = text.replace("Strata", APP_NAME)

        if path == RES_ROOT / "values" / "strings.xml":
            text = re.sub(r'\s*<string name="app_name"[^>]*>.*?</string>\s*', "\n", text)
            if "<resources>" in text and "</resources>" in text and not re.search(r"<resources>\s*</resources>", text):
                pass

        if text != original:
            write_text(path, text)
            updated += 1

    print(f"migrate complete: updated {updated} files.")
    return 0


def verify_namespace(ns: str, package: str | None = None) -> list[str]:
    """Cross-check namespace, component renames, native libs, and resources."""
    errors: list[str] = []
    ns_slash = ns.replace(".", "/")
    ns_under = ns.replace(".", "_")

    g_ns = read_one_safe(APP_GRADLE, NS_GRADLE_RE, 2, "namespace", errors)
    if g_ns is not None and g_ns != ns:
        errors.append(f"app/build.gradle.kts namespace is {g_ns!r}, expected {ns!r}")

    for rs_path in (NATIVE_LIB_RS, NATIVE_PDFIUM_RS):
        jni_prefix = read_unique_safe(rs_path, JNI_FN_RE, 1, "JNI symbol namespace", errors)
        if jni_prefix is not None and jni_prefix != ns_under:
            errors.append(f"{rel(rs_path)} Java_ prefix uses {jni_prefix!r}, expected {ns_under!r}")

    if MANIFEST.is_file():
        manifest = read_text(MANIFEST)
        for comp in (
            'android:name=".ToolShearApp"',
            'android:name=".MainActivity"',
            f'<action android:name="{ns}.plugin.action.FILE" />',
            'android:theme="@style/Theme.ToolShear"',
            'android:theme="@style/Theme.ToolShear.Splash"',
        ):
            if comp not in manifest:
                errors.append(f"AndroidManifest.xml is missing {comp}")
        for old in ("StrataApp", "Theme.Strata", OFFICIAL_NAMESPACE):
            if old in manifest:
                errors.append(f"AndroidManifest.xml still references {old!r}")
    else:
        errors.append(f"missing {rel(MANIFEST)}")

    aidl = AIDL_ROOT.joinpath(*ns.split("."), "core", "shizuku", "IShizukuFileService.aidl")
    if not aidl.is_file():
        errors.append(f"missing {rel(aidl)}")
    else:
        aidl_text = read_text(aidl)
        if not re.search(rf"^package {re.escape(ns)}\.core\.shizuku;\r?$", aidl_text, re.MULTILINE):
            errors.append(f"{rel(aidl)} does not declare package {ns}.core.shizuku")

    for base in (JAVA_ROOT, AIDL_ROOT):
        old_dir = base.joinpath(*OFFICIAL_NAMESPACE.split("."))
        new_dir = base.joinpath(*ns.split("."))
        if old_dir.exists():
            errors.append(f"upstream source dir still exists: {rel(old_dir)}")
        if not new_dir.is_dir():
            errors.append(f"renamed source dir missing: {rel(new_dir)}")

    if PROGUARD.is_file():
        pg = read_text(PROGUARD)
        for req in (
            f"-keep interface {ns}.core.nativebridge.RarSink {{ *; }}",
            f"-keep class {ns}.core.shizuku.** {{ *; }}",
        ):
            if req not in pg:
                errors.append(f"proguard-rules.pro is missing {req!r}")
    else:
        errors.append(f"missing {rel(PROGUARD)}")

    if PROGUARD_MIN.is_file():
        pgm = read_text(PROGUARD_MIN)
        for req in (
            f"-keep class {ns}.** {{ *; }}",
            "-keep class org.apache.commons.compress.archivers.sevenz.AppAesDecoder { *; }",
        ):
            if req not in pgm:
                errors.append(f"proguard-minified-test.pro is missing {req!r}")
    else:
        errors.append(f"missing {rel(PROGUARD_MIN)}")

    ns_java = JAVA_ROOT.joinpath(*ns.split("."))
    require_tokens(ns_java / "ToolShearApp.kt", ("class ToolShearApp",), errors)
    require_tokens(ns_java / "core" / "root" / "AppRootService.kt", ("class AppRootService",), errors)
    require_tokens(ns_java / "core" / "nativebridge" / "NativeBridge.kt", (f'System.loadLibrary("{JNI_LIB_NAME}")',), errors)
    require_tokens(ns_java / "core" / "pdf" / "view" / "Pdfium.kt", ('System.getProperty("toolshear.pdfium")', f'System.loadLibrary("{JNI_LIB_NAME}")'), errors)
    require_tokens(ns_java / "ui" / "drawer" / "AppDrawer.kt", ("fun AppDrawerContent", f'"{APP_NAME}"'), errors)
    require_tokens(ns_java / "ui" / "theme" / "Theme.kt", ("fun ToolShearTheme", "object AppColors"), errors)
    require_tokens(ns_java / "core" / "root" / "ScriptExecutor.kt", ("class ScriptRunController", "ProcessBuilder"), errors)
    require_tokens(ns_java / "feature" / "script" / "ScriptRunnerDialog.kt", ("fun ScriptRunnerDialog",), errors)

    aes_file = JAVA_ROOT / "org" / "apache" / "commons" / "compress" / "archivers" / "sevenz" / "AppAesDecoder.java"
    require_tokens(aes_file, ("package org.apache.commons.compress.archivers.sevenz;", "public final class AppAesDecoder"), errors)
    old_aes = JAVA_ROOT / "org" / "apache" / "commons" / "compress" / "archivers" / "sevenz" / "StrataAesDecoder.java"
    if old_aes.exists():
        errors.append(f"old upstream decoder still exists: {rel(old_aes)}")

    return errors


def check_repo_rules(package: str, ns: str) -> list[str]:
    errors: list[str] = []

    require_tokens(SETTINGS_GRADLE, (f'rootProject.name = "{APP_NAME}"',), errors)
    require_tokens(
        GRADLE_PROPERTIES,
        ("toolshear.versionName=", "toolshear.versionCode="),
        errors,
    )
    require_tokens(
        APP_GRADLE,
        (
            f'applicationId = "{DEFAULT_PACKAGE}"',
            'val isPrBuild =',
            f'val defaultAppName = if (isPrBuild) "{PR_APP_NAME}" else "{APP_NAME}"',
            'resValue("string", "app_name", appName)',
            'toolshear.splitApks',
            'applicationIdSuffix = ".pr"',
            f'target/release/{JNI_LIB}',
            'systemProperty("toolshear.pdfium"',
        ),
        errors,
    )

    require_tokens(CARGO_TOML, (f'name = "{JNI_LIB_NAME}"',), errors)
    require_tokens(CARGO_LOCK, (f'name = "{JNI_LIB_NAME}"',), errors)
    require_tokens(NATIVE_BUILD_SH, (JNI_LIB,), errors)

    require_tokens(RES_ROOT / "values" / "themes.xml", ('name="Theme.ToolShear"', 'name="Theme.ToolShear.Splash"'), errors)
    require_tokens(RES_ROOT / "values" / "colors.xml", ('name="toolshear_seed"', 'name="toolshear_window_background"'), errors)
    require_tokens(RES_ROOT / "values-night" / "colors.xml", ('name="toolshear_window_background"',), errors)
    require_tokens(RES_ROOT / "drawable" / "ic_launcher_foreground.xml", ("<vector",), errors)
    require_tokens(RES_ROOT / "drawable" / "ic_launcher_monochrome.xml", ("<vector",), errors)

    for sf in sorted(RES_ROOT.glob("values*/strings*.xml")):
        try:
            xml_root = ET.fromstring(read_text(sf))
        except ET.ParseError as e:
            errors.append(f"{rel(sf)} failed XML parsing: {e}")
            continue
        if sf.name == "strings.xml":
            for elem in xml_root.iter():
                if elem.attrib.get("name") == "app_name":
                    errors.append(f"{rel(sf)} must not define app_name (injected via app/build.gradle.kts resValue)")

    ns_java = JAVA_ROOT.joinpath(*ns.split("."))
    require_tokens(ns_java / "core" / "donate" / "Donation.kt", ("emptyList<Wallet>()",), errors)
    if (ns_java / "core" / "donate" / "Donation.kt").is_file():
        d_txt = read_text(ns_java / "core" / "donate" / "Donation.kt")
        for addr in ("TRxVSHcoADZnBfztFmFb2TQopusAwWYEVR", "0x20c980AEF36Aa71D0A0e7bE382AeD20b73bC6D27", "UQAH75bXaaRUhZMwiF0ZujOXFDDmvLSPASKoOsWF0HNasiaM"):
            if addr in d_txt:
                errors.append(f"Donation.kt still contains upstream wallet address {addr}")

    require_tokens(RESOURCES_ROOT / "toolshear-web" / "index.html", (APP_NAME, "X-ToolShear"), errors)
    if (RESOURCES_ROOT / "strata-web").exists():
        errors.append("app/src/main/resources/strata-web still exists")

    require_tokens(GITIGNORE, (".diy-secrets/", "*.jks", "*.p12", "*.keystore", "builds/", "dist/"), errors)
    require_tokens(
        PRE_COMMIT,
        (".diy-secrets/", "dev\\.cluvex\\.strata", "libstrata_native", "toolshear_diy.py check"),
        errors,
    )

    if WF_BUILD.is_file():
        wf = read_text(WF_BUILD)
        for req in (
            "python3 diy/toolshear_diy.py check",
            "secrets.KEYSTORE",
            "secrets.KEYSTORE_PASSWORD",
            "secrets.KEY_ALIAS",
            "secrets.KEY_PASSWORD",
            "-Ptoolshear.splitApks=true",
            '"$APKSIGNER" sign',
            "--v2-signing-enabled true",
            "--v3-signing-enabled false",
            "python3 diy/toolshear_diy.py check --apk dist/*.apk",
        ):
            if req not in wf:
                errors.append(f".github/workflows/build.yml is missing {req!r}")
        for bad in ("STRATA_KEYSTORE_BASE64", "gh release create", "tags: ['v*']", "--verify-tag"):
            if bad in wf:
                errors.append(f".github/workflows/build.yml still contains {bad!r}")
    else:
        errors.append(f"missing {rel(WF_BUILD)}")

    # Scan repo for leaked upstream or other-DIY tokens (excluding docs/diy/git/secrets/builds).
    scan_roots = [APP_DIR, NATIVE_DIR, ROOT / ".github", GRADLE_PROPERTIES, SETTINGS_GRADLE, README_FILE]
    scan_files: list[Path] = []
    for item in scan_roots:
        if item.is_file():
            scan_files.append(item)
        elif item.is_dir():
            for p in sorted(item.rglob("*")):
                if p.is_file() and p.suffix.lower() not in {".png", ".webp", ".jpg", ".so", ".jar", ".ttf", ".otf", ".pdf"}:
                    scan_files.append(p)

    for p in scan_files:
        try:
            text = read_text(p)
        except UnicodeDecodeError:
            continue
        for tok in UPSTREAM_FORBIDDEN_TOKENS + OTHER_DIY_LEAK_TOKENS:
            if tok in text:
                errors.append(f"forbidden token {tok!r} found in {rel(p)}")

    return errors


def check_apk_contents(path: Path, package: str, ns: str, errors: list[str]) -> None:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        found_libs = [n for n in names if n.endswith(f"/{JNI_LIB}")]
        if not found_libs:
            errors.append(f"{path}: missing any */{JNI_LIB}")
        for name in sorted(names):
            if "strata_native" in name.lower():
                errors.append(f"{path}: contains forbidden library {name}")

        if "AndroidManifest.xml" not in names:
            errors.append(f"{path}: missing AndroidManifest.xml")
        else:
            manifest = z.read("AndroidManifest.xml")
            for forbidden in ("dev.cluvex.strata", "StrataApp", "Theme.Strata", "libstrata_native"):
                if forbidden.encode("utf-8") in manifest or forbidden.encode("utf-16-le") in manifest:
                    errors.append(f"{path}: binary manifest still contains {forbidden!r}")

        ns_slash = ns.replace(".", "/")
        for member in sorted(names):
            if not re.fullmatch(r"classes\d*\.dex", member):
                continue
            data = z.read(member)
            for token in (
                b"Ldev/cluvex/strata/",
                b"dev/cluvex/strata",
                b"dev.cluvex.strata",
                b"dev_cluvex_strata",
                b"libstrata_native",
                b"strata_native",
                b"CluvexStudio",
                *(t.encode("utf-8") for t in OTHER_DIY_LEAK_TOKENS),
            ):
                count = data.count(token)
                if count:
                    errors.append(f"{path}: {member} contains forbidden {token.decode()} ({count}x)")
            if f"L{ns_slash}/".encode("utf-8") not in data and member == "classes.dex":
                pass


def cmd_info(_args: argparse.Namespace) -> int:
    errors: list[str] = []
    pkg = read_one_safe(APP_GRADLE, PKG_GRADLE_RE, 2, "applicationId", errors)
    ns = read_one_safe(APP_GRADLE, NS_GRADLE_RE, 2, "namespace", errors)

    cert_status = "<missing>"
    if CERT_FILE.is_file():
        c_size, c_hash = describe_cert(load_cert(CERT_FILE))
        cert_status = f"0x{c_size:04x} ({c_size} bytes) sha256={c_hash}"

    print(f"app name     : {APP_NAME} (PR: {PR_APP_NAME}, prefix: {APK_PREFIX})")
    print(f"package name : {pkg or '<missing>'}")
    print(f"namespace    : {ns or '<missing>'}")
    print(f"native lib   : {JNI_LIB} (Cargo target={JNI_LIB_NAME})")
    print(f"expected cert: size=0x{EXPECTED_CERT_SIZE:04x} ({EXPECTED_CERT_SIZE} bytes) sha256={EXPECTED_CERT_SHA256}")
    print(f"cert pem     : {rel(CERT_FILE)} -> {cert_status}")
    for err in errors:
        print(f"warning      : {err}", file=sys.stderr)
    return 0 if not errors else 1


def cmd_cert_info(args: argparse.Namespace) -> int:
    status = 0
    for name in args.files:
        path = Path(name)
        problems: list[str] = []
        if path.read_bytes()[:2] == b"PK":
            try:
                der, problems = read_apk_cert(path)
            except ApkError as e:
                print(f"{name}: REJECTED APK: {e}")
                status = 1
                continue
        else:
            der = load_cert(path)
        size, digest = describe_cert(der)
        print(f"{name}:\n  CERT_SIZE=0x{size:04x} ({size} bytes)\n  CERT_SHA256={digest}")
        for problem in problems:
            print(f"  PROBLEM: {problem}")
            status = 1
    return status


def cmd_verify_namespace(args: argparse.Namespace) -> int:
    errors: list[str] = []
    ns = args.namespace or read_one_safe(APP_GRADLE, NS_GRADLE_RE, 2, "namespace", errors)
    pkg = read_one_safe(APP_GRADLE, PKG_GRADLE_RE, 2, "applicationId", errors)
    if ns:
        errors.extend(verify_namespace(ns, pkg))
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1
    print(f"Namespace {ns} verified cleanly across Gradle, AIDL, Manifest, ProGuard, Java/Kotlin, and Rust JNI.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    errors: list[str] = []

    pkg = read_one_safe(APP_GRADLE, PKG_GRADLE_RE, 2, "applicationId", errors)
    ns = read_one_safe(APP_GRADLE, NS_GRADLE_RE, 2, "namespace", errors)

    if pkg and pkg == OFFICIAL_PACKAGE:
        errors.append(f"applicationId is still upstream {OFFICIAL_PACKAGE}")
    if ns and ns == OFFICIAL_NAMESPACE:
        errors.append(f"namespace is still upstream {OFFICIAL_NAMESPACE}")
    if pkg and ns and pkg == ns:
        errors.append(f"applicationId and namespace must stay decoupled (both {pkg!r})")

    if CERT_FILE.is_file():
        c_size, c_hash = describe_cert(load_cert(CERT_FILE))
        if c_size != EXPECTED_CERT_SIZE:
            errors.append(f"{rel(CERT_FILE)} DER size is 0x{c_size:04x}, expected 0x{EXPECTED_CERT_SIZE:04x}")
        if c_hash != EXPECTED_CERT_SHA256:
            errors.append(f"{rel(CERT_FILE)} sha256 is {c_hash}, expected {EXPECTED_CERT_SHA256}")
    else:
        errors.append(f"missing {rel(CERT_FILE)}")

    if ns:
        errors.extend(verify_namespace(ns, pkg))
    if pkg and ns:
        errors.extend(check_repo_rules(pkg, ns))

    for apk_name in args.apk:
        apk_path = Path(apk_name)
        if not apk_path.is_file():
            errors.append(f"missing APK: {apk_name}")
            continue
        try:
            der, problems = read_apk_cert(apk_path)
            a_size, a_hash = describe_cert(der)
            if a_size != EXPECTED_CERT_SIZE or a_hash != EXPECTED_CERT_SHA256:
                errors.append(
                    f"{apk_name}: APK cert mismatch (got size=0x{a_size:04x} sha256={a_hash}, "
                    f"expected 0x{EXPECTED_CERT_SIZE:04x} {EXPECTED_CERT_SHA256})"
                )
            for prob in problems:
                errors.append(f"{apk_name}: {prob}")
        except ApkError as e:
            errors.append(f"{apk_name}: {e}")
        if pkg and ns:
            check_apk_contents(apk_path, pkg, ns, errors)

    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        print(f"FAILED: {len(errors)} error(s).", file=sys.stderr)
        return 1

    apk_note = f" + {len(args.apk)} APK(s)" if args.apk else ""
    print(f"OK: ToolShear check passed (pkg={pkg}, ns={ns}, lib={JNI_LIB}, cert=0x{EXPECTED_CERT_SIZE:04x}{apk_note}).")
    return 0


def cmd_set_package(args: argparse.Namespace) -> int:
    pkg = args.package
    if not is_valid_id(pkg) or pkg == OFFICIAL_PACKAGE:
        raise SystemExit(f"error: invalid or upstream package {pkg!r}")
    text = read_text(APP_GRADLE)
    new_text, n = PKG_GRADLE_RE.subn(rf"\g<1>{pkg}\g<3>", text)
    if n != 1:
        raise SystemExit(f"error: expected 1 applicationId match in {rel(APP_GRADLE)}, found {n}")
    write_text(APP_GRADLE, new_text)
    print(f"updated {rel(APP_GRADLE)} applicationId -> {pkg}")
    return 0


def cmd_set_namespace(args: argparse.Namespace) -> int:
    ns = args.namespace
    if not is_valid_id(ns) or ns == OFFICIAL_NAMESPACE:
        raise SystemExit(f"error: invalid or upstream namespace {ns!r}")
    errors: list[str] = []
    cur = read_one_safe(APP_GRADLE, NS_GRADLE_RE, 2, "namespace", errors)
    if not cur:
        raise SystemExit("\n".join(errors))
    if cur == ns:
        print(f"namespace is already {ns}")
        return 0
    cur_slash = cur.replace(".", "/")
    ns_slash = ns.replace(".", "/")
    cur_under = cur.replace(".", "_")
    ns_under = ns.replace(".", "_")

    for base in (JAVA_ROOT, AIDL_ROOT):
        old_dir = base.joinpath(*cur.split("."))
        new_dir = base.joinpath(*ns.split("."))
        if old_dir.exists():
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_dir), str(new_dir))
            remove_empty_parents(old_dir.parent, base)

    for root in (JAVA_ROOT, AIDL_ROOT, NATIVE_DIR / "src"):
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            try:
                t = o = read_text(p)
            except UnicodeDecodeError:
                continue
            t = t.replace(cur, ns).replace(cur_slash, ns_slash).replace(f"Java_{cur_under}_", f"Java_{ns_under}_")
            if t != o:
                write_text(p, t)

    for p in (APP_GRADLE, MANIFEST, PROGUARD, PROGUARD_MIN):
        if p.is_file():
            t = o = read_text(p)
            t = t.replace(cur, ns)
            if t != o:
                write_text(p, t)

    print(f"updated namespace {cur} -> {ns}")
    return 0


def cmd_set_cert(args: argparse.Namespace) -> int:
    der = load_cert(Path(args.cert))
    size, digest = describe_cert(der)
    write_text(CERT_FILE, Path(args.cert).read_text(encoding="utf-8") if b"BEGIN CERTIFICATE" in Path(args.cert).read_bytes() else read_text(CERT_FILE))
    print(f"CERT_SIZE=0x{size:04x} ({size} bytes) CERT_SHA256={digest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ToolShear DIY helper and consistency checker")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="show current identity, lib, and cert pin")

    ci = sub.add_parser("cert-info", help="inspect PEM/DER cert or APK v2 signature")
    ci.add_argument("files", nargs="+")

    vn = sub.add_parser("verify-namespace", help="verify namespace and JNI wiring")
    vn.add_argument("--namespace")

    ck = sub.add_parser("check", help="run all DIY consistency and leak-guard checks")
    ck.add_argument("--apk", nargs="*", default=[], help="signed APK path(s) to inspect")

    sub.add_parser("migrate", help="one-shot migration from upstream Strata to ToolShear")

    sp = sub.add_parser("set-package", help="update applicationId in app/build.gradle.kts")
    sp.add_argument("package")

    sn = sub.add_parser("set-namespace", help="rename internal Kotlin/Java/AIDL/Rust namespace")
    sn.add_argument("namespace")

    sc = sub.add_parser("set-cert", help="print/pin public certificate summary")
    sc.add_argument("cert")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {
        "info": cmd_info,
        "cert-info": cmd_cert_info,
        "verify-namespace": cmd_verify_namespace,
        "check": cmd_check,
        "migrate": cmd_migrate,
        "set-package": cmd_set_package,
        "set-namespace": cmd_set_namespace,
        "set-cert": cmd_set_cert,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
