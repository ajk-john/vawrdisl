package io.vngkzxq.mprt.feature.script

import android.content.ClipData
import android.content.ClipboardManager
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material.icons.rounded.Terminal
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.vngkzxq.mprt.R
import io.vngkzxq.mprt.core.root.ScriptRunController
import io.vngkzxq.mprt.ui.isolated
import java.io.File

@Composable
fun ScriptRunnerDialog(
    path: String,
    initialRoot: Boolean = true,
    onEdit: (() -> Unit)? = null,
    onBeforeRun: (((() -> Unit) -> Unit))? = null,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val controller = remember(path) { ScriptRunController() }
    val state by controller.state.collectAsStateWithLifecycle()

    var useRoot by rememberSaveable(path) { mutableStateOf(initialRoot) }
    var argsText by rememberSaveable(path) { mutableStateOf("") }
    var copiedNotice by remember { mutableStateOf(false) }

    val scrollState = rememberScrollState()
    LaunchedEffect(state.output.length, state.running) {
        if (scrollState.maxValue > 0) {
            scrollState.scrollTo(scrollState.maxValue)
        }
    }

    LaunchedEffect(copiedNotice) {
        if (copiedNotice) {
            kotlinx.coroutines.delay(1800L)
            copiedNotice = false
        }
    }

    DisposableEffect(controller) {
        onDispose { controller.stop() }
    }

    fun triggerExecute() {
        copiedNotice = false
        val runAction = { controller.start(context, scope, path, argsText, useRoot) }
        if (onBeforeRun != null) onBeforeRun(runAction) else runAction()
    }

    val fileName = remember(path) { File(path).name.ifBlank { path } }
    val colors = MaterialTheme.colorScheme

    Dialog(
        onDismissRequest = {
            controller.stop()
            onDismiss()
        },
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.94f)
                .widthIn(max = 600.dp)
                .heightIn(max = 740.dp),
            shape = RoundedCornerShape(24.dp),
            color = colors.surfaceContainerHigh,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = if (useRoot) colors.primaryContainer else colors.secondaryContainer,
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Terminal,
                            contentDescription = null,
                            tint = if (useRoot) colors.onPrimaryContainer else colors.onSecondaryContainer,
                            modifier = Modifier.padding(10.dp).size(22.dp),
                        )
                    }
                    Column(Modifier.weight(1f)) {
                        Text(
                            text = isolated(fileName),
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            text = path,
                            style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                            color = colors.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Surface(
                        shape = RoundedCornerShape(999.dp),
                        color = if (useRoot) colors.errorContainer else colors.secondaryContainer,
                    ) {
                        Text(
                            text = stringResource(if (useRoot) R.string.script_mode_root else R.string.script_mode_shell),
                            style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.SemiBold),
                            color = if (useRoot) colors.onErrorContainer else colors.onSecondaryContainer,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                        )
                    }
                }

                HorizontalDivider(color = colors.outlineVariant.copy(alpha = 0.6f))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column(Modifier.weight(1f).padding(end = 12.dp)) {
                        Text(
                            text = stringResource(R.string.script_use_root),
                            style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                        )
                        Text(
                            text = stringResource(R.string.script_use_root_summary),
                            style = MaterialTheme.typography.bodySmall,
                            color = colors.onSurfaceVariant,
                        )
                    }
                    Switch(
                        checked = useRoot,
                        onCheckedChange = { useRoot = it },
                        enabled = !state.running,
                    )
                }

                OutlinedTextField(
                    value = argsText,
                    onValueChange = { argsText = it },
                    enabled = !state.running,
                    singleLine = true,
                    label = { Text(stringResource(R.string.script_args_label)) },
                    placeholder = { Text(stringResource(R.string.script_args_hint)) },
                    textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
                    modifier = Modifier.fillMaxWidth(),
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = stringResource(R.string.script_output_label),
                            style = MaterialTheme.typography.labelLarge,
                            color = colors.onSurfaceVariant,
                        )
                        when {
                            state.running -> {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(14.dp),
                                    strokeWidth = 2.dp,
                                )
                                Text(
                                    text = stringResource(R.string.script_status_running),
                                    style = MaterialTheme.typography.labelMedium,
                                    color = colors.primary,
                                )
                            }
                            !state.started -> {
                                Text(
                                    text = stringResource(R.string.script_status_ready),
                                    style = MaterialTheme.typography.labelMedium,
                                    color = colors.onSurfaceVariant,
                                )
                            }
                            state.exitCode != null -> {
                                val code = state.exitCode!!
                                val elapsed = ScriptRunController.formatElapsed(state.elapsedMs)
                                val statusColor = if (code == 0) colors.primary else colors.error
                                Text(
                                    text = stringResource(R.string.script_status_done, code, elapsed),
                                    style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Medium),
                                    color = statusColor,
                                )
                            }
                        }
                    }

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (copiedNotice) {
                            Text(
                                text = stringResource(R.string.script_output_copied),
                                style = MaterialTheme.typography.labelSmall,
                                color = colors.primary,
                                modifier = Modifier.padding(end = 4.dp),
                            )
                        }
                        IconButton(
                            onClick = {
                                val cm = context.getSystemService(ClipboardManager::class.java)
                                cm?.setPrimaryClip(ClipData.newPlainText(fileName, state.output))
                                copiedNotice = true
                            },
                            enabled = state.output.isNotEmpty(),
                        ) {
                            Icon(
                                imageVector = Icons.Rounded.ContentCopy,
                                contentDescription = stringResource(R.string.script_copy_output),
                                modifier = Modifier.size(18.dp),
                            )
                        }
                    }
                }

                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 170.dp, max = 330.dp),
                    shape = RoundedCornerShape(14.dp),
                    color = colors.surfaceContainerLowest,
                    tonalElevation = 1.dp,
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .verticalScroll(scrollState)
                            .padding(12.dp),
                    ) {
                        val display = when {
                            state.output.isNotEmpty() -> state.output
                            state.started && !state.running -> stringResource(R.string.script_no_output_recorded)
                            else -> stringResource(R.string.script_empty_output)
                        }
                        SelectionContainer {
                            Text(
                                text = display,
                                style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                                color = if (state.output.isEmpty()) colors.onSurfaceVariant else colors.onSurface,
                            )
                        }
                    }
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (onEdit != null) {
                        OutlinedButton(
                            onClick = {
                                controller.stop()
                                onDismiss()
                                onEdit()
                            },
                            enabled = !state.running,
                        ) {
                            Icon(Icons.Rounded.Edit, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.size(6.dp))
                            Text(stringResource(R.string.script_edit))
                        }
                    }

                    Spacer(Modifier.weight(1f))

                    TextButton(
                        onClick = {
                            controller.stop()
                            onDismiss()
                        },
                    ) {
                        Text(stringResource(R.string.common_close))
                    }

                    if (state.running) {
                        Button(
                            onClick = { controller.stop() },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = colors.error,
                                contentColor = colors.onError,
                            ),
                        ) {
                            Icon(Icons.Rounded.Stop, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.size(6.dp))
                            Text(stringResource(R.string.script_stop))
                        }
                    } else {
                        Button(onClick = ::triggerExecute) {
                            Icon(Icons.Rounded.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.size(6.dp))
                            Text(stringResource(if (state.started) R.string.script_rerun else R.string.script_execute))
                        }
                    }
                }
            }
        }
    }
}
