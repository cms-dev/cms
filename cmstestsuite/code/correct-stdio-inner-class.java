import java.util.Scanner;

public class batchstdio {

    private static class Inner {
        public String solve(int n) {
            return "correct " + n;
        }
    }

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int n = scanner.nextInt();
        Inner inner = new Inner();
        System.out.println(inner.solve(n));
    }
}
