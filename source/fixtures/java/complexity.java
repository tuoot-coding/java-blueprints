class Complex {
  void m(int a, int b, int c, int d, int e, int f, int g, int h, int i, int j) {
    if (a > 0) { return; }
    if (b > 0) { return; }
    if (c > 0) { return; }
    if (d > 0) { return; }
    if (e > 0) { return; }
    if (f > 0) { return; }
    if (g > 0) { return; }
    if (h > 0) { return; }
    if (i > 0 && j > 0) { return; }
    while (j > 0) { j = j - 1; }
  }
}
