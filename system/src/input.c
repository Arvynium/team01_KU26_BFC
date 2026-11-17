#include "bfc.h"

#include <stdlib.h>

char *read_line(const char *prompt) {
    char *line = NULL;
    size_t capacity = 0;
    printf("%s", prompt);
    ssize_t length = getline(&line, &capacity, stdin);
    if (length < 0) {
        free(line);
        return NULL;
    }
    if (length > 0 && line[length - 1] == '\n')
        line[--length] = '\0';
    if (length > 0 && line[length - 1] == '\r')
        line[--length] = '\0';
    return line;
}

int read_u32(const char *prompt, uint32_t *value) {
    char *line = read_line(prompt);
    if (!line)
        return 0;
    if (line[0] == '\0') {
        puts("Enter an unsigned 32-bit decimal number.");
        free(line);
        return 0;
    }
    uint64_t number = 0;
    for (size_t i = 0; line[i] != '\0'; i++) {
        if (line[i] < '0' || line[i] > '9') {
            puts("Enter an unsigned 32-bit decimal number.");
            free(line);
            return 0;
        }
        number = number * 10 + (line[i] - '0');
        if (number > UINT32_MAX) {
            puts("Number out of range.");
            free(line);
            return 0;
        }
    }
    free(line);
    *value = (uint32_t)number;
    return 1;
}
