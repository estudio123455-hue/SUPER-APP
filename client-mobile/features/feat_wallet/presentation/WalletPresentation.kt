package co.superapp.features.feat_wallet.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import co.superapp.core.designsystem.SuperAppLottieHeader
import co.superapp.core.eventbus.ClientAppEvent
import co.superapp.core.eventbus.ClientEventBus
import co.superapp.features.feat_wallet.application.ManageWalletUseCase
import co.superapp.features.feat_wallet.domain.LedgerMovement
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class WalletUiState(
    val currency: String = "COP",
    val balanceCents: Long = 0L,
    val loyaltyTier: String = "BRONZE",
    val loyaltyPoints: Int = 0,
    val lifetimeVolumeCents: Long = 0L,
    val isLoading: Boolean = false,
    val movements: List<LedgerMovement> = emptyList(),
    val errorMessage: String? = null,
    val successMessage: String? = null,
)

sealed interface WalletUiEvent {
    data object RefreshWallet : WalletUiEvent
    data class DepositClicked(val amountCents: Long, val idempotencyKey: String) : WalletUiEvent
    data class WithdrawClicked(val amountCents: Long, val idempotencyKey: String) : WalletUiEvent
    data object RedeemPointsClicked : WalletUiEvent
}


class WalletViewModel(
    private val manageWalletUseCase: ManageWalletUseCase,
    private val eventBus: ClientEventBus,
    private val dispatcher: CoroutineDispatcher,
) : ViewModel() {

    private val _uiState = MutableStateFlow(WalletUiState())
    val uiState: StateFlow<WalletUiState> = _uiState.asStateFlow()

    fun onEvent(event: WalletUiEvent) {
        when (event) {
            WalletUiEvent.RefreshWallet -> refresh()
            is WalletUiEvent.DepositClicked -> executeDeposit(event.amountCents, event.idempotencyKey)
            is WalletUiEvent.WithdrawClicked -> executeWithdraw(event.amountCents, event.idempotencyKey)
            WalletUiEvent.RedeemPointsClicked -> executeRedeemPoints()
        }
    }

    private fun refresh() {
        _uiState.update { it.copy(isLoading = true, errorMessage = null, successMessage = null) }
        viewModelScope.launch(dispatcher) {
            manageWalletUseCase.loadOverview()
                .onSuccess { overview ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            currency = overview.currency,
                            balanceCents = overview.balanceCents,
                            loyaltyTier = overview.loyaltyTier,
                            loyaltyPoints = overview.loyaltyPoints,
                            lifetimeVolumeCents = overview.lifetimeVolumeCents,
                            movements = overview.recentMovements,
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun executeDeposit(amountCents: Long, idempotencyKey: String) {
        _uiState.update { it.copy(isLoading = true, errorMessage = null, successMessage = null) }
        viewModelScope.launch(dispatcher) {
            manageWalletUseCase.depositCop(amountCents, idempotencyKey)
                .onSuccess { overview ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            balanceCents = overview.balanceCents,
                            loyaltyTier = overview.loyaltyTier,
                            loyaltyPoints = overview.loyaltyPoints,
                            lifetimeVolumeCents = overview.lifetimeVolumeCents,
                            movements = overview.recentMovements,
                        )
                    }
                    eventBus.publish(
                        ClientAppEvent.WalletBalanceChanged(
                            newBalanceCents = overview.balanceCents,
                            currency = overview.currency,
                        )
                    )
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun executeWithdraw(amountCents: Long, idempotencyKey: String) {
        _uiState.update { it.copy(isLoading = true, errorMessage = null, successMessage = null) }
        viewModelScope.launch(dispatcher) {
            manageWalletUseCase.withdrawCop(amountCents, idempotencyKey)
                .onSuccess { overview ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            balanceCents = overview.balanceCents,
                            loyaltyTier = overview.loyaltyTier,
                            loyaltyPoints = overview.loyaltyPoints,
                            lifetimeVolumeCents = overview.lifetimeVolumeCents,
                            movements = overview.recentMovements,
                        )
                    }
                    eventBus.publish(
                        ClientAppEvent.WalletBalanceChanged(
                            newBalanceCents = overview.balanceCents,
                            currency = overview.currency,
                        )
                    )
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun executeRedeemPoints() {
        _uiState.update { it.copy(isLoading = true, errorMessage = null, successMessage = null) }
        viewModelScope.launch(dispatcher) {
            manageWalletUseCase.redeemCashbackPoints()
                .onSuccess { overview ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            balanceCents = overview.balanceCents,
                            loyaltyTier = overview.loyaltyTier,
                            loyaltyPoints = overview.loyaltyPoints,
                            lifetimeVolumeCents = overview.lifetimeVolumeCents,
                            movements = overview.recentMovements,
                            successMessage = "¡Puntos de cashback canjeados exitosamente!",
                        )
                    }
                    eventBus.publish(
                        ClientAppEvent.WalletBalanceChanged(
                            newBalanceCents = overview.balanceCents,
                            currency = overview.currency,
                        )
                    )
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

}

@Composable
fun WalletRoute(
    viewModel: WalletViewModel,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsState()
    WalletScreen(
        uiState = uiState,
        onEvent = viewModel::onEvent,
        modifier = modifier,
    )
}

/**
 * Law 4 (UDF): Stateless Screen receiving only immutable WalletUiState and onEvent lambda.
 */
@Composable
fun WalletScreen(
    uiState: WalletUiState,
    onEvent: (WalletUiEvent) -> Unit,
    modifier: Modifier = Modifier,
) {
    val formattedCop = uiState.balanceCents / 100
    Column(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = modifier
            .fillMaxSize()
            .padding(20.dp),
    ) {
        SuperAppLottieHeader(
            title = "Billetera Super App (${uiState.currency})",
            subtitle = "Saldo disponible: $$formattedCop ${uiState.currency}",
        )
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(14.dp)) {
                Text(text = "Nivel VIP: ${uiState.loyaltyTier}")
                Text(text = "Puntos Cashback: ${uiState.loyaltyPoints} ($${uiState.loyaltyPoints} COP)")
                Button(
                    onClick = { onEvent(WalletUiEvent.RedeemPointsClicked) },
                    enabled = !uiState.isLoading && uiState.loyaltyPoints > 0,
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Text("Canjear Cashback a Saldo")
                }
            }
        }
        if (uiState.successMessage != null) {
            Text(text = uiState.successMessage)
        }
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {

            Button(
                onClick = {
                    onEvent(
                        WalletUiEvent.DepositClicked(
                            amountCents = 5_000_000L,
                            idempotencyKey = "ui-topup-${System.currentTimeMillis()}",
                        )
                    )
                },
                enabled = !uiState.isLoading,
                modifier = Modifier.weight(1f),
            ) {
                Text("Recargar +$50k")
            }
            Button(
                onClick = {
                    onEvent(
                        WalletUiEvent.WithdrawClicked(
                            amountCents = 2_000_000L,
                            idempotencyKey = "ui-withdraw-${System.currentTimeMillis()}",
                        )
                    )
                },
                enabled = !uiState.isLoading,
                modifier = Modifier.weight(1f),
            ) {
                Text("Retirar -$20k")
            }
        }
        if (uiState.errorMessage != null) {
            Text(text = uiState.errorMessage)
        }
        uiState.movements.forEach { entry ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(text = "${entry.transactionType}: $${entry.amountCents / 100} COP")
                    Text(text = entry.reference)
                }
            }
        }
    }
}
