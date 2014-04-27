import java.util.Scanner;

public class batchstdio {

    public static void main(String[] args) {
    	int[] big = new int[128 * 1024 * 1024];
        Scanner scanner = new Scanner(System.in);
        big[10000] = scanner.nextInt();
        System.out.println("correct "+big[10000]);
    }
}
