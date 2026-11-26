"""Build the three compatibility fixes from source and sign with your own key."""
import argparse
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

from manifest import remove_aspect_limit
from verify import SOURCE_STAMP, apksigner, check_source, digest, is_signature, jdk, sdk_tools, verify, zipalign

ROOT = Path(__file__).resolve().parents[1]
MAVEN = "https://repo.maven.apache.org/maven2/"
DEPENDENCIES = {
    "org/smali/dexlib2/2.5.2/dexlib2-2.5.2.jar":
        "5a5c8982d8bd7d6e3bb1a0713049e3c78b719ec32b20f6b619885cec30a0dd61",
    "com/google/guava/guava/32.1.3-jre/guava-32.1.3-jre.jar":
        "6d4e2b5a118aab62e6e5e29d185a0224eed82c85c40ac3d33cf04a270c3b3744",
}
STAGES = [
    ("service", "bitter.jnibridge.ServiceConnectionCompat"),
    ("allocator", "pl.kip.compat.AllocatorLaunch"),
    ("display", "pl.kip.compat.CutoutLayout"),
]


def dependencies(cache):
    cache.mkdir(parents=True, exist_ok=True)
    jars = []
    for url_path, expected in DEPENDENCIES.items():
        target = cache / Path(url_path).name
        if not target.exists():
            with tempfile.TemporaryDirectory(dir=cache) as folder:
                download = Path(folder) / target.name
                with urlopen(MAVEN + url_path, timeout=60) as remote, download.open("wb") as out:
                    shutil.copyfileobj(remote, out)
                with download.open("rb") as jar:
                    if digest(jar) != expected:
                        raise ValueError(f"Invalid download: {target.name}")
                download.replace(target)
        with target.open("rb") as jar:
            if digest(jar) != expected:
                raise ValueError(f"Dependency checksum mismatch. Replace the cached file: {target}")
        jars.append(str(target.resolve()))
    return os.pathsep.join(jars)


def patched_dex(work, original, tools, platform, jars, profile):
    rewriters = work / "rewriters"
    rewriters.mkdir()
    subprocess.run([jdk("javac"), "-cp", jars, "-d", rewriters, *sorted((ROOT / "tools").glob("*.java"))],
                   check=True)
    classpath = os.pathsep.join([str(rewriters), jars])
    current = work / "original.dex"
    current.write_bytes(original)
    for stage, qualified in STAGES:
        folder = work / stage
        classes = folder / "classes"
        helper = folder / "helper"
        classes.mkdir(parents=True)
        helper.mkdir()
        simple = qualified.split(".")[-1]
        inputs = [ROOT / "src" / stage / (simple + ".java")]
        d8_options = []
        if stage == "service":
            inputs.append(ROOT / "compileonly" / "JNIBridge.java")
            d8_options = ["--classpath", classes]
        subprocess.run([jdk("javac"), "--release", "8", "-Xlint:-options", "-classpath", platform,
                        "-d", classes, *inputs], check=True)
        compiled = classes / (qualified.replace(".", "/") + ".class")
        subprocess.run([jdk("java"), "-cp", tools / "lib" / "d8.jar", "com.android.tools.r8.D8",
                        "--release", "--min-api", "21", "--lib", platform, *d8_options,
                        "--output", helper, compiled], check=True)
        current.replace(folder / "classes.dex")
        entry = ["BuildDex"] if stage == "service" else ["PatchStartup", stage, profile.activity]
        subprocess.run([jdk("java"), "-cp", classpath, *entry], cwd=folder, check=True)
        current = folder / "fixed.dex"
    return current.read_bytes()


def build(args):
    source = args.input.resolve()
    output = args.output.resolve()
    profile = check_source(source)
    print(f"Building {profile.title}", flush=True)
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    if not args.keystore.is_file():
        raise ValueError("Signing keystore not found")
    tools = sdk_tools(args.sdk)
    platforms = tools.parents[1] / "platforms"
    platform = next((platforms / name / "android.jar" for name in ("android-37.0", "android-37")
                     if (platforms / name / "android.jar").is_file()), None)
    if platform is None:
        raise ValueError("Install Android SDK Platform 37")
    jars = dependencies(args.cache)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kip-build-") as tmp:
        work = Path(tmp)
        unsigned, aligned, signed = (work / f"{stage}.apk" for stage in ("unsigned", "aligned", "signed"))
        with ZipFile(source) as original:
            replacements = {
                "AndroidManifest.xml": remove_aspect_limit(original.read("AndroidManifest.xml"), profile),
                "classes.dex": patched_dex(work, original.read("classes.dex"), tools, platform, jars, profile),
            }
            with ZipFile(unsigned, "x") as archive:
                for info in original.infolist():
                    if is_signature(info.filename) or info.filename == SOURCE_STAMP:
                        continue
                    data = replacements.get(info.filename)
                    archive.writestr(copy.copy(info), original.read(info) if data is None else data)
        subprocess.run([zipalign(tools), "-P", "16", "4", unsigned, aligned], check=True)
        signing = [*apksigner(tools), "sign", "--ks", args.keystore, "--ks-key-alias", args.alias,
                   "--v4-signing-enabled", "false"]
        if "KIP_STORE_PASSWORD" in os.environ:
            signing += ["--ks-pass", "env:KIP_STORE_PASSWORD"]
        subprocess.run([*signing, "--out", signed, aligned], check=True)
        verify(source, signed, tools)
        with signed.open("rb") as result, output.open("xb") as out:
            try:
                shutil.copyfileobj(result, out)
                out.flush()
            except BaseException:
                out.close()
                output.unlink()
                raise
    print(f"Verified APK written to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keystore", type=Path, required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--sdk", help="Android SDK directory (default: ANDROID_HOME)")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "kip-patcher",
                        help="Directory containing the two pinned Maven dependencies")
    build(parser.parse_args())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, BadZipFile, subprocess.CalledProcessError) as exc:
        sys.exit(f"Build failed: {exc}")
