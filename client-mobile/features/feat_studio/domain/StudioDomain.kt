package co.superapp.features.feat_studio.domain

enum class StudioJobType {
    VIRAL_SHORT_CLIP,
    AUTO_CAPTIONS_WHISPER,
    AI_OUTFIT_RECOMMENDATION,
    PRODUCT_SHOWCASE_VIDEO,
}

enum class StudioContentNiche {
    DESK_SETUP_UGC,
    RAP_CULTURE_VIRAL,
    YOUTUBE_HIGHLIGHT_CLIP,
    MENSWEAR_LOOKBOOK,
}

enum class StudioPublishingSlot {
    SLOT_1_MIDDAY,
    SLOT_2_EVENING,
}

enum class WardrobeCategory {
    TOP,
    BOTTOM,
    OUTERWEAR,
    SHOES,
}

data class WardrobeItem(
    val id: String,
    val title: String,
    val category: WardrobeCategory,
    val imageUri: String,
    val colorHex: String,
    val linkedCommerceProductId: String? = null,
)

data class DailyOutfitPlanItem(
    val dayKey: String,
    val dayLabel: String,
    val outfitSummary: String,
    val featuredSku: String? = "CHAQUETA-RBR-EDITION",
)

data class StudioMediaJob(
    val id: String,
    val jobType: StudioJobType,
    val contentNiche: StudioContentNiche = StudioContentNiche.DESK_SETUP_UGC,
    val sourceUrlOrPrompt: String,
    val linkedProductId: String?,
    val status: String,
    val progressPercent: Int,
    val resultPayload: Map<String, String>?,
)

data class ScheduledStudioPost(
    val id: String,
    val jobId: String,
    val platform: String,
    val scheduledDate: String,
    val slot: StudioPublishingSlot,
    val conversionsCount: Int,
    val revenueAttributedCents: Long,
    val contentNiche: StudioContentNiche? = null,
)

data class StudioNichePerformanceMetric(
    val contentNiche: StudioContentNiche,
    val totalVideosCreated: Int,
    val totalVideosScheduled: Int,
    val conversionsCount: Int,
    val revenueAttributedCents: Long,
    val conversionsPerVideo: Double,
)

data class StudioNicheAnalyticsSummary(
    val topPerformingNiche: StudioContentNiche?,
    val totalVideosCreated: Int,
    val totalVideosScheduled: Int,
    val totalConversions: Int,
    val totalRevenueAttributedCents: Long,
    val niches: List<StudioNichePerformanceMetric>,
)

interface StudioRepository {
    suspend fun enqueueJob(
        jobType: StudioJobType,
        contentNiche: StudioContentNiche,
        sourceUrlOrPrompt: String,
        linkedProductId: String?,
    ): Result<StudioMediaJob>

    suspend fun listCreatorJobs(): Result<List<StudioMediaJob>>

    suspend fun scheduleJobSlot(
        jobId: String,
        slot: StudioPublishingSlot,
    ): Result<ScheduledStudioPost>

    suspend fun getPublishingSchedule(): Result<List<ScheduledStudioPost>>

    suspend fun getNichePerformanceAnalytics(): Result<StudioNicheAnalyticsSummary>
}
