import java.io.InputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.function.Supplier;
import java.util.stream.Collectors;

enum Palette {
  RED,
  GREEN(2);

  final int code;

  Palette() {
    this.code = 0;
  }

  Palette(int code) {
    this.code = code;
  }
}

record Point(int x, int y) {
  public Point {
    if (x < 0 || y < 0) {
      throw new IllegalArgumentException("negative");
    }
  }

  int sum() {
    return x + y;
  }
}

public class AdvancedTz<T extends Number> {
  private final List<? extends T> items;

  public AdvancedTz(List<? extends T> items) {
    this.items = items;
  }

  public <U> U identity(U value) {
    return value;
  }

  List<String> streams(List<String> input) {
    Function<String, String> trim = String::trim;
    Predicate<String> nonEmpty = s -> !s.isEmpty();
    Consumer<String> sink = System.out::println;
    Supplier<Integer> answer = () -> 42;
    sink.accept(String.valueOf(answer.get()));
    return input.stream()
        .filter(Objects::nonNull)
        .map(trim)
        .filter(nonEmpty)
        .sorted()
        .collect(Collectors.toList());
  }

  void concurrent() throws Exception {
    ExecutorService pool = Executors.newFixedThreadPool(2);
    Future<Integer> future = pool.submit(() -> 1);
    ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
    map.put("a", future.get());
    pool.shutdown();
  }

  void reflect() throws Exception {
    Class<?> cls = String.class;
    Method method = cls.getMethod("length");
    Object value = method.invoke("hi");
    Field[] fields = cls.getDeclaredFields();
    System.out.println(value);
    System.out.println(fields.length);
  }

  void files() throws Exception {
    Path path = Paths.get("a.txt");
    Files.writeString(path, "привет", StandardCharsets.UTF_8);
    String text = Files.readString(path);
    System.out.println(text);
  }

  void net() throws Exception {
    URL url = new URI("https://example.com").toURL();
    try (InputStream in = url.openStream()) {
      in.read();
    }
    InetAddress addr = InetAddress.getByName("localhost");
    System.out.println(addr.getHostName());
  }

  void timeApi() {
    LocalDateTime now = LocalDateTime.now();
    Duration duration = Duration.ofMinutes(5);
    Instant instant = Instant.now();
    String formatted = now.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
    System.out.println(duration.toMinutes() + formatted + instant);
  }
}
