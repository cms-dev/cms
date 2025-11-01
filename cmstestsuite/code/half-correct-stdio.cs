using System;

public static class Batchstdio
{
    public static void Main()
    {
        int n = int.Parse(Console.ReadLine());
        Console.WriteLine("correct " + (n % 2 != 0 ? n : 0));
    }
}
