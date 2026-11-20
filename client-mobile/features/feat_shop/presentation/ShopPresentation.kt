package co.superapp.features.feat_shop.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import co.superapp.features.feat_shop.application.ShopCatalogAndOrderUseCase
import co.superapp.features.feat_shop.domain.OrderLifecycleMessages
import co.superapp.features.feat_shop.domain.ShopCrossSellBundle
import co.superapp.features.feat_shop.domain.ShopPaymentMethod
import co.superapp.features.feat_shop.domain.ShopProduct
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ShopUiState(
    val products: List<ShopProduct> = emptyList(),
    val searchQuery: String = "",
    val selectedCategoryTag: String? = null,
    val availableCategories: List<String> = listOf("MENSWEAR", "DESK_SETUP", "GENERAL"),
    val selectedVariantByProduct: Map<String, String> = emptyMap(),
    val shippingAddress: String = "Calle 93 #11-27, Bogotá",
    val couponCode: String = "SUPER10",
    val carrierName: String = "InterRapidísimo",
    val trackingCode: String = "GUIA-2400991188",
    val attributedSourceJobId: String? = null,
    val isLoading: Boolean = false,
    val lastPlacedOrderId: String? = null,
    val lastOrderMessage: String? = null,
    val lastWhatsappCheckoutUrl: String? = null,
    val lastLifecycleMessages: OrderLifecycleMessages? = null,
    val crossSellBundle: ShopCrossSellBundle? = null,
    val errorMessage: String? = null,
)

sealed interface ShopUiEvent {
    data object LoadCatalog : ShopUiEvent
    data class SearchQueryChanged(val query: String) : ShopUiEvent
    data class CategoryTagSelected(val categoryTag: String?) : ShopUiEvent
    data object ApplyCatalogFilters : ShopUiEvent
    data class LoadCrossSellBundle(val productId: String) : ShopUiEvent
    data class CouponCodeChanged(val code: String) : ShopUiEvent
    data class CarrierNameChanged(val carrierName: String) : ShopUiEvent
    data class TrackingCodeChanged(val trackingCode: String) : ShopUiEvent
    data class VariantSelected(val productId: String, val variantSku: String) : ShopUiEvent
    data class ApplyDynamicPriceClicked(val productId: String) : ShopUiEvent
    data class QuickBuyClicked(
        val productId: String,
        val paymentMethod: ShopPaymentMethod,
        val idempotencyKey: String,
        val variantSku: String? = null,
    ) : ShopUiEvent
    data class ShipOrderClicked(val orderId: String) : ShopUiEvent
    data class LoadLifecycleMessagesClicked(val orderId: String) : ShopUiEvent
    data class MarkOrderDeliveredClicked(val orderId: String) : ShopUiEvent
    data class OpenWhatsAppCheckout(val whatsappUrl: String) : ShopUiEvent
}

