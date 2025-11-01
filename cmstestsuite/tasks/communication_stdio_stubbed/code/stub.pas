program stub;
uses communication;

var
    n: longint;

begin
    while True do
    begin
        readln(n);
        if (n = 0) then
            break;
        writeln('correct ', userfunc(n));
        flush(output);
    end;
end.
