package co.superapp.features.feat_studio.infrastructure

import co.superapp.core.network.EnqueueMediaJobRequestDto
import co.superapp.core.network.MediaJobResponseDto
import co.superapp.core.network.ScheduleMediaPostRequestDto
import co.superapp.core.network.SuperAppApiService
import co.superapp.features.feat_studio.domain.ScheduledStudioPost
import co.superapp.features.feat_studio.domain.StudioContentNiche
import co.superapp.features.feat_studio.domain.StudioJobType
import co.superapp.features.feat_studio.domain.StudioMediaJob
import co.superapp.features.feat_studio.domain.StudioNicheAnalyticsSummary
import co.superapp.features.feat_studio.domain.StudioNichePerformanceMetric
import co.superapp.features.feat_studio.domain.StudioPublishingSlot
import co.superapp.features.feat_studio.domain.StudioRepository
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext

class RemoteStudioRepository(
    private val api: SuperAppApiService,
    private val ioDispatcher: CoroutineDispatcher,
) : StudioRepository {

    private fun MediaJobResponseDto.toDomain(): StudioMediaJob = StudioMediaJob(
        id = id,
        jobType = StudioJobType.valueOf(jobType),
        contentNiche = runCatching { StudioContentNiche.valueOf(contentNiche) }
            .getOrDefault(StudioContentNiche.DESK_SETUP_UGC),
        sourceUrlOrPrompt = sourceUrlOrPrompt,
        linkedProductId = linkedProductId,
        status = status,
        progressPercent = progressPercent,
        resultPayload = resultPayload,
    )

    override suspend fun enqueueJob(
        jobType: StudioJobType,
        contentNiche: StudioContentNiche,
        sourceUrlOrPrompt: String,
        linkedProductId: String?,
    ): Result<StudioMediaJob> = withContext(ioDispatcher) {
        runCatching {
            api.enqueueMediaJob(
                EnqueueMediaJobRequestDto(
                    jobType = jobType.name,
                    contentNiche = contentNiche.name,
                    sourceUrlOrPrompt = sourceUrlOrPrompt,
                    linkedProductId = linkedProductId,
                )
            ).toDomain()
        }
    }

    override suspend fun listCreatorJobs(): Result<List<StudioMediaJob>> = withContext(ioDispatcher) {
        runCatching {
            api.listMyJobs().map { it.toDomain() }
        }
    }

    override suspend fun scheduleJobSlot(
        jobId: String,
        slot: StudioPublishingSlot,
    ): Result<ScheduledStudioPost> = withContext(ioDispatcher) {
        runCatching {
            val dto = api.scheduleMediaPost(
                jobId = jobId,
                payload = ScheduleMediaPostRequestDto(
                    platform = "TIKTOK",
                    slot = slot.name,
                ),
            )
            ScheduledStudioPost(
                id = dto.id,
                jobId = dto.jobId,
                platform = dto.platform,
                scheduledDate = dto.scheduledDate,
                slot = StudioPublishingSlot.valueOf(dto.slot),
                conversionsCount = dto.conversionsCount,
                revenueAttributedCents = dto.revenueAttributedCents,
            )
        }
    }

    override suspend fun getPublishingSchedule(): Result<List<ScheduledStudioPost>> =
        withContext(ioDispatcher) {
            runCatching {
                api.getPublishingSchedule().scheduledPosts.map { dto ->
                    ScheduledStudioPost(
                        id = dto.id,
                        jobId = dto.jobId,
                        platform = dto.platform,
                        scheduledDate = dto.scheduledDate,
                        slot = StudioPublishingSlot.valueOf(dto.slot),
                        conversionsCount = dto.conversionsCount,
                        revenueAttributedCents = dto.revenueAttributedCents,
                    )
                }
            }
        }

    override suspend fun getNichePerformanceAnalytics(): Result<StudioNicheAnalyticsSummary> =
        withContext(ioDispatcher) {
            runCatching {
                val dto = api.getNichePerformanceAnalytics()
                StudioNicheAnalyticsSummary(
                    topPerformingNiche = dto.topPerformingNiche?.let {
                        runCatching { StudioContentNiche.valueOf(it) }.getOrNull()
                    },
                    totalVideosCreated = dto.totalVideosCreated,
                    totalVideosScheduled = dto.totalVideosScheduled,
                    totalConversions = dto.totalConversions,
                    totalRevenueAttributedCents = dto.totalRevenueAttributedCents,
                    niches = dto.niches.map { n ->
                        StudioNichePerformanceMetric(
                            contentNiche = runCatching { StudioContentNiche.valueOf(n.contentNiche) }
                                .getOrDefault(StudioContentNiche.DESK_SETUP_UGC),
                            totalVideosCreated = n.totalVideosCreated,
                            totalVideosScheduled = n.totalVideosScheduled,
                            conversionsCount = n.conversionsCount,
                            revenueAttributedCents = n.revenueAttributedCents,
                            conversionsPerVideo = n.conversionsPerVideo,
                        )
                    },
                )
            }
        }
}
