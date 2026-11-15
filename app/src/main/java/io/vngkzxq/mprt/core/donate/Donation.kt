package io.vngkzxq.mprt.core.donate

data class Wallet(val id: String, val network: String, val address: String)

object Donation {
    val wallets: List<Wallet> = emptyList<Wallet>()
}
