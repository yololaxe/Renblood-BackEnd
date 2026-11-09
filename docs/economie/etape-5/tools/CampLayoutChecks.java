import fr.renblood.medievalstructures.manager.CampLayout;
import java.util.HashSet;

public class CampLayoutChecks {
    public static void main(String[] args) {
        var offsets = CampLayout.chestOffsets();
        if (offsets.size() != 4216 || new HashSet<>(offsets).size() != offsets.size()) {
            throw new AssertionError("Camp chest coordinates overlap");
        }
        for (var position : offsets) {
            if ((position.x() & 1) != 0 || (position.z() & 1) != 0
                    || Math.max(Math.abs(position.x()), Math.abs(position.z())) < 4) {
                throw new AssertionError("Chest spacing or central camp clearance changed");
            }
        }
        if (!CampLayout.overlaps(0, 0, 4000, 0) || CampLayout.overlaps(0, 0, 5000, 0)
                || CampLayout.overlaps(Integer.MAX_VALUE, 0, Integer.MIN_VALUE, 0)) {
            throw new AssertionError("Exploration area separation failed");
        }
        if (!CampLayout.contains(1999, 0, 0, 0) || CampLayout.contains(2000, 0, 0, 0)) {
            throw new AssertionError("Exploration border threshold changed");
        }
        System.out.println("CampLayout: 4216 distinct chest locations, spacing, borders and overflow checks passed.");
    }
}
