class Car {
    var model: String

    init(model: String) {
        self.model = model
    }

    func drive() {
        print("Driving \(model)")
    }
}

func create_car() -> Car {
    let car = Car(model: "Tesla")
    car.drive()
    return car
}
