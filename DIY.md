# ToolShear DIY Guide

This repository contains the customized **ToolShear** build (AGPL-3.0) with isolated Android identity, custom native library naming, and built-in ROOT / Shell `.sh` script execution.

## Identity & Signing Pin

| Property | Value |
|---|---|
| App name | `ToolShear` (PR builds: `ToolShear PR`) |
| `applicationId` | `com.kxwphnruvde.tqymsfobg` (PR suffix: `.pr`) |
| Code / JNI / AIDL namespace | `io.vngkzxq.mprt` |
| Native Rust JNI library | `libhvzqck.so` (`hvzqck`) |
| Signing certificate pin | `diy/manager-cert.pem` (`0x0317` bytes, SHA-256 `94dc8bf3d10ca39999b9bcdf688642705edc8ea2aeb47e6feef33d6ca65afc6c`) |

Run `python diy/toolshear_diy.py info` at any time to inspect the live configuration.

## Root / Shell `.sh` Script Execution

ToolShear provides an in-app **Script Runner** (`core/root/ScriptExecutor.kt` + `feature/script/ScriptRunnerDialog.kt`) accessible from three entry points:

1. **Tap / Default Opener**: `.sh` files default to `Opener.SCRIPT_RUNNER` (while `TEXT_EDITOR` remains available via **Open with…**).
2. **Item Action Sheet**: Long-press action sheet exposes **Run script** (`SheetAction.RUN_SCRIPT`) for local `.sh` files.
3. **Text Editor**: Opening a `.sh` or `source.shell` file enables the top-bar **Play** button, auto-saving unsaved edits before launching `ScriptRunnerDialog`.

Features:
- Toggles between **ROOT (`su`)** (calling `RootManager.request()`) and standard **`/system/bin/sh`**.
- Supports optional CLI arguments, injects root manager/system `PATH` + `SCRIPT_FILE` + `SCRIPT_DIR`, strips CRLF safely via temporary staging, and streams merged stdout/stderr live with a Stop button and output copy.

## Repository Rules & CI

- **Never commit** `.diy-secrets/`, `*.jks`, `*.p12`, `*.pfx`, `*.keystore`, or `keystore.properties`.
- **Line endings**: keep `core.autocrlf = false`, `core.eol = lf`; `.sh` scripts, hooks, Gradle files, workflows, and docs must stay LF (`\n`).
- **Pre-commit check**: `.githooks/pre-commit` validates staged paths/diffs and runs `python diy/toolshear_diy.py check`.
- **GitHub Actions CI**: `.github/workflows/build.yml` verifies `diy/toolshear_diy.py check`, builds native core (`cargo-ndk` + PDFium), compiles debug & split release APKs, re-signs with Android SDK `apksigner` (v1 + v2 only), verifies APKs with `diy/toolshear_diy.py check --apk`, and uploads workflow artifacts (`toolshear-release`, `toolshear-debug`, `mappings`) without creating GitHub Releases or tags.
- **Fetching artifacts**: run `python diy/fetch_builds.py` to download and verify CI artifacts into local gitignored `builds/`.
