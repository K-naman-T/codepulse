/* Accuracy test fixture: TypeScript — must contain exactly these symbols and calls. */
/* Expected: 2 classes (Database, UserService), 2 interfaces (User, Config)   */
/* Expected: 2 functions (start, initialize)                                  */
/* Expected calls: listen, parseInt, connect, log, getFullName, sendEmail      */
/* Expected imports: named (readFile), default (express), namespace (fs),      */
/*   side-effect (dotenv)                                                     */

import { readFile } from 'fs/promises';
import express from 'express';
import { readFileSync } from 'fs';
import * as fs from 'fs';
import 'dotenv/config';

interface User {
  id: number;
  name: string;
  email: string;
}

interface Config {
  port: number;
  database: string;
}

class Database {
  private url: string;

  constructor(url: string) {
    this.url = url;
  }

  async query(sql: string): Promise<any> {
    const result = await connect(this.url);
    return result;
  }
}

class UserService {
  constructor(private db: Database) {}

  async getFullName(userId: number): Promise<string> {
    const user = await this.db.query(`SELECT * FROM users WHERE id = ${userId}`);
    return `${user.name} (${user.email})`;
  }

  async sendEmail(userId: number): Promise<void> {
    const user = await this.db.query(`SELECT * FROM users WHERE id = ${userId}`);
    log(`Sending email to ${user.email}`);
  }
}

function start(port: number): void {
  const server = express();
  server.listen(port, () => {
    log(`Server started on port ${port}`);
  });
}

function initialize(): void {
  const port = parseInt('3000', 10);
  start(port);
}

function log(message: string): void {
  console.log(message);
}

function connect(url: string): Promise<any> {
  return fetch(url);
}
