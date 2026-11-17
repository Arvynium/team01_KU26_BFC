#include "bfc.h"

#include <inttypes.h>
#include <stdlib.h>

void epilogue() {
    printf("----------------------------------------------\n");

    printf("Professor Lee has a new request for us.\n"
           "CCSLAB has been developing an XML processing tool\n"
           "for internal use, and this is its very first demo version.\n\n");

    printf("Before putting it into actual use,\n"
           "the professor asked us to perform a security assessment.\n\n");

    printf("At first glance, everything seems to work just fine...\n"
           "but something feels a little off.\n\n");

    printf("A few suspicious bugs are hiding somewhere in the code,\n"
           "and some of them might be more dangerous than they look.\n");

    printf("So, what vulnerabilities are lurking inside this program?\n"
           "And which of them can actually be exploited?\n\n");

    printf("Time to put our security skills to the test!\n");

    printf("----------------------------------------------\n\n\n");
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 1) {
        fprintf(stderr, "Usage: %s\n", argv[0]);
        return EXIT_FAILURE;
    }

    Document document = {0};
    epilogue();
    puts("BFC XML Workshop");
    printf("Credits: %" PRIu32 "; balance=$%" PRIu32 "\n", credit_balance(), balance);
    for (;;) {
        puts("\n1. Memory document\n2. XML files\n3. XML processing"
             "\n4. XML parsing credits\n5. Reviews\n0. Exit");
        uint32_t choice;
        if (!read_u32("Choice: ", &choice)) {
            if (feof(stdin) || ferror(stdin))
                break;
            continue;
        }
        switch (choice) {
        case 0: document_clear(&document); return EXIT_SUCCESS;
        case 1: memory_menu(&document); break;
        case 2: file_menu(&document); break;
        case 3: parser_menu(&document); break;
        case 4: credit_menu(); break;
        case 5: review_menu(); break;
        default: puts("Unknown choice."); break;
        }
    }
    document_clear(&document);
    return EXIT_SUCCESS;
}
