package com.example;

import java.util.List;

interface Drawable {
    void draw();
}

class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int compute() {
        return this.add(3, 4);
    }
}

class Circle implements Drawable {
    private int radius;

    public Circle(int radius) {
        this.radius = radius;
    }

    @Override
    public void draw() {
        System.out.println("Drawing");
    }

    public static Circle unit() {
        return new Circle(1);
    }
}
