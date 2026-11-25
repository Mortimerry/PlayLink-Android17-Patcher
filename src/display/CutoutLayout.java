package pl.kip.compat;

import android.app.Activity;
import android.os.Build;
import android.view.Window;
import android.view.WindowManager;

public final class CutoutLayout {
    private CutoutLayout() {}

    public static void configure(Activity activity) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) return;
        Window window = activity.getWindow();
        WindowManager.LayoutParams params = window.getAttributes();
        params.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        window.setAttributes(params);
    }
}
