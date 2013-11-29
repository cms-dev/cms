<?php
$fin = fopen("input.txt", "r");
$n = intval(fgets($fin));
$fout = fopen("output.txt", "w");
fwrite($fout, "correct $n\n");
exit(1);
?>
