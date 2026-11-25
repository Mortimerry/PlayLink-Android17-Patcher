# Knowledge is Power 1.5 on Android 17

Build the PS4 companion app from your own copy of the version 1.5 APK and sign it with your own key. This unofficial project provides the source code for three compatibility fixes, a build script, and a standalone verifier. Your APK supplies the game files.

The first two fixes address startup crashes. The third lets the game use the full width of the display in landscape. PS4 gameplay and compatibility with 16 KB memory pages remain unverified.

## What the patches change

| Fix | Symptom | Change |
|---|---|---|
| Android service connection | After the Sony logo, the older JNI bridge threw `NoSuchMethodError` when Android called the new overload of `onServiceConnected`. | The [service adapter](src/service/ServiceConnectionCompat.java) recognizes the specific three-argument signature and passes the first two arguments to the legacy method. The [DEX patch](tools/BuildDex.java) redirects one call to the adapter. |
| Unity memory allocator | During loading, the `UnityPreload` thread crashed with `SIGSEGV` after the allocator reported an address-range error. | In 64-bit processes on API 30 or later, the [startup code](src/allocator/AllocatorLaunch.java) passes `-debugallocator 0` before Unity starts. It preserves existing arguments and respects an explicit allocator setting. |
| Full-screen layout | In landscape, a black bar appeared along the edge with the front camera. | On API 28 or later, the [window configuration](src/display/CutoutLayout.java) lets the app draw in the display cutout area on a short edge. The [manifest patch](scripts/manifest.py) removes the game activity's 2.1 aspect ratio limit. |

The [startup patch](tools/PatchStartup.java) configures the allocator before Unity's `onCreate` runs and sets the window layout after it returns. Each of the three DEX patching stages reverses its edit on a copy, then compares the result with the input written by the same serializer. The [compile-time JNIBridge declaration](compileonly/JNIBridge.java) gives the compiler the signature of an existing method. Only the three new classes under `src` are added to the APK.

## Requirements

- Your own copy of the **single-file APK, version 1.5**, package `com.playstation.knowledge`, version code **10508**. The supported file has SHA-256 `b8382fe09858b5eabf953322ecefd0485db67c15c8e283ef083b89fc0e15892d`. The script checks this hash before applying any patches.
- Python **3.11 or later** and JDK **21**, including `java`, `javac`, and `keytool`.
- Android SDK **Build Tools 36.0.0** and **SDK Platform 37**. You can install both through Android Studio's SDK Manager. Set `ANDROID_HOME` to the SDK directory or pass `--sdk "path to SDK"` to the Python commands below. You can build without a Unity project or the Android NDK.
- On the first build, the script downloads **dexlib2 2.5.2** and **Guava 32.1.3-jre** from Maven Central. It checks both JARs against their pinned SHA-256 hashes on every build. The [build script](scripts/build.py) lists the download URLs and hashes. The default cache is `~/.cache/kip-patcher`. To build offline, use `--cache` to point to a directory containing both JARs. APK verification works offline.

## Build from your own APK

Run these PowerShell commands from the repository root. Create a directory next to the repository, then place your original APK in it as `original-1.5.apk`.

```powershell
New-Item -ItemType Directory -Force ../KiP-local | Out-Null
```

If you already have an app signing key, use its keystore path and alias in the build command below. To create a new key, run the following command once. Keep the keystore and its password for future updates.

```powershell
keytool -genkeypair -storetype PKCS12 -keystore "../KiP-local/my-key.p12" -alias kip -keyalg RSA -keysize 3072 -validity 3650
```

Build the APK with your key. The signing tool prompts for the password. For an automated build, you can supply the keystore password through the `KIP_STORE_PASSWORD` environment variable.

```powershell
python scripts/build.py --input "../KiP-local/original-1.5.apk" --output "../KiP-local/KiP-Android17.apk" --keystore "../KiP-local/my-key.p12" --alias kip
```

The script compiles the fixes, packages and aligns the APK, signs it, and verifies the result before writing it to the output path. Choose a new output filename each time. Android requires a signed APK for installation and a matching signature for updates. Modifying the APK invalidates its original signature, so the build signs it with your key. If your installed copy has a different signature, switching to your own key requires uninstalling that copy first. Uninstalling deletes the app's local data.

## Verify an APK independently

You can verify your own build or an APK you received using your original APK as a reference. This step requires neither a rebuild nor a private key.

```powershell
python scripts/verify.py --input "../KiP-local/original-1.5.apk" --apk "../KiP-local/KiP-Android17.apk"
```

The verifier checks the signature with `apksigner` and ZIP alignment with `zipalign`. It also compares the archive entries and their compression methods. For **663 files**, including every native library and game asset, it compares the SHA-256 hash of the uncompressed contents with your original APK. For the two patched files, it uses the reference hashes below. The verifier exits with a nonzero status if a check fails.

| Uncompressed file | SHA-256 |
|---|---|
| `classes.dex` | `549cd6d391941b0b0d8a8689e7a7018b2cb5a3aa058750d829d4d4e37f69b414` |
| `AndroidManifest.xml` | `3260ccb14ad984a150e7fef2469d18f3c57e5a540a98b869c9c546e7422b5dd3` |

A successful standalone verification ends with this line.

```text
OK: signature, ZIP alignment, 2 patched entries and 663 original entries verified.
```

Signing with a different key changes the hash of the whole APK. To check who signed a build, compare the reported `Signer #1 certificate SHA-256 digest` with the signer's known certificate fingerprint. To display your own certificate fingerprint, run this command.

```powershell
keytool -list -v -keystore "../KiP-local/my-key.p12" -alias kip
```

## PS4 test checklist

- [ ] Start *Knowledge is Power* on the PS4 and open the screen where players join. Connect the phone to the same local network as the PS4 or to the console's hotspot.
- [ ] Tap **Play** on the phone. Check that the app finds the correct PS4.
- [ ] Join the game. Check that your player appears on the TV and the first question appears on your phone.
- [ ] Choose different answers to two consecutive questions. On the TV, check that the game credits your player with the answer you selected for each question.
- [ ] Finish the round. Check the score on the PS4 and confirm that the phone stayed in the session. Record the date, network type, and first failed step, if any.

## License

The [MIT License](LICENSE) covers the patcher code and documentation. The game, the original app, and their assets belong to their respective rights holders.
