program stub;
uses sysutils, user1, user2;

var
    n: longint;
    infile, outfile: text;
    procid: longint;
    buf: array[1..1] of byte;

begin
    assign(infile, ParamStr(1));
    reset(infile);
    assign(outfile, ParamStr(2));
    rewrite(outfile);
    (* The output must be unbuffered - this seems to work. *)
    settextbuf(outfile, buf, 1);

    procid := StrToInt(ParamStr(3));

    while True do
    begin
        readln(infile, n);
        if (n = 0) then
            break;
        write(outfile, 'correct ');
        if (procid = 0) then
            writeln(outfile, userfunc1(n))
        else
            writeln(outfile, userfunc2(n));
        flush(outfile);
    end;
    close(infile);
    close(outfile);
end.
