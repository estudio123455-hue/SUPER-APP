package co.superapp.features.feat_shop.infrastructure

import co.superapp.core.network.DynamicPricingRequestDto
import co.superapp.core.network.OrderItemRequestDto
import co.superapp.core.network.OrderResponseDto
import co.superapp.core.network.PlaceOrderRequestDto
import co.superapp.core.network.ProductResponseDto
import co.superapp.core.network.ShipOrderRequestDto
import co.superapp.core.network.SuperAppApiService
import co.superapp.features.feat_shop.domain.OrderLifecycleMessages
import co.superapp.features.feat_shop.domain.PlacedShopOrder
import co.superapp.features.feat_shop.domain.ShopCrossSellBundle
import co.superapp.features.feat_shop.domain.ShopPaymentMethod
import co.superapp.features.feat_shop.domain.ShopProduct
import co.superapp.features.feat_shop.domain.ShopProductVariant
import co.superapp.features.feat_shop.domain.ShopRepository
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext

class RemoteShopRepository(
    private val api: SuperAppApiService,
    private val ioDispatcher: CoroutineDispatcher,
) : ShopRepository {

    private fun ProductResponseDto.toDomain(): ShopProduct = ShopProduct(
        id = id,
        sku = sku,
        title = title,
        description = description,
        priceCents = priceCents,
        unitCostCents = unitCostCents,
        unitMarginCents = unitMarginCents,
        marginPercentage = marginPercentage,
        stockQuantity = stockQuantity,
        variants = variants.map {
            ShopProductVariant(
                variantSku = it.variantSku,
                size = it.size,
                color = it.color,
                stockQuantity = it.stockQuantity,
            )
        },
        categoryTag = categoryTag,
        complementTags = complementTags,
    )

    private fun OrderResponseDto.toDomain(): PlacedShopOrder = PlacedShopOrder(
        orderId = id,
        totalCents = totalCents,
        netProfitCents = netProfitCents,
        currency = currency,
        paymentMethod = ShopPaymentMethod.valueOf(paymentMethod),
        status = status,
        sourceJobId = sourceJobId,
        carrierName = carrierName,
        trackingCode = trackingCode,
        couponCode = couponCode,
        discountCents = discountCents,
        whatsappCheckoutUrl = whatsappCheckoutUrl,
    )

    override suspend fun fetchCatalog(
        search: String?,
        categoryTag: String?,
    ): Result<List<ShopProduct>> = withContext(ioDispatcher) {
        runCatching {
            api.listProducts(
                search = search,
                categoryTag = categoryTag,
            ).map { it.toDomain() }
        }
    }

    override suspend fun applyDynamicPrice(
        productId: String,
        demandConversions: Int,
    ): Result<ShopProduct> = withContext(ioDispatcher) {
        runCatching {
            api.applyDynamicPrice(
                productId = productId,
                payload = DynamicPricingRequestDto(demandConversions = demandConversions),
            ).product.toDomain()
        }
    }

    override suspend fun placeSingleItemOrder(
        productId: String,
        quantity: Int,
        paymentMethod: ShopPaymentMethod,
        shippingAddress: String,
        idempotencyKey: String,
        sourceJobId: String?,
        couponCode: String?,
        variantSku: String?,
    ): Result<PlacedShopOrder> = withContext(ioDispatcher) {
        runCatching {
            api.placeOrder(
                PlaceOrderRequestDto(
                    items = listOf(
                        OrderItemRequestDto(
                            productId = productId,
                            quantity = quantity,
                            variantSku = variantSku,
                        )
                    ),
                    paymentMethod = paymentMethod.name,
                    shippingAddress = shippingAddress,
                    idempotencyKey = idempotencyKey,
                    shippingCostCents = 1_200_000L,
                    sourceJobId = sourceJobId,
                    couponCode = couponCode,
                )
            ).toDomain()
        }
    }

    override suspend fun shipOrder(
        orderId: String,
        carrierName: String,
        trackingCode: String,
    ): Result<PlacedShopOrder> = withContext(ioDispatcher) {
        runCatching {
            api.shipOrder(
                orderId = orderId,
                payload = ShipOrderRequestDto(
                    carrierName = carrierName,
                    trackingCode = trackingCode,
                ),
            ).toDomain()
        }
    }

    override suspend fun getOrderLifecycleMessages(
        orderId: String,
    ): Result<OrderLifecycleMessages> = withContext(ioDispatcher) {
        runCatching {
            val dto = api.getOrderLifecycleMessages(orderId)
            OrderLifecycleMessages(
                orderId = dto.orderId,
                status = dto.status,
                confirmationMsg = dto.confirmationMsg,
                shippingMsg = dto.shippingMsg,
                postDeliveryMsg = dto.postDeliveryMsg,
                confirmationWhatsappUrl = dto.confirmationWhatsappUrl,
                shippingWhatsappUrl = dto.shippingWhatsappUrl,
                postDeliveryWhatsappUrl = dto.postDeliveryWhatsappUrl,
            )
        }
    }

    override suspend fun markOrderDelivered(orderId: String): Result<PlacedShopOrder> =
        withContext(ioDispatcher) {
            runCatching {
                api.deliverOrder(orderId).toDomain()
            }
        }

    override suspend fun getCrossSellBundle(productId: String): Result<ShopCrossSellBundle?> =
        withContext(ioDispatcher) {
            runCatching {
                val dto = api.getCrossSellBundle(productId) ?: return@runCatching null
                ShopCrossSellBundle(
                    anchorProductId = dto.anchorProductId,
                    anchorSku = dto.anchorSku,
                    anchorTitle = dto.anchorTitle,
                    anchorPriceCents = dto.anchorPriceCents,
                    complementProductId = dto.complementProductId,
                    complementSku = dto.complementSku,
                    complementTitle = dto.complementTitle,
                    complementPriceCents = dto.complementPriceCents,
                    bundleName = dto.bundleName,
                    originalTotalCents = dto.originalTotalCents,
                    bundlePriceCents = dto.bundlePriceCents,
                    savingsCents = dto.savingsCents,
                    discountPercentage = dto.discountPercentage,
                    combinedCogsCents = dto.combinedCogsCents,
                )
            }
        }
}
