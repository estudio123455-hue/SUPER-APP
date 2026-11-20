package co.superapp.features.feat_wallet.infrastructure

import co.superapp.core.network.SuperAppApiService
import co.superapp.core.network.TransactionRequestDto
import co.superapp.features.feat_wallet.domain.LedgerMovement
import co.superapp.features.feat_wallet.domain.WalletFeatureRepository
import co.superapp.features.feat_wallet.domain.WalletOverview
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext

class RemoteWalletFeatureRepository(
    private val api: SuperAppApiService,
    private val ioDispatcher: CoroutineDispatcher,
) : WalletFeatureRepository {

    override suspend fun getMyWallet(): Result<WalletOverview> = withContext(ioDispatcher) {
        runCatching {
            val dto = api.getMyWallet()
            WalletOverview(
                walletId = dto.wallet.id,
                currency = dto.wallet.currency,
                balanceCents = dto.wallet.balanceCents,
                loyaltyTier = dto.wallet.loyaltyTier,
                loyaltyPoints = dto.wallet.loyaltyPoints,
                lifetimeVolumeCents = dto.wallet.lifetimeVolumeCents,
                isLocked = dto.wallet.isLocked,
                recentMovements = dto.recentEntries.map {
                    LedgerMovement(
                        id = it.id,
                        amountCents = it.amountCents,
                        transactionType = it.transactionType,
                        reference = it.reference,
                        createdAt = it.createdAt,
                    )
                },
            )
        }
    }


    override suspend fun deposit(
        amountCents: Long,
        reference: String,
        idempotencyKey: String,
    ): Result<WalletOverview> = withContext(ioDispatcher) {
        runCatching {
            api.depositFunds(
                TransactionRequestDto(
                    amountCents = amountCents,
                    reference = reference,
                    idempotencyKey = idempotencyKey,
                )
            )
            getMyWallet().getOrThrow()
        }
    }

    override suspend fun withdraw(
        amountCents: Long,
        reference: String,
        idempotencyKey: String,
    ): Result<WalletOverview> = withContext(ioDispatcher) {
        runCatching {
            api.withdrawFunds(
                TransactionRequestDto(
                    amountCents = amountCents,
                    reference = reference,
                    idempotencyKey = idempotencyKey,
                )
            )
            getMyWallet().getOrThrow()
        }
    }

    override suspend fun redeemLoyaltyPoints(): Result<WalletOverview> = withContext(ioDispatcher) {
        runCatching {
            api.redeemLoyaltyPoints()
            getMyWallet().getOrThrow()
        }
    }
}

