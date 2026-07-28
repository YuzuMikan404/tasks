package org.tasks.di

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PurchaseStateTest {
    @Test
    fun libreDesktopHasProWithoutSubscription() {
        assertTrue(
            hasProAccess(
                isLibre = true,
                hasTasksAccount = false,
                hasSubscription = false,
            )
        )
    }

    @Test
    fun regularDesktopRequiresEntitlement() {
        assertFalse(
            hasProAccess(
                isLibre = false,
                hasTasksAccount = false,
                hasSubscription = false,
            )
        )
    }

    @Test
    fun regularDesktopAcceptsRealSubscription() {
        assertTrue(
            hasProAccess(
                isLibre = false,
                hasTasksAccount = false,
                hasSubscription = true,
            )
        )
    }
}
