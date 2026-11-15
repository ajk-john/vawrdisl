package io.vngkzxq.mprt

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.vngkzxq.mprt.core.data.SettingsRepository
import io.vngkzxq.mprt.core.data.AppSettings
import io.vngkzxq.mprt.core.i18n.L10n
import io.vngkzxq.mprt.core.sound.UiSounds
import io.vngkzxq.mprt.core.util.Formatters
import io.vngkzxq.mprt.feature.pdf.ReaderSource
import io.vngkzxq.mprt.ui.AppShell
import io.vngkzxq.mprt.ui.LocalSettings
import io.vngkzxq.mprt.ui.LocalUiDensity
import io.vngkzxq.mprt.ui.i18n.AndroidStrings
import io.vngkzxq.mprt.ui.i18n.AppLocales
import io.vngkzxq.mprt.ui.security.AppLock
import io.vngkzxq.mprt.ui.security.AppLockGate
import io.vngkzxq.mprt.ui.security.DeviceAuth
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import io.vngkzxq.mprt.ui.theme.ToolShearTheme

class MainActivity : FragmentActivity() {

    companion object {
        const val EXTRA_PATH = "path"
        const val EXTRA_PATH_OTHER = "path2"
    }

    private fun incomingPdf(intent: Intent?): ReaderSource? {
        if (intent?.action != Intent.ACTION_VIEW) return null
        val uri = intent.data ?: return null
        val type = intent.type ?: runCatching { contentResolver.getType(uri) }.getOrNull()
        val named = uri.lastPathSegment?.endsWith(".pdf", ignoreCase = true) == true
        if (type != "application/pdf" && !named) return null
        return when (uri.scheme) {
            "file" -> uri.path?.let { ReaderSource(it, null) }
            "content" -> ReaderSource(null, uri.toString())
            else -> null
        }
    }

    private fun incomingFile(intent: Intent?): Uri? {
        if (intent?.action != Intent.ACTION_VIEW) return null
        return intent.data?.takeIf { it.scheme == "file" || it.scheme == "content" }
    }

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(AppLocales.wrap(newBase))
    }

    @Suppress("OVERRIDE_DEPRECATION", "DEPRECATION")
    override fun startActivityForResult(intent: Intent, requestCode: Int, options: Bundle?) {
        AppLock.leavingForResult()
        super.startActivityForResult(intent, requestCode, options)
    }

    private fun applySecurity(appLock: Boolean) {
        if (Build.VERSION.SDK_INT >= 33) setRecentsScreenshotEnabled(!appLock)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        DeviceAuth.attach(this)
        Formatters.locale = resources.configuration.locales[0]
        L10n.source = AndroidStrings(applicationContext.createConfigurationContext(resources.configuration))

        val settingsRepo = SettingsRepository(applicationContext)
        val startPath = if (BuildConfig.DEBUG) intent?.getStringExtra(EXTRA_PATH) else null
        val startPath2 = if (BuildConfig.DEBUG) intent?.getStringExtra(EXTRA_PATH_OTHER) else null

        val settingsFlow = settingsRepo.settings.catch { emit(AppSettings()) }
        val initial = runBlocking { withTimeoutOrNull(500) { settingsFlow.first() } } ?: AppSettings()
        if (initial.security.secureScreen) window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        AppLock.apply(initial.security)
        applySecurity(initial.security.appLock)
        Formatters.solarHijri = initial.list.persianCalendar
        UiSounds.enabled = initial.appearance.sounds
        UiSounds.inSilent = initial.appearance.soundsInSilent
        val incoming = incomingPdf(intent)
        val incomingFile = if (incoming == null && savedInstanceState == null) incomingFile(intent) else null
        setContent {
            val settings by settingsFlow.collectAsStateWithLifecycle(initialValue = initial)
            val sounds = settings.appearance.sounds
            LaunchedEffect(sounds) { UiSounds.enabled = sounds }
            val inSilent = settings.appearance.soundsInSilent
            LaunchedEffect(inSilent) { UiSounds.inSilent = inSilent }
            val secure = settings.security.secureScreen
            LaunchedEffect(secure) {
                if (secure) window.addFlags(WindowManager.LayoutParams.FLAG_SECURE) else window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
            }
            val security = settings.security
            LaunchedEffect(security) {
                AppLock.apply(security)
                applySecurity(security.appLock)
            }
            Formatters.solarHijri = settings.list.persianCalendar
            val scope = rememberCoroutineScope()
            ToolShearTheme(appearance = settings.appearance) {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CompositionLocalProvider(LocalUiDensity provides settings.uiDensity, LocalSettings provides settings) {
                        AppLockGate(onTurnOff = { scope.launch { settingsRepo.editSecurity { it.copy(appLock = false) } } }) {
                            AppShell(
                                settings = settings,
                                settingsRepo = settingsRepo,
                                startPath = startPath,
                                startPathOther = startPath2,
                                incoming = incoming,
                                incomingFile = incomingFile,
                                onIncomingDone = { finish() },
                            )
                        }
                    }
                }
            }
        }
    }
}
