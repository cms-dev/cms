program stub;
uses sysutils, user1, user2;

var
    n: longint;
    procid: longint;

begin
    procid := StrToInt(ParamStr(1));

    while True do
    begin
        readln(n);
        if (n = 0) then
            break;
        if (procid = 0) then
            writeln('correct ', userfunc1(n))
        else
            writeln('correct ', userfunc2(n));
        flush(output);
    end;
end.
