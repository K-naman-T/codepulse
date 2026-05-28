class Greeter
  def greet(name)
    puts "Hello, #{name}"
  end
end

def helper
  greeting = Greeter.new
  greeting.greet("World")
end
