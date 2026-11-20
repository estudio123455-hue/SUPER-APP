package co.superapp.features.feat_studio.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import co.superapp.core.designsystem.SuperAppLottieHeader
import co.superapp.features.feat_studio.application.StudioJobsUseCase
import co.superapp.features.feat_studio.domain.DailyOutfitPlanItem
import co.superapp.features.feat_studio.domain.ScheduledStudioPost
import co.superapp.features.feat_studio.domain.StudioContentNiche
import co.superapp.features.feat_studio.domain.StudioJobType
import co.superapp.features.feat_studio.domain.StudioMediaJob
import co.superapp.features.feat_studio.domain.StudioNicheAnalyticsSummary
import co.superapp.features.feat_studio.domain.StudioNichePerformanceMetric
import co.superapp.features.feat_studio.domain.StudioPublishingSlot
import co.superapp.features.feat_studio.domain.WardrobeCategory
import co.superapp.features.feat_studio.domain.WardrobeItem
import coil.compose.AsyncImage
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class StudioUiState(
    val promptOrSourceUrl: String = "https://storage.superapp.io/demo/setup_ergo_raw.mp4",
    val selectedJobType: StudioJobType = StudioJobType.VIRAL_SHORT_CLIP,
    val selectedNiche: StudioContentNiche = StudioContentNiche.DESK_SETUP_UGC,
    val activeNicheFilter: StudioContentNiche? = null,
    val availableNiches: List<String> = listOf(
        StudioContentNiche.DESK_SETUP_UGC.name,
        StudioContentNiche.RAP_CULTURE_VIRAL.name,
        StudioContentNiche.YOUTUBE_HIGHLIGHT_CLIP.name,
        StudioContentNiche.MENSWEAR_LOOKBOOK.name,
    ),
    val selectedDayKey: String = "monday",
    val newGarmentTitle: String = "",
    val newGarmentCategory: WardrobeCategory = WardrobeCategory.OUTERWEAR,
    val newGarmentImageUri: String = "https://cdn.superapp.io/wardrobe/rbr_jacket.png",
    val wardrobeItems: List<WardrobeItem> = defaultWardrobeItems(),
    val scheduledPosts: List<ScheduledStudioPost> = emptyList(),
    val nicheAnalytics: StudioNicheAnalyticsSummary? = null,
    val dailyGoalCount: Int = 0,
    val isSubmitting: Boolean = false,
    val showMascotCelebration: Boolean = false,
    val jobs: List<StudioMediaJob> = emptyList(),
    val weeklyOutfitCalendar: List<DailyOutfitPlanItem> = defaultWeeklyOutfitCalendar(),
    val errorMessage: String? = null,
) {
    val filteredJobs: List<StudioMediaJob>
        get() = activeNicheFilter?.let { niche ->
            jobs.filter { it.contentNiche == niche }
        } ?: jobs

    val filteredScheduledPosts: List<ScheduledStudioPost>
        get() {
            val filter = activeNicheFilter ?: return scheduledPosts
            val matchingJobIds = jobs.filter { it.contentNiche == filter }.map { it.id }.toSet()
            return scheduledPosts.filter { post ->
                post.contentNiche == filter || post.jobId in matchingJobIds
            }
        }

    val filteredNicheMetrics: List<StudioNichePerformanceMetric>
        get() = nicheAnalytics?.niches?.let { metrics ->
            activeNicheFilter?.let { niche ->
                metrics.filter { it.contentNiche == niche }
            } ?: metrics
        } ?: emptyList()
}

private fun defaultWardrobeItems(): List<WardrobeItem> = listOf(
    WardrobeItem(
        id = "item-rbr-01",
        title = "Chaqueta Oversize RBR Edition",
        category = WardrobeCategory.OUTERWEAR,
        imageUri = "https://cdn.superapp.io/wardrobe/rbr_jacket.png",
        colorHex = "#111827",
        linkedCommerceProductId = "CHAQUETA-RBR-EDITION",
    ),
    WardrobeItem(
        id = "item-cargo-02",
        title = "Pantalón Cargo Techwear Negro",
        category = WardrobeCategory.BOTTOM,
        imageUri = "https://cdn.superapp.io/wardrobe/cargo_black.png",
        colorHex = "#0B0F17",
    ),
)

