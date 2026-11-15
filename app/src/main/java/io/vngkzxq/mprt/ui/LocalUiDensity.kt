package io.vngkzxq.mprt.ui

import androidx.compose.runtime.staticCompositionLocalOf
import io.vngkzxq.mprt.core.data.AppSettings
import io.vngkzxq.mprt.core.model.UiDensity

val LocalUiDensity = staticCompositionLocalOf { UiDensity.DEFAULT }

val LocalSettings = staticCompositionLocalOf { AppSettings() }
