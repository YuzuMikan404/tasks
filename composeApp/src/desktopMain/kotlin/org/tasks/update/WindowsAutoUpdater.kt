package org.tasks.update

import co.touchlab.kermit.Logger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.tasks.TasksBuildConfig
import java.io.File
import java.net.HttpURLConnection
import java.net.URI
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest

private const val TAG = "WindowsAutoUpdater"
private const val RELEASE_API =
    "https://api.github.com/repos/YuzuMikan404/tasks/releases/latest"
private const val CHECK_INTERVAL_MS = 24L * 60L * 60L * 1000L
private val SHA256 = Regex("(?i)\\b[0-9a-f]{64}\\b")

data class WindowsUpdate(
    val version: String,
    val installer: File,
)

/**
 * Checks the fork's latest GitHub release without delaying application startup. The MSI and its
 * published checksum are downloaded together; an installer is only returned after SHA-256
 * verification succeeds.
 */
suspend fun prepareWindowsUpdate(dataDir: File): WindowsUpdate? = withContext(Dispatchers.IO) {
    val updateDir = File(dataDir, "updates").also { it.mkdirs() }
    val checkedAt = File(updateDir, "last-check")
    if (System.currentTimeMillis() - checkedAt.lastModified() < CHECK_INTERVAL_MS) {
        return@withContext null
    }

    runCatching {
        val release = requestText(RELEASE_API)
        checkedAt.writeText(System.currentTimeMillis().toString())
        val root = Json.parseToJsonElement(release).jsonObject
        val version = root.getValue("tag_name").jsonPrimitive.content
            .removePrefix("windows-v")
        if (compareVersions(version, TasksBuildConfig.VERSION_NAME) <= 0) {
            return@runCatching null
        }

        val assets = root.getValue("assets").jsonArray.map { it.jsonObject }
        val installerName = "tasks-org-windows-x64-$version.msi"
        val checksumName = "tasks-org-windows-x64-$version.sha256"
        val installerUrl = assets.firstOrNull {
            it["name"]?.jsonPrimitive?.content == installerName
        }?.get("browser_download_url")?.jsonPrimitive?.content
            ?: error("Release $version has no $installerName")
        val checksumUrl = assets.firstOrNull {
            it["name"]?.jsonPrimitive?.content == checksumName
        }?.get("browser_download_url")?.jsonPrimitive?.content
            ?: error("Release $version has no $checksumName")
        val expectedHash = SHA256.find(requestText(checksumUrl))?.value?.lowercase()
            ?: error("Release $version has an invalid checksum")

        val installer = File(updateDir, installerName)
        if (!installer.isFile || sha256(installer) != expectedHash) {
            downloadVerified(installerUrl, installer, expectedHash)
        }
        WindowsUpdate(version, installer)
    }.onFailure { error ->
        Logger.w(error, tag = TAG) { "Automatic update check failed" }
    }.getOrNull()
}

/** Starts the verified MSI. The caller should immediately begin the application's normal close. */
fun launchWindowsUpdate(update: WindowsUpdate): Boolean = runCatching {
    ProcessBuilder(
        "msiexec.exe",
        "/i",
        update.installer.absolutePath,
        "/passive",
        "/norestart",
    ).start()
    true
}.onFailure { error ->
    Logger.e(error, tag = TAG) { "Could not launch Windows update ${update.version}" }
}.getOrDefault(false)

internal fun compareVersions(left: String, right: String): Int {
    val leftParts = left.split('.', '-', '_').map { it.toIntOrNull() ?: 0 }
    val rightParts = right.split('.', '-', '_').map { it.toIntOrNull() ?: 0 }
    for (index in 0 until maxOf(leftParts.size, rightParts.size)) {
        val comparison = (leftParts.getOrNull(index) ?: 0)
            .compareTo(rightParts.getOrNull(index) ?: 0)
        if (comparison != 0) return comparison
    }
    return 0
}

private fun requestText(url: String): String = open(url).run {
    inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
}

private fun downloadVerified(url: String, destination: File, expectedHash: String) {
    val temporary = File(destination.parentFile, "${destination.name}.part")
    try {
        open(url).inputStream.use { input ->
            temporary.outputStream().buffered().use(input::copyTo)
        }
        check(sha256(temporary) == expectedHash) { "Downloaded MSI checksum mismatch" }
        try {
            Files.move(
                temporary.toPath(),
                destination.toPath(),
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING,
            )
        } catch (_: Exception) {
            Files.move(
                temporary.toPath(),
                destination.toPath(),
                StandardCopyOption.REPLACE_EXISTING,
            )
        }
    } finally {
        temporary.delete()
    }
}

private fun open(url: String): HttpURLConnection =
    (URI(url).toURL().openConnection() as HttpURLConnection).apply {
        connectTimeout = 10_000
        readTimeout = 60_000
        instanceFollowRedirects = true
        setRequestProperty("Accept", "application/vnd.github+json")
        setRequestProperty("User-Agent", "Tasks.org-Windows/${TasksBuildConfig.VERSION_NAME}")
        check(responseCode in 200..299) { "HTTP $responseCode from $url" }
    }

private fun sha256(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().buffered().use { input ->
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            digest.update(buffer, 0, read)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}