private fun defaultWeeklyOutfitCalendar(): List<DailyOutfitPlanItem> = listOf(
    DailyOutfitPlanItem("monday", "Lunes", "Chaqueta Oversize RBR Edition + Cargo Negro + Sneakers Blancos"),
    DailyOutfitPlanItem("tuesday", "Martes", "Hoodie Gris Minimal + Jeans Rectos + Botas Urbanas"),
    DailyOutfitPlanItem("wednesday", "Miércoles", "Camiseta Heavyweight Blanca + Chaqueta Oversize RBR Edition"),
    DailyOutfitPlanItem("thursday", "Jueves", "Look Smart-Casual Oficina Creativa + Accesorios Negros"),
    DailyOutfitPlanItem("friday", "Viernes", "Total Black Nocturno + Chaqueta Oversize RBR Edition"),
    DailyOutfitPlanItem("weekend", "Fin de Semana", "Athleisure Cómodo + Gorra Estructurada"),
)

sealed interface StudioUiEvent {
    data class PromptChanged(val value: String) : StudioUiEvent
    data class JobTypeSelected(val jobType: StudioJobType) : StudioUiEvent
    data class ContentNicheSelected(val niche: StudioContentNiche) : StudioUiEvent
    data class NicheFilterSelected(val niche: StudioContentNiche?) : StudioUiEvent
    data class NicheSelected(val niche: String?) : StudioUiEvent
    data class ScheduleSlotClicked(val jobId: String, val slot: StudioPublishingSlot) : StudioUiEvent
    data class OutfitDaySelected(val dayKey: String) : StudioUiEvent
    data class NewGarmentTitleChanged(val title: String) : StudioUiEvent
    data object AddWardrobeItemClicked : StudioUiEvent
    data object EnqueueClicked : StudioUiEvent
    data object RefreshJobs : StudioUiEvent
}

class StudioViewModel(
    private val useCase: StudioJobsUseCase,
    private val dispatcher: CoroutineDispatcher,
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudioUiState())
    val uiState: StateFlow<StudioUiState> = _uiState.asStateFlow()

    fun onEvent(event: StudioUiEvent) {
        when (event) {
            is StudioUiEvent.PromptChanged -> {
                _uiState.update { it.copy(promptOrSourceUrl = event.value, errorMessage = null) }
            }
            is StudioUiEvent.JobTypeSelected -> {
                _uiState.update { it.copy(selectedJobType = event.jobType) }
            }
            is StudioUiEvent.ContentNicheSelected -> {
                _uiState.update { it.copy(selectedNiche = event.niche) }
            }
            is StudioUiEvent.NicheFilterSelected -> {
                _uiState.update { it.copy(activeNicheFilter = event.niche) }
            }
            is StudioUiEvent.NicheSelected -> {
                val parsed = event.niche?.let { name ->
                    runCatching { StudioContentNiche.valueOf(name) }.getOrNull()
                }
                _uiState.update { it.copy(activeNicheFilter = parsed) }
            }
            is StudioUiEvent.ScheduleSlotClicked -> {
                scheduleSlot(event.jobId, event.slot)
            }
            is StudioUiEvent.OutfitDaySelected -> {
                _uiState.update { it.copy(selectedDayKey = event.dayKey) }
            }
            is StudioUiEvent.NewGarmentTitleChanged -> {
                _uiState.update { it.copy(newGarmentTitle = event.title) }
            }
            StudioUiEvent.AddWardrobeItemClicked -> addGarmentToLocalWardrobe()
            StudioUiEvent.EnqueueClicked -> enqueueJob()
            StudioUiEvent.RefreshJobs -> refreshJobs()
        }
    }

    private fun addGarmentToLocalWardrobe() {
        val snapshot = _uiState.value
        val cleanedTitle = snapshot.newGarmentTitle.trim()
        if (cleanedTitle.isEmpty()) return

        val newItem = WardrobeItem(
            id = "wardrobe-${System.currentTimeMillis()}",
            title = cleanedTitle,
            category = snapshot.newGarmentCategory,
            imageUri = snapshot.newGarmentImageUri,
            colorHex = "#00E5A3",
        )
        _uiState.update {
            it.copy(
                newGarmentTitle = "",
                wardrobeItems = listOf(newItem) + it.wardrobeItems,
                showMascotCelebration = true,
            )
        }
    }

    private fun enqueueJob() {
        val snapshot = _uiState.value
        _uiState.update { it.copy(isSubmitting = true, errorMessage = null) }
        viewModelScope.launch(dispatcher) {
            useCase.launchAsyncJob(
                jobType = snapshot.selectedJobType,
                contentNiche = snapshot.selectedNiche,
                sourceUrlOrPrompt = snapshot.promptOrSourceUrl,
            )
                .onSuccess { newJob ->
                    _uiState.update {
                        it.copy(
                            isSubmitting = false,
                            showMascotCelebration = true,
                            jobs = listOf(newJob) + it.jobs,
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isSubmitting = false, errorMessage = err.message) }
                }
        }
    }

    private fun scheduleSlot(jobId: String, slot: StudioPublishingSlot) {
        viewModelScope.launch(dispatcher) {
            useCase.scheduleVideoInSlot(jobId, slot)
                .onSuccess { post ->
                    _uiState.update {
                        val updated = listOf(post) + it.scheduledPosts.filterNot { p -> p.jobId == jobId }
                        it.copy(
                            scheduledPosts = updated,
                            dailyGoalCount = updated.size.coerceAtMost(2),
                            showMascotCelebration = updated.size >= 2,
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(errorMessage = err.message) }
                }
        }
    }

    private fun refreshJobs() {
        viewModelScope.launch(dispatcher) {
            useCase.loadMyJobs()
                .onSuccess { list ->
                    _uiState.update {
                        it.copy(
                            jobs = list,
                            showMascotCelebration = list.any { j -> j.status == "COMPLETED" },
                        )
                    }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(errorMessage = err.message) }
                }
            useCase.loadPublishingSchedule()
                .onSuccess { posts ->
                    _uiState.update {
                        it.copy(
                            scheduledPosts = posts,
                            dailyGoalCount = posts.size.coerceAtMost(2),
                        )
                    }
                }
            useCase.loadNichePerformanceAnalytics()
                .onSuccess { summary ->
                    _uiState.update { it.copy(nicheAnalytics = summary) }
                }
        }
    }
}

