"""Synthetic fixture repositories for LaunchFrame tests and scenario evals.

Every fixture is TEST DATA: minimal files that exercise discovery and workflow decisions.
Images are flat placeholders labelled "TEST DATA"; they are not app UI and never store assets.

    from fixtures import build
    path = build("phone-tv", tmpdir)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

APP_GRADLE = """plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "com.example.fixture"
    defaultConfig { applicationId = "com.example.fixture" }
    buildTypes {
        release { isMinifyEnabled = true }
        debug { }
    }
%s
}
dependencies {
%s
}
"""
ROOT_GRADLE = 'plugins {\n    id("com.android.application") apply false\n}\n'
LIB_GRADLE = 'plugins { id("com.android.library") }\nandroid { namespace = "com.example.tvlib" }\n' \
             'dependencies { implementation("androidx.leanback:leanback:1.0.0") }\n'


def manifest(launcher=True, leanback_launcher=False, leanback_feature=None, extra=""):
    feats = ""
    if leanback_feature is not None:
        feats += f'    <uses-feature android:name="android.software.leanback" android:required="{leanback_feature}"/>\n'
    if leanback_launcher:
        feats += '    <uses-feature android:name="android.hardware.touchscreen" android:required="false"/>\n'
    cats = []
    if launcher:
        cats.append('<category android:name="android.intent.category.LAUNCHER"/>')
    if leanback_launcher:
        cats.append('<category android:name="android.intent.category.LEANBACK_LAUNCHER"/>')
    banner = ' android:banner="@drawable/tv_banner"' if leanback_launcher else ""
    return f"""<manifest xmlns:android="http://schemas.android.com/apk/res/android">
{feats}    <application android:label="Fixture"{banner}>
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                {' '.join(cats)}
            </intent-filter>
            <intent-filter>
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data android:scheme="fixture" android:host="open"/>
            </intent-filter>
        </activity>
{extra}    </application>
</manifest>
"""


def w(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def img(root: Path, rel: str, size, color=(30, 30, 34), label="TEST DATA"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", size, color)
    ImageDraw.Draw(im).text((20, 20), label, fill=(240, 240, 240))
    im.save(p)


def android_app(root: Path, man: str, deps: str = "", android_extra: str = "", readme: str = "Fixture app."):
    w(root, "settings.gradle.kts", 'include(":app")\n')
    w(root, "build.gradle.kts", ROOT_GRADLE)
    w(root, "gradlew", "#!/bin/sh\necho fixture\n")
    w(root, "app/build.gradle.kts", APP_GRADLE % (android_extra, deps))
    w(root, "app/src/main/AndroidManifest.xml", man)
    w(root, "app/src/main/res/values/colors.xml",
      '<resources><color name="brand_primary">#1F6F5C</color><color name="surface">#F7F5F0</color></resources>')
    w(root, "README.md", f"# Fixture (TEST DATA)\n\n{readme}\n")


def pbxproj(family: str, sdk="iphoneos", bundle="com.example.fixture", extra_blocks=""):
    return f"""// !$*UTF8*$!
{{
  objects = {{
    A1 = {{ isa = XCBuildConfiguration; buildSettings = {{
        PRODUCT_BUNDLE_IDENTIFIER = {bundle};
        SDKROOT = {sdk};
        TARGETED_DEVICE_FAMILY = "{family}";
    }}; name = Debug; }};
    A2 = {{ isa = XCBuildConfiguration; buildSettings = {{
        PRODUCT_BUNDLE_IDENTIFIER = {bundle}.UITests;
        SDKROOT = {sdk};
    }}; name = Debug; }};
{extra_blocks}  }};
}}
"""


def build(name: str, root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if name == "phone-only":
        android_app(root, manifest(), readme="A habit tracker for Android phones.")
    elif name == "phone-tablet":
        android_app(root, manifest(), readme="Notes app for phones and tablets.")
        w(root, "app/src/main/res/layout-sw600dp/activity_main.xml", "<LinearLayout/>")
    elif name == "tv-only":
        android_app(root, manifest(launcher=False, leanback_launcher=True, leanback_feature="true"),
                    readme="A 10-foot player for Android TV only.")
    elif name == "phone-tv":
        android_app(root, manifest(leanback_launcher=True, leanback_feature="false"),
                    deps='    implementation("androidx.tv:tv-material:1.0.0")',
                    readme="Media player for phones and Android TV.")
    elif name == "phone-tv-amazon":
        android_app(root, manifest(leanback_launcher=True, leanback_feature="false"),
                    android_extra='    flavorDimensions += "store"\n    productFlavors {\n'
                                  '        create("play") { dimension = "store" }\n'
                                  '        create("amazon") { dimension = "store" }\n    }',
                    readme="Media player for phones, Android TV and Fire TV. Published on Google Play and the "
                           "Amazon Appstore.")
    elif name == "cross-platform":
        w(root, "pubspec.yaml", "name: fixture\nflutter:\n  uses-material-design: true\n")
        (root / "web").mkdir(parents=True, exist_ok=True)
        w(root, "web/index.html", "<html></html>")
        android_app(root / "android", manifest())
        w(root, "ios/Runner.xcodeproj/project.pbxproj", pbxproj("1,2"))
        w(root, "README.md", "# Fixture (TEST DATA)\n\nFlutter app for Android, iOS and web.\n")
    elif name == "misleading-keywords":
        android_app(root, manifest(), readme="Phone app. We might support Android TV, Wear OS and tablets "
                                             "someday; Chromebook too.")
        w(root, "settings.gradle.kts", 'include(":app", ":tvlib")\n')
        w(root, "tvlib/build.gradle.kts", LIB_GRADLE)
        w(root, "tvlib/src/main/AndroidManifest.xml",
          '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
          '<uses-feature android:name="android.software.leanback" android:required="false"/></manifest>')
        w(root, "website/package.json", '{"scripts": {"build": "vite build"}, "dependencies": {"vite": "5"}}')
    elif name == "existing-automation":
        android_app(root, manifest(), deps='    testImplementation("io.github.takahirom.roborazzi:roborazzi:1.0.0")')
        w(root, ".maestro/screenshots.yaml", "appId: com.example.fixture\n---\n- launchApp\n- takeScreenshot: home\n")
        img(root, "fastlane/metadata/android/en-US/images/phoneScreenshots/1.png", (1080, 2400))
    elif name == "apple-only":
        w(root, "Fixture.xcodeproj/project.pbxproj", pbxproj("1"))
        w(root, "README.md", "# Fixture (TEST DATA)\n\niPhone app.\n")
    elif name == "apple-tv":
        w(root, "Fixture.xcodeproj/project.pbxproj", pbxproj("1,2") + pbxproj("3", sdk="appletvos",
                                                                                 bundle="com.example.fixture.tv"))
    elif name == "login-required":
        android_app(root, manifest(), readme="Team chat. Requires an account on your company server.")
        w(root, "app/src/main/java/com/example/fixture/LoginScreen.kt", "fun LoginScreen() { /* sign in */ }")
        w(root, "app/src/main/res/values/strings.xml",
          '<resources><string name="sign_in">Sign in</string><string name="server_url">Server URL</string>'
          '</resources>')
    elif name == "limited-captures":
        android_app(root, manifest())
        img(root, "docs/screenshots/home.png", (1080, 2400), (20, 60, 50))
        img(root, "docs/screenshots/detail.png", (1080, 2400), (20, 50, 60))
    elif name == "broken-build":
        android_app(root, manifest())
        w(root, "app/build.gradle.kts", APP_GRADLE % ("", "") + "\nthis is not valid kotlin {{{\n")
        err = ("FAILURE: Build failed with an exception.\n* Where: Build file 'app/build.gradle.kts' line: 17\n"
               "* What went wrong: Script compilation error: Expecting an element\n")
        w(root, "gradlew", "#!/bin/sh\ncat >&2 <<'EOF'\n" + err + "EOF\nexit 1\n")
        w(root, "gradlew.bat", "@echo off\r\n" + "".join(f"echo {ln} 1>&2\r\n" for ln in err.strip().splitlines())
          + "exit /b 1\r\n")
    elif name == "prior-release":
        android_app(root, manifest())
        w(root, "store-assets/release-1.0.0/README.md", "# Fixture 1.0.0 store assets (TEST DATA)\n\nStatus: uploaded.\n")
        img(root, "store-assets/release-1.0.0/google-play/phone/01.png", (1080, 1920))
    elif name == "unusual-brand":
        android_app(root, manifest(), readme="A recipe journal with a warm editorial feel.")
        w(root, "app/src/main/java/com/example/fixture/ui/theme/Color.kt",
          "val Terracotta = Color(0xFFE85D3A)\nval Parchment = Color(0xFFF4EBDD)\nval Ink = Color(0xFF2B2118)\n")
        w(root, "app/src/main/java/com/example/fixture/ui/theme/Type.kt",
          "val Display = FontFamily(Font(R.font.fraunces_bold))\nval Body = FontFamily(Font(R.font.work_sans))\n")
        w(root, "app/src/main/res/font/README.txt", "Fraunces (OFL) and Work Sans (OFL) go here.\n")
    elif name == "empty-state":
        android_app(root, manifest(), readme="Podcast player. The library is empty until you subscribe to a feed.")
        img(root, "docs/screenshots/library.png", (1080, 2400), (12, 12, 12), "TEST DATA - empty library")
    else:
        raise KeyError(f"unknown fixture {name}")
    return root


NAMES = ["phone-only", "phone-tablet", "tv-only", "phone-tv", "phone-tv-amazon", "cross-platform",
         "misleading-keywords", "existing-automation", "apple-only", "apple-tv", "login-required",
         "limited-captures", "broken-build", "prior-release", "unusual-brand", "empty-state"]
