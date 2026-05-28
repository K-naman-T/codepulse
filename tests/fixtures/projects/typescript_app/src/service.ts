import { User, AdminUser, validate } from './models';

export class UserService {
  save(user: User): boolean {
    return true;
  }

  process(user: User): string {
    return user.name;
  }

  validate(user: User): boolean {
    return validate(user.email);
  }
}

export class AdminService {
  save(admin: AdminUser): boolean {
    return true;
  }

  process(admin: AdminUser): string {
    return `[ADMIN] ${admin.name}`;
  }
}

export default UserService;
