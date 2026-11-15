package io.vngkzxq.mprt.core.root

import android.content.Context
import android.os.Build
import io.vngkzxq.mprt.R
import io.vngkzxq.mprt.core.i18n.tr
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader

data class ScriptRunState(
    val started: Boolean = false,
    val running: Boolean = false,
    val usedRoot: Boolean = true,
    val exitCode: Int? = null,
    val output: String = "",
    val elapsedMs: Long = 0L,
    val errorMessage: String? = null,
)

class ScriptRunController {

    private val _state = MutableStateFlow(ScriptRunState())
    val state: StateFlow<ScriptRunState> = _state.asStateFlow()

    @Volatile
    private var process: Process? = null

    @Volatile
    private var activeJob: Job? = null

    @Volatile
    private var stoppedByUser: Boolean = false

    fun start(
        context: Context,
        scope: CoroutineScope,
        path: String,
        argsText: String,
        useRoot: Boolean,
    ) {
        stop()
        stoppedByUser = false
        _state.value = ScriptRunState(
            started = true,
            running = true,
            usedRoot = useRoot,
            output = "",
        )

        val appCtx = context.applicationContext
        activeJob = scope.launch(Dispatchers.IO) {
            val startMs = System.currentTimeMillis()
            var tempScript: File? = null
            try {
                if (useRoot && !RootManager.request()) {
                    val denied = tr(R.string.script_root_denied)
                    _state.value = ScriptRunState(
                        started = true,
                        running = false,
                        usedRoot = true,
                        exitCode = 126,
                        output = "$denied\n",
                        elapsedMs = System.currentTimeMillis() - startMs,
                        errorMessage = denied,
                    )
                    return@launch
                }

                val targetFile = File(path)
                val localReadable = runCatching { targetFile.isFile && targetFile.canRead() }.getOrDefault(false)
                if (!localReadable && !useRoot) {
                    val msg = tr(R.string.script_cannot_read, path)
                    _state.value = ScriptRunState(
                        started = true,
                        running = false,
                        usedRoot = false,
                        exitCode = 1,
                        output = "$msg\n",
                        elapsedMs = System.currentTimeMillis() - startMs,
                        errorMessage = msg,
                    )
                    return@launch
                }

                if (localReadable) {
                    val raw = targetFile.readText(Charsets.UTF_8)
                    val normalized = raw.replace("\r\n", "\n").replace('\r', '\n')
                    tempScript = File.createTempFile("toolshear_script_", ".sh", appCtx.cacheDir).apply {
                        writeText(normalized, Charsets.UTF_8)
                    }
                }

                val args = parseArgs(argsText)
                val shellCmd = buildShellCommand(
                    originalPath = path,
                    stagedTempPath = tempScript?.absolutePath,
                    args = args,
                    useRoot = useRoot,
                )

                val proc = ProcessBuilder(if (useRoot) "su" else "/system/bin/sh")
                    .redirectErrorStream(true)
                    .start()
                process = proc

                proc.outputStream.bufferedWriter(Charsets.UTF_8).use { writer ->
                    writer.write(shellCmd)
                    writer.newLine()
                    writer.flush()
                }

                val sb = StringBuilder()
                var truncated = false
                var lastEmit = 0L

                BufferedReader(InputStreamReader(proc.inputStream, Charsets.UTF_8)).use { reader ->
                    while (true) {
                        val line = reader.readLine() ?: break
                        if (!truncated) {
                            if (sb.length + line.length + 1 <= MAX_OUTPUT_CHARS) {
                                sb.append(line).append('\n')
                            } else {
                                sb.append("\n... [output truncated at ").append(MAX_OUTPUT_CHARS).append(" chars]\n")
                                truncated = true
                            }
                        }
                        val now = System.currentTimeMillis()
                        if (now - lastEmit >= 50L) {
                            lastEmit = now
                            _state.value = _state.value.copy(
                                output = sb.toString(),
                                elapsedMs = now - startMs,
                            )
                        }
                    }
                }

                val code = proc.waitFor()
                val elapsed = System.currentTimeMillis() - startMs
                _state.value = ScriptRunState(
                    started = true,
                    running = false,
                    usedRoot = useRoot,
                    exitCode = code,
                    output = sb.toString(),
                    elapsedMs = elapsed,
                    errorMessage = if (stoppedByUser) tr(R.string.script_status_stopped) else null,
                )
            } catch (t: Throwable) {
                val elapsed = System.currentTimeMillis() - startMs
                val err = t.message ?: t.javaClass.simpleName
                val existing = _state.value.output
                val merged = if (existing.isEmpty()) "$err\n" else "$existing\n$err\n"
                _state.value = ScriptRunState(
                    started = true,
                    running = false,
                    usedRoot = useRoot,
                    exitCode = if (stoppedByUser) 130 else 1,
                    output = merged,
                    elapsedMs = elapsed,
                    errorMessage = if (stoppedByUser) tr(R.string.script_status_stopped) else err,
                )
            } finally {
                process = null
                runCatching { tempScript?.delete() }
            }
        }
    }

