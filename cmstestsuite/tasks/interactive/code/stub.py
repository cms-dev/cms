import sys
import interactive

def main():
    try:
        line = sys.stdin.readline()
        if not line: return
        a, b = map(int, line.split())
        print(interactive.op(0, a, b))
        sys.stdout.flush()

        line = sys.stdin.readline()
        if not line: return
        a, b = map(int, line.split())
        print(interactive.op(1, a, b))
        sys.stdout.flush()
    except EOFError:
        pass

if __name__ == "__main__":
    main()
