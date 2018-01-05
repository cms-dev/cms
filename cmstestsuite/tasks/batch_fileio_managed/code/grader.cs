using System;
using System.IO;

public static class Grader
{
    public static void Main()
    {
        StreamReader reader = new StreamReader("input.txt");
        int n = int.Parse(reader.ReadLine());
        StreamWriter writer = new StreamWriter("output.txt");
        writer.WriteLine("correct " + Batchfileiomanaged.Userfunc(n));
        reader.Close();
        writer.Close();
    }
}
