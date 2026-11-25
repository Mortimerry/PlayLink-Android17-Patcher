import java.io.File;
import java.nio.file.*;
import java.util.*;
import org.jf.dexlib2.*;
import org.jf.dexlib2.iface.*;
import org.jf.dexlib2.iface.instruction.*;
import org.jf.dexlib2.iface.instruction.formats.Instruction35c;
import org.jf.dexlib2.iface.reference.MethodReference;
import org.jf.dexlib2.immutable.ImmutableDexFile;
import org.jf.dexlib2.immutable.reference.ImmutableMethodReference;
import org.jf.dexlib2.immutable.instruction.ImmutableInstruction35c;
import org.jf.dexlib2.rewriter.*;
import org.jf.dexlib2.writer.pool.DexPool;

public final class BuildDex {
    static final String BRIDGE="Lbitter/jnibridge/JNIBridge;";
    static final String HELPER="Lbitter/jnibridge/ServiceConnectionCompat;";
    static final String HANDLER="Lbitter/jnibridge/JNIBridge$a;";
    static final List<String> SIG=Arrays.asList("J","Ljava/lang/Class;","Ljava/lang/reflect/Method;","[Ljava/lang/Object;");
    static final String RESULT="Ljava/lang/Object;";
    static final Opcodes OPS=Opcodes.forApi(21);
    static DexFile read(String path) throws Exception {return DexFileFactory.loadDexFile(new File(path), OPS);}
    static void write(String path, Collection<ClassDef> classes) throws Exception {
        DexPool.writeTo(path,new ImmutableDexFile(OPS,classes));
    }
    static MethodReference ref(String className){return new ImmutableMethodReference(className,"invoke",SIG,RESULT);}
    static List<ClassDef> redirect(DexFile input,String from,String to) {
        List<ClassDef> out=new ArrayList<>();
        int[] changes={0};
        DexRewriter rewriter=new DexRewriter(new RewriterModule(){
            public Rewriter<Instruction> getInstructionRewriter(Rewriters r){return instruction -> {
                if(instruction instanceof Instruction35c && instruction.getOpcode()==Opcode.INVOKE_STATIC) {
                    Instruction35c i=(Instruction35c)instruction;
                    if(i.getReference().equals(ref(from))) {
                        changes[0]++;
                        return new ImmutableInstruction35c(i.getOpcode(),i.getRegisterCount(),i.getRegisterC(),
                            i.getRegisterD(),i.getRegisterE(),i.getRegisterF(),i.getRegisterG(),ref(to));
                    }
                }
                return instruction;
            };}
        });
        for(ClassDef c:input.getClasses()) {
            if(c.getType().equals(HELPER))continue;
            if(c.getType().equals(HANDLER))
                out.add(org.jf.dexlib2.immutable.ImmutableClassDef.of(rewriter.getClassDefRewriter().rewrite(c)));
            else out.add(c);
        }
        if(changes[0]!=1)throw new IllegalStateException("expected one JNI call, got "+changes[0]);
        return out;
    }
    public static void main(String[] args) throws Exception {
        DexFile original=read("classes.dex");
        DexFile helper=read("helper/classes.dex");
        if(helper.getClasses().size()!=1 || !helper.getClasses().iterator().next().getType().equals(HELPER))
            throw new IllegalStateException("unexpected helper contents");
        List<ClassDef> patched=redirect(original,BRIDGE,HELPER);
        patched.addAll(helper.getClasses());write("fixed.dex",patched);
        write("normalized.dex",new ArrayList<>(original.getClasses()));
        write("reversed.dex",redirect(read("fixed.dex"),HELPER,BRIDGE));
        if(Files.mismatch(Paths.get("normalized.dex"),Paths.get("reversed.dex"))!=-1)
            throw new AssertionError("unexpected DEX changes");
        System.out.println("Reversing the single call edit and removing the adapter restores the canonical original DEX. Original classes: "+original.getClasses().size());
    }
}
