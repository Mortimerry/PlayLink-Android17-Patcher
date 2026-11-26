# PlayLink Android 17 Patcher

Build the Android 17 patches for the PS4 PlayLink companion apps **Knowledge is Power**, **Knowledge is Power: Decades**, and **That's You!** from your own original APK and sign the result with your own key. This unofficial patcher recognizes the three releases below by SHA-256. Each build uses the same three fixes and selects the launcher and manifest edits for that release. Your APK supplies the game files.

The two startup fixes and the full-screen change reproduce the original Knowledge is Power patch. Decades and That's You! are test builds. Startup on Android 17, PS4 gameplay and camera layout still need device testing for those two games. Compatibility with 16 KB memory pages remains unverified for all three.

| Supported input | Android package | Version code | SHA-256 of the original APK |
|---|---|---:|---|
| Knowledge is Power 1.5 | `com.playstation.knowledge` | 10508 | `b8382fe09858b5eabf953322ecefd0485db67c15c8e283ef083b89fc0e15892d` |
| Knowledge is Power: Decades 1.4 | `com.playstation.kipdecades` | 10404 | `877c21a0baf6e88d526acff64683746259f359a432434291b1cea5c8f629a60e` |
| That's You! 1.6 | `com.playstation.iwyk` | 1623 | `6bf13282cd189e3a960e56fff0f8f5acd1e4460d831d0c21ee022c55889379d5` |

## What the patches change

| Fix | Symptom | Change |
|---|---|---|
| Android service connection | After the Sony logo, the older JNI bridge threw `NoSuchMethodError` when Android called the new overload of `onServiceConnected`. | The [service adapter](src/service/ServiceConnectionCompat.java) recognizes the specific three-argument signature and passes the first two arguments to the legacy method. The [DEX patch](tools/BuildDex.java) redirects one call to the adapter. |
| Unity memory allocator | During loading, the `UnityPreload` thread crashed with `SIGSEGV` after the allocator reported an address-range error. | In 64-bit processes on API 30 or later, the [startup code](src/allocator/AllocatorLaunch.java) passes `-debugallocator 0` before Unity starts. It preserves existing arguments and respects an explicit allocator setting. |
| Full-screen layout | In Knowledge is Power, a black bar appeared along the edge with the front camera. | On API 28 or later, the [window configuration](src/display/CutoutLayout.java) allows drawing around the cutout on a short edge. The [manifest patch](scripts/manifest.py) removes the 2.1 metadata limit on the launcher in Knowledge is Power, on the application in Decades, and both 2.4 limits on the portrait launcher in That's You!. |

The [startup patch](tools/PatchStartup.java) configures the allocator before Unity's `onCreate` runs and sets the window layout after it returns. Each of the three DEX patching stages reverses its edit on a copy, then compares the result with the input written by the same serializer. The [compile-time JNIBridge declaration](compileonly/JNIBridge.java) gives the compiler the signature of an existing method. Only the three new classes under `src` are added to the APK.

## Requirements

- Your own copy of one of the **single-file APKs** listed above. The script checks its hash before applying any patches.
- Python **3.11 or later** and JDK **21**, including `java`, `javac`, and `keytool`.
- Android SDK **Build Tools 36.0.0** and **SDK Platform 37**. You can install both through Android Studio's SDK Manager. Set `ANDROID_HOME` to the SDK directory or pass `--sdk "path to SDK"` to the Python commands below. You can build without a Unity project or the Android NDK.
- On the first build, the script downloads **dexlib2 2.5.2** and **Guava 32.1.3-jre** from Maven Central. It checks both JARs against their pinned SHA-256 hashes on every build. The [build script](scripts/build.py) lists the download URLs and hashes. The default cache is `~/.cache/kip-patcher`. To build offline, use `--cache` to point to a directory containing both JARs. APK verification works offline.

## Build from your own APK

Run these PowerShell commands from the repository root. Create a directory next to the repository and place your original APK in it. The example uses Knowledge is Power 1.5. Choose the input and output filenames for your game from the table below. The filenames are examples and the script identifies your APK by its contents. The verifier takes the same original APK used for the build.

| Game | Example input filename | Example output filename |
|---|---|---|
| Knowledge is Power 1.5 | `original-1.5.apk` | `KiP-Android17.apk` |
| Knowledge is Power: Decades 1.4 | `Decades-1.4.apk` | `Decades-Android17.apk` |
| That's You! 1.6 | `Thats-You-1.6.apk` | `Thats-You-Android17.apk` |

```powershell
New-Item -ItemType Directory -Force ../PlayLink-local | Out-Null
```

If you already have an app signing key, use its keystore path and alias in the build command below. To create a new key, run the following command once. Keep the keystore and its password for future updates.

```powershell
keytool -genkeypair -storetype PKCS12 -keystore "../PlayLink-local/my-key.p12" -alias kip -keyalg RSA -keysize 3072 -validity 3650
```

Build the APK with your key. The signing tool prompts for the password. For an automated build, you can supply the keystore password through the `KIP_STORE_PASSWORD` environment variable.

```powershell
python scripts/build.py --input "../PlayLink-local/original-1.5.apk" --output "../PlayLink-local/KiP-Android17.apk" --keystore "../PlayLink-local/my-key.p12" --alias kip
```

The script compiles the fixes, packages and aligns the APK, signs it, and verifies the result before writing it to the output path. Choose a new output filename each time. Android requires a signed APK for installation and a matching signature for updates. Modifying the APK invalidates its original signature, so the build signs it with your key. If your installed copy has a different signature, switching to your own key requires uninstalling that copy first. Uninstalling deletes the app's local data.

## Verify an APK independently

You can verify your own build or an APK you received using your original APK as a reference. This step requires neither a rebuild nor a private key.

```powershell
python scripts/verify.py --input "../PlayLink-local/original-1.5.apk" --apk "../PlayLink-local/KiP-Android17.apk"
```

The verifier checks the signature with `apksigner`, ZIP alignment with `zipalign`, the archive entries and their compression methods. It compares the uncompressed contents of all game resources and native libraries against the source APK. For `classes.dex` and `AndroidManifest.xml`, it uses the two pinned SHA-256 hashes in the [selected release profile](scripts/profiles.py). A mismatch returns a nonzero exit status.

The Decades input also carries a 32-byte distributor source-stamp digest (`stamp-cert-sha256`). Re-signing removes that signing metadata. The verifier requires it to be absent from the rebuilt package.

For Knowledge is Power 1.5, verification ends with the following line. The original-entry count depends on the game.

```text
OK: signature, ZIP alignment, 2 patched entries and 663 original entries verified.
```

Signing with a different key changes the hash of the whole APK. To check who signed a build, compare the reported `Signer #1 certificate SHA-256 digest` with the signer's known certificate fingerprint. To display your own certificate fingerprint, run this command.

```powershell
keytool -list -v -keystore "../PlayLink-local/my-key.p12" -alias kip
```

## PS4 test checklist

- [ ] Start the matching game on the PS4 and open its player join screen. Connect the phone to the same local network as the PS4 or to the console's hotspot.
- [ ] Open the app, enter console discovery and check that it finds the correct PS4. In That's You!, also check the portrait layout, camera preview and shutter button.
- [ ] Join the game. Check that your player appears on the TV and the first question appears on your phone.
- [ ] Send two different answers or votes. Confirm on the TV that both were registered for the correct player.
- [ ] Finish the round. Check the score on the PS4 and confirm that the phone stayed in the session. Record the date, network type, and first failed step, if any.

## License

The [MIT License](LICENSE) covers the patcher code and documentation. The game, the original app, and their assets belong to their respective rights holders.
