package co.superapp.features.feat_shop.application

import co.superapp.features.feat_shop.domain.OrderLifecycleMessages
import co.superapp.features.feat_shop.domain.PlacedShopOrder
import co.superapp.features.feat_shop.domain.ShopCrossSellBundle
import co.superapp.features.feat_shop.domain.ShopPaymentMethod
import co.superapp.features.feat_shop.domain.ShopProduct
import co.superapp.features.feat_shop.domain.ShopRepository

class ShopCatalogAndOrderUseCase(
    private val repository: ShopRepository,
) {
    suspend fun loadActiveCatalog(
        search: String? = null,
        categoryTag: String? = null,
    ): Result<List<ShopProduct>> = repository.fetchCatalog(
        search = search?.trim()?.ifEmpty { null },
        categoryTag = categoryTag?.trim()?.ifEmpty { null },
    )

    suspend fun adjustProductDynamicPrice(
        productId: String,
        demandConversions: Int = 0,
    ): Result<ShopProduct> = repository.applyDynamicPrice(productId, demandConversions)

    suspend fun quickBuyProduct(
        productId: String,
        paymentMethod: ShopPaymentMethod,
        shippingAddress: String,
        idempotencyKey: String,
        sourceJobId: String? = null,
        couponCode: String? = null,
        variantSku: String? = null,
    ): Result<PlacedShopOrder> {
        require(shippingAddress.isNotBlank()) { "La dirección de envío es obligatoria." }
        return repository.placeSingleItemOrder(
            productId = productId,
            quantity = 1,
            paymentMethod = paymentMethod,
            shippingAddress = shippingAddress.trim(),
            idempotencyKey = idempotencyKey,
            sourceJobId = sourceJobId,
            couponCode = couponCode?.trim()?.ifEmpty { null },
            variantSku = variantSku?.trim()?.ifEmpty { null },
        )
    }

    suspend fun shipOrderWithTracking(
        orderId: String,
        carrierName: String,
        trackingCode: String,
    ): Result<PlacedShopOrder> = repository.shipOrder(
        orderId = orderId,
        carrierName = carrierName.trim(),
        trackingCode = trackingCode.trim(),
    )

    suspend fun fetchOrderLifecycleMessages(orderId: String): Result<OrderLifecycleMessages> =
        repository.getOrderLifecycleMessages(orderId)

    suspend fun deliverAndSettleOrder(orderId: String): Result<PlacedShopOrder> =
        repository.markOrderDelivered(orderId)

    suspend fun loadCrossSellBundle(productId: String): Result<ShopCrossSellBundle?> =
        repository.getCrossSellBundle(productId)
}
