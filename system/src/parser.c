#include "bfc.h"

#include <expat.h>
#include <string.h>

#define XML_PARSE_CHUNK 256

enum { FIELD_NONE, FIELD_TITLE, FIELD_DESCRIPTION };

typedef struct {
    XML_Parser parser;
    size_t elements;
    size_t depth;
    int field;
    int title_seen;
    int description_seen;
    int memory_error;
    Document title;
    Document description;
} ParseState;

static void print_xml_name(const XML_Char *name) {
    printf("[XML name] ");

    for (const unsigned char *p = (const unsigned char *)name; *p; p++) {
        if (*p == '\n')
            printf("\\n");
        else if (*p == '\r')
            printf("\\r");
        else if (*p == '\t')
            printf("\\t");
        else if (*p >= 0x20 && *p <= 0x7e)
            putchar(*p);
        else
            printf("\\x%02x", *p);
    }

    putchar('\n');
}

static void XMLCALL start_element(void *context, const XML_Char *name,
                                 const XML_Char **attributes) {
    ParseState *state = context;
    (void)attributes;
    print_xml_name(name);
    state->elements++;
    state->depth++;

    if (state->depth == 2) {
        if (strcmp(name, "title") == 0 && !state->title_seen) {
            state->title_seen = 1;
            state->field = FIELD_TITLE;
        } else if (strcmp(name, "description") == 0 && !state->description_seen) {
            state->description_seen = 1;
            state->field = FIELD_DESCRIPTION;
        }
    }
}

static void XMLCALL end_element(void *context, const XML_Char *name) {
    ParseState *state = context;
    (void)name;
    if (state->depth == 2)
        state->field = FIELD_NONE;
    state->depth--;
}

static void XMLCALL text_data(void *context, const XML_Char *text, int length) {
    ParseState *state = context;
    Document *field;
    if (state->field == FIELD_TITLE)
        field = &state->title;
    else if (state->field == FIELD_DESCRIPTION)
        field = &state->description;
    else
        return;

    if (!document_append(field, text, (size_t)length)) {
        state->memory_error = 1;
        XML_StopParser(state->parser, XML_FALSE);
    }
}
static void XMLCALL element_decl(void *context, const XML_Char *name, XML_Content *model) {
    ParseState *state = context;

    (void)name;
    XML_FreeContentModel(state->parser, model);
}

int document_parse(const Document *document) {
    if (!credit_use())
        return 0;
    XML_Parser parser = XML_ParserCreateNS(NULL, '\n');
    if (!parser) {
        fputs("Cannot create XML parser.\n", stderr);
        return 0;
    }
    ParseState state = {0};
    state.parser = parser;
    XML_SetUserData(parser, &state);
    XML_SetElementHandler(parser, start_element, end_element);
    XML_SetCharacterDataHandler(parser, text_data);
    XML_SetElementDeclHandler(parser, element_decl);
    XML_SetParamEntityParsing(parser, XML_PARAM_ENTITY_PARSING_ALWAYS);

    size_t offset = 0;
    int ok = 1;
    do {
        size_t remaining = document->length - offset;
        int chunk = remaining > XML_PARSE_CHUNK ? XML_PARSE_CHUNK : (int)remaining;
        int final = (size_t)chunk == remaining;
        const char *data = document->data ? document->data + offset : "";
        if (XML_Parse(parser, data, chunk, final) == XML_STATUS_ERROR) {
            if (state.memory_error)
                fputs("Cannot allocate XML summary memory.\n", stderr);
            else
                fprintf(stderr, "XML error at line %lu, column %lu: %s\n",
                        (unsigned long)XML_GetCurrentLineNumber(parser),
                        (unsigned long)XML_GetCurrentColumnNumber(parser),
                        XML_ErrorString(XML_GetErrorCode(parser)));
            ok = 0;
            break;
        }
        offset += (size_t)chunk;
    } while (offset < document->length);

    if (ok) {
        const char *title = NULL;
        const char *description = NULL;
        if (state.title_seen)
            title = state.title.data ? state.title.data : "";
        if (state.description_seen)
            description = state.description.data ? state.description.data : "";
        document_print_summary(state.elements, title, description);
    }
    XML_ParserFree(parser);
    document_clear(&state.title);
    document_clear(&state.description);
    return ok;
}
