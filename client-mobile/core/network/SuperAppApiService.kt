package co.superapp.core.network

import okhttp3.Interceptor
import okhttp3.Response
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query


interface AuthTokenProvider {
    fun currentAccessToken(): String?
}

class AuthTokenInterceptor(
    private val tokenProvider: AuthTokenProvider,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = tokenProvider.currentAccessToken()
        val request = if (!token.isNullOrBlank()) {
            original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            original
        }
        return chain.proceed(request)
    }
}

/**
 * Retrofit contract synchronized with shared-contracts/openapi.json.
 * Default Android Emulator base URL: http://10.0.2.2:8000/
 */
interface SuperAppApiService {
    companion object {
        const val EMULATOR_BASE_URL: String = "http://10.0.2.2:8000/"
    }

    // Identity Bounded Context
    @POST("api/v1/identity/register")
    suspend fun registerUser(@Body payload: RegisterUserRequestDto): UserResponseDto

    @POST("api/v1/identity/login")
    suspend fun loginUser(@Body payload: LoginRequestDto): TokenPairResponseDto

    @POST("api/v1/identity/auth/refresh")
    suspend fun refreshTokens(@Body payload: RefreshTokenRequestDto): TokenPairResponseDto

    @POST("api/v1/identity/auth/logout")
    suspend fun logoutUser(@Body payload: LogoutRequestDto): LogoutResponseDto

    @GET("api/v1/identity/me")
    suspend fun getMe(): UserResponseDto

    // Wallet Bounded Context
    @GET("api/v1/wallet/me")
    suspend fun getMyWallet(): WalletMeResponseDto

    @POST("api/v1/wallet/me/deposit")
    suspend fun depositFunds(@Body payload: TransactionRequestDto): TransactionResultResponseDto

    @POST("api/v1/wallet/me/withdraw")
    suspend fun withdrawFunds(@Body payload: TransactionRequestDto): TransactionResultResponseDto

    @POST("api/v1/wallet/me/redeem-points")
    suspend fun redeemLoyaltyPoints(): TransactionResultResponseDto


    // Commerce Bounded Context
    @GET("api/v1/commerce/products")
    suspend fun listProducts(
        @Query("search") search: String? = null,
        @Query("category_tag") categoryTag: String? = null,
    ): List<ProductResponseDto>


    @GET("api/v1/commerce/products/{productId}/cross-sell")
    suspend fun getCrossSellBundle(
        @Path("productId") productId: String,
    ): CrossSellBundleResponseDto?

    @PATCH("api/v1/commerce/products/{productId}/stock")
    suspend fun restockProduct(
        @Path("productId") productId: String,
        @Body payload: RestockProductRequestDto,
    ): ProductResponseDto

    @POST("api/v1/commerce/products/{productId}/dynamic-price")
    suspend fun applyDynamicPrice(
        @Path("productId") productId: String,
        @Body payload: DynamicPricingRequestDto,
    ): DynamicPricingResponseDto

    @POST("api/v1/commerce/coupons")
    suspend fun createPromoCoupon(@Body payload: CreatePromoCouponRequestDto): PromoCouponResponseDto

    @POST("api/v1/commerce/orders")
    suspend fun placeOrder(@Body payload: PlaceOrderRequestDto): OrderResponseDto

    @POST("api/v1/commerce/orders/{orderId}/ship")
    suspend fun shipOrder(
        @Path("orderId") orderId: String,
        @Body payload: ShipOrderRequestDto,
    ): OrderResponseDto

    @GET("api/v1/commerce/orders/{orderId}/messages")
    suspend fun getOrderLifecycleMessages(
        @Path("orderId") orderId: String,
    ): OrderLifecycleMessagesResponseDto

    @POST("api/v1/commerce/orders/{orderId}/deliver")
    suspend fun deliverOrder(@Path("orderId") orderId: String): OrderResponseDto

    @GET("api/v1/commerce/orders/me")
    suspend fun listMyOrders(): List<OrderResponseDto>

    @GET("api/v1/commerce/analytics/summary")
    suspend fun getCommerceAnalyticsSummary(): CommerceFinancialSummaryResponseDto

    @GET("api/v1/commerce/analytics/weekly-report")
    suspend fun downloadWeeklyExecutiveReport(): ResponseBody

    // Media AI Bounded Context
    @POST("api/v1/media-ai/jobs")
    suspend fun enqueueMediaJob(@Body payload: EnqueueMediaJobRequestDto): MediaJobResponseDto

    @GET("api/v1/media-ai/jobs")
    suspend fun listMyJobs(): List<MediaJobResponseDto>

    @GET("api/v1/media-ai/jobs/{jobId}")
    suspend fun getMediaJob(@Path("jobId") jobId: String): MediaJobResponseDto

    @GET("api/v1/media-ai/jobs/{jobId}/download-srt")
    suspend fun downloadJobSrt(@Path("jobId") jobId: String): ResponseBody

    @GET("api/v1/media-ai/jobs/{jobId}/download-pack")
    suspend fun downloadJobProductionPack(@Path("jobId") jobId: String): ResponseBody

    @POST("api/v1/media-ai/jobs/{jobId}/schedule")
    suspend fun scheduleMediaPost(
        @Path("jobId") jobId: String,
        @Body payload: ScheduleMediaPostRequestDto,
    ): ScheduledPostResponseDto

    @GET("api/v1/media-ai/schedule")
    suspend fun getPublishingSchedule(): DailyStreakProgressResponseDto

    @GET("api/v1/media-ai/jobs/{jobId}/download-ics")
    suspend fun downloadJobCalendarIcs(@Path("jobId") jobId: String): ResponseBody

    @GET("api/v1/media-ai/analytics/by-niche")
    suspend fun getNichePerformanceAnalytics(): NichePerformanceAnalyticsResponseDto
}
