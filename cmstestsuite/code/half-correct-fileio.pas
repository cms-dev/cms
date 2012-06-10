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
    if n mod 2 = 0 then n := 0;
    writeln(outfile, 'correct ', n);
    close(infile);
    close(outfile);
end.
