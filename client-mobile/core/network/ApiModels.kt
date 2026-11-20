package co.superapp.core.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class RegisterUserRequestDto(
    val email: String,
    val password: String,
    @SerialName("full_name") val fullName: String,
    val roles: List<String> = listOf("USER"),
)

@Serializable
data class LoginRequestDto(
    val email: String,
    val password: String,
)

@Serializable
data class TokenPairResponseDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
)

@Serializable
data class RefreshTokenRequestDto(
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class LogoutRequestDto(
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class LogoutResponseDto(
    val status: String = "logged_out",
    val message: String = "Successfully logged out",
)


@Serializable
data class UserResponseDto(
    val id: String,
    val email: String,
    @SerialName("full_name") val fullName: String,
    val roles: List<String>,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class TransactionRequestDto(
    @SerialName("amount_cents") val amountCents: Long,
    val reference: String,
    @SerialName("idempotency_key") val idempotencyKey: String,
)

@Serializable
data class LedgerEntryResponseDto(
    val id: String,
    @SerialName("wallet_id") val walletId: String,
    @SerialName("amount_cents") val amountCents: Long,
    @SerialName("transaction_type") val transactionType: String,
    val status: String,
    val reference: String,
    @SerialName("idempotency_key") val idempotencyKey: String,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class WalletSummaryResponseDto(
    val id: String,
    @SerialName("user_id") val userId: String,
    val currency: String,
    @SerialName("balance_cents") val balanceCents: Long,
    @SerialName("loyalty_tier") val loyaltyTier: String = "BRONZE",
    @SerialName("loyalty_points") val loyaltyPoints: Int = 0,
    @SerialName("lifetime_volume_cents") val lifetimeVolumeCents: Long = 0L,
    @SerialName("is_locked") val isLocked: Boolean,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class WalletMeResponseDto(
    val wallet: WalletSummaryResponseDto,
    @SerialName("recent_entries") val recentEntries: List<LedgerEntryResponseDto>,
)

@Serializable
data class TransactionResultResponseDto(
    val wallet: WalletSummaryResponseDto,
    val entry: LedgerEntryResponseDto,
)

@Serializable
data class RestockProductRequestDto(
    @SerialName("quantity_to_add") val quantityToAdd: Int,
)

@Serializable
data class DynamicPricingRequestDto(
    @SerialName("demand_conversions") val demandConversions: Int = 0,
)

@Serializable
data class ProductVariantDto(
    @SerialName("variant_sku") val variantSku: String,
    val size: String? = null,
    val color: String? = null,
    @SerialName("stock_quantity") val stockQuantity: Int = 0,
)

typealias ProductVariantResponseDto = ProductVariantDto

@Serializable
data class ProductResponseDto(
    val id: String,
    @SerialName("merchant_id") val merchantId: String,
    val sku: String,
    val title: String,
    val description: String,
    @SerialName("price_cents") val priceCents: Long,
    @SerialName("unit_cost_cents") val unitCostCents: Long = 0L,
    @SerialName("unit_margin_cents") val unitMarginCents: Long = 0L,
    @SerialName("margin_percentage") val marginPercentage: Double = 0.0,
    @SerialName("stock_quantity") val stockQuantity: Int,
    val variants: List<ProductVariantDto> = emptyList(),
    @SerialName("category_tag") val categoryTag: String = "GENERAL",
    @SerialName("complement_tags") val complementTags: List<String> = emptyList(),
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class CrossSellBundleResponseDto(
    @SerialName("anchor_product_id") val anchorProductId: String,
    @SerialName("anchor_sku") val anchorSku: String,
    @SerialName("anchor_title") val anchorTitle: String,
    @SerialName("anchor_price_cents") val anchorPriceCents: Long,
    @SerialName("complement_product_id") val complementProductId: String,
    @SerialName("complement_sku") val complementSku: String,
    @SerialName("complement_title") val complementTitle: String,
    @SerialName("complement_price_cents") val complementPriceCents: Long,
    @SerialName("bundle_name") val bundleName: String,
    @SerialName("original_total_cents") val originalTotalCents: Long,
    @SerialName("bundle_price_cents") val bundlePriceCents: Long,
    @SerialName("savings_cents") val savingsCents: Long,
    @SerialName("discount_percentage") val discountPercentage: Double,
    @SerialName("combined_cogs_cents") val combinedCogsCents: Long,
)

@Serializable
data class DynamicPricingResponseDto(
    val product: ProductResponseDto,
    @SerialName("old_price_cents") val oldPriceCents: Long,
    @SerialName("new_price_cents") val newPriceCents: Long,
    @SerialName("pricing_strategy") val pricingStrategy: String,
)

@Serializable
data class CommerceFinancialSummaryResponseDto(
    @SerialName("inventory_cost_value_cents") val inventoryCostValueCents: Long,
    @SerialName("inventory_retail_value_cents") val inventoryRetailValueCents: Long,
    @SerialName("potential_inventory_profit_cents") val potentialInventoryProfitCents: Long,
    @SerialName("orders_count") val ordersCount: Int,
    @SerialName("delivered_orders_count") val deliveredOrdersCount: Int,
    @SerialName("gross_revenue_cents") val grossRevenueCents: Long,
    @SerialName("accumulated_cogs_cents") val accumulatedCogsCents: Long,
    @SerialName("accumulated_shipping_cents") val accumulatedShippingCents: Long,
    @SerialName("realized_net_profit_cents") val realizedNetProfitCents: Long,
)

@Serializable
data class OrderItemRequestDto(
    @SerialName("product_id") val productId: String,
    val quantity: Int,
    @SerialName("variant_sku") val variantSku: String? = null,
)

typealias OrderItemInputDto = OrderItemRequestDto

@Serializable
data class PlaceOrderRequestDto(
    val items: List<OrderItemRequestDto>,
    @SerialName("payment_method") val paymentMethod: String,
    @SerialName("shipping_address") val shippingAddress: String,
    @SerialName("idempotency_key") val idempotencyKey: String,
    @SerialName("shipping_cost_cents") val shippingCostCents: Long = 0L,
    @SerialName("source_job_id") val sourceJobId: String? = null,
    @SerialName("coupon_code") val couponCode: String? = null,
)

typealias CreateOrderRequestDto = PlaceOrderRequestDto

@Serializable
data class ShipOrderRequestDto(
    @SerialName("carrier_name") val carrierName: String,
    @SerialName("tracking_code") val trackingCode: String,
)

@Serializable
data class OrderLifecycleMessagesResponseDto(
    @SerialName("order_id") val orderId: String,
    val status: String,
    @SerialName("carrier_name") val carrierName: String? = null,
    @SerialName("tracking_code") val trackingCode: String? = null,
    @SerialName("confirmation_msg") val confirmationMsg: String,
    @SerialName("shipping_msg") val shippingMsg: String,
    @SerialName("post_delivery_msg") val postDeliveryMsg: String,
    @SerialName("confirmation_whatsapp_url") val confirmationWhatsappUrl: String,
    @SerialName("shipping_whatsapp_url") val shippingWhatsappUrl: String,
    @SerialName("post_delivery_whatsapp_url") val postDeliveryWhatsappUrl: String,
)

@Serializable
data class CreatePromoCouponRequestDto(
    val code: String,
    @SerialName("discount_percentage") val discountPercentage: Int,
    @SerialName("max_uses") val maxUses: Int? = null,
)

@Serializable
data class PromoCouponResponseDto(
    val id: String,
    val code: String,
    @SerialName("discount_percentage") val discountPercentage: Int,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("times_used") val timesUsed: Int,
    @SerialName("max_uses") val maxUses: Int? = null,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class OrderItemResponseDto(
    @SerialName("product_id") val productId: String,
    val sku: String,
    val title: String,
    @SerialName("unit_price_cents") val unitPriceCents: Long,
    @SerialName("unit_cost_cents") val unitCostCents: Long = 0L,
    val quantity: Int,
    @SerialName("subtotal_cents") val subtotalCents: Long,
    @SerialName("subtotal_cost_cents") val subtotalCostCents: Long = 0L,
    @SerialName("variant_sku") val variantSku: String? = null,
)

@Serializable
data class OrderResponseDto(
    val id: String,
    @SerialName("buyer_id") val buyerId: String,
    val items: List<OrderItemResponseDto>,
    @SerialName("total_cents") val totalCents: Long,
    @SerialName("shipping_cost_cents") val shippingCostCents: Long = 0L,
    @SerialName("total_cogs_cents") val totalCogsCents: Long = 0L,
    @SerialName("net_profit_cents") val netProfitCents: Long = 0L,
    val currency: String,
    @SerialName("payment_method") val paymentMethod: String,
    val status: String,
    @SerialName("shipping_address") val shippingAddress: String,
    @SerialName("idempotency_key") val idempotencyKey: String,
    @SerialName("source_job_id") val sourceJobId: String? = null,
    @SerialName("carrier_name") val carrierName: String? = null,
    @SerialName("tracking_code") val trackingCode: String? = null,
    @SerialName("coupon_code") val couponCode: String? = null,
    @SerialName("discount_cents") val discountCents: Long = 0L,
    @SerialName("whatsapp_checkout_url") val whatsappCheckoutUrl: String,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class EnqueueMediaJobRequestDto(
    @SerialName("job_type") val jobType: String,
    @SerialName("content_niche") val contentNiche: String = "DESK_SETUP_UGC",
    @SerialName("source_url_or_prompt") val sourceUrlOrPrompt: String,
    @SerialName("linked_product_id") val linkedProductId: String? = null,
)

@Serializable
data class MediaJobResponseDto(
    val id: String,
    @SerialName("creator_id") val creatorId: String,
    @SerialName("job_type") val jobType: String,
    @SerialName("content_niche") val contentNiche: String = "DESK_SETUP_UGC",
    @SerialName("source_url_or_prompt") val sourceUrlOrPrompt: String,
    @SerialName("linked_product_id") val linkedProductId: String? = null,
    val status: String,
    @SerialName("progress_percent") val progressPercent: Int,
    @SerialName("result_payload") val resultPayload: Map<String, String>? = null,
    @SerialName("error_message") val errorMessage: String? = null,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class ScheduleMediaPostRequestDto(
    val platform: String = "TIKTOK",
    val slot: String,
)

@Serializable
data class ScheduledPostResponseDto(
    val id: String,
    @SerialName("job_id") val jobId: String,
    @SerialName("creator_id") val creatorId: String,
    val platform: String,
    @SerialName("scheduled_date") val scheduledDate: String,
    val slot: String,
    @SerialName("conversions_count") val conversionsCount: Int,
    @SerialName("revenue_attributed_cents") val revenueAttributedCents: Long,
    @SerialName("ics_download_url") val icsDownloadUrl: String,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class DailyStreakProgressResponseDto(
    @SerialName("target_date") val targetDate: String,
    @SerialName("scheduled_today_count") val scheduledTodayCount: Int,
    @SerialName("daily_goal") val dailyGoal: Int,
    @SerialName("goal_completed") val goalCompleted: Boolean,
    @SerialName("total_conversions") val totalConversions: Int,
    @SerialName("total_revenue_attributed_cents") val totalRevenueAttributedCents: Long,
    @SerialName("scheduled_posts") val scheduledPosts: List<ScheduledPostResponseDto>,
)

@Serializable
data class NichePerformanceMetricResponseDto(
    @SerialName("content_niche") val contentNiche: String,
    @SerialName("total_videos_created") val totalVideosCreated: Int,
    @SerialName("total_videos_scheduled") val totalVideosScheduled: Int,
    @SerialName("conversions_count") val conversionsCount: Int,
    @SerialName("revenue_attributed_cents") val revenueAttributedCents: Long,
    @SerialName("conversions_per_video") val conversionsPerVideo: Double,
)

@Serializable
data class NichePerformanceAnalyticsResponseDto(
    @SerialName("top_performing_niche") val topPerformingNiche: String? = null,
    @SerialName("total_videos_created") val totalVideosCreated: Int,
    @SerialName("total_videos_scheduled") val totalVideosScheduled: Int,
    @SerialName("total_conversions") val totalConversions: Int,
    @SerialName("total_revenue_attributed_cents") val totalRevenueAttributedCents: Long,
    val niches: List<NichePerformanceMetricResponseDto>,
)
