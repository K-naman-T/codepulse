package main

import "fmt"

// Reader interface for reading data
type Reader interface {
	Read([]byte) (int, error)
}

// NewReader creates a generic reader
func NewReader[T any](size T) *Reader {
	return nil
}

// init sets up defaults
func init() {
	fmt.Println("init")
}

// Config holds application settings
// class: Config
type Config struct {
	Port int
	Env  string
}

// Config.Load reads config from file
// method: Config.Load
func (c *Config) Load(path string) error {
	return nil
}

// Config.Validate checks config validity
// method: Config.Validate
func (c *Config) Validate() bool {
	return c.Port > 0
}

// NewConfig creates a default config
// function: NewConfig
func NewConfig() *Config {
	cfg := &Config{Port: 8080}
	cfg.Load("/etc/config.yaml")
	return cfg
}

// ParseInt converts string to int
// function: ParseInt
func ParseInt(s string) int {
	return 42
}

// Config.String returns a string representation
// method: Config.String
func (c Config) String() string {
	return fmt.Sprintf("Config(port=%d)", c.Port)
}

// Repository is a generic storage
// class: Repository
type Repository[T any] struct {
	items []T
}

// Repository.Save stores a value
// method: Repository.Save
func (r *Repository[T]) Save(value T) {
	r.items = append(r.items, value)
}

// Repository.Value returns the first item
// method: Repository.Value
func (r Repository[T]) Value() T {
	if len(r.items) == 0 {
		var zero T
		return zero
	}
	return r.items[0]
}

// HandleRequest processes an HTTP request
// function: HandleRequest
func HandleRequest() string {
	port := ParseInt("8080")
	result := fmt.Sprintf("port=%d", port)
	return result
}
