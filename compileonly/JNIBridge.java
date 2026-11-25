package bitter.jnibridge;
import java.lang.reflect.Method;
class JNIBridge {
    static native Object invoke(long handle, Class<?> owner, Method method, Object[] args);
}
