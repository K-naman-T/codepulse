export interface User {
  id: number;
  name: string;
  email: string;
}

export interface AdminUser {
  id: number;
  name: string;
  email: string;
  role: string;
}

export function validate(data: string): boolean {
  return data.length > 0;
}
