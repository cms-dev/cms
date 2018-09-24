program stub;
uses communication;

var
    n: longint;
    infile, outfile: text;
    buf: array[1..1] of byte;

begin
    assign(infile, ParamStr(1));
    reset(infile);
    assign(outfile, ParamStr(2));
    rewrite(outfile);
    (* The output must be unbuffered - this seems to work. *)
    settextbuf(outfile, buf, 1);

    while True do
    begin
        readln(infile, n);
        if (n = 0) then
            break;
        write(outfile, 'correct ');
        writeln(outfile, userfunc(n));
        flush(outfile);
    end;
    close(infile);
    close(outfile);
end.
