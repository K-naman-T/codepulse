class Calculator {
    fun add(a: Int, b: Int): Int {
        return a + b
    }
}

fun main() {
    val calc = Calculator()
    println(calc.add(3, 4))
}
