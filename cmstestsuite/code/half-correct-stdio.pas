program correct;

var
    n: integer;

begin
    readln(n);
    if n mod 2 = 0 then n := 0;
    writeln('correct ', n);
end.
