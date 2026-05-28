package com.example

import scala.math.Pi

trait Greeter {
  def greet(): String
}

trait Drawable {
  def draw(): Unit
}

abstract class Shape {
  def area(): Double
}

class Hello extends Greeter {
  override def greet(): String = "Hello"
}

class Circle(radius: Double) extends Shape with Drawable {
  override def draw(): Unit = println("Circle")
  override def area(): Double = Pi * radius * radius
}

object Main {
  def run(): Unit = {
    println("running")
  }
}

object CircleFactory {
  def unit(): Circle = new Circle(1.0)
}

def helper(): Unit = {
  Main.run()
}

def demo(): Unit = {
  val c = CircleFactory.unit()
  c.draw()
}
