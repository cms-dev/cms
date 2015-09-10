program correct;

var
   big: array[0..128 * 1024 * 1024 div sizeof(integer)] of integer;
   i: longint;

begin
     for i := 1 to 128 * 1024 * 1024 div sizeof(integer) do
       big[i] := 0;
    readln(big[10000]);
    writeln('correct ', big[10000]);
end.
