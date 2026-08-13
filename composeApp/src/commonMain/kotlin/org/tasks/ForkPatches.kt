package org.tasks

import org.tasks.compose.accounts.Platform

/**
 * Fork-only patch surface. Kept in a file upstream never creates, so future upstream merges
 * cannot touch these lines and cannot conflict with them. See WINDOWS_FORK.md.
 *
 * Call sites in upstream files should only ever gain a single, additive boolean clause
 * (e.g. `&& !platform.isForkEntitlementExempt()`) rather than rewriting upstream's own
 * conditionals or `when` blocks. That keeps the diff against upstream to one stable line,
 * instead of a growing list upstream is also actively editing every release.
 */

/**
 * Platforms this fork keeps free of the Tasks.org Cloud entitlement gate. CalDAV and EteSync are
 * independent, self-hosted-capable protocols, so this fork does not require a subscription for
 * them. Anything upstream adds later (e.g. a new proprietary sync provider) is gated by default,
 * with no patch required here unless the fork wants to exempt it too.
 */
private val FORK_EXEMPT_PLATFORMS: Set<Platform> = setOf(Platform.CALDAV, Platform.ETEBASE)

fun Platform.isForkEntitlementExempt(): Boolean = this in FORK_EXEMPT_PLATFORMS
