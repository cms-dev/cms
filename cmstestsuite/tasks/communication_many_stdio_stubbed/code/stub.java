import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;

public class stub {

    public static void main(String[] args) throws IOException {
        int procid = Integer.parseInt(args[0]);

        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        while (true) {
            int n = Integer.parseInt(br.readLine());
            if (n == 0)
                break;
            if (procid == 0)
                System.out.println("correct " + user1.userfunc1(n));
            else
                System.out.println("correct " + user2.userfunc2(n));
            System.out.flush();
        }
    }
}
