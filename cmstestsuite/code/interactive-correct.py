import sys

def op(code, a, b):
    if code == 0:
        return a + b
    elif code == 1:
        return a * b
    return 0

def main():
    try:
        line = sys.stdin.readline()
        if not line: return
        a, b = map(int, line.split())
        print(op(0, a, b))
        sys.stdout.flush()

        line = sys.stdin.readline()
        if not line: return
        a, b = map(int, line.split())
        print(op(1, a, b))
        sys.stdout.flush()
    except EOFError:
        pass

if __name__ == "__main__":
    main()
