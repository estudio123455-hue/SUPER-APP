package co.superapp.core.network

import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * Centralized Retrofit + OkHttp factory for the Super App Android client.
 * Defaults to Vercel + Neon PostgreSQL production URL with 30s timeouts to tolerate
 * Neon scale-to-zero cold starts gracefully.
 */
object SuperAppApiClient {
    const val DEFAULT_PRODUCTION_BASE_URL: String = SuperAppApiService.DEFAULT_PRODUCTION_BASE_URL
    const val LOCAL_EMULATOR_BASE_URL: String = SuperAppApiService.LOCAL_EMULATOR_BASE_URL
    const val DEFAULT_TIMEOUT_SECONDS: Long = 30L

    private val defaultJson: Json = Json {
        ignoreUnknownKeys = true
    }

    fun createOkHttpClient(
        tokenProvider: AuthTokenProvider,
        timeoutSeconds: Long = DEFAULT_TIMEOUT_SECONDS,
    ): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(timeoutSeconds, TimeUnit.SECONDS)
        .readTimeout(timeoutSeconds, TimeUnit.SECONDS)
        .writeTimeout(timeoutSeconds, TimeUnit.SECONDS)
        .addInterceptor(AuthTokenInterceptor(tokenProvider))
        .build()

    fun create(
        tokenProvider: AuthTokenProvider,
        baseUrl: String = DEFAULT_PRODUCTION_BASE_URL,
        timeoutSeconds: Long = DEFAULT_TIMEOUT_SECONDS,
    ): SuperAppApiService {
        val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        val okHttpClient = createOkHttpClient(
            tokenProvider = tokenProvider,
            timeoutSeconds = timeoutSeconds,
        )
        return Retrofit.Builder()
            .baseUrl(normalizedBaseUrl)
            .client(okHttpClient)
            .addConverterFactory(defaultJson.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(SuperAppApiService::class.java)
    }
}
