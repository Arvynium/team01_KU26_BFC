#include "bfc.h"

#include <inttypes.h>
#include <pthread.h>
#include <string.h>
#include <unistd.h>

typedef struct {
    pthread_t thread;
    int active;
    atomic_bool done;
} Checkout;

static Checkout workers[2];
static pthread_mutex_t balance_mutex = PTHREAD_MUTEX_INITIALIZER;

uint32_t balance_read(void) {
    pthread_mutex_lock(&balance_mutex);
    uint32_t current = balance;
    pthread_mutex_unlock(&balance_mutex);
    return current;
}

static void *buy_credit(void *arg) {
    Checkout *checkout = arg;
    int approved = balance_read() >= 100;
    if (approved)
        usleep(100000);

    pthread_mutex_lock(&balance_mutex);
    if (approved) {
        balance -= 100;
        credit_add(1);
    } else {
        puts("Insufficient balance to buy credits.");
    }
    printf("Checkout: credits=%" PRIu32 " balance=%" PRIu32 "\n",
           credit_balance(), balance);
    pthread_mutex_unlock(&balance_mutex);
    atomic_store(&checkout->done, 1);
    return NULL;
}

void func_wait(void) {
    for (size_t i = 0; i < 2; i++) {
        if (workers[i].active) {
            pthread_join(workers[i].thread, NULL);
            workers[i].active = 0;
        }
    }
}

void func_buy(void) {
    Checkout *available = NULL;
    for (size_t i = 0; i < 2; i++) {
        if (workers[i].active && atomic_load(&workers[i].done)) {
            pthread_join(workers[i].thread, NULL);
            workers[i].active = 0;
        }
        if (!workers[i].active && !available)
            available = &workers[i];
    }
    if (!available) {
        puts("Two purchases are already pending. Try again after they finish.");
        return;
    }
    atomic_store(&available->done, 0);
    int error = pthread_create(&available->thread, NULL, buy_credit, available);
    if (error != 0) {
        fprintf(stderr, "Cannot create worker: %s\n", strerror(error));
        return;
    }
    available->active = 1;
    puts("Purchase started.");
}
