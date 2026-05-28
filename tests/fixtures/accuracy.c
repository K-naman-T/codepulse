struct Point {
    int x;
    int y;
};

struct Point make_point(int x, int y) {
    struct Point p = {x, y};
    return p;
}

void print_point(struct Point p) {
    printf("(%d, %d)\n", p.x, p.y);
}
