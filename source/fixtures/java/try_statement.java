class Safety {
  void m() {
    try {
      risky();
    } catch (Exception error) {
      throw error;
    } finally {
      cleanup();
    }
  }
}
