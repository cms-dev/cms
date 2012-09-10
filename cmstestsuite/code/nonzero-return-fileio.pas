program nonzero;

var
    n: integer;
    infile, outfile: text;

begin
    assign(infile, 'input.txt');
    reset(infile);
    assign(outfile, 'output.txt');
    rewrite(outfile);
    readln(infile, n);
    writeln(outfile, 'correct ', n);
    close(infile);
    close(outfile);
    exitcode := 1;
end.
