#!/usr/bin/env node
import { createCLI } from "./cli.js";

const program = createCLI();
await program.parseAsync(process.argv);
