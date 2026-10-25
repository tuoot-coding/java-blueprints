from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

lang = Language(tsjava.language())
parser = Parser(lang)
src = b"""
class T {
  int f(int x) {
    switch (x) {
      case 1: return 1;
      case 2: case 3: break;
      case 4 -> { yield 4; }
      default -> 0;
    }
  }
  void g() { synchronized(this) { int a = 1; } }
  void h() { assert x > 0 : "bad"; }
}
"""
tree = parser.parse(src)


def walk(node, depth=0):
    if depth < 12 and node.is_named:
        print("  " * depth + node.type)
    for child in node.children:
        walk(child, depth + 1)


walk(tree.root_node)
