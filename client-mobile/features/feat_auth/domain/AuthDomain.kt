package co.superapp.features.feat_auth.domain

data class AuthUserSession(
    val userId: String,
    val email: String,
    val fullName: String,
    val roles: Set<String>,
    val accessToken: String,
    val refreshToken: String,
)

interface AuthRepository {
    suspend fun login(email: String, password: String): Result<AuthUserSession>
    suspend fun refresh(refreshToken: String): Result<AuthUserSession>
}

