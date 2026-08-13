package org.tasks.auth

import com.sun.net.httpserver.HttpServer
import kotlinx.coroutines.CancellableContinuation
import java.net.InetSocketAddress
import kotlin.coroutines.resumeWithException

/**
 * Fork-only OAuth loopback-server hardening, kept in a file upstream never creates so future
 * upstream merges cannot touch these lines. DesktopOAuthFlow.kt should only ever call these as a
 * single-line substitution for upstream's own call, so a future upstream change to that call
 * (e.g. a renamed parameter) merges as an ordinary one-line-vs-one-line diff instead of
 * conflicting with a multi-line fork block. See WINDOWS_FORK.md.
 */

/** Creates the loopback HTTP server, or resumes [cont] with the failure and returns null. */
internal fun createLoopbackServerOrNull(
    cont: CancellableContinuation<*>,
    host: String,
): HttpServer? =
    try {
        HttpServer.create(InetSocketAddress(host, 0), 0)
    } catch (e: Exception) {
        cont.resumeWithException(e)
        null
    }

/**
 * Runs [block], or stops [server] and resumes [cont] with the failure (only if still active) and
 * returns null.
 */
internal inline fun <T> runOnReadyOrNull(
    cont: CancellableContinuation<*>,
    server: HttpServer,
    block: () -> T,
): T? =
    try {
        block()
    } catch (e: Throwable) {
        server.stop(0)
        if (cont.isActive) {
            cont.resumeWithException(e)
        }
        null
    }
