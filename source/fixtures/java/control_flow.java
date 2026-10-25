class Flow {
  void branch(boolean flag) {
    if (flag) {
      return;
    } else {
      flag = false;
    }
  }

  void loop(int n) {
    while (n > 0) {
      n = n - 1;
    }
  }

  void scan(int n) {
    for (int i = 0; i < n; i++) {
      if (i == 1) {
        continue;
      }
      if (i == 2) {
        break;
      }
    }
  }
}
