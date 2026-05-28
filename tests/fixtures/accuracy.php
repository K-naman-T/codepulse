<?php

namespace App\Util;

class Logger {
    public function log(string $msg): void {
        echo "[LOG] $msg\n";
    }
}

class Calculator {
    public function add(int $a, int $b): int {
        return $a + $b;
    }

    public static function multiply(int $a, int $b): int {
        return $a * $b;
    }
}

function helper(string $msg): void {
    \strlen($msg);
}
