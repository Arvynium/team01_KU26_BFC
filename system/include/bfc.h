#ifndef BFC_H
#define BFC_H

#include <stddef.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>

extern _Atomic uint32_t credits;
extern uint32_t balance;

enum { REVIEW_CAPACITY = 10 };

typedef struct Review {
    char name[16];
    int star;
    char review_text[40];
} Rev;

/* Keep the admin string after the ten reviews in one global object. */
typedef struct {
    Rev reviews[REVIEW_CAPACITY];
    char check_admin[9];
} ReviewStorage;

extern ReviewStorage review_storage;

typedef struct {
    char *data;
    size_t length;
} Document;

char *read_line(const char *prompt);
int read_u32(const char *prompt, uint32_t *value);
int document_edit(Document *document);
int document_append(Document *document, const char *data, size_t length);
int document_load(Document *document, FILE *stream);
void document_save_file(const Document *document);
void document_open_file(Document *document);
void document_show(const Document *document);
void document_clear(Document *document);
int document_parse(const Document *document);
void document_print_summary(size_t elements, const char *title, const char *description);
void memory_menu(Document *document);
void file_menu(Document *document);
void parser_menu(Document *document);
void credit_menu(void);
void review_menu(void);
void review_write(void);
void review_show(void);
void review_admin_edit(void);
void credit_add(uint32_t quantity);
uint32_t credit_balance(void);
int credit_use(void);
void shop_refund(void);
void func_buy(void);
void func_wait(void);
uint32_t balance_read(void);

#endif
