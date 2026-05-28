<?php

class Logger {
    public function log(string $msg): void {
        echo "[LOG] $msg\n";
    }
}

function helper(string $msg): void {
    \strlen($msg);
}
