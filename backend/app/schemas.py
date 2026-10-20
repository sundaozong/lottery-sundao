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


class RecordVerifyIn(BaseModel):
    """apply 默认关闭：先预览差额，确认后再写回奖金。"""
    apply: bool = False
    record_ids: Optional[list[int]] = None


class BasketTicketIn(BaseModel):
    id: Optional[str] = None
    numbers: Any = None
    play: Optional[str] = None
    pick: Optional[int] = None


class BasketVerifyIn(BaseModel):
    """选号篮对照某一期开奖。只读，不写购彩记录。"""
    lottery_type: str
    issue: str = ""
    tickets: list[BasketTicketIn] = Field(default_factory=list)
    multiple: int = 1


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


class ZhongweiIn(BaseModel):
    main: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)
    short: int = Field(default=10, ge=5, le=30)
    long: int = Field(default=50, ge=20, le=200)


class ZhongweiBucket(BaseModel):
    median_value: float
    count: int
    rate: float


class ZhongweiCommon(BaseModel):
    median_value: float
    count: int
    rate: float


class ZhongweiLatest(BaseModel):
    issue: str
    draw_date: str = ""
    main: list[str]
    special: list[str]
    median_value: Optional[float] = None
    special_median_value: Optional[float] = None


class ZhongweiBlock(BaseModel):
    label: str
    sample_size: int
    distribution: list[ZhongweiBucket]
    common: list[ZhongweiCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None


class ZhongweiTicket(BaseModel):
    median_value: Optional[float] = None
    percentile: Optional[float] = None
    typicality: Optional[float] = None
    rarity: Optional[str] = None
    alignment: Optional[str] = None
    note: str = ""


class ZhongweiQuery(BaseModel):
    main: list[str]
    special: list[str]


class ZhongweiOut(BaseModel):
    lottery_type: str
    mode: str
    basis: str
    sample_size: int
    short: int
    long: int
    threshold: float
    distribution: list[ZhongweiBucket]
    common: list[ZhongweiCommon]
    mean: Optional[float] = None
    median: Optional[float] = None
    short_avg: Optional[float] = None
    long_avg: Optional[float] = None
    pulse: Optional[float] = None
    drift: Optional[str] = None
    note: str
    latest_draw: Optional[ZhongweiLatest] = None
    special: Optional[ZhongweiBlock] = None
    data_status: str
    disclaimer: str


class ZhongweiScoreOut(ZhongweiOut):
    query: ZhongweiQuery
    ticket: ZhongweiTicket
    special_ticket: ZhongweiTicket


class CollisionTicket(BaseModel):
    main: Any = None
    special: Any = None


class CollisionIn(BaseModel):
    tickets: list[CollisionTicket] = Field(default_factory=list)
    from_records: bool = False


class PredictConstraints(BaseModel):
    """机选硬条件，字段都可省略。省略或空对象时与原来的按策略抽样一致。

    乐透（双色球、大乐透、七乐彩、快乐八）按号码集合：胆码和杀号去重，奇偶、和值、跨度、大小、区位、连号都看去重后的主号。
    数字彩（福彩3D、排列三、排列五、七星彩）保留位置和重复：奇偶、和值、跨度、大小、区位按各位计，0 为偶，0–4 为小、5–9 为大。
    连号上限只约束乐透主号里的连续号码段，数字彩传入会拒绝。
    """

    include_main: Optional[list[str]] = Field(default=None, description="主号胆码，必须全部出现。乐透按集合，数字彩至少出现一次。")
    exclude_main: Optional[list[str]] = Field(default=None, description="主号杀号，不得出现。")
    include_special: Optional[list[str]] = Field(default=None, description="特别号胆码，必须全部出现。")
    exclude_special: Optional[list[str]] = Field(default=None, description="特别号杀号，不得出现。")
    odd_count: Optional[int] = Field(default=None, description="主号奇数个数，精确值。数字彩按位计并保留重复，0 为偶数。")
    odd_min: Optional[int] = Field(default=None, description="主号奇数个数下限。")
    odd_max: Optional[int] = Field(default=None, description="主号奇数个数上限。")
    sum_min: Optional[int] = Field(default=None, description="主号和值下限。")
    sum_max: Optional[int] = Field(default=None, description="主号和值上限。")
    span_min: Optional[int] = Field(default=None, description="主号跨度下限，跨度为最大号减最小号。")
    span_max: Optional[int] = Field(default=None, description="主号跨度上限。")
    max_consecutive: Optional[int] = Field(default=None, description="主号连续号码段的最大长度，仅乐透。")
    zone_counts: Optional[list[int]] = Field(default=None, description="三区个数，长度 3，分区与区位脉动相同。")
    big_count: Optional[int] = Field(default=None, description="大号个数精确值。分界与大小脉动相同：小于等于中点为小，大于中点为大。")
    big_min: Optional[int] = Field(default=None, description="大号个数下限。")
    big_max: Optional[int] = Field(default=None, description="大号个数上限。")


class PredictIn(BaseModel):
    lottery_type: str
    strategy: str = Field(
        default="hot",
        description="推荐策略：hot 热号、cold 冷号、hybrid 冷热混合、random 纯随机、pulse 脉动综合。pulse 汇总已有脉动打分，仅供娱乐。",
    )
    count: int = Field(default=1, ge=1, le=10)
    weights: Optional[dict[str, float]] = Field(
        default=None,
        description="仅 strategy=pulse 时生效。模块权重，缺省等权。可用键：repeat、momentum、neighbor、span、cluster、road、sum、parity、prime、zone、tail、ac、hewei、daxiao、shengping、zhenfu、junzhi、zhongwei。",
    )
    constraints: Optional[PredictConstraints] = Field(
        default=None,
        description="机选硬条件。只在 hot、cold、hybrid、random 上生效；不传或字段全空时与原来的抽样一致。脉动综合不套用。",
    )


class ReplayTicketIn(BaseModel):
    lottery_type: str
    bet_numbers: Any
    multiple: int = Field(default=1, ge=1, le=99)
    play: Optional[str] = None
    pick: Optional[int] = None
    window: Any = 30


class ReplayStrategyIn(BaseModel):
    lottery_type: str
    strategy: str = "hot"
    constraints: Optional[PredictConstraints] = None
    tickets: int = Field(default=1, ge=1, le=5)
    window: Any = 30
    seed: Optional[int] = None


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


class FormCheckIn(BaseModel):
    """一注体检。lottery_type / type 二选一；main 与 numbers 二选一。"""

    lottery_type: str = ""
    type: str = ""
    main: Any = None
    numbers: Any = None
    special: Any = None
    limit: int = Field(default=80, ge=5, le=200)


class FormCheckMetric(BaseModel):
    key: str
    label: str
    value: Optional[int] = None
    display: str = ""
    compared: str = ""
    percentile: Optional[float] = None
    band_low: Optional[float] = None
    band_high: Optional[float] = None
    band_label: str = ""
    history_min: Optional[int] = None
    history_max: Optional[int] = None
    stance: str
    stance_label: str
    sample_size: int
    note: str = ""


class FormCheckSummary(BaseModel):
    centered: int
    low: int
    high: int
    unavailable: int


class FormCheckQuery(BaseModel):
    main: list[str]
    special: list[str]


class BetExpandZoneIn(BaseModel):
    numbers: Any = None
    bankers: Any = None
    drags: Any = None


class BetExpandIn(BaseModel):
    lottery_type: str
    mode: str = "compound"
    pick: Optional[int] = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=60, ge=0, le=200)
    only_center: bool = False
    band_limit: int = Field(default=80, ge=5, le=200)
    main: Optional[BetExpandZoneIn] = None
    special: Optional[BetExpandZoneIn] = None
    positions: Optional[list[BetExpandZoneIn]] = None


