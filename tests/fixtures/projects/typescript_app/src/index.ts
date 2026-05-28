export * from './models';
export { UserService, AdminService } from './service';

import { UserService, AdminService } from './service';
import { User } from './models';

function run(): void {
  const user: User = { id: 1, name: "Alice", email: "alice@example.com" };
  const svc = new UserService();
  svc.save(user);
  svc.process(user);

  const adminSvc = new AdminService();
  adminSvc.save({ id: 2, name: "Bob", email: "bob@example.com", role: "admin" });
  adminSvc.process({ id: 2, name: "Bob", email: "bob@example.com", role: "admin" });
}
