/* Accuracy test fixture: TypeScript — must contain exactly these symbols and calls. */

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

type Alias = string;

enum Direction { Up, Down }

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

export class ExportedClass {
  value: string;

  constructor(val: string) {
    this.value = val;
  }

  getValue<T>(key: T): string {
    return this.value;
  }
}

export default class DefaultClass {
  run(): void {
    log("default");
  }
}

const arrowFn = (x: number): number => x * 2;

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

function demo(): void {
  const obj = new ExportedClass("test");
  const val = obj?.getValue("key");
  log(val);
  Direction.Up;
}
