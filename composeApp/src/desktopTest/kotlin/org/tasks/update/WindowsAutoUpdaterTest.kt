package org.tasks.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WindowsAutoUpdaterTest {
    @Test
    fun comparesNumericReleaseVersions() {
        assertTrue(compareVersions("15.11", "15.9.1") > 0)
        assertTrue(compareVersions("16.0", "15.11") > 0)
        assertTrue(compareVersions("15.10", "15.11") < 0)
    }

    @Test
    fun ignoresInsignificantTrailingZeroes() {
        assertEquals(0, compareVersions("15.11", "15.11.0"))
    }

    @Test
    fun checksumAssetNameIncludesInstallerExtension() {
        assertEquals(
            "tasks-org-windows-x64-15.13.msi.sha256",
            checksumAssetName("tasks-org-windows-x64-15.13.msi"),
        )
        assertEquals(
            "tasks-org-linux-x64-15.13.deb.sha256",
            checksumAssetName("tasks-org-linux-x64-15.13.deb"),
        )
    }
}
