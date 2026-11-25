"""Verify a patched APK against the original APK and the reference hashes."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zipfile import BadZipFile, ZipFile

SOURCE_HASH = "b8382fe09858b5eabf953322ecefd0485db67c15c8e283ef083b89fc0e15892d"
PATCHED = {
    "classes.dex": "549cd6d391941b0b0d8a8689e7a7018b2cb5a3aa058750d829d4d4e37f69b414",
    "AndroidManifest.xml": "3260ccb14ad984a150e7fef2469d18f3c57e5a540a98b869c9c546e7422b5dd3",
}
BUILD_TOOLS = "36.0.0"


def digest(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()


def check_source(path):
    with path.open("rb") as source:
        actual = digest(source)
    if actual != SOURCE_HASH:
        raise ValueError(f"Unsupported input APK. Expected {SOURCE_HASH}, got {actual}")


def sdk_tools(sdk):
    location = sdk or os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
    if not location:
        raise ValueError("Set ANDROID_HOME or pass --sdk")
    return Path(location).expanduser().resolve() / "build-tools" / BUILD_TOOLS


def jdk(tool):
    if os.getenv("JAVA_HOME"):
        suffix = ".exe" if os.name == "nt" else ""
        return str(Path(os.environ["JAVA_HOME"]) / "bin" / (tool + suffix))
    found = shutil.which(tool)
    if not found:
        raise ValueError(f"Missing {tool} on PATH. Install JDK 21 or set JAVA_HOME")
    return found


def zipalign(tools):
    return tools / ("zipalign.exe" if os.name == "nt" else "zipalign")


def apksigner(tools):
    return [jdk("java"), "-jar", tools / "lib" / "apksigner.jar"]


def is_signature(name):
    return name == "META-INF/MANIFEST.MF" or bool(
        re.fullmatch(r"META-INF/[A-Za-z0-9_-]{1,8}\.(?:SF|RSA|DSA|EC)", name))


def payload(archive):
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("Duplicate ZIP entry")
    return {name for name in names if not is_signature(name)}


def verify(source, candidate, tools):
    check_source(source)
    subprocess.run([*apksigner(tools), "verify", "--verbose", "--print-certs", candidate], check=True)
    subprocess.run([zipalign(tools), "-c", "-P", "16", "4", candidate], check=True)
    with ZipFile(source) as original, ZipFile(candidate) as patched:
        names = payload(original)
        if names != payload(patched):
            raise ValueError("APK payload file list differs")
        for name in sorted(names):
            if original.getinfo(name).compress_type != patched.getinfo(name).compress_type:
                raise ValueError(f"Compression method differs: {name}")
            if name in PATCHED:
                expected = PATCHED[name]
            else:
                with original.open(name) as entry:
                    expected = digest(entry)
            with patched.open(name) as entry:
                if digest(entry) != expected:
                    raise ValueError(f"Unexpected contents: {name}")
    print(f"OK: signature, ZIP alignment, {len(PATCHED)} patched entries and "
          f"{len(names) - len(PATCHED)} original entries verified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Original APK 1.5")
    parser.add_argument("--apk", type=Path, required=True, help="Signed patched APK")
    parser.add_argument("--sdk", help="Android SDK directory (default: ANDROID_HOME)")
    args = parser.parse_args()
    verify(args.input, args.apk, sdk_tools(args.sdk))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, BadZipFile, subprocess.CalledProcessError) as exc:
        sys.exit(f"Verification failed: {exc}")
