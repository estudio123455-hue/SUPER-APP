package co.superapp.features.feat_wallet.domain

data class LedgerMovement(
    val id: String,
    val amountCents: Long,
    val transactionType: String,
    val reference: String,
    val createdAt: String,
)

data class WalletOverview(
    val walletId: String,
    val currency: String,
    val balanceCents: Long,
    val loyaltyTier: String = "BRONZE",
    val loyaltyPoints: Int = 0,
    val lifetimeVolumeCents: Long = 0L,
    val isLocked: Boolean,
    val recentMovements: List<LedgerMovement>,
)

interface WalletFeatureRepository {
    suspend fun getMyWallet(): Result<WalletOverview>
    suspend fun deposit(amountCents: Long, reference: String, idempotencyKey: String): Result<WalletOverview>
    suspend fun withdraw(amountCents: Long, reference: String, idempotencyKey: String): Result<WalletOverview>
    suspend fun redeemLoyaltyPoints(): Result<WalletOverview>
}

