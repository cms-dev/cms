program correct;

var
   big: array of integer;

begin
    setlength(big, 125 * 1000 * 1000 div sizeof(integer));
    readln(big[10000]);
    writeln('correct ', big[10000]);
end.
