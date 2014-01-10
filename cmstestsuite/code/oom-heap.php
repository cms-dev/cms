<?php
// PHP arrays are extremely greedy; 1M elements are enough to cross the 128MB limit.
$n = range(0, 1024 * 1024);
$n[10000] = intval(fgets(STDIN));
echo "correct $n[10000]\n";
?>
