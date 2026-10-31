# -*- coding: utf-8 -*-
"""
把 WebView 壳打成 APK —— 不走 Gradle，直接调用 build-tools 里的官方工具链：

    aapt2 compile  ->  aapt2 link  ->  javac  ->  d8  ->  塞 dex  ->  zipalign  ->  apksigner

好处是零 Maven 依赖、几秒出包；代价是要自己管 R.java 和 dex 合并。
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app")
TOOLS = os.path.normpath(os.path.join(ROOT, "..", "tools"))
JDK = os.path.join(TOOLS, "jdk-17.0.20.1+1")
SDK = os.path.join(TOOLS, "android-sdk")
BT = os.path.join(SDK, "build-tools", "34.0.0")
ANDROID_JAR = os.path.join(SDK, "platforms", "android-34", "android.jar")

BUILD = os.path.join(ROOT, "build")
OUT_APK = os.path.join(ROOT, "..", "新能源车价计算器.apk")

PKG = "com.nev.pricecalc"
MIN_SDK = "24"
KEYSTORE = os.path.join(ROOT, "debug.keystore")

ENV = dict(os.environ)
ENV["JAVA_HOME"] = JDK
ENV["PATH"] = os.path.join(JDK, "bin") + os.pathsep + ENV.get("PATH", "")


def run(cmd, what, cwd=None):
    print("[%s]" % what, flush=True)
    p = subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True)
    out = (p.stdout or b"").decode("utf-8", "ignore")
    err = (p.stderr or b"").decode("utf-8", "ignore")
    if out.strip():
        print(out.strip()[-1500:])
    if p.returncode != 0:
        print(err.strip()[-3000:])
        sys.exit("[FAIL] %s (exit %d)" % (what, p.returncode))
    if err.strip() and "warning" not in err.lower():
        print(err.strip()[-800:])
    return out


def tool(name):
    p = os.path.join(BT, name)
    if not os.path.exists(p):
        sys.exit("缺少工具: " + p)
    return p


def clean():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD, ignore_errors=True)
    for d in ("compiled", "gen", "classes", "dex"):
        os.makedirs(os.path.join(BUILD, d), exist_ok=True)


def make_keystore():
    if os.path.exists(KEYSTORE):
        print("[keystore] 复用已有 debug.keystore")
        return
    run([os.path.join(JDK, "bin", "keytool.exe"), "-genkeypair", "-v",
         "-keystore", KEYSTORE, "-storepass", "android", "-keypass", "android",
         "-alias", "androiddebugkey", "-keyalg", "RSA", "-keysize", "2048",
         "-validity", "10000", "-dname", "CN=Android Debug,O=Android,C=US"],
        "keytool")


def build():
    clean()

    # 0) 每次都从项目根目录同步最新页面，避免 apk 用到旧 HTML
    src_html = os.path.normpath(os.path.join(ROOT, "..", "车价计算器.html"))
    dst_html = os.path.join(APP, "assets", "index.html")
    if os.path.exists(src_html):
        shutil.copy2(src_html, dst_html)
        print("[sync] 车价计算器.html -> assets/index.html (%.1f KB)"
              % (os.path.getsize(dst_html) / 1024))

    apk_unsigned = os.path.join(BUILD, "unsigned.apk")
    apk_dexed = os.path.join(BUILD, "dexed.apk")
    apk_aligned = os.path.join(BUILD, "aligned.apk")

    # 1) 编译资源 -> flat
    compiled = os.path.join(BUILD, "res.zip")
    run([tool("aapt2.exe"), "compile", "--dir", os.path.join(APP, "res"),
         "-o", compiled], "aapt2 compile")

    # 2) 链接资源 + 生成 R.java，同时把 assets 打进去
    gen_dir = os.path.join(BUILD, "gen")
    run([tool("aapt2.exe"), "link",
         "-o", apk_unsigned,
         "-I", ANDROID_JAR,
         "--manifest", os.path.join(APP, "AndroidManifest.xml"),
         "-A", os.path.join(APP, "assets"),
         "--java", gen_dir,
         "--min-sdk-version", MIN_SDK,
         "--target-sdk-version", "34",
         "--auto-add-overlay",
         compiled], "aapt2 link")

    # 3) 编译 Java（R.java + 业务代码）
    sources = []
    for base in (gen_dir, os.path.join(APP, "src")):
        for dirpath, _, files in os.walk(base):
            for f in files:
                if f.endswith(".java"):
                    sources.append(os.path.join(dirpath, f))
    if not sources:
        sys.exit("没有找到 Java 源码")
    print("[javac] %d 个源文件" % len(sources))
    classes = os.path.join(BUILD, "classes")
    run([os.path.join(JDK, "bin", "javac.exe"),
         "-encoding", "UTF-8",
         "-source", "8", "-target", "8", "-nowarn",
         "-classpath", ANDROID_JAR,
         "-d", classes] + sources, "javac")

    # 4) class -> dex
    class_files = []
    for dirpath, _, files in os.walk(classes):
        for f in files:
            if f.endswith(".class"):
                class_files.append(os.path.join(dirpath, f))
    dex_dir = os.path.join(BUILD, "dex")
    run([tool("d8.bat"), "--lib", ANDROID_JAR, "--min-api", MIN_SDK,
         "--output", dex_dir] + class_files, "d8")
    dex = os.path.join(dex_dir, "classes.dex")
    if not os.path.exists(dex):
        sys.exit("d8 未产出 classes.dex")

    # 5) 把 dex 并入 apk
    shutil.copy2(apk_unsigned, apk_dexed)
    with zipfile.ZipFile(apk_dexed, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(dex, "classes.dex")
    print("[merge] classes.dex -> apk (%.1f KB)" % (os.path.getsize(dex) / 1024))

    # 6) 对齐 + 签名
    run([tool("zipalign.exe"), "-f", "-p", "4", apk_dexed, apk_aligned], "zipalign")
    make_keystore()
    if os.path.exists(OUT_APK):
        os.remove(OUT_APK)
    run([tool("apksigner.bat"), "sign",
         "--ks", KEYSTORE, "--ks-pass", "pass:android", "--key-pass", "pass:android",
         "--min-sdk-version", MIN_SDK,
         "--out", OUT_APK, apk_aligned], "apksigner")
    run([tool("apksigner.bat"), "verify", "--verbose", "--print-certs", OUT_APK], "apksigner verify")
    print("\n[OK] %s  %.2f MB" % (OUT_APK, os.path.getsize(OUT_APK) / 1024 / 1024))


if __name__ == "__main__":
    build()
