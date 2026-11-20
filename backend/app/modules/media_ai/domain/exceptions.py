"""Pure domain exceptions for the Media AI bounded context (Law 3)."""


class MediaAiDomainError(Exception):
    """Base domain exception for the Media AI module."""


class MediaJobNotFoundError(MediaAiDomainError):
    """Raised when a MediaJob cannot be found by ID."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"MediaJob '{job_id}' was not found.")
        self.job_id = job_id


class InvalidJobStateTransitionError(MediaAiDomainError):
    """Raised when attempting an illegal state transition on a MediaJob."""

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            f"Cannot transition MediaJob from '{current_status}' to '{target_status}'."
        )
        self.current_status = current_status
        self.target_status = target_status


class LinkedProductNotFoundError(MediaAiDomainError):
    """Raised when a linked_product_id does not exist or is inactive in Commerce."""

    def __init__(self, product_id: str) -> None:
        super().__init__(
            f"Linked product '{product_id}' was not found or is inactive in the catalog."
        )
        self.product_id = product_id


class InvalidMediaSourceError(MediaAiDomainError):
    """Raised when source_url_or_prompt or progress_percent is invalid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SlotAlreadyBookedError(MediaAiDomainError):
    """Raised when a creator tries to book two posts in the same date and publishing slot."""

    def __init__(self, scheduled_date: str, slot: str) -> None:
        super().__init__(
            f"Publishing slot '{slot}' on '{scheduled_date}' is already booked."
        )
        self.scheduled_date = scheduled_date
        self.slot = slot
