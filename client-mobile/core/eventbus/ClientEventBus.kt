package co.superapp.core.eventbus

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

sealed interface ClientAppEvent {
    data class UserAuthenticated(
        val userId: String,
        val email: String,
        val accessToken: String,
        val refreshToken: String = "",
    ) : ClientAppEvent


    data class WalletBalanceChanged(
        val newBalanceCents: Long,
        val currency: String = "COP",
    ) : ClientAppEvent

    data class OrderPlaced(
        val orderId: String,
        val totalCents: Long,
        val paymentMethod: String,
    ) : ClientAppEvent
}

/**
 * Decoupled client-side Event Bus using SharedFlow so Mini-Apps never import each other (Law 1).
 */
class ClientEventBus {
    private val _events = MutableSharedFlow<ClientAppEvent>(extraBufferCapacity = 16)
    val events: SharedFlow<ClientAppEvent> = _events.asSharedFlow()

    suspend fun publish(event: ClientAppEvent) {
        _events.emit(event)
    }
}
