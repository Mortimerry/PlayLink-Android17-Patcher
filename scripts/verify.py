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

from profiles import PROFILES

BUILD_TOOLS = "36.0.0"
SOURCE_STAMP = "stamp-cert-sha256"


def digest(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()


def check_source(path):
    with path.open("rb") as source:
        actual = digest(source)
    if actual not in PROFILES:
        raise ValueError(f"Unsupported input APK (SHA-256: {actual}). See README for supported releases.")
    return PROFILES[actual]


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
    profile = check_source(source)
    expected_patches = {"classes.dex": profile.dex_hash, "AndroidManifest.xml": profile.manifest_hash}
    subprocess.run([*apksigner(tools), "verify", "--verbose", "--print-certs", candidate], check=True)
    subprocess.run([zipalign(tools), "-c", "-P", "16", "4", candidate], check=True)
    with ZipFile(source) as original, ZipFile(candidate) as patched:
        names = payload(original)
        # A rebuilt APK cannot retain the original distributor's source stamp.
        names.discard(SOURCE_STAMP)
        if names != payload(patched):
            raise ValueError("APK payload file list differs")
        for name in sorted(names):
            if original.getinfo(name).compress_type != patched.getinfo(name).compress_type:
                raise ValueError(f"Compression method differs: {name}")
            if name in expected_patches:
                expected = expected_patches[name]
            else:
                with original.open(name) as entry:
                    expected = digest(entry)
            with patched.open(name) as entry:
                if digest(entry) != expected:
                    raise ValueError(f"Unexpected contents: {name}")
    print(f"OK: signature, ZIP alignment, {len(expected_patches)} patched entries and "
          f"{len(names) - len(expected_patches)} original entries verified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Original supported PlayLink APK")
    parser.add_argument("--apk", type=Path, required=True, help="Signed patched APK")
    parser.add_argument("--sdk", help="Android SDK directory (default: ANDROID_HOME)")
    args = parser.parse_args()
    verify(args.input, args.apk, sdk_tools(args.sdk))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, BadZipFile, subprocess.CalledProcessError) as exc:
        sys.exit(f"Verification failed: {exc}")
