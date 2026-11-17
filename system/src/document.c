#include "bfc.h"

#include <stdlib.h>
#include <string.h>

int document_append(Document *document, const char *data, size_t length) {
    if (document->length == SIZE_MAX ||
        length > SIZE_MAX - document->length - 1)
        return 0;
    char *buffer = realloc(document->data, document->length + length + 1);
    if (!buffer)
        return 0;
    memcpy(buffer + document->length, data, length);
    document->length += length;
    buffer[document->length] = '\0';
    document->data = buffer;
    return 1;
}

void document_clear(Document *document) {
    free(document->data);
    document->data = NULL;
    document->length = 0;
}

int document_edit(Document *document) {
    Document draft = {0};
    puts("Enter XML; a line containing only . stores it in memory.");
    for (;;) {
        char *line = read_line("xml> ");
        if (!line) {
            puts("Input ended; draft discarded.");
            document_clear(&draft);
            return 0;
        }
        if (strcmp(line, ".") == 0) {
            free(line);
            break;
        }
        int ok = document_append(&draft, line, strlen(line)) &&
                 document_append(&draft, "\n", 1);
        free(line);
        if (!ok) {
            puts("Cannot allocate document memory.");
            document_clear(&draft);
            return 0;
        }
    }
    document_clear(document);
    *document = draft;
    printf("Saved %zu bytes in memory.\n", document->length);
    return 1;
}

int document_load(Document *document, FILE *stream) {
    Document draft = {0};
    char buffer[8192];
    size_t length;
    while ((length = fread(buffer, 1, sizeof(buffer), stream)) > 0) {
        if (!document_append(&draft, buffer, length)) {
            document_clear(&draft);
            return 0;
        }
    }
    if (ferror(stream)) {
        document_clear(&draft);
        return 0;
    }
    document_clear(document);
    *document = draft;
    return 1;
}

void document_show(const Document *document) {
    printf("Document: %zu bytes\n", document->length);
    if (document->length)
        fwrite(document->data, 1, document->length, stdout);
    putchar('\n');
}
