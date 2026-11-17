#include "bfc.h"
#include <string.h>

ReviewStorage review_storage = {
    .reviews = {
        [0] = {
            .name = "Tony",
            .star = 5,
            .review_text = "Review: This is AWESOME Program!!"
        }
    },
    .check_admin = "USER1"
};
static int user_review_written;

static void finish_review_input(void) {
    int ch;
    while ((ch = getchar()) != '\n' && ch != EOF) {}
}

static int scan_review_string(const char *prompt, char *destination) {
    char temp[40];
    const char prefix[] = "Review: ";
    size_t prefix_len = sizeof(prefix) - 1;

    printf("%s", prompt);

    size_t n = 0;

    while (n < 40) {
        int c = getchar();

        if (c == EOF || c == '\n')
            break;

        temp[n++] = (unsigned char)c;
    }
    if (n <= 0)
    return 0;

    if (n == 40)
    finish_review_input();

    memcpy(destination, prefix, prefix_len);
    memcpy(destination + prefix_len, temp, n);

    return 1;
}

static int scan_review_name(const char *prompt, char *name) {
    printf("%s", prompt);
    return scanf("%15s", name) == 1;
}

static int scan_review_int(const char *prompt, int *number) {
    printf("%s", prompt);
    return scanf("%d", number) == 1;
}

void review_write(void) {
    if (user_review_written) {
        puts("You can write only one review per session.");
        return;
    }
    int index;
    if (!scan_review_int("Review index (0-9): ", &index))
        goto done;
    Rev *review = &review_storage.reviews[index];
    if (review->name[0] != '\0') {
        puts("This review slot has already been written.");
        goto done;
    }

    /* Commit only after every field has been read. */
    if (!scan_review_name("Name: ", review->name))
        goto done;
    if (!scan_review_int("Stars (1-5): ", &review->star))
        goto done;
    finish_review_input();
    if (!scan_review_string("Review text : ", review->review_text))
        goto done;
    user_review_written = 1;
    printf("Review saved at index %d.\n", index);
    return;
done:
    finish_review_input();
}

void review_show(void) {
    for (int i = 0; i < REVIEW_CAPACITY; i++) {
        const Rev *review = &review_storage.reviews[i];
        if (review->name[0] == '\0') {
            printf("[%d] Empty\n", i);
            continue;
        }
        printf("[%d] Name: %s | Stars: %d | %s\n",
               i, review->name, review->star, review->review_text);
    }
}

void review_admin_edit(void) {
    if (strcmp(review_storage.check_admin, "IAMADMIN") != 0) {
        puts("Admin access required.");
        return;
    }
    int index;
    if (!scan_review_int("Review index (0-9): ", &index))
        goto done;
    Rev *review = &review_storage.reviews[index];
    printf("Edit?: ");
    if (scanf("%40s", review->review_text) == 1)
        puts("Review text updated.");
done:
    finish_review_input();
}
