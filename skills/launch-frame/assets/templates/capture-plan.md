<!-- LaunchFrame template: capture-plan.md. Fill before capturing; update Status as you go. -->
# Capture plan — {{App name}} {{release}}

Environment: {{from check_env.py, e.g. Windows host; emulators Reflux_Phone, Reflux_TV; no macOS}}
App build: {{variant and how it was installed, e.g. debug build already installed, versionName 1.2.0-debug}}
Demo data: {{source of content and its rights, e.g. Blender open movies on a local Jellyfin test server}}

| # | Target | Screen / feature | How to reach it | Device | Data/state needed | Status |
|---|---|---|---|---|---|---|
| 1 | {{google-play/phone}} | {{Home, Continue Watching}} | {{launch; wait text "Continue Watching"}} | {{emulator Reflux_Phone 1080x2400}} | {{2 titles partly watched}} | {{planned}} |

Status values: planned · captured · failed (reason) · skipped (reason) · existing (path) · provided-by-user

## Blockers and fallbacks
- {{e.g. Apple targets: host is Windows; using none. iPhone set not produced.}}

## Restore
- {{e.g. capture_android.py restore --serial emulator-5554; emulator stopped}}
