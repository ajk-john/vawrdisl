# Agent Instructions for ToolShear

Read [`DIY.md`](DIY.md) and [`diy/HANDOFF.md`](diy/HANDOFF.md) before modifying files in this repository.

## Required Invariants

1. **Secrets isolation**: Never read, print, stage, or commit `.diy-secrets/`, `*.jks`, `*.p12`, `*.pfx`, `*.keystore`, or `keystore.properties`. Only `diy/manager-cert.pem` (public certificate) is tracked.
2. **Identity decoupling**: Keep `applicationId = "com.kxwphnruvde.tqymsfobg"`, `namespace = "io.vngkzxq.mprt"`, and Rust JNI library `hvzqck` (`libhvzqck.so`) distinct and consistent across Gradle, AIDL, Manifest, ProGuard, Rust `native/`, and Kotlin/Java sources.
3. **Verification gate**: Run `python diy/toolshear_diy.py check` before every commit and confirm exit code `0`. For built APKs, run `python diy/toolshear_diy.py check --apk <path>`.
4. **Line endings**: Keep shell scripts, hooks, YAML workflows, Python helpers, and Kotlin/Rust files in LF (`\n`). On Windows Git, ensure `.githooks/pre-commit` is active via `git config core.hooksPath .githooks`.
5. **No Releases/Tags**: Do not push tags or add `gh release create` to CI workflows; artifacts are archived locally via `python diy/fetch_builds.py`.
6. **Handoff hygiene**: Record repository metadata, CI run numbers, build conclusions, and APK SHA-256 digests in [`diy/HANDOFF.md`](diy/HANDOFF.md).
