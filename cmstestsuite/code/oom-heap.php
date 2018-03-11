<?php
// PHP arrays are extremely greedy; 10M elements are enough to cross the 125MB limit.
$n = range(0, 10 * 1000 * 1000);
$n[10000] = intval(fgets(STDIN));
echo "correct $n[10000]\n";
?>
