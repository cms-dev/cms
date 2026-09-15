#ifdef EVAL // this file can accidentally OOM editors/language servers...
#define a "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#define b a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a
#define c b b b b b b b b b b b b b b b b b b b b b b b b b b b b b b b b
#define d c c c c c c c c c c c c c c c c c c c c c c c c c c c c c c c c
#define e d d d d d d d d d d d d d d d d d d d d d d d d d d d d d d d d
const char* x = e e;
#endif
int main() { return 0; }
