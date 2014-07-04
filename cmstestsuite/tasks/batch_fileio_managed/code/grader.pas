program grader;
uses batchfileiomanaged;

var
    n: longint;
    infile, outfile: text;

begin
    assign(infile, 'input.txt');
    reset(infile);
    assign(outfile, 'output.txt');
    rewrite(outfile);

    readln(infile, n);
    write(outfile, 'correct ');
    writeln(outfile, userfunc(n));

    close(infile);
    close(outfile);
end.
