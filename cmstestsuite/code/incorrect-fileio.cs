using System;
using System.IO;

public static class Batchfileio
{
    public static void Main()
    {
        StreamReader reader = new StreamReader("input.txt");
        int n = int.Parse(reader.ReadLine());
        StreamWriter writer = new StreamWriter("output.txt");
        writer.WriteLine("incorrect " + n);
        reader.Close();
        writer.Close();
    }
}
