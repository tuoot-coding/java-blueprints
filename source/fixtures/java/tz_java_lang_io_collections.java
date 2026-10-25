import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Formatter;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Scanner;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/** Фикстура покрытия ТЗ: java.lang, I/O, коллекции, исключения. */
interface Marker {
  void mark();

  default int hint() {
    return 1;
  }
}

class DomainError extends Exception {
  DomainError(String message) {
    super(message);
  }
}

public class TzCoverage implements Marker {
  private static final int LIMIT = 10;
  private int[] values = new int[] {1, 2, 3};

  public TzCoverage() {}

  public static void main(String[] args) {
    try (Scanner scanner = new Scanner(System.in, StandardCharsets.UTF_8)) {
      System.out.printf("%s%n", String.format("hi %d", 1));
      System.err.println("diag");
      String line = scanner.nextLine();
      int n = Integer.parseInt(line.trim());
      Object boxed = Integer.valueOf(n);
      int raw = (Integer) boxed;
      boolean ok = boxed instanceof Integer;
      int flag = ok ? 1 : 0;
      System.out.println(Math.max(flag, values[0]));
    } catch (NumberFormatException | IllegalArgumentException ex) {
      System.err.println(ex.getMessage());
    } catch (RuntimeException ex) {
      throw ex;
    } finally {
      System.out.flush();
    }
  }

  @Override
  public void mark() {
    List<String> list = new ArrayList<>();
    list.add("a");
    LinkedList<String> linked = new LinkedList<>();
    linked.addAll(list);
    Set<String> set = new HashSet<>(List.of("a", "b"));
    TreeSet<String> treeSet = new TreeSet<>(Comparator.naturalOrder());
    treeSet.addAll(set);
    Map<String, Integer> map = new HashMap<>();
    map.put("k", 1);
    TreeMap<String, Integer> treeMap = new TreeMap<>(Map.of("x", 2));
    Iterator<String> it = set.iterator();
    while (it.hasNext()) {
      String item = it.next();
      if (item.isEmpty()) {
        continue;
      }
      break;
    }
    Collections.sort(list);
    Arrays.sort(values);
    Optional<String> optional = Optional.ofNullable(list.isEmpty() ? null : list.get(0));
    Formatter formatter = new Formatter();
    formatter.format("%s", optional.orElse("-"));
    formatter.close();
  }

  void mayFail() throws DomainError, IOException {
    if (LIMIT < 0) {
      throw new DomainError("limit");
    }
    try {
      mayFailInner();
    } catch (DomainError error) {
      throw error;
    }
  }

  private void mayFailInner() throws DomainError {
    throw new DomainError("inner");
  }
}
