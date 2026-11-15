# ToolShear DIY Handoff

## Identity & Signing Summary

- **App Name**: `ToolShear` (`ToolShear PR` on PR builds)
- **`applicationId`**: `com.kxwphnruvde.tqymsfobg` (`.pr` suffix on PR builds)
- **Code / JNI Namespace**: `io.vngkzxq.mprt`
- **Rust JNI Library**: `libhvzqck.so` (`native/Cargo.toml` -> `name = "hvzqck"`)
- **Public Signing Cert**: `diy/manager-cert.pem` (`0x0317` / 791 bytes, SHA-256 `94dc8bf3d10ca39999b9bcdf688642705edc8ea2aeb47e6feef33d6ca65afc6c`)
- **Upstream Base Commit**: `07d9974` (`upstream` remote only, no upstream tags)

## GitHub Repository & Branch Protection

- **Repository**: _pending creation in Step 6_
- **Branch Protection Ruleset**: _pending creation in Step 6_

## Build & Artifact Log

| Date | Event / Run | Result | Notes |
|---|---|---|---|
| 2026-11-15 | Initial DIY migration & native ROOT `.sh` runner implementation | Pending push & CI | Rebranded codebase, removed donation wallets/support card, added `ScriptExecutor.kt` + `ScriptRunnerDialog.kt` across Opener/Sheet/Editor |
