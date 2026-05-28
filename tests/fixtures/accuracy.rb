module Utils
  def self.helper
    puts "helper text"
  end

  class Inner
    def initialize(name)
      @name = name
    end

    def hello
      puts "hi #{@name}"
    end
  end
end

class Greeter
  def greet(name)
    puts "Hello, #{name}"
  end
end

def helper
  greeting = Greeter.new
  greeting.greet("World")
end

def demo
  Utils.helper
  x = Utils::Inner.new("test")
  x.hello
end
