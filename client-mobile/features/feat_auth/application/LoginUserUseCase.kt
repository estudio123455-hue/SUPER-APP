package co.superapp.features.feat_auth.application

import co.superapp.features.feat_auth.domain.AuthRepository
import co.superapp.features.feat_auth.domain.AuthUserSession

class LoginUserUseCase(
    private val repository: AuthRepository,
) {
    suspend fun execute(email: String, password: String): Result<AuthUserSession> {
        if (email.isBlank() || !email.contains("@")) {
            return Result.failure(IllegalArgumentException("Ingresa un correo electrónico válido."))
        }
        if (password.isBlank()) {
            return Result.failure(IllegalArgumentException("Ingresa tu contraseña."))
        }
        return repository.login(email.trim(), password)
    }

    suspend fun refreshSession(refreshToken: String): Result<AuthUserSession> {
        if (refreshToken.isBlank()) {
            return Result.failure(IllegalArgumentException("Refresh token inválido."))
        }
        return repository.refresh(refreshToken)
    }
}

