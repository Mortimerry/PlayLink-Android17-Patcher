package bitter.jnibridge;

import android.content.ComponentName;
import android.content.ServiceConnection;
import android.os.IBinder;
import java.lang.reflect.Method;

public final class ServiceConnectionCompat {
    private ServiceConnectionCompat() {}

    static Object invoke(long handle, Class<?> owner, Method method, Object[] args)
            throws NoSuchMethodException {
        if (owner == ServiceConnection.class && method.getDeclaringClass() == owner
                && method.getName().equals("onServiceConnected") && args != null && args.length == 3) {
            Class<?>[] types = method.getParameterTypes();
            if (types.length == 3 && types[0] == ComponentName.class && types[1] == IBinder.class
                    && types[2].getName().equals("android.app.IBinderSession") && method.getReturnType() == void.class) {
                Method legacy = ServiceConnection.class.getMethod("onServiceConnected", ComponentName.class, IBinder.class);
                return JNIBridge.invoke(handle, owner, legacy, new Object[] { args[0], args[1] });
            }
        }
        return JNIBridge.invoke(handle, owner, method, args);
    }
}
