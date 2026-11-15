package io.vngkzxq.mprt

import android.app.Application
import android.os.Build
import coil3.ImageLoader
import coil3.PlatformContext
import coil3.SingletonImageLoader
import coil3.gif.AnimatedImageDecoder
import coil3.gif.GifDecoder
import coil3.request.crossfade
import coil3.svg.SvgDecoder
import coil3.video.VideoFrameDecoder
import io.vngkzxq.mprt.core.media.ApkIconFetcher
import io.vngkzxq.mprt.core.media.ApkIconKeyer
import io.vngkzxq.mprt.core.remote.SafFileSystem
import io.vngkzxq.mprt.core.root.RootManager
import io.vngkzxq.mprt.core.shizuku.ShizukuManager
import io.vngkzxq.mprt.core.sound.SoundPoolDevice
import io.vngkzxq.mprt.core.sound.UiSounds
import io.vngkzxq.mprt.core.util.Formatters
import io.vngkzxq.mprt.core.vault.Vault
import io.vngkzxq.mprt.ui.i18n.AppLocales
import io.vngkzxq.mprt.ui.security.AppLock

class ToolShearApp : Application(), SingletonImageLoader.Factory {

    override fun onCreate() {
        super.onCreate()
        AppLocales.install(this)
        Formatters.locale = resources.configuration.locales[0]
        Vault.init(filesDir, cacheDir)
        AppLock.track(this)
        RootManager.init(this)
        SafFileSystem.appContext = this
        runCatching { ShizukuManager.init(this) }
        runCatching { UiSounds.device = SoundPoolDevice(this).also { it.trackActivities(this) } }
    }

    override fun newImageLoader(context: PlatformContext): ImageLoader =
        ImageLoader.Builder(context)
            .components {
                add(VideoFrameDecoder.Factory())
                if (Build.VERSION.SDK_INT >= 28) add(AnimatedImageDecoder.Factory()) else add(GifDecoder.Factory())
                add(SvgDecoder.Factory())
                add(ApkIconFetcher.Factory())
                add(ApkIconKeyer())
            }
            .crossfade(true)
            .build()
}
