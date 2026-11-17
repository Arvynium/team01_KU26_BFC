#include "bfc.h"

#include <inttypes.h>

static int submenu_choice(const char *title, const char *const options[],
                          uint32_t count) {
    for (;;) {
        printf("\n[%s]\n", title);
        for (uint32_t i = 0; i < count; i++)
            printf("%u. %s\n", (unsigned int)(i + 1), options[i]);
        puts("0. Back");
        uint32_t choice;
        if (!read_u32("Select: ", &choice)) {
            if (feof(stdin) || ferror(stdin))
                return 0;
            continue;
        }
        if (choice <= count)
            return (int)choice;
        puts("Unknown choice.");
    }
}

void flag_print(){
    FILE *file = fopen("flag.txt", "r");
    if (file == NULL) {
        printf("Failed to open flag.txt");
    } else {
        char flag[200];
        if (fgets(flag, sizeof(flag), file) != NULL) {
            printf("%s\n", flag);
        }
        fclose(file);
    }
}

void memory_menu(Document *document) {
    const char *const options[] = {"Write XML", "Show XML"};
    for (;;) {
        int choice = submenu_choice("Memory document", options, 2);
        if (choice == 0)
            return;
        if (choice == 1)
            document_edit(document);
        else
            document_show(document);
    }
}

void file_menu(Document *document) {
    const char *const options[] = {"Save XML to file", "Load XML from file"};
    for (;;) {
        int choice = submenu_choice("XML files", options, 2);
        if (choice == 0)
            return;
        if (choice == 1)
            document_save_file(document);
        else
            document_open_file(document);
    }
}

void parser_menu(Document *document) {
    const char *const options[] = {"Parse XML", "Clear XML memory"};
    for (;;) {
        int choice = submenu_choice("XML processing", options, 2);
        if (choice == 0)
            return;
        if (choice == 1)
            document_parse(document);
        else {
            document_clear(document);
            puts("Document cleared.");
        }
    }
}

void credit_menu(void) {
    const char *const options[] = {
        "Buy credits",
        "Refund credits",
        "I'm millionaire!", "I'm credit rich!"
    };
    for (;;) {
        printf("Remaining credits: %" PRIu32 "; balance=$%" PRIu32 "\n",
               credit_balance(), balance_read());
        int choice = submenu_choice("XML parsing credits", options, 4);
        if (choice != 1)
            func_wait();
        switch (choice) {
        case 0: return;
        case 1: func_buy(); break;
        case 2: shop_refund(); break;
        case 3:
            if (balance > 1000000)
            {
                puts("Only overwhelming capital can overcome everything.");
                flag_print();
            }
            else
                puts("You are not millionaire yet. Keep working to increase your balance.");
            break;
        case 4:
            if (credit_balance() > 100000)
            {
                puts("Only overwhelming credits can overcome everything.");
                flag_print();
            }
            else
                puts("You are not credit rich yet. Keep working to increase your credit balance.");
            break;
        default: puts("Unknown choice."); break;
        }
    }
}

void review_menu(void) {
    const char *const options[] = {
        "Write a review", "Show all reviews", "Edit review text (admin)"
    };
    for (;;) {
        int choice = submenu_choice("Reviews", options, 3);
        switch (choice) {
        case 0: return;
        case 1: review_write(); break;
        case 2: review_show(); break;
        case 3: review_admin_edit(); break;
        }
    }
}
