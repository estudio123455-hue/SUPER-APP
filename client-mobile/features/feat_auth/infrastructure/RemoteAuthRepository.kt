package co.superapp.features.feat_auth.infrastructure

import co.superapp.core.network.LoginRequestDto
import co.superapp.core.network.RefreshTokenRequestDto
import co.superapp.core.network.SuperAppApiService
import co.superapp.features.feat_auth.domain.AuthRepository
import co.superapp.features.feat_auth.domain.AuthUserSession
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext

class RemoteAuthRepository(
    private val api: SuperAppApiService,
    private val ioDispatcher: CoroutineDispatcher,
) : AuthRepository {
    override suspend fun login(email: String, password: String): Result<AuthUserSession> =
        withContext(ioDispatcher) {
            runCatching {
                val tokens = api.loginUser(LoginRequestDto(email = email, password = password))
                val me = api.getMe()
                AuthUserSession(
                    userId = me.id,
                    email = me.email,
                    fullName = me.fullName,
                    roles = me.roles.toSet(),
                    accessToken = tokens.accessToken,
                    refreshToken = tokens.refreshToken,
                )
            }
        }

    override suspend fun refresh(refreshToken: String): Result<AuthUserSession> =
        withContext(ioDispatcher) {
            runCatching {
                val tokens = api.refreshTokens(RefreshTokenRequestDto(refreshToken = refreshToken))
                val me = api.getMe()
                AuthUserSession(
                    userId = me.id,
                    email = me.email,
                    fullName = me.fullName,
                    roles = me.roles.toSet(),
                    accessToken = tokens.accessToken,
                    refreshToken = tokens.refreshToken,
                )
            }
        }
}

