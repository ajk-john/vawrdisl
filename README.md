# ToolShear

**ToolShear** is an open-source dual-pane file manager and power-user toolkit for Android with built-in ROOT / Shell script execution.

## Features

- **Files**: dual panes side by side, drag and drop onto folders, Root and Shizuku access, recycle bin, search by name or content, batch rename, bookmarks, permissions, links, split and merge, file encryption
- **Root / Shell Script Runner**: run `.sh` scripts directly inside the app with ROOT (`su`) or standard `/system/bin/sh`, optional CLI arguments, and live scrollable console output — no external Termux required
- **Archives**: open and extract ZIP, 7z, RAR, TAR, GZ, XZ, ZST and more; create ZIP, 7z and TAR archives with passwords
- **APK tools**: app details, split APK install, signing (v1 to v3) and signing keys, clone with a new name and icon, DEX and smali editor, Java decompiler, manifest and resource editors
- **Editors and viewers**: code editor with syntax highlighting, hex editor, PDF reader, image viewer, music and video player, font viewer, Markdown preview, 9-patch editor, color picker
- **Network**: FTP, SFTP, SMB and WebDAV right in the panes, plus Wi-Fi sharing with an FTP server or a file manager in the browser
- **Privacy**: an encrypted vault opened with your fingerprint, app lock, and nothing that leaves your device unless you send it
- **Languages**: English, Persian (RTL), Russian, and Simplified Chinese

## Building

You need the Android SDK with an NDK, and Rust with the Android targets and `cargo-ndk`. JDK 17 is configured automatically.

```bash
rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android
cargo install cargo-ndk
native/fetch-pdfium.sh
native/build.sh
python3 diy/toolshear_diy.py check
./gradlew :app:assembleRelease -Ptoolshear.splitApks=true
```

## License

ToolShear is licensed under the [GNU AGPL v3.0 or later](LICENSE). Third-party components keep their own licenses; they are listed in the app under **Settings → About**.