class OmitStat(BaseModel):
    n: str
    current: int
    avg: float
    max: int
    count: int
    rate: float
    ratio: float
    last_issue: Optional[str] = None
    cold: bool


class OmitBoardOut(BaseModel):
    lottery_type: str
    limit: int
    sample_size: int
    sort: str
    cold_rule: str
    main: list[OmitStat]
    special: list[OmitStat]
    data_status: str
    disclaimer: str


class FormCheckOut(BaseModel):
    lottery_type: str
    mode: str
    sample_size: int
    limit: int
    band: str
    query: FormCheckQuery
    metrics: list[FormCheckMetric]
    special_metrics: list[FormCheckMetric]
    summary: FormCheckSummary
    glance: str
    data_status: str
    disclaimer: str
    number_scope: str


class FormCheckBatchTicketIn(BaseModel):
    id: str = ""
    main: Any = None
    numbers: Any = None
    special: Any = None


class FormCheckBatchIn(BaseModel):
    lottery_type: str = ""
    type: str = ""
    limit: int = Field(default=80, ge=5, le=200)
    tickets: list[FormCheckBatchTicketIn] = Field(default_factory=list, max_length=200)


class FormCheckBatchItem(BaseModel):
    id: str = ""
    index: int
    ok: bool
    error: str = ""
    report: Optional[FormCheckOut] = None


class FormCheckBatchOut(BaseModel):
    lottery_type: str
    limit: int
    sample_size: int
    band: str
    data_status: str
    disclaimer: str
    items: list[FormCheckBatchItem]
