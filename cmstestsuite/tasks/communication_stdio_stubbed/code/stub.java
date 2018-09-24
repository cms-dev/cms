import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;

public class stub {

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        while (true) {
            int n = Integer.parseInt(br.readLine());
            if (n == 0)
                break;
            System.out.println("correct " + communication.userfunc(n));
            System.out.flush();
        }
    }
}
