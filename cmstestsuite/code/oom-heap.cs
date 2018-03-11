using System;

public static class Batchstdio
{
    public static void Main()
    {
        int[] big = new int[125 * 1000 * 1000 / 4];

        // If we don't do this cycle, the compiler is smart enough not to
        // map the array into resident memory.
        for (int i = 0; i < 125 * 1000 * 1000 / sizeof(int); i++)
        {
            big[i] = 0;
        }

        big[10000] = int.Parse(Console.ReadLine());
        Console.WriteLine("correct " + big[10000]);
    }
}
