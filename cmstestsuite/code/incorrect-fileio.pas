program correct;

var
    n: integer;
    infile, outfile: text;

begin
    assign(infile, 'input.txt');
    reset(infile);
    assign(outfile, 'output.txt');
    rewrite(outfile);
    readln(infile, n);
    writeln(outfile, 'incorrect ', n);
    close(infile);
    close(outfile);
end.
