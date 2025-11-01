program communication;

var
    n: longint;

begin
    while True do
    begin
        readln(n);
        if (n = 0) then
            break;
        writeln('correct ', n + 1);
        flush(output);
    end;
end.
