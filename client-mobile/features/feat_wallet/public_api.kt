package co.superapp.features.feat_wallet

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import co.superapp.features.feat_wallet.presentation.WalletRoute
import co.superapp.features.feat_wallet.presentation.WalletViewModel

/**
 * Public API surface for feat_wallet (Law 1).
 */
@Composable
fun FeatWalletEntryPoint(
    viewModel: WalletViewModel,
    modifier: Modifier = Modifier,
) {
    WalletRoute(viewModel = viewModel, modifier = modifier)
}
