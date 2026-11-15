package io.vngkzxq.mprt.feature.termux

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.vngkzxq.mprt.core.termux.AndroidTermux
import io.vngkzxq.mprt.core.termux.TermuxSession

class TermuxViewModel(app: Application) : AndroidViewModel(app) {
    val session = TermuxSession(AndroidTermux(app), viewModelScope)
}
