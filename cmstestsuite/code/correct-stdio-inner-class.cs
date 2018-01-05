using System;

public static class Batchstdio
{
    public static void Main(string[] args)
    {
        int n = int.Parse(Console.ReadLine());
        Console.WriteLine(Inner.Solve(n));
    }

    private static class Inner
    {
        public static string Solve(int n)
        {
            return "correct " + n;
        }
    }
}
