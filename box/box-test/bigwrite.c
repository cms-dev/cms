
#include <stdio.h>

int dim = 100000000;

int main() {

	FILE *fout = fopen("output.txt", "w");
	int i;
	for (i = 0; i < dim; i++) {
		fputc(i % 256, fout);
	}
	fclose(fout);
	return 0;

}