class ShopViewModel(
    private val useCase: ShopCatalogAndOrderUseCase,
    private val eventBus: ClientEventBus,
    private val dispatcher: CoroutineDispatcher,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ShopUiState())
    val uiState: StateFlow<ShopUiState> = _uiState.asStateFlow()

    fun onEvent(event: ShopUiEvent) {
        when (event) {
            ShopUiEvent.LoadCatalog -> loadCatalog()
            is ShopUiEvent.SearchQueryChanged -> {
                _uiState.update { it.copy(searchQuery = event.query) }
                loadCatalog()
            }
            is ShopUiEvent.CategoryTagSelected -> {
                _uiState.update { it.copy(selectedCategoryTag = event.categoryTag) }
                loadCatalog()
            }
            ShopUiEvent.ApplyCatalogFilters -> loadCatalog()
            is ShopUiEvent.CouponCodeChanged -> {
                _uiState.update { it.copy(couponCode = event.code) }
            }
            is ShopUiEvent.CarrierNameChanged -> {
                _uiState.update { it.copy(carrierName = event.carrierName) }
            }
            is ShopUiEvent.TrackingCodeChanged -> {
                _uiState.update { it.copy(trackingCode = event.trackingCode) }
            }
            is ShopUiEvent.VariantSelected -> {
                _uiState.update {
                    it.copy(
                        selectedVariantByProduct = it.selectedVariantByProduct + (event.productId to event.variantSku),
                    )
                }
            }
            is ShopUiEvent.ApplyDynamicPriceClicked -> applyDynamicPrice(event.productId)
            is ShopUiEvent.QuickBuyClicked -> quickBuy(
                productId = event.productId,
                paymentMethod = event.paymentMethod,
                idempotencyKey = event.idempotencyKey,
                variantSku = event.variantSku ?: _uiState.value.selectedVariantByProduct[event.productId],
            )
            is ShopUiEvent.ShipOrderClicked -> shipOrder(event.orderId)
            is ShopUiEvent.LoadLifecycleMessagesClicked -> loadLifecycleMessages(event.orderId)
            is ShopUiEvent.MarkOrderDeliveredClicked -> markDelivered(event.orderId)
            is ShopUiEvent.LoadCrossSellBundle -> loadCrossSellBundle(event.productId)
            is ShopUiEvent.OpenWhatsAppCheckout -> Unit
        }
    }

    private fun loadCrossSellBundle(productId: String) {
        viewModelScope.launch(dispatcher) {
            useCase.loadCrossSellBundle(productId)
                .onSuccess { bundle ->
                    _uiState.update { it.copy(crossSellBundle = bundle) }
                }
        }
    }

    private fun loadCatalog() {
        val snapshot = _uiState.value
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            useCase.loadActiveCatalog(
                search = snapshot.searchQuery,
                categoryTag = snapshot.selectedCategoryTag,
            )
                .onSuccess { items ->
                    _uiState.update { it.copy(isLoading = false, products = items) }
                    val first = items.firstOrNull()
                    if (first != null) {
                        loadCrossSellBundle(first.id)
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun applyDynamicPrice(productId: String) {
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            useCase.adjustProductDynamicPrice(productId)
                .onSuccess {
                    loadCatalog()
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun quickBuy(
        productId: String,
        paymentMethod: ShopPaymentMethod,
        idempotencyKey: String,
        variantSku: String? = null,
    ) {
        val snapshot = _uiState.value
        _uiState.update {
            it.copy(
                isLoading = true,
                errorMessage = null,
                lastOrderMessage = null,
                lastWhatsappCheckoutUrl = null,
            )
        }
        viewModelScope.launch(dispatcher) {
            useCase.quickBuyProduct(
                productId = productId,
                paymentMethod = paymentMethod,
                shippingAddress = snapshot.shippingAddress,
                idempotencyKey = idempotencyKey,
                sourceJobId = snapshot.attributedSourceJobId,
                couponCode = snapshot.couponCode,
                variantSku = variantSku,
            )
                .onSuccess { order ->
                    val couponNote = if (order.discountCents > 0) {
                        " • Cupón ${order.couponCode} (-$${order.discountCents / 100} COP)"
                    } else {
                        ""
                    }
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            lastPlacedOrderId = order.orderId,
                            lastOrderMessage = "Orden ${order.status}$couponNote • Utilidad Neta: $${order.netProfitCents / 100} COP",
                            lastWhatsappCheckoutUrl = order.whatsappCheckoutUrl,
                        )
                    }
                    eventBus.publish(
                        ClientAppEvent.OrderPlaced(
                            orderId = order.orderId,
                            totalCents = order.totalCents,
                            paymentMethod = order.paymentMethod.name,
                        )
                    )
                    loadCatalog()
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun shipOrder(orderId: String) {
        val snapshot = _uiState.value
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            useCase.shipOrderWithTracking(
                orderId = orderId,
                carrierName = snapshot.carrierName,
                trackingCode = snapshot.trackingCode,
            )
                .onSuccess { shipped ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            lastOrderMessage = "🚚 Despachada vía ${shipped.carrierName} (Guía: ${shipped.trackingCode})",
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun loadLifecycleMessages(orderId: String) {
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            useCase.fetchOrderLifecycleMessages(orderId)
                .onSuccess { messages ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            lastLifecycleMessages = messages,
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }

    private fun markDelivered(orderId: String) {
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            useCase.deliverAndSettleOrder(orderId)
                .onSuccess { delivered ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            lastOrderMessage = "Entregada y Liquidada en Wallet (+$${delivered.netProfitCents / 100} COP)",
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }
}

@Composable
fun ShopRoute(
    viewModel: ShopViewModel,
    onOpenWhatsAppUrl: (String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsState()
    ShopScreen(
        uiState = uiState,
        onEvent = { event ->
            if (event is ShopUiEvent.OpenWhatsAppCheckout) {
                onOpenWhatsAppUrl(event.whatsappUrl)
            } else {
                viewModel.onEvent(event)
            }
        },
        modifier = modifier,
    )
}

/**
 * Law 4 (UDF): Stateless Screen receiving only immutable ShopUiState and onEvent lambda.
 */
@Composable
fun ShopScreen(
    uiState: ShopUiState,
    onEvent: (ShopUiEvent) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = modifier
            .fillMaxSize()
            .padding(20.dp),
    ) {
        SuperAppLottieHeader(
            title = "Tienda & Unidad Económica",
            subtitle = "Precios Dinámicos IA, Cupones SUPER10 y Guías de Despacho",
        )
        OutlinedTextField(
            value = uiState.searchQuery,
            onValueChange = { onEvent(ShopUiEvent.SearchQueryChanged(it)) },
            label = { Text("🔍 Buscar producto por título o SKU") },
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Button(
                onClick = { onEvent(ShopUiEvent.CategoryTagSelected(null)) },
                enabled = !uiState.isLoading,
            ) {
                Text("${if (uiState.selectedCategoryTag == null) "✓ " else ""}Todas")
            }
            uiState.availableCategories.forEach { category ->
                val isSelected = uiState.selectedCategoryTag == category
                Button(
                    onClick = { onEvent(ShopUiEvent.CategoryTagSelected(category)) },
                    enabled = !uiState.isLoading,
                ) {
                    Text("${if (isSelected) "✓ " else ""}$category")
                }
            }
        }
        OutlinedTextField(
            value = uiState.couponCode,
            onValueChange = { onEvent(ShopUiEvent.CouponCodeChanged(it)) },
            label = { Text("🎟️ Cupón Promocional (ej. SUPER10 — Piso COGS 1.15x)") },
            modifier = Modifier.fillMaxWidth(),
        )
        if (uiState.lastOrderMessage != null) {
            Text(text = uiState.lastOrderMessage)
        }
        if (uiState.lastWhatsappCheckoutUrl != null) {
            Button(
                onClick = {
                    onEvent(ShopUiEvent.OpenWhatsAppCheckout(uiState.lastWhatsappCheckoutUrl))
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("📲 Enviar Orden por WhatsApp Business")
            }
        }
        if (uiState.lastPlacedOrderId != null) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        onEvent(ShopUiEvent.ShipOrderClicked(uiState.lastPlacedOrderId))
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text("🚚 Despachar con Guía")
                }
                Button(
                    onClick = {
                        onEvent(ShopUiEvent.LoadLifecycleMessagesClicked(uiState.lastPlacedOrderId))
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text("💬 Mensajes Seguimiento")
                }
            }
            Button(
                onClick = {
                    onEvent(ShopUiEvent.MarkOrderDeliveredClicked(uiState.lastPlacedOrderId))
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("📦 Marcar Entregado & Liquidar en Wallet")
            }
        }
        if (uiState.lastLifecycleMessages != null) {
            val msgs = uiState.lastLifecycleMessages
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.padding(12.dp),
                ) {
                    Text("💬 Embudo de Mensajes Post-Venta (WhatsApp Intent)")
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Button(
                            onClick = {
                                onEvent(ShopUiEvent.OpenWhatsAppCheckout(msgs.confirmationWhatsappUrl))
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("1. Confirmación")
                        }
                        Button(
                            onClick = {
                                onEvent(ShopUiEvent.OpenWhatsAppCheckout(msgs.shippingWhatsappUrl))
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("2. Guía Envío")
                        }
                        Button(
                            onClick = {
                                onEvent(ShopUiEvent.OpenWhatsAppCheckout(msgs.postDeliveryWhatsappUrl))
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("3. Post-Venta")
                        }
                    }
                }
            }
        }
        if (uiState.errorMessage != null) {
            Text(text = uiState.errorMessage)
        }
        uiState.products.forEach { product ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(14.dp),
                ) {
                    Text(text = product.title)
                    Text(
                        text = "$${product.priceCents / 100} COP | COGS: $${product.unitCostCents / 100} | Margen: ${product.marginPercentage}% | Stock: ${product.stockQuantity}"
                    )
                    if (product.variants.isNotEmpty()) {
                        val selectedVariant = uiState.selectedVariantByProduct[product.id]
                            ?: product.variants.firstOrNull()?.variantSku
                        Text("Tallas y Colores Disponibles:")
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            product.variants.forEach { variant ->
                                val isSelected = selectedVariant == variant.variantSku
                                Button(
                                    onClick = {
                                        onEvent(ShopUiEvent.VariantSelected(product.id, variant.variantSku))
                                    },
                                    enabled = !uiState.isLoading,
                                ) {
                                    Text("${if (isSelected) "✓ " else ""}Talla ${variant.size ?: variant.variantSku} (${variant.stockQuantity})")
                                }
                            }
                        }
                    }
                    Button(
                        onClick = { onEvent(ShopUiEvent.ApplyDynamicPriceClicked(product.id)) },
                        enabled = !uiState.isLoading,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("⚡ Ajuste Dinámico de Precio (IA)")
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        val activeVariantSku = uiState.selectedVariantByProduct[product.id]
                            ?: product.variants.firstOrNull()?.variantSku
                        Button(
                            onClick = {
                                onEvent(
                                    ShopUiEvent.QuickBuyClicked(
                                        productId = product.id,
                                        paymentMethod = ShopPaymentMethod.WALLET,
                                        idempotencyKey = "wallet-buy-${product.id}-${System.currentTimeMillis()}",
                                        variantSku = activeVariantSku,
                                    )
                                )
                            },
                            enabled = !uiState.isLoading,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("Pagar con Wallet")
                        }
                        Button(
                            onClick = {
                                onEvent(
                                    ShopUiEvent.QuickBuyClicked(
                                        productId = product.id,
                                        paymentMethod = ShopPaymentMethod.CASH_ON_DELIVERY,
                                        idempotencyKey = "cod-buy-${product.id}-${System.currentTimeMillis()}",
                                        variantSku = activeVariantSku,
                                    )
                                )
                            },
                            enabled = !uiState.isLoading,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("Contraentrega")
                        }
                    }
                }
            }
        }
        if (uiState.crossSellBundle != null) {
            val bundle = uiState.crossSellBundle
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.padding(14.dp),
                ) {
                    Text("✨ Sugerencia de Combo IA (Cross-Selling)")
                    Text(text = bundle.bundleName)
                    Text(text = "Combina ${bundle.anchorTitle} + ${bundle.complementTitle}")
                    Text(
                        text = "Precio Combo: $${bundle.bundlePriceCents / 100} COP (Antes: $${bundle.originalTotalCents / 100} COP) • Ahorras $${bundle.savingsCents / 100} COP (-${bundle.discountPercentage}%)"
                    )
                    Button(
                        onClick = {
                            onEvent(
                                ShopUiEvent.QuickBuyClicked(
                                    productId = bundle.anchorProductId,
                                    paymentMethod = ShopPaymentMethod.WALLET,
                                    idempotencyKey = "bundle-buy-${bundle.anchorProductId}-${System.currentTimeMillis()}",
                                )
                            )
                        },
                        enabled = !uiState.isLoading,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("🛍️ Comprar Combo con Wallet")
                    }
                }
            }
        }
    }
}
