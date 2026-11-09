import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import com.google.gson.*;
import net.minecraft.world.entity.player.Player;
import fr.renblood.npcshopkeeper.procedures.trade.CreateTradeValidationProcedure;
public class OfferCreationChecks {
 static void check(boolean c,String message){if(!c)throw new AssertionError(message);}
 static JsonObject offer(String name){var object=new JsonObject();object.addProperty("Name",name);return object;}
 public static void main(String[] args) throws Exception {
  Path root=Path.of(args[0]);Files.createDirectories(root);Path path=root.resolve("offers.json");Files.writeString(path,"{\"schema\":1,\"trades\":[]}");
  var player=new Player();
  check(CreateTradeValidationProcedure.writeNewTradeToFile(path.toString(),offer("First"),player),"Valid offer not committed");
  check(player.messages.isEmpty(),"Helper claimed UI success before caller closed the form");
  check(!CreateTradeValidationProcedure.writeNewTradeToFile(path.toString(),offer("FIRST"),player),"Duplicate name accepted");
  var result=JsonParser.parseString(Files.readString(path)).getAsJsonObject();check(result.getAsJsonArray("trades").size()==1&&result.get("schema").getAsInt()==1,"Duplicate attempt changed catalog");
  Path blocked=root.resolve("blocked");Files.createDirectory(blocked);
  check(!CreateTradeValidationProcedure.writeNewTradeToFile(blocked.toString(),offer("Blocked"),player),"Failed publication returned success");
  Path malformed=root.resolve("malformed.json");Files.writeString(malformed,"[]");
  check(!CreateTradeValidationProcedure.writeNewTradeToFile(malformed.toString(),offer("Lost"),player)&&Files.readString(malformed).equals("[]"),"Malformed document overwritten");
  Path concurrent=root.resolve("concurrent.json");Files.writeString(concurrent,"{\"trades\":[]}");var pool=Executors.newFixedThreadPool(2);
  try {
   var gate=new CountDownLatch(1);List<Future<Boolean>> tasks=new ArrayList<>();
   for(int i=0;i<2;i++)tasks.add(pool.submit(()->{gate.await();return CreateTradeValidationProcedure.writeNewTradeToFile(concurrent.toString(),offer("Same"),new Player());}));
   gate.countDown();int accepted=0;for(var task:tasks)if(task.get())accepted++;
   check(accepted==1&&JsonParser.parseString(Files.readString(concurrent)).getAsJsonObject().getAsJsonArray("trades").size()==1,"Concurrent duplicate accepted or lost");
  } finally {pool.shutdownNow();}
  System.out.println("Offer publication: committed success, duplicate names, failed IO, invalid document and concurrent duplicate checks passed.");
 }
}
