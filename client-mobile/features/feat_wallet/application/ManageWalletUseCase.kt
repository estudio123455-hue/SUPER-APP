package co.superapp.features.feat_wallet.application

import co.superapp.features.feat_wallet.domain.WalletFeatureRepository
import co.superapp.features.feat_wallet.domain.WalletOverview

class ManageWalletUseCase(
    private val repository: WalletFeatureRepository,
) {
    suspend fun loadOverview(): Result<WalletOverview> = repository.getMyWallet()

    suspend fun depositCop(amountCents: Long, idempotencyKey: String): Result<WalletOverview> {
        require(amountCents > 0) { "El monto a recargar debe ser mayor a 0." }
        return repository.deposit(
            amountCents = amountCents,
            reference = "Recarga App Móvil PSE",
            idempotencyKey = idempotencyKey,
        )
    }

    suspend fun withdrawCop(amountCents: Long, idempotencyKey: String): Result<WalletOverview> {
        require(amountCents > 0) { "El monto a retirar debe ser mayor a 0." }
        return repository.withdraw(
            amountCents = amountCents,
            reference = "Retiro App Móvil",
            idempotencyKey = idempotencyKey,
        )
    }

    suspend fun redeemCashbackPoints(): Result<WalletOverview> = repository.redeemLoyaltyPoints()
}

