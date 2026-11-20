package co.superapp.features.feat_auth

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import co.superapp.features.feat_auth.presentation.AuthRoute
import co.superapp.features.feat_auth.presentation.AuthViewModel

/**
 * Public API surface for feat_auth (Law 1).
 */
@Composable
fun FeatAuthEntryPoint(
    viewModel: AuthViewModel,
    modifier: Modifier = Modifier,
) {
    AuthRoute(viewModel = viewModel, modifier = modifier)
}
