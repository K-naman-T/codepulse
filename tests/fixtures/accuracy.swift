import Foundation

protocol Drawable {
    func draw()
}

class Car {
    var model: String

    init(model: String) {
        self.model = model
    }

    func drive() {
        print("Driving \(model)")
    }
}

class Circle: Drawable {
    var radius: Int

    init(radius: Int) {
        self.radius = radius
    }

    func draw() {
        print("Drawing circle")
    }

    static func unit() -> Circle {
        return Circle(radius: 1)
    }
}

func create_car() -> Car {
    let car = Car(model: "Tesla")
    car.drive()
    return car
}

func create_circle() -> Circle {
    let c = Circle(radius: 5)
    c.draw()
    return c
}
