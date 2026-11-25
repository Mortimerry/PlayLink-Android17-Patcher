import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import org.jf.dexlib2.*;
import org.jf.dexlib2.builder.MutableMethodImplementation;
import org.jf.dexlib2.builder.instruction.BuilderInstruction35c;
import org.jf.dexlib2.iface.*;
import org.jf.dexlib2.iface.instruction.formats.Instruction35c;
import org.jf.dexlib2.immutable.*;
import org.jf.dexlib2.immutable.reference.ImmutableMethodReference;
import org.jf.dexlib2.rewriter.*;
import org.jf.dexlib2.writer.pool.DexPool;

public final class PatchStartup {
    static final Opcodes OPS = Opcodes.forApi(21);
    static final String ENTRY = "Lcom/playstation/knowledge/UnityPlayerActivityWithPS4Discovery;";
    static final List<String> BUNDLE = List.of("Landroid/os/Bundle;");
    static final ImmutableMethodReference PARENT = new ImmutableMethodReference(
            "Lcom/unity3d/player/UnityPlayerActivity;", "onCreate", BUNDLE, "V");

    final String helper;
    final int parentIndex;
    final int callIndex;
    final ImmutableMethodReference configure;

    PatchStartup(String className, int parentIndex, int callIndex) {
        helper = "Lpl/kip/compat/" + className + ";";
        this.parentIndex = parentIndex;
        this.callIndex = callIndex;
        configure = new ImmutableMethodReference(helper, "configure", List.of("Landroid/app/Activity;"), "V");
    }

    static DexFile read(String path) throws Exception {
        return DexFileFactory.loadDexFile(new File(path), OPS);
    }

    static void write(String path, Collection<? extends ClassDef> classes) throws Exception {
        DexPool.writeTo(path, new ImmutableDexFile(OPS, classes));
    }

    List<ClassDef> edit(DexFile input, boolean insert) {
        List<ClassDef> classes = new ArrayList<>();
        int[] edits = {0};
        DexRewriter editor = new DexRewriter(new RewriterModule() {
            public Rewriter<Method> getMethodRewriter(Rewriters rewriters) {
                return method -> {
                    if (!method.getDefiningClass().equals(ENTRY) || !method.getName().equals("onCreate")
                            || !method.getParameterTypes().equals(BUNDLE)) return method;
                    MutableMethodImplementation body = new MutableMethodImplementation(method.getImplementation());
                    if (!insert) {
                        Instruction35c call = (Instruction35c) body.getInstructions().get(callIndex);
                        if (call.getOpcode() != Opcode.INVOKE_STATIC || !configure.equals(call.getReference()))
                            throw new IllegalStateException("Missing expected configure call");
                        body.removeInstruction(callIndex);
                    }
                    Instruction35c parent = (Instruction35c) body.getInstructions().get(parentIndex);
                    if (parent.getOpcode() != Opcode.INVOKE_SUPER || !PARENT.equals(parent.getReference())
                            || parent.getRegisterCount() != 2)
                        throw new IllegalStateException("Unexpected parent onCreate call");
                    if (insert) body.addInstruction(callIndex, new BuilderInstruction35c(
                            Opcode.INVOKE_STATIC, 1, parent.getRegisterC(), 0, 0, 0, 0, configure));
                    edits[0]++;
                    return new ImmutableMethod(method.getDefiningClass(), method.getName(), method.getParameters(),
                            method.getReturnType(), method.getAccessFlags(), method.getAnnotations(),
                            method.getHiddenApiRestrictions(), body);
                };
            }
        });
        for (ClassDef cls : input.getClasses()) {
            if (cls.getType().equals(helper)) {
                if (insert) throw new IllegalStateException("Helper already present");
            } else if (cls.getType().equals(ENTRY)) {
                classes.add(ImmutableClassDef.of(editor.getClassDefRewriter().rewrite(cls)));
            } else {
                classes.add(cls);
            }
        }
        if (edits[0] != 1) throw new IllegalStateException("Expected exactly one startup method");
        return classes;
    }

    public static void main(String[] args) throws Exception {
        PatchStartup patch = switch (args[0]) {
            case "allocator" -> new PatchStartup("AllocatorLaunch", 0, 0);
            case "display" -> new PatchStartup("CutoutLayout", 1, 2);
            default -> throw new IllegalArgumentException("Unknown startup patch");
        };
        DexFile source = read("classes.dex");
        DexFile helper = read("helper/classes.dex");
        if (helper.getClasses().size() != 1 || !helper.getClasses().iterator().next().getType().equals(patch.helper))
            throw new IllegalStateException("Unexpected helper DEX contents");
        List<ClassDef> classes = patch.edit(source, true);
        classes.addAll(helper.getClasses());
        write("fixed.dex", classes);
        write("inverse.dex", patch.edit(read("fixed.dex"), false));
        write("base-canonical.dex", source.getClasses());
        if (Files.mismatch(Path.of("inverse.dex"), Path.of("base-canonical.dex")) != -1)
            throw new IllegalStateException("Reversing startup patch did not restore original DEX");
    }
}
