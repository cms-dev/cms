import java.util.Scanner;

public class batchstdio {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int n = scanner.nextInt();
        System.out.println("correct "+(n % 2 == 1 ? n : 0));
    }
}
