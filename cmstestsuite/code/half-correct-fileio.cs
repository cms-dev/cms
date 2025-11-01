using System;
using System.IO;

public static class Batchfileio
{
    public static void Main()
    {
        StreamReader reader = new StreamReader("input.txt");
        int n = int.Parse(reader.ReadLine());
        StreamWriter writer = new StreamWriter("output.txt");
        writer.WriteLine("correct " + (n % 2 != 0 ? n : 0));
        reader.Close();
        writer.Close();
    }
}
