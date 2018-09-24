import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;

public class communication {

    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        while (true) {
            int n = Integer.parseInt(br.readLine());
            if (n == 0)
                break;
            System.out.println("correct " + (n + 1));
            System.out.flush();
        }
    }
}
