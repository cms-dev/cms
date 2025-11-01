program communication;

var
    n: longint;

begin
    while True do
    begin
        readln(n);
        if (n = 0) then
            break;
        writeln('correct ', n);
        flush(output);
    end;
end.
