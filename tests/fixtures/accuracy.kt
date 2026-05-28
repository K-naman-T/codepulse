package com.example

import kotlin.math.sqrt

interface Drawable {
    fun draw()
}

abstract class Shape : Drawable {
    abstract fun area(): Double
}

class Calculator {
    fun add(a: Int, b: Int): Int {
        return a + b
    }
}

class Circle(val radius: Double) : Shape() {
    override fun draw() {
        println("Circle")
    }

    override fun area(): Double {
        return Math.PI * radius * radius
    }

    companion object {
        fun unit() = Circle(1.0)
    }
}

fun main() {
    val calc = Calculator()
    println(calc.add(3, 4))
}
