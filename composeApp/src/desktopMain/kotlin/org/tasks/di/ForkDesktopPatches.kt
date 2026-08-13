package org.tasks.di

import org.tasks.PlatformConfiguration

/**
 * Fork-only patch, kept in a file upstream never creates. Applied after construction so
 * DesktopModule.kt's own named-argument list — which upstream actively grows every release
 * (e.g. supportsMicrosoft in 15.9) — never needs a fork-only line inside it. See
 * WINDOWS_FORK.md.
 */
fun PlatformConfiguration.asForkLibreBuild(): PlatformConfiguration = copy(isLibre = true)
