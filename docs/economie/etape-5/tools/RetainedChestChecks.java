import fr.renblood.medievalstructures.manager.RetainedChestRegistry;
import java.util.concurrent.atomic.AtomicInteger;

public class RetainedChestChecks {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        var registry = new RetainedChestRegistry();
        check(registry.page(1).total() == 0 && registry.page(100).number() == 1, "Empty pagination");
        for (long i = 0; i < 23; i++) registry.put(i, 1000 + i);
        check(registry.page(1).incidents().size() == 10 && registry.page(2).incidents().size() == 10
                && registry.page(3).incidents().size() == 3, "Incidents beyond first page are missing");
        check(registry.page(Integer.MAX_VALUE).number() == 3 && registry.page(-1).number() == 1, "Page bounds");
        check(registry.page(3).incidents().get(0).camp() == 20, "Stable incident ordering");
        try { registry.snapshot().clear(); throw new AssertionError("Mutable snapshot"); }
        catch (UnsupportedOperationException expected) { }

        var inspections = new AtomicInteger();
        var result = registry.resolve(-1, camp -> { inspections.incrementAndGet(); return true; }, camp -> false);
        check(result == RetainedChestRegistry.Resolution.NOT_FOUND && inspections.get() == 0, "Unknown position inspected");
        result = registry.resolve(0, camp -> false, camp -> { throw new AssertionError("Unloaded chest inspected"); });
        check(result == RetainedChestRegistry.Resolution.UNLOADED && registry.page(1).total() == 23, "Unloaded incident removed");
        result = registry.resolve(0, camp -> true, camp -> true);
        check(result == RetainedChestRegistry.Resolution.NOT_EMPTY && registry.page(1).total() == 23, "Nonempty incident removed");
        try {
            registry.resolve(0, camp -> true, camp -> { throw new IllegalStateException("Unavailable inventory"); });
            throw new AssertionError("Inspection failure ignored");
        } catch (IllegalStateException expected) { }
        check(registry.page(1).total() == 23, "Failed inspection mutated registry");
        result = registry.resolve(0, camp -> true, camp -> false);
        check(result == RetainedChestRegistry.Resolution.RESOLVED && registry.page(1).total() == 22, "Resolved incident retained");
        check(!registry.anyCamp(camp -> camp == 0) && registry.anyCamp(camp -> camp == 1), "Camp reservation not released precisely");
        result = registry.resolve(0, camp -> { throw new AssertionError("Resolved position inspected twice"); }, camp -> true);
        check(result == RetainedChestRegistry.Resolution.NOT_FOUND, "Resolution not idempotent");

        registry.put(Long.MIN_VALUE, Long.MAX_VALUE);
        var restored = new RetainedChestRegistry();
        registry.snapshot().forEach(row -> restored.put(row.camp(), row.source()));
        check(restored.snapshot().equals(registry.snapshot()), "Packed save coordinates changed during round-trip");
        System.out.println("Retained chests: pagination, unloaded/nonempty guards, failed inspection, precise closure and save round-trip passed.");
    }
}
