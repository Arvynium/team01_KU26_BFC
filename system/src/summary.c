#include "bfc.h"

#include <string.h>

void document_print_summary(size_t elements, const char *title, const char *description) {
    printf("XML OK: elements=%zu\n", elements);
    if (title){
        char label[64] = {0};
        strncpy(label, title, sizeof(label) - 1);
        printf("Title: %s\n", label);
    }
    if (description) {
        printf("Description: ");
        printf(description);
        putchar('\n');
    }
}
