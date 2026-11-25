package pl.kip.compat;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Process;
import android.util.Log;

public final class AllocatorLaunch {
    private AllocatorLaunch() {}

    public static void configure(Activity activity) {
        if (Build.VERSION.SDK_INT < 30 || !Process.is64Bit()) return;
        Intent launch = activity.getIntent();
        if (launch == null) return;
        final String setting = "-debugallocator 0";
        String args = launch.getStringExtra("unity");
        if (args != null && java.util.Arrays.asList(args.trim().split("\\s+")).contains("-debugallocator")) return;
        launch.putExtra("unity", args == null || args.trim().isEmpty() ? setting : args + " " + setting);
        Log.i("KiPCompat", "Requested Unity alternative allocator, mode 0");
    }
}
