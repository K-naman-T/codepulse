// Rust golden fixture for accuracy testing

mod utils {
    fn helper() -> bool {
        true
    }
}

enum Status {
    Active,
    Inactive,
}

/// A user record
struct User {
    name: String,
    active: bool,
}

impl User {
    fn new(name: &str) -> Self {
        User {
            name: String::from(name),
            active: true,
        }
    }

    /// Get the user's name
    fn get_name(&self) -> &str {
        &self.name
    }

    /// Check if active
    fn is_active(&self) -> bool {
        self.active
    }
}

/// A simple greeting trait
trait Greeter {
    fn greet(&self) -> &str;
}

impl Greeter for User {
    /// Say hello
    fn greet(&self) -> &str {
        "Hello!"
    }
}

/// Identity generic function
fn identity<T>(x: T) -> T {
    x
}

/// Create a user
fn create_user(name: &str) -> User {
    let u = User::new(name);
    u.is_active();
    u
}

/// Compute factorial
fn factorial(n: u32) -> u32 {
    if n <= 1 { 1 } else { n * factorial(n - 1) }
}

/// Run the app
fn run() -> bool {
    let u = create_user("test");
    u.is_active();
    u.greet();
    identity(true);
    true
}
