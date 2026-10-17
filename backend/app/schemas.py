from pydantic import BaseModel, Field
from typing import Any, Optional


class DrawOut(BaseModel):
    id: int
    lottery_type: str
    issue: str
    numbers: Any
    draw_date: str = ""
    source: str = "seed"

    class Config:
        from_attributes = True


class RecordIn(BaseModel):
    lottery_type: str
    issue: str = ""
    numbers: Any
    cost: float = 2.0
    prize: float = 0.0
    note: str = ""
    purchased_at: str = ""


class RecordOut(RecordIn):
    id: int

    class Config:
        from_attributes = True


class RecordUpdate(BaseModel):
    lottery_type: Optional[str] = None
    issue: Optional[str] = None
    numbers: Optional[Any] = None
    cost: Optional[float] = None
    prize: Optional[float] = None
    note: Optional[str] = None
    purchased_at: Optional[str] = None


class PrizeCalcIn(BaseModel):
    lottery_type: str
    bet_numbers: Any
    draw_numbers: Any = None
    multiple: int = 1
    play: Optional[str] = None
    pick: Optional[int] = None


class BacktestIn(BaseModel):
    lottery_type: str
    bet_numbers: Any
    multiple: int = 1
    play: Optional[str] = None
    pick: Optional[int] = None
    limit: int = Field(default=30, ge=1, le=200)


class EchoIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=1, le=200)
    top: int = Field(default=8, ge=1, le=20)


class RepeatIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)


class MomentumIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class NeighborIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    horizon: int = Field(default=3, ge=1, le=10)


class SpanIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class ClusterIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class RoadIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class SumIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class CollisionTicket(BaseModel):
    main: Any = None
    special: Any = None


class CollisionIn(BaseModel):
    tickets: list[CollisionTicket] = Field(default_factory=list)
    from_records: bool = False


class PredictIn(BaseModel):
    lottery_type: str
    strategy: str = "hot"  # hot | cold | random | hybrid
    count: int = Field(default=1, ge=1, le=10)


class SettingsOut(BaseModel):
    crawl_interval_minutes: int = 60
    subscribed_types: list[str] = []
    mail_enabled: bool = False
    mail_to: str = ""
    smtp_configured: bool = False


class SettingsIn(BaseModel):
    crawl_interval_minutes: Optional[int] = None
    subscribed_types: Optional[list[str]] = None
    mail_enabled: Optional[bool] = None
    mail_to: Optional[str] = None


class MailTestIn(BaseModel):
    to: Optional[str] = None


class MailPredictIn(BaseModel):
    to: Optional[str] = None
    lottery_type: str
    strategy: str = ""
    recommendations: list[Any] = []
