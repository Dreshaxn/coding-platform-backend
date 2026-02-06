from datetime import datetime
from pydantic import BaseModel


# ============================================================================
# Response Schemas
# ============================================================================

class UserStatsResponse(BaseModel):
    """Full user stats response"""
    id: int
    user_id: int
    
    # Core stats
    xp: int = 0
    streak: int = 0
    longest_streak: int = 0
    
    # Problem solving breakdown
    problems_solved: int = 0
    easy_solved: int = 0
    medium_solved: int = 0
    hard_solved: int = 0
    
    # Submission metrics
    total_submissions: int = 0
    accepted_submissions: int = 0
    
    # Ranking
    global_rank: int | None = None
    global_percentile: float | None = None
    
    # Contest stats
    contests_participated: int = 0
    best_contest_rank: int | None = None
    
    # Timestamps
    last_submission_at: datetime | None = None
    last_streak_update: datetime | None = None

    class Config:
        from_attributes = True


class UserStatsPublicResponse(BaseModel):
    """Public stats shown on profiles"""
    xp: int = 0
    streak: int = 0
    longest_streak: int = 0
    problems_solved: int = 0
    easy_solved: int = 0
    medium_solved: int = 0
    hard_solved: int = 0
    global_rank: int | None = None
    global_percentile: float | None = None
    contests_participated: int = 0

    class Config:
        from_attributes = True


class UserStatsSummary(BaseModel):
    """Minimal stats for leaderboards/cards"""
    xp: int = 0
    streak: int = 0
    problems_solved: int = 0
    global_rank: int | None = None

    class Config:
        from_attributes = True



