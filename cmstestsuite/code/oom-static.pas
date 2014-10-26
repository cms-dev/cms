program correct;

var
   big: array[0..132108864] of integer;
   i: longint;

begin
     for i := 1 to 132108864 do
       big[i] := 0;
    readln(big[10000]);
    writeln('correct ', big[10000]);
end.
