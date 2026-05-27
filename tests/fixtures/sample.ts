import { readFile } from 'fs/promises';
import { join } from 'path';

interface Config {
    path: string;
    verbose: boolean;
}

class FileProcessor {
    constructor(private config: Config) {}

    async process(): Promise<string> {
        const content = await readFile(this.config.path, 'utf-8');
        return this.transform(content);
    }

    private transform(input: string): string {
        return input.toUpperCase();
    }
}

function createProcessor(path: string): FileProcessor {
    return new FileProcessor({ path, verbose: false });
}
