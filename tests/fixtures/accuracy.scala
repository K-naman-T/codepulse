trait Greeter {
  def greet(): String
}

class Hello extends Greeter {
  override def greet(): String = "Hello"
}

object Main {
  def run(): Unit = {
    println("running")
  }
}

def helper(): Unit = {
  Main.run()
}
