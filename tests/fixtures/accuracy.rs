// Rust golden fixture for accuracy testing
// Symbols:
//   function: create_user, factorial, run
//   method: User.get_name, User.is_active
//   class: User

/// A user record
struct User {
    name: String,
    active: bool,
}

impl User {
    /// Get the user's name
    fn get_name(&self) -> &str {
        &self.name
    }

    /// Check if active
    fn is_active(&self) -> bool {
        self.active
    }
}

/// Create a user
fn create_user(name: &str) -> User {
    let u = User { name: String::from(name), active: true };
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
    u.is_active()
}
