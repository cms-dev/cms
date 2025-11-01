<?php
$fin = fopen("input.txt", "r");
$n = intval(fgets($fin));
$fout = fopen("output.txt", "w");
if ($n % 2 == 0)
    fwrite($fout, "correct 0\n");
else
    fwrite($fout, "correct $n\n");
?>
