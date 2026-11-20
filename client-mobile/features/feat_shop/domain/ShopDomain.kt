package co.superapp.features.feat_shop.domain

enum class ShopPaymentMethod {
    WALLET,
    CASH_ON_DELIVERY,
}

data class ShopProductVariant(
    val variantSku: String,
    val size: String? = null,
    val color: String? = null,
    val stockQuantity: Int = 0,
)

data class ShopProduct(
    val id: String,
    val sku: String,
    val title: String,
    val description: String,
    val priceCents: Long,
    val unitCostCents: Long = 0L,
    val unitMarginCents: Long = 0L,
    val marginPercentage: Double = 0.0,
    val stockQuantity: Int,
    val variants: List<ShopProductVariant> = emptyList(),
    val categoryTag: String = "GENERAL",
    val complementTags: List<String> = emptyList(),
)

data class ShopCrossSellBundle(
    val anchorProductId: String,
    val anchorSku: String,
    val anchorTitle: String,
    val anchorPriceCents: Long,
    val complementProductId: String,
    val complementSku: String,
    val complementTitle: String,
    val complementPriceCents: Long,
    val bundleName: String,
    val originalTotalCents: Long,
    val bundlePriceCents: Long,
    val savingsCents: Long,
    val discountPercentage: Double,
    val combinedCogsCents: Long,
)

data class PlacedShopOrder(
    val orderId: String,
    val totalCents: Long,
    val netProfitCents: Long = 0L,
    val currency: String,
    val paymentMethod: ShopPaymentMethod,
    val status: String,
    val sourceJobId: String? = null,
    val carrierName: String? = null,
    val trackingCode: String? = null,
    val couponCode: String? = null,
    val discountCents: Long = 0L,
    val whatsappCheckoutUrl: String,
)

data class OrderLifecycleMessages(
    val orderId: String,
    val status: String,
    val confirmationMsg: String,
    val shippingMsg: String,
    val postDeliveryMsg: String,
    val confirmationWhatsappUrl: String,
    val shippingWhatsappUrl: String,
    val postDeliveryWhatsappUrl: String,
)

interface ShopRepository {
    suspend fun fetchCatalog(
        search: String? = null,
        categoryTag: String? = null,
    ): Result<List<ShopProduct>>
    suspend fun applyDynamicPrice(productId: String, demandConversions: Int): Result<ShopProduct>
    suspend fun placeSingleItemOrder(
        productId: String,
        quantity: Int,
        paymentMethod: ShopPaymentMethod,
        shippingAddress: String,
        idempotencyKey: String,
        sourceJobId: String? = null,
        couponCode: String? = null,
        variantSku: String? = null,
    ): Result<PlacedShopOrder>
    suspend fun shipOrder(
        orderId: String,
        carrierName: String,
        trackingCode: String,
    ): Result<PlacedShopOrder>
    suspend fun getOrderLifecycleMessages(orderId: String): Result<OrderLifecycleMessages>
    suspend fun markOrderDelivered(orderId: String): Result<PlacedShopOrder>
    suspend fun getCrossSellBundle(productId: String): Result<ShopCrossSellBundle?>
}
