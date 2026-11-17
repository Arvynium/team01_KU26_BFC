#include "bfc.h"

#include <inttypes.h>

_Atomic uint32_t credits = 10;
uint32_t balance = 1000;

void credit_add(uint32_t quantity) {
    atomic_fetch_add(&credits, quantity);
}

uint32_t credit_balance(void) {
    return atomic_load(&credits);
}

int credit_use(void) {
    if (credit_balance() == 0) {
        puts("Insufficient credits. Buy credits before parsing XML.");
        return 0;
    }
    atomic_fetch_sub(&credits, 1);
    printf("Used 1 credit; remaining credits=%" PRIu32 "\n", credit_balance());
    return 1;
}

void shop_refund(void) {
    const uint32_t unit_price = 100;
    int32_t quantity;
    puts("Refund: $100 per XML parsing credit.");
    if (!scanf("%d", &quantity))
        return;
    if (quantity < 0) {
        quantity = -quantity;
    }
    if (quantity > (int32_t)credit_balance()) {
        puts("Insufficient credits to refund.");
        return;
    }
    uint32_t total = quantity * unit_price;
    atomic_fetch_sub(&credits, quantity);
    balance += total;
    printf("Refunded %u parsing credits for %u; remaining credits=%" PRIu32
           "; balance=$%" PRIu32 "\n",
           (unsigned int)quantity, (unsigned int)total, credit_balance(), balance);
}
