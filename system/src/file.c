#include "bfc.h"

#include <dirent.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static int valid_xml_filename(const char *name) {
    size_t length = strlen(name);
    if (length < 5 || length > 128 || name[0] == '.' ||
        strcmp(name + length - 4, ".xml") != 0)
        return 0;

    for (size_t i = 0; name[i] != '\0'; i++) {
        char c = name[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.')
            continue;
        return 0;
    }
    return 1;
}

static char *read_filename(void) {
    char *name = read_line("XML filename (e.g. document.xml): ");
    if (!name)
        return NULL;
    if (!valid_xml_filename(name)) {
        puts("Use a name ending in .xml with letters, digits, _, - or .; no paths.");
        free(name);
        return NULL;
    }
    return name;
}

static int list_xml_files(void) {
    DIR *directory = opendir(".");
    if (!directory) {
        perror("Cannot list XML files");
        return 0;
    }

    puts("Available XML files:");
    int found = 0;
    struct dirent *entry;
    while ((entry = readdir(directory)) != NULL) {
        if (!valid_xml_filename(entry->d_name))
            continue;
        struct stat info;
        if (stat(entry->d_name, &info) != 0 || !S_ISREG(info.st_mode))
            continue;
        printf("  %s\n", entry->d_name);
        found = 1;
    }
    closedir(directory);
    if (!found)
        puts("No XML files found. Save an XML file first.");
    return found;
}

void document_save_file(const Document *document) {
    char *name = read_filename();
    if (!name)
        return;
    FILE *stream = fopen(name, "wb");
    if (!stream) {
        perror("Cannot save XML file");
        free(name);
        return;
    }
    int ok = document->length == 0 ||
             fwrite(document->data, 1, document->length, stream) == document->length;
    if (fclose(stream) != 0)
        ok = 0;
    if (ok)
        printf("Saved %zu bytes to %s.\n", document->length, name);
    else
        fputs("Could not write the complete XML file.\n", stderr);
    free(name);
}

void document_open_file(Document *document) {
    if (!list_xml_files())
        return;
    char *name = read_filename();
    if (!name)
        return;
    FILE *stream = fopen(name, "rb");
    if (!stream) {
        perror("Cannot open XML file");
        free(name);
        return;
    }
    int ok = document_load(document, stream);
    fclose(stream);
    if (ok)
        printf("Loaded %zu bytes from %s into memory.\n",
               document->length, name);
    else
        fputs("Cannot read XML file; memory document unchanged.\n", stderr);
    free(name);
}
