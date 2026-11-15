package io.vngkzxq.mprt.core.util

import io.vngkzxq.mprt.core.fs.FsUtil
import java.io.File

object SharePolicy {
    fun mayShare(file: File, privateDirs: List<File>, cacheDirs: List<File>): Boolean =
        privateDirs.none { FsUtil.isSameOrDescendant(it, file) } || cacheDirs.any { FsUtil.isSameOrDescendant(it, file) }
}