@Composable
fun StudioRoute(
    viewModel: StudioViewModel,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsState()
    StudioScreen(
        uiState = uiState,
        onEvent = viewModel::onEvent,
        modifier = modifier,
    )
}

/**
 * Law 4 (UDF) & Law 5: Stateless Screen monitoring asynchronous MediaJobs, Multi-Niche Templates,
 * 2-Videos/Day Schedule, Wardrobe (Coil), and Outfit Calendar.
 */
@Composable
fun StudioScreen(
    uiState: StudioUiState,
    onEvent: (StudioUiEvent) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = modifier
            .fillMaxSize()
            .padding(20.dp),
    ) {
        SuperAppLottieHeader(
            title = "Studio IA Multinicho (${uiState.dailyGoalCount}/2 Videos Hoy)",
            subtitle = "Nicho activo: ${uiState.selectedNiche.name}",
            lottieAssetName = "pet_mascot.json",
        )
        TopNicheBadge(
            nicheAnalytics = uiState.nicheAnalytics,
            activeNicheFilter = uiState.activeNicheFilter,
            onNicheFilterSelected = { niche -> onEvent(StudioUiEvent.NicheFilterSelected(niche)) },
        )
        Row(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            StudioContentNiche.entries.forEach { niche ->
                Button(
                    onClick = { onEvent(StudioUiEvent.ContentNicheSelected(niche)) },
                    modifier = Modifier.weight(1f),
                ) {
                    Text(niche.name.take(6))
                }
            }
        }
        OutlinedTextField(
            value = uiState.promptOrSourceUrl,
            onValueChange = { onEvent(StudioUiEvent.PromptChanged(it)) },
            label = { Text("URL de video o Prompt de IA") },
            modifier = Modifier.fillMaxWidth(),
        )
        Button(
            onClick = { onEvent(StudioUiEvent.EnqueueClicked) },
            enabled = !uiState.isSubmitting,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                if (uiState.isSubmitting) {
                    "Encolando tarea..."
                } else {
                    "Lanzar ${uiState.selectedJobType.name} (${uiState.selectedNiche.name})"
                }
            )
        }
        if (uiState.errorMessage != null) {
            Text(text = uiState.errorMessage)
        }
        WeeklyOutfitCalendarSection(
            selectedDayKey = uiState.selectedDayKey,
            weeklyPlan = uiState.weeklyOutfitCalendar,
            wardrobeItems = uiState.wardrobeItems,
            newGarmentTitle = uiState.newGarmentTitle,
            onNewGarmentTitleChanged = { onEvent(StudioUiEvent.NewGarmentTitleChanged(it)) },
            onAddGarmentClicked = { onEvent(StudioUiEvent.AddWardrobeItemClicked) },
            onDaySelected = { dayKey -> onEvent(StudioUiEvent.OutfitDaySelected(dayKey)) },
        )
        val postsByJobId = uiState.scheduledPosts.associateBy { it.jobId }
        uiState.filteredJobs.forEach { job ->
            val attributedPost = postsByJobId[job.id]
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.padding(12.dp),
                ) {
                    Text(text = "${job.jobType.name} [${job.contentNiche.name}] — ${job.status} (${job.progressPercent}%)")
                    if (attributedPost != null) {
                        Text(
                            text = "💰 Atribución: ${attributedPost.conversionsCount} ventas • $${attributedPost.revenueAttributedCents / 100} COP (${attributedPost.slot.name})"
                        )
                    }
                    LinearProgressIndicator(
                        progress = { job.progressPercent / 100f },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = {
                                onEvent(
                                    StudioUiEvent.ScheduleSlotClicked(
                                        jobId = job.id,
                                        slot = StudioPublishingSlot.SLOT_1_MIDDAY,
                                    )
                                )
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("📅 Franja 1 (12:30)")
                        }
                        Button(
                            onClick = {
                                onEvent(
                                    StudioUiEvent.ScheduleSlotClicked(
                                        jobId = job.id,
                                        slot = StudioPublishingSlot.SLOT_2_EVENING,
                                    )
                                )
                            },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("📅 Franja 2 (19:30)")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun TopNicheBadge(
    nicheAnalytics: StudioNicheAnalyticsSummary?,
    activeNicheFilter: StudioContentNiche? = null,
    onNicheFilterSelected: (StudioContentNiche?) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(
            verticalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier.padding(12.dp),
        ) {
            val topLabel = nicheAnalytics?.topPerformingNiche?.name ?: "Evaluando ROI por vertical..."
            val totalCop = (nicheAnalytics?.totalRevenueAttributedCents ?: 0L) / 100
            val totalConversions = nicheAnalytics?.totalConversions ?: 0
            Text(text = "🏆 TopNicheBadge — Vertical Líder: $topLabel ($totalConversions ventas • $$totalCop COP)")
            Row(
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Button(onClick = { onNicheFilterSelected(null) }) {
                    Text("${if (activeNicheFilter == null) "✓ " else ""}Todos")
                }
                StudioContentNiche.entries.forEach { niche ->
                    val isSelected = activeNicheFilter == niche
                    Button(onClick = { onNicheFilterSelected(niche) }) {
                        Text("${if (isSelected) "✓ " else ""}${niche.name.take(5)}")
                    }
                }
            }
            val visibleMetrics = nicheAnalytics?.niches?.let { list ->
                activeNicheFilter?.let { filter -> list.filter { it.contentNiche == filter } } ?: list
            } ?: emptyList()
            visibleMetrics.forEach { metric ->
                val highlightPrefix = if (activeNicheFilter == metric.contentNiche) "★ " else "• "
                Text(
                    text = "$highlightPrefix${metric.contentNiche.name}: ${metric.totalVideosCreated} videos | " +
                        "${metric.conversionsCount} ventas | $${metric.revenueAttributedCents / 100} COP " +
                        "(${metric.conversionsPerVideo} conv/video)"
                )
            }
        }
    }
}

/**
 * Stateless Weekly Outfit Organizer Composable with Coil AsyncImage & Lottie Mascot Header (Law 4 UDF).
 */
@Composable
fun WeeklyOutfitCalendarSection(
    selectedDayKey: String,
    weeklyPlan: List<DailyOutfitPlanItem>,
    wardrobeItems: List<WardrobeItem>,
    newGarmentTitle: String,
    onNewGarmentTitleChanged: (String) -> Unit,
    onAddGarmentClicked: () -> Unit,
    onDaySelected: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = modifier.fillMaxWidth(),
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedTextField(
                value = newGarmentTitle,
                onValueChange = onNewGarmentTitleChanged,
                label = { Text("Agregar prenda al armario (Room)") },
                modifier = Modifier.weight(1f),
            )
            Button(onClick = onAddGarmentClicked) {
                Text("+ Prenda")
            }
        }
        wardrobeItems.forEach { garment ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(10.dp),
                ) {
                    AsyncImage(
                        model = garment.imageUri,
                        contentDescription = garment.title,
                        modifier = Modifier.size(48.dp),
                    )
                    Column {
                        Text(text = garment.title)
                        Text(text = "Categoría: ${garment.category.name}")
                    }
                }
            }
        }
        weeklyPlan.forEach { dayItem ->
            Card(
                onClick = { onDaySelected(dayItem.dayKey) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    val prefix = if (dayItem.dayKey == selectedDayKey) "★ " else ""
                    Text(text = "$prefix${dayItem.dayLabel}: ${dayItem.outfitSummary}")
                }
            }
        }
    }
}
