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


class ParityIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class PrimeIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class ZoneIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class TailIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class AcIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class HeweiIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class DaxiaoIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class DaxiaoBoundary(BaseModel):
    lo: int
    hi: int
    mid: int


class DaxiaoBucket(BaseModel):
    big_count: int
    count: int
    rate: float


class DaxiaoCommon(BaseModel):
    big_count: int
    small_count: int
    ratio: str
    count: int
    rate: float


class DaxiaoLatest(BaseModel):
    issue: str
    draw_date: str = ""
    main: list[str]
    special: list[str]
    big_count: int
    small_count: int
    special_big_count: Optional[int] = None
    special_small_count: Optional[int] = None


class DaxiaoBlock(BaseModel):
    label: str
    sample_size: int
    distribution: list[DaxiaoBucket]
    common: list[DaxiaoCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None
    boundary: DaxiaoBoundary


class DaxiaoTicket(BaseModel):
    big_count: Optional[int] = None
    small_count: Optional[int] = None
    percentile: Optional[float] = None
    typicality: Optional[float] = None
    rarity: Optional[str] = None
    alignment: Optional[str] = None
    note: str = ""


class DaxiaoQuery(BaseModel):
    main: list[str]
    special: list[str]


class DaxiaoOut(BaseModel):
    lottery_type: str
    mode: str
    basis: str
    sample_size: int
    short: int
    long: int
    threshold: float
    distribution: list[DaxiaoBucket]
    common: list[DaxiaoCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None
    boundary: DaxiaoBoundary
    note: str
    latest_draw: Optional[DaxiaoLatest] = None
    special: Optional[DaxiaoBlock] = None
    data_status: str
    disclaimer: str


class DaxiaoScoreOut(DaxiaoOut):
    query: DaxiaoQuery
    ticket: DaxiaoTicket
    special_ticket: DaxiaoTicket


class ShengpingIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class ShengpingBucket(BaseModel):
    rise_count: int
    count: int
    rate: float


class ShengpingCommon(BaseModel):
    rise_count: int
    flat_count: int
    fall_count: int
    pattern: str
    count: int
    rate: float


class ShengpingLatest(BaseModel):
    issue: str
    draw_date: str = ""
    main: list[str]
    special: list[str]
    rise_count: Optional[int] = None
    flat_count: Optional[int] = None
    fall_count: Optional[int] = None
    pattern: Optional[str] = None
    special_rise_count: Optional[int] = None
    special_flat_count: Optional[int] = None
    special_fall_count: Optional[int] = None
    special_pattern: Optional[str] = None


class ShengpingBlock(BaseModel):
    label: str
    sample_size: int
    distribution: list[ShengpingBucket]
    common: list[ShengpingCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None


class ShengpingTicket(BaseModel):
    rise_count: Optional[int] = None
    flat_count: Optional[int] = None
    fall_count: Optional[int] = None
    pattern: Optional[str] = None
    percentile: Optional[float] = None
    typicality: Optional[float] = None
    rarity: Optional[str] = None
    alignment: Optional[str] = None
    note: str = ""


class ShengpingQuery(BaseModel):
    main: list[str]
    special: list[str]


class ShengpingOut(BaseModel):
    lottery_type: str
    mode: str
    basis: str
    sample_size: int
    short: int
    long: int
    threshold: float
    distribution: list[ShengpingBucket]
    common: list[ShengpingCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None
    note: str
    latest_draw: Optional[ShengpingLatest] = None
    special: Optional[ShengpingBlock] = None
    data_status: str
    disclaimer: str


class ShengpingScoreOut(ShengpingOut):
    query: ShengpingQuery
    ticket: ShengpingTicket
    special_ticket: ShengpingTicket


class ZhenfuIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class ZhenfuBucket(BaseModel):
    amplitude_sum: int
    count: int
    rate: float


class ZhenfuCommon(BaseModel):
    amplitude_sum: int
    count: int
    rate: float


class ZhenfuLatest(BaseModel):
    issue: str
    draw_date: str = ""
    main: list[str]
    special: list[str]
    amplitude_sum: Optional[int] = None
    special_amplitude_sum: Optional[int] = None


class ZhenfuBlock(BaseModel):
    label: str
    sample_size: int
    distribution: list[ZhenfuBucket]
    common: list[ZhenfuCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None


class ZhenfuTicket(BaseModel):
    amplitude_sum: Optional[int] = None
    percentile: Optional[float] = None
    typicality: Optional[float] = None
    rarity: Optional[str] = None
    alignment: Optional[str] = None
    note: str = ""


class ZhenfuQuery(BaseModel):
    main: list[str]
    special: list[str]


class ZhenfuOut(BaseModel):
    lottery_type: str
    mode: str
    basis: str
    sample_size: int
    short: int
    long: int
    threshold: float
    distribution: list[ZhenfuBucket]
    common: list[ZhenfuCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None
    note: str
    latest_draw: Optional[ZhenfuLatest] = None
    special: Optional[ZhenfuBlock] = None
    data_status: str
    disclaimer: str


class ZhenfuScoreOut(ZhenfuOut):
    query: ZhenfuQuery
    ticket: ZhenfuTicket
    special_ticket: ZhenfuTicket


class JunzhiIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class JunzhiBucket(BaseModel):
    mean_value: float
    count: int
    rate: float


class JunzhiCommon(BaseModel):
    mean_value: float
    count: int
    rate: float


class JunzhiLatest(BaseModel):
    issue: str
    draw_date: str = ""
    main: list[str]
    special: list[str]
    mean_value: Optional[float] = None
    special_mean_value: Optional[float] = None


class JunzhiBlock(BaseModel):
    label: str
    sample_size: int
    distribution: list[JunzhiBucket]
    common: list[JunzhiCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None


class JunzhiTicket(BaseModel):
    mean_value: Optional[float] = None
    percentile: Optional[float] = None
    typicality: Optional[float] = None
    rarity: Optional[str] = None
    alignment: Optional[str] = None
    note: str = ""


class JunzhiQuery(BaseModel):
    main: list[str]
    special: list[str]


class JunzhiOut(BaseModel):
    lottery_type: str
    mode: str
    basis: str
    sample_size: int
    short: int
    long: int
    threshold: float
    distribution: list[JunzhiBucket]
    common: list[JunzhiCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None
    note: str
    latest_draw: Optional[JunzhiLatest] = None
    special: Optional[JunzhiBlock] = None
    data_status: str
    disclaimer: str


class JunzhiScoreOut(JunzhiOut):
    query: JunzhiQuery
    ticket: JunzhiTicket
    special_ticket: JunzhiTicket


class CollisionTicket(BaseModel):
    main: Any = None
    special: Any = None


class CollisionIn(BaseModel):
    tickets: list[CollisionTicket] = Field(default_factory=list)
    from_records: bool = False


class PredictIn(BaseModel):
    lottery_type: str
    strategy: str = Field(
        default="hot",
        description="推荐策略：hot 热号、cold 冷号、hybrid 冷热混合、random 纯随机、pulse 脉动综合。pulse 汇总已有脉动打分，仅供娱乐。",
    )
    count: int = Field(default=1, ge=1, le=10)
    weights: Optional[dict[str, float]] = Field(
        default=None,
        description="仅 strategy=pulse 时生效。模块权重，缺省等权。可用键：repeat、momentum、neighbor、span、cluster、road、sum、parity、prime、zone、tail、ac、hewei、daxiao、shengping、zhenfu、junzhi。",
    )


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
