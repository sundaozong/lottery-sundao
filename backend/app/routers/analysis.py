from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import AcIn, ClusterIn, CollisionIn, DaxiaoIn, DaxiaoOut, DaxiaoScoreOut, EchoIn, FormCheckIn, FormCheckOut, HeweiIn, JunzhiIn, JunzhiOut, JunzhiScoreOut, MomentumIn, NeighborIn, ParityIn, PrimeIn, RepeatIn, RoadIn, ShengpingIn, ShengpingOut, ShengpingScoreOut, SpanIn, SumIn, TailIn, ZhenfuIn, ZhenfuOut, ZhenfuScoreOut, ZhongweiIn, ZhongweiOut, ZhongweiScoreOut, ZoneIn
from ..services.affinity import affinity_stats
from ..services.analyze import analyze
from ..services.collision import collide, collide_records
from ..services.echo import find_echoes
from ..services.momentum import momentum_summary, score_momentum
from ..services.neighbor import neighbor_summary, score_neighbor
from ..services.repeat import repeat_pulse, score_repeat
from ..services.cluster import cluster_summary, score_cluster
from ..services.road import road_summary, score_road
from ..services.span import score_span, span_summary
from ..services.parity import parity_summary, score_parity
from ..services.prime import prime_summary, score_prime
from ..services.ac import ac_summary, score_ac
from ..services.hewei import hewei_summary, score_hewei
from ..services.daxiao import daxiao_summary, score_daxiao
from ..services.shengping import score_shengping, shengping_summary
from ..services.zhenfu import score_zhenfu, zhenfu_summary
from ..services.junzhi import score_junzhi, junzhi_summary
from ..services.zhongwei import score_zhongwei, zhongwei_summary
from ..services.tail import score_tail, tail_summary
from ..services.zone import score_zone, zone_summary
from ..services.sum_pulse import score_sum, sum_summary
from ..services.shape import shape_stats
from ..services.form_check import check_form
from ..services.seed import ensure_seed
from ..lotteries import normalize_type

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{lottery_type}/repeat")
def get_repeat(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return repeat_pulse(db, normalize_type(lottery_type), limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/repeat")
def post_repeat(lottery_type: str, body: RepeatIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_repeat(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/momentum")
def get_momentum(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return momentum_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/momentum")
def post_momentum(lottery_type: str, body: MomentumIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_momentum(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/neighbor")
def get_neighbor(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    horizon: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return neighbor_summary(db, normalize_type(lottery_type), limit=limit, horizon=horizon)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/neighbor")
def post_neighbor(lottery_type: str, body: NeighborIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_neighbor(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            horizon=body.horizon,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/span")
def get_span(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return span_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/span")
def post_span(lottery_type: str, body: SpanIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_span(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/cluster")
def get_cluster(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return cluster_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/cluster")
def post_cluster(lottery_type: str, body: ClusterIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_cluster(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/road")
def get_road(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return road_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/road")
def post_road(lottery_type: str, body: RoadIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_road(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/sum")
def get_sum(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return sum_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/sum/score")
def post_sum(lottery_type: str, body: SumIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_sum(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/parity")
def get_parity(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return parity_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/parity/score")
def post_parity(lottery_type: str, body: ParityIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_parity(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/prime")
def get_prime(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return prime_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/prime/score")
def post_prime(lottery_type: str, body: PrimeIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_prime(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/zone")
def get_zone(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return zone_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/zone/score")
def post_zone(lottery_type: str, body: ZoneIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_zone(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/tail")
def get_tail(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return tail_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/tail/score")
def post_tail(lottery_type: str, body: TailIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_tail(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/ac")
def get_ac(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return ac_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/ac/score")
def post_ac(lottery_type: str, body: AcIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_ac(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/hewei")
def get_hewei(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return hewei_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/hewei/score")
def post_hewei(lottery_type: str, body: HeweiIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_hewei(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/daxiao", response_model=DaxiaoOut)
def get_daxiao(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return daxiao_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/daxiao/score", response_model=DaxiaoScoreOut)
def post_daxiao(lottery_type: str, body: DaxiaoIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_daxiao(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/shengping", response_model=ShengpingOut)
def get_shengping(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return shengping_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/shengping/score", response_model=ShengpingScoreOut)
def post_shengping(lottery_type: str, body: ShengpingIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_shengping(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/zhenfu", response_model=ZhenfuOut)
def get_zhenfu(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return zhenfu_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/zhenfu/score", response_model=ZhenfuScoreOut)
def post_zhenfu(lottery_type: str, body: ZhenfuIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_zhenfu(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/junzhi", response_model=JunzhiOut)
def get_junzhi(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return junzhi_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/junzhi/score", response_model=JunzhiScoreOut)
def post_junzhi(lottery_type: str, body: JunzhiIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_junzhi(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/zhongwei", response_model=ZhongweiOut)
def get_zhongwei(
    lottery_type: str,
    limit: int = Query(80, ge=5, le=200),
    short: int = Query(10, ge=5, le=30),
    long: int = Query(50, ge=20, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return zhongwei_summary(
            db,
            normalize_type(lottery_type),
            limit=limit,
            short=short,
            long=long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/zhongwei/score", response_model=ZhongweiScoreOut)
def post_zhongwei(lottery_type: str, body: ZhongweiIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return score_zhongwei(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            short=body.short,
            long=body.long,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/affinity")
def get_affinity(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    seed: str | None = Query(None),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return affinity_stats(db, normalize_type(lottery_type), limit=limit, seed=seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}/shape")
def get_shape(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return shape_stats(db, normalize_type(lottery_type), limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/collision")
def post_collision(lottery_type: str, body: CollisionIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        lottery = normalize_type(lottery_type)
        if body.from_records:
            return collide_records(db, lottery)
        return collide(lottery, [item.model_dump() for item in body.tickets])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/echo")
def post_echo(lottery_type: str, body: EchoIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return find_echoes(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            top=body.top,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _form_ticket(body: FormCheckIn):
    lottery = (body.lottery_type or body.type or "").strip()
    main = body.main
    special = body.special
    if main is None and body.numbers is not None:
        if isinstance(body.numbers, dict):
            main = body.numbers.get("main", body.numbers.get("red", body.numbers.get("front")))
            if special is None:
                special = body.numbers.get("special", body.numbers.get("blue", body.numbers.get("back")))
        else:
            main = body.numbers
    return lottery, main, special


@router.get("/form-check", response_model=FormCheckOut)
def get_form_check(
    type: str = Query(..., description="彩种"),
    numbers: str = Query(..., description="主号，空格或逗号分隔"),
    special: str | None = Query(None, description="特别号，不并进主号指标"),
    limit: int = Query(80, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return check_form(db, type, numbers, special, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/form-check", response_model=FormCheckOut)
def post_form_check(body: FormCheckIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    lottery, main, special = _form_ticket(body)
    try:
        return check_form(db, lottery, main, special, limit=body.limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}")
def get_analysis(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    return analyze(db, normalize_type(lottery_type), limit=limit)
