# ToolShear DIY Handoff

## Identity & Signing Summary

- **App Name**: `ToolShear` (`ToolShear PR` on PR builds)
- **`applicationId`**: `com.kxwphnruvde.tqymsfobg` (`.pr` suffix on PR builds)
- **Code / JNI Namespace**: `io.vngkzxq.mprt`
- **Rust JNI Library**: `libhvzqck.so` (`native/Cargo.toml` -> `name = "hvzqck"`)
- **Public Signing Cert**: `diy/manager-cert.pem` (`0x0317` / 791 bytes, SHA-256 `94dc8bf3d10ca39999b9bcdf688642705edc8ea2aeb47e6feef33d6ca65afc6c`)
- **Upstream Base Commit**: `07d9974` (`upstream` remote only, no upstream tags)

## GitHub Repository & Branch Protection

- **Repository**: `https://github.com/ajk-john/vawrdisl` (public, default branch `main`)
- **Collaborators**: Only owner `ajk-john` (0 extra collaborators)
- **Branch Protection Ruleset**: `Protect main` (ID `27299319`, `enforcement: active`)
  - Target: `~DEFAULT_BRANCH` (`main`)
  - Rules: `Restrict deletions` (`deletion`), `Block force pushes` (`non_fast_forward`), `Require a pull request before merging` (`pull_request`, `required_approving_review_count = 1`)
  - Bypass list: `Repository admin` (`RepositoryRole`, `actor_id = 5`, `bypass_mode = always`)

## Build & Artifact Log

| Date | Event / Run | Result | Notes |
|---|---|---|---|
| 2026-11-15 | Run #1 (`43686958047`, `cfb58be`) | Failure | Fixed missing `buildFeatures { resValues = true }` for AGP 9.3.2 |
| 2026-11-15 | Run #2 (`43687238912`, `664cf87`) | Failure | Escaped `$` vars in `ScriptExecutor.kt`; imported `runBuild` in `ArscEditorViewModel.kt` to avoid `io` shadowing |
| 2026-11-15 | Run #3 (`43687881596`, `fbb8b0c`) | Failure | Native/Debug/Release/apksigner v2 passed; excluded generated `app/build` & `.cxx` from `toolshear_diy.py` scan |
| 2026-11-15 | Run #4 (`43688989893`, `9147547`) | Success | Full CI green (`https://github.com/ajk-john/vawrdisl/actions/runs/43688989893`); archived locally via `diy/fetch_builds.py` |

## Signed Release APK Digests (`builds/004-main-9147547-success/toolshear-release/`)

All 4 APKs passed `apksigner verify` (v2-only) and `python diy/toolshear_diy.py check --apk` (`cert=0x0317`, `94dc8bf3d10ca39999b9bcdf688642705edc8ea2aeb47e6feef33d6ca65afc6c`):

| File | Size (bytes) | SHA-256 |
|---|---|---|
| `ToolShear-v1.0.0-arm64-v8a.apk` | 30,197,917 | `8050b7085e4e69f97681e9365e8bb40a80492bf42a9074a39a28023fe3349f4f` |
| `ToolShear-v1.0.0-armeabi-v7a.apk` | 29,591,719 | `e49a61ef31cf39cc458d45f52a6ae1c39134f020d6b62d185a2787c2fe9bef02` |
| `ToolShear-v1.0.0-universal.apk` | 37,993,650 | `15cd902643cba6fb148b1f0f57b626c1ec43a451ba23121bcf34d63a62b48e56` |
| `ToolShear-v1.0.0-x86_64.apk` | 30,390,414 | `dc07bab372cae6560222c917dabdf741e86bae930905fd2be0435b79b3dcb63d` |
