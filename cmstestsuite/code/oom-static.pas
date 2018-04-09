program correct;

var
   big: array[0..125 * 1000 * 1000 div sizeof(integer)] of integer;
   i: longint;

begin
     for i := 1 to 125 * 1000 * 1000 div sizeof(integer) do
       big[i] := 0;
    readln(big[10000]);
    writeln('correct ', big[10000]);
end.
