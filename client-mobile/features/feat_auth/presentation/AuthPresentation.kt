package co.superapp.features.feat_auth.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
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
import co.superapp.features.feat_auth.application.LoginUserUseCase
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AuthUiState(
    val email: String = "demo@superapp.co",
    val password: String = "",
    val isLoading: Boolean = false,
    val authenticatedUserName: String? = null,
    val refreshToken: String? = null,
    val errorMessage: String? = null,
)

sealed interface AuthUiEvent {
    data class EmailChanged(val email: String) : AuthUiEvent
    data class PasswordChanged(val password: String) : AuthUiEvent
    data object SubmitLogin : AuthUiEvent
    data object RefreshSessionClicked : AuthUiEvent
}


class AuthViewModel(
    private val loginUserUseCase: LoginUserUseCase,
    private val eventBus: ClientEventBus,
    private val dispatcher: CoroutineDispatcher,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun onEvent(event: AuthUiEvent) {
        when (event) {
            is AuthUiEvent.EmailChanged -> {
                _uiState.update { it.copy(email = event.email, errorMessage = null) }
            }
            is AuthUiEvent.PasswordChanged -> {
                _uiState.update { it.copy(password = event.password, errorMessage = null) }
            }
            AuthUiEvent.SubmitLogin -> submitLogin()
            AuthUiEvent.RefreshSessionClicked -> refreshSession()
        }
    }

    private fun submitLogin() {
        val snapshot = _uiState.value
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            loginUserUseCase.execute(snapshot.email, snapshot.password)
                .onSuccess { session ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            authenticatedUserName = session.fullName,
                            refreshToken = session.refreshToken,
                        )
                    }
                    eventBus.publish(
                        ClientAppEvent.UserAuthenticated(
                            userId = session.userId,
                            email = session.email,
                            accessToken = session.accessToken,
                            refreshToken = session.refreshToken,
                        )
                    )
                }
                .onFailure { err ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = err.message ?: "Error de autenticación",
                        )
                    }
                }
        }
    }

    private fun refreshSession() {
        val currentRt = _uiState.value.refreshToken ?: return
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            loginUserUseCase.refreshSession(currentRt)
                .onSuccess { session ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            authenticatedUserName = session.fullName,
                            refreshToken = session.refreshToken,
                        )
                    }
                    eventBus.publish(
                        ClientAppEvent.UserAuthenticated(
                            userId = session.userId,
                            email = session.email,
                            accessToken = session.accessToken,
                            refreshToken = session.refreshToken,
                        )
                    )
                }
                .onFailure { err ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = err.message ?: "Error al renovar sesión",
                        )
                    }
                }
        }
    }

}

@Composable
fun AuthRoute(
    viewModel: AuthViewModel,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsState()
    AuthScreen(
        uiState = uiState,
        onEvent = viewModel::onEvent,
        modifier = modifier,
    )
}

/**
 * Law 4 (UDF): Stateless Screen receiving only immutable AuthUiState and onEvent lambda.
 */
@Composable
fun AuthScreen(
    uiState: AuthUiState,
    onEvent: (AuthUiEvent) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = modifier
            .fillMaxSize()
            .padding(20.dp),
    ) {
        SuperAppLottieHeader(
            title = "Identidad Multi-Rol",
            subtitle = "Creadores, Comercios y Usuarios en un solo ecosistema",
        )
        OutlinedTextField(
            value = uiState.email,
            onValueChange = { onEvent(AuthUiEvent.EmailChanged(it)) },
            label = { Text("Correo electrónico") },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = uiState.password,
            onValueChange = { onEvent(AuthUiEvent.PasswordChanged(it)) },
            label = { Text("Contraseña") },
            modifier = Modifier.fillMaxWidth(),
        )
        if (uiState.errorMessage != null) {
            Text(text = uiState.errorMessage)
        }
        if (uiState.authenticatedUserName != null) {
            Text(text = "Sesión activa: ${uiState.authenticatedUserName}")
        }
        Button(
            onClick = { onEvent(AuthUiEvent.SubmitLogin) },
            enabled = !uiState.isLoading,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (uiState.isLoading) "Autenticando..." else "Iniciar Sesión")
        }
    }
}