    fun stop() {
        stoppedByUser = true
        val p = process
        if (p != null) {
            runCatching {
                p.destroy()
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && p.isAlive) {
                    p.destroyForcibly()
                }
            }
        }
        activeJob?.cancel()
        activeJob = null
        if (_state.value.running) {
            _state.value = _state.value.copy(
                running = false,
                errorMessage = tr(R.string.script_status_stopped),
            )
        }
    }

    companion object {
        private const val MAX_OUTPUT_CHARS = 512 * 1024

        private const val STANDARD_PATH =
            "/data/adb/ksu/bin:/data/adb/ap/bin:/data/adb/magisk:/sbin:/system/bin:/system/xbin:/vendor/bin:/product/bin"

        internal fun parseArgs(raw: String): List<String> {
            val out = mutableListOf<String>()
            val cur = StringBuilder()
            var quote: Char? = null
            var escaped = false
            var hasToken = false

            for (ch in raw) {
                when {
                    escaped -> {
                        cur.append(ch)
                        escaped = false
                        hasToken = true
                    }
                    ch == '\\' && quote != '\'' -> {
                        escaped = true
                        hasToken = true
                    }
                    quote != null -> {
                        if (ch == quote) {
                            quote = null
                        } else {
                            cur.append(ch)
                        }
                        hasToken = true
                    }
                    ch == '\'' || ch == '"' -> {
                        quote = ch
                        hasToken = true
                    }
                    ch.isWhitespace() -> {
                        if (hasToken) {
                            out.add(cur.toString())
                            cur.setLength(0)
                            hasToken = false
                        }
                    }
                    else -> {
                        cur.append(ch)
                        hasToken = true
                    }
                }
            }
            if (escaped) cur.append('\\')
            if (hasToken) out.add(cur.toString())
            return out
        }

        internal fun buildShellCommand(
            originalPath: String,
            stagedTempPath: String?,
            args: List<String>,
            useRoot: Boolean,
        ): String {
            val origFile = File(originalPath)
            val parent = origFile.parent ?: "/"
            val qOrig = RootCommands.quote(originalPath)
            val qDir = RootCommands.quote(parent)
            val qPathEnv = RootCommands.quote(STANDARD_PATH)
            val qArgs = args.joinToString(" ") { RootCommands.quote(it) }

            return buildString {
                append("PATH=").append(qPathEnv).append(":\"$").append("PATH\"\n")
                append("export PATH\n")
                append("SCRIPT_FILE=").append(qOrig).append('\n')
                append("SCRIPT_DIR=").append(qDir).append('\n')
                append("export SCRIPT_FILE SCRIPT_DIR\n")
                append("cd ").append(qDir).append(" 2>/dev/null || true\n")
                append("set --")
                if (qArgs.isNotEmpty()) append(' ').append(qArgs)
                append('\n')

                if (stagedTempPath != null) {
                    val qStaged = RootCommands.quote(stagedTempPath)
                    append("/system/bin/sh ").append(qStaged).append(" \"$@\"\n")
                    append("exit $?\n")
                } else {
                    append("_ts_tmp=$(mktemp /data/local/tmp/toolshear_XXXXXX.sh 2>/dev/null || echo /data/local/tmp/toolshear_$$.sh)\n")
                    append("if command -v tr >/dev/null 2>&1; then\n")
                    append("  tr -d '\\r' < \"$SCRIPT_FILE\" > \"$_ts_tmp\"\n")
                    append("else\n")
                    append("  cat \"$SCRIPT_FILE\" > \"$_ts_tmp\"\n")
                    append("fi\n")
                    append("if [ -s \"$_ts_tmp\" ] || [ -f \"$SCRIPT_FILE\" ]; then\n")
                    append("  /system/bin/sh \"$_ts_tmp\" \"$@\"\n")
                    append("  _ts_rc=$?\n")
                    append("  rm -f \"$_ts_tmp\"\n")
                    append("  exit $_ts_rc\n")
                    append("else\n")
                    append("  rm -f \"$_ts_tmp\"\n")
                    append("  /system/bin/sh \"$SCRIPT_FILE\" \"$@\"\n")
                    append("  exit $?\n")
                    append("fi\n")
                }
            }
        }

        internal fun formatElapsed(ms: Long): String = when {
            ms < 1000L -> "${ms}ms"
            ms < 60_000L -> String.format(java.util.Locale.ROOT, "%.2fs", ms / 1000.0)
            else -> {
                val secs = ms / 1000L
                "${secs / 60}m ${secs % 60}s"
            }
        }
    }
}
