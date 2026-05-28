class Counter {
    int value;
};

Counter create_counter(int v) {
    Counter c;
    return c;
}

int run() {
    Counter c = create_counter(5);
    c.getValue();
    return 0;
}
